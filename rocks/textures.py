"""Paper and watercolor textures, computed with numpy and cached as plates (D-12)."""
import hashlib
import json
import os
import numpy as np
import skia
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

from .config import W, H, HORIZON, CACHE, OUT_W, OUT_H


def noise(scale, seed, shape=(H, W)):
    return gaussian_filter(np.random.default_rng(seed).normal(0, 1, shape), scale)


def norm(a):
    return (a - a.min()) / (a.max() - a.min() + 1e-9)


class Washer:
    """Applies watercolor washes; granulation fields are computed once and reused."""

    def __init__(self, shape=(H, W), variants=3):
        self.shape = shape
        self.gran = [norm(noise(1.2, s, shape)) * 0.5 + norm(noise(14, s + 3, shape)) * 0.5 for s in range(variants)]

    def paper(self, color=(243, 236, 222), seed=11):
        base = np.full(self.shape + (3,), color, float)
        base += ((norm(noise(1, seed, self.shape)) - 0.5) * 9
                 + (norm(noise(30, seed + 1, self.shape)) - 0.5) * 12)[..., None]
        return base

    def wash(self, base, poly, color, alpha=0.55, seed=0, blur=6):
        """Soft pigment with darker drying edges and granulation, multiplied onto base."""
        h, w = self.shape
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).polygon([tuple(p) for p in poly], fill=255)
        m = np.asarray(m.filter(ImageFilter.GaussianBlur(blur)), float) / 255
        edge = np.clip(m * (1 - m) * 4, 0, 1) ** 1.5
        a = np.clip(m * (0.55 + 0.45 * self.gran[seed % len(self.gran)]) + edge * 0.35, 0, 1) * alpha
        return base * (1 - a[..., None]) + base * np.array(color) / 255 * a[..., None]


def to_skia(base):
    h, w = base.shape[:2]
    rgba = np.dstack([np.clip(base, 0, 255), np.full((h, w), 255)]).astype(np.uint8)
    return skia.Image.fromarray(rgba)


def grain_image(seed=77):
    """Granulation texture used as a shader inside wash fills drawn per frame."""
    g = norm(noise(1.0, seed)) * 0.6 + norm(noise(5, seed + 1)) * 0.4
    g = (205 + 50 * g).astype(np.uint8)
    return skia.Image.fromarray(np.dstack([g, g, g, np.full_like(g, 255)]))


def cached_plate(name, params, build):
    """Return plate `name` from cache/plates, rebuilding when params change. build() -> float RGB array."""
    key = hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
    path = CACHE / "plates" / f"{name}-{key}.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp.png")      # write, then rename: parallel builds never read half a file
        Image.fromarray(np.clip(build(), 0, 255).astype(np.uint8)).save(tmp)
        os.replace(tmp, path)
    img = Image.open(path).convert("RGB")
    if img.size != (OUT_W, OUT_H):                         # painted on the stage grid, scaled smoothly to the film's
        img = img.resize((OUT_W, OUT_H), Image.LANCZOS)
    return to_skia(np.asarray(img, float))


SUN = (0.8, 0.2, 46)          # the pale sun in the desert sky: x, y as fractions of the stage, radius


def desert_plate(washer, sky=(150, 175, 205), sun=SUN[:2]):
    """The approved sketchbook desert (D-7): paper, dusk sky, far dunes, sand, pale sun."""
    hy = H * HORIZON
    base = washer.paper()
    base = washer.wash(base, [(0, 0), (W, 0), (W, hy + 10), (0, hy + 10)], sky, 0.55, 0, 14)
    base = washer.wash(base, [(0, hy - 30), (W * .3, hy - 55), (W * .62, hy - 22), (W, hy - 40), (W, hy + 8), (0, hy + 8)],
                       (200, 160, 150), 0.35, 1, 6)
    base = washer.wash(base, [(0, hy), (W, hy), (W, H), (0, H)], (222, 190, 140), 0.6, 2, 10)
    base = washer.wash(base, [(0, H * .86), (W * .3, H * .8), (W * .7, H * .83), (W, H * .79), (W, H), (0, H)],
                       (205, 160, 115), 0.3, 0, 18)
    if sun is not None:
        t = np.linspace(0, 2 * np.pi, 64)
        base = washer.wash(base, np.stack([W * sun[0] + SUN[2] * np.cos(t), H * sun[1] + SUN[2] * np.sin(t)], 1),
                           (240, 200, 150), 0.55, 1, 8)
    return base
