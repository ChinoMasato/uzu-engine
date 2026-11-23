#!/usr/bin/env python3
"""B-1325 asset preparation (one-off material processing, NOT a standing
ai_loop tool -- PIL is used here only, by hand, once).

The four new art-driven persona screens reuse B-1324's two source
assets (the midnight-library art and the cut-out character). To keep
the reuse from reading as reuse, each screen gets its own window into
the library and its own colour grade, baked here:

Inputs:
  ~/workspace/aaa-refs/ref_asset_background.png  (1672x941, the library)
  project/art/chara.png                          (1000x1514, B-1324 cut-out)

Outputs (into the showcase project's art/):
  bg_menu.jpg      right window: staircase + moon window, cooler/darker
  bg_settings.jpg  left window: desk, globe and lamp, warm and dim
  bg_talk.jpg      centre window: shelves and hanging lanterns, contrast up
  bg_hud.jpg       the full frame, muted toward a gameplay view
  chara_bust.png   upper-body crop of the character (the talk portrait)

Run: python3 prep_assets.py [refs_dir] [project_art_dir]
"""
import sys

import numpy as np
from PIL import Image, ImageEnhance

REFS = sys.argv[1] if len(sys.argv) > 1 else "/home/hatch/workspace/aaa-refs"
ART = (sys.argv[2] if len(sys.argv) > 2 else
       "/home/hatch/workspace/godot-b1325/ai_loop/look_samples/b1315/project/art")

OUT_SIZE = (1600, 900)


def grade(im, brightness=1.0, color=1.0, contrast=1.0, channels=(1.0, 1.0, 1.0)):
    im = ImageEnhance.Brightness(im).enhance(brightness)
    im = ImageEnhance.Color(im).enhance(color)
    im = ImageEnhance.Contrast(im).enhance(contrast)
    if channels != (1.0, 1.0, 1.0):
        arr = np.asarray(im).astype(np.float32)
        arr *= np.array(channels, dtype=np.float32)[None, None, :]
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return im


def window(im, cx, cy, width):
    """A 16:9 crop of the source, centred at (cx, cy) as fractions."""
    w, h = im.size
    cw = int(w * width)
    ch = int(cw * 9 / 16)
    x = int(min(max(cx * w - cw / 2, 0), w - cw))
    y = int(min(max(cy * h - ch / 2, 0), h - ch))
    return im.crop((x, y, x + cw, y + ch))


def save_bg(im, name):
    im = im.resize(OUT_SIZE, Image.LANCZOS)
    im.save(f"{ART}/{name}", quality=88)
    print(name, im.size)


def make_backgrounds():
    src = Image.open(f"{REFS}/ref_asset_background.png").convert("RGB")
    # Menu: the staircase and the moon window -- the far corner of the
    # same room the title showed whole. Cooler and darker: a pause
    # screen sits quieter than a title.
    save_bg(grade(window(src, 0.70, 0.46, 0.60),
                  brightness=0.84, color=0.95, contrast=1.05,
                  channels=(0.96, 1.0, 1.06)), "bg_menu.jpg")
    # Settings: the desk with the armillary sphere and the lamp --
    # warm and dim, so the panel's text keeps its contrast.
    save_bg(grade(window(src, 0.30, 0.52, 0.60),
                  brightness=0.72, color=1.0, contrast=1.03,
                  channels=(1.05, 1.0, 0.94)), "bg_settings.jpg")
    # Talk: the shelves and hanging lanterns behind the speaker --
    # a touch more contrast so the portrait separates from it.
    save_bg(grade(window(src, 0.48, 0.40, 0.66),
                  brightness=0.80, color=0.97, contrast=1.08,
                  channels=(1.0, 0.99, 1.02)), "bg_talk.jpg")
    # HUD: the whole room again (the player is *in* the title's room),
    # muted toward gameplay: less saturation, a shade darker.
    save_bg(grade(src.copy(),
                  brightness=0.90, color=0.90, contrast=1.04,
                  channels=(0.99, 1.01, 1.03)), "bg_hud.jpg")


def make_bust():
    im = Image.open(f"{ART}/chara.png")  # RGBA, 1000x1514
    # Upper body: head, the reaching hand, torso and belt. The crop
    # keeps the full width so the coat's red lining stays in frame.
    bust = im.crop((0, 0, im.width, 900))
    bbox = bust.getchannel("A").getbbox()
    bust = bust.crop(bbox)
    bust.save(f"{ART}/chara_bust.png")
    print("chara_bust.png", bust.size)


if __name__ == "__main__":
    make_backgrounds()
    make_bust()
