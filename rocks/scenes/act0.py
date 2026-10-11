"""Cold open (spec §1): blank paper; a horizon line draws itself; the sky and sand washes bleed in, and with them the
loose rocks and the man asleep among them; the title. It ends on the wide view that shot 1.1 starts from."""
import skia

from ..config import W, H, INK
from ..ink import path_of
from ..lettering import Lettering
from .common import smooth, horizon_points, HORIZON_PAINT, full
from .desert import static_desert, wake_rocks, sleeper, WAKE_X, WAKE_GY


def cold_open(ctx, shot):
    paper = ctx.paper
    pens = ctx.pens
    # the desert of shot 1.1 with its rocks and his shadow, without the horizon (that one draws itself here)
    shadow = skia.Rect.MakeXYWH(WAKE_X - 75, WAKE_GY - 5, 150, 10)
    backdrop = static_desert(ctx, wake_rocks(), with_horizon=False, extra=lambda c, b: c.drawOval(shadow, pens.shadow))
    title_font = Lettering(64)
    title = "A Bunch of Rocks"
    tw = title_font.measure(title)
    ink = skia.Paint(AntiAlias=True, Color=skia.Color(*INK))
    man = sleeper()

    def draw(c, t, boil):
        full(c, paper)
        sand = smooth((t - 3.5) / 4.0)
        if sand > 0:                                                   # the sand, its rocks and the sleeping man fade in
            full(c, backdrop[boil], skia.Paint(Alphaf=float(sand)))
            c.saveLayerAlpha(None, int(255 * sand))
            man.draw(c, pens, boil)
            c.restore()
        k = smooth((t - 1.0) / 2.6)                                    # the horizon draws itself
        if k > 0:
            pts = horizon_points(boil=boil)                          # the same line every later shot draws
            n = max(2, int(len(pts) * k))
            c.drawPath(path_of(pts[:n]), HORIZON_PAINT)
        a = smooth((t - 7.5) / 1.5) * (1 - smooth((t - 12.5) / 1.5))  # the title, then gone
        if a > 0:
            ink.setAlphaf(float(a))
            title_font.draw(c, title, (W - tw) / 2, H * 0.3, ink)
    return draw


SCENES = {"cold_open": cold_open}
