#!/usr/bin/env python3
"""Spec-image diff verification (BACKLOG B-1223): how far is the built scene
from the illustration that specified it?

The image-first flow (B-1221) turns a specification illustration into a
scene scaffold and records, in its generation report, where every element
sits in the picture. This module closes the loop: it compares a screenshot
of the scene (taken from the scaffold's reference camera) against the
illustration, mechanically, and returns a verdict as structured JSON:

  * composition -- edge agreement between the two frames (gradient edges,
    matched with a small positional tolerance, so a couple of pixels of
    resampling shift do not dominate),
  * colour -- the distance between the two frames' colour histograms,
  * elements -- for every element of the generation report (layer cards
    and interact candidates), whether it is still present in the shot:
    a gain-compensated pixel agreement (tone mapping darkens brights, so
    each region is first re-exposed to the spec's mean colour), the
    region's mean-colour distance, and how much the region still stands
    out from its surroundings compared to the spec (contrast ratio).

Candidates (B-1227): elements of kind "glow" are the B-1221 detector's
unverified bright-blob guesses. They are reported in the verdict's
"advisory" breakdown but never gate it: the overall ok is decided by the
composition and colour metrics plus the gating elements (cards and
registered semantic elements). Every element entry carries a "candidate"
flag saying which side of that line it is on.

Every number is reported per element, so an agent can tell *which* element
is off and by how much, and pick the next fix. Thresholds are data
(DEFAULT_THRESHOLDS, overridable from a JSON file or CLI flags) because
what counts as "close enough" is a per-project call.

Element input is the B-1221 generation report today (layers.cards +
candidates.interact, image bboxes in the report's working resolution).
elements_from_report() is the only place that knows that shape, so the
B-1222 spec registry can feed the same {id, kind, bbox, basis} list later.

Pure Python, standard library only; PNG reading reuses ai_loop/image_scene
(which reuses image_diff). Public entry: compare(spec_path, shot_path,
elements, thresholds) -> verdict dict. The CLI wiring lives in
ai_loop/uzu.py ("spec-diff"); this file also runs standalone with
--spec-image/--shot/--report for engine-free checks.
"""

import json
import math
import os
import sys
from array import array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_scene  # noqa: E402  (PNG in/out, downscale, box_blur)

DEFAULT_THRESHOLDS = {
    "composition_min": 0.30,        # Edge agreement at or above this passes.
    "color_max": 0.32,              # Histogram distance at or below this passes.
    "element_agreement_min": 0.50,  # Gain-compensated pixel agreement.
    "element_agreement_color_max": 0.45,  # The agreement only counts when
    # the region's mean colour is also in the spec's family: exposure
    # compensation models tone mapping, not a repaint in another colour.
    "element_color_max": 0.12,      # Fallback: region mean-colour distance.
    "element_contrast_ratio_min": 0.45,  # Fallback: shot/spec contrast.
    "candidate_contrast_ratio_min": 0.25,  # Candidates (glow/door) are
    # judged mainly by still standing out: a lamp in the scene is a light,
    # not the painted blob, so pixel agreement is often low by design.
    "element_edge_ratio_min": 0.45,  # Fallback (cards): internal edges kept.
}

EDGE_GRADIENT_MIN = 28.0   # |gx| + |gy| on 0..255 luminance counts as an edge.
PIXEL_TOL = 0.25           # Per-pixel colour distance that counts as agreement.
MAX_SHIFT = 3              # Element alignment search radius, in working px.


# ---------------------------------------------------------------- loading


def resample(w, h, rgba, nw, nh):
    """Box-average resample of an RGBA buffer to (nw, nh)."""
    if (w, h) == (nw, nh):
        return rgba
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        y0, y1 = int(y * h / nh), max(int((y + 1) * h / nh), int(y * h / nh) + 1)
        for x in range(nw):
            x0, x1 = int(x * w / nw), max(int((x + 1) * w / nw), int(x * w / nw) + 1)
            acc = [0, 0, 0, 0]
            n = 0
            for sy in range(y0, min(y1, h)):
                base = sy * w * 4
                for sx in range(x0, min(x1, w)):
                    i = base + sx * 4
                    for k in range(4):
                        acc[k] += rgba[i + k]
                    n += 1
            o = (y * nw + x) * 4
            for k in range(4):
                out[o + k] = acc[k] // n
    return out


def load_pair(spec_path, shot_path):
    """Both images at the spec's working resolution (the frame the B-1221
    report's bboxes live in). Returns (w, h, spec_rgba, shot_rgba, notes)."""
    sw, sh, spec = image_scene.load_rgba(spec_path)
    sw, sh, spec = image_scene.downscale(sw, sh, spec)
    tw, th, shot = image_scene.load_rgba(shot_path)
    notes = []
    if (tw, th) != (sw, sh):
        spec_aspect = sw / sh
        shot_aspect = tw / th
        if abs(spec_aspect - shot_aspect) / spec_aspect > 0.03:
            notes.append("shot aspect %.3f differs from spec aspect %.3f by over 3%%: "
                         "the shot was resampled to the spec's working size, so element "
                         "positions are approximate" % (shot_aspect, spec_aspect))
        shot = resample(tw, th, shot, sw, sh)
    return sw, sh, spec, shot, notes


# ---------------------------------------------------------------- metrics


def luminance_array(w, h, rgba):
    lum = array("f", bytes(4 * w * h))
    for p in range(w * h):
        i = p * 4
        lum[p] = 0.2126 * rgba[i] + 0.7152 * rgba[i + 1] + 0.0722 * rgba[i + 2]
    return lum


def edge_map(w, h, lum):
    edges = bytearray(w * h)
    for y in range(h):
        row = y * w
        up = max(y - 1, 0) * w
        down = min(y + 1, h - 1) * w
        for x in range(w):
            gx = lum[row + min(x + 1, w - 1)] - lum[row + max(x - 1, 0)]
            gy = lum[down + x] - lum[up + x]
            if abs(gx) + abs(gy) > EDGE_GRADIENT_MIN:
                edges[row + x] = 1
    return edges


def _dilate(edges, w, h):
    """Two 3x3 box-blur passes: an edge counts as matched when a counterpart
    sits within roughly two pixels."""
    vals = array("f", [float(v) for v in edges])
    vals = image_scene.box_blur(vals, w, h)
    vals = image_scene.box_blur(vals, w, h)
    return bytearray(1 if v > 0.02 else 0 for v in vals)


def composition_score(w, h, spec_lum, shot_lum):
    """Symmetric edge agreement in [0, 1] with positional tolerance."""
    ea = edge_map(w, h, spec_lum)
    eb = edge_map(w, h, shot_lum)
    na, nb = sum(ea), sum(eb)
    if na == 0 or nb == 0:
        return 1.0 if na == nb else 0.0
    da, db = _dilate(ea, w, h), _dilate(eb, w, h)
    hit_a = sum(1 for p in range(w * h) if ea[p] and db[p])
    hit_b = sum(1 for p in range(w * h) if eb[p] and da[p])
    return 0.5 * (hit_a / na + hit_b / nb)


def color_distance(w, h, spec, shot, bins=4):
    """1 - histogram intersection over a 4x4x4 RGB histogram, in [0, 1]."""
    def hist(rgba):
        counts = [0.0] * (bins ** 3)
        for p in range(w * h):
            i = p * 4
            key = (min(rgba[i] * bins // 256, bins - 1) * bins
                   + min(rgba[i + 1] * bins // 256, bins - 1)) * bins \
                + min(rgba[i + 2] * bins // 256, bins - 1)
            counts[key] += 1
        total = float(w * h)
        return [c / total for c in counts]
    ha, hb = hist(spec), hist(shot)
    return 1.0 - sum(min(a, b) for a, b in zip(ha, hb))


def _region_mean(w, rgba, x0, y0, x1, y1):
    acc = [0, 0, 0]
    n = 0
    for y in range(y0, y1):
        base = y * w * 4
        for x in range(x0, x1):
            i = base + x * 4
            acc[0] += rgba[i]
            acc[1] += rgba[i + 1]
            acc[2] += rgba[i + 2]
            n += 1
    n = max(n, 1)
    return (acc[0] / n, acc[1] / n, acc[2] / n)


def _ring_mean(w, h, rgba, x0, y0, x1, y1, pad):
    acc = [0, 0, 0]
    n = 0
    for y in range(max(y0 - pad, 0), min(y1 + pad, h)):
        base = y * w * 4
        for x in range(max(x0 - pad, 0), min(x1 + pad, w)):
            if x0 <= x < x1 and y0 <= y < y1:
                continue
            i = base + x * 4
            acc[0] += rgba[i]
            acc[1] += rgba[i + 1]
            acc[2] += rgba[i + 2]
            n += 1
    n = max(n, 1)
    return (acc[0] / n, acc[1] / n, acc[2] / n)


def _color_dist(a, b):
    return math.sqrt(sum((a[k] - b[k]) ** 2 for k in range(3))) / 255.0


def _mean_lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _agreement(w, h, spec, shot, bbox, dx, dy, gain, stride):
    """Share of the region's pixels whose gain-compensated shot colour is
    within PIXEL_TOL of the spec colour, sampled every `stride` pixels."""
    x0, y0, x1, y1 = bbox
    tol2 = (PIXEL_TOL * 255.0) ** 2
    hit = tot = 0
    for y in range(y0, y1, stride):
        yy = y + dy
        if not 0 <= yy < h:
            continue
        sbase = y * w * 4
        tbase = yy * w * 4
        for x in range(x0, x1, stride):
            xx = x + dx
            if not 0 <= xx < w:
                continue
            i = sbase + x * 4
            j = tbase + xx * 4
            d2 = 0.0
            for k in range(3):
                d = spec[i + k] - min(255.0, shot[j + k] * gain[k])
                d2 += d * d
            tot += 1
            if d2 <= tol2:
                hit += 1
    return hit / max(tot, 1)


def element_check(w, h, spec, shot, spec_edges, shot_edges, element, th):
    """One element's presence verdict, with every measured number."""
    x0, y0, x1, y1 = [int(v) for v in element["bbox"]]
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, w), min(y1, h)
    out = {"id": element.get("id", ""), "kind": element.get("kind", ""),
           "basis": element.get("basis", "inferred"), "bbox": [x0, y0, x1, y1]}
    if element.get("node"):
        out["node"] = element["node"]
    if x1 - x0 < 3 or y1 - y0 < 3:
        out.update({"pass": False, "verdict": "too_small",
                    "hint": "the element's box is under 3x3 working pixels: too small to judge"})
        return out
    bbox = (x0, y0, x1, y1)
    mean_spec = _region_mean(w, spec, *bbox)
    mean_shot = _region_mean(w, shot, *bbox)
    # The ring hugs the box but stays at least 6 px out: closer in, a small
    # bright element's own bloom in the shot would wash the ring out and
    # the element would stop standing out against it.
    pad = max(6, min(12, min(x1 - x0, y1 - y0) // 2))
    ring_spec = _ring_mean(w, h, spec, *bbox, pad)
    ring_shot = _ring_mean(w, h, shot, *bbox, pad)
    col_dist = _color_dist(mean_spec, mean_shot)
    contrast_spec = _color_dist(mean_spec, ring_spec)
    contrast_shot = _color_dist(mean_shot, ring_shot)
    contrast_ratio = contrast_shot / contrast_spec if contrast_spec > 1e-6 else 0.0
    dir_spec = _mean_lum(mean_spec) - _mean_lum(ring_spec)
    dir_shot = _mean_lum(mean_shot) - _mean_lum(ring_shot)
    direction_match = (dir_spec > 2.0 and dir_shot > 0.0) or (dir_spec < -2.0 and dir_shot < 0.0) \
        or abs(dir_spec) <= 2.0

    def density(edges):
        n = 0
        for y in range(y0, y1):
            row = y * w
            for x in range(x0, x1):
                n += edges[row + x]
        return n / max((x1 - x0) * (y1 - y0), 1)
    dens_spec = density(spec_edges)
    dens_shot = density(shot_edges)
    edge_ratio = dens_shot / dens_spec if dens_spec > 1e-6 else (1.0 if dens_shot > 1e-6 else 0.0)

    gain = []
    for k in range(3):
        g = mean_spec[k] / mean_shot[k] if mean_shot[k] > 4.0 else 1.0
        gain.append(min(max(g, 0.6), 1.8))  # Tone mapping's plausible range.
    stride = 2 if (x1 - x0) * (y1 - y0) > 8000 else 1
    agreement = _agreement(w, h, spec, shot, bbox, 0, 0, gain, stride)
    shift = [0, 0]
    if agreement < th["element_agreement_min"]:
        for dy in range(-MAX_SHIFT, MAX_SHIFT + 1):
            for dx in range(-MAX_SHIFT, MAX_SHIFT + 1):
                if dx == 0 and dy == 0:
                    continue
                a = _agreement(w, h, spec, shot, bbox, dx, dy, gain, stride)
                if a > agreement:
                    agreement, shift = a, [dx, dy]
        # The gain was fitted at the unshifted position; keep it (a global
        # exposure fit, not a per-pixel one).

    by_agreement = agreement >= th["element_agreement_min"] \
        and col_dist <= th["element_agreement_color_max"]
    by_appearance = col_dist <= th["element_color_max"] \
        and contrast_ratio >= th["element_contrast_ratio_min"]
    if element.get("kind") == "card":
        present = by_agreement or (by_appearance and edge_ratio >= th["element_edge_ratio_min"])
        via = "agreement" if by_agreement else ("appearance+edges" if present else "")
    else:
        by_contrast = contrast_ratio >= th["candidate_contrast_ratio_min"] and direction_match
        present = by_agreement or by_appearance or by_contrast
        via = "agreement" if by_agreement else ("appearance" if by_appearance
                                                else ("contrast" if by_contrast else ""))
    out.update({
        "pass": bool(present),
        "via": via,
        "agreement": round(agreement, 3),
        "agreement_shift": shift,
        "color_distance": round(col_dist, 3),
        "contrast": {"spec": round(contrast_spec, 3), "shot": round(contrast_shot, 3),
                     "ratio": round(contrast_ratio, 3)},
        "edge_density": {"spec": round(dens_spec, 4), "shot": round(dens_shot, 4),
                         "ratio": round(edge_ratio, 3)},
    })
    if not present:
        out["hint"] = ("not present in the shot: agreement %.2f (needs %.2f), colour distance "
                       "%.2f, contrast ratio %.2f -- the element is missing, moved, or "
                       "visually changed" % (agreement, th["element_agreement_min"],
                                             col_dist, contrast_ratio))
    return out


# ---------------------------------------------------------------- verdict


def is_candidate(element):
    """A candidate is an unverified detector guess (B-1227): kind "glow",
    the bright blobs B-1221 picks out of the illustration. Candidates are
    reported as advisory and never gate the verdict."""
    return element.get("kind") == "glow"


def elements_from_report(report):
    """The element list of a B-1221 generation report: layer cards plus
    interact candidates, each {id, kind, bbox, basis} in working pixels.
    This is the seam where the B-1222 registry plugs in via elements_from_registry()."""
    elements = []
    layers = report.get("layers", {})
    for card in layers.get("cards", []):
        elements.append({"id": card.get("name", ""), "kind": "card",
                         "bbox": card["image_bbox"], "basis": card.get("basis", "inferred"),
                         "candidate": False})
    for cand in report.get("candidates", {}).get("interact", []):
        elements.append({"id": cand.get("id", ""), "kind": cand.get("kind", ""),
                         "bbox": cand["image_bbox"], "basis": cand.get("basis", "inferred"),
                         "candidate": is_candidate(cand)})
    return elements


def elements_from_registry(registry_or_scene, scene=None):
    """The element list of a B-1222 specification image registry scene binding:
    each {id, kind, bbox, basis, node?} in working pixels."""
    if scene is not None:
        import spec_registry
        binding = spec_registry.get_scene_binding(registry_or_scene, scene)
        if not binding:
            raise ValueError(f"scene {scene!r} is not registered in the specification registry")
        raw_elements = binding.get("elements") or []
    else:
        raw_elements = (registry_or_scene or {}).get("elements") or []
    elements = []
    for elem in raw_elements:
        bbox = elem.get("image_bbox") if "image_bbox" in elem else elem.get("bbox")
        item = {
            "id": elem.get("id", ""),
            "kind": elem.get("kind", ""),
            "bbox": list(bbox),
            "basis": elem.get("basis", "inferred"),
            "candidate": is_candidate(elem),
        }
        if elem.get("node"):
            item["node"] = elem["node"]
        elements.append(item)
    return elements


def load_thresholds(path=None, overrides=None):
    th = dict(DEFAULT_THRESHOLDS)
    if path:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for key, value in data.items():
            if key not in th:
                raise ValueError(f"unknown threshold {key!r} (known: {', '.join(sorted(th))})")
            th[key] = float(value)
    for key, value in (overrides or {}).items():
        if value is not None:
            if key not in th:
                raise ValueError(f"unknown threshold {key!r} (known: {', '.join(sorted(th))})")
            th[key] = float(value)
    return th


def compare(spec_path, shot_path, elements, thresholds=None):
    """The verdict dict (format uzu-spec-diff/1). Pure: reads two PNGs."""
    th = dict(DEFAULT_THRESHOLDS)
    th.update(thresholds or {})
    w, h, spec, shot, notes = load_pair(spec_path, shot_path)
    spec_lum = luminance_array(w, h, spec)
    shot_lum = luminance_array(w, h, shot)
    comp = composition_score(w, h, spec_lum, shot_lum)
    col = color_distance(w, h, spec, shot)
    spec_edges = edge_map(w, h, spec_lum)
    shot_edges = edge_map(w, h, shot_lum)
    checks = [element_check(w, h, spec, shot, spec_edges, shot_edges, e, th) for e in elements]
    for element, check in zip(elements, checks):
        check["candidate"] = is_candidate(element)
    gating = {"checked": 0, "passed": 0, "failed": []}
    advisory = {"checked": 0, "passed": 0, "failed": []}
    for check in checks:
        bucket = advisory if check["candidate"] else gating
        bucket["checked"] += 1
        if check["pass"]:
            bucket["passed"] += 1
        else:
            bucket["failed"].append(check["id"])
    metrics = {
        "composition": {"score": round(comp, 4), "threshold": th["composition_min"],
                        "pass": comp >= th["composition_min"]},
        "color": {"distance": round(col, 4), "threshold": th["color_max"],
                  "pass": col <= th["color_max"]},
    }
    ok = metrics["composition"]["pass"] and metrics["color"]["pass"] \
        and not gating["failed"]
    return {
        "format": "uzu-spec-diff/1",
        "ok": bool(ok),
        "spec_image": os.path.abspath(spec_path),
        "shot": os.path.abspath(shot_path),
        "working_size": [w, h],
        "metrics": metrics,
        "gating": gating,
        "advisory": advisory,
        "elements": checks,
        "thresholds": th,
        "notes": notes,
    }


def main(argv):
    """Standalone, engine-free: spec_diff.py --spec-image A.png --shot B.png
    --report report.json [--registry spec_registry.json --scene res://scene.tscn]
    [--thresholds t.json] [--out verdict.json]."""
    def opt(name, default=""):
        for i, a in enumerate(argv):
            if a == "--" + name and i + 1 < len(argv):
                return argv[i + 1]
        return default
    spec_image, shot = opt("spec-image"), opt("shot")
    reg_path, scene_ref = opt("registry"), opt("scene")
    elements = []
    element_source = None
    if opt("report"):
        with open(opt("report"), encoding="utf-8") as f:
            elements = elements_from_report(json.load(f))
        element_source = "report"
    if reg_path:
        import spec_registry
        reg = spec_registry.load_registry(reg_path)
        binding = None
        if scene_ref:
            binding = spec_registry.get_scene_binding(reg, scene_ref)
        elif len(reg.get("scenes") or {}) == 1:
            only_scene = next(iter(reg["scenes"]))
            binding = spec_registry.get_scene_binding(reg, only_scene)
        elif spec_image:
            matches = spec_registry.find_scenes_for_image(reg, spec_image)
            if matches:
                binding = matches[0]
        if binding:
            if not spec_image and binding.get("spec_image_path"):
                base_dir = os.path.dirname(os.path.abspath(reg_path))
                spec_image = spec_registry.resolve_project_path(base_dir, binding["spec_image_path"])
            if not elements:
                elements = elements_from_registry(binding)
                element_source = "registry"
    if not spec_image or not shot:
        print(__doc__)
        return 2
    th = load_thresholds(opt("thresholds") or None)
    verdict = compare(spec_image, shot, elements, th)
    if element_source:
        verdict["element_source"] = element_source
    if opt("out"):
        with open(opt("out"), "w", encoding="utf-8") as f:
            json.dump(verdict, f, ensure_ascii=False, indent=2)
    print(json.dumps(verdict, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
