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
     Two structural pairs are scored the same way (B-1315): the slider groove
     against the panel and the slider fill against the groove, >= 2.0 each --
     a track you cannot see is a state you cannot read.
  3. state_completeness -- Button must carry normal/hover/pressed/disabled/
     focus styleboxes, none of them StyleBoxEmpty, and hover/pressed/focus
     must be visually distinguishable from normal. (The current themes set
     focus to StyleBoxEmpty: keyboard/gamepad focus is invisible.)
  4. coverage -- fraction of the standard control types that carry a world
     stylebox in the theme. Must be 1.0 (no default-Godot-looking parts).
  5. scale -- spacing (content margins, separation), corner radii and shadow
     sizes must come from the scale sets below, not ad-hoc values.
  6. texture_sheet -- check 1 asked of a texture on its own, rendered as an
     empty panel sheet at native resolution (B-1315). A designed micro
     pattern (persona's halftone grid, period <= 24 px) is judged by the
     residue its period cannot explain -- the band correlation's deviation
     from the period-folded prediction (<= 0.30) -- plus the uniformity of
     its period cells; an unpatterned material is judged by a visibility index,
     the band peak weighted by how much the channel varies at all
     (min(1, std/20)) -- correlation alone is blind to amplitude, and the
     audit's bar is repetition a viewer cannot *perceive*. The frame's
     centre slice (the part that actually repeats) must also carry no
     alpha hole: a wedge-shaped gap fails outright, however it repeats.
  7. containment -- every control inside a panel stays within the panel's
     safe area (the stylebox content rect, narrowed for a skew frame by
     the slant at the control's own rows), at rest and at the peak phase
     of the screen's motions. Data: ai_loop/ui_containment_probe.gd
     (--containment), run against the sample screens.

Theme data comes from a probe JSON produced by ai_loop/ui_quality_probe.gd
(--probe), or by running the engine here (--engine PATH [--godot-project DIR]).
Exit code: 0 = pass, 1 = fail, 2 = usage/input error.
"""

import argparse
import cmath
import json
import math
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

# The slider's structural pairs (B-1315): below this the groove merges with
# the panel or the fill merges with the groove at a glance.
SLIDER_CONTRAST_MIN = 2.0

# Texture-sheet measurement (B-1315). A designed pattern's period is at most
# this many px (the halftone pitch is a style parameter since B-1321 --
# halftone_cells; persona uses a 4 px cell); anything longer is texture,
# not print. The residue and visibility bars are the audit's 0.30, unchanged.
SHEET_PERIOD_MAX = 24
SHEET_RESIDUE_MAX = 0.30
SHEET_VISIBILITY_MAX = 0.30
# Channel std (0..255) at which variation counts as fully visible; below it
# the visibility index scales down linearly.
SHEET_STD_FULL = 20.0
# A designed pattern's period cells may drift this far, relative to the
# channel's own scale, before the grid counts as non-uniform.
SHEET_UNIFORMITY_MAX = 0.6


# ---------------------------------------------------------------- images

def _next_pow2(n):
    p = 1
    while p < n:
        p <<= 1
    return p


def _fft_1d(a):
    """Iterative radix-2 FFT, in place, on a list of complex (length a power of 2)."""
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        wlen = cmath.exp(-2j * cmath.pi / length)
        half = length // 2
        for i in range(0, n, length):
            w = 1 + 0j
            for k in range(half):
                u = a[i + k]
                v = a[i + k + half] * w
                a[i + k] = u + v
                a[i + k + half] = u - v
                w *= wlen
        length <<= 1
    return a


def _fft2(a):
    """2D FFT of rows of complex (any size; zero-padded to powers of 2)."""
    h = len(a)
    w = len(a[0])
    H = _next_pow2(h)
    W = _next_pow2(w)
    rows = [[complex(a[y][x]) if y < h and x < w else 0j for x in range(W)] for y in range(H)]
    for y in range(H):
        _fft_1d(rows[y])
    for x in range(W):
        col = [rows[y][x] for y in range(H)]
        _fft_1d(col)
        for y in range(H):
            rows[y][x] = col[y]
    return rows


def _ifft2(F):
    """Inverse 2D FFT via the conjugate trick."""
    H = len(F)
    W = len(F[0])
    conj = [[v.conjugate() for v in row] for row in F]
    out = _fft2(conj)
    return [[v.conjugate() / (H * W) for v in row] for row in out]


def _autocorr_peak_stdlib(a, lag_min, lag_max):
    """Autocorrelation peak via the stdlib FFT (same maths as the numpy path,
    slower). a is rows of float, already high-passed and mean-removed."""
    F = _fft2(a)
    P = [[v * v.conjugate() for v in row] for row in F]
    corr = _ifft2(P)
    c00 = corr[0][0].real
    if c00 <= 1e-12:
        return 0.0, (0, 0)
    h = len(a)
    w = len(a[0])
    best = -1.0
    best_lag = (0, 0)
    for dy in range(0, h // 2 + 1):
        for dx in range(0, w // 2 + 1):
            dist = math.hypot(dx, dy)
            if dist < lag_min or dist > lag_max:
                continue
            val = corr[dy][dx].real / c00
            if val > best:
                best, best_lag = val, (dx, dy)
    return best, best_lag


def _prep_autocorr(channel):
    """High-pass and mean-remove a channel for autocorrelation, so a smooth
    gradient or vignette cannot masquerade as repetition. Returns the
    prepared rows, or None when the channel carries no variation."""
    from PIL import Image, ImageFilter

    h = len(channel)
    w = len(channel[0])
    flat = [v for row in channel for v in row]
    lo = min(flat)
    hi = max(flat)
    if hi - lo <= 1e-9:
        return None
    u8 = Image.new("L", (w, h))
    u8.putdata([round((v - lo) / (hi - lo) * 255.0) for v in flat])
    blur = u8.filter(ImageFilter.GaussianBlur(4))
    blur_px = list(blur.getdata())
    scale = (hi - lo) / 255.0
    a = [[channel[y][x] - blur_px[y * w + x] * scale for x in range(w)] for y in range(h)]
    mean = sum(sum(row) for row in a) / (h * w)
    a = [[v - mean for v in row] for row in a]
    if sum(v * v for row in a for v in row) <= 1e-9:
        return None
    return a


def _autocorr_peak(channel, lag_min, lag_max, _force_stdlib=False):
    """Strongest normalised autocorrelation at lag distance in
    [lag_min, lag_max] (FFT based). Returns (peak, (dx, dy)). A flat
    channel scores 0. numpy is used when available; otherwise a stdlib
    FFT computes the same values (slower), so the gate also runs on
    runners without numpy."""
    a = _prep_autocorr(channel)
    if a is None:
        return 0.0, (0, 0)
    if not _force_stdlib:
        try:
            import numpy as np
        except ImportError:
            return _autocorr_peak_stdlib(a, lag_min, lag_max)
        arr = np.asarray(a, dtype=np.float64)
        f = np.fft.rfft2(arr)
        corr = np.fft.irfft2(f * np.conj(f), s=arr.shape)
        corr /= corr[0, 0]
        ch, cw = corr.shape
        ys, xs = np.mgrid[0 : ch // 2 + 1, 0 : cw // 2 + 1]
        dist = np.sqrt(xs**2 + ys**2)
        region = corr[: ch // 2 + 1, : cw // 2 + 1].copy()
        region[(dist < lag_min) | (dist > lag_max)] = -1.0
        idx = int(np.argmax(region))
        dy, dx = np.unravel_index(idx, region.shape)
        return float(region[dy, dx]), (int(dx), int(dy))
    return _autocorr_peak_stdlib(a, lag_min, lag_max)


def texture_repetition(image_path, region=None, max_side=512):
    """Repetition index of one screenshot (optionally cropped to a panel
    region x,y,w,h). Two channels: luminance and red excess (vermillion
    ornament dots on parchment are strongest in the second)."""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    if region:
        x, y, w, h = region
        img = img.crop((x, y, x + w, y + h))
    scale = 1.0
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((max(8, int(img.size[0] * scale)), max(8, int(img.size[1] * scale))))
    w, h = img.size
    pix = list(img.getdata())
    lum = [[0.2126 * pix[y * w + x][0] + 0.7152 * pix[y * w + x][1] + 0.0722 * pix[y * w + x][2] for x in range(w)] for y in range(h)]
    red = [[pix[y * w + x][0] - 0.5 * (pix[y * w + x][1] + pix[y * w + x][2]) for x in range(w)] for y in range(h)]
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


def _autocorr_grid(a, max_lag):
    """Normalised autocorrelation A[dy][dx] of a prepared channel for
    0 <= dx, dy <= max_lag (same FFT maths as _autocorr_peak)."""
    try:
        import numpy as np
    except ImportError:
        return _autocorr_grid_stdlib(a, max_lag)
    arr = np.asarray(a, dtype=np.float64)
    f = np.fft.rfft2(arr)
    corr = np.fft.irfft2(f * np.conj(f), s=arr.shape)
    corr /= corr[0, 0]
    return [[float(corr[dy, dx]) for dx in range(max_lag + 1)] for dy in range(max_lag + 1)]


def _autocorr_grid_stdlib(a, max_lag):
    F = _fft2(a)
    P = [[v * v.conjugate() for v in row] for row in F]
    corr = _ifft2(P)
    c00 = corr[0][0].real
    if c00 <= 1e-12:
        return [[0.0] * (max_lag + 1) for _ in range(max_lag + 1)]
    return [[corr[dy][dx].real / c00 for dx in range(max_lag + 1)] for dy in range(max_lag + 1)]


def _detect_period(axis):
    """The fundamental period of one axis' autocorrelation (axis[d] for
    d = 0..N), or None. A designed micro-pattern's correlation forms a
    comb: a local peak of at least 0.5 at the period, again at twice the
    period, standing at least 0.15 above the trough before it. The comb
    test matters: wide dots in a narrow cell correlate almost as well one
    px short of the period (a shoulder, A(7) = 0.65 for an 8 px cell),
    but the shoulder has no peak at its double. A smooth material's
    correlation only decays, so it never qualifies."""
    n = len(axis)
    for d in range(3, min(SHEET_PERIOD_MAX, n - 2) + 1):
        if axis[d] < 0.5:
            continue
        if axis[d] < axis[d - 1] or axis[d] < axis[d + 1]:
            continue  # A shoulder of the true period, not its peak.
        if 2 * d < n and axis[2 * d] < 0.5:
            continue  # The comb must continue at the double lag.
        if axis[d] - min(axis[1:d]) < 0.15:
            continue  # No resurgence: a decaying correlation's tail.
        return d
    return None


def _cell_uniformity(channel, period, axis):
    """Spread of the per-period cell means along one axis, relative to the
    channel's own scale. A uniform grid has the same ink in every period
    cell; a pattern that fades, breaks off or is interrupted drifts."""
    h = len(channel)
    w = len(channel[0])
    flat = [v for row in channel for v in row]
    mean = sum(flat) / len(flat)
    std = math.sqrt(sum((v - mean) ** 2 for v in flat) / len(flat))
    means = []
    if axis == 0:
        for j in range(w // period):
            vals = [channel[y][x] for y in range(h) for x in range(j * period, (j + 1) * period)]
            means.append(sum(vals) / len(vals))
    else:
        for j in range(h // period):
            vals = [channel[y][x] for y in range(j * period, (j + 1) * period) for x in range(w)]
            means.append(sum(vals) / len(vals))
    if not means:
        return 0.0
    return (max(means) - min(means)) / max(abs(mean), std, 1.0)


def _sheet_channel(channel):
    """Score one channel of a texture sheet. Two ways to pass, by what the
    material is (see the module docstring): a designed pattern is judged
    on residue + uniformity, anything else on the visibility index."""
    h = len(channel)
    w = len(channel[0])
    flat = [v for row in channel for v in row]
    mean = sum(flat) / len(flat)
    std = math.sqrt(sum((v - mean) ** 2 for v in flat) / len(flat))
    out = {"std": round(std, 3)}
    a = _prep_autocorr(channel)
    if a is None:
        out.update({"mode": "flat", "index": 0.0, "pass": True})
        return out
    max_lag = int(min(REPETITION_LAG_MAX, min(w, h) - 1))
    grid = _autocorr_grid(a, max_lag)
    band_peak, band_lag = 0.0, [0, 0]
    for dy in range(max_lag + 1):
        for dx in range(max_lag + 1):
            dist = math.hypot(dx, dy)
            if REPETITION_LAG_MIN <= dist <= REPETITION_LAG_MAX and grid[dy][dx] > band_peak:
                band_peak, band_lag = grid[dy][dx], [dx, dy]
    out["band_peak"] = round(band_peak, 4)
    out["band_lag_px"] = band_lag
    px = _detect_period([grid[0][d] for d in range(max_lag + 1)])
    py = _detect_period([grid[d][0] for d in range(max_lag + 1)])
    if px or py:
        # Residue: how far the band correlation strays from what the
        # period itself predicts. A perfectly periodic texture's
        # correlation depends only on the lag modulo the period (wide
        # dots correlate at period-1 too -- that shoulder is the
        # pattern's own footprint, not an artifact), so the prediction
        # for a lag is the correlation at the folded lag. A moire
        # (TILE_FIT rescaling beating against the grid) drifts in phase
        # as the lag grows and strays far from the fold, even though the
        # grid itself is perfect.
        residue = 0.0
        for dy in range(max_lag + 1):
            for dx in range(max_lag + 1):
                dist = math.hypot(dx, dy)
                if not (REPETITION_LAG_MIN <= dist <= REPETITION_LAG_MAX):
                    continue
                fx = dx % px if px else dx
                fy = dy % py if py else dy
                residue = max(residue, abs(grid[dy][dx] - grid[fy][fx]))
        uniformity = 0.0
        if px:
            uniformity = max(uniformity, _cell_uniformity(channel, px, 0))
        if py:
            uniformity = max(uniformity, _cell_uniformity(channel, py, 1))
        out.update({
            "mode": "pattern", "period_px": [px, py],
            "residue": round(residue, 4), "uniformity": round(uniformity, 4),
            "index": round(residue, 4),
            "pass": residue <= SHEET_RESIDUE_MAX and uniformity <= SHEET_UNIFORMITY_MAX,
        })
        return out
    visibility = band_peak * min(1.0, std / SHEET_STD_FULL)
    out.update({"mode": "visibility", "visibility": round(visibility, 4),
                "index": round(visibility, 4), "pass": visibility <= SHEET_VISIBILITY_MAX})
    return out


def texture_repetition_sheet(image_path, region=None, max_side=512):
    """Repetition of a texture on its own: an empty-panel sheet rendered
    at native resolution (no rescale -- rescaling would hide exactly the
    periodicity being measured, and invent moire that is not in the
    texture). The centre window of at most max_side px is scored."""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    if region:
        x, y, w, h = region
        img = img.crop((x, y, x + w, y + h))
    w, h = img.size
    if w > max_side or h > max_side:
        cw, ch = min(w, max_side), min(h, max_side)
        img = img.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2))
        w, h = img.size
    pix = list(img.getdata())
    lum = [[0.2126 * pix[y * w + x][0] + 0.7152 * pix[y * w + x][1] + 0.0722 * pix[y * w + x][2] for x in range(w)] for y in range(h)]
    red = [[pix[y * w + x][0] - 0.5 * (pix[y * w + x][1] + pix[y * w + x][2]) for x in range(w)] for y in range(h)]
    channels = {}
    worst = 0.0
    for name, channel in (("luminance", lum), ("red_excess", red)):
        channels[name] = _sheet_channel(channel)
        worst = max(worst, channels[name]["index"])
    return {
        "image": os.path.basename(image_path),
        "window_px": [w, h],
        "index": round(worst, 4),
        "threshold": SHEET_RESIDUE_MAX,
        "channels": channels,
        "pass": all(c["pass"] for c in channels.values()),
    }


def texture_coverage(theme):
    """Frame coverage: the panel frame's centre slice -- the part of the
    texture that actually repeats across a panel -- must not contain an
    alpha hole: a local collapse of opacity, judged against the slice's
    own mean (a glass panel is translucent everywhere by design and
    passes; the B-1318 skew wedge was a fully transparent seam in an
    opaque frame and fails). The wedge was invisible to correlation --
    it repeated perfectly; it is exactly an alpha hole here. Data comes
    from the probe's centre-slice alpha sampling."""
    types = theme.get("types", {})
    sb = types.get("PanelContainer", {}).get("styleboxes", {}).get("panel")
    if not sb:
        return {"pass": False, "reason": "no panel stylebox"}
    if "center_alpha_min" in sb:
        amin = sb["center_alpha_min"]
        amean = sb.get("center_alpha_mean", amin)
        return {"pass": amean > 0.0 and amin >= 0.5 * amean,
                "center_alpha_min": round(amin, 4), "center_alpha_mean": round(amean, 4)}
    if "bg_color" in sb:  # A flat panel paints its colour everywhere.
        alpha = sb["bg_color"][3] if len(sb["bg_color"]) > 3 else 1.0
        return {"pass": alpha > 0.0, "center_alpha_min": round(alpha, 4),
                "center_alpha_mean": round(alpha, 4)}
    return {"pass": False, "reason": "no frame coverage data in probe"}


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

    def add_fill(name, fg_type, fg_box, bg_type, bg_box, minimum):
        fg = _fill_of(types.get(fg_type, {}).get("styleboxes", {}).get(fg_box))
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
    # Structural pairs (B-1315): the slider's groove sits on the panel and
    # its fill travels inside the groove; both fills come from the built
    # styleboxes, like the text pairs.
    add_fill("slider groove on panel", "HSlider", "slider", "PanelContainer", "panel", SLIDER_CONTRAST_MIN)
    add_fill("slider fill on groove", "HSlider", "grabber_area", "HSlider", "slider", SLIDER_CONTRAST_MIN)
    return {"pass": all(p["pass"] for p in pairs), "pairs": pairs,
            "body_min": BODY_CONTRAST_MIN, "heading_min": HEADING_CONTRAST_MIN,
            "slider_min": SLIDER_CONTRAST_MIN}


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


def check_containment(data):
    """Containment (B-1315, owner rule): every control inside a panel
    stays within the panel's safe area -- at rest and at the peak phase
    of the screen's motions. Data comes from ai_loop/ui_containment_probe.gd
    run against the sample project; the probe has already applied the
    skew narrowing, so this only reads its verdicts."""
    if data.get("format") != "uzu-ui-containment/1":
        return {"pass": False, "reason": f"containment format is {data.get('format')!r}"}
    screens = {}
    for name, s in sorted(data.get("screens", {}).items()):
        screens[name] = {
            "pass": bool(s.get("pass")),
            "rest_violations": len(s.get("rest", [])),
            "peak_violations": len(s.get("peak", [])),
            "violations": (s.get("rest", []) + s.get("peak", []))[:8],
        }
    return {"pass": all(s["pass"] for s in screens.values()) and bool(screens),
            "screens": screens}


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

def build_report(probe, theme_name, images, region=None, texture_images=None, texture_region=None,
                 containment=None):
    themes = probe.get("themes", {})
    if theme_name not in themes:
        raise ValueError(f"theme '{theme_name}' not in probe (have: {', '.join(sorted(themes))})")
    theme = themes[theme_name]
    checks = {}
    if texture_images:
        # B-1315: when empty-panel sheets are the texture evidence, the
        # sheet measurement replaces the screenshot one -- it scores the
        # material at native resolution and can tell a designed pattern
        # from a tiling artifact, which the screenshot peak cannot.
        sheets = [texture_repetition_sheet(p, texture_region) for p in texture_images]
        coverage = texture_coverage(theme)
        checks["texture_sheet"] = {
            "pass": all(s["pass"] for s in sheets) and coverage["pass"],
            "sheets": sheets, "coverage": coverage}
    if images:
        per_image = [texture_repetition(p, region) for p in images]
        checks["texture_repetition"] = {
            "pass": all(r["pass"] for r in per_image), "images": per_image}
    elif not texture_images:
        checks["texture_repetition"] = {"pass": False, "reason": "no screenshot given"}
    checks["contrast"] = check_contrast(theme)
    checks["state_completeness"] = check_states(theme)
    checks["coverage"] = check_coverage(theme)
    checks["scale"] = check_scale(theme)
    if containment is not None:
        checks["containment"] = check_containment(containment)
    verdict = "pass" if all(c["pass"] for c in checks.values()) else "fail"
    return {"format": FORMAT, "theme": theme_name, "verdict": verdict, "checks": checks}


def main(argv=None):
    ap = argparse.ArgumentParser(description="U.ZU Engine UI quality gate (B-1310)")
    ap.add_argument("--probe", help="probe JSON from ai_loop/ui_quality_probe.gd")
    ap.add_argument("--engine", help="engine binary; runs the probe when --probe is absent")
    ap.add_argument("--theme", default="wafu", help="theme to score (default wafu; 'default' = create_theme)")
    ap.add_argument("--image", action="append", default=[], help="sample screenshot PNG (repeatable)")
    ap.add_argument("--region", help="panel crop x,y,w,h applied to every --image")
    ap.add_argument("--texture-image", action="append", default=[],
                    help="empty-panel sheet PNG for the texture-sheet check (repeatable)")
    ap.add_argument("--texture-region", help="interior crop x,y,w,h applied to every --texture-image")
    ap.add_argument("--containment", help="containment JSON from ai_loop/ui_containment_probe.gd")
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
        texture_region = None
        if args.texture_region:
            texture_region = tuple(int(v) for v in args.texture_region.split(","))
            if len(texture_region) != 4:
                raise ValueError("--texture-region must be x,y,w,h")
        containment = None
        if args.containment:
            with open(args.containment, encoding="utf-8") as f:
                containment = json.load(f)
        report = build_report(probe, args.theme, args.image, region,
                              texture_images=args.texture_image, texture_region=texture_region,
                              containment=containment)
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
