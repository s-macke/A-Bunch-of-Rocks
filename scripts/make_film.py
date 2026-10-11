"""Make the whole film from a fresh checkout: render all six parts, rebuild the music, mix, encode, subtitles,
thumbnail.

Output: film/a_bunch_of_rocks.mp4 with one audio track per narration language (English default, German), and next to
it a_bunch_of_rocks.de.m4a (the German audio alone, for YouTube's multi-language audio), .en.srt / .de.srt and
.thumbnail.png (for YouTube; see docs/youtube.md).

Needs the generated audio (voice/, music/*.mp3, cache/audio/); in a fresh checkout run scripts/make_audio.py first.
Takes about 12 minutes on 8 cores.

--acts 1,2 renders only those parts again (after changing their scenes or shots) and reuses the others' videos from
build/ (--acts "" renders none, e.g. after changing only the audio); music, mix, subtitles and thumbnail are always redone, in order. Only one make_film.py runs at a time: a second
one waits for the first (a lock on build/.make_film.lock, released by the system whenever a run ends, even on a crash).

usage: .venv/bin/python scripts/make_film.py [--acts 1,2] [out.mp4]      (default: all parts, film/a_bunch_of_rocks.mp4)
"""
import argparse
import fcntl
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rocks.config import BUILD, FILM, ROOT
from rocks.shots import recorded_langs

PY = sys.executable

if not (ROOT / "voice" / "timings.json").exists():
    sys.exit("no generated audio yet: run scripts/make_audio.py first (needs an ElevenLabs API key, about $1)")


def run(*args):
    subprocess.run([PY, *args], check=True, cwd=ROOT)


ap = argparse.ArgumentParser(description="The whole film (or some parts again), its mix, subtitles and thumbnail.")
ap.add_argument("out", nargs="?", default=str(FILM))
ap.add_argument("--acts", help='parts to render again, e.g. "1,2" ("" for none; default: all)')
a = ap.parse_args()
acts = range(6) if a.acts is None else [int(x) for x in a.acts.split(",") if x]
missing = [a for a in range(6) if a not in acts and not (BUILD / f"act{a}_silent.mp4").exists()]
if missing:
    sys.exit(f"no rendered video of part(s) {missing} in build/ yet: render them too (--acts) or leave out --acts")

BUILD.mkdir(exist_ok=True)
lock = open(BUILD / ".make_film.lock", "w")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("waiting for another make_film.py run to finish…", flush=True)
    fcntl.flock(lock, fcntl.LOCK_EX)

# 1. picture: every part renders independently (silent video + the sound events its scenes report)
with ThreadPoolExecutor() as pool:
    list(pool.map(lambda a: run("-m", "rocks.build", str(a), "--no-stills"), acts))
# 2. music: levelled against the voice, fitted to the picture's timing
run(str(ROOT / "scripts" / "make_music.py"))
# 3. sound and final encode: one continuous mix for the whole film
out = a.out
run("-m", "rocks.filmmix", out)
# 4. subtitles from the narration's word timings, next to the film (for YouTube Studio), one file per language
for lang in recorded_langs():
    run("-m", "rocks.subtitles", "--lang", lang, str(Path(out).with_suffix(f".{lang}.srt")))
# 5. the YouTube thumbnail (title, description and upload settings: docs/youtube.md)
run(str(ROOT / "scripts" / "thumbnail.py"), str(Path(out).with_suffix(".thumbnail.png")))
