"""Whole-film mix (M5): one continuous audio track for all six parts, one loudness pass.

Why: mixed per act, every shot's wind had its own fade in/out, so the wind dipped at every cut and restarted
at every act boundary (user: "the wind stops between the scenes"). Here the wind is ONE bed across the film:
a continuous loop whose level follows the shots' desert_wind gains, gliding over 0.4 s at cuts and fading only
where a shot has no wind (space) or asks for a fade_out. Voice, other SFX, scene events and music come from the
per-act stems exactly as approved; music is ducked under the voice; then a single two-pass loudnorm. One mix per
narration language (config.LANGS), all on the same picture.

Usage: .venv/bin/python -m rocks.filmmix [out.mp4]      (default: film/a_bunch_of_rocks.mp4)
"""
import argparse
import pathlib
import subprocess
import numpy as np

from .config import FPS, BUILD, FILM, ROOT
from .files import atomic
from .shots import ACTS, CHAPTERS, act_starts, load, recorded_langs
from .mix import stems, write_wav, decode, sfx_clip, loudnorm_measure, loudness, SR, TARGET_I, TARGET_TP



def wind_envelope(n, spans):
    """spans: (start_s, end_s, gain_db, fade_out_s). Linear gain, smoothed so level changes glide over ~0.4 s."""
    g = np.zeros(n, np.float32)
    for a, b, db, fo in spans:
        i, j = int(a * SR), min(n, int(b * SR))
        g[i:j] = 10 ** (db / 20)
        if fo:
            k = int(fo * SR)
            g[max(i, j - k):j] *= np.linspace(1, 0, j - max(i, j - k))
    w = int(0.4 * SR)
    kernel = np.ones(w, np.float32) / w
    return np.convolve(g, kernel, mode="same")


LANG_TAGS = {"en": ("eng", "English"), "de": ("deu", "Deutsch")}     # ISO 639-2 code and track title


TITLE = "A Bunch of Rocks"
TAGS = ["-metadata", f"title={TITLE}", "-metadata", "artist=Sebastian Macke",          # what players show
        "-metadata", "comment=After xkcd #505 by Randall Munroe (CC BY-NC 2.5). https://github.com/s-macke/A-Bunch-of-Rocks"]


def chapters(path, starts, total):
    """An ffmpeg metadata file with one chapter per act (shots.CHAPTERS): players show them as chapter marks.
    YouTube ignores them and takes its chapters from the description (docs/youtube.md)."""
    ends = [starts[a + 1] if a + 1 in starts else total for a in ACTS]
    text = ";FFMETADATA1\n" + "".join(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(starts[a] * 1000)}\n"
                                       f"END={round(e * 1000)}\ntitle={CHAPTERS[a]}\n" for a, e in zip(ACTS, ends))
    pathlib.Path(path).write_text(text)
    return path


def check_video(act, length):
    """Stop if the act's rendered video no longer has the length shots.yaml gives it (picture and sound would drift)."""
    path = BUILD / f"act{act}_silent.mp4"
    if not path.exists():
        raise SystemExit(f"{path.name} is missing: render it (scripts/make_film.py --acts {act})")
    got = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(path)], check=True, capture_output=True, text=True).stdout)
    if abs(got - length) > 2 / FPS:
        raise SystemExit(f"{path.name} is {got:.2f} s, but act {act} is now {length:.2f} s long: render it again "
                         f"(scripts/make_film.py --acts {act})")


def build(out_path):
    """The film with one audio track per recorded narration language (English first, the default), and next to it each
    other language's audio on its own (<film>.<lang>.m4a: for YouTube's multi-language audio)."""
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    langs = recorded_langs()
    starts, total = act_starts()
    for a in ACTS:
        check_video(a, (starts[a + 1] if a + 1 in starts else total) - starts[a])
    n = int(round(total * SR))
    voice = {lang: np.zeros(n, np.float32) for lang in langs}
    fx, music = np.zeros(n, np.float32), np.zeros(n, np.float32)
    spans = []
    for a in ACTS:
        i = int(round(starts[a] * SR))
        for lang in langs:                       # the same effects and events in every language: the picture is one
            v, f, dur = stems(a, skip=("desert_wind",), lang=lang)
            voice[lang][i:i + len(v)] += v[: n - i]
        fx[i:i + len(f)] += f[: n - i]
        mpath = ROOT / "music" / f"act{a}.wav"
        if mpath.exists():
            m = decode(mpath)
            music[i:i + len(m)] += m[: n - i]
        for sh in load(a):
            for e in sh.sfx:
                if e["name"] == "desert_wind":
                    s0 = starts[a] + sh.start + e["at"]
                    spans.append((s0, s0 + e.get("dur", sh.duration), e.get("gain_db", 0), e.get("fade_out", 0)))
    bed = sfx_clip("desert_wind", {})
    bed = np.tile(bed, int(np.ceil(n / len(bed))))[:n]          # one continuous loop, no restarts
    fx += bed * wind_envelope(n, spans)
    write_wav(BUILD / "film_sfx.wav", fx)
    write_wav(BUILD / "film_music.wav", music)
    mixes = {}
    for lang in langs:
        paths = [BUILD / f"film_voice_{lang}.wav", BUILD / "film_sfx.wav", BUILD / "film_music.wav"]
        write_wav(paths[0], voice[lang])
        inputs = sum((["-i", str(p)] for p in paths), [])
        graph = ("[0:a]asplit=2[v][key];[2:a][key]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=500[m];"
                 "[v][1:a][m]amix=inputs=3:normalize=0")
        # one static gain to −16 LUFS (loudnorm's linear mode fell short at −17.1: the film's wide range — quiet cold
        # open, loud bang — hits the peak ceiling first), then a limiter catches the few peaks, 4x oversampled
        m = loudnorm_measure(inputs, graph)
        gain = TARGET_I - float(m["input_i"])
        ceiling = 10 ** ((TARGET_TP - 0.5) / 20)
        norm = (f",volume={gain:.2f}dB,aresample={SR * 4},alimiter=limit={ceiling:.4f}:attack=2:release=80:level=false,"
                f"aresample={SR}")
        mixes[lang] = BUILD / f"film_mix_{lang}.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph + norm, "-t", f"{total:.3f}",
                        "-c:a", "pcm_s24le", str(mixes[lang])], check=True)
    # picture: the six silent renders joined; one audio track per language, tagged, English the default
    vids = [BUILD / f"act{a}_silent.mp4" for a in ACTS]
    vin = sum((["-i", str(p)] for p in vids), []) + sum((["-i", str(mixes[lang])] for lang in langs), [])
    vin += ["-i", str(chapters(BUILD / "film_chapters.txt", starts, total))]
    vgraph = "".join(f"[{k}:v]" for k in range(len(vids))) + f"concat=n={len(vids)}:v=1:a=0[v]"
    amap, meta = [], []
    for k, lang in enumerate(langs):
        code, title = LANG_TAGS[lang]
        amap += ["-map", f"{len(vids) + k}:a"]
        meta += [f"-metadata:s:a:{k}", f"language={code}", f"-metadata:s:a:{k}", f"title={title}",
                 f"-metadata:s:a:{k}", f"handler_name={title}",          # MP4 keeps a track's name here, not in title
                 f"-disposition:a:{k}", "default" if k == 0 else "0"]
    with atomic(out_path) as tmp:                # a failed encode never leaves a broken film behind
        subprocess.run(["ffmpeg", "-y", "-v", "error", *vin, "-filter_complex", vgraph,
                        "-map", "[v]", *amap, "-map_chapters", str(len(vids) + len(langs)), "-c:v", "libx264", "-preset", "slow", "-tune", "animation",
                        "-crf", "26", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", *meta,
                        *TAGS, "-movflags", "+faststart", "-shortest", str(tmp)], check=True)   # SSIM 0.993 vs crf 18
    for lang in langs[1:]:                       # YouTube takes the first track only; the others are uploaded as dubs
        with atomic(pathlib.Path(out_path).with_suffix(f".{lang}.m4a")) as tmp:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mixes[lang]), "-c:a", "aac", "-b:a", "192k",
                            *TAGS, "-metadata", f"title={TITLE} ({LANG_TAGS[lang][1]})", str(tmp)], check=True)
    return out_path, total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="The whole film's mix and final video.")
    ap.add_argument("out", nargs="?", default=str(FILM))
    out = ap.parse_args().out
    path, total = build(out)
    I, tp = loudness(path)
    print(f"{path}  {total:.1f} s  integrated {I:.1f} LUFS, true peak {tp:.1f} dBTP")
