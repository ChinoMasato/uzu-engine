import json
import subprocess
import sys
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))

import font_locale_check  # noqa: E402

GAME_FONT = LOOP / "samples" / "hikari" / "art" / "game_font.ttf"
NOTO_TTC = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")

try:
    import fontTools  # noqa: F401

    HAVE_FONTTOOLS = True
except ImportError:
    HAVE_FONTTOOLS = False


def find_face(path, suffix, exact):
    """Face index of a TTC face by full name: exact match first, then a
    non-Mono name ending with the locale suffix. None when absent."""
    faces = font_locale_check.list_faces(str(path))
    for face in faces:
        if face["name"] == exact:
            return face["index"]
    for face in faces:
        name = face["name"] or ""
        if name.endswith(suffix) and "Mono" not in name:
            return face["index"]
    return None


class JudgeTest(unittest.TestCase):
    """The pure judgement: fraction of the body band where the ink top
    sits. Numbers are the ones measured on the real faces (B-1316)."""

    def test_jp_ink_top_is_in_lower_half(self):
        band = {"y_min": -80, "y_max": 840}
        self.assertAlmostEqual(font_locale_check.judge_top_fraction(band, 244), 0.352, places=3)
        self.assertLessEqual(font_locale_check.judge_top_fraction(band, 244), font_locale_check.TOP_FRACTION_MAX)

    def test_tc_ink_top_is_in_upper_half(self):
        band = {"y_min": -88, "y_max": 839}
        self.assertAlmostEqual(font_locale_check.judge_top_fraction(band, 531), 0.668, places=3)
        self.assertGreater(font_locale_check.judge_top_fraction(band, 531), font_locale_check.TOP_FRACTION_MAX)


@unittest.skipUnless(HAVE_FONTTOOLS, "fontTools is not installed")
class FontLocaleCheckTest(unittest.TestCase):
    def test_game_font_passes(self):
        # The shipped JP subset of 『灯りの欠片』: punctuation sits low.
        report = font_locale_check.check_file(str(GAME_FONT))
        self.assertTrue(report["ok"], report)
        for key in ("U+3001", "U+3002"):
            self.assertTrue(report["checks"][key]["pass"], report["checks"][key])
            self.assertLess(report["checks"][key]["top_fraction"], 0.5)

    def test_cli_on_game_font_exits_0(self):
        proc = subprocess.run(
            [sys.executable, str(LOOP / "font_locale_check.py"), str(GAME_FONT)],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(report["ok"], report)

    @unittest.skipUnless(NOTO_TTC.exists(), "system Noto Sans CJK TTC is not installed")
    def test_noto_jp_face_passes(self):
        face = find_face(NOTO_TTC, " JP", "Noto Sans CJK JP")
        if face is None:
            self.skipTest("no JP face in the system TTC")
        report = font_locale_check.check_file(str(NOTO_TTC), face=face)
        self.assertTrue(report["ok"], report)
        self.assertIn("JP", report["face_name"])

    @unittest.skipUnless(NOTO_TTC.exists(), "system Noto Sans CJK TTC is not installed")
    def test_noto_tc_face_fails(self):
        # The face that produced the wrong B-1311 / B-1313 captures:
        # centred punctuation must fail.
        face = find_face(NOTO_TTC, " TC", "Noto Sans CJK TC")
        if face is None:
            self.skipTest("no TC face in the system TTC")
        report = font_locale_check.check_file(str(NOTO_TTC), face=face)
        self.assertFalse(report["ok"], report)
        for key in ("U+3001", "U+3002"):
            self.assertFalse(report["checks"][key]["pass"], report["checks"][key])
            self.assertGreater(report["checks"][key]["top_fraction"], 0.5)

    def test_font_without_japanese_glyphs_is_an_input_error(self):
        dejavu = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        if not dejavu.exists():
            self.skipTest("DejaVu Sans is not installed")
        with self.assertRaises(font_locale_check.FontLocaleError):
            font_locale_check.check_file(str(dejavu))


if __name__ == "__main__":
    unittest.main()
