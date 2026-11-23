#!/usr/bin/env python3
"""B-1324: side-by-side of the ChatGPT stylish reference (left) and the
art-driven title built from its assets (right), same height, labelled.

Run: python3 make_compare.py [title.png] [out.png]
"""
import sys

from PIL import Image, ImageDraw

REF = "/home/hatch/workspace/aaa-refs/ref_aaa_stylish.png"
TITLE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/art_title_final.png"
OUT = (sys.argv[2] if len(sys.argv) > 2 else
       "/home/hatch/workspace/godot-b1324/ai_loop/look_samples/b1324/compare_stylish.png")
H = 648

ref = Image.open(REF).convert("RGB").resize((1152, H))
title = Image.open(TITLE).convert("RGB").resize((1152, H))
canvas = Image.new("RGB", (1152 * 2 + 8, H + 28), (24, 24, 28))
canvas.paste(ref, (0, 28))
canvas.paste(title, (1160, 28))
d = ImageDraw.Draw(canvas)
d.text((10, 7), "REFERENCE -- ChatGPT AAA image (the target)", fill=(255, 255, 255))
d.text((1170, 7), "B-1324 -- art-driven title in U.ZU Engine (live UI on art)", fill=(255, 255, 255))
canvas.save(OUT)
print("wrote", OUT, canvas.size)
