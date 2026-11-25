#!/usr/bin/env python3
"""B-1330 asset preparation for the Star Horse sample (one-off material
processing, NOT a standing ai_loop tool -- PIL/numpy/scipy by hand, once).

Inputs (owner-generated ChatGPT art, ~/workspace/starhorse-art/):
  title_keyvisual.png  sunset farm with horses (title backdrop)
  farm_bg.png          morning stable, no horses (farm backdrop)
  racecourse_bg.png    side-view racecourse: stand / turf / white rail
  horse_gallop.png     galloping horse + jockey on a black ground

Outputs (into this project's art/):
  title_art.jpg / farm_art.jpg / racecourse_art.jpg
      the three backdrops at 1600x900 (JPEG q88)
  race_far.jpg    racecourse rows 0..500 (sky + stand), wrap-blended
  race_turf.jpg   racecourse rows 500..800 (turf), wrap-blended
  race_rail.png   racecourse rows 765..941 with the turf keyed out,
      leaving the near white rail as a fast foreground layer
  horse_var0..7.png
      the gallop cut out (B-1324's local-texture flood: colour alone
      cannot separate the black ground from the dark lower legs, the
      texture can) and graded into eight runners: coat grading for the
      coat colours, hue replacement for the silks / cap, and the saddle
      cloth recoloured to each gate's frame colour
  shade.png       soft gradient shade for the art-led screens
  shadow.png      soft ellipse blob (horse ground shadow)
  dust.png        soft round puff (turf dust particles)

Run: python3 prep_assets.py [art_src_dir] [project_art_dir]
"""
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

SRC = sys.argv[1] if len(sys.argv) > 1 else "/home/hatch/workspace/starhorse-art"
ART = (sys.argv[2] if len(sys.argv) > 2 else
       "/home/hatch/workspace/godot-b1330/ai_loop/samples/starhorse/art")

FRAME_COLORS = ["#f5f5f5", "#26221f", "#e60012", "#0055c4",
                "#f7d117", "#009944", "#f08300", "#ee86a8"]


def save_jpg(im, name, q=88):
    im.convert("RGB").save(f"{ART}/{name}", quality=q)
    print(name, im.size)


def backdrop(src_name, out_name):
    im = Image.open(f"{SRC}/{src_name}").convert("RGB")
    im = im.resize((1600, 900), Image.LANCZOS)
    save_jpg(im, out_name)


def wrap_blend(im, blend=220):
    """Cross-fade the left/right edges so the image tiles horizontally."""
    a = np.asarray(im).astype(np.float32)
    w = a.shape[1]
    t = np.linspace(0.0, 1.0, blend, dtype=np.float32)[None, :, None]
    left = a[:, :blend]
    right = a[:, w - blend:]
    mixed = left * (1.0 - t) + right * t
    a[:, :blend] = mixed
    a[:, w - blend:] = mixed
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), im.mode)


def race_layers():
    im = Image.open(f"{SRC}/racecourse_bg.png").convert("RGB")
    far = wrap_blend(im.crop((0, 0, 1672, 500)))
    save_jpg(far, "race_far.jpg")
    turf = wrap_blend(im.crop((0, 500, 1672, 800)))
    save_jpg(turf, "race_turf.jpg")
    # Near rail: the band holds white rail + posts over saturated turf.
    # Key on green dominance: turf goes transparent, the rail stays.
    band = np.asarray(im.crop((0, 765, 1672, 941))).astype(np.float32)
    r, g, b = band[..., 0], band[..., 1], band[..., 2]
    dom = (g - np.maximum(r, b)) / 255.0  # turf ~0.25+, rail ~0
    alpha = np.clip(1.0 - (dom - 0.03) / 0.16, 0.0, 1.0)
    # The rail is bright; dim turf remnants under partial alpha go away
    # by premultiplying against the alpha curve.
    alpha = alpha * alpha * (3.0 - 2.0 * alpha)
    out = np.dstack([band.astype(np.uint8),
                     (alpha * 255).astype(np.uint8)])
    rail = Image.fromarray(out, "RGBA")
    rail.save(f"{ART}/race_rail.png")
    print("race_rail.png", rail.size, "opaque share",
          float((alpha > 0.5).mean()))


# ------------------------------------------------------------------ horse

def flood_background(rgb):
    """B-1324's separation, unchanged in spirit: the background is the
    flat, dark, edge-connected region. The horse's black-stockinged
    lower legs share the ground's colour but not its flatness."""
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


def cutout():
    im = Image.open(f"{SRC}/horse_gallop.png").convert("RGB")
    rgb = np.asarray(im)
    bg, bg_col, dist = flood_background(rgb)
    near = ndimage.binary_dilation(bg, iterations=2) & ~bg
    alpha = np.where(bg, 0.0, 1.0).astype(np.float32)
    fringe = near & (dist < 46.0)
    alpha[fringe] = np.clip((dist[fringe] - 18.0) / 28.0, 0.15, 0.85)
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
    res = res.resize((1150, int(res.height * 1150 / res.width)),
                     Image.LANCZOS)
    print("cutout", res.size, "bg share", float(bg.mean()))
    return res


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# Coat grades: (hue shift deg, sat x, val x) applied to the coat only.
COATS = [
    (0, 1.00, 1.00),    # 1 鹿毛 (the original)
    (0, 1.05, 0.70),    # 2 黒鹿毛
    (10, 1.12, 1.06),   # 3 栗毛
    (-2, 1.02, 0.88),   # 4 鹿毛・深
    (0, 0.75, 0.52),    # 5 青毛
    (0, 0.22, 1.30),    # 6 芦毛
    (14, 1.10, 0.78),   # 7 栃栗毛
    (-4, 1.05, 1.10),   # 8 鹿毛・明
]
# Silk targets per gate: (hue deg or None for keep, mode) -- the white
# diamonds stay white; only the coloured field is replaced.
SILKS = [
    (None, "white"),    # 1 白
    (None, "black"),    # 2 黒
    (0, "hue"),         # 3 赤
    (222, "hue"),       # 4 青
    (52, "hue"),        # 5 黄
    (145, "hue"),       # 6 緑
    (28, "hue"),        # 7 橙
    (330, "hue"),       # 8 桃
]


def variants(base):
    w, h = base.size
    hsv = np.asarray(base.convert("HSV")).astype(np.float32)
    rgb = np.asarray(base.convert("RGB")).astype(np.float32)
    alpha = np.asarray(base.getchannel("A")).astype(np.float32) / 255.0
    H = hsv[..., 0] * 360.0 / 255.0
    S = hsv[..., 1]
    V = hsv[..., 2]
    yy, xx = np.mgrid[0:h, 0:w]
    fx, fy = xx / w, yy / h
    solid = alpha > 0.6
    # Region + hue masks (fractions measured on the cropped sprite:
    # jockey torso upper-middle, cap above it, cloth under the saddle).
    # The silks' hue is tight (measured 327-350 deg); the coat lives at
    # 10-25 deg and its shadow at V ~33, so the band is one-sided and
    # lit-only. A binary opening then removes the per-pixel flicker the
    # textured coat would otherwise leave at any boundary.
    silks_m = solid & (fx > 0.44) & (fx < 0.70) & (fy > 0.02) & (fy < 0.38) \
        & (S > 55) & (V > 60) & (H > 322)
    silks_m = ndimage.binary_opening(silks_m, iterations=2)
    cap_m = solid & (fx > 0.60) & (fx < 0.76) & (fy < 0.16) \
        & (S > 70) & (H > 34) & (H < 66)
    cloth_m = solid & (fx > 0.42) & (fx < 0.65) & (fy > 0.30) & (fy < 0.52) \
        & (S > 45) & (H > 240) & (H < 295)
    cloth_m = ndimage.binary_opening(cloth_m, iterations=2)
    white_m = solid & (S < 46) & (V > 150)  # blaze / socks / diamonds
    coat_m = solid & ~silks_m & ~cap_m & ~cloth_m & ~white_m & (V > 60)
    print("masks: silks", int(silks_m.sum()), "cap", int(cap_m.sum()),
          "cloth", int(cloth_m.sum()), "coat", int(coat_m.sum()))
    for gate in range(8):
        hh, ss, vv = H.copy(), S.copy(), V.copy()
        dh, ds, dv = COATS[gate]
        hh[coat_m] = (hh[coat_m] + dh) % 360.0
        ss[coat_m] = np.clip(ss[coat_m] * ds, 0, 255)
        vv[coat_m] = np.clip(vv[coat_m] * dv, 0, 255)
        hue, mode = SILKS[gate]
        if mode == "hue":
            hh[silks_m] = hue
            hh[cap_m] = hue
        elif mode == "white":
            ss[silks_m] = 14
            vv[silks_m] = 205 + (vv[silks_m] - 128) * 0.35
            hh[cap_m] = 0
            ss[cap_m] = 200
        elif mode == "black":
            ss[silks_m] = 16
            vv[silks_m] = vv[silks_m] * 0.30
            ss[cap_m] = 16
            vv[cap_m] = vv[cap_m] * 0.30
        # Saddle cloth takes the gate's frame colour (hue + saturation
        # from the frame swatch, shading from the cloth itself).
        fr, fg, fb = hex_rgb(FRAME_COLORS[gate])
        fhsv = np.asarray(Image.new("RGB", (1, 1), (fr, fg, fb))
                          .convert("HSV")).astype(np.float32)[0, 0]
        hh[cloth_m] = fhsv[0] * 360.0 / 255.0
        ss[cloth_m] = max(fhsv[1], 60.0)
        out_hsv = np.dstack([hh * 255.0 / 360.0, ss, vv]).astype(np.uint8)
        out = Image.fromarray(out_hsv, "HSV").convert("RGB")
        res = Image.fromarray(
            np.dstack([np.asarray(out), np.asarray(base.getchannel("A"))]),
            "RGBA")
        res.save(f"{ART}/horse_var{gate}.png")
        print("horse_var%d.png" % gate, res.size)


def shade():
    w, h = 1152, 648
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(0, 1, w)[None, :]
    bottom = np.clip((y - 0.55) / 0.45, 0, 1) ** 1.6 * 150
    top = np.clip((0.20 - y) / 0.20, 0, 1) * 85
    left = np.clip((0.26 - x) / 0.26, 0, 1) ** 1.5 * 55
    a = np.maximum(np.maximum(bottom, top), left).astype(np.uint8)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(f"{ART}/shade.png")
    print("shade.png", (w, h))


def blob(size, name, hard=0.0):
    y, x = np.mgrid[0:size[1], 0:size[0]]
    cx, cy = size[0] / 2, size[1] / 2
    d = ((x - cx) / (size[0] / 2)) ** 2 + ((y - cy) / (size[1] / 2)) ** 2
    a = np.clip(1.0 - d, 0, 1) ** (1.6 - hard)
    rgba = np.zeros((size[1], size[0], 4), np.uint8)
    rgba[..., 3] = (a * 255).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(f"{ART}/{name}")
    print(name, size)


if __name__ == "__main__":
    backdrop("title_keyvisual.png", "title_art.jpg")
    backdrop("farm_bg.png", "farm_art.jpg")
    backdrop("racecourse_bg.png", "racecourse_art.jpg")
    race_layers()
    variants(cutout())
    shade()
    blob((256, 128), "shadow.png")
    blob((128, 128), "dust.png", hard=0.5)
