"""Where a narration recording is silent: for cutting a line between two words, and where a re-take's speech starts
and ends (rocks.shots)."""
import subprocess
from functools import lru_cache

import numpy as np

RATE, HOP, WIN = 16000, 0.005, 0.04       # analysis rate, step and window (s): a cut needs 40 ms of quiet
QUIET_DB = -45.0                          # a cut must be at least this quiet (speech is around -20 dB)
MIN_SILENCE = 0.12                        # s of quiet a pause needs: shorter dips are stop consonants ("Klingt|nett")


@lru_cache(maxsize=None)
def envelope(path):
    """RMS level in dB of the recording, every HOP seconds (window WIN)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    hop, win = int(HOP * RATE), int(WIN * RATE)
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    starts = np.arange(0, max(1, len(x) - win), hop)
    return 10 * np.log10((c[starts + win] - c[starts]) / win + 1e-12)


def quiet_cut(path, t0, t1, first=False):
    """The middle of the longest pause (at least MIN_SILENCE of quiet) between t0 and t1 s, or None.
    first=True: of the first such pause instead (right after a sentence, before a sigh that may follow it)."""
    env = envelope(path)
    a, b = max(0, int(t0 / HOP)), min(len(env), int(t1 / HOP))
    best, run = None, 0
    for i in range(a, b + 1):
        if i < b and env[i] <= QUIET_DB:
            run += 1
            continue
        if run * HOP + WIN >= MIN_SILENCE and (best is None or (run > best[1] and not first)):
            best = (i - run, run)
        run = 0
    if best is None:
        return None
    return (best[0] + best[1] / 2) * HOP + WIN / 2


def onset(path, t, back=0.25):
    """Where the sound going on at t s started, if that was at most `back` s earlier; else (a sigh or breath running
    into the word) t. The alignment puts a word's start late after a stop consonant: the K of "Klar" is before it."""
    env = envelope(path)
    i = min(int(t / HOP), len(env) - 1)
    stop = max(0, int((t - back) / HOP))
    while i > stop and env[i - 1] > QUIET_DB:
        i -= 1
    return t if i == stop else round(i * HOP, 3)


def speech_span(path):
    """(start, end) in s of the speech in a recording: from its first to its last moment above QUIET_DB (a sigh
    counts). Re-takes are played from here to there; the mix adds its own short lead-in and tail."""
    env = envelope(path)
    loud = np.nonzero(env > QUIET_DB)[0]
    if not len(loud):
        raise ValueError(f"{path}: no speech found")
    return round(float(loud[0] * HOP), 3), round(float(loud[-1] * HOP + WIN), 3)
