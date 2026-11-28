#!/usr/bin/env python3
"""Image-first scene scaffold (BACKLOG B-1221): one specification illustration
in, a walkable scene scaffold out.

The illustration is the spec (BRIEFING: the image-first flow). This module
analyses it in pure Python (standard library only, PNG in / PNG out) and
produces a B-1207 declarative build spec plus a generation report:

  * the illustration itself becomes a full-bleed backdrop card,
  * foreground / midground elements are cut out as alpha cards and placed
    at depths derived from a depth proxy, so walking gives parallax,
  * the ground strip below the horizon becomes the walkable area, with a
    ground colour sampled from the illustration,
  * bright blobs and tall ground-standing shapes come back as *candidate*
    interact points, and ground-standing cards as *candidate* collisions.

Everything derived here is a candidate, never a fact: following the B-1509
convention, each derived item carries "basis": "inferred" (with the reason),
and only what was actually measured from the image file (its size, the
sampled colours, a depth map the caller supplied) is "observed".

Depth: an external estimator's map can be passed with depth_path (B-903
keeps models outside the engine, Q13); without one, a heuristic proxy is
used (image height dominates: higher in the picture is farther, tempered by
local detail) and the report says so. The layering is a scaffold to grow
from -- the spec is plain JSON the agent edits and rebuilds (B-1207).

Public entry: analyze(image_path, options) -> (spec, report, assets) where
assets maps file names to PNG bytes to write next to the spec. The CLI
wiring lives in ai_loop/uzu.py ("image-scene").
"""

import heapq
import math
import struct
import zlib
from array import array

from image_diff import read_png

WORK_MAX_W = 768  # Analysis resolution cap; card textures keep this detail.
MIN_COMPONENT_SHARE = 0.0015  # Smallest kept cut-out, as a share of the image.
MAX_CARDS_PER_BAND = 8
MAX_GLOW = 6


# ---------------------------------------------------------------- PNG out


def write_png(path, width, height, rgba):
    """Write an RGBA buffer as a PNG file (see write_png_bytes)."""
    with open(path, "wb") as f:
        f.write(write_png_bytes(width, height, rgba))


def load_rgba(path):
    """(width, height, bytearray RGBA) from an 8-bit RGB/RGBA PNG."""
    w, h, channels, rows = read_png(path)
    out = bytearray(w * h * 4)
    for y in range(h):
        row = rows[y]
        base = y * w * 4
        if channels == 4:
            out[base:base + w * 4] = row[:w * 4]
        else:
            for x in range(w):
                o, i = base + x * 4, x * 3
                out[o:o + 3] = row[i:i + 3]
                out[o + 3] = 255
    return w, h, out


def downscale(w, h, rgba, max_w=WORK_MAX_W):
    """Box-average down to at most max_w wide. Returns (w, h, rgba)."""
    if w <= max_w:
        return w, h, rgba
    scale = max_w / w
    nw, nh = max_w, max(1, round(h * scale))
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        y0, y1 = int(y / scale), max(int((y + 1) / scale), int(y / scale) + 1)
        for x in range(nw):
            x0, x1 = int(x / scale), max(int((x + 1) / scale), int(x / scale) + 1)
            acc = [0, 0, 0, 0]
            n = 0
            for sy in range(y0, min(y1, h)):
                for sx in range(x0, min(x1, w)):
                    i = (sy * w + sx) * 4
                    for k in range(4):
                        acc[k] += rgba[i + k]
                    n += 1
            o = (y * nw + x) * 4
            for k in range(4):
                out[o + k] = acc[k] // n
    return nw, nh, out


# ---------------------------------------------------------------- analysis


def luminance(rgba, i):
    return (0.2126 * rgba[i] + 0.7152 * rgba[i + 1] + 0.0722 * rgba[i + 2]) / 255.0


def depth_proxy(w, h, rgba, depth_rgba=None, depth_white_far=True):
    """Per-pixel farness in [0, 1] (1 = far). Returns (values, source).

    With a depth map: its luminance, normalised; white means far unless
    depth_white_far is false. Without one: a heuristic -- the vertical
    position dominates (the top of a landscape illustration is far), with
    local detail pulling nearer (subjects are drawn with more contrast
    than the backdrop wash)."""
    if depth_rgba is not None:
        vals = array("f", bytes(4 * w * h))
        lo, hi = 1.0, 0.0
        for p in range(w * h):
            v = luminance(depth_rgba, p * 4)
            vals[p] = v if depth_white_far else 1.0 - v
            lo, hi = min(lo, vals[p]), max(hi, vals[p])
        span = max(hi - lo, 1e-6)
        for p in range(w * h):
            vals[p] = (vals[p] - lo) / span
        return vals, "map"
    # Local luminance variance in a 5x5 window, as the "detail" term.
    lum = array("f", bytes(4 * w * h))
    for p in range(w * h):
        lum[p] = luminance(rgba, p * 4)
    vals = array("f", bytes(4 * w * h))
    for y in range(h):
        row_far = 1.0 - (y / max(h - 1, 1))  # 1 at the top, 0 at the bottom.
        for x in range(w):
            acc = acc2 = 0.0
            n = 0
            for dy in (-2, 0, 2):
                for dx in (-2, 0, 2):
                    xx, yy = min(max(x + dx, 0), w - 1), min(max(y + dy, 0), h - 1)
                    v = lum[yy * w + xx]
                    acc += v
                    acc2 += v * v
                    n += 1
            mean = acc / n
            var = max(acc2 / n - mean * mean, 0.0)
            detail = min(var * 14.0, 1.0)  # Busy patches read as nearer.
            vals[y * w + x] = max(0.0, min(1.0, row_far - 0.35 * detail * row_far))
    return vals, "heuristic"


def box_blur(vals, w, h):
    out = array("f", bytes(4 * w * h))
    for y in range(h):
        for x in range(w):
            acc = 0.0
            n = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    xx, yy = min(max(x + dx, 0), w - 1), min(max(y + dy, 0), h - 1)
                    acc += vals[yy * w + xx]
                    n += 1
            out[y * w + x] = acc / n
    return out


def find_horizon(depth, w, h):
    """First row (from the top) whose mean farness drops below 0.5: above it
    the picture is backdrop, below it the ground plane starts. Falls back
    to 60% of the height when the depth never crosses."""
    for y in range(h):
        mean = sum(depth[y * w:(y + 1) * w]) / w
        if mean < 0.5:
            return y
    return int(h * 0.6)


def components(mask, w, h, min_area):
    """4-connected components of a bytearray mask. Returns a list of
    {bbox: (x0, y0, x1, y1) inclusive-exclusive, area, label} plus the
    label image (array of int, -1 = none)."""
    labels = array("i", [-1]) * (w * h)
    found = []
    for start in range(w * h):
        if not mask[start] or labels[start] >= 0:
            continue
        label = len(found)
        stack = [start]
        labels[start] = label
        area = 0
        x0 = x1 = start % w
        y0 = y1 = start // w
        while stack:
            p = stack.pop()
            area += 1
            x, y = p % w, p // w
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
            for q in (p - 1 if x > 0 else -1, p + 1 if x < w - 1 else -1,
                      p - w if y > 0 else -1, p + w if y < h - 1 else -1):
                if q >= 0 and mask[q] and labels[q] < 0:
                    labels[q] = label
                    stack.append(q)
        if area >= min_area:
            found.append({"bbox": (x0, y0, x1 + 1, y1 + 1), "area": area, "label": label})
        else:
            found.append(None)
    return [c for c in found if c], labels


COLOR_TOL = 0.13  # Flood-fill colour tolerance (normalised RGB distance).


def segment_bands(rgba, w, h, band_of):
    """Colour-tolerant flood fill within each depth band: a component is a
    connected run of same-band pixels whose colours stay within COLOR_TOL
    of the component's running mean, so a dark doorway separates from the
    green ground it stands on even inside one band. Returns (components,
    labels); each component has bbox, area, mean RGB and mean luminance."""
    labels = array("i", [-1]) * (w * h)
    found = []
    for start in range(w * h):
        band = band_of[start]
        if band == 0 or labels[start] >= 0:
            continue
        label = len(found)
        stack = [start]
        labels[start] = label
        area = 0
        x0 = x1 = start % w
        y0 = y1 = start // w
        sr = sg = sb = sl = 0.0
        while stack:
            p = stack.pop()
            area += 1
            x, y = p % w, p // w
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
            i = p * 4
            sr += rgba[i]
            sg += rgba[i + 1]
            sb += rgba[i + 2]
            sl += luminance(rgba, i)
            mr, mg, mb = sr / area, sg / area, sb / area
            for q in (p - 1 if x > 0 else -1, p + 1 if x < w - 1 else -1,
                      p - w if y > 0 else -1, p + w if y < h - 1 else -1):
                if q >= 0 and labels[q] < 0 and band_of[q] == band:
                    j = q * 4
                    d = math.sqrt((rgba[j] - mr) ** 2 + (rgba[j + 1] - mg) ** 2 + (rgba[j + 2] - mb) ** 2) / 255.0
                    if d < COLOR_TOL:
                        labels[q] = label
                        stack.append(q)
        found.append({"bbox": (x0, y0, x1 + 1, y1 + 1), "area": area, "label": label,
                      "band": band, "mean_rgb": (sr / area, sg / area, sb / area),
                      "mean_luminance": sl / area})
    return found, labels


def mean_color(rgba, w, comp_pixels):
    acc = [0, 0, 0]
    for p in comp_pixels:
        i = p * 4
        for k in range(3):
            acc[k] += rgba[i + k]
    n = max(len(comp_pixels), 1)
    return "#%02x%02x%02x" % tuple(v // n for v in acc)


def quantile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    return sorted_vals[min(int(q * len(sorted_vals)), len(sorted_vals) - 1)]


def _bbox_iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max((a[2] - a[0]) * (a[3] - a[1]), 1)
    area_b = max((b[2] - b[0]) * (b[3] - b[1]), 1)
    return inter / (area_a + area_b - inter)


def to_registry_elements(spec, report):
    """Convert (spec, report) into B-1222 element correspondence entries."""
    import spec_registry
    return spec_registry.elements_from_report_data(report, spec=spec)


# ---------------------------------------------------------------- layout


def route_waypoints(spawn, waypoints, footprints, walk, cell=0.3, clearance=0.6):
    """Route spawn -> wp1 -> wp2 ... around obstacle footprints on the walk
    grid using deterministic A*. Inserts only turning corners where a
    straight line is blocked; leaves clear legs and unreachable legs
    unchanged. Returns (new_waypoints, legs)."""
    if not waypoints:
        return [], []

    x_min, x_max = float(walk["x"][0]), float(walk["x"][1])
    z_min, z_max = float(walk["z"][0]), float(walk["z"][1])
    span_x = max(x_max - x_min, 0.0)
    span_z = max(z_max - z_min, 0.0)
    nx = max(1, int(math.ceil(span_x / cell - 1e-9)))
    nz = max(1, int(math.ceil(span_z / cell - 1e-9)))

    boxes = [
        (cx - w * 0.5 - clearance, cx + w * 0.5 + clearance,
         cz - clearance, cz + clearance)
        for cx, cz, w in (footprints or [])
    ]

    def point_blocked(px, pz):
        for bx0, bx1, bz0, bz1 in boxes:
            if bx0 <= px <= bx1 and bz0 <= pz <= bz1:
                return True
        return False

    def segment_clear(x0, z0, x1, z1):
        dx = x1 - x0
        dz = z1 - z0
        for bx0, bx1, bz0, bz1 in boxes:
            t_enter, t_exit = 0.0, 1.0
            if abs(dx) < 1e-12:
                if x0 < bx0 or x0 > bx1:
                    continue
            else:
                tx0 = (bx0 - x0) / dx
                tx1 = (bx1 - x0) / dx
                if tx0 > tx1:
                    tx0, tx1 = tx1, tx0
                t_enter = max(t_enter, tx0)
                t_exit = min(t_exit, tx1)
                if t_enter > t_exit:
                    continue
            if abs(dz) < 1e-12:
                if z0 < bz0 or z0 > bz1:
                    continue
            else:
                tz0 = (bz0 - z0) / dz
                tz1 = (bz1 - z0) / dz
                if tz0 > tz1:
                    tz0, tz1 = tz1, tz0
                t_enter = max(t_enter, tz0)
                t_exit = min(t_exit, tz1)
                if t_enter > t_exit:
                    continue
            return False
        return True

    def cell_x(ix):
        if span_x < cell:
            return round((x_min + x_max) * 0.5, 3)
        return round(min(x_max, max(x_min, x_min + (ix + 0.5) * cell)), 3)

    def cell_z(iz):
        if span_z < cell:
            return round((z_min + z_max) * 0.5, 3)
        return round(min(z_max, max(z_min, z_min + (iz + 0.5) * cell)), 3)

    gx_coords = [cell_x(ix) for ix in range(nx)]
    gz_coords = [cell_z(iz) for iz in range(nz)]
    blocked = [[point_blocked(gx_coords[ix], gz_coords[iz]) for ix in range(nx)]
               for iz in range(nz)]

    def to_cell(px, pz):
        # The nearest free cell for a point. A point inside an expanded
        # footprint is not hopeless: the expansion is a safety margin around
        # a thin card (the built collider is 0.2 m deep), and the walker
        # only has to get within reach of the point. Such a point maps to
        # the closest free cell, and the final hop to the point itself is
        # exempt from the segment test.
        ix0 = min(nx - 1, max(0, int((px - x_min) / cell)))
        iz0 = min(nz - 1, max(0, int((pz - z_min) / cell)))
        if not point_blocked(px, pz) and not blocked[iz0][ix0] \
                and segment_clear(px, pz, gx_coords[ix0], gz_coords[iz0]):
            return (ix0, iz0)
        inside = point_blocked(px, pz)
        best = None
        best_key = None
        for radius in range(0, 5):
            for d_ix in range(-radius, radius + 1):
                for d_iz in range(-radius, radius + 1):
                    if max(abs(d_ix), abs(d_iz)) != radius:
                        continue
                    ix, iz = ix0 + d_ix, iz0 + d_iz
                    if 0 <= ix < nx and 0 <= iz < nz and not blocked[iz][ix]:
                        cx, cz = gx_coords[ix], gz_coords[iz]
                        if not inside and not segment_clear(px, pz, cx, cz):
                            continue
                        d2 = (cx - px) ** 2 + (cz - pz) ** 2
                        key = (round(d2, 9), ix, iz)
                        if best_key is None or key < best_key:
                            best_key = key
                            best = (ix, iz)
            if best is not None:
                break
        return best

    sqrt2 = math.sqrt(2.0)
    dirs = (
        (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, sqrt2), (1, -1, sqrt2), (-1, 1, sqrt2), (-1, -1, sqrt2),
    )

    def heuristic(a, b):
        adx = abs(a[0] - b[0])
        adz = abs(a[1] - b[1])
        return (adx + adz) + (sqrt2 - 2.0) * min(adx, adz)

    def astar(start_c, goal_c):
        if start_c == goal_c:
            return [start_c]
        g_score = {start_c: 0.0}
        came_from = {}
        closed = set()
        heap = [(round(heuristic(start_c, goal_c), 9), start_c[0], start_c[1])]
        while heap:
            _, ix, iz = heapq.heappop(heap)
            cur = (ix, iz)
            if cur in closed:
                continue
            if cur == goal_c:
                path = [cur]
                while cur in came_from:
                    cur = came_from[cur]
                    path.append(cur)
                path.reverse()
                return path
            closed.add(cur)
            g_cur = g_score[cur]
            cx0, cz0 = gx_coords[ix], gz_coords[iz]
            for dx, dz, step_cost in dirs:
                nx_i, nz_i = ix + dx, iz + dz
                if not (0 <= nx_i < nx and 0 <= nz_i < nz):
                    continue
                if blocked[nz_i][nx_i]:
                    continue
                if dx != 0 and dz != 0:
                    if blocked[iz][nx_i] or blocked[nz_i][ix]:
                        continue
                nb = (nx_i, nz_i)
                if nb in closed:
                    continue
                if not segment_clear(cx0, cz0, gx_coords[nx_i], gz_coords[nz_i]):
                    continue
                tentative_g = g_cur + step_cost
                if tentative_g < g_score.get(nb, float("inf")) - 1e-12:
                    g_score[nb] = tentative_g
                    came_from[nb] = cur
                    f_val = tentative_g + heuristic(nb, goal_c)
                    heapq.heappush(heap, (round(f_val, 9), nx_i, nz_i))
        return None

    new_waypoints = []
    legs = []
    curr = [float(spawn[0]), float(spawn[1]), float(spawn[2])]

    for raw_wp in waypoints:
        wp = [float(raw_wp[0]), float(raw_wp[1]), float(raw_wp[2])]
        sx, sy, sz = curr
        gx, gy, gz = wp

        if segment_clear(sx, sz, gx, gz):
            new_waypoints.append(list(raw_wp))
            legs.append({"from": list(curr), "to": list(raw_wp), "routed": True, "inserted": 0})
            curr = list(wp)
            continue

        start_c = to_cell(sx, sz)
        goal_c = to_cell(gx, gz)
        cell_path = astar(start_c, goal_c) if (start_c is not None and goal_c is not None) else None
        if not cell_path:
            new_waypoints.append(list(raw_wp))
            legs.append({"from": list(curr), "to": list(raw_wp), "routed": False, "inserted": 0})
            curr = list(wp)
            continue

        pts = [(sx, sz)]
        for ix, iz in cell_path:
            pt = (gx_coords[ix], gz_coords[iz])
            if abs(pt[0] - pts[-1][0]) > 1e-6 or abs(pt[1] - pts[-1][1]) > 1e-6:
                pts.append(pt)
        if abs(gx - pts[-1][0]) > 1e-6 or abs(gz - pts[-1][1]) > 1e-6:
            pts.append((gx, gz))

        corners = []
        i = 0
        n_pts = len(pts)
        while i < n_pts - 1:
            best_j = i + 1
            for j in range(n_pts - 1, i, -1):
                if segment_clear(pts[i][0], pts[i][1], pts[j][0], pts[j][1]):
                    best_j = j
                    break
            if best_j < n_pts - 1:
                cx, cz = pts[best_j]
                corners.append([cx, sy, cz])
            i = best_j

        for c_pt in corners:
            new_waypoints.append(c_pt)
        new_waypoints.append(list(raw_wp))
        legs.append({"from": list(curr), "to": list(raw_wp), "routed": True, "inserted": len(corners)})
        curr = list(wp)

    return new_waypoints, legs


def analyze(image_path, depth_path=None, depth_white_far=True,
            backdrop_width=26.0, backdrop_z=-20.0, fov=50.0,
            out_res="res://image_scene", scene_name="image_scene",
            registry_elements=None):
    """Returns (spec, report, assets): a B-1207 build spec (dict), the
    generation report (dict), and {file name: PNG bytes} to write beside
    the spec (the layer textures). Pure: no file writes except reading the
    input images, so tests can pin the shape.

    When `registry_elements` (from B-1222 ai_loop/spec_registry.py) is
    given, registered element-to-node mappings override matching generated
    names/bases and unmatched registered elements are injected as markers."""
    orig_w, orig_h, orig = load_rgba(image_path)
    w, h, rgba = downscale(orig_w, orig_h, orig)
    depth_rgba = None
    if depth_path:
        dw, dh, draw = load_rgba(depth_path)
        if (dw, dh) == (w, h):
            depth_rgba = draw
        else:  # Resample to the working size by nearest neighbour.
            depth_rgba = bytearray(w * h * 4)
            for y in range(h):
                for x in range(w):
                    si = (int(y * dh / h) * dw + int(x * dw / w)) * 4
                    di = (y * w + x) * 4
                    depth_rgba[di:di + 4] = draw[si:si + 4]
    depth, depth_source = depth_proxy(w, h, rgba, depth_rgba, depth_white_far)
    depth = box_blur(depth, w, h)
    horizon = find_horizon(depth, w, h)

    # Depth bands below the horizon, by terciles of the farness there.
    below = sorted(depth[y * w + x] for y in range(horizon, h) for x in range(w))
    q1, q2 = quantile(below, 1 / 3), quantile(below, 2 / 3)
    band_of = bytearray(w * h)  # 0 background, 1 midground, 2 foreground.
    for y in range(h):
        for x in range(w):
            p = y * w + x
            if y < horizon:
                band_of[p] = 0
            elif depth[p] >= q2:
                band_of[p] = 0
            elif depth[p] >= q1:
                band_of[p] = 1
            else:
                band_of[p] = 2

    # The ground colour, sampled from the bottom rows (observed), is the
    # reference for telling floor regions from objects standing on them.
    bottom_rows = [p for p in range((h - max(h // 12, 1)) * w, w * h)]
    ground_rgb = tuple(sum(rgba[p * 4 + k] for p in bottom_rows) / len(bottom_rows) for k in range(3))

    def color_dist(a, b):
        return math.sqrt(sum((a[k] - b[k]) ** 2 for k in range(3))) / 255.0

    min_area = max(24, int(w * h * MIN_COMPONENT_SHARE))
    band_names = {1: "midground", 2: "foreground"}
    cards = []
    assets = {}
    skipped = []
    comps, labels = segment_bands(rgba, w, h, band_of)
    comps = [c for c in comps if c["area"] >= min_area]
    for comp in comps:
        comp["labels"] = [comp.pop("label")]
        x0, y0, x1, y1 = comp["bbox"]
        # Floor is decided per component, before any merging, and floor
        # never takes part in a merge: otherwise an object whose colour is
        # close to the floor's would be swallowed by it.
        comp["floor"] = bool((y1 >= h - 1 and y0 > horizon)
                             or (y0 >= horizon - 2 and color_dist(comp["mean_rgb"], ground_rgb) < 0.10))
    # A region in a floor region's *near-identical* colour (0.03) is the
    # same surface seen higher in the picture (the far part of a path
    # whose near part touches the bottom edge): floor too. The threshold
    # is tight on purpose: object colours sit within 0.05 of a floor shade
    # easily (a tree's shadowed green against dark grass), and losing an
    # object is worse than keeping a path slab as a card.
    floor_colors = [c["mean_rgb"] for c in comps if c["floor"]]
    if floor_colors:
        for comp in comps:
            x0, y0, x1, y1 = comp["bbox"]
            if not comp["floor"] and y0 > horizon and min(color_dist(comp["mean_rgb"], fc) for fc in floor_colors) < 0.03:
                comp["floor"] = True
    # Merge parts of one object that the band boundary cut in two (a tree
    # whose crown is in one band and trunk in the next): touching boxes,
    # strong horizontal overlap, near-identical colour (0.05 -- only parts
    # of one surface, like a path crossing the boundary, qualify).
    merged = True
    while merged:
        merged = False
        comps.sort(key=lambda c: -c["area"])
        for i in range(len(comps)):
            if merged:
                break
            for j in range(i + 1, len(comps)):
                a, b = comps[i], comps[j]
                if a["band"] == b["band"] or a["floor"] or b["floor"]:
                    continue
                ax0, ay0, ax1, ay1 = a["bbox"]
                bx0, by0, bx1, by1 = b["bbox"]
                overlap = min(ax1, bx1) - max(ax0, bx0)
                narrow = min(ax1 - ax0, bx1 - bx0)
                touching = abs(ay1 - by0) <= 2 or abs(by1 - ay0) <= 2
                if touching and overlap > 0.5 * narrow and color_dist(a["mean_rgb"], b["mean_rgb"]) < 0.05:
                    keep, drop = (a, b) if ay1 >= by1 else (b, a)  # The ground-contact part sets the band.
                    total = a["area"] + b["area"]
                    keep["mean_rgb"] = tuple((a["mean_rgb"][k] * a["area"] + b["mean_rgb"][k] * b["area"]) / total for k in range(3))
                    keep["mean_luminance"] = (a["mean_luminance"] * a["area"] + b["mean_luminance"] * b["area"]) / total
                    keep["bbox"] = (min(ax0, bx0), min(ay0, by0), max(ax1, bx1), max(ay1, by1))
                    keep["area"] = total
                    keep["labels"] = a["labels"] + b["labels"]
                    comps.remove(drop)
                    merged = True
                    break
    comps.sort(key=lambda c: -c["area"])
    kept_per_band = {1: 0, 2: 0}
    for comp in comps:
        x0, y0, x1, y1 = comp["bbox"]
        bw_px, bh_px = x1 - x0, y1 - y0
        band = comp["band"]
        if comp["floor"]:
            skipped.append({"reason": "ground surface: a region reaching the bottom edge, or in the ground's own colour below the horizon, is floor (grass, a path), not a card; a foreground object cropped by the frame's bottom edge would be lost here",
                            "bbox": [x0, y0, x1, y1], "area": comp["area"]})
            continue
        if bw_px > 0.65 * w and bh_px > 0.2 * h:
            skipped.append({"reason": "oversized region (over 65% of the width and 20% of the height): a mis-segmented area, not an object",
                            "bbox": [x0, y0, x1, y1], "area": comp["area"]})
            continue
        if kept_per_band[band] >= MAX_CARDS_PER_BAND:
            continue
        idx = kept_per_band[band]
        kept_per_band[band] += 1
        # Card texture: the component's box, alpha from the segmentation.
        label_set = set(comp["labels"])
        cw, ch = bw_px, bh_px
        tex = bytearray(cw * ch * 4)
        for yy in range(ch):
            for xx in range(cw):
                p = (y0 + yy) * w + (x0 + xx)
                o = (yy * cw + xx) * 4
                if labels[p] in label_set:
                    tex[o:o + 4] = rgba[p * 4:p * 4 + 4]
        fname = "card_%s_%d.png" % (band_names[band], idx)
        assets[fname] = write_png_bytes(cw, ch, tex)
        cards.append({
            "band": band_names[band], "file": fname, "bbox": [x0, y0, x1, y1],
            "area": comp["area"],
            "mean_color": "#%02x%02x%02x" % tuple(int(v) for v in comp["mean_rgb"]),
            "mean_luminance": comp["mean_luminance"],
            "touches_ground": y1 >= horizon + 0.45 * (h - horizon),
        })

    # Interact candidates: bright blobs (glow) and tall grounded shapes (door).
    lum_mask = bytearray(w * h)
    lum_vals = sorted(luminance(rgba, p * 4) for p in range(w * h))
    lum_hi = max(0.80, quantile(lum_vals, 0.93))
    for p in range(w * h):
        lum_mask[p] = 1 if luminance(rgba, p * 4) >= lum_hi else 0
    glow_comps, _ = components(lum_mask, w, h, max(8, int(w * h * 0.0002)))
    glow_comps = [c for c in glow_comps if c["area"] <= w * h * 0.04]
    glow_comps.sort(key=lambda c: -c["area"])
    candidates = []
    for i, comp in enumerate(glow_comps[:MAX_GLOW]):
        x0, y0, x1, y1 = comp["bbox"]
        candidates.append({
            "id": "glow_%d" % i, "kind": "glow", "basis": "inferred",
            "reason": "a bright blob (luminance >= %.2f): lit windows, lamps and signs read as interact points" % lum_hi,
            "image_bbox": [x0, y0, x1, y1],
            "confidence": round(min(1.0, 0.5 + comp["area"] / (w * h * 0.01)), 2),
        })
    door_n = 0
    for card in cards:
        x0, y0, x1, y1 = card["bbox"]
        bw, bh = x1 - x0, y1 - y0
        aspect = bh / max(bw, 1)
        if card["touches_ground"] and 1.6 <= aspect <= 3.4 and 0.015 <= bw / w <= 0.14 and card["mean_luminance"] < 0.75:
            candidates.append({
                "id": "door_%d" % door_n, "kind": "door", "basis": "inferred",
                "reason": "a tall (aspect %.1f) ground-standing shape in the %s band: a doorway-sized opening" % (aspect, card["band"]),
                "image_bbox": [x0, y0, x1, y1],
                "confidence": round(min(1.0, aspect / 3.0), 2),
            })
            door_n += 1

    # ---- 3D layout ------------------------------------------------------
    aspect = orig_w / orig_h
    backdrop_h = backdrop_width / aspect
    cam_dist = (backdrop_h / 2.0) / math.tan(math.radians(fov / 2.0))
    cam_z = backdrop_z + cam_dist
    cam_y = 1.7
    horizon_frac = horizon / h

    def project(cx, cy, z):
        """Image point (px) -> world (x, y) on the plane at depth z,
        through the reference camera."""
        vh = 2.0 * (cam_z - z) * math.tan(math.radians(fov / 2.0))
        return ((cx / w - 0.5) * vh * aspect, cam_y + (0.5 - cy / h) * vh)

    def meters_per_px(z):
        return 2.0 * (cam_z - z) * math.tan(math.radians(fov / 2.0)) / h

    z_of_band = {"midground": backdrop_z + 0.45 * cam_dist, "foreground": backdrop_z + 0.75 * cam_dist}
    spec_cards = [{
        "name": "Backdrop", "image": out_res + "/background.png",
        "position": [0.0, round(backdrop_h / 2.0, 3), backdrop_z],
        "size": [round(backdrop_width, 3), round(backdrop_h, 3)],
    }]
    card_reports = []
    collision_candidates = []
    reg_list = list(registry_elements or [])
    matched_reg_ids = set()
    reg_cards = [e for e in reg_list if e.get("kind") == "card"]
    reg_interact = [e for e in reg_list if e.get("kind") != "card"]

    for card in cards:
        x0, y0, x1, y1 = card["bbox"]
        # A card's depth: its ground contact maps through the ground plane
        # (bottom of the picture is near), its band keeps it in range.
        t = max(0.0, min(1.0, (y1 - horizon) / max(h - horizon, 1)))
        z = min(z_of_band[card["band"]] + (1.0 - t) * 2.0, cam_z - 4.0) if card["touches_ground"] else z_of_band[card["band"]]
        z = max(z, backdrop_z + 2.0)
        s = meters_per_px(z)
        cw_m, ch_m = (x1 - x0) * s, (y1 - y0) * s
        cx_m, cy_m = project((x0 + x1) / 2.0, (y0 + y1) / 2.0, z)
        if card["touches_ground"]:
            cy_m = ch_m / 2.0
        # A card wider than 40% of the backdrop is scenery (a ridge, a
        # terrace), not an obstacle a walker bumps into.
        collide = bool(card["touches_ground"] and 0.7 <= cw_m <= 0.4 * backdrop_width)
        default_name = "Card_%s_%s" % (card["band"].capitalize(), card["file"].split("_")[-1].split(".")[0])
        matched_reg = None
        for re_item in reg_cards:
            if re_item.get("id") == default_name or re_item.get("card") == default_name:
                matched_reg = re_item
                break
        if matched_reg is None and reg_cards:
            best = max(((re_item, _bbox_iou(re_item.get("image_bbox", [0, 0, 0, 0]), card["bbox"])) for re_item in reg_cards),
                       key=lambda pair: pair[1])
            if best[1] >= 0.7:
                matched_reg = best[0]
        card_name = matched_reg["node"] if (matched_reg and matched_reg.get("node")) else default_name
        entry = {
            "name": card_name,
            "image": out_res + "/" + card["file"],
            "position": [round(cx_m, 3), round(cy_m, 3), round(z, 3)],
            "size": [round(cw_m, 3), round(ch_m, 3)],
            "collision": collide,
        }
        spec_cards.append(entry)
        creport = {**entry, "band": card["band"], "basis": "inferred",
                   "image_bbox": card["bbox"], "mean_color": card["mean_color"]}
        if matched_reg:
            matched_reg_ids.add(matched_reg["id"])
            if matched_reg.get("basis") == "observed":
                creport["basis"] = "observed"
                if matched_reg.get("evidence"):
                    creport["evidence"] = matched_reg["evidence"]
        card_reports.append(creport)
        if collide:
            collision_candidates.append({
                "card": entry["name"], "basis": "inferred",
                "reason": "a ground-standing %s card %.1f m wide: something a walker should not pass through" % (card["band"], cw_m),
                "footprint": [entry["position"][0], entry["position"][2], entry["size"][0]],
            })

    for cand in candidates:
        x0, y0, x1, y1 = cand["image_bbox"]
        band = "midground"
        for card in cards:
            if card["bbox"] == cand["image_bbox"]:
                band = card["band"]
        z = z_of_band[band]
        cx_m, cy_m = project((x0 + x1) / 2.0, (y0 + y1) / 2.0, z)
        if cand["kind"] == "door":
            cy_m = (y1 - y0) * meters_per_px(z) / 2.0
        cand["position"] = [round(cx_m, 3), round(max(cy_m, 0.4), 3), round(z, 3)]
        matched_reg = None
        for re_item in reg_interact:
            if re_item.get("id") == cand["id"]:
                matched_reg = re_item
                break
        if matched_reg is None and reg_interact:
            best = max(((re_item, _bbox_iou(re_item.get("image_bbox", [0, 0, 0, 0]), cand["image_bbox"]))
                        for re_item in reg_interact if re_item.get("id") not in matched_reg_ids),
                       key=lambda pair: pair[1], default=(None, 0.0))
            if best[1] >= 0.5:
                matched_reg = best[0]
        if matched_reg:
            matched_reg_ids.add(matched_reg["id"])
            cand["id"] = matched_reg["id"]
            if matched_reg.get("kind"):
                cand["kind"] = matched_reg["kind"]
            if matched_reg.get("node"):
                cand["node"] = matched_reg["node"]
            if matched_reg.get("basis") == "observed":
                cand["basis"] = "observed"
                cand.pop("reason", None)
                if matched_reg.get("evidence"):
                    cand["evidence"] = matched_reg["evidence"]

    injected_count = 0
    for re_item in reg_interact:
        if re_item.get("id") in matched_reg_ids:
            continue
        bbox = re_item.get("image_bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = [int(v) for v in bbox]
        band = "foreground" if y1 >= horizon + 0.75 * max(h - horizon, 1) else "midground"
        z = z_of_band[band]
        cx_m, cy_m = project((x0 + x1) / 2.0, (y0 + y1) / 2.0, z)
        if re_item.get("kind") in ("door", "sign", "npc", "prop"):
            cy_m = (y1 - y0) * meters_per_px(z) / 2.0
        pos = re_item.get("position") if isinstance(re_item.get("position"), list) else [round(cx_m, 3), round(max(cy_m, 0.4), 3), round(z, 3)]
        injected = {
            "id": re_item["id"],
            "kind": re_item.get("kind", "interact"),
            "basis": re_item.get("basis", "inferred"),
            "image_bbox": [x0, y0, x1, y1],
            "node": re_item.get("node") or ("Candidate_%s" % str(re_item["id"]).capitalize()),
            "position": pos,
        }
        if injected["basis"] == "observed":
            injected["evidence"] = re_item.get("evidence") or "registered in spec_registry"
        else:
            injected["reason"] = re_item.get("reason") or "registered element injected from spec_registry"
        if re_item.get("confidence") is not None:
            injected["confidence"] = float(re_item["confidence"])
        candidates.append(injected)
        injected_count += 1

    # Ground: coloured from the sample above (observed), sized to run from
    # behind the camera to the backdrop's base.
    ground_color = "#%02x%02x%02x" % tuple(int(v) for v in ground_rgb)
    ground_depth = cam_z + 4.0 - backdrop_z
    ground_center_z = backdrop_z + ground_depth / 2.0
    ground_width = backdrop_width * 1.25

    # Walkable area and waypoints (the walker stays on the centre lane,
    # clear of the card footprints by construction).
    walk = {
        "x": [-round(backdrop_width * 0.30, 2), round(backdrop_width * 0.30, 2)],
        "z": [round(backdrop_z + 3.0, 2), round(cam_z - 2.0, 2)],
        "basis": "inferred",
        "reason": "the ground strip below the horizon, narrowed to the centre lane so scaffold cards at the edges stay out of the way",
    }
    spawn = [0.0, 0.0, round(cam_z - 3.5, 2)]
    mid_z = round((walk["z"][0] + walk["z"][1]) / 2.0, 2)
    lane_z = round(mid_z + 0.7, 2)  # The sideways legs run a step nearer, clear of the card frontage.
    waypoints = [[0.0, 0.0, mid_z],
                 [round(walk["x"][0] * 0.7, 2), 0.0, lane_z],
                 [round(walk["x"][1] * 0.7, 2), 0.0, lane_z]]
    if candidates:
        first = min(candidates, key=lambda c: abs(c["position"][0]) + abs(c["position"][2] - spawn[2]))
        tx, tz = first["position"][0], first["position"][2] + 1.4  # Stop short of it.
        if walk["z"][0] <= tz <= walk["z"][1]:
            waypoints.append([round(max(walk["x"][0], min(tx, walk["x"][1])), 2), 0.0, round(tz, 2)])
    waypoints.append(spawn)
    footprints = [c["footprint"] for c in collision_candidates]
    waypoints, walk_legs = route_waypoints(spawn, waypoints, footprints, walk)

    look_at = [0.0, round(backdrop_h * (1.0 - horizon_frac), 3), backdrop_z]
    top_mean = sum(luminance(rgba, p * 4) for p in range(0, w * (h // 3))) / max(w * (h // 3), 1)
    warm = 0.0
    n_warm = 0
    for p in range(0, w * (h // 3)):
        i = p * 4
        warm += (rgba[i] - rgba[i + 2]) / 255.0
        n_warm += 1
    warm /= max(n_warm, 1)
    atmosphere = "night" if top_mean < 0.16 else ("golden_hour" if warm > 0.06 else "clear")

    spec = {
        "scene": out_res + "/" + scene_name + ".tscn",
        "look": {"quality": "standard", "atmosphere": atmosphere},
        "ground": {"size": [round(ground_width, 2), round(ground_depth, 2)],
                   "position": [0.0, 0.0, round(ground_center_z, 2)],
                   "color": ground_color, "collision": True},
        "camera": {"position": [0.0, cam_y, round(cam_z, 3)], "look_at": look_at, "fov": fov},
        "cards": spec_cards,
        "lamps": [c["position"] for c in candidates if c["kind"] in ("glow", "lamp")],
        "markers": [{"name": c.get("node") or ("Candidate_%s" % c["id"].capitalize()), "kind": c["kind"],
                     "position": c["position"], "radius": 0.9} for c in candidates],
    }
    report = {
        "format": "uzu-image-scene/1",
        "image": {"width": orig_w, "height": orig_h, "basis": "observed",
                  "working_size": [w, h]},
        "depth": {"source": depth_source,
                  "basis": "observed" if depth_source == "map" else "inferred",
                  "reason": "caller-supplied depth map (B-903 import path)" if depth_source == "map"
                            else "no depth map supplied: vertical-position heuristic with a local-detail term"},
        "horizon": {"y_px": horizon, "fraction": round(horizon_frac, 3), "basis": "inferred"},
        "ground_color": {"value": ground_color, "basis": "observed",
                         "reason": "mean colour of the illustration's bottom rows"},
        "atmosphere": {"value": atmosphere, "basis": "inferred",
                       "reason": "from the top third's mean luminance and warmth"},
        "layers": {"backdrop": {"file": "background.png", "size_m": [round(backdrop_width, 2), round(backdrop_h, 2)]},
                   "cards": card_reports, "skipped": skipped},
        "walk_area": walk,
        "spawn": spawn,
        "waypoints": waypoints,
        "walk_routing": walk_legs,
        "candidates": {"interact": candidates, "collision": collision_candidates},
        "camera": {"position": spec["camera"]["position"], "look_at": look_at, "fov": fov,
                   "basis": "inferred",
                   "reason": "placed so the backdrop fills the frame at the given fov; B-1223 diffs the scene against the illustration from here"},
    }
    if reg_list:
        report["registry"] = {"matched": len(matched_reg_ids), "injected": injected_count}
    assets["background.png"] = None  # The caller copies the source file.
    return spec, report, assets


def write_png_bytes(width, height, rgba):
    """write_png to memory (assets are collected, then written by the caller)."""
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    return png
