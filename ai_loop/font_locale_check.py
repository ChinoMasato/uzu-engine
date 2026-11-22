#!/usr/bin/env python3
"""Font locale check: Japanese punctuation position (BACKLOG B-1316).

Whether 、 (U+3001) and 。 (U+3002) sit low in the em square (Japanese
convention) or centred (TC / HK convention) is a property of the font
*face*, not of the text. The B-1311 / B-1313 look samples were captured
with the VM's system-font fallback, which resolved to the Noto Sans CJK
TC face, so their dialogue showed centred punctuation -- wrong for
Japanese -- and the mistake reached the owner before anyone noticed.
This check makes the property a number, so a font can be vetted before
it is used for a sample or shipped in a game.

Rule: for each of 、 and 。, the top of the glyph's ink (bounding box)
must lie in the lower half of the body band. The body band is measured
from the same font (the union of the ink bounds of the reference kana /
kanji below), never from fixed metrics, so the check follows the font's
own proportions. Measured separation is wide: JP faces put the ink top
at 0.33..0.36 of the band height, TC / HK faces at 0.65..0.67; the
threshold is 0.5.

    uzu.py font-locale-check <font.ttf|otf|ttc> [--face N] [--list-faces]
                             [--out report.json]

A TTC holds several faces; --face N selects one (default 0) and
--list-faces prints the face names so the right index can be found.
Exit code: 0 = pass, 1 = fail, 2 = usage / input error (including
fontTools missing). Needs fontTools (the same dependency as
make_game_font.py); no numpy / PIL.
"""

import argparse
import json
import sys

FORMAT = "uzu-font-locale-check/1"

# The glyphs whose vertical placement this check judges.
PUNCTUATION = (0x3001, 0x3002)
# Reference glyphs for the body band: common kana and kanji whose ink
# spans the full body height. Whichever of them the font has are used;
# a font with none of them cannot be judged (input error).
REFERENCE_CODEPOINTS = (
    0x3042, 0x3044, 0x3046, 0x3048, 0x304A,  # あ い う え お
    0x304B, 0x304D, 0x304F, 0x3051, 0x3053,  # か き く け こ
    0x6C38, 0x56FD, 0x65E5, 0x6728, 0x4EBA,  # 永 国 日 木 人
    0x5C71, 0x5DDD, 0x7530,                  # 山 川 田
)
# The punctuation ink top, as a fraction of the body band height
# (0 = band bottom, 1 = band top), must not exceed this.
TOP_FRACTION_MAX = 0.5


class FontLocaleError(Exception):
    pass


def _ink_bounds(glyph_set, glyph_name):
    """Ink bounding box (x_min, y_min, x_max, y_max) of one glyph, or
    None when the glyph draws nothing."""
    from fontTools.pens.boundsPen import BoundsPen

    pen = BoundsPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return pen.bounds


def measure_body_band(font):
    """Union of the ink bounds of the reference glyphs this font has.

    Returns {"y_min", "y_max", "reference_glyphs"} or None when the font
    has none of the reference glyphs."""
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    y_min = None
    y_max = None
    used = []
    for cp in REFERENCE_CODEPOINTS:
        if cp not in cmap:
            continue
        bounds = _ink_bounds(glyph_set, cmap[cp])
        if bounds is None:
            continue
        used.append("U+%04X" % cp)
        y_min = bounds[1] if y_min is None else min(y_min, bounds[1])
        y_max = bounds[3] if y_max is None else max(y_max, bounds[3])
    if not used:
        return None
    return {"y_min": y_min, "y_max": y_max, "reference_glyphs": used}


def judge_top_fraction(band, ink_y_max):
    """Position of a punctuation ink top inside the body band, as a
    fraction of the band height (0 = band bottom, 1 = band top)."""
    height = band["y_max"] - band["y_min"]
    if height <= 0:
        raise FontLocaleError("body band has no height")
    return (ink_y_max - band["y_min"]) / height


def check_font(font, source, face=0, face_name=None):
    """Run the punctuation-position check on an opened fontTools font."""
    band = measure_body_band(font)
    if band is None:
        raise FontLocaleError(
            "none of the reference kana/kanji glyphs is present; "
            "the body band cannot be measured (not a Japanese text font?)"
        )
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    checks = {}
    ok = True
    for cp in PUNCTUATION:
        entry = {"char": chr(cp)}
        if cp not in cmap:
            entry.update({"pass": False, "error": "glyph missing from the font"})
            ok = False
        else:
            bounds = _ink_bounds(glyph_set, cmap[cp])
            if bounds is None:
                entry.update({"pass": False, "error": "glyph has no ink"})
                ok = False
            else:
                fraction = judge_top_fraction(band, bounds[3])
                passed = fraction <= TOP_FRACTION_MAX
                entry.update({
                    "ink": {"y_min": bounds[1], "y_max": bounds[3]},
                    "top_fraction": round(fraction, 3),
                    "pass": passed,
                })
                ok = ok and passed
        checks["U+%04X" % cp] = entry
    return {
        "format": FORMAT,
        "ok": ok,
        "font": source,
        "face": face,
        "face_name": face_name,
        "body_band": {
            "y_min": band["y_min"],
            "y_max": band["y_max"],
            "reference_glyphs": band["reference_glyphs"],
        },
        "threshold": {"top_fraction_max": TOP_FRACTION_MAX},
        "checks": checks,
    }


def _face_name(font):
    try:
        return font["name"].getDebugName(4) or font["name"].getDebugName(1)
    except Exception:
        return None


def _is_ttc(path):
    with open(path, "rb") as f:
        return f.read(4) == b"ttcf"


def list_faces(path):
    """[{"index", "name"}] for every face in the file (one for a plain
    font file)."""
    from fontTools.ttLib import TTFont

    if _is_ttc(path):
        from fontTools.ttLib.ttCollection import TTCollection

        collection = TTCollection(path)
        return [{"index": i, "name": _face_name(f)} for i, f in enumerate(collection.fonts)]
    font = TTFont(path)
    return [{"index": 0, "name": _face_name(font)}]


def check_file(path, face=0):
    """Open a font file (TTC face selectable) and run the check."""
    from fontTools.ttLib import TTFont

    try:
        font = TTFont(path, fontNumber=face)
    except Exception as error:
        raise FontLocaleError("cannot open %s (face %d): %s" % (path, face, error))
    return check_font(font, path, face=face, face_name=_face_name(font))


def main(argv):
    parser = argparse.ArgumentParser(description="Japanese punctuation position check (B-1316)")
    parser.add_argument("font", nargs="?", help="font file (.ttf / .otf / .ttc)")
    parser.add_argument("--face", type=int, default=0, help="face index inside a TTC (default 0)")
    parser.add_argument("--list-faces", action="store_true", help="list the faces of the file and exit")
    parser.add_argument("--out", help="write the report JSON here too")
    a = parser.parse_args(argv)
    if not a.font:
        parser.print_usage(sys.stderr)
        return 2
    try:
        import fontTools  # noqa: F401
    except ImportError:
        print(json.dumps({"ok": False, "error": "fontTools is required: pip install fonttools"}, ensure_ascii=False))
        return 2
    try:
        if a.list_faces:
            report = {"ok": True, "font": a.font, "faces": list_faces(a.font)}
            print(json.dumps(report, ensure_ascii=False))
            return 0
        report = check_file(a.font, face=a.face)
    except FontLocaleError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 2
    except OSError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 2
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
