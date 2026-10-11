# Experiments

Standalone scripts from the first evening, kept for the making-of. They don't use the `rocks` package and are not
part of building the film.

- `style_samples.py` renders the same key frame in four candidate looks (sketchbook, Moebius, chalk, paper cut-out),
  with numpy and Pillow only. The sketchbook look won. This renderer took 124 s per frame: far too slow for a film.
- `spike_skia.py` renders a 4 s test shot of the sketchbook look with skia over cached watercolor plates, at 12 fps:
  about 0.19 s per frame. Its result decided the renderer the film uses.

usage: `.venv/bin/python scripts/experiments/<script> <out_dir>`
