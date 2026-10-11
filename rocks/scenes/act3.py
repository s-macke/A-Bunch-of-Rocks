"""Act 3 "Universe" (spec §1, D-27): not much → infinite time and space → more and more particles → "I decided
to simulate a universe." → a narration-free big bang that swirls into a galaxy → eons blur → stars, dust,
planets → life copying itself → someone stands up and looks around.

Space is painted on a dark wash with the paper grain multiplied on top, so it stays "sketchbook", and light is
added with screen-blended soft glows (watercolor blooms)."""
from dataclasses import replace
import numpy as np
import skia

from ..config import W, H, HORIZON
from ..rig import Figure, BlendFigure, POSES, walk, blend, walk_distance_per_cycle
from ..ink import circle
from ..sprites import SHAPES
from .common import bake, Camera, fade_to, horizon, smooth, full, boil_jitter, shadow
from .common import night_overlay, night_tools, day
from .desert import COLS, world, rows_static, rock_rows, field_rows, dune_plate, PLACED_ROCK, PLACED_SEED

GY = H * 0.86
DUSK = 0.65          # how dark it gets as he decides to simulate a universe (end of 3.4, start of 3.5)


def glow(color, blur, alpha=1.0):
    p = skia.Paint(AntiAlias=True, Color=skia.Color(*color), BlendMode=skia.BlendMode.kScreen,
                   MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    p.setAlphaf(alpha)
    return p


def _space_plate(washer):
    base = washer.paper() * np.array([0.16, 0.17, 0.26])            # deep indigo paper
    base = washer.wash(base, [(0, 0), (W, 0), (W, H), (0, H)], (120, 110, 170), 0.35, 1, 30)
    return base


def space_bg(ctx):
    return ctx.plate("space", {"v": 1}, _space_plate)


# ---------- 3.1 "Which isn't much." ---------------------------------------------------------

def not_much(ctx, shot):
    bg = rows_static(ctx, zoom=1.5)
    pens = ctx.pens
    x = W * 0.7

    def draw(c, t, boil):
        k = smooth((t - 0.5) / 0.4) * (1 - smooth((t - 1.6) / 0.4))
        with Camera(c) as cam:
            cam.look(1.5, x - 40, GY - 110)
            full(c, bg[boil])
            c.drawOval(skia.Rect.MakeXYWH(x - 70, GY - 5, 150, 10), pens.shadow)
            Figure(x=x, ground=GY, pose=blend(POSES["stand"], POSES["shrug"], k), facing=-1, scale=1.1).draw(c, pens, boil)
    return draw


# ---------- 3.2 "But I have infinite time and space." — rows converging to the horizon ---------

def infinite(ctx, shot):
    pens = ctx.pens
    plate = ctx.desert()
    sprites = ctx.sprites
    vp = np.array([W * 0.5, H * HORIZON])
    rng = np.random.default_rng(32)

    def static(c, b):
        full(c, plate)
        horizon(c, boil=b)
        for a in np.linspace(-1.35, 1.35, 23):                     # rays of rocks from the vanishing point
            d = np.array([np.sin(a), np.cos(a)])
            for u in np.geomspace(4, 1300, 70):                     # distance along the ray
                p = vp + d * u
                if p[1] > H + 20 or p[0] < -20 or p[0] > W + 20 or rng.random() < 0.25:
                    continue
                size = 1.0 + 0.045 * u
                if size < 3:
                    dx, dy = boil_jitter(int(p[0] * 7 + p[1]), b)
                    c.drawCircle(float(p[0] + dx), float(p[1] + dy), size * 0.5, pens.hatch)
                else:
                    c.save()
                    c.translate(float(p[0]), float(p[1]))
                    c.scale(1, 0.62)
                    sprites.draw(c, 0, 0, size / 0.62 * 0.9, int(u) % SHAPES, b)
                    c.restore()
    bg = bake(static)

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(1.0 + 0.12 * smooth(t / shot.duration), W / 2, H * 0.55)
            full(c, bg[boil])
            shadow(c, pens, W * 0.5, H * 0.9 - 4.5, w=117)
            Figure(x=W * 0.5, ground=H * 0.9, pose=POSES["look_up"], scale=0.9, facing=-1).draw(c, pens, boil)
    return draw


# ---------- 3.3 more particles, then more ----------------------------------------------------

def _field(ctx):
    cells = ctx.cache("world", world)
    sprites = ctx.sprites
    plate = ctx.plate("dune", {"v": 1}, dune_plate)
    rows = field_rows(70, H * 0.2, H * 1.02, 30, 2.2)
    dot = skia.Paint(AntiAlias=True, Color=skia.Color(110, 92, 84, 200))
    rocks = []
    for k, (y, sp, size) in enumerate(rows):
        ncell = int(W / sp) + 2
        off = COLS // 2 - ncell // 2
        for jj in np.nonzero(cells[k, off:off + ncell])[0]:
            rocks.append((jj * sp - sp / 2, y, size, k, jj))

    def static(c, b):
        full(c, plate)
        horizon(c, H * 0.2, b)
        for x, y, size, k, jj in rocks:
            if size < 4:
                dx, dy = boil_jitter(k * 1000 + jj, b)
                c.drawCircle(x + dx, y + dy, max(0.6, size * 0.45), dot)
            else:
                c.save()
                c.translate(x, y)
                c.scale(1, 0.62)
                sprites.draw(c, 0, 0, size / 0.62 * 0.9, (k * 7 + jj * 13) % SHAPES, b)
                c.restore()
    return bake(static, 3.2), rocks


def more_particles(ctx, shot):
    bg, rocks = ctx.cache("field3", lambda: _field(ctx))
    pens = ctx.pens
    rng = np.random.default_rng(33)
    idx = rng.permutation(len(rocks))
    pos = np.array([(r[0], r[1] - r[2] * 0.5) for r in rocks])
    size = np.array([r[2] for r in rocks])
    t_more, t_stop = shot.cues["more"], shot.cues["stopped"]
    spark = glow((255, 225, 150), 5, 0.7)
    core = skia.Paint(AntiAlias=True, Color=skia.Color(255, 250, 230))

    def count(t):
        """2 sparks, doubling faster and faster; after "stopped counting" the field is simply full."""
        if t < t_more:
            return 2 + int(6 * smooth(t / t_more))
        if t < t_stop:
            return int(8 * 2 ** ((t - t_more) / (t_stop - t_more) * 5))
        return min(len(rocks) // 3, int(256 * 2 ** ((t - t_stop) * 1.2)))      # a full field, not snow

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(1.05, W * 0.5, H * 0.52)
            full(c, bg[boil])
            n = min(len(rocks), count(t))
            hop = (t * 2.2 + np.arange(n) * 0.37) % 1.0                  # each spark hops, rock to rock
            for m in range(n):
                i = idx[m]
                p = pos[i] + (0, -np.sin(np.pi * hop[m]) * (3 + size[i] * 0.4))
                r = 1.5 + size[i] * 0.22
                c.drawCircle(float(p[0]), float(p[1]), r * 2.2, spark)
                c.drawCircle(float(p[0]), float(p[1]), max(0.8, r * 0.5), core)
        # in front of the field, standing still and watching it fill (not a speck inside it)
        c.drawOval(skia.Rect.MakeXYWH(W * 0.2 - 40, H * 0.97 - 4, 90, 8), pens.shadow)
        Figure(x=W * 0.2, ground=H * 0.97, scale=0.62, pose=POSES["look_up"], facing=1).draw(c, pens, boil)
    return draw


# ---------- 3.4 "I decided to simulate a universe." ------------------------------------------

DECIDED_X = W * 0.62                 # where he stands in 3.4
DECIDED_VIEW = (2.05, DECIDED_X - 30, GY - 115)  # 3.4's camera at its end (zoom, centre): 3.5 may start from it


def _decided_figure(c, pens, boil):
    shadow(c, pens, DECIDED_X, GY - 5)
    Figure(x=DECIDED_X, ground=GY, pose=replace(POSES["stand"], head=-14), facing=-1).draw(c, pens, boil)


def decided(ctx, shot):
    bg = rows_static(ctx, zoom=2.05)
    pens = ctx.pens
    stars, star, night = night_tools()
    sky = ctx.desert_sky()
    z1, cx, cy = DECIDED_VIEW

    def draw(c, t, boil):
        with Camera(c) as cam:
            cam.look(z1 - 0.15 + 0.15 * smooth(t / shot.duration), cx, cy)
            full(c, bg[boil])
            _decided_figure(c, pens, boil)
        night_overlay(c, DUSK * smooth(t / shot.duration), stars, star, night, cam, sky)   # dusk gathers from daylight
    return draw


# ---------- 3.5 THE BIG PAUSE: into a spark, darkness, a watercolor big bang, a galaxy ----------

def _into_the_rows(ctx):
    """big_bang's first 1.6 s, without a cut from 3.4: from 3.4's last view the camera pans left onto a rock in the
    rows and zooms in; the rock lights up and its light fills the frame. Drawn live (not baked): the zoom goes far."""
    pens = ctx.pens
    plate = ctx.desert()
    rocks = rock_rows()
    stars, star, night = night_tools()
    sky = ctx.desert_sky()
    z0, x0, y0 = DECIDED_VIEW
    rock = min(rocks, key=lambda r: (r[0] - W * 0.36) ** 2 + 30 * (r[5] - 1) ** 2)   # 2nd row, left of him
    sp = np.array([rock[0], rock[1] - rock[3] * 0.3])
    z1 = 6.0

    def draw(c, t, boil):
        k = smooth(t / 1.6)
        z = z0 * (z1 / z0) ** k
        with Camera(c) as cam:
            cam.look(z, x0 + (sp[0] - x0) * k, y0 + (sp[1] - y0) * k)
            full(c, plate)
            horizon(c, boil=boil)
            for i, r in enumerate(rocks):
                pens.rock(c, *r[:5], seed=i, boil=boil)
            pens.rock(c, *PLACED_ROCK, seed=PLACED_SEED, boil=boil)
            _decided_figure(c, pens, boil)
        night_overlay(c, DUSK, stars, star, night, cam, sky)
        g = smooth((t - 0.3) / 1.3)
        with Camera(c) as cam:
            cam.look(z, x0 + (sp[0] - x0) * k, y0 + (sp[1] - y0) * k)
            c.drawCircle(float(sp[0]), float(sp[1]), 3 + 40 * g ** 2, glow((255, 230, 160), 3 + 20 * g ** 2, g))
        wash = skia.Paint(Color=skia.Color(255, 244, 215))
        wash.setAlphaf(float(smooth((t - 0.8) / 0.8)))
        c.drawRect(skia.Rect.MakeWH(W, H), wash)
    return draw


def big_bang(ctx, shot):
    """No narration (D-27). 0–1.6 s: no cut from 3.4, the camera pans into the rows onto a rock whose light fills
    the frame (_into_the_rows); 1.6–2.6 s: the light gives way to dark paper; 3.2 s: a point of light; 4.0 s: the
    bang, a bloom and particles flying out; then gravity and rotation pull the particles into a spiral galaxy that
    turns slowly until the end."""
    into = _into_the_rows(ctx)
    space = space_bg(ctx)
    paper = ctx.paper
    grain = skia.Paint(BlendMode=skia.BlendMode.kMultiply)
    grain.setAlphaf(0.35)
    rng = np.random.default_rng(35)
    n = 2600
    # final galaxy: two log-spiral arms + a bulge
    arm = rng.integers(0, 2, n)
    rr = rng.gamma(2.0, 70, n) + 8
    theta = np.log(rr) * 2.3 + arm * np.pi + rng.normal(0, 0.28, n)
    bulge = rng.random(n) < 0.22
    rr[bulge] = np.abs(rng.normal(0, 30, bulge.sum()))
    theta[bulge] = rng.uniform(0, 2 * np.pi, bulge.sum())
    flat = 0.45                                                       # tilted disc
    # explosion directions
    ex_dir = rng.normal(0, 1, (n, 2))
    ex_dir /= np.linalg.norm(ex_dir, axis=1, keepdims=True)
    ex_speed = rng.uniform(0.3, 1.0, n) ** 0.5
    warm = rng.random(n)
    centre = np.array([W / 2, H / 2])
    t_point, t_bang = 3.2, 4.0
    dot = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kScreen)

    def draw(c, t, boil):
        if t < 1.6:
            into(c, t, boil)
            return
        full(c, space)
        if t < 2.6:                                                   # light fades into the dark
            wash = skia.Paint(Color=skia.Color(255, 244, 215))
            wash.setAlphaf(float(1 - smooth((t - 1.6) / 1.0)))
            c.drawRect(skia.Rect.MakeWH(W, H), wash)
        if t_point <= t < t_bang:                                     # a single point of light
            k = smooth((t - t_point) / 0.8)
            c.drawCircle(float(centre[0]), float(centre[1]), 1.5 + 2 * k, glow((255, 250, 235), 3, k))
        if t >= t_bang:
            u = t - t_bang
            # bloom: warm watercolor flash that fades into a soft nebula
            b = np.exp(-u * 1.2)
            c.drawCircle(float(centre[0]), float(centre[1]), 60 + 420 * (1 - np.exp(-u * 2.5)),
                         glow((255, 200, 140), 80, 0.9 * b + 0.12))
            c.drawCircle(float(centre[0]), float(centre[1]), 20 + 120 * (1 - np.exp(-u * 3)),
                         glow((255, 245, 225), 30, 0.8 * b + 0.1))
            # particles: fly out, then settle into the rotating spiral
            expand = (1 - np.exp(-u * 1.8))
            ex = centre + ex_dir * ex_speed[:, None] * 520 * expand
            s = smooth((u - 1.2) / 5.5)
            rot = theta + 0.18 * u + 0.9 / np.sqrt(rr / 60 + 0.3) * u * 0.12
            gal = centre + np.stack([rr * np.cos(rot), rr * np.sin(rot) * flat], 1) * (1.0 + 0.08 * s)
            p = ex * (1 - s) + gal * s
            fade_in = min(1.0, u * 3)
            for i in range(n):
                col = (255, 214, 160) if warm[i] < 0.45 else (190, 205, 255) if warm[i] > 0.8 else (250, 240, 230)
                dot.setColor(skia.Color(*col))
                dot.setAlphaf(float(fade_in * (0.55 + 0.45 * ((i * 7919) % 97) / 97)))
                c.drawCircle(float(p[i, 0]), float(p[i, 1]), 1.1 + (i % 5) * 0.25, dot)
            if s > 0:                                                  # the galaxy's glowing core and arm haze
                c.drawOval(skia.Rect.MakeXYWH(centre[0] - 70, centre[1] - 32, 140, 64), glow((255, 225, 170), 30, 0.7 * s))
        full(c, paper, grain)        # paper grain over space
        fade_to(c, ctx.paper, 0)
    return draw


# ---------- 3.6 the eons blur past while I walk down a single row ------------------------------

def eons_blur(ctx, shot):
    pens = ctx.pens
    plate = ctx.desert()
    bg = bake(lambda c, b: (full(c, plate), horizon(c, boil=b)))
    stars, star, night = night_tools()
    sky = ctx.desert_sky()
    cells = ctx.cache("world", world)
    cyc = 12.0 / walk_distance_per_cycle()                    # he moves 12 px/s: feet stay planted
    streak = skia.Paint(AntiAlias=True, Color=skia.Color(120, 100, 88, 150), StrokeCap=skia.Paint.kRound_Cap)
    t_rows = shot.cues["rows"]
    far_rows = field_rows(9, H * HORIZON, H * 0.8, 30, 6)

    def draw(c, t, boil):
        full(c, bg[boil])
        # far rows: each frame a later generation (the pattern flickers as rows are computed)
        gen = int(t * 12 * (1 + 4 * smooth((t - t_rows) / 1.5)))
        for k, (y, sp, size) in enumerate(far_rows):
            ncell = int(W / sp) + 2
            row = cells[(gen + k) % len(cells)]
            off = COLS // 2 - ncell // 2
            for jj in np.nonzero(row[off:off + ncell])[0]:
                x = jj * sp - sp / 2
                streak.setStrokeWidth(max(1.0, size * 0.5))
                c.drawLine(x - size * 1.4, y, x + size * 1.4, y, streak)     # motion-smeared rocks
        x = W * 0.6 - 12 * t
        c.drawOval(skia.Rect.MakeXYWH(x - 55, GY - 5, 120, 10), pens.shadow)
        Figure(x=x, ground=GY, pose=walk(2 * np.pi * cyc * t), facing=-1).draw(c, pens, boil)
        n, sun = day(0.9 * t)
        night_overlay(c, 0.7 * n, stars, star, night, sky=sky, sun=sun)          # last: night darkens him too
    return draw


# ---------- 3.7 stars, dust, planets ------------------------------------------------------------

def stars_dust_planets(ctx, shot):
    space = space_bg(ctx)
    paper = ctx.paper
    grain = skia.Paint(BlendMode=skia.BlendMode.kMultiply)
    grain.setAlphaf(0.35)
    pens = ctx.pens
    cue = shot.cues
    rng = np.random.default_rng(37)
    m = 9
    home = np.stack([rng.uniform(W * 0.12, W * 0.88, m), rng.uniform(H * 0.15, H * 0.85, m)], 1)
    home[4] = (W * 0.5, H * 0.5)                                        # the star that gets planets
    clouds = rng.normal(0, 1, (m, 40, 2)) * 60
    dust = rng.normal(0, 1, (m, 60, 2)) * 1.0
    dot = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kScreen)
    _, star, night = night_tools()
    planets = [(95, 0.9, (150, 190, 255), 12), (150, 0.55, (230, 170, 120), 15), (215, 0.35, (170, 220, 170), 14)]

    def draw(c, t, boil):
        full(c, space)
        clump = smooth(t / cue["stars"])                                 # gas clumps into stars
        burn = smooth((t - cue["burned"]) / 2.0)                          # most stars burn down to dust
        disk = smooth((t - cue["burned"] - 1.0) / 1.5)
        form = smooth((t - cue["planets"] + 1.2) / 1.8)                   # the dust clumps into planets
        for s in range(m):
            is_home = s == 4
            b = 0.0 if is_home else burn
            for q in range(40):                                           # gas
                p = home[s] + clouds[s, q] * (1 - 0.92 * clump)
                dot.setColor(skia.Color(210, 190, 255))
                dot.setAlphaf(float(0.25 * (1 - clump) + 0.02))
                c.drawCircle(float(p[0]), float(p[1]), 6, dot)
            if clump > 0.3 and b < 1:                                     # the star itself
                a = (clump - 0.3) / 0.7 * (1 - b)
                c.drawCircle(float(home[s][0]), float(home[s][1]), 10 + 8 * b, glow((255, 225, 170), 14, a))
                c.drawCircle(float(home[s][0]), float(home[s][1]), 3, glow((255, 252, 240), 2, a))
            if b > 0:                                                     # a puff of dust
                for q in range(60):
                    p = home[s] + dust[s, q] * (10 + 70 * b)
                    dot.setColor(skia.Color(230, 190, 150))
                    dot.setAlphaf(float(0.6 * b))
                    c.drawCircle(float(p[0]), float(p[1]), 1.3, dot)
        # the home star: a dust disc that clumps into orbiting planets
        cx, cy = home[4]
        if disk > 0:
            for q in range(160):
                r = 60 + (q * 37 % 190)
                a = q * 2.39996 + t * 0.6 * 60 / r
                dot.setColor(skia.Color(230, 200, 160))
                dot.setAlphaf(float(0.5 * disk * (1 - form)))
                c.drawCircle(float(cx + r * np.cos(a)), float(cy + r * np.sin(a) * 0.4), 1.2, dot)
        for r, w, col, rad in planets:
            if form <= 0:
                continue
            a = t * w + r
            px, py = cx + r * np.cos(a), cy + r * np.sin(a) * 0.4
            paint = skia.Paint(AntiAlias=True, Color=skia.Color(*col))
            paint.setAlphaf(float(form))
            c.drawCircle(float(px), float(py), rad * form, paint)
            pens.line(c, circle((px, py), rad * form), 1.4, 8700 + r + boil, amp=0.2)
        full(c, paper, grain)
    return draw


# ---------- 3.8 something started copying itself ------------------------------------------------

def _planet_plate(washer):
    """A small watercolor planet on the space paper: sea, land patches, a soft terminator."""
    base = _space_plate(washer)
    t = np.linspace(0, 2 * np.pi, 90)
    cx, cy, r = W * 0.5, H * 0.5, 170
    disc = np.stack([cx + r * np.cos(t), cy + r * np.sin(t)], 1)
    paper = washer.paper()
    yy, xx = np.mgrid[0:H, 0:W]
    inside = ((xx - cx) ** 2 + (yy - cy) ** 2) < r ** 2
    base[inside] = paper[inside]                                     # the planet is a disc of bare paper...
    base = washer.wash(base, disc, (110, 165, 200), 0.85, 0, 3)      # ...washed with sea
    for i, (dx, dy, rx, ry) in enumerate([(-60, -50, 70, 40), (50, 40, 55, 35), (-10, 90, 40, 20)]):
        blob_t = np.linspace(0, 2 * np.pi, 40)
        land = np.stack([cx + dx + rx * np.cos(blob_t) * (1 + 0.2 * np.sin(3 * blob_t + i)),
                         cy + dy + ry * np.sin(blob_t)], 1)
        base = washer.wash(base, land, (150, 180, 115), 0.8, i, 3)
    shade = np.stack([cx + 40 + r * np.cos(t), cy + r * np.sin(t)], 1)
    base = washer.wash(base, shade, (120, 120, 170), 0.35, 2, 30)     # night side
    return base


def _sea_plate(washer):
    base = washer.paper()
    base = washer.wash(base, [(0, 0), (W, 0), (W, H), (0, H)], (120, 175, 200), 0.75, 0, 10)
    rng = np.random.default_rng(3)
    for i in range(9):                                               # lighter and darker currents
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        t = np.linspace(0, 2 * np.pi, 30)
        poly = np.stack([x + rng.uniform(120, 300) * np.cos(t), y + rng.uniform(40, 110) * np.sin(t)], 1)
        base = washer.wash(base, poly, (95, 150, 185) if i % 2 else (175, 210, 215), 0.35, i, 25)
    return base


def life(ctx, shot):
    """"On one of them, something started copying itself. It got good at it." A watercolor planet, then its sea:
    one cell, two, four ... each one pinching in two."""
    planet = ctx.plate("planet", {"v": 1}, _planet_plate)
    sea = ctx.plate("sea", {"v": 1}, _sea_plate)
    pens = ctx.pens
    cell_fill = skia.Paint(AntiAlias=True, Color=skia.Color(225, 240, 228, 210))
    rng = np.random.default_rng(38)
    pool = list(rng.uniform(-1, 1, (64, 2)))
    spots = [pool.pop(0)]                         # cell i + n/2 is the daughter of cell i: give it the free spot
    while len(spots) < 64:                        # nearest to its parent, so it only slides a short way
        for parent in list(spots):
            if len(spots) == 64:
                break
            near = int(np.argmin([np.hypot(*(q - parent)) for q in pool]))
            spots.append(pool.pop(near))
    spots = np.array(spots)
    t_sea = 1.6

    def spread(n):
        return np.array([420, 230]) * min(1.0, n / 24) ** 0.5

    def cell_pos(i, n, e):
        """Where cell i sits while n cells exist; e (0..1) eases the colony's spread from n/2 cells to n, so the
        older cells drift apart smoothly as the new ones appear instead of jumping."""
        s = spread(max(1, n // 2)) + (spread(n) - spread(max(1, n // 2))) * e
        return np.array([W * 0.5, H * 0.5]) + spots[i] * s

    def draw(c, t, boil):
        if t < t_sea + 0.6:
            with Camera(c) as cam:
                m = smooth(t / (t_sea + 0.6))              # zoom and aim move together: no swing at the start
                cam.look(1.0 + 1.6 * m, W * (0.5 - 0.04 * m), H * (0.5 - 0.06 * m))
                full(c, planet)
                pens.line(c, circle((W * 0.5, H * 0.5), 170), 2.2, 8900 + boil, amp=0.6)
        if t >= t_sea:
            c.save()
            full(c, sea, skia.Paint(Alphaf=float(smooth((t - t_sea) / 0.6))))
            c.restore()
            gens = min(5.999, (t - t_sea - 0.3) / 0.75)          # stops just before a 7th split, the 6th complete
            if gens >= 0:
                n = 2 ** int(gens)
                split = gens - int(gens)
                e = smooth(min(1.0, split * 1.4))
                for i in range(n):
                    base = cell_pos(i, n, e)
                    if n > 1 and i >= n // 2:                  # the newest half slides out of its parent
                        parent = cell_pos(i - n // 2, n, e)
                        base = parent + (base - parent) * e
                    r = 20 * (0.9 + 0.15 * np.sin(i * 1.7))
                    squeeze = 1 + 0.4 * np.sin(np.pi * min(1.0, split * 1.4)) if split < 0.7 else 1.0
                    c.drawOval(skia.Rect.MakeXYWH(base[0] - r * squeeze, base[1] - r, 2 * r * squeeze, 2 * r), cell_fill)
                    pens.line(c, circle(base, r), 2.0, 9000 + i + boil, amp=0.35)
                    pens.line(c, [base + (-4, -2), base + (4, 2)], 1.4, 9100 + i + boil, amp=0.2)
    return draw


# ---------- 3.9 it stood up, looked around, wondered ------------------------------------------

def stood_up(ctx, shot):
    pens = ctx.pens
    stars, star, night = night_tools(9)
    plate = ctx.plate("hill", {"v": 1}, _hill_plate)
    x, gy = W * 0.46, H * 0.7

    def draw(c, t, boil):
        full(c, plate)
        crouch = Figure(x=x, ground=gy, pose=POSES["crouch"], facing=1, scale=0.8)
        stand = Figure(x=x, ground=gy, pose=POSES["stand"], facing=1, scale=0.8)
        up = Figure(x=x, ground=gy, pose=POSES["look_up"], facing=1, scale=0.8)
        if t < 0.8:
            fig = crouch
        elif t < 2.0:
            fig = BlendFigure(crouch, stand, (t - 0.8) / 1.2)
        elif t < 3.0:
            fig = Figure(x=x, ground=gy, pose=POSES["stand"], facing=-1 if 2.4 < t < 2.9 else 1, scale=0.8)
        else:
            fig = BlendFigure(stand, up, (t - 3.0) / 0.8)
        fig.draw(c, pens, boil, width=2.8)
        night_overlay(c, 0.9, stars, star, night)                        # last: night darkens him too
        fade_to(c, ctx.paper, (t - (shot.duration - 1.8)) / 1.8)   # a page of the sketchbook turns (D-31)
    return draw


def _hill_plate(washer):
    base = washer.paper()
    base = washer.wash(base, [(0, 0), (W, 0), (W, H), (0, H)], (150, 170, 200), 0.5, 0, 14)
    xs = np.linspace(-20, W + 20, 40)
    top = H * 0.7 + 40 * ((xs - W * 0.46) / W) ** 2 * 6 - 0
    hill = list(zip(xs, top)) + [(W + 20, H + 20), (-20, H + 20)]
    base = washer.wash(base, hill, (120, 140, 110), 0.7, 1, 4)
    return base


SCENES = {"not_much": not_much, "infinite": infinite, "more_particles": more_particles, "decided": decided,
          "big_bang": big_bang, "eons_blur": eons_blur, "stars_dust_planets": stars_dust_planets, "life": life,
          "stood_up": stood_up}
