"""Build an act: render shots -> silent video (+ contact sheet); audio and mux live in rocks/mix.py.

Usage: .venv/bin/python -m rocks.build <act> [--stills]
"""
import argparse
import importlib
import json
import time
from PIL import Image

from .config import FPS, BUILD, W, H, boil_at
from .render import Film, stage_canvas, stage_surface
from .shots import load
from .scenes.common import Ctx


def scenes_for(act):
    return importlib.import_module(f"rocks.scenes.act{act}").SCENES


def act_of(shot_id):
    """The act a shot belongs to: shot "2.8" is in act 2."""
    return int(shot_id.split(".")[0])


def shot_drawer(shot_id, scene=None, ctx=None, lang="en"):
    """(shot, draw) for one shot; `scene` swaps in another scene function by name, for tests. `lang` only changes
    the voice placements in shot (the picture is the same in every language)."""
    act = act_of(shot_id)
    shot = next((s for s in load(act, lang) if s.id == shot_id), None)
    if shot is None:
        raise SystemExit(f"act {act} has no shot {shot_id}")
    return shot, scenes_for(act)[scene or shot.scene](ctx or Ctx(), shot)


def still(shot_id, t, over=None):
    """One frame of a shot at t s into it, as in the film (same line boil), as an RGB image at the output size.
    over(canvas): draws on top in stage coordinates (e.g. a title)."""
    shot, draw = shot_drawer(shot_id)
    surface = stage_surface()
    c = stage_canvas(surface)
    draw(c, t, boil_at(round((shot.start + t) * FPS)))
    if over:
        over(c)
    return Image.fromarray(surface.makeImageSnapshot().toarray()[..., :3])


def render_act(act, stills=True):
    shots = load(act)
    ctx = Ctx()
    registry = scenes_for(act)
    path = BUILD / f"act{act}_silent.mp4"
    sheet = []
    events = []            # sound events reported by scenes: {"name", "at" (act time), "gain_db"}
    t0 = time.perf_counter()
    total = shots[-1].start + shots[-1].duration
    with Film(path) as film:
        i, draw, still_taken = -1, None, True
        for k in range(int(round(total * FPS))):        # frames follow the act's clock, so cuts never drift
            t = k / FPS
            while i + 1 < len(shots) and t >= shots[i + 1].start - 1e-6:
                i += 1
                shot = shots[i]
                draw = registry[shot.scene](ctx, shot)
                for e in getattr(draw, "events", []):
                    events.append({**e, "at": round(shot.start + e["at"], 3)})
                still_taken = not stills
            c = film.canvas()
            draw(c, t - shot.start, boil_at(k))
            arr = film.frame()
            if not still_taken and t >= shot.start + shot.duration / 2:
                sheet.append((shot.id, arr[..., :3].copy()))
                still_taken = True
    (BUILD / f"act{act}_events.json").write_text(json.dumps(events, indent=1))
    if stills:
        cols = 3
        rows = (len(sheet) + cols - 1) // cols
        tw, th = W // 3, H // 3
        img = Image.new("RGB", (tw * cols, th * rows), "white")
        for i, (sid, arr) in enumerate(sheet):
            img.paste(Image.fromarray(arr).resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
        img.save(BUILD / f"act{act}_sheet.png")
    return path, f"{film.stats()}, wall {time.perf_counter() - t0:.1f}s"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("act", type=int)
    ap.add_argument("--no-stills", action="store_true")
    a = ap.parse_args()
    print(*render_act(a.act, stills=not a.no_stills))
