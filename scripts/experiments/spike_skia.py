"""Spike: sketchbook look (D-7) rendered with skia at 12 fps over cached textures.

A 4 s shot: the figure walks along the front row and sets down a rock; lines boil.
Static paper + sky/sand washes are computed once (numpy), everything else is drawn
per frame with skia and piped straight into ffmpeg.

Usage: .venv/bin/python scripts/experiments/spike_skia.py <out_dir>
"""
import sys
import time
import pathlib
import subprocess
import numpy as np
import skia
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

W, H, FPS, SECONDS = 1280, 720, 12, 4
BOIL = 3  # distinct drawings per boil cycle (lines change every frame, repeat every 3)
HORIZON = 0.52
INK = (40, 36, 38)


# ---------- cached textures (computed once per film / per shot) ----------------

def noise(scale, seed, shape=(H, W)):
    return gaussian_filter(np.random.default_rng(seed).normal(0, 1, shape), scale)


def norm(a):
    return (a - a.min()) / (a.max() - a.min() + 1e-9)


def wash(base, poly, color, alpha, seed, blur, gran):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in poly], fill=255)
    m = np.asarray(m.filter(ImageFilter.GaussianBlur(blur)), float) / 255
    edge = np.clip(m * (1 - m) * 4, 0, 1) ** 1.5
    a = np.clip(m * (0.55 + 0.45 * gran[seed % len(gran)]) + edge * 0.35, 0, 1) * alpha
    return base * (1 - a[..., None]) + base * np.array(color) / 255 * a[..., None]


def build_plate():
    gran = [norm(noise(1.2, s)) * 0.5 + norm(noise(14, s + 3)) * 0.5 for s in range(3)]
    base = np.full((H, W, 3), (243, 236, 222), float)
    base += ((norm(noise(1, 11)) - 0.5) * 9 + (norm(noise(30, 12)) - 0.5) * 12)[..., None]
    hy = H * HORIZON
    base = wash(base, [(0, 0), (W, 0), (W, hy + 10), (0, hy + 10)], (150, 175, 205), 0.55, 0, 14, gran)
    base = wash(base, [(0, hy - 30), (W * .3, hy - 55), (W * .62, hy - 22), (W, hy - 40), (W, hy + 8), (0, hy + 8)],
                (200, 160, 150), 0.35, 1, 6, gran)
    base = wash(base, [(0, hy), (W, hy), (W, H), (0, H)], (222, 190, 140), 0.6, 2, 10, gran)
    base = wash(base, [(0, H * .86), (W * .3, H * .8), (W * .7, H * .83), (W, H * .79), (W, H), (0, H)],
                (205, 160, 115), 0.3, 0, 18, gran)
    t = np.linspace(0, 2 * np.pi, 64)
    base = wash(base, np.stack([W * .8 + 46 * np.cos(t), H * .2 + 46 * np.sin(t)], 1), (240, 200, 150), 0.55, 1, 8, gran)
    rgba = np.dstack([np.clip(base, 0, 255), np.full((H, W), 255)]).astype(np.uint8)
    # granulation texture used as a shader inside rock fills
    g = (norm(noise(1.0, 77)) * 0.6 + norm(noise(5, 78)) * 0.4)
    g = (205 + 50 * g).astype(np.uint8)
    grain = np.dstack([g, g, g, np.full_like(g, 255)])
    return skia.Image.fromarray(rgba), skia.Image.fromarray(grain)


# ---------- geometry --------------------------------------------------------------

def rocks_layout(seed=1):
    r = np.random.default_rng(seed)
    out = []
    for row in range(5):
        depth = 1.0 - row * 0.16
        y = H * (HORIZON + 0.08 + 0.34 * depth ** 2.2)
        size = 20 * depth ** 1.6 + 3
        n = 9 + row * 3
        x0, x1 = W * (0.08 + row * 0.05), W * (0.50 - row * 0.02)
        for i in range(n):
            if r.random() < 0.28:
                continue
            out.append((x0 + (x1 - x0) * i / (n - 1) + r.normal(0, 2), y + r.normal(0, 1.5),
                        size * r.uniform(.8, 1.2), size * r.uniform(.5, .75), r.uniform(-.3, .3), row, i))
    return out


def blob(cx, cy, rx, ry, rot, seed, n=40, irr=0.12):
    r = np.random.default_rng(seed)
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    k = 1 + gaussian_filter(r.normal(0, irr, n), 2, mode="wrap") * 2.5
    x, y = rx * k * np.cos(a), ry * k * np.sin(a)
    c, s = np.cos(rot), np.sin(rot)
    return np.stack([cx + c * x - s * y, cy + s * x + c * y], 1)


def wobble(pts, amp, seed, step=4.0):
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


def figure(t, gx, gy):
    """Walk cycle, then bend and set the rock down (t in seconds)."""
    walk = t < 2.5
    ph = t * 2 * np.pi * 1.6
    sw = 16 * np.sin(ph) if walk else 0
    bend = 0 if walk else min(1, (t - 2.5) / 0.8)
    hip = np.array([gx, gy - 70 + (2 * abs(np.sin(ph)) if walk else 0)])
    neck = hip + np.array([-8 - 12 * bend, -58 + 8 * bend])
    head = neck + np.array([-6 - 10 * bend, -24 + 4 * bend])
    sh = hip + (neck - hip) * 0.83
    hand_y = gy - 70 + 64 * bend
    strokes = [
        [hip, neck],
        [hip, hip + (sw * .5 - 4, 34), (gx + sw - 6, gy)],
        [hip, hip + (-sw * .5 + 8, 34), (gx - sw + 8, gy)],
        [sh, sh + (-22 - 6 * bend, 30), (gx - 40 - 10 * bend, hand_y)],
        [sh, sh + (18, 26), (gx + 6 - sw * .4, gy - 70)],
    ]
    return strokes, head, 22, (gx - 44 - 10 * bend, hand_y + 6)


# ---------- per-frame drawing ------------------------------------------------------

def make_paints(grain):
    ink = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, Color=skia.Color(*INK),
                     StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
    grain_shader = grain.makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat)
    fill = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kMultiply,
                      MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 1.2))
    fill.setShader(skia.Shaders.Blend(skia.BlendMode.kModulate,
                                      skia.Shaders.Color(skia.Color(195, 185, 180)), grain_shader))
    shadow = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kMultiply, Color=skia.Color(215, 200, 190, 150),
                        MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 4))
    hatch = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, Color=skia.Color(70, 60, 60), StrokeWidth=1.3)
    return ink, fill, shadow, hatch


def draw_rock(c, rock, boil, paints, seed):
    ink, fill, _, hatch = paints
    x, y, rx, ry, rot = rock[:5]
    b = blob(x, y, rx, ry, rot, seed)
    c.drawPath(path_of(b, close=True), fill)
    ink.setStrokeWidth(1.4 + rx / 18)
    c.drawPath(path_of(wobble(np.vstack([b, b[:3]]), 0.4, seed * 7 + boil)), ink)
    for k in range(3):
        hx = x + rx * (0.1 + 0.25 * k)
        c.drawLine(hx, y + ry * .2, hx + ry * .4, y + ry * .75, hatch)


def render(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    plate, grain = build_plate()
    t_plate = time.perf_counter() - t0
    paints = make_paints(grain)
    ink, _, shadow, _ = paints
    rocks = rocks_layout()
    front = [r for r in rocks if r[5] == 0]
    placed_at = front[-1]  # this rock appears when the figure sets it down
    static = [r for r in rocks if r is not placed_at]

    surface = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    mp4 = out_dir / "spike_skia_12fps.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-crf", "18", str(mp4)], stdin=subprocess.PIPE)
    draw_times = []
    n = FPS * SECONDS
    for f in range(n):
        t = f / FPS
        boil = f % BOIL
        ts = time.perf_counter()
        c = surface.getCanvas()
        c.drawImage(plate, 0, 0)
        c.drawLine(0, H * HORIZON, W, H * HORIZON + 1, skia.Paint(AntiAlias=True, Color=skia.Color(*INK), StrokeWidth=1.6))
        for i, r in enumerate(static):
            draw_rock(c, r, boil, paints, i)
        target = placed_at[0] + 50                    # stop where the hand meets the free slot
        gx = W * 0.78 + (target - W * 0.78) * min(t, 2.5) / 2.5
        strokes, head, hr, rock = figure(t, gx, H * 0.86)
        c.drawOval(skia.Rect.MakeXYWH(gx - 70, H * .86 - 4, 180, 12), shadow)
        ink.setStrokeWidth(3.0)
        for i, st in enumerate(strokes):
            c.drawPath(path_of(wobble(st, 0.9, 300 + i * 11 + boil)), ink)
        a = np.linspace(0, 2.16 * np.pi, 48)
        c.drawPath(path_of(wobble(np.stack([head[0] + hr * np.cos(a), head[1] + hr * np.sin(a)], 1), 0.7, 320 + boil)), ink)
        if t < 3.3:
            draw_rock(c, (rock[0], rock[1], 11, 8, 0.2), boil, paints, 999)
        else:
            draw_rock(c, placed_at, boil, paints, 998)
        frame = surface.makeImageSnapshot().toarray()
        draw_times.append(time.perf_counter() - ts)
        ff.stdin.write(frame.tobytes())
        if f == 40:
            Image.fromarray(frame[..., :3]).save(out_dir / "spike_skia_frame.png")
    ff.stdin.close()
    ff.wait()
    total = time.perf_counter() - t0
    dt = np.array(draw_times)
    print(f"plate (once): {t_plate:.2f}s")
    print(f"per frame draw: mean {dt.mean()*1000:.1f} ms, max {dt.max()*1000:.1f} ms ({n} frames)")
    print(f"total incl. encode: {total:.2f}s for {SECONDS}s of film")
    est = (dt.mean() * 5 * 60 * FPS)
    print(f"extrapolated 5:00 film @ {FPS} fps: {est/60:.1f} CPU-min draw time (single core), + ~{t_plate:.0f}s per new plate")
    print("wrote", mp4)


if __name__ == "__main__":
    render(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "."))
