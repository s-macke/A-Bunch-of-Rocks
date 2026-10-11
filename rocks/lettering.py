"""Hand lettering in xkcd Script (Randall Munroe's handwriting, github.com/ipython/xkcd-font, CC BY-NC 3.0).

The font has no super/subscript digits, no middle dot and no ellipsis; those are drawn from its own glyphs
(smaller and raised or lowered; a raised full stop for the middle dot), so every mark on screen stays in the one handwriting.
Sizes are DejaVu-equivalent: xkcd Script runs ~25 % narrower, so it is scaled up to keep layouts as tuned.
"""
import skia

from .config import ROOT

FACE = skia.Typeface.MakeFromFile(str(ROOT / "fonts" / "xkcd-script.ttf"))
SCALE = 1.25
SUP = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹ˣⁿ", "0123456789xn"))
SUB = dict(zip("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
SWAP = {"…": "..."}


class Lettering:
    """Text in xkcd Script at a given size: measure(text) and draw(canvas, text, x, y, paint), like skia.Font."""

    def __init__(self, size):
        self.font = skia.Font(FACE, size * SCALE)
        self.small = skia.Font(FACE, size * SCALE * 0.62)
        self.size = size * SCALE

    def runs(self, text):
        """(string, font, dy) pieces, in order."""
        out = []
        for ch in text:
            ch = SWAP.get(ch, ch)
            if ch == "·":
                piece = (".", self.font, -0.3 * self.size)
            elif ch[0] in SUP:
                piece = (SUP[ch], self.small, -0.42 * self.size)
            elif ch[0] in SUB:
                piece = (SUB[ch], self.small, 0.16 * self.size)
            else:
                piece = (ch, self.font, 0.0)
            if out and out[-1][1] is piece[1] and out[-1][2] == piece[2]:
                out[-1] = (out[-1][0] + piece[0], piece[1], piece[2])
            else:
                out.append(piece)
        return out

    def measure(self, text):
        return sum(f.measureText(s) for s, f, _ in self.runs(text))

    def draw(self, c, text, x, y, paint):
        for s, f, dy in self.runs(text):
            c.drawString(s, x, y + dy, f, paint)
            x += f.measureText(s)
