"""Fast checks of the film's structure: every shot has a scene, voice lines fit their shots, text is drawable."""
import importlib

import pytest
import yaml

from rocks.config import ROOT
from rocks.lettering import FACE, Lettering
from rocks.shots import load, recorded_langs

from rocks.shots import ACTS


SPEC = yaml.safe_load((ROOT / "shots.yaml").read_text())
HAS_AUDIO = (ROOT / "voice" / "timings.json").exists()


@pytest.mark.parametrize("act", ACTS)
def test_every_shot_has_a_scene(act):
    scenes = importlib.import_module(f"rocks.scenes.act{act}").SCENES
    for shot in SPEC[f"act{act}"]:
        assert shot["scene"] in scenes, f"shot {shot['id']}: no scene '{shot['scene']}' in act{act}.SCENES"


@pytest.mark.skipif(not HAS_AUDIO, reason="no generated audio yet (scripts/make_audio.py)")
@pytest.mark.parametrize("act", ACTS)
def test_voice_lines_fit_their_shots(act):
    for lang in recorded_langs():
        load(act, lang)                        # raises if a voice line runs past its shot or a word cue is missing


@pytest.mark.skipif(not HAS_AUDIO, reason="no generated audio yet (scripts/make_audio.py)")
@pytest.mark.parametrize("act", ACTS)
def test_every_language_shares_one_picture(act):
    timing = [[(s.duration, s.cues) for s in load(act, lang)] for lang in recorded_langs()]
    assert all(t == timing[0] for t in timing)
    for s in load(act):
        assert all(late < 0.15 for m in s.mismatch.values() for late in m.values()), f"shot {s.id}: {s.mismatch}"


def test_shot_ids_are_unique_and_in_order():
    for act in ACTS:
        ids = [s["id"] for s in SPEC[f"act{act}"]]
        assert ids == [f"{act}.{n}" for n in range(1, len(ids) + 1)]


def test_lettering_has_every_glyph_it_draws():
    font = Lettering(40)
    text = "iħ ∂ψ/∂t = Ĥψ · ΔxΔp ≥ ħ/2 · ∇·E = ρ/ε₀ · F = G m₁m₂ / r² · π = 3.14159… · d/dx eˣ"
    for piece, f, _ in font.runs(text):
        for ch in piece:
            assert FACE.unicharToGlyph(ord(ch)) != 0 or ch == " ", f"xkcd Script has no glyph for {ch!r}"


@pytest.mark.skipif(not HAS_AUDIO, reason="no generated audio yet (scripts/make_audio.py)")
@pytest.mark.parametrize("lang", ["en", "de"])
def test_subtitles_are_ordered_and_fit_two_lines(lang):
    from rocks.subtitles import MAX_LINE, cues, spoken_lines, wrap
    if lang not in recorded_langs():
        pytest.skip(f"no {lang} narration recorded")
    cs = cues(spoken_lines(lang))
    assert cs
    for (a, b, text), nxt in zip(cs, cs[1:] + [(float("inf"),)]):
        assert a < b <= nxt[0]
        assert len(wrap(text).split("\n")) <= 2
        assert all(len(line) <= MAX_LINE + 4 for line in wrap(text).split("\n"))


@pytest.mark.skipif(not HAS_AUDIO, reason="the narration is not recorded yet (scripts/make_audio.py)")
def test_youtube_chapters_match_the_film():
    """docs/youtube.md lists one chapter per act, in each language; their times follow the act lengths."""
    import re
    from rocks.shots import ACTS, act_starts, timecode
    starts, _ = act_starts()
    want = [timecode(starts[a]) for a in ACTS]
    times = re.findall(r"^(\d+:\d\d) ", (ROOT / "docs" / "youtube.md").read_text(), re.M)
    assert times == want * (len(times) // len(want)) and times, \
        f"chapters in docs/youtube.md: {times}; the acts start at {want} (python -m rocks.shots)"
    from rocks.shots import CHAPTERS                 # the English titles are the film's own chapter marks
    english = [f"{timecode(starts[a])} {CHAPTERS[a]}" for a in ACTS]
    assert "\n".join(english) in (ROOT / "docs" / "youtube.md").read_text(), \
        f"docs/youtube.md has no English chapter list {english} (rocks.shots.CHAPTERS)"
