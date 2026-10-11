"""Outputs that are written under a temporary name and get their real name only when complete.

A failed or interrupted step then never leaves a half-written video or mix behind, and a step reading the file
(rocks.filmmix reading build/act<N>_silent.mp4) always sees a whole one.
"""
import os
from contextlib import contextmanager
from pathlib import Path


def partial(path):
    """The temporary name for `path`: same folder and extension (ffmpeg picks its format from it)."""
    path = Path(path)
    return path.with_name(f".{path.stem}.partial{path.suffix}")


@contextmanager
def atomic(path):
    """with atomic(out) as tmp: write tmp; on success it replaces `out`, on any error it is removed."""
    tmp = partial(path)
    try:
        yield tmp
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
