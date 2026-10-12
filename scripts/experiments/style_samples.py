"""Render the same key frame (figure laying a row of rocks in an endless desert)
in four candidate art directions, fully procedurally with numpy + Pillow.

Usage: .venv/bin/python scripts/experiments/style_samples.py <out_dir> [sheet.jpg]
       sheet.jpg: the four side by side, labelled (the README's docs/style_samples.jpg)
"""
import sys
import pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
from scipy.ndimage import gaussian_filter

W, H = 1280, 720
SS = 2  # supersampling factor
rng = np.random.default_rng(505)


# ---------- shared geometry -------------------------------------------------

HORIZON = 0.52

def scene_rocks(seed=1):
    """Rock rows receding toward the horizon, like the start of the rock computer."""
    r = np.random.default_rng(seed)
    rocks = []
    for row in range(5):
        depth = 1.0 - row * 0.16          # 1 = near, smaller = far
        y = H * (HORIZON + 0.08 + 0.34 * depth ** 2.2)
        size = 20 * depth ** 1.6 + 3
        n = int(9 + row * 3)
        x0 = W * (0.08 + row * 0.05)
        x1 = W * (0.50 - row * 0.02)
        for i in range(n):
            if r.random() < 0.28:           # gaps: pattern, not a wall
                continue
            x = x0 + (x1 - x0) * i / (n - 1) + r.normal(0, 2)
            rocks.append((x, y + r.normal(0, 1.5), size * r.uniform(0.8, 1.2),
                          size * r.uniform(0.5, 0.75), r.uniform(-0.3, 0.3)))
    return rocks

FIG_X, FIG_GROUND = W * 0.62, H * 0.86

def figure_strokes(scale=1.0):
    """Simple character: round head, thin body, bending to place a rock."""
    s = 1.0 * scale
    gx, gy = FIG_X, FIG_GROUND
    hip = (gx, gy - 70 * s)
    neck = (gx - 18 * s, gy - 128 * s)
    head_c = (gx - 30 * s, gy - 152 * s)
    strokes = [
        [hip, neck],                                           # torso (leaning)
        [hip, (gx - 16 * s, gy - 36 * s), (gx - 22 * s, gy)],  # front leg
        [hip, (gx + 16 * s, gy - 34 * s), (gx + 22 * s, gy)],  # back leg
        [(gx - 14 * s, gy - 118 * s), (gx - 40 * s, gy - 84 * s), (gx - 58 * s, gy - 58 * s)],  # arm down with rock
        [(gx - 14 * s, gy - 118 * s), (gx + 8 * s, gy - 92 * s), (gx + 4 * s, gy - 70 * s)],   # other arm
    ]
    return strokes, head_c, 22 * s, (gx - 62 * s, gy - 50 * s)  # held rock position


def wobble(points, amp=1.5, step=4.0, seed=None):
    """Resample a polyline and add smooth hand-drawn jitter."""
    r = np.random.default_rng(seed)
    pts = np.array(points, float)
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(2, int(np.linalg.norm(b - a) / step))
        t = np.linspace(0, 1, n, endpoint=False)[:, None]
        out.append(a + (b - a) * t)
    out.append(pts[-1:])
    seg = np.vstack(out)
    noise = gaussian_filter(r.normal(0, 1, seg.shape), sigma=(3, 0)) * amp * 2.2
    return seg + noise


def circle_pts(c, rad, n=48, start=0.0, extra=0.12):
    a = np.linspace(start, start + 2 * np.pi * (1 + extra), n)
    return np.stack([c[0] + rad * np.cos(a), c[1] + rad * np.sin(a)], 1)


def blob(cx, cy, rx, ry, rot, n=40, irregular=0.12, seed=None):
    r = np.random.default_rng(seed)
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    k = 1 + gaussian_filter(r.normal(0, irregular, n), 2, mode="wrap") * 2.5
    x, y = rx * k * np.cos(a), ry * k * np.sin(a)
    c, s = np.cos(rot), np.sin(rot)
    return np.stack([cx + c * x - s * y, cy + s * x + c * y], 1)


def S(pts):
    return [tuple(p) for p in (np.asarray(pts) * SS)]


def canvas(color):
    return Image.new("RGB", (W * SS, H * SS), color)


def finish(img):
    return img.resize((W, H), Image.LANCZOS)


def noise_field(scale, seed, w=W * SS, h=H * SS):
    r = np.random.default_rng(seed)
    return gaussian_filter(r.normal(0, 1, (h, w)), scale)


def normalize(a):
    return (a - a.min()) / (a.max() - a.min() + 1e-9)


def paper_texture(base, strength=10, seed=0):
    fine = noise_field(1.0, seed)
    coarse = noise_field(30, seed + 1)
    t = (normalize(fine) - 0.5) * strength + (normalize(coarse) - 0.5) * strength * 1.4
    arr = np.asarray(base, float) + t[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ---------- style 1: sketchbook ink + muted wash ------------------------------

def wash(img, mask_pts, color, alpha=0.55, seed=0, blur=6):
    """Watercolor: soft pigment with darker drying edges and granulation."""
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).polygon(S(mask_pts), fill=255)
    m = np.asarray(m.filter(ImageFilter.GaussianBlur(blur * SS)), float) / 255
    edge = np.clip(m * (1 - m) * 4, 0, 1) ** 1.5          # pigment pools at edges
    gran = normalize(noise_field(1.2, seed)) * 0.5 + normalize(noise_field(14, seed + 3)) * 0.5
    a = np.clip(m * (0.55 + 0.45 * gran) + edge * 0.35, 0, 1) * alpha
    base = np.asarray(img, float)
    out = base * (1 - a[..., None]) + (base * np.array(color) / 255.0) * a[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def ink(draw, pts, width=2.2, color=(40, 36, 38), amp=1.2, seed=None, passes=1):
    for p in range(passes):
        w = wobble(pts, amp=amp, seed=None if seed is None else seed + p)
        draw.line(S(w), fill=color, width=int(width * SS), joint="curve")


def style_sketchbook():
    img = paper_texture(canvas((243, 236, 222)), strength=9, seed=11)
    hy = H * HORIZON
    # washes: dusk sky, far dunes, sand
    img = wash(img, [(0, 0), (W, 0), (W, hy + 10), (0, hy + 10)], (150, 175, 205), 0.55, seed=1, blur=14)
    img = wash(img, [(0, hy - 30), (W * 0.3, hy - 55), (W * 0.62, hy - 22), (W, hy - 40), (W, hy + 8), (0, hy + 8)],
               (200, 160, 150), 0.35, seed=2)
    img = wash(img, [(0, hy), (W, hy), (W, H), (0, H)], (222, 190, 140), 0.6, seed=3, blur=10)
    img = wash(img, [(0, H * 0.86), (W * 0.3, H * 0.8), (W * 0.7, H * 0.83), (W, H * 0.79), (W, H), (0, H)], (205, 160, 115), 0.3, seed=4, blur=18)
    # pale sun
    img = wash(img, circle_pts((W * 0.8, H * 0.2), 46, extra=0), (240, 200, 150), 0.55, seed=5, blur=8)
    d = ImageDraw.Draw(img)
    # horizon & a few sketchy dune lines
    ink(d, [(0, hy), (W * 0.4, hy - 2), (W, hy + 1)], 1.6, amp=0.8, seed=20)
    for i, yy in enumerate([0.6, 0.68, 0.78]):
        x0 = rng.uniform(0.0, 0.5) * W
        ink(d, [(x0, H * yy), (x0 + W * 0.18, H * yy + 3)], 1.0, color=(110, 90, 70), amp=0.6, seed=30 + i)
    # rocks: wash fill + ink outline + hatch shadow
    for i, (x, y, rx, ry, rot) in enumerate(scene_rocks()):
        b = blob(x, y, rx, ry, rot, seed=i)
        img = wash(img, b, (150, 140, 135), 0.55, seed=100 + i, blur=1.5)
    d = ImageDraw.Draw(img)
    for i, (x, y, rx, ry, rot) in enumerate(scene_rocks()):
        b = blob(x, y, rx, ry, rot, seed=i)
        ink(d, np.vstack([b, b[:3]]), 1.4 + rx / 18, amp=0.4, seed=200 + i)
        for k in range(3):
            hx = x + rx * (0.1 + 0.25 * k)
            d.line(S([(hx, y + ry * 0.2), (hx + ry * 0.4, y + ry * 0.75)]), fill=(70, 60, 60), width=SS)
    # character
    strokes, hc, hr, rock = figure_strokes()
    img = wash(img, [(FIG_X - 70, FIG_GROUND - 4), (FIG_X + 120, FIG_GROUND - 2), (FIG_X + 110, FIG_GROUND + 8), (FIG_X - 60, FIG_GROUND + 6)],
               (140, 120, 110), 0.4, seed=7, blur=4)
    d = ImageDraw.Draw(img)
    for i, st in enumerate(strokes):
        ink(d, st, 3.0, amp=0.9, seed=300 + i)
    ink(d, circle_pts(hc, hr, extra=0.08), 3.0, amp=0.7, seed=320)
    rb = blob(*rock, 11, 8, 0.2, seed=9)
    ink(d, np.vstack([rb, rb[:3]]), 2.2, seed=330)
    return finish(img)


# ---------- style 2: Moebius desert -----------------------------------------------

def style_moebius():
    img = canvas((0, 0, 0))
    arr = np.zeros((H * SS, W * SS, 3), float)
    y = np.linspace(0, 1, H * SS)[:, None]
    top, mid = np.array([38, 120, 170]), np.array([250, 205, 150])
    hy = HORIZON
    sky = top + (mid - top) * np.clip(y / hy, 0, 1) ** 1.6
    bands = np.floor(np.clip(y / hy, 0, 1) * 7) / 7          # flat posterized bands
    sky = top + (mid - top) * bands ** 1.3
    arr[:] = sky[:, None, :] if sky.ndim == 2 else sky
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    K = (25, 20, 30)
    # giant sun disc + rings
    sc = (W * 0.3, H * 0.34)
    d.ellipse(S([(sc[0] - 150, sc[1] - 150), (sc[0] + 150, sc[1] + 150)]), fill=(255, 238, 190), outline=K, width=3 * SS)
    for rr in (175, 205):
        d.ellipse(S([(sc[0] - rr, sc[1] - rr), (sc[0] + rr, sc[1] + rr)]), outline=(255, 230, 190), width=2 * SS)
    # sand planes in flat colors with clean ink contours
    hyp = H * hy
    planes = [
        ([(0, hyp), (W, hyp), (W, H), (0, H)], (232, 150, 90)),
        ([(0, hyp + 40), (W * 0.45, hyp + 25), (W, hyp + 70), (W, H), (0, H)], (240, 175, 110)),
        ([(0, H * 0.78), (W * 0.5, H * 0.73), (W, H * 0.8), (W, H), (0, H)], (246, 196, 130)),
    ]
    for poly, col in planes:
        d.polygon(S(poly), fill=col)
        d.line(S(poly[: len(poly) - 2]), fill=K, width=2 * SS)
    # distant mesa
    d.polygon(S([(W * 0.72, hyp), (W * 0.75, hyp - 60), (W * 0.86, hyp - 64), (W * 0.9, hyp)]), fill=(180, 110, 110), outline=K, width=2 * SS)
    # rocks with hard long shadows (low sun from the left)
    for i, (x, y, rx, ry, rot) in enumerate(scene_rocks()):
        sh = [(x, y + ry * 0.6), (x + rx * 3.2, y + ry * 0.9), (x + rx * 3.0, y + ry * 1.3), (x - rx * 0.2, y + ry * 1.0)]
        d.polygon(S(sh), fill=(190, 105, 80))
    for i, (x, y, rx, ry, rot) in enumerate(scene_rocks()):
        b = blob(x, y, rx, ry, rot, irregular=0.06, seed=i)
        d.polygon(S(b), fill=(120, 150, 170), outline=K, width=max(1, int(rx / 10)) * SS)
        d.line(S([(x - rx * 0.4, y - ry * 0.3), (x + rx * 0.2, y - ry * 0.6)]), fill=(230, 240, 245), width=SS)
    # small figure in a vast space: scaled down
    strokes, hc, hr, rock = figure_strokes(scale=0.65)
    shadow = [(FIG_X - 10, FIG_GROUND), (FIG_X + 230, FIG_GROUND + 22), (FIG_X + 225, FIG_GROUND + 30), (FIG_X - 12, FIG_GROUND + 6)]
    d.polygon(S(shadow), fill=(190, 105, 80))
    for st in strokes:
        d.line(S(st), fill=K, width=int(4 * SS), joint="curve")
    d.ellipse(S([(hc[0] - hr, hc[1] - hr), (hc[0] + hr, hc[1] + hr)]), fill=(255, 245, 230), outline=K, width=3 * SS)
    d.ellipse(S([(rock[0] - 7, rock[1] - 5), (rock[0] + 7, rock[1] + 5)]), fill=(120, 150, 170), outline=K, width=2 * SS)
    return finish(img)


# ---------- style 3: chalk on blackboard -----------------------------------------

def style_chalk():
    base = canvas((34, 44, 40))
    board = np.asarray(base, float) + (normalize(noise_field(40, 3)) - 0.5)[..., None] * 18
    board += (normalize(noise_field(1, 4)) - 0.5)[..., None] * 8
    # faint erased smudges
    smudge = normalize(noise_field(60, 5)) ** 3 * 30
    board += smudge[..., None]
    layer = Image.new("L", base.size, 0)
    col_layers = []
    grain = normalize(noise_field(0.8, 6))
    tooth = (grain > 0.35).astype(float) * 0.85 + 0.15    # chalk skips over board grain

    def chalk_line(dr, pts, width=3.0, amp=1.2, passes=3, seed=0):
        for p in range(passes):
            w = wobble(pts, amp=amp * (1 + 0.3 * p), seed=seed * 10 + p)
            dr.line(S(w), fill=int(170 + 30 * p), width=max(1, int(width * SS * (1 - 0.2 * p))))

    def new_layer():
        return Image.new("L", base.size, 0)

    white, yellow, pink, blue = new_layer(), new_layer(), new_layer(), new_layer()
    dw, dy, dp, db = (ImageDraw.Draw(x) for x in (white, yellow, pink, blue))
    hy = H * HORIZON
    chalk_line(dw, [(20, hy), (W * 0.5, hy - 3), (W - 20, hy + 2)], 2.5, seed=1)
    # sun, drawn with a circle + rays in yellow
    sc = (W * 0.82, H * 0.2)
    chalk_line(dy, circle_pts(sc, 44, extra=0.05), 3.5, seed=2)
    for k in range(10):
        a = k * np.pi / 5
        chalk_line(dy, [(sc[0] + 60 * np.cos(a), sc[1] + 60 * np.sin(a)), (sc[0] + 85 * np.cos(a), sc[1] + 85 * np.sin(a))], 2.5, seed=3 + k)
    # side-of-chalk sand shading: many short diagonal strokes
    for i in range(700):
        x = rng.uniform(0, W)
        yy = rng.uniform(hy + 10, H - 10)
        dp.line(S([(x, yy), (x + 14, yy - 5)]), fill=int(rng.uniform(40, 90)), width=int(3 * SS))
    # equations hovering in the sky: he is "rederiving physics"
    for i, (x, y, rx, ry, rot) in enumerate(scene_rocks()):
        b = blob(x, y, rx, ry, rot, seed=i)
        chalk_line(dw, np.vstack([b, b[:3]]), 2.0 + rx / 16, amp=0.6, passes=2, seed=40 + i)
    strokes, hc, hr, rock = figure_strokes()
    for i, st in enumerate(strokes):
        chalk_line(dw, st, 4.0, amp=0.8, seed=200 + i)
    chalk_line(dw, circle_pts(hc, hr, extra=0.1), 4.0, seed=220)
    rb = blob(*rock, 11, 8, 0.2, seed=9)
    chalk_line(db, np.vstack([rb, rb[:3]]), 3.0, seed=230)
    # text scribbles as in a lecture: E = mc^2, a Gaussian, a ket
    txt = new_layer()
    dt = ImageDraw.Draw(txt)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("DejaVuSans-Oblique.ttf", 34 * SS)
        dt.text(S([(W * 0.08, H * 0.12)])[0], "E = mc²", fill=200, font=font)
        dt.text(S([(W * 0.36, H * 0.26)])[0], "iħ ∂ψ/∂t = Ĥψ", fill=190, font=font)
    except OSError:
        pass
    gx = np.linspace(W * 0.1, W * 0.3, 60)
    gy = H * 0.42 - 70 * np.exp(-((gx - W * 0.2) / 40) ** 2)
    chalk_line(dy, np.stack([gx, gy], 1), 2.5, seed=300)
    txt = txt.filter(ImageFilter.GaussianBlur(0.6 * SS))
    out = board
    for L, col in ((pink, (230, 150, 150)), (white, (240, 240, 232)), (txt, (240, 240, 232)),
                   (yellow, (245, 225, 130)), (blue, (150, 200, 235))):
        a = np.asarray(L.filter(ImageFilter.GaussianBlur(0.5 * SS)), float) / 255 * tooth
        out = out * (1 - a[..., None]) + np.array(col) * a[..., None]
    return finish(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)))


# ---------- style 4: paper cutout ------------------------------------------------

def paper_layer(size, poly, color, seed, rough=1.2):
    """A cut paper shape: rough edge, fibre texture, soft drop shadow."""
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(S(wobble(np.vstack([poly, poly[:1]]), amp=rough, step=6, seed=seed)), fill=255)
    fibre = normalize(noise_field(0.9, seed)) * 0.6 + normalize(noise_field(8, seed + 1)) * 0.4
    tex = np.array(color, float)[None, None, :] * (0.9 + 0.14 * fibre[..., None])
    return m, tex


def style_cutout():
    size = (W * SS, H * SS)
    out = np.asarray(paper_texture(canvas((250, 224, 190)), 6, seed=40), float)
    hy = H * HORIZON

    def place(poly, color, seed, shadow=10, rough=1.2):
        nonlocal out
        m, tex = paper_layer(size, np.asarray(poly, float), color, seed, rough)
        sh = np.asarray(ImageChops.offset(m, int(shadow * 0.6 * SS), int(shadow * SS)).filter(ImageFilter.GaussianBlur(shadow * 0.8 * SS)), float) / 255
        out = out * (1 - 0.28 * sh[..., None])
        a = np.asarray(m, float)[..., None] / 255
        out = out * (1 - a) + tex * a

    # sky gradient as stacked paper strips
    for i, c in enumerate([(120, 170, 200), (150, 190, 205), (190, 205, 200), (235, 215, 185)]):
        y0 = hy * i / 4 - (40 if i == 0 else 0)
        place([(-20, y0), (W + 20, y0 + 6), (W + 20, hy + 20), (-20, hy + 20)], c, 50 + i, shadow=6)
    place(circle_pts((W * 0.2, H * 0.24), 50, extra=0), (250, 240, 200), 60, shadow=8)
    # layered dunes
    dunes = [((226, 170, 110), 0.0), ((236, 186, 124), 0.07), ((244, 201, 140), 0.17), ((250, 214, 158), 0.29)]
    for i, (c, off) in enumerate(dunes):
        y0 = hy + H * off
        xs = np.linspace(-20, W + 20, 9)
        ys = y0 + 18 * np.sin(xs / 170 + i * 1.7)
        place(list(zip(xs, ys)) + [(W + 20, H + 20), (-20, H + 20)], c, 70 + i, shadow=10)
    for i, (x, y, rx, ry, rot) in enumerate(scene_rocks()):
        place(blob(x, y, rx, ry, rot, irregular=0.08, seed=i), (135, 128, 125), 100 + i, shadow=3 + rx / 6, rough=0.5)
    # character: jointed cutout puppet (limb pieces as separate paper strips)
    strokes, hc, hr, rock = figure_strokes()
    for i, st in enumerate(strokes):
        pts = np.asarray(st, float)
        for a, b in zip(pts[:-1], pts[1:]):
            dvec = b - a
            nrm = np.array([-dvec[1], dvec[0]]) / (np.linalg.norm(dvec) + 1e-9) * 5
            place([a + nrm, b + nrm, b - nrm, a - nrm], (60, 55, 70), 200 + i, shadow=5, rough=0.4)
    place(circle_pts(hc, hr, extra=0), (245, 240, 230), 220, shadow=6, rough=0.5)
    place(blob(*rock, 11, 8, 0.2, seed=9), (135, 128, 125), 230, shadow=4, rough=0.4)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # split-pin joints: a visible detail of cutout animation
    for st in strokes:
        for p in st[1:-1]:
            d.ellipse(S([(p[0] - 3, p[1] - 3), (p[0] + 3, p[1] + 3)]), fill=(200, 170, 90))
    return finish(img)


STYLES = [("1_sketchbook", "Sketchbook (chosen)"), ("2_moebius", "Moebius"), ("3_chalk", "Chalk"),
          ("4_cutout", "Paper cut-out")]


def sheet(out, path):
    """The four samples in a 2 x 2 grid, each labelled, as one 1280 x 720 JPEG."""
    font = ImageFont.truetype(str(pathlib.Path(__file__).resolve().parents[2] / "fonts" / "xkcd-script.ttf"), 30)
    img = Image.new("RGB", (W, H), (244, 241, 234))
    tw, th, gap = (W - 6) // 2, (H - 6) // 2, 6
    for k, (name, label) in enumerate(STYLES):
        x, y = (k % 2) * (tw + gap), (k // 2) * (th + gap)
        img.paste(Image.open(out / f"{name}.png").convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
        d = ImageDraw.Draw(img, "RGBA")
        w = d.textlength(label, font=font)
        d.rounded_rectangle((x + 10, y + th - 52, x + 30 + w, y + th - 10), 8, fill=(244, 241, 234, 225))
        d.text((x + 20, y + th - 50), label, font=font, fill=(40, 36, 38))
    img.save(path, quality=88, optimize=True)


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "style_samples")
    out.mkdir(parents=True, exist_ok=True)
    fns = {"1_sketchbook": style_sketchbook, "2_moebius": style_moebius, "3_chalk": style_chalk,
           "4_cutout": style_cutout}
    for name, _ in STYLES:
        fns[name]().save(out / f"{name}.png")
        print("wrote", out / f"{name}.png")
    if len(sys.argv) > 2:
        sheet(out, sys.argv[2])
        print("wrote", sys.argv[2])
