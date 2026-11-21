#!/usr/bin/env python3
"""UI quality gate (B-1310): score a UZUUI theme + sample screenshots against
the AAA bar defined in the 2026-11-22 UI quality audit, as numbers in one JSON
report (format uzu-ui-quality/1). The gate is a measuring stick, not a taste
judgement; the current themes are expected to FAIL it (that is the point --
B-1311..B-1315 fix what it detects).

Checks:
  1. texture_repetition -- normalised autocorrelation peak of the panel area
     of each screenshot (luminance and red-excess channels). A tiled texture
     whose period is visible -- e.g. the wafu ornament dots leaking into a
     grid over the whole panel -- produces a strong peak at the tile lag.
  2. contrast -- WCAG relative-luminance ratios of theme text colours against
     the panel / button fills sampled by the probe. Body >= 4.5, heading >= 3.0.
  3. state_completeness -- Button must carry normal/hover/pressed/disabled/
     focus styleboxes, none of them StyleBoxEmpty, and hover/pressed/focus
     must be visually distinguishable from normal. (The current themes set
     focus to StyleBoxEmpty: keyboard/gamepad focus is invisible.)
  4. coverage -- fraction of the standard control types that carry a world
     stylebox in the theme. Must be 1.0 (no default-Godot-looking parts).
  5. scale -- spacing (content margins, separation), corner radii and shadow
     sizes must come from the scale sets below, not ad-hoc values.

Theme data comes from a probe JSON produced by ai_loop/ui_quality_probe.gd
(--probe), or by running the engine here (--engine PATH [--godot-project DIR]).
Exit code: 0 = pass, 1 = fail, 2 = usage/input error.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FORMAT = "uzu-ui-quality/1"
PROBE_FORMAT = "uzu-ui-probe/1"

# The standard control surface a game UI is built from (audit item 4).
STANDARD_TYPES = [
    "PanelContainer", "Button", "CheckBox", "OptionButton", "HSlider", "VSlider",
    "LineEdit", "SpinBox", "HScrollBar", "VScrollBar", "PopupMenu", "Tree",
    "TabContainer", "ItemList", "ProgressBar", "TooltipPanel",
]
BUTTON_STATES = ["normal", "hover", "pressed", "disabled", "focus"]

SPACING_SCALE = {0, 4, 8, 12, 16, 24, 32, 48, 64}
RADIUS_SCALE = {0, 2, 4, 6, 8, 12, 16, 24, 32}
SHADOW_SCALE = {0, 4, 8, 12, 16, 24, 32}

BODY_CONTRAST_MIN = 4.5
HEADING_CONTRAST_MIN = 3.0
# Repetition is judged on autocorrelation peaks at tile-like lags (40..300 px
# in the original screenshot). Short lags correlate in any natural texture;
# a tiled texture's correlation resurges at the tile period -- e.g. the wafu
# frame tile is 128 px and the leaked ornament dots peak at lag 126 with 0.42
# in the red-excess channel of the current dialogue capture, while a natural
# 3D ground crop stays at 0.26 in the same band.
REPETITION_MAX = 0.30
REPETITION_LAG_MIN = 40
REPETITION_LAG_MAX = 300


# ---------------------------------------------------------------- images

def _autocorr_peak(channel, lag_min, lag_max):
    """Strongest normalised autocorrelation at lag distance in
    [lag_min, lag_max] (FFT based). The channel is high-passed first so a
    smooth gradient or vignette cannot masquerade as repetition.
    Returns (peak, (dx, dy)). A flat channel scores 0."""
    import numpy as np
    from PIL import Image, ImageFilter

    a = channel.astype(np.float64)
    lo = float(a.min())
    hi = float(a.max())
    if hi - lo <= 1e-9:
        return 0.0, (0, 0)
    u8 = ((a - lo) / (hi - lo) * 255.0).astype(np.uint8)
    blur = Image.fromarray(u8).filter(ImageFilter.GaussianBlur(4))
    a = a - np.asarray(blur).astype(np.float64) * ((hi - lo) / 255.0)
    a -= a.mean()
    if float((a * a).sum()) <= 1e-9:
        return 0.0, (0, 0)
    f = np.fft.rfft2(a)
    corr = np.fft.irfft2(f * np.conj(f), s=a.shape)
    corr /= corr[0, 0]
    h, w = corr.shape
    ys, xs = np.mgrid[0 : h // 2 + 1, 0 : w // 2 + 1]
    dist = np.sqrt(xs**2 + ys**2)
    region = corr[: h // 2 + 1, : w // 2 + 1].copy()
    region[(dist < lag_min) | (dist > lag_max)] = -1.0
    idx = int(np.argmax(region))
    dy, dx = np.unravel_index(idx, region.shape)
    return float(region[dy, dx]), (int(dx), int(dy))


def texture_repetition(image_path, region=None, max_side=512):
    """Repetition index of one screenshot (optionally cropped to a panel
    region x,y,w,h). Two channels: luminance and red excess (vermillion
    ornament dots on parchment are strongest in the second)."""
    import numpy as np
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    if region:
        x, y, w, h = region
        img = img.crop((x, y, x + w, y + h))
    scale = 1.0
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((max(8, int(img.size[0] * scale)), max(8, int(img.size[1] * scale))))
    a = np.asarray(img).astype(np.float64)
    lum = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    red = a[:, :, 0] - 0.5 * (a[:, :, 1] + a[:, :, 2])
    lag_min = max(2, int(round(REPETITION_LAG_MIN * scale)))
    lag_max = max(lag_min + 1, int(round(REPETITION_LAG_MAX * scale)))
    results = {}
    worst = 0.0
    worst_lag = (0, 0)
    for name, channel in (("luminance", lum), ("red_excess", red)):
        peak, (dx, dy) = _autocorr_peak(channel, lag_min, lag_max)
        results[name] = {"peak": round(peak, 4), "lag_px": [round(dx / scale), round(dy / scale)]}
        if peak > worst:
            worst, worst_lag = peak, results[name]["lag_px"]
    return {
        "image": os.path.basename(image_path),
        "index": round(worst, 4),
        "worst_lag_px": worst_lag,
        "channels": results,
        "threshold": REPETITION_MAX,
        "lag_band_px": [REPETITION_LAG_MIN, REPETITION_LAG_MAX],
        "pass": worst <= REPETITION_MAX,
    }


# ---------------------------------------------------------------- contrast

def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    r, g, b = (_lin(min(1.0, max(0.0, float(v)))) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg):
    """WCAG contrast ratio. A translucent bg is composited over black and
    over white and the worse ratio wins (the game behind it is unknown)."""
    def lum_over(base):
        a = bg[3] if len(bg) > 3 else 1.0
        comp = [bg[i] * a + base[i] * (1.0 - a) for i in range(3)]
        return relative_luminance(comp)

    fa = fg[3] if len(fg) > 3 else 1.0
    worst = None
    for base in ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)):
        back = lum_over(base)
        fore = relative_luminance([fg[i] * fa + base[i] * (1.0 - fa) for i in range(3)])
        hi, lo = max(fore, back), min(fore, back)
        ratio = (hi + 0.05) / (lo + 0.05)
        worst = ratio if worst is None else min(worst, ratio)
    return worst


def _fill_of(stylebox):
    """The colour a stylebox paints its middle with, as sampled by the probe."""
    if not stylebox:
        return None
    if "center_color" in stylebox:
        return stylebox["center_color"]
    if "bg_color" in stylebox:
        return stylebox["bg_color"]
    return None


def check_contrast(theme):
    types = theme.get("types", {})
    pairs = []

    def add(name, fg_type, fg_name, bg_type, bg_box, minimum):
        fg = types.get(fg_type, {}).get("colors", {}).get(fg_name)
        bg = _fill_of(types.get(bg_type, {}).get("styleboxes", {}).get(bg_box))
        if fg is None or bg is None:
            pairs.append({"pair": name, "pass": False, "reason": "missing colour data"})
            return
        ratio = contrast_ratio(fg, bg)
        pairs.append({
            "pair": name, "ratio": round(ratio, 3), "min": minimum,
            "fg": [round(v, 4) for v in fg], "bg": [round(v, 4) for v in bg],
            "pass": ratio >= minimum,
        })

    add("body: Label text on panel", "Label", "font_color", "PanelContainer", "panel", BODY_CONTRAST_MIN)
    add("heading: Button text on button", "Button", "font_color", "Button", "normal", HEADING_CONTRAST_MIN)
    return {"pass": all(p["pass"] for p in pairs), "pairs": pairs,
            "body_min": BODY_CONTRAST_MIN, "heading_min": HEADING_CONTRAST_MIN}


# ---------------------------------------------------------------- states / coverage / scale

def _signature(stylebox):
    if stylebox is None:
        return None
    return json.dumps(stylebox, sort_keys=True)


def check_states(theme):
    boxes = theme.get("types", {}).get("Button", {}).get("styleboxes", {})
    states = {}
    for state in BUTTON_STATES:
        sb = boxes.get(state)
        if sb is None:
            states[state] = {"present": False, "pass": False, "reason": "no stylebox"}
        elif sb.get("class") == "StyleBoxEmpty":
            states[state] = {"present": True, "pass": False, "reason": "StyleBoxEmpty (invisible)"}
        else:
            states[state] = {"present": True, "pass": True, "class": sb.get("class")}
    normal = _signature(boxes.get("normal"))
    for state in ("hover", "pressed", "focus"):
        if states[state]["pass"] and normal is not None and _signature(boxes.get(state)) == normal:
            states[state]["pass"] = False
            states[state]["reason"] = "identical to normal (not distinguishable)"
    return {"pass": all(s["pass"] for s in states.values()), "states": states}


def check_coverage(theme):
    types = theme.get("types", {})
    covered, missing = [], []
    for type_name in STANDARD_TYPES:
        if types.get(type_name, {}).get("styleboxes"):
            covered.append(type_name)
        else:
            missing.append(type_name)
    ratio = len(covered) / len(STANDARD_TYPES)
    return {"pass": ratio >= 1.0, "ratio": round(ratio, 4),
            "covered": covered, "missing": missing}


def _num(v):
    return int(v) if float(v) == int(v) else float(v)


def check_scale(theme):
    spacing, radii, shadows = [], [], []  # (where, value); one entry per distinct value
    for type_name, td in theme.get("types", {}).items():
        for box_name, sb in td.get("styleboxes", {}).items():
            where = f"{type_name}.{box_name}"
            for v in sorted({v for v in sb.get("content_margins", []) if v >= 0}):
                spacing.append((where + " content_margin", _num(v)))
            for v in sorted({v for v in sb.get("expand_margins", []) if v > 0}):
                shadows.append((where + " expand_margin(shadow)", _num(v)))
            for v in sorted(set(sb.get("corner_radius", []))):
                radii.append((where + " corner_radius", _num(v)))
            if sb.get("shadow_size"):
                shadows.append((where + " shadow_size", _num(sb["shadow_size"])))
        for name, v in td.get("constants", {}).items():
            if "separation" in name or "margin" in name:
                spacing.append((f"{type_name}.{name}", _num(v)))
    options = theme.get("options", {})
    for section in ("frame", "button", "panel"):
        sec = options.get(section)
        if isinstance(sec, dict):
            if "radius" in sec:
                radii.append((f"options.{section}.radius", _num(sec["radius"])))
            if "shadow" in sec:
                shadows.append((f"options.{section}.shadow", _num(sec["shadow"])))
            if "padding" in sec:
                spacing.append((f"options.{section}.padding", _num(sec["padding"])))

    def off(values, scale):
        return [{"where": w, "value": v} for w, v in values if v not in scale]

    result = {
        "spacing_off_scale": off(spacing, SPACING_SCALE),
        "radius_off_scale": off(radii, RADIUS_SCALE),
        "shadow_off_scale": off(shadows, SHADOW_SCALE),
        "counts": {"spacing": len(spacing), "radius": len(radii), "shadow": len(shadows)},
    }
    result["pass"] = not (result["spacing_off_scale"] or result["radius_off_scale"] or result["shadow_off_scale"])
    return result


# ---------------------------------------------------------------- probe runner

def run_probe(engine, project=None):
    """Run ui_quality_probe.gd with the engine binary in a scratch project and
    return the parsed probe JSON."""
    tmp = tempfile.mkdtemp(prefix="uzu-ui-quality-")
    proj = project or tmp
    if project is None:
        with open(os.path.join(proj, "project.godot"), "w", encoding="utf-8") as f:
            f.write('; Engine configuration file.\nconfig_version=5\n\n[application]\nconfig/name="uzu-ui-quality-probe"\n')
    out = os.path.join(tmp, "probe.json")
    cmd = [engine, "--headless", "--path", proj, "--script",
           os.path.join(HERE, "ui_quality_probe.gd"), "--", out]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"probe failed (rc={proc.returncode}): {proc.stdout[-2000:]} {proc.stderr[-2000:]}")
    with open(out, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- main

def build_report(probe, theme_name, images, region=None):
    themes = probe.get("themes", {})
    if theme_name not in themes:
        raise ValueError(f"theme '{theme_name}' not in probe (have: {', '.join(sorted(themes))})")
    theme = themes[theme_name]
    checks = {}
    if images:
        per_image = [texture_repetition(p, region) for p in images]
        checks["texture_repetition"] = {
            "pass": all(r["pass"] for r in per_image), "images": per_image}
    else:
        checks["texture_repetition"] = {"pass": False, "reason": "no screenshot given"}
    checks["contrast"] = check_contrast(theme)
    checks["state_completeness"] = check_states(theme)
    checks["coverage"] = check_coverage(theme)
    checks["scale"] = check_scale(theme)
    verdict = "pass" if all(c["pass"] for c in checks.values()) else "fail"
    return {"format": FORMAT, "theme": theme_name, "verdict": verdict, "checks": checks}


def main(argv=None):
    ap = argparse.ArgumentParser(description="U.ZU Engine UI quality gate (B-1310)")
    ap.add_argument("--probe", help="probe JSON from ai_loop/ui_quality_probe.gd")
    ap.add_argument("--engine", help="engine binary; runs the probe when --probe is absent")
    ap.add_argument("--theme", default="wafu", help="theme to score (default wafu; 'default' = create_theme)")
    ap.add_argument("--image", action="append", default=[], help="sample screenshot PNG (repeatable)")
    ap.add_argument("--region", help="panel crop x,y,w,h applied to every --image")
    ap.add_argument("--out", help="write the report JSON here (default: stdout)")
    args = ap.parse_args(argv)

    try:
        if args.probe:
            with open(args.probe, encoding="utf-8") as f:
                probe = json.load(f)
        elif args.engine:
            probe = run_probe(args.engine)
        else:
            ap.error("give --probe FILE or --engine PATH")
            return 2
        if probe.get("format") != PROBE_FORMAT:
            raise ValueError(f"probe format is {probe.get('format')!r}, expected {PROBE_FORMAT!r}")
        region = None
        if args.region:
            region = tuple(int(v) for v in args.region.split(","))
            if len(region) != 4:
                raise ValueError("--region must be x,y,w,h")
        report = build_report(probe, args.theme, args.image, region)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as e:
        print(f"ui_quality: error: {e}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
