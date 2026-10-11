"""Global film settings (spec D-12, D-15)."""
import pathlib

W, H = 1280, 720    # the stage: every scene draws in these coordinates
OUT_W, OUT_H = 1920, 1080   # the rendered film; the stage is scaled up to it, so lines stay sharp (1440p: 2560, 1440)
RES = OUT_W / W     # output pixels per stage unit
FPS = 24            # frame rate of the film (12 until 2026-10-10)
BOIL = 3            # distinct drawings per line-boil cycle
BOIL_FPS = 12       # line-boil drawings per second, independent of FPS: at 24 fps each drawing holds two frames
HORIZON = 0.52      # horizon height as a fraction of H
INK = (40, 36, 38)

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
SCRIPT = ROOT / "docs" / "script.md"            # the narration script, read by the audio and storyboard code
BUILD = ROOT / "build"                       # intermediate renders and mixes, rebuilt on every run
FILM = ROOT / "film" / "a_bunch_of_rocks.mp4"   # the finished film
# narration languages: script and recording folder. English is the original and the film's first audio track; the others
# are line-by-line translations of it, sharing one picture (rocks.shots fits the timing to all of them)
LANGS = {"en": (SCRIPT, ROOT / "voice"), "de": (SCRIPT.with_name("script.de.md"), ROOT / "voice" / "de")}
# a second recording at the voice's natural pace, for languages recorded faster to fit the picture: rocks.shots takes a
# line from it wherever it fits the shot as it is (German is recorded at speed 1.15, and calm at 1.0)
CALM = {"de": ROOT / "voice" / "de" / "calm"}


def boil_at(frame):
    """Which of the BOIL drawings frame number `frame` shows."""
    return frame * BOIL_FPS // FPS % BOIL
