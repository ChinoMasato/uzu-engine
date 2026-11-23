#!/usr/bin/env python3
"""B-1326: side-by-sides of the ChatGPT references (left) and the data
screens built from them (right), same height, labelled.

Run: python3 make_compare.py [out_dir]
Reads the stills next to this script (racing_stable.png,
racing_entries.png, sim_main.png) and the references in
~/workspace/aaa-refs/.
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = "/home/hatch/workspace/aaa-refs"
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else HERE
H = 648

PAIRS = [
    ("ref_racing_stable.png", "racing_stable.png", "compare_stable.png",
     "REFERENCE -- ChatGPT racing stable (the target)",
     "B-1326 -- stable screen in U.ZU Engine (kit data parts)"),
    ("ref_racing_entries.png", "racing_entries.png", "compare_entries.png",
     "REFERENCE -- ChatGPT race entries (the target)",
     "B-1326 -- entries screen in U.ZU Engine (kit data parts)"),
    ("ref_sim_management.png", "sim_main.png", "compare_sim.png",
     "REFERENCE -- ChatGPT management sim (the target)",
     "B-1326 -- sim main screen in U.ZU Engine (kit data parts)"),
]

for ref_name, shot_name, out_name, ref_label, shot_label in PAIRS:
    ref = Image.open(os.path.join(REFS, ref_name)).convert("RGB")
    ref = ref.resize((1152, H))
    shot = Image.open(os.path.join(HERE, shot_name)).convert("RGB")
    shot = shot.resize((1152, H))
    canvas = Image.new("RGB", (1152 * 2 + 8, H + 28), (24, 24, 28))
    canvas.paste(ref, (0, 28))
    canvas.paste(shot, (1160, 28))
    d = ImageDraw.Draw(canvas)
    d.text((10, 7), ref_label, fill=(255, 255, 255))
    d.text((1170, 7), shot_label, fill=(255, 255, 255))
    out = os.path.join(OUT_DIR, out_name)
    canvas.save(out)
    print("wrote", out, canvas.size)
