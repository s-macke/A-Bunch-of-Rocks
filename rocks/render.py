"""Frame loop plumbing: skia surface -> raw RGBA -> ffmpeg (D-12). No PNG intermediates."""
import os
import subprocess
import time
import skia

from .config import FPS, OUT_W, OUT_H, RES
from .files import partial


def stage_surface():
    """A raster surface at the output resolution."""
    return skia.Surface.MakeRaster(skia.ImageInfo.Make(OUT_W, OUT_H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))


def stage_canvas(surface):
    """surface's canvas, reset and scaled so that drawing in stage coordinates fills the whole surface."""
    c = surface.getCanvas()
    c.resetMatrix()
    c.scale(surface.width() / OUT_W * RES, surface.height() / OUT_H * RES)
    return c


class Film:
    """Context manager that owns a skia surface and an ffmpeg process; call frame() once per frame."""

    def __init__(self, path, fps=FPS, size=(OUT_W, OUT_H)):
        self.path, self.fps, (self.w, self.h) = path, fps, size
        self.times = []

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tmp = partial(self.path)                 # renamed to path only when the video is complete
        self.surface = skia.Surface.MakeRaster(
            skia.ImageInfo.Make(self.w, self.h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
        self.ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{self.w}x{self.h}",
             "-r", str(self.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(self.tmp)],
            stdin=subprocess.PIPE)
        return self

    def canvas(self):
        """The canvas for the next frame, in stage coordinates (W x H), scaled to the output resolution."""
        self._t = time.perf_counter()
        return stage_canvas(self.surface)

    def frame(self):
        """Emit what was drawn since canvas(); returns the RGBA array (handy for stills)."""
        arr = self.surface.makeImageSnapshot().toarray()
        self.times.append(time.perf_counter() - self._t)
        self.ff.stdin.write(arr.tobytes())
        return arr

    def __exit__(self, exc_type, *exc):
        self.ff.stdin.close()
        self.ff.wait()
        if exc_type is None and self.ff.returncode == 0:
            os.replace(self.tmp, self.path)
        else:
            self.tmp.unlink(missing_ok=True)
            if exc_type is None:
                raise RuntimeError(f"ffmpeg failed ({self.ff.returncode}) writing {self.path}")
        return False

    def stats(self):
        if not self.times:
            return "no frames"
        return f"{len(self.times)} frames, mean {1000 * sum(self.times) / len(self.times):.0f} ms, max {1000 * max(self.times):.0f} ms"
