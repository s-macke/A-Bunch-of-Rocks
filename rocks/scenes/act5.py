"""Credits (spec §1, AC-12): text from credits.md on paper; below, he walks along an endless row."""
import numpy as np
import skia

from ..config import W, H, INK, ROOT
from ..rig import Figure, walk, walk_distance_per_cycle
from ..lettering import Lettering
from .common import smooth, full


def credits(ctx, shot):
    paper = ctx.paper
    pens = ctx.pens
    lines = [l.lstrip("# ").strip() for l in (ROOT / "credits.md").read_text().splitlines() if l.strip()]
    big = Lettering(48)
    small = Lettering(24)
    ink = skia.Paint(AntiAlias=True, Color=skia.Color(*INK))
    gy = H * 0.86
    speed = 40.0
    cyc = speed / (walk_distance_per_cycle() * 0.8)        # his stride at scale 0.8 matches the ground's speed

    def draw(c, t, boil):
        full(c, paper)
        shift = speed * t                                               # he walks left, so the row scrolls right
        for k in range(31):                                             # 31 x 44 px = one seamless loop of W + 88
            x = (k * 44 + shift) % (W + 88) - 44
            pens.rock(c, x, gy + 4, 11, 7, 0.2 * np.sin(k), seed=9500 + k, boil=boil)
        appear = smooth(t / 1.2)                                        # 4.6 ends on blank paper: row and man fade in
        if appear < 1:                                                  # (the rocks are multiplied into the paper,
            full(c, paper, skia.Paint(Alphaf=float(1 - appear)))        #  so they are faded by covering them)
        fade = appear * (1 - smooth((t - shot.duration + 1.6) / 1.4))
        c.saveLayerAlpha(None, int(255 * fade))
        Figure(x=W * 0.5, ground=gy - 2, pose=walk(2 * np.pi * cyc * t), facing=-1, scale=0.8).draw(c, pens, boil)
        c.restore()
        for i, text in enumerate(lines):
            a = smooth((t - 0.6 - i * 0.7) / 0.8) * (1 - smooth((t - shot.duration + 1.6) / 1.4))
            if a <= 0:
                continue
            ink.setAlphaf(float(a))
            font = big if i == 0 else small
            y = H * 0.2 if i == 0 else H * 0.32 + i * 40
            font.draw(c, text, (W - font.measure(text)) / 2, y, ink)
    return draw


SCENES = {"credits": credits}
