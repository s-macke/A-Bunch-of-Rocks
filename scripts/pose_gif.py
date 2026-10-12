"""The stick figure going through its named poses, blended as in the film, with line boil -> an animated GIF.

Like scripts/pose_sheet.py, but in motion: each pose is held for a moment and named, then blends into the next;
a few steps of the walk cycle at the end, back to standing. The README shows it (docs/poses.gif).

usage: .venv/bin/python scripts/pose_gif.py [out.gif]      (default: build/poses.gif)
"""
import argparse

import numpy as np
import skia
from PIL import Image

from rocks.config import BOIL, BUILD, W, H, OUT_W
from rocks.ink import Pens
from rocks.lettering import Lettering
from rocks.render import stage_canvas, stage_surface
from rocks.rig import Figure, POSES, blend, walk
from rocks.scenes.common import full
from rocks.textures import Washer, grain_image, to_skia

FPS = 12                                    # one drawing per frame: the film's line boil rate
HOLD, MOVE = 0.9, 0.7                       # s a pose is held, s a blend takes
ORDER = ["stand", "look_up", "shrug", "hold_rock", "crouch", "place_rock", "sit_ground", "write_in_sand"]
VIEW = (W * 0.25, H * 0.2, W * 0.5, H * 0.5)    # the part of the stage the GIF shows (x, y, w, h)
SIZE = (640, 360)

ap = argparse.ArgumentParser(description="The figure's poses in motion -> GIF.")
ap.add_argument("out", nargs="?", default=str(BUILD / "poses.gif"))
out = ap.parse_args().out

paper = to_skia(Washer().paper())
pens = Pens(grain_image())
font = Lettering(26)
label = skia.Paint(AntiAlias=True, Color=skia.Color(90, 80, 75))
ground = skia.Paint(AntiAlias=True, Color=skia.Color(150, 130, 110), StrokeWidth=1.5)
cx, gy, scale = W / 2, H * 0.62, 1.4

# the timeline: (pose at t, its name or "") for every frame
frames = []
for i, name in enumerate(ORDER):
    nxt = POSES[ORDER[i + 1]] if i + 1 < len(ORDER) else walk(0.0)
    frames += [(POSES[name], name)] * round(HOLD * FPS)
    frames += [(blend(POSES[name], nxt, k / round(MOVE * FPS)), "") for k in range(round(MOVE * FPS))]
steps = round(2.5 * FPS)                    # two and a half seconds of walking on the spot
frames += [(walk(2 * np.pi * 0.7 * k / FPS), "walk") for k in range(steps)]
end = walk(2 * np.pi * 0.7 * steps / FPS)
frames += [(blend(end, POSES["stand"], k / round(MOVE * FPS)), "") for k in range(round(MOVE * FPS))]

images = []
for k, (pose, name) in enumerate(frames):
    surface = stage_surface()
    c = stage_canvas(surface)
    full(c, paper)
    c.drawLine(cx - 160, gy, cx + 160, gy, ground)
    fig = Figure(x=cx, ground=gy, pose=pose, facing=-1, scale=scale)
    if name == "hold_rock":
        hand = fig.joints()["hand_f"]
        pens.rock(c, hand[0] - 8, hand[1] + 3, 15, 11, 0.2, seed=9, boil=k % BOIL)
    fig.draw(c, pens, boil=k % BOIL, width=3.4)
    if name:
        font.draw(c, name.replace("_", " "), cx - font.measure(name.replace("_", " ")) / 2, gy + 50, label)
    s = OUT_W / W                           # stage -> output pixels
    img = Image.fromarray(surface.makeImageSnapshot().toarray()[..., :3])
    x, y, w, h = (round(v * s) for v in VIEW)
    images.append(img.crop((x, y, x + w, y + h)).resize(SIZE, Image.LANCZOS))

pal = images[0].quantize(colors=48, method=Image.Quantize.MEDIANCUT)    # one palette: no flicker between frames
images = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in images]
images[0].save(out, save_all=True, append_images=images[1:], duration=round(1000 / FPS), loop=0, optimize=True)
print(out, f"{len(images)} frames")
