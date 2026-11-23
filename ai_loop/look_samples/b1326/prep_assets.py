#!/usr/bin/env python3
"""B-1326 asset preparation (one-off material processing, NOT a standing
ai_loop tool -- PIL/numpy/scipy/fontTools are used here only, by hand, once).

Inputs (owner-generated ChatGPT references, ~/workspace/aaa-refs/):
  ref_racing_stable.png   the stable / horse-list reference (UI included)
  ref_racing_entries.png  the race-entries reference (UI included)
  ref_sim_management.png  the management-sim reference (UI included)
  ref_asset_horse.png     a bay thoroughbred, full body, on a dark ground

The three screen references are finished pictures WITH their UI baked
in, so no clean full-frame art can be cut from them. What can be cut
honestly (the showcase's recorded compromise):
  stable_pano.jpg   the farm panorama strip that runs behind the
                    reference's own header (mountains, ranch, stable
                    block, grazing horses);
  entries_pano.jpg  the sky / grandstand strip behind the entries
                    reference's header;
  sim_map.jpg       the map's centre, reframed to 16:9 -- the one
                    genuinely clean art cut. Four of the reference's
                    baked facility labels stay visible in open ground
                    (ironworks, lumber mill, warehouse, port) and read
                    as map labels; the showcase's own labels are placed
                    on the facilities the crop leaves unlabelled.
Outputs (into the showcase project's art/):
  stable_pano.jpg / entries_pano.jpg / sim_map.jpg   as above
  horse_cut.png     the horse cut out with B-1324's texture-separation
                    flood fill (colour cannot separate the black legs
                    and mane from the dark ground; local flatness can)
  horse_face.png    the head crop of the cutout (detail portraits)
  face_0.png..7.png 96x96 row thumbnails: the face crop under mild
                    colour casts (a grey and a black coat included), so
                    eight rows do not repeat one identical face
  game_font_jp.ttf  an extended subset of Noto Sans CJK JP covering
                    every character the showcase's specs and driver
                    use (the shipped game_font.ttf is a 614-glyph
                    subset that lacks most of the data screens' kanji:
                    芝, 牡, 牝, 歳, 週, 億, 円, 枠, 騎, 厩, ...)

Run: python3 prep_assets.py [refs_dir] [project_art_dir] [repo_root]
"""
import glob
import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

REFS = sys.argv[1] if len(sys.argv) > 1 else "/home/hatch/workspace/aaa-refs"
ART = (sys.argv[2] if len(sys.argv) > 2 else
       os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "b1315", "project", "art"))
REPO = sys.argv[3] if len(sys.argv) > 3 else os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def make_panos():
    stable = Image.open(f"{REFS}/ref_racing_stable.png").convert("RGB")
    # The farm panorama between the reference's chips row and its tabs.
    pano = stable.crop((0, 95, 1672, 215))
    pano.save(f"{ART}/stable_pano.jpg", quality=88)
    print("stable_pano.jpg", pano.size)
    entries = Image.open(f"{REFS}/ref_racing_entries.png").convert("RGB")
    # Sky, mountains and the grandstand roof above the race header band.
    pano = entries.crop((0, 70, 1672, 150))
    pano.save(f"{ART}/entries_pano.jpg", quality=88)
    print("entries_pano.jpg", pano.size)


def make_sim_map():
    sim = Image.open(f"{REFS}/ref_sim_management.png").convert("RGB")
    # 16:9 centre cut: right edge stays clear of the calendar panel,
    # the task panel's remnant at the lower left lands under the
    # showcase's own task panel, the advisor bubble's tail under the
    # top resource bar, and the research lab's baked label under the
    # showcase's calendar.
    m = sim.crop((350, 170, 1374, 776)).resize((1600, 900), Image.LANCZOS)
    m.save(f"{ART}/sim_map.jpg", quality=90)
    print("sim_map.jpg", m.size)


def flood_background(rgb):
    """B-1324's separation, unchanged: the background is the set of
    pixels close to the border's dark colour, locally FLAT, and
    connected to the image edge. The horse's black legs, mane and
    tail share the ground's colour but not its flatness."""
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


def make_horse():
    im = Image.open(f"{REFS}/ref_asset_horse.png").convert("RGB")
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
    full = Image.fromarray(rgba, "RGBA")
    bbox = full.getchannel("A").getbbox()
    cut = full.crop(bbox)
    cut.save(f"{ART}/horse_cut.png")
    print("horse_cut.png", cut.size, "bg colour", bg_col,
          "bg share", float(bg.mean()))
    # The head: in the CUTOUT's frame, the alpha mass in the upper
    # left (x < 42% of the width, y < 60% of the height) is the head,
    # the neck and the mane -- the front legs share the head's columns
    # but sit below the 60% line. Boxed with a margin, it makes the
    # detail panels' portrait.
    mask = np.asarray(cut.getchannel("A")) > 100
    hh, ww = mask.shape
    sub = mask.copy()
    sub[:, int(ww * 0.42):] = False
    sub[int(hh * 0.60):, :] = False
    ys, xs = np.nonzero(sub)
    x0, x1 = max(int(xs.min()) - 12, 0), int(xs.max()) + 12
    y0, y1 = max(int(ys.min()) - 12, 0), int(ys.max()) + 12
    face = cut.crop((x0, y0, x1, y1))
    face.save(f"{ART}/horse_face.png")
    print("horse_face.png", face.size, "from", (x0, y0, x1, y1))
    return face


def make_thumbs(face):
    """96x96 row thumbnails: one face, eight coats. The casts are mild
    multiplications on the lit pixels; the grey (index 2, the white
    horse) goes through luminance, the black (index 4) is a deep
    multiply. Alpha is untouched."""
    w, h = face.size
    side = min(w, h)
    cx, cy = int(w * 0.44), int(h * 0.46)
    x0 = min(max(cx - side // 2, 0), w - side)
    y0 = min(max(cy - side // 2, 0), h - side)
    sq = face.crop((x0, y0, x0 + side, y0 + side))
    casts = [
        (1.00, 1.00, 1.00),  # 0 the bay itself
        (0.82, 0.78, 0.92),  # 1 blue-grey cast
        None,                # 2 grey coat (luminance)
        (1.08, 0.94, 0.82),  # 3 warm chestnut
        (0.40, 0.40, 0.44),  # 4 black coat
        (0.94, 0.88, 0.78),  # 5 pale bay
        (1.04, 0.88, 0.72),  # 6 red chestnut
        (0.88, 0.94, 1.00),  # 7 cool bay
    ]
    arr = np.asarray(sq).astype(np.float32)
    for i, cast in enumerate(casts):
        rgb = arr[..., :3].copy()
        if cast is None:
            lum = rgb.mean(axis=2, keepdims=True)
            rgb = np.clip(lum * 1.5 + 26, 0, 255) * np.array(
                [1.0, 0.99, 0.95], np.float32)
        else:
            rgb = np.clip(rgb * np.array(cast, np.float32), 0, 255)
        out = np.dstack([rgb.astype(np.uint8),
                         arr[..., 3].astype(np.uint8)])
        thumb = Image.fromarray(out, "RGBA").resize((96, 96), Image.LANCZOS)
        thumb.save(f"{ART}/face_{i}.png")
    print("face_0..7.png", (96, 96))


# Every string the three data screens show, so the subset below is
# complete by construction (the collector also scans the spec files
# and the driver, which carry the same strings).
EXTRA_TEXT = """
所有馬一覧 入厩馬 放牧馬 育成馬 引退馬 牧場 所有馬 出馬表 レース結果
ランキング スケジュール 所持金 日付 2027年4月3週 表示 全馬 並び替え 馬名順
年齢 性別 スピード スタミナ 調子 芝 ダート 成長型 厩舎 戦績 馬体重 仕上がり
騎手 担当 クラス 本賞金 合計 次走 目標レース 状態 良好 疲労なし 万全
絶好調 好調 普通 不調 絶不調 早熟 晩成 牡 牝 歳 サンライズエース
ミライノカゼ ホワイトオーシャン レッドヴァルキリー キングスパーク
ブルームスター シルバーグローリー ハヤテノツバサ 美浦 坂路 栗東
中山 春風ステークス 4歳以上 オープン 別定 競馬場 晴 馬場 良 枠 馬番 馬名
性齢 負担重量 オッズ 人気 青葉賞 安田記念 日本ダービー 皐月賞 桜花賞
藤原和真 佐々木蓮 高橋宗一郎 中村恵太 小林直樹 山田悠真 鈴木健吾 田村亮太
井上翔太 加藤大輔 資金 資材 木材 石材 鉄 労働力 住民 支持率 領地管理
第42週 春 2年目 今週の予定 月 火 水 木 金 土 日 評議会 市場調査 港の視察
徴税会議 王宮 農園 製鉄所 製材所 倉庫 次の週へ 建設 研究 交易 防衛 外交
タスク一覧 港の拡張工事 小麦畑の収穫 兵舎の訓練 完了 進行中 収穫する
訓練する 拡張する 調査する 食料 人口 幸福 兵舎 城塞都市
"""


def collect_chars():
    chars = set(EXTRA_TEXT)
    specs = os.path.join(REPO, "ai_loop", "look_samples", "b1315",
                         "project", "specs")
    for path in glob.glob(os.path.join(specs, "*.json")):
        with open(path, encoding="utf-8") as fh:
            chars.update(fh.read())
    proj = os.path.join(REPO, "ai_loop", "look_samples", "b1315", "project")
    for path in glob.glob(os.path.join(proj, "*.gd")):
        with open(path, encoding="utf-8") as fh:
            chars.update(fh.read())
    # Blocks: printable ASCII, kana, CJK punctuation, fullwidth forms,
    # and the symbol set the data screens use.
    for lo, hi in [(0x20, 0x7E), (0x3000, 0x303F), (0x3040, 0x30FF),
                   (0xFF00, 0xFF65)]:
        chars.update(chr(c) for c in range(lo, hi + 1))
    chars.update("◎○△×▲▼◆●▶✓＋−％：／（）「」【】・…←→↑↓")
    return "".join(sorted(c for c in chars if not c.isspace() or c == " "))


def make_font():
    from fontTools import subset
    from fontTools.ttLib import TTFont
    text = collect_chars()
    font = TTFont(NOTO, fontNumber=0)  # face 0 of the TTC is JP
    opts = subset.Options(layout_features="*", name_IDs="*",
                          notdef_outline=True, recalc_bounds=True)
    ss = subset.Subsetter(options=opts)
    ss.populate(text=text)
    ss.subset(font)
    out_path = f"{ART}/game_font_jp.ttf"
    font.save(out_path)
    cmap = font.getBestCmap()
    missing = [c for c in text if ord(c) not in cmap]
    print("game_font_jp.ttf", len(cmap), "glyphs;",
          "missing:", "".join(missing) if missing else "none")


def main():
    os.makedirs(ART, exist_ok=True)
    make_panos()
    make_sim_map()
    face = make_horse()
    make_thumbs(face)
    make_font()


if __name__ == "__main__":
    main()
