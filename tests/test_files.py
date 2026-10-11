"""rocks.files: an output gets its real name only when it is complete."""
import pytest

from rocks.files import atomic, partial


def test_atomic_replaces_only_on_success(tmp_path):
    out = tmp_path / "film.mp4"
    out.write_text("old")
    with atomic(out) as tmp:
        assert tmp == partial(out) and tmp.suffix == ".mp4"
        tmp.write_text("new")
    assert out.read_text() == "new" and not partial(out).exists()

    with pytest.raises(RuntimeError):
        with atomic(out) as tmp:
            tmp.write_text("half")
            raise RuntimeError("encode failed")
    assert out.read_text() == "new" and not partial(out).exists()
