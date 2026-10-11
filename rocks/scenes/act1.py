"""Act 1 "Loneliness & discovery" (spec §1, D-27 budgets): waking up, walking the endless desert, time passing,
and rederiving mathematics and physics in the sand (time-lapse takes, D-30)."""
from dataclasses import replace
import numpy as np
import skia

from ..config import W, H
from ..rig import Figure, BlendFigure, POSES, walk, blend, walk_distance_per_cycle
from .common import bake, Camera, horizon, smooth, night_overlay, night_tools, full, shadow, day, SUN_DAY
from .desert import scattered_rocks, static_desert, wake_rocks, sleeper, WAKE_X
from .writing import Takes

GY = H * 0.84


# ---------- 1.1 waking up ---------------------------------------------------------------------

CAMERA_IN = 4.0       # s: the move from the wide desert down to him, before he wakes at 4.2 s


def wake_up(ctx, shot):
    pens = ctx.pens
    bg = static_desert(ctx, wake_rocks(), zoom=1.8)
    x = WAKE_X

    def fig_at(t):
        lie = sleeper()
        sit = Figure(x=x, ground=GY, pose=POSES["sit_ground"], facing=-1)
        crouch = Figure(x=x, ground=GY, pose=POSES["crouch"], facing=-1)
        stand = Figure(x=x, ground=GY, pose=POSES["stand"], facing=-1)
        if t < 4.2:
            return lie
        if t < 5.6:
            return BlendFigure(lie, sit, (t - 4.2) / 1.4)
        if t < 6.6:
            return sit
        if t < 7.4:
            return BlendFigure(sit, crouch, (t - 6.6) / 0.8)
        if t < 8.3:
            return BlendFigure(crouch, stand, (t - 7.4) / 0.9)
        facing = 1 if 8.6 <= t < 10.1 else -1                          # looks around: right, then back ("I don't know
        up = shot.duration - 1.3                                       # how I got here" starts after the first turn)
        return Figure(x=x, ground=GY, pose=blend(POSES["stand"], POSES["look_up"], (t - up) / 0.5), facing=facing)

    def draw(c, t, boil):
        # starts on the cold open's last frame (the whole desert), then moves down and in to him while he sleeps
        m = smooth(t / CAMERA_IN)
        zoom = 1.8 - 0.35 * smooth(t / shot.duration)
        with Camera(c) as cam:
            cam.look(1 + (zoom - 1) * m, W / 2 + (x - 20 - W / 2) * m, H / 2 + (GY - 70 - H / 2) * m)
            full(c, bg[boil])
            c.drawOval(skia.Rect.MakeXYWH(x - 75, GY - 5, 150, 10), pens.shadow)
            fig_at(t).draw(c, pens, boil)
    return draw


# ---------- 1.2 never hungry, never thirsty ------------------------------------------------

def deadpan_stand(ctx, shot):
    """Continues 1.1 without a visible cut: the same rocks and spot, the camera starts on 1.1's last frame and drifts
    a little closer, and he comes down from looking up before the shrug on "nice"."""
    pens = ctx.pens
    bg = static_desert(ctx, wake_rocks(), zoom=1.6)
    x = WAKE_X
    shrug = shot.cues["nice"]

    def draw(c, t, boil):
        u = smooth(t / 1.5)                                            # from 1.1's framing to a closer one
        settle = smooth(t / 0.6)                                       # from 1.1's last pose (looking up) to standing
        k = smooth((t - shrug + 0.2) / 0.5) * (1 - smooth((t - shrug - 1.6) / 0.6))
        pose = blend(blend(POSES["look_up"], POSES["stand"], settle), POSES["shrug"], k)
        with Camera(c) as cam:
            cam.look(1.45 + 0.15 * u, x - 20 - 20 * u, GY - 70 - 30 * u)
            full(c, bg[boil])
            c.drawOval(skia.Rect.MakeXYWH(x - 75, GY - 5, 150, 10), pens.shadow)
            Figure(x=x, ground=GY, pose=pose, facing=-1).draw(c, pens, boil)
    return draw


# ---------- 1.3 the walk: sand, rocks, horizon ------------------------------------------------

def long_walk(ctx, shot):
    pens = ctx.pens
    plate = ctx.desert()
    bg = bake(lambda c, b: (full(c, plate), horizon(c, boil=b)))
    rocks = scattered_rocks(110, -W, 3 * W, 13)
    look = shot.cues["following"]
    speed = 70.0                                   # px/s of the nearest ground plane
    cyc = speed / walk_distance_per_cycle()
    x = W * 0.5
    stop = look - 0.5

    def ground_shift(t):
        """How far the world has moved; he slows to a stop before looking back, then walks on."""
        if t < stop:
            return speed * t
        if t < stop + 2.2:
            return speed * stop + speed * 0.4 * (1 - (1 - min(1, (t - stop) / 0.6)) ** 2) * 0.6
        return speed * stop + speed * 0.24 + speed * (t - stop - 2.2)

    def draw(c, t, boil):
        shift = ground_shift(t)
        full(c, bg[boil])
        for i, r in enumerate(rocks):
            rx = (r[0] + shift * r[5]) % (4 * W) - W                  # parallax: near rocks move faster
            if -40 < rx < W + 40:
                pens.rock(c, rx, r[1], r[2], r[3], r[4], seed=7100 + i, boil=boil)
        stand = replace(POSES["stand"], head=-6)
        stride = walk(2 * np.pi * cyc * stop)                           # the step he stops in and walks on from
        if t < stop or t >= stop + 2.2:
            ph = 2 * np.pi * cyc * (t if t < stop else t - 2.2)
            fig = Figure(x=x, ground=GY, pose=walk(ph), facing=-1)
        else:
            facing = 1 if stop + 0.5 <= t < stop + 1.8 else -1        # looks back at the horizon behind him
            pose = blend(stride, stand, (t - stop) / 0.3)               # comes to a halt ...
            if t >= stop + 1.9:
                pose = blend(stand, stride, (t - stop - 1.9) / 0.3)     # ... and sets off again
            fig = Figure(x=x, ground=GY, pose=pose, facing=facing)
        c.drawOval(skia.Rect.MakeXYWH(x - 60, GY - 5, 130, 10), pens.shadow)
        fig.draw(c, pens, boil)

    # footsteps on the walk cycle's foot contacts
    events, k = [], 0
    while True:
        tc = (0.5 + k) / (2 * cyc)
        real = tc if tc < stop else tc + 2.2
        if real >= shot.duration:
            break
        if not (stop <= real < stop + 2.2):
            events.append({"name": "footstep_sand", "at": round(real, 3), "gain_db": -13})
        k += 1
    draw.events = events
    return draw


# ---------- 1.4 "It goes on forever": pull back until he is a dot -----------------------------

def goes_on_forever(ctx, shot):
    pens = ctx.pens
    bg = static_desert(ctx, scattered_rocks(160, 0, W, 14), zoom=3.2)
    x, gy = W * 0.46, H * 0.72
    cyc = 10.0 / (walk_distance_per_cycle() * 0.5)            # he moves 10 px/s at scale 0.5: feet stay planted

    # zoom about one fixed point: he starts in the middle of the frame, the end is the whole picture, and the camera
    # moves one way only (aiming at him instead, the edge clamp took over in y, then in x: three changes of direction)
    z0 = 3.2
    fx, fy = (z0 * x - W / 2) / (z0 - 1), (z0 * (gy - 35) - H / 2) / (z0 - 1)

    def draw(c, t, boil):
        z = z0 ** (1 - smooth(t / shot.duration))                     # 3.2x -> 1x
        with Camera(c) as cam:
            cam.look(z, fx, fy, anchor=(fx, fy))
            full(c, bg[boil])
            shadow(c, pens, x - 10 * t, gy - 2.5, w=65)
            Figure(x=x - 10 * t, ground=gy, pose=walk(2 * np.pi * cyc * t), scale=0.5, facing=-1
                   ).draw(c, pens, boil, width=2.4)
    return draw


# ---------- 1.5 time to think: days and nights, faster and faster -----------------------------

def time_to_think(ctx, shot):
    pens = ctx.pens
    bg = static_desert(ctx, scattered_rocks(40, 0, W, 15))
    stars, star, night = night_tools()
    sky = ctx.desert_sky()
    x = W * 0.55

    def draw(c, t, boil):
        cycles = 0.175 * t + 0.14 * t * t                              # accelerating days (up to ~2 a second)
        n, sun = day(cycles)
        with Camera(c) as cam:
            cam.look(1.35, x, GY - 80)
            full(c, bg[boil])
            Figure(x=x, ground=GY, pose=POSES["sit_ground"], facing=-1).draw(c, pens, boil)
        night_overlay(c, n, stars, star, night, cam, sky, sun)
    return draw


# ---------- 1.6 + 1.7 rederiving mathematics and physics (time-lapse) ------------------------

# one shared field of writing for 1.6 and 1.7: counting first, then algebra, calculus, physics
# laid out on lines in the sand (depth offsets 8/30/52/74/96 px), no two entries on a line overlap, and each
# one is fully in frame while it is written (the camera of 1.6/1.7 is zoomed in)
MATH = [("|||| ||", 0.36, 8, 2.0), ("1 + 1 = 2", 0.55, 30, 1.8), ("π = 3.2", 0.18, 52, 1.4),
        ("a² + b² = c²", 0.40, 74, 1.6)]
PHYSICS = [("d/dx eˣ = eˣ", 0.57, 8, 1.5), ("∫ x dx = x²/2", 0.12, 30, 1.3), ("F = G m₁m₂ / r²", 0.22, 96, 1.2),
           ("E = mc²", 0.68, 52, 1.0), ("iħ ∂ψ/∂t = Ĥψ", 0.10, 74, 1.0), ("Gμν = 8πG Tμν", 0.60, 96, 0.9),
           ("π = 3.14159…", 0.32, 52, 1.0)]           # the correction, right after the crossed-out 3.2


def _takes(entries, t0):
    return Takes([(txt, W * fx, dy, dur) for txt, fx, dy, dur in entries], t0=t0, ground=H * 0.66, scale=1.0,
                 font_size=40)


CAM_16 = (1.8, W * 0.44, H * 0.7)                    # 1.6's framing; 1.7 starts on it


def cam_17(t, dur):
    """1.7's framing: from 1.6's, it settles on a closer view of the field, then widens to show all of it."""
    k = smooth(t / dur)
    z, cx, cy = 1.45 - 0.45 * k, W * (0.44 + 0.06 * k), H * (0.72 - 0.1 * k)
    m = smooth(t / 1.0)
    return tuple(a + (b - a) * m for a, b in zip(CAM_16, (z, cx, cy)))


def pickup_rock():
    """The rock he picks up in 1.8: a few steps left of where he kneels at his last equation. It lies there in
    1.6 and 1.7 already."""
    kneel = _takes(MATH + PHYSICS, -100).figure(len(MATH + PHYSICS) - 1, 1e9)
    return np.array([kneel.x - 62 - 130, H * 0.84])


def counting(ctx, shot):
    pens = ctx.pens
    bg = static_desert(ctx, [], zoom=1.8)
    tk = _takes(MATH, 0.3)
    rock = pickup_rock()

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(*CAM_16)
            full(c, bg[boil])
            pens.rock(c, rock[0], rock[1], 13, 9, 0.3, seed=7777, boil=boil)
            tk.draw_text(c, t, pens, boil)
            tk.draw_figures(c, t, pens, boil)
    draw.events = [{"name": "sand_scratch", "at": round(s, 3), "gain_db": -16} for s in tk.starts]
    return draw


def physics(ctx, shot):
    pens = ctx.pens
    bg = static_desert(ctx, [], zoom=1.8)
    stars, star, night = night_tools()
    sky = ctx.desert_sky()
    before = _takes(MATH, -100)                        # everything from 1.6 is already written
    tk = _takes(PHYSICS, 0.6)                          # first take fades in from 0, as 1.6's writer fades out
    fix = shot.cues["fixed"]
    before.strikes[2] = fix - 0.3                      # "π = 3.2" gets crossed out...
    # ...and the correction "π = 3.14159…" (last take) is timed to be written right after
    tk.starts[-1] = fix + 0.2

    last_16 = before.figure(len(before.takes) - 1, 1e9)    # 1.6 ends with him kneeling at his last line
    rock = pickup_rock()

    def draw(c, t, boil):
        cycles = 0.6 * t + 0.04 * t * t                    # days behind the writing (up to ~1.6 a second)
        n, _ = day(cycles)
        back = 1 - smooth((t - (shot.duration - 1.5)) / 1.5)  # back to daylight (and the sun to its place) by the cut to 1.8
        n *= 0.6 * back
        sun = SUN_DAY + ((2 * np.pi * cycles + np.pi) % (2 * np.pi) - np.pi) * back
        with Camera(c) as cam:
            cam.look(*cam_17(t, shot.duration))
            full(c, bg[boil])
            pens.rock(c, rock[0], rock[1], 13, 9, 0.3, seed=7777, boil=boil)
            before.draw_text(c, t, pens, boil)
            tk.draw_text(c, t, pens, boil)
            if t < 0.6:                                         # 1.6's writer fades out as the first take fades in
                a = 1 - smooth(t / 0.6)
                shadow(c, pens, last_16.x - 10, last_16.ground - 5, alpha=a)
                c.saveLayerAlpha(None, int(255 * a))
                last_16.draw(c, pens, boil, seed=300 + (len(before.takes) - 1) * 40)
                c.restore()
            tk.draw_figures(c, t, pens, boil)
        night_overlay(c, n, stars, star, night, cam, sky, sun)
    draw.events = [{"name": "sand_scratch", "at": round(s, 3), "gain_db": -18} for s in tk.starts if 0 <= s < shot.duration]
    return draw


# ---------- 1.8 "fewer distractions than a Swiss patent office"; he picks up a rock --------------

def patent_office(ctx, shot):
    pens = ctx.pens
    bg = static_desert(ctx, [])                        # the same bare sand as 1.6 and 1.7
    written = _takes(MATH + PHYSICS, -100)
    written.strikes[2] = -50
    kneel = written.figure(len(written.takes) - 1, 1e9)   # 1.7 ends with him kneeling at his last equation
    x0 = kneel.x                                        # he gets up right there ...
    rock = pickup_rock()                                # ... and walks to the rock a few steps to his left
    cam_from = cam_17(1e9, 13.0)                        # 1.7's last framing

    def draw(c, t, boil):
        # stands among his equations; later walks to a rock, picks it up, looks at it
        stand, hold = replace(POSES["stand"], head=10), replace(POSES["hold_rock"], head=26)
        if t < 7.5:
            fig = Figure(x=x0, ground=kneel.ground, pose=stand, facing=-1)
            if t < 0.9:                                                    # gets up from kneeling
                fig = BlendFigure(kneel, fig, t / 0.9)
            holding = False
        elif t < 9.5:
            u = (t - 7.5) / 2.0
            walked = np.hypot(x0 - rock[0] - 62, GY - kneel.ground) * smooth(u)  # stride follows the distance covered
            pose = walk(2 * np.pi * walked / walk_distance_per_cycle())
            pose = blend(stand, pose, (t - 7.5) / 0.3) if t < 7.8 else pose      # sets off ...
            pose = blend(pose, stand, (t - 9.2) / 0.3) if t >= 9.2 else pose     # ... and stops at the rock
            g = kneel.ground + (GY - kneel.ground) * smooth(u)                # comes forward on the way to the rock
            fig = Figure(x=x0 - (x0 - rock[0] - 62) * smooth(u), ground=g, pose=pose, facing=-1)
            holding = False
        elif t < 11.2:
            u = (t - 9.5) / 1.7
            k = np.sin(np.pi * u)                                          # down and back up
            up = stand if u < 0.5 else hold                                # comes up holding the rock
            fig = Figure(x=rock[0] + 62, ground=GY, pose=blend(up, POSES["place_rock"], k), facing=-1)
            rest = fig.joints()["hand_f"]                                  # the hand eases from where the pose has it
            fig.hand_target = tuple(rest + (rock - (0, 4) - rest) * k)
            holding = u > 0.5
        else:
            fig = Figure(x=rock[0] + 62, ground=GY, pose=hold, facing=-1)
            holding = True
        with Camera(c) as cam:
            path = (1.25 + 0.2 * smooth((t - 9) / 5), W * 0.5 + 40 * smooth((t - 8) / 3), H * 0.66)
            m = smooth(t / 1.5)                                            # from 1.7's last framing
            cam.look(*(a + (b - a) * m for a, b in zip(cam_from, path)))
            full(c, bg[boil])
            written.draw_text(c, t, pens, boil)
            c.drawOval(skia.Rect.MakeXYWH(fig.x - 60, fig.ground - 5, 130, 10), pens.shadow)
            if not holding:
                pens.rock(c, rock[0], rock[1], 13, 9, 0.3, seed=7777, boil=boil)
            fig.draw(c, pens, boil)
            if holding:
                hand = fig.joints()["hand_f"]
                pens.rock(c, hand[0] - 6, hand[1] + 3, 13, 9, 0.3, seed=7777, boil=boil)
    return draw


SCENES = {"wake_up": wake_up, "deadpan_stand": deadpan_stand, "long_walk": long_walk,
          "goes_on_forever": goes_on_forever, "time_to_think": time_to_think, "counting": counting,
          "physics": physics, "patent_office": patent_office}
