#!/usr/bin/env python3
"""B-1324 asset preparation (one-off material processing, NOT a standing
ai_loop tool -- PIL/numpy/scipy are used here only, by hand, once).

Inputs (owner-generated ChatGPT references, ~/workspace/aaa-refs/):
  ref_asset_background.png  midnight library art, no UI
  ref_asset_character.png   full-body character on a near-black ground
  ref_aaa_stylish.png       the stylish title reference (eye panel crop)

Outputs (into the showcase project's art/):
  library_bg.jpg   background resized to 1600x900, JPEG q88
  chara.png        character cut out (edge flood fill + defringe), RGBA
  eye_panel.png    the eye close-up insert panel, cropped from the reference
  shade.png        soft gradient shade (bottom + left) for grounding layers
  shadow.png       soft elliptical blob shadow for the character's feet

Run: python3 prep_assets.py [refs_dir] [project_art_dir]
"""
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

REFS = sys.argv[1] if len(sys.argv) > 1 else "/home/hatch/workspace/aaa-refs"
ART = (sys.argv[2] if len(sys.argv) > 2 else
       "/home/hatch/workspace/godot-b1324/ai_loop/look_samples/b1315/project/art")


def make_background():
    im = Image.open(f"{REFS}/ref_asset_background.png").convert("RGB")
    im = im.resize((1600, 900), Image.LANCZOS)
    im.save(f"{ART}/library_bg.jpg", quality=88)
    print("library_bg.jpg", im.size)


def flood_background(rgb):
    """Mask of the background: pixels close to the border's dark colour,
    locally FLAT, and connected to the image edge (flood fill).

    Colour alone cannot separate the ground from the costume -- the
    coat's shadow and the trousers reach the ground's exact value
    (16,16,20) and are darker in places. What separates them is
    texture: the ground is a flat wash (local std ~0.3) while even the
    flattest costume shading is painterly (std >= 3). The flood only
    travels through flat, dark, ground-coloured pixels, so it stops at
    the silhouette instead of leaking into the clothes (measured:
    trousers std 3.0-18.5, glove 78, shirt 32, boots 28)."""
    border = np.concatenate([
        rgb[0, :, :], rgb[-1, :, :], rgb[:, 0, :], rgb[:, -1, :]])
    bg_col = np.median(border, axis=0)
    f = rgb.astype(np.float32)
    dist = np.sqrt(((f - bg_col) ** 2).sum(axis=2))
    lum = f.mean(axis=2)
    mean = ndimage.uniform_filter(lum, size=9)
    sq = ndimage.uniform_filter(lum * lum, size=9)
    std = np.sqrt(np.maximum(sq - mean * mean, 0.0))
    cand = (dist < 30.0) & (lum < 52.0) & (std < 2.2)
    lab, _ = ndimage.label(cand)
    edge_labels = set(np.unique(np.concatenate([
        lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(edge_labels))
    return bg, bg_col, dist


def make_character():
    im = Image.open(f"{REFS}/ref_asset_character.png").convert("RGB")
    rgb = np.asarray(im)
    bg, bg_col, dist = flood_background(rgb)
    # Feather: background pixels one step inside the silhouette keep a
    # little alpha so the edge is not a hard stair; costume pixels just
    # outside the flood whose colour is still background-like are pulled
    # in as semi-transparent fringe and decontaminated below.
    near = ndimage.binary_dilation(bg, iterations=2) & ~bg
    alpha = np.where(bg, 0.0, 1.0).astype(np.float32)
    fringe = near & (dist < 46.0)
    alpha[fringe] = np.clip((dist[fringe] - 18.0) / 28.0, 0.15, 0.85)
    # Decontaminate: un-blend the dark ground out of the fringe pixels.
    out = rgb.astype(np.float32).copy()
    a = alpha[..., None]
    sel = (alpha > 0.0) & (alpha < 1.0)
    if sel.any():
        un = (out - (1.0 - a) * bg_col) / np.maximum(a, 0.05)
        out[sel] = np.clip(un[sel], 0, 255)
    alpha_im = Image.fromarray((alpha * 255).astype(np.uint8), "L")
    alpha_im = alpha_im.filter(ImageFilter.GaussianBlur(0.7))
    rgba = np.dstack([out.astype(np.uint8), np.asarray(alpha_im)])
    res = Image.fromarray(rgba, "RGBA")
    bbox = res.getchannel("A").getbbox()
    res = res.crop(bbox)
    res.save(f"{ART}/chara.png")
    print("chara.png", res.size, "bg colour", bg_col,
          "bg share", float(bg.mean()))


def make_eye_panel():
    im = Image.open(f"{REFS}/ref_aaa_stylish.png").convert("RGB")
    # The eye close-up panel: top-left of the reference, a tilted manga
    # insert. Crop tight on the eye itself (the panel's lower-left in
    # the reference); the scene tilts the texture itself.
    crop = im.crop((24, 150, 400, 320))
    crop.save(f"{ART}/eye_panel.png")
    print("eye_panel.png", crop.size)


def make_shade():
    w, h = 1152, 648
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(0, 1, w)[None, :]
    bottom = np.clip((y - 0.52) / 0.48, 0, 1) ** 1.6 * 165
    left = np.clip((0.30 - x) / 0.30, 0, 1) ** 1.5 * 70
    top = np.clip((0.16 - y) / 0.16, 0, 1) * 60
    a = np.maximum(np.maximum(bottom, left), top).astype(np.uint8)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(f"{ART}/shade.png")
    print("shade.png", (w, h))


def make_shadow():
    w, h = 520, 130
    yy, xx = np.mgrid[0:h, 0:w]
    d = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    a = (np.clip(1 - d, 0, 1) ** 1.4 * 170).astype(np.uint8)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(f"{ART}/shadow.png")
    print("shadow.png", (w, h))


if __name__ == "__main__":
    make_background()
    make_character()
    make_eye_panel()
    make_shade()
    make_shadow()
