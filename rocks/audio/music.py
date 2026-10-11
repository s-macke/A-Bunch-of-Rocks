"""Music via ElevenLabs Music (D-9). Always ask the user before generating (D-21).
Note: the API rejects `seed` together with a text `prompt` (seed only works with a composition_plan)."""
import requests

from . import el

MODEL = "music_v2_5"
MOTIF = ("a slow, patient minimal motif of five repeating notes on soft felt piano and marimba, "
         "in D minor, 72 bpm, minimalist and hypnotic, interlocking repetitive arpeggios that shift very slowly")
# note: naming real artists (e.g. "in the style of <composer>") is rejected as copyrighted_material_detected


def compose(prompt, seconds, model=MODEL, confirm=False):
    payload = {"prompt": prompt, "music_length_ms": int(seconds * 1000), "model_id": model,
               "force_instrumental": True, "output_format": "mp3_48000_192"}

    def fetch(p):
        r = requests.post(f"{el.API}/v1/music", headers=el.headers(), json=p, timeout=600)
        if not r.ok:
            raise RuntimeError(f"music failed {r.status_code}: {r.text[:300]}")
        return r.content, None

    est = seconds / 60 * el.PRICE["music_per_min"]
    return el.cached_call("music", payload, est, fetch, ".mp3", confirm=confirm)


def compose_plan(plan, model=MODEL, confirm=False):
    """Section-timed composition (ElevenLabs composition_plan): each section has an exact duration_ms."""
    seconds = sum(sec["duration_ms"] for sec in plan["sections"]) / 1000
    payload = {"composition_plan": plan, "model_id": model, "output_format": "mp3_48000_192"}

    def fetch(p):
        r = requests.post(f"{el.API}/v1/music", headers=el.headers(), json=p, timeout=900)
        if not r.ok:
            raise RuntimeError(f"music (plan) failed {r.status_code}: {r.text[:400]}")
        return r.content, None

    est = seconds / 60 * el.PRICE["music_per_min"]
    return el.cached_call("music", payload, est, fetch, ".mp3", confirm=confirm)


def _sec(name, ms, pos, neg=()):
    return {"section_name": name, "positive_local_styles": list(pos), "negative_local_styles": list(neg),
            "duration_ms": ms, "lines": []}


# Act 3 timeline (shots.yaml): 3.1–3.3 0–18.5 s, 3.4 + flight + darkness 18.5–26.0 s, the bang at 26.0 s,
# galaxy to 35.0 s, eons / stars 35.0–53.3 s, life / standing up 53.3–65.5 s
ACT3_PLAN = {
    "positive_global_styles": ["instrumental", "cinematic minimalism", "soft felt piano", "marimba", "strings",
                               "warm synth pads", "D minor", "72 bpm", "hand-made, intimate"],
    "negative_global_styles": ["vocals", "lyrics", "drums", "electronic beats", "rock", "pop"],
    "sections": [
        _sec("wonder", 18500, ["the five-note motif on felt piano and marimba", "quiet", "curious",
                               "slowly adding soft pulsing strings"], ["loud"]),
        _sec("hush", 7500, ["almost silence", "one long held soft string tone", "breath held", "anticipation"],
             ["melody", "rhythm", "loud"]),
        _sec("big bang", 9000, ["sudden enormous warm orchestral bloom", "full strings and choir-like pads",
                                "awe", "vast", "shimmering"], ["drums", "percussion hits"]),
        _sec("eons and stars", 18300, ["the motif returns, flowing", "warm pulsing strings", "marimba",
                                       "time passing", "gently majestic"], ["loud"]),
        _sec("life", 12700, ["tender", "felt piano", "soft pads", "resolving slowly", "quiet ending"],
             ["loud", "abrupt ending"]),
    ],
}

CUES = {
    "act4_pad": ("barely-there ambient pad, warm and hushed, very sparse, slowly breathing, no drums, no melody, "
                 "near silence, ending on one single soft felt piano note that rings out, melancholic and gentle", 56),
    "act2_score": (MOTIF + "; begins almost silent, the motif alone on soft felt piano, very sparse; over eighty seconds "
                   "it slowly adds marimba, a gentle pulsing low string ostinato and soft pads, patiently building, "
                   "curious and wondering, never loud, no drums", 82),
    # the big bang (D-32): a dedicated majestic cue, placed on the picture's bang; the Act 3 score continues after it
    "universe_a": ("instrumental, starts immediately with one enormous majestic orchestral chord: full strings, "
                   "brass, choir and a timpani roll, in D minor opening into radiant D major, slow and vast, "
                   "awe-inspiring, triumphant but not martial, cosmic, the birth of a universe; after the peak it "
                   "settles into shimmering high strings and soft choir", 22),
    "universe_b": ("instrumental, begins at once with a huge swelling crescendo of full orchestra and wordless choir, "
                   "deep organ-like low brass underneath, shimmering harp and celesta on top, in D major, slow "
                   "60 bpm, overwhelming wonder, majestic and luminous like light filling the cosmos, then slowly "
                   "calming into warm sustained strings", 22),
    # D-32 round 2 (user: "too majestic… doesn't build up seconds before"): a build-up, then a warm bloom
    "universe_build_a": ("instrumental; begins almost silent with one high, fragile sustained string note, then a slow, "
                         "steady crescendo of strings and soft pads rising for about eight seconds, like holding one's "
                         "breath; then it opens into a warm, luminous, gentle bloom of strings, felt piano and soft "
                         "wordless choir, full of wonder and tenderness; D minor opening into D major, slow; "
                         "not triumphant, no brass, no fanfare, no drums, no percussion; ends calm", 26),
    "universe_build_b": ("instrumental; starts in near silence with a faint shimmering tremolo in high strings and a low "
                         "pad slowly swelling underneath, a gradual rising crescendo of about eight seconds full of "
                         "anticipation; at its top it blossoms into a glowing, weightless bloom of warm strings, harp "
                         "and celesta, soft and radiant like first light; D major, slow and tender; "
                         "not epic, not bombastic, no brass, no drums, no percussion", 26),
    "motif_test_sparse": (MOTIF + "; very sparse and quiet, just the motif alone, like stones being placed one by one", 30),
    "motif_test_swell": (MOTIF + "; the same motif growing into a full, awe-struck swell with strings, choir pads and "
                         "warm synths, cosmic and vast", 30),
}

if __name__ == "__main__":
    import argparse
    import shutil
    from ..config import ROOT
    ap = argparse.ArgumentParser(description="Compose music cues -> music/<name>.mp3 (cached; costs on a miss).")
    ap.add_argument("names", nargs="*", help=f"cues to compose (default: all of {', '.join(CUES)})")
    (ROOT / "music").mkdir(exist_ok=True)
    for name in ap.parse_args().names or CUES:
        prompt, sec = CUES[name]
        p = compose(prompt, sec)
        shutil.copy(p, ROOT / "music" / f"{name}.mp3")
        print(name, p.name)
    print(f"spent: ${el.spent():.3f}, requests: {el.requests_made}")
