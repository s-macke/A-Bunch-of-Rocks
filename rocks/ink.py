"""Hand-drawn ink primitives drawn per frame with skia (D-7, D-12)."""
import numpy as np
import skia
from scipy.ndimage import gaussian_filter

from .config import INK


def wobble(pts, amp, seed, step=4.0):
    """Resample a polyline and add smooth jitter; a different seed per boil state makes lines boil."""
    pts = np.asarray(pts, float)
    seg = [a + (b - a) * np.linspace(0, 1, max(2, int(np.linalg.norm(b - a) / step)), endpoint=False)[:, None]
           for a, b in zip(pts[:-1], pts[1:])] + [pts[-1:]]
    seg = np.vstack(seg)
    return seg + gaussian_filter(np.random.default_rng(seed).normal(0, 1, seg.shape), (3, 0)) * amp * 2.2


def path_of(pts, close=False):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    return p


def blob(cx, cy, rx, ry, rot, seed, n=40, irr=0.12):
    r = np.random.default_rng(seed)
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    k = 1 + gaussian_filter(r.normal(0, irr, n), 2, mode="wrap") * 2.5
    x, y = rx * k * np.cos(a), ry * k * np.sin(a)
    c, s = np.cos(rot), np.sin(rot)
    return np.stack([cx + c * x - s * y, cy + s * x + c * y], 1)


def circle(c, r, n=48, overshoot=0.08):
    a = np.linspace(0, 2 * np.pi * (1 + overshoot), n)
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a)], 1)


class Pens:
    """Shared paints: ink line, rock fill (grain shader, opaque), soft ground shadow (multiply), fine ink dots."""

    def __init__(self, grain):
        self.ink = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, Color=skia.Color(*INK),
                              StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
        # opaque, so a rock in front covers the one behind it; the colour is what the earlier multiplied wash gave on
        # sand: (195, 185, 180) x sand (216, 188, 152) / 255 (the sprites use the same, see sprites.FILL)
        self.fill = skia.Paint(AntiAlias=True, MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 1.2))
        self.fill.setShader(skia.Shaders.Blend(
            skia.BlendMode.kModulate, skia.Shaders.Color(skia.Color(165, 136, 107)),
            grain.makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat)))
        self.shadow = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kMultiply, Color=skia.Color(215, 200, 190, 150),
                                 MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 4))
        self.hatch = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, Color=skia.Color(70, 60, 60), StrokeWidth=1.3)

    def line(self, c, pts, width, seed, amp=0.9):
        self.ink.setStrokeWidth(width)
        c.drawPath(path_of(wobble(pts, amp, seed)), self.ink)

    def rock(self, c, x, y, rx, ry, rot, seed, boil):
        b = blob(x, y, rx, ry, rot, seed)
        c.drawPath(path_of(b, close=True), self.fill)
        self.line(c, np.vstack([b, b[:3]]), 1.4 + rx / 18, seed * 7 + boil, amp=0.4)
