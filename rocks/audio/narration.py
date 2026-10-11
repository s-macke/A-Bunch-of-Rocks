"""Script -> per-act narration audio + per-line timings (D-22 audio-first, D-25 voice).

docs/script.md: '## Act N…' headings split acts; 'N: ' lines are spoken (with v3 audio tags);
'(beat…)' / '(long beat…)' direction lines become [pause] / [long pause].
Outputs voice/act<N>.mp3 and voice/timings.json (German, from docs/script.de.md: voice/de/…):
  {"act1": {"duration": s, "lines": [{"text": ..., "start": s, "end": s, "words": [{"w", "start", "end"}]}]}, ...}
"""
import json
import re
import shutil
import subprocess

from ..config import CALM, LANGS, ROOT, SCRIPT
from . import el, tts

VOICE = {"voice_id": "lCfIptVKzlPoj4vLmTLz", "model": "eleven_v3", "settings": {"stability": 0.5}}  # Drew, D-25
# per language: German is spoken faster (speed 1.15, about 12% shorter), so it fits the picture of the English version
SETTINGS = {"de": {"stability": 0.5, "speed": 1.15}}
TAG = re.compile(r"\[[^\]]*\]\s*")

# context for the German re-takes: the lines around them in docs/script.de.md (recorded along, cut away again)
DE_CONTEXT = {
    "1.4": {"before": "Also laufe ich. Sand. Steine. Horizont. Dann mehr Sand, mehr Steine und derselbe Horizont, der "
                      "mir offenbar folgt.",
            "after": "[pause] [sighs] Hier draußen hat man viel Zeit zum Nachdenken. Genau genommen: alle."},  # as recorded
    "1.5": {"before": "[wearily] Tja. Ich sitze in dieser Wüste fest. Für immer, soweit ich das sagen kann. "
                      "Ich weiß nicht, wie ich hergekommen bin. Ich bin eines Tages einfach hier aufgewacht. "
                      "[flatly] Ich habe nie Hunger. Nie Durst. Bin nie müde. Klingt nett, bis man merkt, dass "
                      "es hier nichts gibt, worauf man Hunger haben könnte. Also laufe ich. Sand. Steine. "
                      "Horizont. Dann mehr Sand, mehr Steine und derselbe Horizont, der mir offenbar folgt. "
                      "[dryly] Ich hab's nachgeprüft. Es geht ewig so weiter. Oder zumindest weiter als ich, und "
                      "ich gehe ewig weiter.",
            "after": "Angefangen hab ich mit dem Zählen. Dann kam die Algebra."},
    "1.6": {"before": "[sighs] Hier draußen hat man viel Zeit zum Nachdenken. Genau genommen: die ganze Zeit.",
            "after": "Ein paar tausend Jahre später hatte ich die Infinitesimalrechnung."},
    "2.8": {"before": "[flatly] Klar, Steine statt Strom, aber es ist dasselbe. Nur langsamer. [sighs] Viel langsamer. "
                      "Zwei Zahlen zu addieren dauert ungefähr eine Woche. Zu Fuß.",
            "after": "Mit genug Zeit und genug Reihen konnte ich zwei ganze Teilchen simulieren, die aneinanderstoßen."},
    "3.1": {"before": "Mit genug Zeit und genug Reihen konnte ich zwei ganze Teilchen simulieren, die aneinanderstoßen.",
            "after": "[pause] Aber ich habe unendlich viel Zeit und Platz."},
    "3.3": {"before": "[flatly] Klar, Steine statt Strom, aber es ist dasselbe. Nur langsamer. [sighs] Viel "
                      "langsamer. Zwei Zahlen zu addieren dauert ungefähr eine Woche. Zu Fuß. Also legte ich die "
                      "Physik in Steinen aus. Die echten Regeln, die ich im Sand ausgearbeitet hatte. Mit genug "
                      "Zeit und genug Reihen konnte ich zwei ganze Teilchen simulieren, die aneinanderstoßen. "
                      "[wearily] Was nicht viel ist. [pause] Aber ich habe unendlich viel Zeit und Platz.",
            "after": "[long pause] [softly, with quiet wonder] Ich beschloss… ein Universum zu simulieren."},
    "4.1": {"before": "Die Äonen rauschen vorbei, während ich eine einzige Reihe abgehe. Die Reihen rauschen vorbei, um "
                      "einen einzigen Augenblick zu berechnen. Irgendwo da drin ballten sich die Teilchen zu Sternen. "
                      "Die Sterne verglühten zu Staub, und der Staub ballte sich zu Planeten. Auf einem davon fing "
                      "etwas an, sich selbst zu kopieren. Es wurde ziemlich gut darin. Und irgendwann stand es auf, "
                      "sah sich um und fragte sich, woher das alles kommt. [long pause]",
            "after": "[pause] [sighs] Tut mir leid. Ich muss einen Stein verlegt haben."},
    "4.6": {"before": "Falls dir die Minuten in deiner Morgenvorlesung lang vorkommen…",
            "after": "[long pause] Tja. So ist das."},    # thrown away: a recording's last word gets clipped
}
for _c in DE_CONTEXT.values():
    _c["language_code"] = "de"

# single lines recorded again on their own (file in voice/ -> text, voice settings); shots.yaml plays them instead of
# the act recording (voice: take / de_take), from where the speech starts to where it ends (rocks.audio.silence)
RETAKES = {
    # 3.4: "I decided to simulate a universe." with more emotion (D-33, take a: quiet wonder)
    "act3_line3_take_a.mp3": ("[long pause] [softly, with quiet wonder] I decided… to simulate a universe.",
                              {"stability": 0.5}),
    # 4.3: "a few billion years" is our universe's age, not his: each of our instants is a row he walks
    "act4_line2_take_1.mp3": ("It happens. It's a big desert. And a few billion years is a lot of rows.",
                              VOICE["settings"]),
    # German re-takes, each recorded inside its neighbouring lines (DE_CONTEXT: spoken along, then cut away) and held
    # to German: recorded alone, a short line drifts in accent and timbre
    # 1.4: "Es" (all of it), not "Sie": the desert is not named in the line before
    "de/act1_line4_take_e.mp3": ("[dryly] Ich hab's nachgeprüft. Es geht ewig so weiter. Oder zumindest weiter als "
                                 "ich, und ich gehe ewig weiter.", VOICE["settings"], DE_CONTEXT["1.4"]),
    # 1.5: "die ganze Zeit" (all of the time, and all the time) instead of "alle", which German does not say of time;
    # recorded after the act's first lines: with only the line before it the voice drifted (Austrian, English)
    "de/act1_line5_take_c.mp3": ("[sighs] Hier draußen hat man viel Zeit zum Nachdenken. [pause] Genau genommen: "
                                 "die ganze Zeit.", VOICE["settings"], DE_CONTEXT["1.5"]),
    # 1.6: "Angefangen hab ich mit dem Zählen" says "I started with counting" the way German says it; the numbers'
    # opinions (algebra) are left out: no German phrase for them was understood
    "de/act1_line6_take_h.mp3": ("Angefangen hab ich mit dem Zählen. Dann kam die Algebra.",
                                 VOICE["settings"], DE_CONTEXT["1.6"]),
    # 2.8: "die Physik in Steinen auslegen": "ihm Physik beibringen" made the computer a pupil, but he runs it himself
    "de/act2_line8_take_a.mp3": ("Also legte ich die Physik in Steinen aus. Die echten Regeln, die ich im Sand "
                                 "ausgearbeitet hatte. Jedes Teilchen eine Kette aus Steinen. Hier. Nicht hier. Hier.",
                                 VOICE["settings"], DE_CONTEXT["2.8"]),
    # 3.1: at the calm pace (in the act recording the voice drifts on this short line)
    "de/act3_line0_take_b.mp3": ("[wearily] Was nicht viel ist.", {"stability": 0.5}, DE_CONTEXT["3.1"]),
    # 3.3: ends plainly on "zählen." so the silence before "Ich beschloss…" carries the turn; recorded after the end
    # of Act 2 and the start of Act 3: with only the line before it the voice drifted (Austrian, English)
    "de/act3_line2_take_d.mp3": ("Also fügte ich mehr Teilchen hinzu. Dann noch mehr. Irgendwann hörte ich auf zu "
                                 "zählen.", {"stability": 0.5, "speed": 0.92}, DE_CONTEXT["3.3"]),
    # 4.1: the act recording drifted here (Austrian, English); recorded after the end of Act 3
    "de/act4_line0_take_b.mp3": ("[wearily] Wenn du also jemals ein Staubkorn siehst, das einfach… verschwindet. Ein "
                                 "winziges Aufblitzen, und dann nichts.", {"stability": 0.5, "speed": 0.92},
                                 DE_CONTEXT["4.1"]),
    # 4.6, the last line: slow and heavy, there is room for it
    # "die noch vor mir liegt": "abgehen" sounded like a patrol or an exit
    "de/act4_line5_take_d.mp3": ("[pause] [sighs] …jede einzelne davon… [pause] ist eine Reihe, die noch vor mir "
                                 "liegt.", {"stability": 0.5, "speed": 0.9}, DE_CONTEXT["4.6"]),
}


def parse(path=SCRIPT):
    acts, cur = {}, None
    for line in path.read_text().splitlines():
        m = re.match(r"## Act (\d+)", line)
        if m:
            cur = f"act{m.group(1)}"
            acts[cur] = []
        elif line.startswith("## "):
            cur = None
        elif cur and line.startswith("N: "):
            acts[cur].append(line[3:].strip())
        elif cur and line.startswith("(long beat"):
            acts[cur].append("[long pause]")
        elif cur and line.startswith("(beat"):
            acts[cur].append("[pause]")
    return acts


def line_timings(parts, alignment):
    """Map each spoken part to start/end seconds via the character alignment of the joined text."""
    chars = alignment["characters"]
    starts, ends = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    text = "".join(chars)
    out, pos = [], 0
    for part in parts:
        spoken = TAG.sub("", part).strip()
        if not spoken:
            continue
        i = text.find(spoken[:20], pos)
        if i < 0:
            out.append({"text": spoken, "start": None, "end": None})
            continue
        j = min(i + len(spoken), len(ends)) - 1
        words, k = [], i
        for w in spoken.split():
            k = text.find(w, k)
            if k < 0 or k > j:
                break
            words.append({"w": w, "start": round(starts[k], 3), "end": round(ends[min(k + len(w), len(ends)) - 1], 3)})
            k += len(w)
        out.append({"text": spoken, "start": round(starts[i], 3), "end": round(ends[j], 3), "words": words})
        pos = j
    return out


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(path)]))


def synthesize(confirm=False, lang="en", calm=False):
    """Record every act of `lang`; calm=True: the calm recording at the voice's natural pace (config.CALM)."""
    script, voice_dir = LANGS[lang]
    if calm:
        voice_dir = CALM[lang]
    settings = VOICE["settings"] if calm else SETTINGS.get(lang, VOICE["settings"])
    acts = parse(script)
    voice_dir.mkdir(parents=True, exist_ok=True)
    timings = {}
    for act, parts in acts.items():
        text = " ".join(parts)
        mp3 = tts.speak(text, VOICE["voice_id"], model=VOICE["model"], settings=settings, confirm=confirm)
        dst = voice_dir / f"{act}.mp3"
        shutil.copy(mp3, dst)
        align = json.loads(mp3.with_suffix(".json").read_text())
        timings[act] = {"duration": round(duration(dst), 3), "lines": line_timings(parts, align)}
    (voice_dir / "timings.json").write_text(json.dumps(timings, indent=1, ensure_ascii=False))
    return timings


def retake_request(name):
    """(the text sent for RETAKES[name], with its context, voice settings, further request options, the line's
    context before and after it)."""
    text, settings, *more = RETAKES[name]
    opts = dict(more[0]) if more else {}
    before, after = opts.pop("before", ""), opts.pop("after", "")
    return " ".join(x for x in (before, text, after) if x), settings, opts, before, after


def record_retake(name, confirm=False):
    """Record the re-take RETAKES[name] into voice/<name>, with its alignment next to it (.json: word timings).
    A re-take with context (before/after) is recorded together with it and cut out of it: alone, a short line can
    drift in accent and timbre; inside its neighbours it sounds like the act recordings."""
    full, settings, opts, before, after = retake_request(name)
    take = tts.speak(full, VOICE["voice_id"], model=VOICE["model"], settings=settings, confirm=confirm, **opts)
    dst = ROOT / "voice" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not before and not after:
        shutil.copy(take, dst)
        shutil.copy(take.with_suffix(".json"), dst.with_suffix(".json"))
    else:
        i0 = len(before) + 1 if before else 0
        _cut_out(take, i0, i0 + len(RETAKES[name][0]), dst)
    return dst


def _cut_out(take, i0, i1, dst):
    """Cut characters i0:i1 of a recording (by its alignment) into dst (.mp3 + .json), the cuts in the pauses."""
    from .silence import quiet_cut
    a = json.loads(take.with_suffix(".json").read_text())
    chars, starts, ends = a["characters"], a["character_start_times_seconds"], a["character_end_times_seconds"]
    text = "".join(chars)
    spoken = [True] * len(text)
    for m in TAG.finditer(text):
        spoken[m.start():m.end()] = [False] * (m.end() - m.start())
    said = [k for k in range(len(text)) if spoken[k] and not text[k].isspace()]
    inside = [k for k in said if i0 <= k < i1]
    prev = [k for k in said if k < i0]
    nxt = [k for k in said if k >= i1]
    t_in, t_out = starts[inside[0]], ends[inside[-1]]
    # the alignment puts sentence boundaries only roughly: cut in the first pause from a little before the end of a
    # sentence on (a sigh or breath after the pause belongs to the next line; sighs are not in the alignment)
    t0 = (quiet_cut(take, ends[prev[-1]] - 0.2, t_in + 0.5, first=True) or (ends[prev[-1]] + t_in) / 2) if prev else 0.0
    t1 = (quiet_cut(take, t_out - 0.2, starts[nxt[0]] + 0.5, first=True) or (t_out + starts[nxt[0]]) / 2) \
        if nxt else duration(take)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(take), "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
                    "-c:a", "libmp3lame", "-q:a", "2", str(dst)], check=True)
    shift = lambda t: round(min(max(t - t0, 0.0), t1 - t0), 3)
    dst.with_suffix(".json").write_text(json.dumps({
        "characters": chars[i0:i1],
        "character_start_times_seconds": [shift(t) for t in starts[i0:i1]],
        "character_end_times_seconds": [shift(t) for t in ends[i0:i1]]}))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Record the narration of one language (cached; costs on a miss).")
    ap.add_argument("--lang", default="en", choices=list(LANGS))
    ap.add_argument("--calm", action="store_true", help="the calm recording, at the voice's natural pace")
    a = ap.parse_args()
    lang, calm = a.lang, a.calm
    est = sum(len(" ".join(p)) for p in parse(LANGS[lang][0]).values()) / 1000 * el.PRICE["tts_per_1k_chars"]
    print(f"{lang}{' calm' if calm else ''}: estimated ${est:.2f} (nothing if cached); spent before: ${el.spent():.3f}")
    t = synthesize(confirm=True, lang=lang, calm=calm)
    for act, d in t.items():
        missing = sum(1 for l in d["lines"] if l["start"] is None)
        print(f"{act}: {d['duration']:.1f}s, {len(d['lines'])} lines, unaligned: {missing}")
    print(f"spent after: ${el.spent():.3f}, requests this run: {el.requests_made}")
