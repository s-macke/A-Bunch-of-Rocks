"""Every named pose of the stick figure plus a walk-cycle strip, on paper -> build/pose_sheet.png

usage: .venv/bin/python scripts/pose_sheet.py
"""
import numpy as np
import skia
from PIL import Image

from rocks.config import BOIL, W, BUILD
from rocks.textures import Washer, to_skia, grain_image
from rocks.ink import Pens
from rocks.render import stage_canvas, stage_surface
from rocks.scenes.common import full
from rocks.lettering import Lettering
from rocks.rig import Figure, POSES, walk

washer = Washer()
paper = to_skia(washer.paper())
pens = Pens(grain_image())
surface = stage_surface()
c = stage_canvas(surface)
full(c, paper)
font = Lettering(18)
label = skia.Paint(AntiAlias=True, Color=skia.Color(90, 80, 75))
ground = skia.Paint(AntiAlias=True, Color=skia.Color(150, 130, 110), StrokeWidth=1)

names = list(POSES)
cols = 5
for i, name in enumerate(names):
    cx = W * (i % cols + 0.5) / cols
    gy = 200 + 215 * (i // cols)
    c.drawLine(cx - 110, gy, cx + 110, gy, ground)
    fig = Figure(x=cx, ground=gy, pose=POSES[name], facing=-1)
    if name == "lie":
        fig.hip_y = gy - 6
    if name == "sit":
        fig.hip_y = gy - 50
        c.drawLine(cx - 40, gy - 45, cx + 12, gy - 45, ground)  # chair seat under the thighs
        c.drawLine(cx + 12, gy - 45, cx + 12, gy, ground)
        c.drawLine(cx + 12, gy - 45, cx + 16, gy - 110, ground)  # backrest
    if name == "place_rock":
        target = (cx - 70, gy - 8)
        fig.hand_target = target
        pens.rock(c, target[0] - 4, target[1] + 2, 11, 8, 0.2, seed=9, boil=0)
    if name == "hold_rock":
        hand = fig.joints()["hand_f"]
        pens.rock(c, hand[0] - 6, hand[1] + 2, 11, 8, 0.2, seed=9, boil=0)
    fig.draw(c, pens, boil=0)
    font.draw(c, name, cx - 100, gy + 32, label)

# walk cycle strip: 8 phases, in its own row below the poses
cx = W / 2
gy = 200 + 215 * ((len(names) + cols - 1) // cols)
font.draw(c, "walk (8 phases)", cx - 150, gy + 32, label)
c.drawLine(cx - 150, gy, cx + 150, gy, ground)
for k in range(8):
    fig = Figure(x=cx - 130 + k * 37, ground=gy, pose=walk(k / 8 * 2 * np.pi), facing=-1, scale=0.55)
    fig.draw(c, pens, boil=k % BOIL)

out = BUILD / "pose_sheet.png"
out.parent.mkdir(exist_ok=True)
Image.fromarray(surface.makeImageSnapshot().toarray()[..., :3]).save(out)
print("wrote", out)
