"""Subtitles for the whole film from the narration's word timings: python -m rocks.subtitles [--lang de] [out.srt]

Every voice line in shots.yaml is placed in the film at act start + shot start + at; its words carry their times in the
recording (voice/timings.json for the act recordings, voice/<take>.json for the re-takes; read by rocks.shots), so
each subtitle appears exactly while its words are spoken. Lines are split into cues at sentence ends (at most two lines of 42 characters).
Default output: film/a_bunch_of_rocks.<lang>.srt, next to the film (upload it in YouTube Studio under Subtitles).
"""
import argparse
import re

from .config import FILM
from .shots import ACTS, act_starts, load

MAX_LINE = 42                       # characters per subtitle line (two lines per cue)
MIN_SHOW, LINGER, GAP = 1.0, 0.4, 0.04


def spoken_lines(lang="en"):
    """Every voice line of the film in `lang`, in order, as a list of (film time start, end, word). A line placed in
    several segments (rocks.shots: split to land a word on its cue) is still one line."""
    out = []
    starts, _ = act_starts()
    for a in ACTS:
        for sh in load(a, lang):
            for v in sh.voice:
                at = starts[a] + sh.start + v["at"] - v["src_start"]
                # a line's first word may be aligned a little before the speech starts: it counts if it reaches in
                mine = [(at + w["start"], at + w["end"], w["w"]) for w in v["words"]
                        if v["src_start"] - v["pre"] <= (w["end"] if v["pre"] else w["start"]) and
                        w["start"] < v["src_end"] + v["post"]]
                if v["pre"] == 0 and out:                 # the rest of a split line
                    out[-1] += mine
                else:
                    out.append(mine)
    return out


def text(ws):
    return " ".join(w[2] for w in ws)


def split_long(ws):
    """A sentence too long for one cue: split at the comma nearest its middle, else at the middle word."""
    if len(text(ws)) <= 2 * MAX_LINE or len(ws) < 2:
        return [ws]
    mid = len(text(ws)) / 2
    at = [i + 1 for i in range(len(ws) - 1) if ws[i][2].endswith(",")]
    pos = lambda i: len(text(ws[:i]))
    i = min(at or range(1, len(ws)), key=lambda i: abs(pos(i) - mid))
    return split_long(ws[:i]) + split_long(ws[i:])


def cues(lines):
    """(start, end, text) cues: each voice line split into sentences (long ones split again), then short neighbours
    merged while they are short and fit on one line; a cue never spans two voice lines."""
    out = []
    for ws in lines:
        sentences, cur = [], []
        for i, w in enumerate(ws):
            cur.append(w)
            nxt = ws[i + 1][2] if i + 1 < len(ws) else ""
            if not nxt or re.search(r"[.?!]$", w[2]):     # "…" never ends a cue ("just… vanish", "taten… Dinge")
                sentences.append(cur)
                cur = []
        chunks = [c for s in sentences for c in split_long(s)]
        merged = [chunks[0]] if chunks else []
        for c in chunks[1:]:
            short = len(text(merged[-1])) <= 24                  # "Here. Not here. Here.", not "…rocks. Here."
            if short and len(text(merged[-1] + c)) <= MAX_LINE and c[0][0] - merged[-1][-1][1] < 0.6:
                merged[-1] = merged[-1] + c
            else:
                merged.append(c)
        out += [[c[0][0], c[-1][1], text(c)] for c in merged]
    for k, c in enumerate(out):                       # linger a little, at least MIN_SHOW, never into the next cue
        limit = out[k + 1][0] - GAP if k + 1 < len(out) else c[1] + 2
        c[1] = min(max(c[1] + LINGER, c[0] + MIN_SHOW), limit)
    return [tuple(c) for c in out]


def wrap(text):
    """One line, or two lines broken near the middle, after a comma or full stop if there is one close by."""
    if len(text) <= MAX_LINE:
        return text
    spaces = [i for i, ch in enumerate(text) if ch == " "]
    spaces = [i for i in spaces if max(i, len(text) - i - 1) <= MAX_LINE + 4] or spaces
    i = min(spaces, key=lambda s: abs(s - len(text) / 2) - (10 if text[s - 1] in ",." else 0))
    return text[:i] + "\n" + text[i + 1:]


def stamp(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(cs):
    return "\n".join(f"{k}\n{stamp(a)} --> {stamp(b)}\n{wrap(text)}\n" for k, (a, b, text) in enumerate(cs, 1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="The film's subtitles -> .srt.")
    ap.add_argument("out", nargs="?", help="output .srt (default: film/a_bunch_of_rocks.<lang>.srt)")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    lang, out = a.lang, a.out or str(FILM.with_suffix(f".{a.lang}.srt"))
    FILM.parent.mkdir(exist_ok=True)
    cs = cues(spoken_lines(lang))
    open(out, "w").write(srt(cs))
    print(f"{out}: {len(cs)} subtitles")
