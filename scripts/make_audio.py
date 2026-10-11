"""Generate all audio the film uses through the ElevenLabs API: narration (English and German), the re-takes, music
and sound effects.

The generated audio is not in the repository, so a fresh checkout runs this once before scripts/make_film.py.
It needs ELEVENLABS_API_KEY (environment or .env) and costs about $1 (estimate printed first; nothing is spent
without --yes). Results are cached in cache/audio/, so running it again costs nothing.

Generation is not repeatable: every run returns new performances. The shot timings in shots.yaml and the Act 3
music cut (landmarks in scripts/make_music.py) were tuned by ear to the takes of the original film, so check the
result and adjust them where a line or a cue no longer fits.

--retake <file> records just one re-take of rocks/audio/narration.py RETAKES (e.g. de/act3_line0_take_a.mp3), after
adding or changing it there; shots.yaml then plays it with voice: take (English) or de_take (German).

usage: .venv/bin/python scripts/make_audio.py [--retake <file>] [--yes]
"""
import argparse
import shutil
import sys

from rocks.config import CALM, LANGS, ROOT
from rocks.audio import el, music, narration, sfx

MUSIC = ["act2_score", "act4_pad", "universe_build_a"]          # cues from music.CUES that the film uses

ap = argparse.ArgumentParser(description="All the film's audio through the ElevenLabs API (cached; prints the cost first).")
ap.add_argument("--retake", metavar="FILE", help="record only this re-take of rocks/audio/narration.py RETAKES")
ap.add_argument("--yes", action="store_true", help="spend it (without --yes nothing is generated)")
args = ap.parse_args()

if args.retake:
    name = args.retake
    if name not in narration.RETAKES:
        sys.exit(f"no re-take {name} in rocks/audio/narration.py RETAKES")
    text = narration.retake_request(name)[0]
    print(f"re-take {name}: {len(text)} characters, about ${len(text) / 1000 * el.PRICE['tts_per_1k_chars']:.3f} "
          "(nothing if cached)")
    if not args.yes:
        sys.exit("nothing generated; run again with --yes to spend it")
    print(f"{narration.record_retake(name, confirm=True)}; spent ${el.spent():.3f} in total")
    sys.exit()

chars = (sum(len(" ".join(p)) for lang in [*LANGS, *CALM] for p in narration.parse(LANGS[lang][0]).values())
         + sum(len(narration.retake_request(n)[0]) for n in narration.RETAKES))
seconds = sum(music.CUES[n][1] for n in MUSIC) + sum(s["duration_ms"] for s in music.ACT3_PLAN["sections"]) / 1000
sfx_seconds = sum(v[1] for v in sfx.LIBRARY.values())
est = (chars / 1000 * el.PRICE["tts_per_1k_chars"] + seconds / 60 * el.PRICE["music_per_min"]
       + sfx_seconds / 60 * el.PRICE["sfx_per_min"])
print(f"narration {chars} characters, music {seconds:.0f} s, {len(sfx.LIBRARY)} sound effects: about ${est:.2f}")
if not args.yes:
    sys.exit("nothing generated; run again with --yes to spend it")

for lang in LANGS:                                               # voice/act1–4.mp3 + voice/timings.json, voice/de/…
    narration.synthesize(confirm=True, lang=lang)
for lang in CALM:                                                # voice/de/calm/…: German at its natural pace
    narration.synthesize(confirm=True, lang=lang, calm=True)
for name in narration.RETAKES:                                   # voice/<name> + its word timings (.json)
    narration.record_retake(name, confirm=True)

(ROOT / "music").mkdir(exist_ok=True)
for name in MUSIC:
    prompt, sec = music.CUES[name]
    shutil.copy(music.compose(prompt, sec, confirm=True), ROOT / "music" / f"{name}.mp3")
shutil.copy(music.compose_plan(music.ACT3_PLAN, model="music_v1", confirm=True), ROOT / "music" / "act3_score.mp3")

for name in sfx.LIBRARY:
    sfx.get(name, confirm=True)

print(f"done; spent ${el.spent():.2f} in total (cache/audio/ledger.jsonl)")
