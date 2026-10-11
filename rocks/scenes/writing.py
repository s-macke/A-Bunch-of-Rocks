"""Time-lapse writing in the sand for Act 1 (the D-30 technique of shot 2.8): several takes of him writing at
different spots; each take cross-dissolves into the next, so briefly two or three of him are writing at once.
Equations stay once written. Within a take only his arm and a slight lean move."""
from dataclasses import replace
import numpy as np
import skia

from ..rig import Figure, POSES
from ..lettering import Lettering
from .common import smooth, shadow


REACH = (20, 80)        # px at scale 1.2: how far in front of his body his hand reaches along the ground, kneeling


def writer(x0, width, f, base, scale=1.2, head=-35.0, lean=0.4):
    """The kneeling figure writing one line in the sand: first letter at x0, text baseline at `base`, fraction f written.

    He kneels just in front of the line and his hand is on the letters being written. Within a line only his arm
    moves and his body leans along; it shifts only when the line is longer than his arm can reach.
    """
    tx = x0 + width * f
    k = scale / 1.2
    body_x = x0 + width / 2 - 58 * k + (f - 0.5) * width * lean
    body_x = min(max(body_x, tx - REACH[1] * k), tx - REACH[0] * k)
    fig = Figure(x=body_x, ground=base + 6, pose=replace(POSES["write_in_sand"], head=head), scale=scale, facing=1)
    fig.hand_target = (tx, base - 4)                      # on the letters: the first before writing, the last after
    return fig


class Takes:
    def __init__(self, takes, t0=0.3, fade=0.6, overlap=0.1, font_size=40, ground=0.0, scale=1.2,
                 squash=0.42, last_stays=True):
        """takes: list of (text, x of first letter, depth offset in px below `ground`, write seconds)."""
        self.font = Lettering(font_size)
        self.groove = skia.Paint(AntiAlias=True, Color=skia.Color(118, 84, 52, 235))
        self.takes, self.fade, self.gy, self.scale, self.squash = takes, fade, ground, scale, squash
        self.widths = [self.font.measure(t[0]) for t in takes]
        self.starts = [t0]
        for i in range(1, len(takes)):
            self.starts.append(self.starts[-1] + takes[i - 1][3] + overlap)
        self.last_stays = last_stays
        self.strikes = {}          # take index -> time when it gets crossed out

    def end(self):
        return self.starts[-1] + self.takes[-1][3]

    def progress(self, i, t):
        return float(np.clip((t - self.starts[i]) / self.takes[i][3], 0, 1))

    def alpha(self, i, t):
        a = smooth((t - self.starts[i] + self.fade) / self.fade)
        if i < len(self.takes) - 1 or not self.last_stays:
            a *= 1 - smooth((t - self.starts[i] - self.takes[i][3] - 0.1) / self.fade)
        return a

    def figure(self, i, t, head=-35.0):
        txt, x0, dy, _ = self.takes[i]
        return writer(x0, self.widths[i], self.progress(i, t), self.gy + dy, self.scale, head)

    def draw_text(self, c, t, pens=None, boil=0):
        for i, (txt, x0, dy, _) in enumerate(self.takes):
            f = self.progress(i, t)
            if f <= 0:
                continue
            c.save()
            c.translate(x0, self.gy + dy)
            c.scale(1, self.squash)
            c.clipRect(skia.Rect.MakeLTRB(-4, -60, self.widths[i] * f, 24))
            self.font.draw(c, txt, 0, 0, self.groove)
            c.restore()
            if i in self.strikes and t >= self.strikes[i] and pens is not None:
                k = smooth((t - self.strikes[i]) / 0.4)
                y = self.gy + dy - 7
                pens.line(c, [(x0 - 4, y), (x0 - 4 + (self.widths[i] + 8) * k, y - 2)], 2.2, 8800 + i + boil, amp=0.3)

    def draw_figures(self, c, t, pens, boil, head_last=-35.0):
        for i in range(len(self.takes)):
            a = self.alpha(i, t)
            if a <= 0.01:
                continue
            fig = self.figure(i, t, head_last if i == len(self.takes) - 1 else -35.0)
            shadow(c, pens, fig.x - 10, fig.ground - 5, alpha=a)     # onto the sand: multiply needs the sand under it
            c.saveLayerAlpha(None, int(255 * a))
            fig.draw(c, pens, boil, seed=300 + i * 40)
            c.restore()
