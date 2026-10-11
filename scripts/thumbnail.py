"""The YouTube thumbnail: a frame of shot 4.6 (him walking a row, rows to the horizon) with the title in the sky.

usage: .venv/bin/python scripts/thumbnail.py [out.png]      (default: film/a_bunch_of_rocks.thumbnail.png)
YouTube wants 1280×720 and at most 2 MB; upload it in YouTube Studio under Details → Thumbnail.
The README's title image is the same picture as a JPEG in the repository: scripts/thumbnail.py docs/thumbnail.jpg
"""
import argparse

import skia
from PIL import Image

from rocks.build import still
from rocks.config import FILM, INK, W
from rocks.lettering import Lettering

SHOT, T = "4.6", 10.0              # he is mid-stride, in front of the rock field
TITLE, SUB = "A Bunch of Rocks", "after xkcd #505"

ap = argparse.ArgumentParser(description="The YouTube thumbnail -> PNG (1280×720).")
ap.add_argument("out", nargs="?", default=str(FILM.with_suffix(".thumbnail.png")))
out = ap.parse_args().out


def title(c):
    ink = skia.Paint(AntiAlias=True, Color=skia.Color(*INK))
    big, small = Lettering(128), Lettering(50)
    big.draw(c, TITLE, (W - big.measure(TITLE)) / 2, 195, ink)
    small.draw(c, SUB, (W - small.measure(SUB)) / 2, 280, ink)


FILM.parent.mkdir(exist_ok=True)
still(SHOT, T, over=title).resize((1280, 720), Image.LANCZOS).save(out, optimize=True, quality=88)
print(out)
