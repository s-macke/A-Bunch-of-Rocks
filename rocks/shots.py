"""shots.yaml -> timed shots with voice placements and word cues resolved to shot-local seconds.

One picture, several narration languages (config.LANGS): the picture's timing (shot durations, word cues) is fitted to
every recorded language at once, and each language gets its own voice placements on it.

- A voice line starts at its `at` (tuned to the English recording), or later if the line before it in the shot runs
  longer in another language (the English gap between them is kept).
- A word cue is the time of its word; when the languages say their words at different moments, the cue takes the later
  one. The earlier language waits in the last pause before its word (the line is split there), so the word lands on
  the cue (only after a punctuation mark, in a real pause); with no such pause before it in the line, the whole line starts later (or, after an earlier split, the word
  stays where it falls, see `mismatch`).
- A shot grows where a line no longer fits; it keeps the English pause after its last line (0.25–2 s of it).
- A language recorded faster to fit (German) also has a calm recording at the voice's natural pace (config.CALM):
  each line comes from it wherever that fits the shot as it is (no longer shot, no cue lost). Sound effects that span the
  whole shot grow with it.

The English words of a cue are in `word`; the other languages' words under their language code (e.g. `de: "Hier."`).
"""
import json
from dataclasses import dataclass, field
import yaml

from .audio.narration import TAG
from .audio.silence import onset, quiet_cut, speech_span
from .config import CALM, LANGS, ROOT

ACTS = range(6)                    # 0 cold open, 1–4 the acts, 5 credits
PUNCTUATION = tuple(".,;:!?…")
MIN_TAIL, MAX_TAIL = 0.25, 2.0     # s after a grown shot's last line: the English pause, within these bounds
MAX_WAIT = 0.4                     # s a pause inside a translated line may grow to wait for a word cue; the rest
                                   # delays the line (English keeps the pauses shots.yaml was timed with)


@dataclass
class Shot:
    id: str
    act: int
    scene: str
    duration: float
    start: float                      # act-relative start
    voice: list = field(default_factory=list)   # [{line, at, src_start, src_end, words, pre, post, [take]}]: segments
    cues: dict = field(default_factory=dict)    # name -> shot-local seconds
    sfx: list = field(default_factory=list)
    params: dict = field(default_factory=dict)
    mismatch: dict = field(default_factory=dict)  # cue -> {lang: s early}: words that could not be moved onto the cue


def recorded_langs():
    """The languages whose narration has been recorded, English first."""
    return [lang for lang, (_, d) in LANGS.items() if (d / "timings.json").exists()]


def _recordings(act, lang):
    """[(act recording, its lines)]: the language's recording, then its calm one if there is one (config.CALM)."""
    dirs = [LANGS[lang][1]] + ([CALM[lang]] if lang in CALM and (CALM[lang] / "timings.json").exists() else [])
    return [(d / f"act{act}.mp3", json.loads((d / "timings.json").read_text()).get(f"act{act}", {}).get("lines", []))
            for d in dirs]


def _take_words(take):
    """Word timings of a re-take (from the alignment saved next to it), or None for a take without one."""
    path = (ROOT / take).with_suffix(".json")
    if not path.exists():
        return None
    a = json.loads(path.read_text())
    text, starts, ends = "".join(a["characters"]), a["character_start_times_seconds"], a["character_end_times_seconds"]
    spoken = [True] * len(text)                  # audio tags ("[pause]", also mid-line) are performed, not spoken
    for m in TAG.finditer(text):
        spoken[m.start():m.end()] = [False] * (m.end() - m.start())
    words, cur = [], []
    for i, ch in enumerate(text + " "):
        if i < len(text) and spoken[i] and not ch.isspace():
            cur.append(i)
        elif cur:
            words.append({"w": text[cur[0]:cur[-1] + 1], "start": round(starts[cur[0]], 3),
                          "end": round(ends[cur[-1]], 3)})
            cur = []
    return words


def _word(c, lang):
    return c["word"] if lang == "en" else c[lang]


def _occurrence(c, lang):
    return c.get(f"{lang}_occurrence", c.get("occurrence", 1))


def _fit(s, langs, recs, choice):
    """Shared duration and cues of one shot spec, and every language's segments. recs: _recordings() per language;
    choice: {lang: {line: index into recs}} (default 0)."""
    cues, mismatch = {}, {}
    segs = {lang: [] for lang in langs}          # [line, src_a, src_b, at, take, words]
    prev_end = {lang: None for lang in langs}
    prev_end_en = None                           # where the previous line ended in the English timing of shots.yaml
    tail = s["duration"]
    for v in s.get("voice", []):
        own = {}
        for lang in langs:
            key = "take" if lang == "en" else f"{lang}_take"
            if key in v:                         # a separate re-take of this line replaces the act recording
                a, b = speech_span(ROOT / v[key])        # (take_start/take_end in shots.yaml override it)
                own[lang] = (v.get(f"{key}_start", a), v.get(f"{key}_end", b), _take_words(v[key]), v[key],
                             ROOT / v[key])
            else:
                k = choice[lang].get(v["line"], 0)
                rec, lines = recs[lang][k]
                ln = lines[v["line"]]
                own[lang] = (ln["start"], ln["end"], ln["words"], str(rec) if k else None, rec)
        gap = v["at"] - prev_end_en if prev_end_en is not None else 0.0
        line_segs = {}
        for lang in langs:
            a, b, words, take, _ = own[lang]
            start = v["at"] if prev_end[lang] is None else max(v["at"], prev_end[lang] + max(gap, 0.3))
            line_segs[lang] = [[v["line"], a, b, start, take, words]]
        here = [(n, c) for n, c in (s.get("cues") or {}).items() if c["line"] == v["line"]]
        if here and any(own[lang][2] is None for lang in langs):
            raise ValueError(f"shot {s['id']}: word cues on re-takes are not supported")

        def word_of(lang, c):
            ws = own[lang][2]
            k = [i for i, w in enumerate(ws) if w["w"] == _word(c, lang)][_occurrence(c, lang) - 1]
            return k, ws

        def natural(lang, t_src):
            seg = next(g for g in reversed(line_segs[lang]) if g[1] <= t_src)
            return seg[3] + t_src - seg[1]

        here.sort(key=lambda nc: own["en"][2][word_of("en", nc[1])[0]]["start"])     # in spoken order
        for i, (name, c) in enumerate(here):
            t = {lang: natural(lang, own[lang][2][word_of(lang, c)[0]]["start"]) for lang in langs}
            T = max(t.values())
            for lang in langs:
                late = T - t[lang]
                if late <= 1e-6:
                    continue
                k, ws = word_of(lang, c)
                g = line_segs[lang][-1]
                # the last pause before the word (inside the part of the line not yet placed) takes the wait
                rec = own[lang][4]
                cut = None
                for j in range(k, 0, -1):
                    if ws[j - 1]["end"] - 0.12 <= g[1]:
                        break
                    if not ws[j - 1]["w"].endswith(PUNCTUATION):      # wait between phrases, never inside one
                        continue
                    cut = quiet_cut(rec, ws[j - 1]["end"] - 0.12, ws[j]["start"] + 0.06)
                    if cut is not None:
                        break
                if cut is None:
                    if len(line_segs[lang]) == 1:          # no pause yet: the whole line starts later
                        g[3] += late
                    else:
                        mismatch.setdefault(name, {})[lang] = round(late, 3)
                    continue
                # a long wait inside a line sounds like a stumble: start the line later, keep the pause short
                # (only for the line's first cue: a later one would move the cues already placed)
                if lang != "en" and i == 0 and len(line_segs[lang]) == 1:
                    early = max(0.0, late - MAX_WAIT)
                    g[3] += early
                    late -= early
                line_segs[lang][-1] = [g[0], g[1], cut, g[3], g[4], g[5]]
                line_segs[lang].append([g[0], cut, g[2], g[3] + (cut - g[1]) + late, g[4], g[5]])
            cues[name] = T
        for lang in langs:
            g = line_segs[lang][-1]
            prev_end[lang] = g[3] + g[2] - g[1]
            segs[lang] += line_segs[lang]
        a, b = own["en"][:2]
        prev_end_en = v["at"] + b - a
        tail = s["duration"] - prev_end_en
    ends = [e for e in prev_end.values() if e is not None]
    duration = max([s["duration"]] + [e + min(max(tail, MIN_TAIL), MAX_TAIL) for e in ends])
    return duration, cues, segs, mismatch


def load(act, lang="en", path=ROOT / "shots.yaml"):
    """The act's shots, timed for every recorded language, with `lang`'s voice placements."""
    spec = yaml.safe_load(path.read_text())[f"act{act}"]
    langs = recorded_langs()
    if lang not in langs:
        raise ValueError(f"no {lang} narration recorded yet (scripts/make_audio.py)")
    recs = {la: _recordings(act, la) for la in langs}
    shots, t = [], 0.0
    for s in spec:
        choice = {la: {} for la in langs}
        duration, cues, segs, mismatch = _fit(s, langs, recs, choice)
        for la in langs:                         # a calm recording wherever its line fits the shot as it is
            if len(recs[la]) < 2:
                continue
            for v in s.get("voice", []):
                choice[la][v["line"]] = 1
                fit = _fit(s, langs, recs, choice)
                if fit[0] <= duration + 1e-6 and len(fit[3]) <= len(mismatch):
                    _, cues, segs, mismatch = fit
                else:
                    choice[la][v["line"]] = 0
        voice = []
        mine = segs[lang]
        for i, (line, a, b, at, take, words) in enumerate(mine):
            first = i == 0 or mine[i - 1][0] != line
            last = i == len(mine) - 1 or mine[i + 1][0] != line
            pre = 0.0
            if first:                            # from where the first word's sound starts (its alignment is late)
                pre = max(0.06, a - onset(ROOT / take if take else recs[lang][0][0], a))
            seg = {"line": line, "at": at, "src_start": a, "src_end": b, "words": words,
                   "pre": round(pre, 3), "post": 0.25 if last else 0.0}
            if take:
                seg["take"] = take
            voice.append(seg)
        sfx = []
        for e in s.get("sfx", []):
            e = dict(e)
            if isinstance(e["at"], str):
                e["at"] = cues[e["at"]]
            grow = duration - s["duration"]        # effects that last to the end of the shot last the grown shot
            if "dur" in e and e["at"] + e["dur"] >= s["duration"] - 0.01:
                e["dur"] += grow
            if "until" in e and e["until"] >= s["duration"] - 0.01:
                e["until"] += grow
            sfx.append(e)
        shots.append(Shot(id=s["id"], act=s["act"], scene=s["scene"], duration=duration, start=t, voice=voice,
                          cues=cues, sfx=sfx, params=s.get("params", {}), mismatch=mismatch))
        t += duration
    for sh in shots:
        for v in sh.voice:
            if v["at"] + v["src_end"] - v["src_start"] > sh.duration + 0.05:
                raise ValueError(f"shot {sh.id}: voice line {v['line']} runs past the shot end")
    return shots


def act_starts():
    """({act: where it starts in the film, s}, the film's length): one picture for every language."""
    starts, t = {}, 0.0
    for a in ACTS:
        sh = load(a)
        starts[a] = t
        t += sh[-1].start + sh[-1].duration
    return starts, t


# the chapter titles, as in docs/youtube.md (English); the film's MP4 carries them as chapter marks (rocks.filmmix)
CHAPTERS = {0: "Cold open", 1: "Loneliness & discovery", 2: "The computer", 3: "Universe", 4: "Our world",
            5: "Credits"}


def timecode(t):
    """m:ss, as YouTube chapters write it."""
    return f"{int(t // 60)}:{int(t % 60):02d}"


if __name__ == "__main__":                       # python -m rocks.shots: where each act starts (YouTube chapters)
    starts, total = act_starts()
    for a, t in starts.items():
        print(f"{timecode(t)} {CHAPTERS[a]}  (act {a}, {t:.2f} s)")
    print(f"end    {timecode(total)}  ({total:.2f} s)")
