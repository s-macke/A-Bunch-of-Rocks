"""Act 4 "Our world" scenes (spec §1, D-27): dust mote, rock in hand, wide desert, turn, lecture hall, walk.

Each factory takes (ctx, shot) and returns draw(canvas, t, boil) with t in shot-local seconds.
"""
from dataclasses import replace
import numpy as np
import skia

from ..config import W, H
from ..rig import Figure, POSES, blend, walk, walk_distance_per_cycle
from ..ink import path_of, wobble, circle
from ..lettering import Lettering
from .common import bake, Camera, fade_to, horizon, smooth, full
from .desert import endless_rows, rows_static, desert_wide

# ---------- 4.1 dust mote in a sunbeam ---------------------------------------------------

WINDOW = (170, 80, 430, 330)                     # x0, y0, x1, y1


def _room_plate(washer):
    base = washer.paper()
    base = washer.wash(base, [(0, 0), (W, 0), (W, H), (0, H)], (215, 200, 175), 0.45, 0, 12)
    # darker wall outside the light beam, so the beam reads as light
    left = [(0, 0), (170, 0), (170, 330), (560, 720), (0, 720)]
    right = [(430, 0), (W, 0), (W, 560), (1180, 560), (430, 80)]
    base = washer.wash(base, left, (175, 160, 150), 0.55, 1, 22)
    base = washer.wash(base, right, (175, 160, 150), 0.55, 2, 22)
    base = washer.wash(base, [(0, H * .8), (W, H * .8), (W, H), (0, H)], (185, 150, 115), 0.5, 0, 6)
    base = washer.wash(base, [WINDOW[:2], (WINDOW[2], WINDOW[1]), WINDOW[2:], (WINDOW[0], WINDOW[3])],
                       (200, 220, 235), 0.45, 1, 3)
    return base


def dust_room(ctx, shot):
    plate = ctx.plate("room", {"v": 1}, _room_plate)
    pens = ctx.pens
    x0, y0, x1, y1 = WINDOW

    def static(c, b):
        full(c, plate)
        pens.line(c, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], 2.4, 40 + b)
        pens.line(c, [((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], 1.8, 50 + b)
        pens.line(c, [(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)], 1.8, 60 + b)
        pens.line(c, [(0, H * .8), (W, H * .8 + 2)], 1.6, 70 + b)
    bg = bake(static)

    rng = np.random.default_rng(4)
    n = 34
    u, v = rng.uniform(0.1, 0.9, n), rng.uniform(0.05, 0.95, n)   # position along/across the beam
    size = rng.uniform(1.2, 2.8, n)
    phase = rng.uniform(0, 2 * np.pi, (n, 2))
    hero = np.array([770.0, 390.0])
    vanish = shot.cues["vanish"]
    mote = skia.Paint(AntiAlias=True, Color=skia.Color(255, 250, 232, 230),
                      MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 0.8))
    glow = skia.Paint(AntiAlias=True, Color=skia.Color(255, 245, 210, 200),
                      MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 6))

    def beam_point(a, b):
        top = np.array([170, 330]) + (np.array([430, 80]) - np.array([170, 330])) * b
        bottom = np.array([560, 720]) + (np.array([1180, 560]) - np.array([560, 720])) * b
        return top + (bottom - top) * a

    def draw(c, t, boil):
        zoom = 1.0 + 0.5 * smooth(t / (vanish + 0.2))
        with Camera(c) as cam:
            cam.look(zoom, W / 2 + (hero[0] - W / 2) * smooth(t / vanish), H / 2 + (hero[1] - H / 2) * smooth(t / vanish))
            full(c, bg[boil])
            for i in range(n):
                p = beam_point(u[i], v[i]) + 6 * np.sin(t * 0.3 + phase[i]) + np.array([t * 2.0, t * 1.2])
                c.drawCircle(float(p[0]), float(p[1]), float(size[i]), mote)
            hp = hero + np.array([2.5 * np.sin(t * 0.5), 1.5 * np.sin(t * 0.37)])
            if t < vanish:
                c.drawCircle(float(hp[0]), float(hp[1]), 3.2, mote)
            elif t < vanish + 0.34:                                  # a short flash (8 frames at 24 fps)
                k = (t - vanish) / 0.34
                c.drawCircle(float(hp[0]), float(hp[1]), 10 + 18 * k, glow)
                for i, a in enumerate(np.linspace(0, 2 * np.pi, 8, endpoint=False)):   # hand-drawn rays that boil
                    r0, r1 = 5 + 10 * k, 12 + 16 * k
                    pens.line(c, [(hp[0] + r0 * np.cos(a), hp[1] + r0 * np.sin(a)),
                                  (hp[0] + r1 * np.cos(a), hp[1] + r1 * np.sin(a))], 1.4, 760 + i * 3 + boil, amp=0.25)
        fade_to(c, ctx.paper, 1 - smooth(t / 1.2))                   # emerges from the blank page (D-31)
    return draw

# ---------- 4.2 holding the rock -------------------------------------------------------------

def desert_hold_rock(ctx, shot):
    bg = rows_static(ctx)
    pens = ctx.pens
    gx, gy, s = W * 0.72, H * 0.88, 1.25
    line_at = shot.voice[0]["at"]

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(1.45, gx - 30, gy - 110)
            full(c, bg[boil])
            look = 28 - 22 * smooth((t - line_at) / 1.2)               # looks down at the rock, then up
            fig = Figure(x=gx, ground=gy, scale=s, pose=replace(POSES["hold_rock"], head=look))
            hand = fig.joints()["hand_f"]
            c.drawOval(skia.Rect.MakeXYWH(gx - 70, gy - 5, 150, 10), pens.shadow)
            fig.draw(c, pens, boil)
            pens.rock(c, hand[0] - 7, hand[1] + 3, 13, 9, 0.2, seed=999, boil=boil)
    return draw

# ---------- 4.4 the turn: "Oh. And one more thing." ----------------------------------------

def desert_turn(ctx, shot):
    bg = rows_static(ctx)
    pens = ctx.pens
    gx, gy = W * 0.66, H * 0.88
    turn = shot.cues["turn"] - 0.35

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(1.3, gx, gy - 110)
            full(c, bg[boil])
            facing = -1 if t < turn else 1
            hold = POSES["hold_rock"]                                    # still holding the rock from 4.2
            pose = replace(hold, head=6) if t < turn else replace(hold, head=-8 + 8 * smooth((t - turn) / 0.6))
            arm = 1 - smooth((t - turn + 0.3) / 0.3) + smooth((t - turn) / 0.3)   # arm down to turn, then up again
            pose = blend(replace(POSES["stand"], head=pose.head), pose, min(1.0, arm))
            c.drawOval(skia.Rect.MakeXYWH(gx - 60, gy - 5, 140, 10), pens.shadow)
            fig = Figure(x=gx, ground=gy, scale=1.15, facing=facing, pose=pose)
            fig.draw(c, pens, boil)
            hand = fig.joints()["hand_f"]
            pens.rock(c, hand[0] + 7 * facing, hand[1] + 3, 13, 9, 0.2, seed=999, boil=boil)
    return draw


# ---------- 4.5 lecture hall with a slow clock --------------------------------------------

BOARD = (110, 150, 640, 420)
CLOCK = (1010, 235, 34)        # x, y, r (on the wall above the students)
STUDENTS = [870, 1010, 1150]


def _lecture_plate(washer):
    base = washer.paper()
    base = washer.wash(base, [(0, 0), (W, 0), (W, H * .82), (0, H * .82)], (200, 208, 212), 0.5, 0, 14)
    base = washer.wash(base, [(0, H * .82), (W, H * .82), (W, H), (0, H)], (190, 165, 135), 0.55, 1, 6)
    x0, y0, x1, y1 = BOARD
    for k in range(2):
        base = washer.wash(base, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], (70, 105, 88), 0.8, k, 2)
    return base


def lecture_hall(ctx, shot):
    plate = ctx.plate("lecture", {"v": 1}, _lecture_plate)
    pens = ctx.pens
    gy = H * 0.9
    chalk = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, Color=skia.Color(235, 235, 225, 220),
                       StrokeWidth=2.2, StrokeCap=skia.Paint.kRound_Cap)
    font = Lettering(30)
    chalk_fill = skia.Paint(AntiAlias=True, Color=skia.Color(235, 235, 225, 215))
    cx, cy, cr = CLOCK

    def static(c, b):
        full(c, plate)
        x0, y0, x1, y1 = BOARD
        pens.line(c, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], 2.6, 80 + b)
        pens.line(c, [(0, H * .82), (W, H * .82 + 2)], 1.6, 81 + b)
        font.draw(c, "E = mc²", x0 + 40, y0 + 70, chalk_fill)
        font.draw(c, "iħ ∂ψ/∂t = Ĥψ", x0 + 190, y0 + 150, chalk_fill)
        xs = np.linspace(x0 + 40, x0 + 250, 50)
        c.drawPath(path_of(wobble(np.stack([xs, y0 + 230 - 40 * np.exp(-((xs - x0 - 145) / 35) ** 2)], 1), 0.5, 90 + b)), chalk)
        pens.line(c, circle((cx, cy), cr, overshoot=0.04), 2.6, 82 + b)
        for k in range(12):
            a = k * np.pi / 6
            pens.line(c, [(cx + (cr - 7) * np.sin(a), cy - (cr - 7) * np.cos(a)),
                          (cx + (cr - 3) * np.sin(a), cy - (cr - 3) * np.cos(a))], 1.6, 83 + k + b)
        for i, sx in enumerate(STUDENTS):
            # desk in front of each student (they face left, toward the board)
            pens.line(c, [(sx - 95, gy - 78), (sx - 30, gy - 78)], 2.4, 100 + i * 5 + b)
            pens.line(c, [(sx - 88, gy - 78), (sx - 88, gy)], 2.0, 101 + i * 5 + b)
            pens.line(c, [(sx + 18, gy - 48), (sx + 18, gy)], 2.0, 102 + i * 5 + b)          # chair
            pens.line(c, [(sx - 25, gy - 46), (sx + 18, gy - 46)], 2.0, 103 + i * 5 + b)
            if i != 1:
                pose = POSES["sit"]
                Figure(x=sx, ground=gy, pose=pose, hip_y=gy - 52, facing=-1).draw(c, pens, b, seed=400 + i * 50)
    bg = bake(static)

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(1.15, 645, 430)                  # the whole board and all three students in frame
            _draw_lecture(c, t, boil)

    def _draw_lecture(c, t, boil):
        full(c, bg[boil])
        # clock: minute hand parked, second hand ticks once per second
        sec = np.floor(t + 0.5) * 6 + 90
        for ang, length, w in ((np.radians(sec), cr - 8, 1.4), (np.radians(62), cr - 12, 2.6), (np.radians(300), cr - 20, 3.0)):
            pens.line(c, [(cx, cy), (cx + length * np.sin(ang), cy - length * np.cos(ang))], w, 700 + int(w * 10) + boil, amp=0.2)
        # the dozing student slowly sinks toward the desk
        droop = smooth(t / shot.duration)
        pose = replace(POSES["sit"], torso=4 + 30 * droop, head=-4 + 35 * droop, arm_f=(40, 60), arm_b=(35, 65))
        Figure(x=STUDENTS[1], ground=gy, pose=pose, hip_y=gy - 52, facing=-1).draw(c, pens, boil, seed=450)
        # lecturer points at the board, facing the students
        lx = 720
        lec = Figure(x=lx, ground=gy, pose=replace(POSES["stand"], head=-5), facing=1)
        sh = lec.joints()["shoulder"]
        aim = np.array([BOARD[0] + 260 + 30 * np.sin(t * 1.3), BOARD[1] + 150 + 20 * np.sin(t * 0.9)])  # the equations
        lec.hand_target = tuple(sh + (aim - sh) / np.hypot(*(aim - sh)) * 56)    # arm stretched toward the board
        lec.draw(c, pens, boil, seed=500)
    return draw


# ---------- 4.6 walking a single row, camera pulls back, fade to paper -------------------

def desert_walk_row(ctx, shot):
    pens = ctx.pens
    plate = ctx.desert()
    gy = H * 0.84
    row = [(x, gy + np.random.default_rng(int(x) + 1000).normal(0, 1.5), 13, 8.5, 0.1) for x in np.arange(-60, W + 60, 44)]

    def static(c, b):
        full(c, plate)
        horizon(c, boil=b)
        endless_rows(c, pens, b, gy - 34, near_spacing=40, near_size=12)   # behind his row: rows to the horizon
        for i, r in enumerate(row):
            pens.rock(c, *r, seed=5000 + i, boil=b)
    bg = bake(static, 1.7)
    x_start, x_end = W * 0.78, W * 0.46
    speed = (x_start - x_end) / shot.duration
    cyc = speed / walk_distance_per_cycle()

    def draw(c, t, boil):
        x = x_start - speed * t
        k = smooth(t / (shot.duration * 0.85))
        with Camera(c) as cam:
            cam.look(1.7 - 0.7 * k, x + (W / 2 - x) * k, (gy - 90) + (H / 2 - gy + 90) * k)
            full(c, bg[boil])
            c.drawOval(skia.Rect.MakeXYWH(x - 55, gy + 6, 130, 9), pens.shadow)
            Figure(x=x, ground=gy + 10, pose=walk(2 * np.pi * cyc * t)).draw(c, pens, boil)
        fade_to(c, ctx.paper, (t - (shot.duration - 2.5)) / 2.5)
    return draw


SCENES = {"dust_room": dust_room, "desert_hold_rock": desert_hold_rock, "desert_wide": desert_wide,
          "desert_turn": desert_turn, "lecture_hall": lecture_hall, "desert_walk_row": desert_walk_row}
