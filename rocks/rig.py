"""2D stick-figure rig: skeleton, named pose library, easing blends, two-bone IK (D-14).

Angles are in degrees. Limb angles are absolute, measured from straight down, positive = toward the
direction the figure faces. Joint angles (elbow, knee) are relative to the parent bone; knees bend
with negative values, elbows with positive ones. The torso angle is measured from straight up,
positive = leaning forward. Coordinates are screen pixels, y down.
"""
from dataclasses import dataclass, field, replace
import numpy as np
import skia

from .ink import circle

# bone lengths in px at scale 1 (matches the approved sample figure: ~150 px tall)
TORSO, NECK, HEAD_R = 58, 6, 22
UPPER_ARM, FOREARM = 30, 30
THIGH, SHIN = 36, 36


def _clear_head(canvas, head, r):
    """Inside the head, wipe out the thin dark lines already drawn behind it: the pixels there are replaced by a
    dilated (lines removed) and softened copy of themselves, so sky and sand still show through."""
    surf = canvas.getSurface()
    if surf is None:
        return
    m = canvas.getTotalMatrix()
    dev = m.mapRect(skia.Rect.MakeLTRB(head[0] - r, head[1] - r, head[0] + r, head[1] + r))
    pad = int(m.getScaleX() * r) + 8
    box = skia.IRect.MakeLTRB(max(0, int(dev.left()) - pad), max(0, int(dev.top()) - pad),
                              min(surf.width(), int(dev.right()) + pad), min(surf.height(), int(dev.bottom()) + pad))
    if box.isEmpty():
        return
    img = surf.makeImageSnapshot(box)
    rad = max(2, int(round(m.getScaleX() * r * 0.5)))         # wider than a line and than the rocks behind him
    paint = skia.Paint(ImageFilter=skia.ImageFilters.Blur(rad * 0.7, rad * 0.7,
                                                          input=skia.ImageFilters.Dilate(rad, rad)))
    canvas.save()
    canvas.clipPath(skia.Path.Circle(head[0], head[1], r * 0.98), doAntiAlias=True)
    canvas.resetMatrix()
    canvas.drawImage(img, box.left(), box.top(), paint=paint)
    canvas.restore()


@dataclass(frozen=True)
class Pose:
    torso: float = 0.0
    head: float = 0.0
    arm_f: tuple = (6.0, 10.0)     # (shoulder, elbow) for the front arm
    arm_b: tuple = (-6.0, 10.0)
    leg_f: tuple = (4.0, -2.0)     # (hip, knee)
    leg_b: tuple = (-4.0, -2.0)
    grounded: bool = True          # False: hip height is given explicitly (e.g. sitting on a chair)
    # Planted legs: hip height above the ground plus foot x offsets (forward = +). A leg whose foot
    # offset is set is solved with IK so the foot stays on the ground; otherwise its angles are used.
    hip_h: float | None = None
    foot_f: float | None = None
    foot_b: float | None = None
    # Front hand planted on the ground at this x offset (forward = +), solved with IK (e.g. writing in sand).
    hand_ground: float | None = None


POSES = {
    "stand": Pose(),
    "look_up": Pose(torso=-8, head=-35, arm_f=(4, 6), arm_b=(-4, 6)),
    "crouch": Pose(torso=38, head=-18, arm_f=(40, 20), arm_b=(25, 25), hip_h=36, foot_f=22, foot_b=-16),
    # bent deep enough that the hand reaches the sand 6..87 px in front of him (scale 1)
    "place_rock": Pose(torso=72, head=-28, arm_f=(70, 10), arm_b=(30, 30), hip_h=40, foot_f=26, foot_b=-30),
    "hold_rock": Pose(torso=4, head=-12, arm_f=(55, 70), arm_b=(-6, 10)),
    "sit": Pose(torso=4, head=-4, arm_f=(20, 65), arm_b=(15, 70), leg_f=(90, -90), leg_b=(86, -86), grounded=False),
    # lying on his back in the sand (grounded=False: hip height given by the scene, close to the ground)
    "lie": Pose(torso=-88, head=-2, arm_f=(-80, 10), arm_b=(-95, 5), leg_f=(92, -4), leg_b=(88, -2), grounded=False),
    # sitting on the ground, knees up, forearms on the knees
    "sit_ground": Pose(torso=-8, head=-6, arm_f=(40, 55), arm_b=(30, 60), hip_h=4, foot_f=34, foot_b=30),
    "shrug": Pose(torso=-3, head=-10, arm_f=(12, 78), arm_b=(4, 86)),          # forearms forward, palms up
    "write_in_sand": Pose(torso=58, head=-35, arm_b=(5, 60), leg_b=(34, -124), hip_h=30, foot_f=30, hand_ground=52),
}


def walk(phase, stride=24.0):
    """Walk cycle pose at phase (radians). stride = hip swing amplitude in degrees."""
    s = np.sin(phase)
    lift_f = max(0.0, np.cos(phase))       # knee bends while the leg swings forward
    lift_b = max(0.0, -np.cos(phase))
    return Pose(torso=5, head=-3,
                leg_f=(stride * s, -8 - 38 * lift_f), leg_b=(-stride * s, -8 - 38 * lift_b),
                arm_f=(-18 * s, 18), arm_b=(18 * s, 18))


def walk_distance_per_cycle(stride=24.0):
    """How far the ground moves under one full walk cycle, so feet do not slide much."""
    return 4 * (THIGH + SHIN) * np.sin(np.radians(stride)) * 0.85


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def planted(p: Pose) -> Pose:
    """The same standing pose with explicit hip height and foot offsets, computed from its leg angles, so it can be
    blended smoothly with planted poses (crouch, place_rock) instead of switching modes halfway."""
    if p.hip_h is not None or not p.grounded:
        return p
    feet = []
    for a1, a2 in (p.leg_f, p.leg_b):
        knee = np.array([np.sin(np.radians(a1)), np.cos(np.radians(a1))]) * THIGH
        feet.append(knee + np.array([np.sin(np.radians(a1 + a2)), np.cos(np.radians(a1 + a2))]) * SHIN)
    return replace(p, hip_h=float(max(feet[0][1], feet[1][1])), foot_f=float(feet[0][0]), foot_b=float(feet[1][0]))


def blend(a: Pose, b: Pose, t: float) -> Pose:
    if (a.hip_h is None) != (b.hip_h is None):          # one planted, one not: plant both, so nothing pops
        a, b = planted(a), planted(b)
    t = ease(t)
    mix = lambda x, y: x + (y - x) * t
    tup = lambda x, y: (mix(x[0], y[0]), mix(x[1], y[1]))
    return Pose(torso=mix(a.torso, b.torso), head=mix(a.head, b.head),
                arm_f=tup(a.arm_f, b.arm_f), arm_b=tup(a.arm_b, b.arm_b),
                leg_f=tup(a.leg_f, b.leg_f), leg_b=tup(a.leg_b, b.leg_b),
                grounded=b.grounded if t > 0.5 else a.grounded,
                hip_h=_mix_opt(a.hip_h, b.hip_h, t), foot_f=_mix_opt(a.foot_f, b.foot_f, t),
                foot_b=_mix_opt(a.foot_b, b.foot_b, t), hand_ground=_mix_opt(a.hand_ground, b.hand_ground, t))


def _mix_opt(x, y, t):
    if x is None or y is None:
        return y if t > 0.5 else x
    return x + (y - x) * t


def two_bone_ik(root, target, l1, l2, bend):
    """Middle joint position so that root→mid→end reaches target. bend=+1/-1 chooses the side."""
    root, target = np.asarray(root, float), np.asarray(target, float)
    d = target - root
    dist = np.clip(np.linalg.norm(d), 1e-6, l1 + l2 - 1e-3)
    d_hat = d / (np.linalg.norm(d) + 1e-9)
    a = (l1 ** 2 - l2 ** 2 + dist ** 2) / (2 * dist)
    h = np.sqrt(max(l1 ** 2 - a ** 2, 0))
    perp = np.array([-d_hat[1], d_hat[0]]) * bend
    mid = root + d_hat * a + perp * h
    end = root + d_hat * dist
    return mid, end


@dataclass
class Figure:
    """A posed figure in the world: where it stands, which way it faces, how big it is."""
    x: float
    ground: float
    pose: Pose = field(default_factory=Pose)
    facing: int = -1          # -1 = faces left (toward the rock rows), +1 = right
    scale: float = 1.0
    hip_y: float | None = None   # used when pose.grounded is False
    hand_target: tuple | None = None   # IK target for the front hand (world coords)

    def joints(self):
        p, s, f = self.pose, self.scale, self.facing
        down = lambda ang: np.array([np.sin(np.radians(ang)) * f, np.cos(np.radians(ang))])
        up = lambda ang: np.array([np.sin(np.radians(ang)) * f, -np.cos(np.radians(ang))])
        hip = np.zeros(2)
        legs = {}
        for name, (a1, a2), dx in (("f", p.leg_f, p.foot_f), ("b", p.leg_b, p.foot_b)):
            if p.hip_h is not None and dx is not None:     # planted: IK, knee points forward
                legs[name] = two_bone_ik(hip, (dx * f * s, p.hip_h * s), THIGH * s, SHIN * s, bend=-f)
            else:
                knee = hip + down(a1) * THIGH * s
                legs[name] = (knee, knee + down(a1 + a2) * SHIN * s)
        neck = hip + up(p.torso) * TORSO * s
        head = neck + up(p.torso + p.head) * (NECK + HEAD_R) * s
        shoulder = hip + (neck - hip) * 0.85
        arms = {}
        for name, (a1, a2) in (("f", p.arm_f), ("b", p.arm_b)):
            elbow = shoulder + down(a1) * UPPER_ARM * s
            hand = elbow + down(a1 + a2) * FOREARM * s
            arms[name] = (elbow, hand)
        # place in the world: grounded poses stand on their lowest foot
        if p.hip_h is not None:
            origin = np.array([self.x, self.ground - p.hip_h * s])
        elif p.grounded:
            lowest = max(legs["f"][1][1], legs["b"][1][1])
            origin = np.array([self.x, self.ground - lowest])
        else:
            origin = np.array([self.x, self.hip_y if self.hip_y is not None else self.ground - (THIGH + SHIN) * s * 0.55])
        J = {"hip": hip, "neck": neck, "head": head, "shoulder": shoulder,
             "knee_f": legs["f"][0], "foot_f": legs["f"][1], "knee_b": legs["b"][0], "foot_b": legs["b"][1],
             "elbow_f": arms["f"][0], "hand_f": arms["f"][1], "elbow_b": arms["b"][0], "hand_b": arms["b"][1]}
        J = {k: v + origin for k, v in J.items()}
        if p.hand_ground is not None and self.hand_target is None:
            target = (self.x + p.hand_ground * f * s, self.ground - 2 * s)
            J["elbow_f"], J["hand_f"] = two_bone_ik(J["shoulder"], target, UPPER_ARM * s, FOREARM * s, bend=f)
        if self.hand_target is not None:
            J["elbow_f"], J["hand_f"] = two_bone_ik(J["shoulder"], self.hand_target, UPPER_ARM * s, FOREARM * s,
                                                    bend=f)
        return J

    def strokes(self):
        J = self.joints()
        return [
            [J["hip"], J["neck"]],
            [J["shoulder"], J["elbow_b"], J["hand_b"]],
            [J["hip"], J["knee_b"], J["foot_b"]],
            [J["hip"], J["knee_f"], J["foot_f"]],
            [J["shoulder"], J["elbow_f"], J["hand_f"]],
        ], J["head"], HEAD_R * self.scale

    def draw(self, canvas, pens, boil, seed=300, width=3.0):
        strokes, head, r = self.strokes()
        # line boil scales with the figure: on a tiny figure a full-size wobble reads as moving limbs
        k = min(1.0, self.scale)
        for i, st in enumerate(strokes):
            pens.line(canvas, st, width * self.scale ** 0.5, seed + i * 11 + boil, amp=0.9 * k)
        _clear_head(canvas, head, r)              # the head hides the horizon and rocks behind it
        pens.line(canvas, circle(head, r), width * self.scale ** 0.5, seed + 99 + boil, amp=0.7 * k)

    def with_pose(self, pose):
        return replace(self, pose=pose)


class BlendFigure(Figure):
    """Blend two posed figures by joint *positions* (not angles). Use for transitions between very different
    poses (lying -> sitting -> standing), where angle blending would pop when the grounding mode changes."""

    def __init__(self, a: Figure, b: Figure, t: float):
        super().__init__(x=a.x + (b.x - a.x) * ease(t), ground=a.ground, pose=a.pose, facing=a.facing, scale=a.scale)
        self.a, self.b, self.t = a, b, ease(t)

    def joints(self):
        ja, jb = self.a.joints(), self.b.joints()
        return {k: ja[k] + (jb[k] - ja[k]) * self.t for k in ja}
