"""Audio for an act: voice + SFX stems placed sample-accurately (numpy), then ffmpeg ducks music under
the voice (sidechaincompress, AC-11) and normalises to -16 LUFS / -1 dBTP (two-pass loudnorm, AC-10).

Usage: .venv/bin/python -m rocks.mix <act>   (expects build/act<N>_silent.mp4 from rocks.build)
"""
import argparse
import json
import subprocess
import numpy as np

from .config import LANGS, ROOT, BUILD
from .shots import load
from .audio import sfx as sfx_lib

SR = 48000
TARGET_I, TARGET_TP, TARGET_LRA = -16.0, -1.5, 11.0   # -1.5 leaves headroom for AAC overshoot (AC-10 limit is -1)


def decode(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def write_wav(path, x):
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                          "-c:a", "pcm_s24le", str(path)], stdin=subprocess.PIPE)
    p.communicate(x.astype(np.float32).tobytes())


def place(buf, clip, at):
    i = int(round(at * SR))
    j = min(len(buf), i + len(clip))
    if j > i:
        buf[i:j] += clip[: j - i]


def edge_fade(x, fin=0.01, fout=0.03):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b and len(x) > b:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def lufs(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(err[err.rindex("Summary:"):].split("I:")[1].split("LUFS")[0])



SFX_REF_LUFS = -30.0      # every effect is brought to this loudness first; shots.yaml gains are relative to it


# some effects are layers of several generated sounds: (name, relative dB)
COMPOSITES = {
    "desert_wind": [("wind_gusts", -3.0), ("wind_howl", 0.0)],   # user pick: low rumble + rising/falling gusts
}


def sfx_clip(name, cache):
    """Decoded SFX normalised to SFX_REF_LUFS (the generated files differ by >30 dB: wind −57, clock −24)."""
    if name not in cache:
        if name in COMPOSITES:
            parts = [sfx_clip(p, cache) * 10 ** (g / 20) for p, g in COMPOSITES[name]]
            m = min(len(x) for x in parts)
            x = sum(x[:m] for x in parts)
            tmp = BUILD / f"_sfx_{name}.wav"
            write_wav(tmp, x)
            cache[name] = x * 10 ** ((SFX_REF_LUFS - lufs(tmp)) / 20)
        else:
            path = sfx_lib.get(name)
            cache[name] = decode(path) * 10 ** ((SFX_REF_LUFS - lufs(path)) / 20)
    return cache[name]


def act_voice(act, lang="en"):
    """(path, decoded samples) of an act's narration recording; silence for the acts without narration."""
    vpath = LANGS[lang][1] / f"act{act}.mp3"
    return vpath, decode(vpath) if vpath.exists() else np.zeros(1, np.float32)


def place_shot(voice, fx, sh, t0, act_voice, cache, skip=()):
    """Add one shot's voice lines and sound effects to the voice and fx buffers, with the shot starting at t0 s."""
    vpath, src = act_voice
    for v in sh.voice:
        if "take" in v:                     # a re-take or the calm recording, at the act recording's loudness
            key = ("take", v["take"])
            if key not in cache:
                t_ = decode(ROOT / v["take"])
                cache[key] = t_ * 10 ** ((lufs(vpath) - lufs(ROOT / v["take"])) / 20) if vpath.exists() else t_
            s_ = cache[key]
        else:
            s_ = src
        pre, post = v.get("pre", 0.06), v.get("post", 0.25)    # a line split in two: no overlap at the cut
        a = max(0, int((v["src_start"] - pre) * SR))
        b = int((v["src_end"] + post) * SR)
        place(voice, edge_fade(s_[a:b], 0.02 if pre else 0.005, 0.12 if post else 0.005), t0 + v["at"] - pre)
    for e in sh.sfx:
        if e["name"] in skip:                 # handled elsewhere (e.g. the film-wide wind bed)
            continue
        clip = sfx_clip(e["name"], cache)
        if "dur" in e:
            reps = int(np.ceil(e["dur"] * SR / len(clip)))
            clip = np.tile(clip, reps)[: int(e["dur"] * SR)]
        clip = clip * 10 ** (e.get("gain_db", 0) / 20)
        clip = edge_fade(clip, 0.3 if "dur" in e else 0.005, e.get("fade_out", 0.3 if "dur" in e else 0.02))
        times = [e["at"]]
        if "every" in e:
            times = list(np.arange(e["at"], e.get("until", sh.duration), e["every"]))
        for t in times:
            place(fx, clip, t0 + t)


def place_events(fx, events, cache, t0=0.0):
    """Add the sound events a scene reported while rendering (clicks, footsteps), at t0 + their time."""
    for e in events:
        place(fx, edge_fade(sfx_clip(e["name"], cache) * 10 ** (e.get("gain_db", 0) / 20), 0.005, 0.02), t0 + e["at"])


def stems(act, skip=(), lang="en"):
    """(voice, fx, length in s) of one act: every shot's voice and sound effects, plus the scenes' events."""
    shots = load(act, lang)
    total = shots[-1].start + shots[-1].duration
    n = int(round(total * SR))
    voice, fx = np.zeros(n, np.float32), np.zeros(n, np.float32)
    av, cache = act_voice(act, lang), {}
    for sh in shots:
        place_shot(voice, fx, sh, sh.start, av, cache, skip)
    ev_path = BUILD / f"act{act}_events.json"          # events reported by scenes at render time
    place_events(fx, json.loads(ev_path.read_text()) if ev_path.exists() else [], cache)
    return voice, fx, total


def prepare_music(act, src, below_voice_lu, align="start", fade_in=2.0, fade_out=3.0, stretch=False):
    """Level a music file relative to the act's voice stem, fit it to the act length -> music/act<N>.wav.
    align="end" keeps the music's ending (e.g. a final note) at the end of the act. stretch=True: music shorter
    than the act is slowed down to fill it (rubberband, pitch kept; the act grew for the German narration)."""
    shots = load(act)
    total = shots[-1].start + shots[-1].duration
    voice_wav = BUILD / f"act{act}_voice.wav"
    if not voice_wav.exists():
        v, _, _ = stems(act)
        write_wav(voice_wav, v)
    gain = 10 ** (((lufs(voice_wav) - below_voice_lu) - lufs(src)) / 20)
    x = decode(src) * gain
    n = int(round(total * SR))
    if stretch and len(x) < n:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-af", f"rubberband=tempo={len(x) / n:.6f}",
                              "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], check=True, capture_output=True).stdout
        x = np.frombuffer(raw, np.float32).copy() * gain
    if align == "end":
        x = x[len(x) - n:] if len(x) > n else np.pad(x, (n - len(x), 0))
    else:
        x = x[:n] if len(x) > n else np.pad(x, (0, n - len(x)))
    return_path = ROOT / "music" / f"act{act}.wav"
    write_wav(return_path, edge_fade(x, fade_in, fade_out))
    return return_path, 20 * np.log10(gain)


def loudnorm_measure(inputs, graph):
    out = subprocess.run(["ffmpeg", "-hide_banner", *inputs, "-filter_complex",
                          graph + f",loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    return json.loads(out[out.rindex("{"): out.rindex("}") + 1])


def build(act):
    voice, fx, total = stems(act)
    vw, fw = BUILD / f"act{act}_voice.wav", BUILD / f"act{act}_sfx.wav"
    write_wav(vw, voice)
    write_wav(fw, fx)
    music = ROOT / "music" / f"act{act}.wav"
    inputs = ["-i", str(vw), "-i", str(fw)]
    if music.exists():
        inputs += ["-i", str(music)]
        graph = ("[0:a]asplit=2[v][key];[2:a][key]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=500[m];"
                 "[v][1:a][m]amix=inputs=3:normalize=0")
    else:
        graph = "[0:a][1:a]amix=inputs=2:normalize=0"
    gain_file = BUILD / f"act{act}_gain.json"
    if voice.any():
        m = loudnorm_measure(inputs, graph)
        norm = (f",loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:measured_I={m['input_i']}:"
                f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
                f"offset={m['target_offset']}:linear=true,aresample={SR}")
        gain_file.write_text(json.dumps({"gain_db": TARGET_I - float(m["input_i"])}))
    else:
        # no narration (cold open, credits): same gain as the neighbouring act, so levels match across the cut
        ref = {0: 1, 5: 4}[act]
        g = json.loads((BUILD / f"act{ref}_gain.json").read_text())["gain_db"]
        norm = f",volume={g:.2f}dB,alimiter=limit={10 ** (TARGET_TP / 20):.3f}:level=false,aresample={SR}"
    mixed = BUILD / f"act{act}_mix.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph + norm, "-t", f"{total:.3f}",
                    "-c:a", "pcm_s24le", str(mixed)], check=True)
    final = BUILD / f"act{act}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(BUILD / f"act{act}_silent.mp4"), "-i", str(mixed),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    str(final)], check=True)
    return final, music.exists()


def loudness(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    tail = err[err.rindex("Summary:"):]
    I = float(tail.split("I:")[1].split("LUFS")[0])
    peak = float(tail.split("Peak:")[1].split("dBFS")[0])
    return I, peak


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("act", type=int)
    a = ap.parse_args()
    final, has_music = build(a.act)
    I, tp = loudness(final)
    print(f"{final}  music: {has_music}  integrated {I:.1f} LUFS, true peak {tp:.1f} dBTP")
