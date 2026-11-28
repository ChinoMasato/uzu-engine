"""B-1228 prototype: cut individual objects (the 3 moonpost houses) out of
the spec illustration using the registry bboxes as seeds.

Method: expand the bbox, estimate the background colour from the crop
border, flood-fill the background through colour-tolerant pixels, keep
the foreground components that overlap the original bbox, fill holes.
Metrics + a magenta contact sheet judge whether the cut is usable.
Local investigation script (numpy + PIL); not part of ai_loop proper.
"""

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = Path("/tmp/b1228")
OUT.mkdir(parents=True, exist_ok=True)

WORK_W = 768  # image_scene analysis resolution


def load_work():
    im = Image.open(ROOT / "spec.png").convert("RGB")
    scale = WORK_W / im.width
    return im.resize((WORK_W, round(im.height * scale)), Image.LANCZOS)


def flood_background(crop, tol):
    """Boolean mask of background pixels reachable from the crop border."""
    h, w, _ = crop.shape
    border = np.concatenate([
        crop[0, :, :], crop[-1, :, :], crop[:, 0, :], crop[:, -1, :],
    ]).astype(np.float32)
    bg = np.median(border, axis=0)
    dist = np.sqrt(((crop.astype(np.float32) - bg) ** 2).sum(axis=2))
    like_bg = dist < tol
    seen = np.zeros((h, w), dtype=bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if like_bg[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if like_bg[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and like_bg[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return seen


def components(mask):
    """Label 4-connected components; returns (labels, sizes)."""
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
    """Fill foreground holes: background components not touching the border."""
    bg = ~fg
    labels, sizes = components(bg)
    border_labels = set(np.unique(np.concatenate([
        labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1],
    ]))) - {0}
    holes = np.isin(labels, [i + 1 for i in range(len(sizes)) if (i + 1) not in border_labels])
    return fg | holes


def cut_house(work, bbox, tol, margin_ratio=0.18):
    x0, y0, x1, y1 = bbox
    mx = round((x1 - x0) * margin_ratio)
    my = round((y1 - y0) * margin_ratio)
    cx0, cy0 = max(0, x0 - mx), max(0, y0 - my)
    cx1, cy1 = min(work.width, x1 + mx), min(work.height, y1 + my)
    crop = np.asarray(work.crop((cx0, cy0, cx1, cy1)))
    bg = flood_background(crop, tol)
    fg = ~bg
    # keep components overlapping the original bbox region
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
    # metrics inside the original bbox
    inner = keep[oy0:oy1, ox0:ox1]
    fg_ratio = float(inner.mean())
    border = np.concatenate([inner[0, :], inner[-1, :], inner[:, 0], inner[:, -1]])
    border_touch = float(border.mean())
    rgba = np.dstack([crop, (keep * 255).astype(np.uint8)])
    return {
        "crop_box": (cx0, cy0, cx1, cy1),
        "fg_ratio": round(fg_ratio, 3),
        "border_touch": round(border_touch, 3),
        "components_kept_area": int(keep.sum()),
        "rgba": rgba,
    }


def main():
    work = load_work()
    elements = json.loads((ROOT / "elements.json").read_text(encoding="utf-8"))
    houses = [e for e in elements if e.get("kind") == "house"]
    results = {}
    tiles = []
    for tol in (18, 28, 40):
        for e in houses:
            r = cut_house(work, e["image_bbox"], tol)
            results[(e["id"], tol)] = {k: v for k, v in r.items() if k != "rgba"}
            if tol == 28:
                cut = Image.fromarray(r["rgba"], "RGBA")
                bg = Image.new("RGBA", cut.size, (255, 0, 255, 255))
                bg.alpha_composite(cut)
                tiles.append((e["id"], bg.convert("RGB")))
                cut.save(OUT / f"{e['id']}_cut.png")
    sheet_w = max(t.width for _, t in tiles)
    sheet = Image.new("RGB", (sheet_w, sum(t.height for _, t in tiles)), (255, 0, 255))
    y = 0
    for _, t in tiles:
        sheet.paste(t, (0, y))
        y += t.height
    sheet.save(OUT / "contact_sheet.png")
    print(json.dumps({f"{k[0]} tol={k[1]}": v for k, v in results.items()}, indent=1))
    print("sheet:", OUT / "contact_sheet.png", sheet.size)


if __name__ == "__main__":
    main()
