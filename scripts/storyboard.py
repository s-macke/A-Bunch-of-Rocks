"""Storyboard: one HTML page with every shot of the film, act by act: stills, narration, directions, sound.

Stills come from build/act<N>_silent.mp4 (the newest picture), narration and directions from docs/script.md,
timing and sound from shots.yaml + voice/timings.json + build/act<N>_events.json. Images are embedded,
so the page is a single file.

usage: .venv/bin/python scripts/storyboard.py [out.html]
"""
import argparse
import ast
import base64
import html
import json
import pathlib
import re
import subprocess

from rocks.config import FPS, BUILD, ROOT, SCRIPT
from rocks.shots import load

ACTS = {
    0: ("Cold open", "Paper texture; a horizon line draws itself.", "Wind only."),
    1: ("Loneliness & discovery", "He wakes and walks; day and night cycle faster; equations in the sand.",
        "Wind and footsteps, no music."),
    2: ("The computer", "Rock rows follow one rule and spread as a truly computed Rule 110 automaton.",
        "Stone clicks; a pulsing minimal motif starts and grows."),
    3: ("Universe", "Rows blur; particles, a watercolor big bang, galaxies, a planet, life, a human.",
        "Full swell; 13 s of music with no narration for the universe beat."),
    4: ("Our world", "A dust mote vanishes; he holds a rock; a lecture hall with a slow clock; back to one row.",
        "Near silence."),
    5: ("Credits", "Based on xkcd #505 “A Bunch of Rocks” by Randall Munroe, CC BY-NC 2.5.", "Wind carries on."),
}
SFX_NAMES = {"desert_wind": "wind", "rock_set_down": "rock set down", "footstep_sand": "footsteps",
             "dust_flash": "dust flash", "room_tone": "room tone", "clock_tick": "clock tick"}
STILL_AT = (0.15, 0.5, 0.88)          # where in each shot the three stills are taken
STILL_W = 720


def script_lines():
    """script.md -> {act: [{"text", "tags", "signature", "directions"}]}; directions are those just before a line."""
    acts, act, pending = {}, None, []
    for raw in SCRIPT.read_text().splitlines():
        if raw.startswith("## "):
            if act is not None and pending:
                acts[act].append({"text": None, "tags": [], "signature": False, "directions": pending})
            act = 0 if "Cold open" in raw else 5 if "Credits" in raw else int(re.search(r"Act (\d)", raw)[1])
            acts[act], pending = [], []
        elif act is None:
            continue
        elif raw.startswith("("):
            pending.append(re.sub(r";?\s*D-\d+\.?", ".", raw.strip("()")).replace("..", "."))
        elif raw.startswith("N: "):
            text = raw[3:]
            tags = re.findall(r"\[([^\]]+)\]", text)
            sig = any("★" in d for d in pending)
            dirs = [d for d in (re.sub(r"★ signature line;?\s*", "", d).strip() for d in pending) if d]
            acts[act].append({"text": re.sub(r"\[[^\]]+\]\s*", "", text).strip(), "tags": tags,
                              "signature": sig, "directions": dirs})
            pending = []
    if act is not None and pending:
        acts[act].append({"text": None, "tags": [], "signature": False, "directions": pending})
    return acts


def scene_notes():
    """Scene function docstrings, by scene name, with spec references (D-27, …) stripped."""
    notes = {}
    for path in (ROOT / "rocks" / "scenes").glob("*.py"):
        for node in ast.parse(path.read_text()).body:
            doc = isinstance(node, ast.FunctionDef) and ast.get_docstring(node)
            if doc and not node.name.startswith("_"):
                doc = re.sub(r"\s*\((?:D|AC|Q|F)-\d+[^)]*\)", "", " ".join(doc.split()))
                notes[node.name] = doc
    return notes


def still(act, t):
    jpg = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(BUILD / f"act{act}_silent.mp4"),
                          "-frames:v", "1", "-vf", f"scale={STILL_W}:-2", "-q:v", "5", "-f", "image2pipe",
                          "-c:v", "mjpeg", "-"], capture_output=True, check=True).stdout
    return "data:image/jpeg;base64," + base64.b64encode(jpg).decode()


def tc(s):
    return f"{int(s // 60)}:{s % 60:04.1f}"


def sound_chips(shot, events):
    chips = []
    for e in shot.sfx:
        name = SFX_NAMES.get(e["name"], e["name"].replace("_", " "))
        if "every" in e:
            n = int((e["until"] - e["at"]) // e["every"]) + 1
            name += f" ×{n}"
        elif e["name"] != "desert_wind" and e["at"] > 0:
            name += f" @ {e['at']:.1f}s"
        chips.append((name, e.get("gain_db")))
    counts = {}
    for e in events:
        if shot.start <= e["at"] < shot.start + shot.duration:
            counts[e["name"]] = counts.get(e["name"], 0) + 1
    for name, n in counts.items():
        chips.append((f"{SFX_NAMES.get(name, name)} ×{n} (from the scene)", None))
    return chips


def build():
    lines, notes = script_lines(), scene_notes()
    acts, film_t = [], 0.0
    for a in range(6):
        shots = load(a)
        events_path = BUILD / f"act{a}_events.json"
        events = json.loads(events_path.read_text()) if events_path.exists() else []
        script = lines.get(a, [])
        spoken = [ln for ln in script if ln["text"]]
        by_line = {}
        for sh in shots:
            for v in sh.voice:
                by_line[v["line"]] = sh.id
        dirs_for = {sh.id: [] for sh in shots}
        for i, ln in enumerate(spoken):
            if not ln["directions"]:
                continue
            k = next(j for j, sh in enumerate(shots) if sh.id == by_line[i])
            # a direction before a line belongs to a silent shot in front of it, if there is one
            dirs_for[shots[k - 1].id if k and not shots[k - 1].voice else shots[k].id] += ln["directions"]
        for ln in script:
            if not ln["text"]:
                dirs_for[shots[-1].id if spoken else shots[0].id] += ln["directions"]
        out_shots = []
        for sh in shots:
            out_shots.append({
                "id": sh.id, "scene": sh.scene, "start": film_t + sh.start, "dur": sh.duration,
                "note": notes.get(sh.scene, ""),
                "lines": [spoken[v["line"]] for v in sh.voice],
                "directions": dirs_for[sh.id],
                "sound": sound_chips(sh, events),
                "stills": [still(a, sh.start + f * sh.duration) for f in STILL_AT],
            })
        length = sum(sh.duration for sh in shots)
        acts.append({"n": a, "start": film_t, "dur": length, "shots": out_shots,
                     "music": (ROOT / "music" / f"act{a}.wav").exists()})
        film_t += length
    return acts, film_t


def e(s):
    return html.escape(str(s))


def render(acts, total):
    n_shots = sum(len(a["shots"]) for a in acts)
    n_words = sum(len(ln["text"].split()) for a in acts for s in a["shots"] for ln in s["lines"])
    strip = []
    for a in acts:
        segs = "".join(
            f'<a class="seg" href="#shot-{s["id"]}" style="flex-grow:{s["dur"]}" '
            f'title="{s["id"]} · {e(s["scene"])} · {s["dur"]:.1f}s"><span>{s["id"]}</span></a>'
            for s in a["shots"])
        strip.append(f'<div class="strip-act a{a["n"]}" style="flex-grow:{a["dur"]}">'
                     f'<a class="strip-label" href="#act-{a["n"]}">{"Act " + str(a["n"]) if 0 < a["n"] < 5 else ACTS[a["n"]][0]}</a>'
                     f'<div class="segs">{segs}</div></div>')
    body = []
    for a in acts:
        title, picture, sound = ACTS[a["n"]]
        label = f"Act {a['n']}" if 0 < a["n"] < 5 else ("Opening" if a["n"] == 0 else "Ending")
        body.append(
            f'<section class="act a{a["n"]}" id="act-{a["n"]}"><header class="act-head">'
            f'<p class="eyebrow">{label} · <span class="tc">{tc(a["start"])}–{tc(a["start"] + a["dur"])}</span>'
            f' · {len(a["shots"])} shot{"s" if len(a["shots"]) != 1 else ""}</p>'
            f'<h2>{e(title)}</h2><dl class="act-meta"><div><dt>Picture</dt><dd>{e(picture)}</dd></div>'
            f'<div><dt>Sound</dt><dd>{e(sound)}{" Music track: yes." if a["music"] else ""}</dd></div></dl></header>')
        for s in a["shots"]:
            thumbs = "".join(
                f'<button type="button" class="thumb{" on" if i == 1 else ""}" data-src="{src}" '
                f'aria-label="Show still at {int(STILL_AT[i] * 100)}% of the shot"><img src="{src}" alt=""></button>'
                for i, src in enumerate(s["stills"]))
            words = []
            for d in s["directions"]:
                words.append(f'<p class="dir">{e(d)}</p>')
            for ln in s["lines"]:
                tags = "".join(f'<span class="tag">{e(t)}</span>' for t in ln["tags"])
                cls = "line sig" if ln["signature"] else "line"
                star = '<span class="star" title="Kept verbatim from the comic">★ from the comic</span>' if ln["signature"] else ""
                words.append(f'<blockquote class="{cls}">{tags}<p>{e(ln["text"])}</p>{star}</blockquote>')
            if not s["lines"]:
                words.append('<p class="silent">No narration</p>')
            chips = "".join(
                f'<li>{e(n)}{f" <span class=db>{g:+d} dB</span>" if g is not None else ""}</li>' for n, g in s["sound"])
            body.append(
                f'<article class="shot" id="shot-{s["id"]}">'
                f'<figure class="frames"><img class="main" src="{s["stills"][1]}" alt="Still from shot {s["id"]}, {e(s["scene"])}" loading="lazy">'
                f'<div class="thumbs">{thumbs}</div></figure>'
                f'<div class="info"><div class="slate"><span class="num">{s["id"]}</span>'
                f'<span class="scene">{e(s["scene"].replace("_", " "))}</span>'
                f'<span class="tc">{tc(s["start"])} · {s["dur"]:.1f}s</span></div>'
                f'{"<p class=note>" + e(s["note"]) + "</p>" if s["note"] else ""}'
                f'<div class="words">{"".join(words)}</div>'
                f'{"<ul class=sound>" + chips + "</ul>" if chips else ""}</div></article>')
        body.append("</section>")
    return (TEMPLATE.replace("{{STRIP}}", "".join(strip)).replace("{{BODY}}", "".join(body))
            .replace("{{RUNTIME}}", tc(total)[:-2]).replace("{{SHOTS}}", str(n_shots))
            .replace("{{WORDS}}", str(n_words)).replace("{{FPS}}", str(FPS)))


TEMPLATE = (pathlib.Path(__file__).with_name("storyboard.html")).read_text()   # page layout and styles


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="The storyboard page -> HTML.")
    ap.add_argument("out", nargs="?", default=str(BUILD / "storyboard.html"))
    path = ap.parse_args().out
    acts, total = build()
    with open(path, "w") as f:
        f.write(render(acts, total))
    print(path, f"{sum(len(a['shots']) for a in acts)} shots, {total:.1f} s")
