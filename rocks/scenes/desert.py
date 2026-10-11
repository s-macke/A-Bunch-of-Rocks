"""Shared desert pieces used by several acts: loose rocks and the sleeping man of the first shots, the rows of
rocks, the Rule 110 field (the rock computer), the dune plate, and the wide desert shot (2.5 and 4.3).

The field: cell (k, j) = generation k, column j of one Rule 110 run (AC-7), so every row of rocks on screen is the
next generation of the row in front of it.
"""
import numpy as np

from ..config import W, H, HORIZON
from ..automaton import generations
from ..rig import Figure, POSES, walk, walk_distance_per_cycle
from .common import bake, Camera, horizon, smooth, full, boil_jitter, shadow

ROWS, COLS = 1300, 2400
RNG_SEED = 110


def scattered_rocks(n, x0, x1, seed):
    """Loose rocks lying around (before any rows exist): (x, y, rx, ry, rot, depth)."""
    r = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        d = r.uniform(0.05, 1.0)                          # 0 far .. 1 near
        y = H * HORIZON + 6 + (H * 0.99 - H * HORIZON - 6) * d ** 1.6
        size = 2.5 + 13 * d ** 1.4 * r.uniform(0.6, 1.2)
        out.append((r.uniform(x0, x1), y, size, size * 0.62, r.uniform(-0.4, 0.4), d))
    return sorted(out, key=lambda q: q[5])


def static_desert(ctx, rocks, with_horizon=True, extra=None, zoom=1.0):
    """The desert with loose rocks, baked once per boil state; extra(c, b) draws more on top before baking.

    Rocks and shadows are multiplied into the sand, so they must be baked onto it: faded in on a layer of their own,
    they would show their raw grey instead of the sand's brown."""
    plate = ctx.desert()
    pens = ctx.pens

    def static(c, b):
        full(c, plate)
        if with_horizon:
            horizon(c, boil=b)
        for i, r in enumerate(rocks):
            pens.rock(c, *r[:5], seed=7000 + i, boil=b)
        if extra:
            extra(c, b)
    return bake(static, zoom)


# where the film begins: he lies asleep among loose rocks. The cold open (0.1) ends on this wide view and shot 1.1
# starts on it, then moves in, so the cut between them is invisible.
WAKE_X, WAKE_GY = W * 0.52, H * 0.84


def wake_rocks():
    return scattered_rocks(40, 0, W, 11)


def sleeper():
    return Figure(x=WAKE_X, ground=WAKE_GY, pose=POSES["lie"], hip_y=WAKE_GY - 6, facing=-1)


def world():
    """The one computation shown from Act 2 on: a random first row, then Rule 110."""
    first = np.random.default_rng(RNG_SEED).integers(0, 2, COLS).astype(np.uint8)
    return generations(first, ROWS)


def rock_rows(seed=1):
    """Receding rows of rocks, like the start of the rock computer (layout from the approved sample)."""
    r = np.random.default_rng(seed)
    out = []
    for row in range(5):
        depth = 1.0 - row * 0.16
        y = H * (HORIZON + 0.08 + 0.34 * depth ** 2.2)
        size = 20 * depth ** 1.6 + 3
        n = 9 + row * 3
        x0, x1 = W * (0.08 + row * 0.05), W * (0.50 - row * 0.02)
        for i in range(n):
            if r.random() < 0.28:
                continue
            out.append((x0 + (x1 - x0) * i / (n - 1) + r.normal(0, 2), y + r.normal(0, 1.5),
                        size * r.uniform(.8, 1.2), size * r.uniform(.5, .75), r.uniform(-.3, .3), row))
    return out


# the rock he sets down at the end of a row in 2.6 ("Just slower"): from then on it is part of the rows
PLACED_ROCK = (W * 0.7 - 78, H * 0.88, 13, 9, 0.2)
PLACED_SEED = 4000


def rows_static(ctx, extra=None, placed=True, zoom=1.0):
    """The desert with the receding rock rows, baked once per boil state. placed=False: before 2.6 sets the last
    rock down."""
    pens = ctx.pens
    plate = ctx.desert()
    rocks = rock_rows()

    def static(c, b):
        full(c, plate)
        horizon(c, boil=b)
        for i, r in enumerate(rocks):
            pens.rock(c, *r[:5], seed=i, boil=b)
        if placed:
            pens.rock(c, *PLACED_ROCK, seed=PLACED_SEED, boil=b)
        if extra:
            extra(c, b)
    return bake(static, zoom)



def field_rows(n_rows, horizon_y, near_y, near_spacing, far_spacing):
    """Perspective rows (far -> near): y, spacing, rock size per row."""
    out = []
    for k in range(n_rows):
        d = (k + 1) / n_rows                              # 0 far .. 1 near
        y = horizon_y + 4 + (near_y - horizon_y - 4) * d ** 1.7
        sp = far_spacing + (near_spacing - far_spacing) * d ** 1.5
        out.append((y, sp, sp * 0.62))
    return out


def dune_plate(washer):
    hy = H * 0.2
    base = washer.paper()
    base = washer.wash(base, [(0, 0), (W, 0), (W, hy + 8), (0, hy + 8)], (150, 175, 205), 0.55, 0, 12)
    base = washer.wash(base, [(0, hy), (W, hy), (W, H), (0, H)], (222, 190, 140), 0.6, 2, 10)
    base = washer.wash(base, [(0, H * .78), (W * .25, H * .72), (W * .55, H * .8), (W, H * .74), (W, H), (0, H)],
                       (205, 160, 115), 0.35, 1, 20)
    return base


def endless_rows(c, pens, b, near_y, near_spacing=46, near_size=15):
    """Rows of rocks from the horizon down to near_y, each the next Rule 110 generation of the one behind it:
    the desert really is the computation, as far as the eye can see."""
    gens = generations(np.random.default_rng(110).integers(0, 2, 420), 22)
    hy = H * HORIZON
    for k in range(21, -1, -1):                        # far to near
        d = (k + 1) / 22                               # 0 far .. 1 near
        y = hy + 6 + (near_y - hy - 6) * d ** 1.8
        spacing = 5 + (near_spacing) * d ** 1.6
        size = 1.2 + near_size * d ** 1.6
        row = gens[21 - k]
        ncell = int(W / spacing) + 2
        off = (len(row) - ncell) // 2
        for j in range(ncell):
            if row[off + j]:
                x = j * spacing - spacing / 2
                if size < 3:
                    dx, dy = boil_jitter(k * 1000 + j, b)
                    c.drawCircle(x + dx, y + dy, size * 0.7, pens.hatch)
                else:
                    pens.rock(c, x, y, size, size * 0.62, 0.1 * np.sin(j), seed=k * 1000 + j, boil=b)


# ---------- 2.5 and 4.3 wide: endless rows ---------------------------------------------------

def desert_wide(ctx, shot):
    pens = ctx.pens
    plate = ctx.desert()
    hy = H * HORIZON
    def static(c, b):
        full(c, plate)
        horizon(c, boil=b)
        endless_rows(c, pens, b, H * 0.99)
    bg = bake(static)
    gy = hy + 6 + (H * 0.99 - hy - 6) * (12 / 22) ** 1.8 + 2

    walking = shot.params.get("walk", False)
    holding = shot.params.get("hold", False)               # 4.3: still holding the rock from 4.2
    cyc = 14.0 / walk_distance_per_cycle() / 0.42          # ~14 px/s on screen at scale 0.42

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(1.12 - 0.12 * smooth(t / shot.duration), W / 2, H / 2)
            full(c, bg[boil])
            if walking:
                fig = Figure(x=W * 0.66 - 14 * t, ground=gy, scale=0.42, pose=walk(2 * np.pi * cyc * t))
            else:
                fig = Figure(x=W * 0.6, ground=gy, scale=0.42, pose=POSES["hold_rock" if holding else "stand"])
            shadow(c, pens, fig.x, gy - 2, w=55)
            fig.draw(c, pens, boil, width=2.4)
            if holding:
                hand = fig.joints()["hand_f"]
                pens.rock(c, hand[0] - 3, hand[1] + 1.3, 5.5, 3.8, 0.2, seed=999, boil=boil)
    return draw
