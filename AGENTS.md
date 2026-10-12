# AGENTS.md

A Bunch of Rocks: a short-film adaptation of xkcd #505, published non-commercially (e.g. YouTube without monetization).

## Filesystem layout

```
a_bunch_of_rocks.png   the original comic (source material)
.env                   ELEVENLABS_API_KEY=…: secret, never print, copy or commit it; optional ELEVENLABS_BUDGET_USD
.env.example           template for .env, committed; never put a real key in it
AGENTS.md              rules for agents (this file)
LICENSE                MIT, for the code (rocks/, scripts/, tests/)
LICENSE-content        CC BY-NC 4.0 for the film content (scripts, screenplay, shots.yaml, docs, the film); third-party licenses
README.md              the making-of and how to build the film
shots.yaml             shot list per act: scene, duration, voice line placement, word cues, sound effects
credits.md             end-credits text, rendered into the film (act 5)
pyproject.toml         Python package "rocks" and its dependencies (uv)
rocks/                 the film's code
  config.py              stage 1280×720 (all scene coordinates), output 1920×1080, 24 fps, line boil (12 drawings/s), ink, paths
  render.py              Film: skia surface piped into ffmpeg
  files.py               atomic outputs: written under a temporary name, renamed when complete
  ink.py                 wobbly hand-drawn lines, rocks (Pens)
  textures.py            paper and watercolor washes, plates cached on disk
  rig.py                 stick figure: skeleton, named poses, blends, two-bone IK
  sprites.py             pre-drawn rock sprites for large rock fields
  lettering.py           all on-screen text, in the xkcd Script font
  automaton.py           Rule 110
  shots.py               loads shots.yaml: one picture timing fitted to every narration language, word cues to times;
                         act_starts(); python -m rocks.shots prints where each act starts (YouTube chapters)
  build.py               renders one act: python -m rocks.build <act>; shot_drawer(), still(): one shot, one frame
  mix.py                 one act's audio stems: python -m rocks.mix <act>
  filmmix.py             the whole film's mix and final video: python -m rocks.filmmix
  subtitles.py           the film's subtitles (.srt) from the narration's word timings: python -m rocks.subtitles
  scenes/
    act0.py … act5.py      one function per scene; each module's SCENES maps shots.yaml scene names to them
    desert.py              pieces several acts share: rock rows, the Rule 110 field, the wide desert shot
    common.py              scene context Ctx (pens, plates, sprites), Camera, bake, fades, night sky
    writing.py             time-lapse writing in the sand (Act 1)
  audio/
    el.py                  ElevenLabs client: content-hash cache and spend ledger with a budget
    narration.py, tts.py   docs/script.md -> voice/act<N>.mp3 + voice/timings.json (German: script.de.md -> voice/de/);
                           RETAKES: single lines recorded again
    silence.py             where a recording is silent (where shots.py may split a line), where a re-take's speech is
    music.py               music generation
    sfx.py                 sound-effect library (name -> prompt)
scripts/
  make_audio.py          all audio through the ElevenLabs API: narration, re-takes, music, sound effects;
                         --retake <file> records one re-take (rocks/audio/narration.py RETAKES)
  make_film.py           the whole film: build all parts (or --acts 1,2), make_music.py, filmmix, subtitles, thumbnail
  make_music.py          music/*.mp3 -> music/act<N>.wav, fitted to the picture (incl. the Act 3 cut)
  storyboard.py          the storyboard page (layout in storyboard.html)
  thumbnail.py           the YouTube thumbnail: a frame of shot 4.6 with the title
  frame.py, test_shot.py, pose_sheet.py   debug tools: a frame, a shot with sound, the pose sheet
  pose_gif.py            the poses in motion, as a GIF (docs/poses.gif)
  experiments/           early standalone experiments (style samples, renderer speed); not part of the build
tests/                 pytest: Rule 110, shot list, lettering
fonts/                 xkcd fonts and their LICENSE
voice/                 generated narration and word timings, re-takes with their alignment .json; voice/de/: German
                       (speed 1.15), voice/de/calm/: German at its natural pace
                       (not in git)
music/                 *.mp3: generated music; act<N>.wav: fitted by make_music.py (not in git)
cache/audio/           every paid API result plus ledger.jsonl: never delete (not in git)
cache/plates/          cached background plates: safe to delete, they are rebuilt (not in git)
docs/script.md         narration script: "N: " lines are spoken, "(…)" lines are directions
docs/script.de.md      the German translation: the same lines in the same order (line k = line k), so keep both in step
docs/screenplay.md     the screenplay: scenes, action, narration, sound and music cues, by shot and timecode;
                       keep it in step with docs/script.md and shots.yaml when shots change
docs/youtube.md        YouTube upload: titles and descriptions (English, German), chapters, settings, which file goes where;
                       update the chapter times when act lengths change
docs/thumbnail.jpg     the README's title image: the YouTube thumbnail (scripts/thumbnail.py docs/thumbnail.jpg)
docs/style_samples.jpg the README's image of the four looks tried first (scripts/experiments/style_samples.py)
docs/poses.gif         the README's animation of the figure's poses (scripts/pose_gif.py docs/poses.gif)
docs/brainstorm/       spec.md, decisions.md (facts F-n, decisions D-n; code comments cite them), style samples:
                       local only, never commit (see .gitignore)
film/                  the finished film a_bunch_of_rocks.mp4 (audio tracks: English, German), a_bunch_of_rocks.de.m4a
                       (German audio for a YouTube dub), subtitles a_bunch_of_rocks.<lang>.srt, a_bunch_of_rocks.thumbnail.png
                       (not in git)
build/                 intermediate renders and mixes: generated, never edit by hand (not in git)
```

Where things go:

- A new or changed shot: its scene function in `rocks/scenes/act<N>.py`, registered in that module's `SCENES`, and
  the shot in `shots.yaml`. Anything used by more than one act goes in `desert.py` or `common.py`; acts never
  import from each other.
- The narration exists in English and German on one picture. A changed or new line goes into `docs/script.md` and
  `docs/script.de.md` at the same position; a new word cue in `shots.yaml` needs its German word (`de:`). Shot
  lengths and cues follow from both recordings (`rocks/shots.py`), so never tune a shot to one language only.
- On-screen text always goes through `rocks.lettering.Lettering`, never a system font.
- Scenes draw in stage coordinates (1280×720); the renderer scales to the output resolution. Full-frame images
  (plates, paper, baked backgrounds) are drawn with `full()`, never `drawImage(img, 0, 0)`. Multiply-blended paint
  (ground shadows) must be drawn onto the sand, never on a separate layer that is faded in. Rock fills are opaque.
- Every ElevenLabs request goes through `rocks.audio.el.cached_call`, so it is cached and counted against the budget.
- Rendering must stay deterministic (seeded randomness only). After a refactor, compare frames before and after.
- Run `.venv/bin/python -m pytest` after changes.
- To rebuild the film after a change, run `scripts/make_film.py --acts <changed parts>` as one command (in the
  background if it is long), not separate steps chained by hand. It renders, then mixes, in order; a second run waits
  for the first (a lock). Never wait for a build by searching the process list (`pgrep -f`, `ps | grep`): the
  pattern matches the waiting command's own command line, and the wait never ends. Videos and mixes are written
  atomically (`rocks/files.py`), and filmmix stops if an act's video no longer has the length shots.yaml gives it.
- The film and the audio generated with ElevenLabs are never committed (see `.gitignore`). The film must stay
  reproducible from the repository plus an API key: `scripts/make_audio.py`, then `scripts/make_film.py`. So every
  generation request belongs in code (prompts and settings in `rocks/audio/`, called by `make_audio.py`), and every
  step that derives a file from generated audio belongs in code (e.g. `scripts/make_music.py`), never only in a
  one-off command.

## Asset licenses

Anything that ends up in the film or its pages and comes from outside this repo (downloaded from the Internet or
generated through an API) may only be used if its license or terms allow **non-commercial** use. This covers music,
sound effects, voices, fonts, images, textures, video, 3D models, and any other asset.

- Before adding such an asset, find its license or terms of use (the source's license file, the provider's terms page)
  and check that they allow non-commercial use, including adapting it and publishing it on YouTube.
- If the license forbids that, is missing, or is unclear, **do not use the asset. Ask the user first.**
- If the license requires credit (e.g. CC BY or CC BY-NC), add a line to `credits.md` (it is rendered into the end
  credits), naming the asset, its source and its license.
- Keep a copy of the license next to downloaded assets (e.g. `fonts/LICENSE`).

Current external assets and their licenses:

| Asset | Source | License |
|---|---|---|
| Story, signature lines | xkcd #505 by Randall Munroe | CC BY-NC 2.5 |
| Font `fonts/xkcd-script.ttf`, `fonts/xkcd.otf` | github.com/ipython/xkcd-font | CC BY-NC 3.0 |
| Narration, music, sound effects | ElevenLabs API | ElevenLabs terms (commercial use only on a paid plan; non-commercial use is fine) |
