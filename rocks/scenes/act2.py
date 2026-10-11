"""Act 2 "The computer" scenes (spec §1, §6, D-18, D-28): he is in every shot. The first row; Rule 110 laid by
hand (2.2, D-29); rows growing behind him; the field from a dune; the deadpan line; a week of walking; physics in
the sand and a glowing string of rocks (2.8, D-30); two sparks meeting.
"""
from dataclasses import replace
import numpy as np
import skia

from ..config import W, H, HORIZON
from ..rig import Figure, BlendFigure, POSES, walk, blend, walk_distance_per_cycle
from ..sprites import SHAPES
from ..lettering import Lettering
from .common import bake, Camera, horizon, smooth, night_overlay, night_tools, full, shadow, boil_jitter, day
from .writing import writer
from .desert import COLS, world, rock_rows, rows_static, field_rows, dune_plate, desert_wide, PLACED_ROCK, PLACED_SEED


# ---------- 2.1 the first row, side view ----------------------------------------------------

def first_row(ctx, shot):
    pens = ctx.pens
    plate = ctx.desert()
    bg = bake(lambda c, b: (full(c, plate), horizon(c, boil=b)))
    gy = H * 0.84
    spacing, period = 46.0, 1.3
    x_first = W * 0.86
    already = 3

    def slot(n):
        return x_first - n * spacing

    def draw(c, t, boil):
        cyc, ph = divmod(t, period)
        n = already + int(cyc)                              # slot being filled in this cycle
        front = gy + 18                                     # he stands just in front of the row, not on its rocks
        if ph < 0.45:                                       # step to the next slot
            x = slot(n) + 55 + spacing * (1 - smooth(ph / 0.45))
            step = blend(POSES["stand"], walk(2 * np.pi * ph / 0.9), np.sin(np.pi * ph / 0.45))   # from stand to stand
            fig = Figure(x=x, ground=front, pose=step)
            laid = n
        else:
            x = slot(n) + 55
            k = smooth((ph - 0.45) / 0.45) if ph < 0.9 else 1 - smooth((ph - 0.9) / 0.4)
            fig = Figure(x=x, ground=front, pose=blend(POSES["stand"], POSES["place_rock"], k))
            rest = fig.joints()["hand_f"]                   # the hand moves from where the pose has it to the slot
            fig.hand_target = tuple(rest + (np.array([slot(n), gy - 4]) - rest) * k)
            laid = n + (1 if ph >= 0.9 else 0)
        with Camera(c) as cam:
            pan = slot(already + t / period) + 55 + spacing * 0.5      # a steady pan along the row, not stop-and-go
            cam.look(1.35, pan - 60, gy - 100)
            full(c, bg[boil])
            c.drawOval(skia.Rect.MakeXYWH(x - 55, front - 5, 130, 10), pens.shadow)
            for i in range(laid):
                pens.rock(c, slot(i), gy + np.sin(i * 2.3) * 1.5, 12, 8, 0.2 * np.sin(i), seed=3000 + i, boil=boil)
            if ph >= 0.45 and ph < 0.9:
                hand = fig.joints()["hand_f"]
                pens.rock(c, hand[0], hand[1] + 3, 12, 8, 0.2, seed=3999, boil=boil)
            fig.draw(c, pens, boil)
    return draw


PICK, PLACE = 0.35, 0.6       # phases of a slow spot: he has the loose rock in hand, the rock is in the row


def _rule_schedule(shot, cells, j_first, direction):
    """Timing for 2.2: the first spots one by one, then a smooth fast run, then rows 2 and 3 on "third".
    Of the first slow_n spots he kneels only at those that get a rock; past an empty one he shuffles two rocks' width.
    Returns spot(t) -> (row, float index along the row, phase within a slow spot or None, index of the next spot he
    kneels at) and the click events."""
    third = shot.cues["third"]
    slow_n, t_a = 5, 1.0
    t_b = t_a + slow_n * 1.2
    placed = [i for i in range(slow_n) if cells[1, j_first + direction * i]]
    slow_dt = (t_b - t_a) / len(placed)               # the same time in all, shared by the spots that get a rock
    fast_rate = 5.0                                   # spots per second, continuous
    t_c = third - 0.3

    def spot(t):
        if t < t_a:
            return 1, float(placed[0]), 0.0, placed[0]
        if t < t_b:
            k, ph = divmod((t - t_a) / slow_dt, 1)
            k = int(k)
            return 1, float(placed[k]), ph, placed[k + 1] if k + 1 < len(placed) else slow_n
        if t < t_c:
            return 1, slow_n + (t - t_b) * fast_rate, None, None
        return 1, slow_n + (t_c - t_b) * fast_rate, None, None

    events = [{"name": "rock_set_down", "at": round(t_a + (k + PLACE) * slow_dt, 3), "gain_db": -11}
              for k in range(len(placed))]
    n_fast = int((t_c - t_b) * fast_rate)
    for i in range(n_fast):
        if cells[1, j_first + direction * (slow_n + i)]:
            events.append({"name": "rock_set_down", "at": round(t_b + (i + 0.5) / fast_rate, 3), "gain_db": -21})
    return spot, events, third, slow_n


def rule_side(ctx, shot):
    """A raised side view. Rows run across the frame, older rows further back. He kneels in profile
    beside the new row, picks up the loose rock in front of his knee and sets it into the row, then shuffles on to the
    next spot that gets a rock (past an empty one, two rocks' width). Then he gets up and walks along, laying the row
    smoothly; rows 3 and 4 sweep in on "Then a third row. Then a fourth." """
    cells = ctx.cache("world", world)
    pens = ctx.pens
    plate = ctx.desert()
    bg = bake(lambda c, b: (full(c, plate), horizon(c, boil=b)), 1.55)
    direction = -1                                    # he works leftwards
    j_first = 1198                                    # Rule 110 here (leftwards): rock, rock, rock, empty, rock
    spot, events, third, slow_n = _rule_schedule(shot, cells, j_first, direction)
    sp = 56.0
    row_y = [H * 0.64, H * 0.72, H * 0.81, H * 0.9]
    row_size = [15, 18, 21, 24]

    def x_of(j, pan):
        return W * 0.62 + (j - j_first) * sp - pan

    def loose(j, pan):
        """Where the loose rock for spot j lies: on the ground in front of his knees, below the spot, scattered a
        little (within his reach when he leans forward)."""
        return x_of(j, pan) - 12 + ((j * 37) % 11 - 5) * 1.2, kneel_y - 5 + ((j * 53) % 5 - 2) * 1.0

    kneel_off, kneel_y = 62.0, row_y[1] + 40          # where he kneels: his head above the row behind (the three
                                                      # rocks he touches stay in view), the spot in front of his
                                                      # knee, all of it in reach, and his hand's path clear of his
                                                      # shoulder (otherwise the elbow flips sides)
    t_b = 1.0 + slow_n * 1.2                          # end of the slow spots (as in _rule_schedule)
    n_spots = int(spot(third)[1]) + 1                 # spots he fills in all (more when the shot grows)
    j_end = j_first + direction * spot(third)[1]      # where he stops: the view rests around him
    view = W / 1.55                                   # the view's width in stage units (camera zoom 1.55)

    def draw(c, t, boil):
        row, fi, ph, nxt = spot(t)
        i = int(fi)
        j = j_first + direction * i
        # where he is along the row, continuous: at the end of each slow spot he shuffles to the next one he kneels at
        along = fi + ((nxt - fi) * smooth((ph - 0.8) / 0.2) if ph is not None else 0.0)
        glide = fi + ((nxt - fi) * smooth((ph - 0.5) / 0.5) if ph is not None else 0.0)   # the camera, more gently
        # pan so that he stays around 62 % of the width once he walks
        pan = direction * max(0.0, fi - slow_n) * sp            # tracking shot: the rows scroll under him
        with Camera(c) as cam:
            cam.look(1.55, x_of(j_first + direction * glide, pan) + 20, H * 0.66)
            full(c, bg[boil])
            # rows 0 (complete) and 1 (up to the current spot); 2 and 3 sweep in after "third"
            jmin, jmax = j_first - n_spots - 30, j_first + 14   # his whole way, plus a screen to his left
            sweep = [None, None, (t - third + 0.2) / 0.6, (t - third - 1.1) / 0.6]
            for k in range(4):
                for jj in range(jmin, jmax):
                    if not cells[k, jj]:
                        continue
                    x = x_of(jj, pan)
                    if x < -30 or x > W + 30:
                        continue
                    scale = 1.0
                    if k == 1:
                        done = (jj - j_first) * direction                 # 0 = first spot he fills
                        if done >= 0 and (done > fi or (done == i and ph is not None and ph < PLACE)):
                            continue
                    elif k >= 2:
                        f = sweep[k]
                        pos = (x - x_of(j_end, pan) + view / 2) / view   # sweeps in left to right, across the view
                        if f is None or f < pos:
                            continue
                        scale = min(1.0, (f - pos) * 8)
                    pens.rock(c, x, row_y[k], row_size[k] * scale, row_size[k] * 0.62 * scale, 0.2 * np.sin(jj),
                              seed=jj * 7 + k, boil=boil)
            # the loose rocks he lays: one in the sand below every spot that gets a rock, until he picks it up
            for d in range(n_spots):
                jj = j_first + direction * d
                if not cells[1, jj] or d < i or (d == i and (ph is None or ph >= PICK)) or (ph is None and d <= fi):
                    continue
                x, y = loose(jj, pan)
                if -30 < x < W + 30:
                    pens.rock(c, x, y, row_size[1], row_size[1] * 0.62, 0.3, seed=jj * 7 + 1, boil=boil)
            # him
            def kneeling(fx, hand, lean=0.0):
                pose = blend(POSES["crouch"], POSES["place_rock"], lean) if lean > 0 else POSES["crouch"]
                fig = Figure(x=fx, ground=kneel_y, pose=pose, scale=1.25, facing=-1)
                fig.hand_target = tuple(hand)
                return fig

            if ph is not None:                            # kneeling beside the spot
                fx = x_of(j_first + direction * along, pan) + kneel_off
                target_spot = np.array([x_of(j, pan), row_y[1] - 4])
                rest = np.array([fx - 20, row_y[1] + 10])
                low = np.array(loose(j, pan))
                lean = 0.0                                 # he leans forward to pick up the loose rock
                if ph < 0.1:                               # a beat at rest
                    hand = rest
                elif ph < PICK:                            # reach down for the loose rock in front of his knee
                    lean = smooth((ph - 0.1) / (PICK - 0.1))
                    hand = rest + (low - rest) * lean
                elif ph < PLACE:                           # lift it into the row, just above it
                    u = smooth((ph - PICK) / (PLACE - PICK))
                    lean = 1 - u
                    hand = low + (target_spot - low) * u
                else:                                      # and back
                    hand = target_spot + (rest - target_spot) * smooth((ph - PLACE) / 0.2)
                fig = kneeling(fx, hand, lean)
                c.drawOval(skia.Rect.MakeXYWH(fx - 60, kneel_y - 5, 130, 10), pens.shadow)
                fig.draw(c, pens, boil)
                if PICK <= ph < PLACE:
                    pens.rock(c, hand[0], hand[1] + 2, row_size[1], row_size[1] * 0.62, 0.3, seed=j * 7 + 1, boil=boil)
            else:                                         # walking along, laying as he goes; stops when the row is done
                fx = x_of(j_first + direction * fi, pan) + kneel_off
                t_stop = third - 0.3                      # the row is finished and the world stops scrolling
                # the rows scroll under him at fast_rate spots/s; his stride matches (feet planted, at scale 1.25)
                walk_ph = 2 * np.pi * max(0.0, min(t, t_stop) - t_b) * 5.0 * sp / (walk_distance_per_cycle() * 1.25)
                pose = blend(walk(walk_ph), POSES["stand"], (t - t_stop) / 0.4) if t >= t_stop else walk(walk_ph)
                fig = Figure(x=fx, ground=kneel_y, pose=pose, scale=1.25, facing=-1)
                if t < t_b + 0.5:                         # gets up from kneeling into the walk
                    rest = np.array([fx - 20, row_y[1] + 10])
                    fig = BlendFigure(kneeling(fx, rest), fig, (t - t_b) / 0.5)
                c.drawOval(skia.Rect.MakeXYWH(fx - 55, kneel_y - 5, 120, 10), pens.shadow)
                fig.draw(c, pens, boil)
    draw.events = events
    return draw


# ---------- 2.3 he walks on; rows appear behind him ----------------------------------------


def rows_behind(ctx, shot):
    """Side view: he walks along the front; behind him rows appear one after another, near to far,
    as if time were passing (each row is the next Rule 110 generation of the one in front of it)."""
    cells = ctx.cache("world", world)
    sprites = ctx.sprites
    pens = ctx.pens
    plate = ctx.desert()
    bg = bake(lambda c, b: (full(c, plate), horizon(c, boil=b)))
    n = 16
    rows = list(reversed(field_rows(n, H * HORIZON, H * 0.84, 46, 8)))      # index 0 = nearest
    reveal_dt = (shot.duration - 0.8) / n
    gy = H * 0.93
    cyc = 26.0 / walk_distance_per_cycle()

    def draw(c, t, boil):
        full(c, bg[boil])
        done = t / reveal_dt
        for k in range(min(n, int(done) + 1) - 1, -1, -1):              # far first so near rocks overlap
            y, sp, size = rows[k]
            pop = min(1.0, (done - k) * 2.5)                             # a row pops in over 0.4 row-times
            ncell = int(W / sp) + 2
            off = COLS // 2 - ncell // 2
            for jj in np.nonzero(cells[k, off:off + ncell])[0]:
                x = jj * sp - sp / 2
                c.save()
                c.translate(x, y)
                c.scale(1, 0.62)
                sprites.draw(c, 0, 0, size / 0.62 * 0.9 * pop, (k * 7 + jj * 13) % SHAPES, boil)
                c.restore()
        x = W * 0.85 - 26 * t
        c.drawOval(skia.Rect.MakeXYWH(x - 55, gy - 5, 130, 10), pens.shadow)
        Figure(x=x, ground=gy, pose=walk(2 * np.pi * cyc * t)).draw(c, pens, boil)
    return draw


# ---------- 2.4 from a dune: rows to the horizon, him a dot --------------------------------


def dune_view(ctx, shot):
    cells = ctx.cache("world", world)
    sprites = ctx.sprites
    pens = ctx.pens
    plate = ctx.plate("dune", {"v": 1}, dune_plate)
    hy = H * 0.2
    rows = field_rows(70, hy, H * 1.02, 30, 2.2)
    dot = skia.Paint(AntiAlias=True, Color=skia.Color(110, 92, 84, 200))

    def static(c, b):
        full(c, plate)
        horizon(c, hy, b)
        for k, (y, sp, size) in enumerate(rows):
            ncell = int(W / sp) + 2
            off = COLS // 2 - ncell // 2
            for jj in np.nonzero(cells[k, off:off + ncell])[0]:
                x = jj * sp - sp / 2
                if size < 4:
                    dx, dy = boil_jitter(k * 1000 + jj, b)
                    c.drawCircle(x + dx, y + dy, max(0.6, size * 0.45), dot)
                else:
                    c.save()
                    c.translate(x, y)
                    c.scale(1, 0.62)
                    sprites.draw(c, 0, 0, size / 0.62 * 0.9, (k * 7 + jj * 13) % SHAPES, b)
                    c.restore()
    bg = bake(static)
    fy = rows[48][0] - 2

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(1.18 - 0.18 * smooth(t / shot.duration), W * 0.56, H * 0.52)
            full(c, bg[boil])
            shadow(c, pens, W * 0.58, fy - 1, w=21)
            Figure(x=W * 0.58, ground=fy, scale=0.16, pose=POSES["look_up"]).draw(c, pens, boil, width=1.6)   # stands still, taking it in
    return draw


# ---------- 2.5 desert_wide: see desert.py ---------------------------------------------------


# ---------- 2.6 "Sure, it's rocks instead of electricity" -------------------------------------

def place_deadpan(ctx, shot):
    bg = rows_static(ctx, placed=False)               # he is about to set that rock down
    pens = ctx.pens
    gx, gy = W * 0.7, H * 0.88
    target = np.array([PLACED_ROCK[0], PLACED_ROCK[1] - 4])   # where the rock will lie
    look = shot.cues["just"] - 0.25

    def draw(c, t, boil):
        if t < 0.6:
            k = 0.0
        elif t < 1.55:
            k = smooth((t - 0.6) / 0.95)
        else:
            k = 1 - smooth((t - 1.55) / 0.9)
        facing = 1 if t >= look else -1
        fig = Figure(x=gx, ground=gy, scale=1.15, facing=facing, pose=blend(POSES["stand"], POSES["place_rock"], k))
        if facing == -1:                                           # the hand eases from where the pose has it
            rest = fig.joints()["hand_f"]
            fig.hand_target = tuple(rest + (target - rest) * k)
        with Camera(c) as cam:
            cam.look(1.4, gx - 40, gy - 110)
            full(c, bg[boil])
            c.drawOval(skia.Rect.MakeXYWH(gx - 70, gy - 5, 150, 10), pens.shadow)
            if t >= 1.55:
                pens.rock(c, target[0], target[1] + 4, 13, 9, 0.2, seed=PLACED_SEED, boil=boil)
            elif t >= 0.6:
                hand = fig.joints()["hand_f"]
                pens.rock(c, hand[0], hand[1] + 3, 13, 9, 0.2, seed=PLACED_SEED, boil=boil)
            fig.draw(c, pens, boil)
    return draw


# ---------- 2.7 a week of walking: days and nights flicker past -----------------------------

def week_of_walking(ctx, shot):
    bg = rows_static(ctx)
    pens = ctx.pens
    gy = H * 0.9
    stars, star, night = night_tools(7, n=70)
    sky = ctx.desert_sky()
    days = 7
    cyc = 26.0 / walk_distance_per_cycle()

    def draw(c, t, boil):
        n, sun = day(days * t / (shot.duration - 0.4))
        x = W * 0.82 - 26 * t
        with Camera(c) as cam:
            cam.look(1.1, W / 2, H / 2 + 20)                   # the sky in view: the sun crosses all of it
            full(c, bg[boil])
            shadow(c, pens, x, gy - 5)
            Figure(x=x, ground=gy, pose=walk(2 * np.pi * cyc * t)).draw(c, pens, boil)
        night_overlay(c, n, stars, star, night, cam, sky, sun)
    return draw


# ---------- 2.8 side view (D-29 style): he writes physics into the sand; then the row behind him glows ----

def sand_writing_side(ctx, shot):
    """Side view (D-29 style), as a time-lapse (user idea): he writes equations into the sand at different spots;
    each take cross-dissolves into the next, so briefly two or three of him are writing at once. The takes get
    shorter (time passing faster). The last one stays, and on "Every particle" he looks up at the row behind him,
    which glows here / not here / here. Within a take only his arm and a slight lean move: no sliding, no jumps."""
    pens = ctx.pens
    plate = ctx.desert()
    bg = bake(lambda c, b: (full(c, plate), horizon(c, boil=b)))
    cue = shot.cues
    font = Lettering(46)
    groove = skia.Paint(AntiAlias=True, Color=skia.Color(118, 84, 52, 235))
    warm = skia.Paint(AntiAlias=True, Color=skia.Color(255, 225, 150), BlendMode=skia.BlendMode.kScreen,
                      MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 12))
    cool = skia.Paint(AntiAlias=True, Color=skia.Color(200, 215, 255), BlendMode=skia.BlendMode.kScreen,
                      MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 12))
    gy = H * 0.80
    # (text, x of its first letter, row offset in the sand); later takes are quicker: time speeds up
    takes = [("E = mc²", W * 0.30, 10), ("F = ma", W * 0.57, 10), ("S = k ln W", W * 0.10, 30),
             ("ΔxΔp ≥ ħ/2", W * 0.40, 50)]
    widths = [font.measure(t[0]) for t in takes]
    write = [1.8, 1.4, 1.1, 1.0]
    fade = 0.6
    starts = [0.3]
    for i in range(1, len(takes)):
        starts.append(starts[-1] + write[i - 1] + 0.1)        # next take fades in while this one fades out
    row_y, sp = H * 0.64, 50.0
    row_pat = [1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1]
    row_x0 = W * 0.12
    A, B, C = 10, 11, 12
    row_pat[A], row_pat[B], row_pat[C] = 1, 0, 1
    last = len(takes) - 1

    def take_alpha(i, t):
        a = smooth((t - starts[i] + fade) / fade)                  # fades in just before writing starts
        if i < last:
            a *= 1 - smooth((t - starts[i] - write[i] - 0.1) / fade)
        return a

    def figure_for(i, t, look):
        txt, x0, dy = takes[i]
        f = float(np.clip((t - starts[i]) / write[i], 0, 1))
        return writer(x0, widths[i], f, gy + dy, 1.2, head=-35 - 40 * look)

    def draw(c, t, boil):
        look = smooth((t - cue["string"] + 0.6) / 0.8)
        with Camera(c) as cam:
            cam.look(1.2 - 0.1 * look, W * 0.47, H * (0.76 - 0.06 * look))   # wide enough for every take
            full(c, bg[boil])
            for j, v in enumerate(row_pat):
                if v:
                    pens.rock(c, row_x0 + j * sp, row_y, 14, 9, 0.2 * np.sin(j), seed=6000 + j, boil=boil)
            for idx, key, paint, strength in ((A, "here1", warm, 0.75), (B, "not", cool, 0.35), (C, "here2", warm, 0.75)):
                if t >= cue[key]:
                    paint.setAlphaf(float(min(1.0, (t - cue[key]) / 0.35) * strength))
                    c.drawCircle(row_x0 + idx * sp, row_y - 2, 22, paint)
            for i, (txt, x0, dy) in enumerate(takes):              # equations stay once written
                f = float(np.clip((t - starts[i]) / write[i], 0, 1))
                if f <= 0:
                    continue
                c.save()
                c.translate(x0, gy + dy)
                c.scale(1, 0.42)
                c.clipRect(skia.Rect.MakeLTRB(-4, -60, widths[i] * f, 20))
                font.draw(c, txt, 0, 0, groove)
                c.restore()
            for i in range(len(takes)):                            # every take of him, faded by its alpha
                a = take_alpha(i, t)
                if a <= 0.01:
                    continue
                fig = figure_for(i, t, look if i == last else 0.0)
                shadow(c, pens, fig.x - 10, fig.ground - 5, alpha=a)     # onto the sand, faded by alpha
                c.saveLayerAlpha(None, int(255 * a))
                fig.draw(c, pens, boil, seed=300 + i * 40)
                c.restore()
    return draw


# ---------- 2.9 two sparks meet in the rock field; he watches -----------------------------

def sparks_meet(ctx, shot):
    bg = rows_static(ctx)
    pens = ctx.pens
    hit = shot.cues["bumping"]
    rows = rock_rows()
    row = sorted([r for r in rows if r[5] == 1], key=lambda r: r[0])       # a middle row, left to right
    glow = skia.Paint(AntiAlias=True, Color=skia.Color(255, 230, 160, 230), BlendMode=skia.BlendMode.kScreen,
                      MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 7))
    core = skia.Paint(AntiAlias=True, Color=skia.Color(255, 250, 230))
    mid = len(row) // 2

    def rock_pos(i):
        return np.array([row[i][0], row[i][1] - row[i][3] * 0.9])

    def spark(t, start, sign):
        """Hop from rock to rock toward the middle; after the hit, drift apart and fade."""
        if t < hit:
            f = smooth(t / hit)
            i = start + sign * f * abs(mid - start)
            a, b = int(np.floor(i)), int(np.ceil(i))
            p = rock_pos(a) + (rock_pos(b) - rock_pos(a)) * (i - a)
            return p - (0, 8 * abs(np.sin(np.pi * (i - a)))), 1.0
        k = (t - hit) / (shot.duration - hit)
        return rock_pos(mid) + (sign * -1 * 90 * k, -60 * k), max(0.0, 1 - k * 1.2)

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(1.25, W * 0.5, H * 0.66)
            full(c, bg[boil])
            for start, sign in ((0, 1), (len(row) - 1, -1)):
                p, a = spark(t, start, sign)
                glow.setAlphaf(0.9 * a)
                c.drawCircle(float(p[0]), float(p[1]), 9, glow)
                core.setAlphaf(a)
                c.drawCircle(float(p[0]), float(p[1]), 2.4, core)
            if hit <= t < hit + 0.4:
                k = (t - hit) / 0.4
                p = rock_pos(mid)
                glow.setAlphaf(1 - k)
                c.drawCircle(float(p[0]), float(p[1]), 14 + 30 * k, glow)
            shadow(c, pens, W * 0.83, H * 0.9 - 5, w=136)
            Figure(x=W * 0.83, ground=H * 0.9, scale=1.05, facing=-1,
                   pose=replace(POSES["stand"], head=18)).draw(c, pens, boil)
    return draw


SCENES = {"first_row": first_row, "rule_side": rule_side, "rows_behind": rows_behind, "dune_view": dune_view,
          "desert_wide": desert_wide, "place_deadpan": place_deadpan, "week_of_walking": week_of_walking,
          "sand_writing_side": sand_writing_side, "sparks_meet": sparks_meet}
