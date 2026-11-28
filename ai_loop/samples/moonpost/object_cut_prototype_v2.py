"""B-1228 prototype v2: object cutout via border-seeded region growing.

v1 (distance to a single border-median colour) failed: fg_ratio ~1.0 —
a rich illustration's crop border mixes sky, street and foliage, so one
median represents none of them. v2 grows the background from the crop
border through LOCALLY smooth steps only (per-step colour delta below
a threshold); strong painted outlines stop the growth. Same component
filtering, hole filling and metrics as v1. Local script (numpy + PIL).
"""

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = Path("/tmp/b1228")
OUT.mkdir(parents=True, exist_ok=True)
WORK_W = 768


def load_work():
    im = Image.open(ROOT / "spec.png").convert("RGB")
    scale = WORK_W / im.width
    return im.resize((WORK_W, round(im.height * scale)), Image.LANCZOS)


def grow_background(crop, step_tol):
    """Background = pixels reachable from the border via steps whose
    per-channel colour delta to the current pixel stays <= step_tol."""
    h, w, _ = crop.shape
    px = crop.astype(np.int16)
    seen = np.zeros((h, w), dtype=bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        c = px[y, x]
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx]:
                if int(np.abs(px[ny, nx] - c).max()) <= step_tol:
                    seen[ny, nx] = True
                    q.append((ny, nx))
    return seen


def components(mask):
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    sizes = []
    cur = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and labels[y, x] == 0:
                cur += 1
                n = 0
                q = deque([(y, x)])
                labels[y, x] = cur
                while q:
                    cy, cx = q.popleft()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and labels[ny, nx] == 0:
                            labels[ny, nx] = cur
                            q.append((ny, nx))
                sizes.append(n)
    return labels, sizes


def fill_holes(fg):
    labels, sizes = components(~fg)
    border_labels = set(np.unique(np.concatenate([
        labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1],
    ]))) - {0}
    hole_ids = [i + 1 for i in range(len(sizes)) if (i + 1) not in border_labels]
    return fg | np.isin(labels, hole_ids)


def cut_house(work, bbox, step_tol, margin_ratio=0.18):
    x0, y0, x1, y1 = bbox
    mx = round((x1 - x0) * margin_ratio)
    my = round((y1 - y0) * margin_ratio)
    cx0, cy0 = max(0, x0 - mx), max(0, y0 - my)
    cx1, cy1 = min(work.width, x1 + mx), min(work.height, y1 + my)
    crop = np.asarray(work.crop((cx0, cy0, cx1, cy1)))
    bg = grow_background(crop, step_tol)
    fg = ~bg
    ox0, oy0 = x0 - cx0, y0 - cy0
    ox1, oy1 = x1 - cx0, y1 - cy0
    labels, sizes = components(fg)
    keep = np.zeros_like(fg)
    total = crop.shape[0] * crop.shape[1]
    for i, n in enumerate(sizes):
        if n < 0.01 * total:
            continue
        comp = labels == (i + 1)
        if comp[oy0:oy1, ox0:ox1].sum() >= 0.25 * n:
            keep |= comp
    keep = fill_holes(keep)
    inner = keep[oy0:oy1, ox0:ox1]
    border = np.concatenate([inner[0, :], inner[-1, :], inner[:, 0], inner[:, -1]])
    rgba = np.dstack([crop, (keep * 255).astype(np.uint8)])
    return {
        "fg_ratio": round(float(inner.mean()), 3),
        "border_touch": round(float(border.mean()), 3),
        "rgba": rgba,
    }


def main():
    work = load_work()
    elements = json.loads((ROOT / "elements.json").read_text(encoding="utf-8"))
    houses = [e for e in elements if e.get("kind") == "house"]
    for tol in (6, 10, 14):
        tiles = []
        for e in houses:
            r = cut_house(work, e["image_bbox"], tol)
            print(f"{e['id']} step_tol={tol}: fg_ratio={r['fg_ratio']} border_touch={r['border_touch']}")
            if tol == 10:
                cut = Image.fromarray(r["rgba"], "RGBA")
                bg = Image.new("RGBA", cut.size, (255, 0, 255, 255))
                bg.alpha_composite(cut)
                tiles.append(bg.convert("RGB"))
                cut.save(OUT / f"v2_{e['id']}_cut.png")
        if tiles:
            sheet_w = max(t.width for t in tiles)
            sheet = Image.new("RGB", (sheet_w, sum(t.height for t in tiles)), (255, 0, 255))
            y = 0
            for t in tiles:
                sheet.paste(t, (0, y))
                y += t.height
            sheet.save(OUT / "v2_contact_sheet.png")
            print("sheet:", OUT / "v2_contact_sheet.png", sheet.size)


if __name__ == "__main__":
    main()
