"""Rebuild the music each act uses (music/act<N>.wav) from the generated sources in music/*.mp3.

The steps and levels are the ones chosen while making the film (D-9, D-32). Levels are set relative to each act's
voice stem, so run this after `python -m rocks.build <act>` and before `python -m rocks.filmmix` (make_film.py does).
Acts 0 and 1 have no music.

usage: .venv/bin/python scripts/make_music.py
"""
import numpy as np

from rocks.config import ROOT
from rocks.mix import SR, decode, edge_fade, lufs, prepare_music, write_wav
from rocks.shots import load

MUSIC = ROOT / "music"

# Landmarks measured by ear and by level in the original generations (music/act3_score.mp3 and
# music/universe_build_a.mp3). A newly generated score or cue has its own, so measure and set these again.
SCORE_HUSH_END = 33.34        # s in the score: its natural hush ends and its own swell starts (−48 → −11 dB)
BUILD_SEARCH = (8.0, 12.0)    # s in the build-up cue: where to look for its arrival (the steepest rise)
BOOKEND_BEFORE_LIFE = 1.4     # s before shot "life" starts: the score's opening motif returns as a bookend for it
BANG_IN_SHOT = 4.0            # s into shot big_bang: the bang (rocks/scenes/act3.py big_bang)


def act3_edit(cue="universe_build_a"):
    """Cut the Act 3 score to the picture and lay the chosen big-bang cue over it -> music/act3_edit.wav.

    The music model did not follow the score's section timings, so the score is cut by hand:
      start – bang−9 s   the score as is (wonder), giving way to the build-up cue
      ~bang−9.7 – bang   the cue builds, its arrival lands exactly on the picture's bang (D-32)
      bang – bang+14 s   the cue's warm bloom; from bang+11 s the score returns, after its own hush,
                         for the eons and the stars
      54.5 s – end       the score's quiet opening motif again, fading out with the picture
    """
    src = decode(MUSIC / "act3_score.mp3")
    shots = load(3)
    total = shots[-1].start + shots[-1].duration
    n = int(total * SR)
    t = np.arange(n) / SR
    bang = next(sh.start for sh in shots if sh.scene == "big_bang") + BANG_IN_SHOT
    bookend_at = next(sh.start for sh in shots if sh.scene == "life") - BOOKEND_BEFORE_LIFE

    def take(src_start_s, length):
        a = int(src_start_s * SR)
        seg = src[max(0, a):a + length]
        return np.pad(seg, (0, length - len(seg)))

    def ramp(t0, t1):
        return np.clip((t - t0) / (t1 - t0), 0, 1)

    main = take(0, n)                                            # the score as generated
    shifted = take(SCORE_HUSH_END - bang, n)                     # the score moved so its swell starts on the bang
    bookend = np.zeros(n, np.float32)
    b0 = int(bookend_at * SR)
    bookend[b0:] = take(0, n - b0)
    w_book = ramp(bookend_at, bookend_at + 2) * (1 - ramp(total - 4.0, total))

    uni = decode(MUSIC / f"{cue}.mp3")
    uni *= 10 ** ((lufs(MUSIC / "act3_score.mp3") - lufs(MUSIC / f"{cue}.mp3")) / 20)   # level with the score
    win = int(0.05 * SR)
    lo, hi = int(BUILD_SEARCH[0] * SR), int(BUILD_SEARCH[1] * SR)
    env = np.array([np.sqrt(np.mean(uni[i:i + win] ** 2)) for i in range(lo, hi, win)])
    arrive = (lo + (np.argmax(np.diff(20 * np.log10(env + 1e-9))) + 1) * win) / SR
    start = bang - arrive
    seg = np.zeros(n, np.float32)
    i0 = int(start * SR)
    seg[i0:i0 + len(uni)] = uni[: n - i0]
    w_uni = ramp(start, start + 0.5) * (1 - ramp(bang + 11, bang + 14))
    w_main = 1 - ramp(bang - 9, bang - 5)                       # the score yields to the build
    w_after = ramp(bang + 11, bang + 14)                         # and returns for the eons
    out = main * w_main + shifted * w_after + seg * w_uni + bookend * w_book * 1.4
    print(f"{cue}: arrival at {arrive:.2f} s of the cue -> cue starts at {start:.2f} s, bang at {bang:.2f} s")
    path = MUSIC / "act3_edit.wav"
    write_wav(path, out)
    return path


if __name__ == "__main__":
    # Act 2: the motif score, sparse and slowly growing, 14 LU under the voice
    prepare_music(2, MUSIC / "act2_score.mp3", below_voice_lu=14, align="start", fade_in=1.5, fade_out=2.5, stretch=True)
    # Act 3: the score cut to the picture, with the build-up cue landing on the bang
    prepare_music(3, act3_edit(), below_voice_lu=11, align="start", fade_in=1.0, fade_out=0.5)
    # Act 4: a faint pad, barely there, 20 LU under the voice; its final note lands on the act's end
    prepare_music(4, MUSIC / "act4_pad.mp3", below_voice_lu=20, align="end", fade_in=2.5, fade_out=0.0)
    # Credits: the last 15 s of the Act 2 score, at the level the Act 2 mix uses for it
    tail = decode(MUSIC / "act2_score.mp3")[-15 * SR:] * 10 ** (-13.5 / 20)
    write_wav(MUSIC / "act5.wav", edge_fade(tail, 1.5, 3.5))
    print("music/act2.wav … act5.wav rebuilt")
