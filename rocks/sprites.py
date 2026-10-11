"""Rock sprites for the rock computer (D-18): a few rock shapes pre-drawn per boil state, stamped with
drawImageRect, which is fast enough for thousands of rocks per frame."""
import numpy as np
import skia

from .config import BOIL, INK
from .ink import blob, wobble, path_of

SPRITE = 64          # sprite canvas in stage units; rock radius ~ 22 inside it
SUPER = 4            # pixels per stage unit in the sprite images, so rocks stay sharp at 1080p and under zoom
# the same opaque rock colour as Pens.rock: (195, 185, 180) x the sand (216, 188, 152) / 255
FILL = (165, 136, 107)
SHAPES = 10


class RockSprites:
    def __init__(self, grain):
        fill = skia.Paint(AntiAlias=True, MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 1.0))
        fill.setShader(skia.Shaders.Blend(
            skia.BlendMode.kModulate, skia.Shaders.Color(skia.Color(*FILL)),
            grain.makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat)))
        ink = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, Color=skia.Color(*INK), StrokeWidth=2.6,
                         StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
        self.images = [[None] * BOIL for _ in range(SHAPES)]
        c0 = SPRITE / 2
        for s in range(SHAPES):
            rng = np.random.default_rng(900 + s)
            rx, ry, rot = 21 * rng.uniform(0.85, 1.05), 21 * rng.uniform(0.7, 0.95), rng.uniform(0, np.pi)
            b = blob(c0, c0, rx, ry, rot, seed=900 + s, irr=0.14)
            for k in range(BOIL):
                surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(SPRITE * SUPER, SPRITE * SUPER,
                                                                   skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
                c = surf.getCanvas()
                c.scale(SUPER, SUPER)
                c.drawPath(path_of(b, close=True), fill)
                c.drawPath(path_of(wobble(np.vstack([b, b[:3]]), 0.5, 7000 + s * 7 + k)), ink)
                self.images[s][k] = surf.makeImageSnapshot()

    def draw(self, c, x, y, size, shape, boil, paint=None):
        """Stamp a rock centred at (x, y); size = rock diameter in px."""
        d = size * SPRITE / 44.0
        c.drawImageRect(self.images[shape % SHAPES][boil], skia.Rect.MakeXYWH(x - d / 2, y - d / 2, d, d),
                        skia.SamplingOptions(skia.FilterMode.kLinear), paint)
