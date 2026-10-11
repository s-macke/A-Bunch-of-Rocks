"""Render one frame of one shot to a PNG, e.g. to check a pose or a layout without rendering the act.

usage: .venv/bin/python scripts/frame.py <shot_id> <t in the shot, s> <out.png>      e.g. frame.py 2.2 4.0 frame.png
"""
import argparse

from rocks.build import still

ap = argparse.ArgumentParser(description="One frame of one shot -> PNG.")
ap.add_argument("shot", help='shot id, e.g. "2.2"')
ap.add_argument("t", type=float, help="seconds into the shot")
ap.add_argument("out", help="output .png")
a = ap.parse_args()
still(a.shot, a.t).save(a.out)
print(a.out)
