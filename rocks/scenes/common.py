"""Shared scene plumbing: context (pens, plates), baked backgrounds per boil state, camera, fades."""
import numpy as np
import skia

from ..config import W, H, BOIL, HORIZON, INK, OUT_W, OUT_H, RES
from ..textures import SUN, Washer, cached_plate, desert_plate, grain_image
from ..ink import Pens, path_of, wobble
from ..render import stage_canvas
from ..sprites import RockSprites


class Ctx:
    def __init__(self):
        self.pens = Pens(grain_image())
        self._washer = None
        self.paper = cached_plate("paper", {"v": 1}, lambda: self.washer.paper())

    def cache(self, name, make):
        """Share expensive objects (automaton, sprites, textures) between shots of one build."""
        if not hasattr(self, "_objs"):
            self._objs = {}
        if name not in self._objs:
            self._objs[name] = make()
        return self._objs[name]

    @property
    def washer(self):
        if self._washer is None:
            self._washer = Washer()
        return self._washer

    def plate(self, name, params, build):
        """build(washer) -> float RGB array; cached on disk by name+params."""
        return cached_plate(name, params, lambda: build(self.washer))

    @property
    def sprites(self):
        """Pre-drawn rock sprites, shared by all shots of one build."""
        return self.cache("sprites", lambda: RockSprites(grain_image()))

    def desert(self):
        return self.plate("desert", {"v": 1}, desert_plate)

    def desert_sky(self):
        """The desert's sky for night_overlay: the plate without the sun (painted over the baked sun) and the sun on
        its own, to draw wherever it is on its way across the sky."""
        return self.cache("desert_sky", lambda: Sky(self.desert(), self.plate("desert_nosun", {"v": 1},
                                                                             lambda w: desert_plate(w, sun=None))))


class Sky:
    """The sunless desert plate, and the sun cut out of the desert plate as a multiply sprite: the wash multiplied the
    sand by sun/nosun, so drawing that ratio with kMultiply anywhere on the sunless sky paints the same sun there."""
    R = SUN[2] * 1.6                                   # half size of the sprite: the wash's soft edge included

    def __init__(self, desert, nosun):
        self.image = nosun
        sx, sy = SUN[0] * W * RES, SUN[1] * H * RES
        r = int(self.R * RES)
        box = np.s_[int(sy) - r:int(sy) + r, int(sx) - r:int(sx) + r, :3]
        ratio = desert.toarray()[box].astype(float) / np.maximum(nosun.toarray()[box].astype(float), 1)
        ratio = np.clip(ratio * 255, 0, 255).astype(np.uint8)
        self.sun = skia.Image.fromarray(np.dstack([ratio, np.full(ratio.shape[:2], 255, np.uint8)])
                                        ).withDefaultMipmaps()


# the sun's way across the sky: it rises at the left horizon, crosses the whole picture and sets at the right one.
# angle 0 is noon (top middle), pi/2 sunset, pi midnight, 3pi/2 sunrise. The path is a flattened arc (it stays high
# most of the day and drops steeply near the horizon), through the spot where the desert plate paints the sun: that
# is the afternoon of every daylight shot, at angle SUN_DAY.
SUN_SPAN, SUN_FLAT = W * 0.40, 0.25
SUN_DAY = float(np.arcsin((SUN[0] - 0.5) * W / SUN_SPAN))
_SUN_BASE = H * HORIZON + 15                           # the sun's centre at sunset: just below the horizon
_SUN_RISE = (_SUN_BASE - H * SUN[1]) / np.cos(SUN_DAY) ** SUN_FLAT


def _elevation(angle):
    c = np.cos(angle)
    return np.sign(c) * abs(c) ** SUN_FLAT             # 1 noon, 0 on the horizon, -1 midnight


def sun_at(angle):
    """Where the sun is at `angle` (stage coordinates)."""
    return W / 2 + SUN_SPAN * np.sin(angle), _SUN_BASE - _SUN_RISE * _elevation(angle)


def day(cycles):
    """(night n, sun angle) after `cycles` days, starting in the afternoon of the daylight shots: it gets dark as
    the sun goes down (half dark when it touches the horizon, fully dark at midnight)."""
    angle = SUN_DAY + 2 * np.pi * cycles
    e0 = _elevation(SUN_DAY)
    return float(np.clip((e0 - _elevation(angle)) / (e0 + 1), 0, 1)), angle


def bake(draw_static, zoom=1.0):
    """Render draw_static(canvas, boil) once per boil state, at the output resolution times `zoom` (the most the
    shot's camera zooms in, so the baked lines stay as sharp as the live ones); returns images to draw with full()."""
    out = []
    for b in range(BOIL):
        s = skia.Surface.MakeRaster(skia.ImageInfo.Make(int(OUT_W * zoom), int(OUT_H * zoom),
                                                        skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
        draw_static(stage_canvas(s), b)
        out.append(s.makeImageSnapshot().withDefaultMipmaps())   # shrinks cleanly when the camera is wider
    return out


SMOOTH = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


def full(c, image, paint=None):
    """Draw a full-frame image (plate, paper, baked background) over the whole stage, whatever its pixel size."""
    c.drawImageRect(image, skia.Rect.MakeWH(W, H), SMOOTH, paint)


class Camera:
    """Zoom about a world point: world (cx, cy) lands on screen centre (or on `anchor`)."""

    def __init__(self, c):
        self.c = c

    def __enter__(self):
        self.c.save()
        return self

    def look(self, zoom, cx, cy, anchor=(W / 2, H / 2)):
        """Clamped so the view never leaves the W x H picture (zoom >= 1)."""
        zoom = max(1.0, zoom)
        hw, hh = anchor[0] / zoom, anchor[1] / zoom
        cx = min(max(cx, hw), W - (W - anchor[0]) / zoom)
        cy = min(max(cy, hh), H - (H - anchor[1]) / zoom)
        self.view = (zoom, cx, cy, anchor)
        self.c.translate(*anchor)
        self.c.scale(zoom, zoom)
        self.c.translate(-cx, -cy)

    def to_screen(self, x, y):
        """Where world point (x, y) appears on screen under the last look() (identity before any look)."""
        zoom, cx, cy, (ax, ay) = getattr(self, "view", (1.0, 0.0, 0.0, (0.0, 0.0)))
        return ax + (x - cx) * zoom, ay + (y - cy) * zoom

    def __exit__(self, *exc):
        self.c.restore()
        return False


def fade_to(c, image, alpha):
    """Cross-fade toward a full-frame image (e.g. blank paper) with alpha in 0..1."""
    if alpha <= 0:
        return
    full(c, image, skia.Paint(Alphaf=float(min(1.0, alpha))))


HORIZON_PAINT = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, Color=skia.Color(*INK), StrokeWidth=1.8,
                           StrokeCap=skia.Paint.kRound_Cap)


def boil_jitter(i, b, amp=0.35):
    """A tiny, fixed offset for dot i in boil drawing b: far-away dots shimmer with the line boil, like every
    other ink mark, instead of standing still."""
    return amp * np.sin(i * 12.9898 + b * 78.233), amp * np.cos(i * 4.1414 + b * 39.346)


def shadow(c, pens, x, y, w=130, alpha=1.0):
    """Soft ground shadow centred under x, its top at y. It is multiplied into the sand, so it must be drawn onto
    the sand directly (never inside a faded layer); `alpha` fades it instead."""
    p = skia.Paint(pens.shadow)
    p.setAlphaf(pens.shadow.getAlphaf() * alpha)
    c.drawOval(skia.Rect.MakeXYWH(x - w / 2 + 5, y, w, 10), p)


def horizon_points(y=H * HORIZON, boil=0):
    """The hand-drawn horizon: a long line, slightly uneven, that wobbles a little with every boil state."""
    return wobble([(0, y), (W * 0.4, y - 1), (W, y + 1)], 0.5, 20 + boil)


def horizon(c, y=H * HORIZON, boil=0):
    """Draw the horizon (the same line the cold open draws, so shots match at every cut)."""
    c.drawPath(path_of(horizon_points(y, boil)), HORIZON_PAINT)


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def night_overlay(c, n, stars, star_paint, night_paint, cam=None, sky=None, sun=None):
    """Darken toward night (n = 0 day .. 1 night); stars come out above n = 0.6.

    With `sky` (Ctx.desert_sky()) the sun moves along its arc (sun_at) and sets below the horizon: `sun` is its angle,
    by default the one that belongs to n on an evening (setting). Shots that run through whole days pass it (day()).
    Stars are world points above the horizon; with `cam` (the Camera the shot was drawn with) they and the sun are
    projected through its zoom, so they stay in the sky wherever the camera puts the horizon. Stars keep their size.
    """
    if sun is None:                                    # an evening: the sun as low as the darkness n says
        e0 = _elevation(SUN_DAY)
        e = e0 - min(max(n, 0.0), 1.0) * (e0 + 1)
        sun = float(np.arccos(np.sign(e) * abs(e) ** (1 / SUN_FLAT)))
    if sky is not None and abs((sun - SUN_DAY + np.pi) % (2 * np.pi) - np.pi) > 1e-3:
        c.save()
        if cam is not None and hasattr(cam, "view"):
            z, cx, cy, (ax, ay) = cam.view
            c.translate(ax, ay)
            c.scale(z, z)
            c.translate(-cx, -cy)
        c.save()                                       # paint the sunless sky over the baked sun...
        sx, sy, sr = SUN
        c.clipRect(skia.Rect.MakeLTRB(W * sx - sr * 1.8, H * sy - sr * 1.8, W * sx + sr * 1.8, H * sy + sr * 1.8))
        full(c, sky.image)
        c.restore()
        x, y = sun_at(sun)                             # ...and the sun where it is now, behind the horizon when it sets
        r = Sky.R
        c.clipRect(skia.Rect.MakeLTRB(0, 0, W, H * HORIZON - 3))
        c.drawImageRect(sky.sun, skia.Rect.MakeLTRB(x - r, y - r, x + r, y + r), SMOOTH,
                        skia.Paint(BlendMode=skia.BlendMode.kMultiply))
        c.restore()
    if n > 0.02:
        night_paint.setColor(skia.Color4f(1 - 0.75 * n, 1 - 0.7 * n, 1 - 0.45 * n, 1))
        c.drawRect(skia.Rect.MakeWH(W, H), night_paint)
    if n > 0.6:
        star_paint.setAlphaf(float((n - 0.6) / 0.4))
        for sx, sy in stars:
            x, y = cam.to_screen(sx, sy) if cam else (sx, sy)
            if 0 <= x <= W and 0 <= y <= H:
                c.drawCircle(float(x), float(y), 1.3, star_paint)


def night_tools(seed=7, n=80):
    """(stars, star paint, night paint) for night_overlay; stars are scattered over the sky above the horizon."""
    rng = np.random.default_rng(seed)
    stars = np.stack([rng.uniform(0, W, n), rng.uniform(0, H * HORIZON - 20, n)], 1)
    return stars, skia.Paint(AntiAlias=True, Color=skia.Color(255, 250, 225)), skia.Paint(BlendMode=skia.BlendMode.kMultiply)
