"""Render one shot with its voice and sound effects, as in the film, to try a change or an alternative scene.

The sound is built with the film's own code (rocks.mix): the same voice takes, wind and effect levels. There is no
music and no final loudness pass, so levels are close to the film but not exact.

usage: .venv/bin/python scripts/test_shot.py [--lang de] [--scene <name>] <shot_id> <out.mp4>
       e.g. test_shot.py --lang de 2.8 test.mp4
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from rocks.build import act_of, shot_drawer
from rocks.config import BUILD, FPS, boil_at
from rocks.mix import SR, act_voice, place_events, place_shot, write_wav
from rocks.render import Film

ap = argparse.ArgumentParser(description="One shot with its sound -> MP4.")
ap.add_argument("shot", help='shot id, e.g. "2.8"')
ap.add_argument("out", type=Path, help="output .mp4")
ap.add_argument("--lang", default="en", help="narration language (default en); the picture is the same in all")
ap.add_argument("--scene", help="another scene from the act's SCENES, to compare variants (default: the shot's own)")
a = ap.parse_args()
shot, draw = shot_drawer(a.shot, scene=a.scene, lang=a.lang)

with tempfile.TemporaryDirectory(dir=BUILD) as tmp:     # the silent video and the sound, removed afterwards
    silent, wav = Path(tmp) / "silent.mp4", Path(tmp) / "sound.wav"
    first = round(shot.start * FPS)                     # boil phase as in the film
    with Film(silent) as film:
        for k in range(round(shot.duration * FPS)):
            draw(film.canvas(), k / FPS, boil_at(first + k))
            film.frame()

    n = int(round(shot.duration * SR))
    voice, fx, cache = np.zeros(n, np.float32), np.zeros(n, np.float32), {}
    place_shot(voice, fx, shot, 0.0, act_voice(act_of(a.shot), a.lang), cache)
    place_events(fx, getattr(draw, "events", []), cache)
    write_wav(wav, voice + fx)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(a.out)], check=True)
print(a.out)
