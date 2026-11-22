import json
import sys
import tempfile
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))

import ui_quality  # noqa: E402

try:
    import PIL  # noqa: F401  (Pillow is needed only to synthesise test images)
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


def flat(r, g, b, a=1.0):
    return {"class": "StyleBoxFlat", "bg_color": [r, g, b, a],
            "content_margins": [16, 16, 16, 16], "corner_radius": [8, 8, 8, 8],
            "shadow_size": 8}


def good_theme():
    """A theme that satisfies every probe-side check."""
    types = {}
    for type_name in ui_quality.STANDARD_TYPES:
        types[type_name] = {"styleboxes": {"panel": flat(0.1, 0.1, 0.12)}}
    types["Button"] = {"styleboxes": {
        "normal": flat(0.2, 0.2, 0.25), "hover": flat(0.3, 0.3, 0.35),
        "pressed": flat(0.12, 0.12, 0.15), "disabled": flat(0.5, 0.5, 0.5),
        "focus": {"class": "StyleBoxFlat", "bg_color": [0.9, 0.7, 0.2, 1.0],
                  "content_margins": [16, 16, 16, 16], "corner_radius": [8, 8, 8, 8],
                  "shadow_size": 0},
    }, "colors": {"font_color": [1.0, 1.0, 1.0, 1.0]}}
    types["Label"] = {"colors": {"font_color": [1.0, 1.0, 1.0, 1.0]}}
    # The slider's structural pairs (B-1315): a mid-grey groove the dark
    # panel and the white fill both read against.
    types["HSlider"] = {"styleboxes": {
        "slider": flat(0.55, 0.55, 0.58), "grabber_area": flat(1.0, 1.0, 1.0)}}
    return {"types": types, "options": {}}


def current_wafu_like_theme():
    """The shape of the current wafu theme: focus empty, most types bare,
    ad-hoc padding 14 and shadow 6."""
    theme = good_theme()
    types = theme["types"]
    for missing in ("CheckBox", "OptionButton", "HSlider", "VSlider", "LineEdit",
                    "SpinBox", "HScrollBar", "VScrollBar", "PopupMenu", "Tree"):
        del types[missing]
    types["Button"]["styleboxes"]["focus"] = {"class": "StyleBoxEmpty",
                                              "content_margins": [0, 0, 0, 0]}
    types["PanelContainer"]["styleboxes"]["panel"] = {
        "class": "StyleBoxTexture", "center_color": [0.937, 0.886, 0.769, 1.0],
        "content_margins": [14, 14, 14, 14], "expand_margins": [6, 6, 6, 6]}
    types["Label"]["colors"]["font_color"] = [0.165, 0.102, 0.063, 1.0]
    return theme


class ContrastTest(unittest.TestCase):
    def test_black_on_white_is_21(self):
        self.assertAlmostEqual(ui_quality.contrast_ratio([0, 0, 0, 1], [1, 1, 1, 1]), 21.0, places=1)

    def test_same_colour_is_1(self):
        self.assertAlmostEqual(ui_quality.contrast_ratio([0.5, 0.5, 0.5, 1], [0.5, 0.5, 0.5, 1]), 1.0, places=6)

    def test_good_theme_passes(self):
        self.assertTrue(ui_quality.check_contrast(good_theme())["pass"])

    def test_low_contrast_fails(self):
        theme = good_theme()
        theme["types"]["Label"]["colors"]["font_color"] = [0.2, 0.2, 0.2, 1.0]
        theme["types"]["PanelContainer"]["styleboxes"]["panel"] = flat(0.25, 0.25, 0.25)
        result = ui_quality.check_contrast(theme)
        self.assertFalse(result["pass"])
        self.assertFalse(result["pairs"][0]["pass"])

    def test_slider_pairs_are_scored(self):
        result = ui_quality.check_contrast(good_theme())
        names = [p["pair"] for p in result["pairs"]]
        self.assertIn("slider groove on panel", names)
        self.assertIn("slider fill on groove", names)

    def test_invisible_groove_fails(self):
        theme = good_theme()
        # A groove painted in the panel's own colour (the B-1313 state of
        # most themes) must fail the groove pair.
        theme["types"]["HSlider"]["styleboxes"]["slider"] = flat(0.1, 0.1, 0.12)
        result = ui_quality.check_contrast(theme)
        self.assertFalse(result["pass"])
        groove = [p for p in result["pairs"] if p["pair"] == "slider groove on panel"][0]
        self.assertFalse(groove["pass"])


class StateAndCoverageTest(unittest.TestCase):
    def test_good_theme_passes(self):
        theme = good_theme()
        self.assertTrue(ui_quality.check_states(theme)["pass"])
        self.assertTrue(ui_quality.check_coverage(theme)["pass"])

    def test_empty_focus_fails(self):
        result = ui_quality.check_states(current_wafu_like_theme())
        self.assertFalse(result["pass"])
        self.assertIn("StyleBoxEmpty", result["states"]["focus"]["reason"])

    def test_missing_types_fail_coverage(self):
        result = ui_quality.check_coverage(current_wafu_like_theme())
        self.assertFalse(result["pass"])
        self.assertIn("LineEdit", result["missing"])
        self.assertAlmostEqual(result["ratio"], 6 / 16)


class ScaleTest(unittest.TestCase):
    def test_good_theme_passes(self):
        self.assertTrue(ui_quality.check_scale(good_theme())["pass"])

    def test_adhoc_values_fail(self):
        result = ui_quality.check_scale(current_wafu_like_theme())
        self.assertFalse(result["pass"])
        values = {e["value"] for e in result["spacing_off_scale"]}
        self.assertIn(14, values)
        shadow_values = {e["value"] for e in result["shadow_off_scale"]}
        self.assertIn(6, shadow_values)


@unittest.skipUnless(HAVE_PIL, "Pillow (PIL) is not installed")
class RepetitionTest(unittest.TestCase):
    def _write(self, img):
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name)
        return tmp.name

    def _noise_image(self, seed, blur):
        import random
        from PIL import Image, ImageFilter

        rng = random.Random(seed)
        noise = Image.new("L", (640, 160))
        noise.putdata([max(0, min(255, int(rng.gauss(128, 40)))) for _ in range(640 * 160)])
        return noise.filter(ImageFilter.GaussianBlur(blur))

    def test_dot_grid_fails(self):
        from PIL import Image, ImageDraw

        base = Image.new("RGB", (640, 160), (239, 226, 196))
        noise = self._noise_image(7, 2).convert("RGB")
        img = Image.blend(base, noise, 0.15)
        draw = ImageDraw.Draw(img)
        for yy in range(16, 160, 32):
            for xx in range(16, 640, 32):
                draw.rectangle([xx - 2, yy - 2, xx + 2, yy + 2], fill=(184, 50, 42))
        result = ui_quality.texture_repetition(self._write(img))
        self.assertFalse(result["pass"], result)
        self.assertGreater(result["index"], ui_quality.REPETITION_MAX)

    def test_smooth_parchment_passes(self):
        from PIL import Image

        base = Image.new("RGB", (640, 160), (239, 226, 196))
        noise = self._noise_image(11, 9).convert("RGB")
        img = Image.blend(base, noise, 0.2)
        result = ui_quality.texture_repetition(self._write(img))
        self.assertTrue(result["pass"], result)


@unittest.skipUnless(HAVE_PIL, "Pillow (PIL) is not installed")
class SheetTest(unittest.TestCase):
    """The texture-sheet measurement (B-1315): a designed micro-pattern is
    judged on residue + uniformity, anything else on visibility."""

    def _write(self, img):
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name)
        return tmp.name

    def test_halftone_grid_passes_as_pattern(self):
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (256, 256), (230, 0, 18))
        draw = ImageDraw.Draw(img)
        for cy in range(4, 256, 8):
            for cx in range(4, 256, 8):
                draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 255, 255))
        result = ui_quality.texture_repetition_sheet(self._write(img))
        self.assertTrue(result["pass"], result)
        lum = result["channels"]["luminance"]
        self.assertEqual(lum["mode"], "pattern")
        self.assertEqual(lum["period_px"][0], 8)

    def test_moire_grid_fails_on_residue(self):
        # Dots at a non-integer spacing (what TILE_FIT rescaling does to a
        # printed grid): the cells stay uniform, but the phase drifts, so
        # the band correlation strays from the period's own prediction.
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (256, 256), (230, 0, 18))
        draw = ImageDraw.Draw(img)
        cy = 4.0
        while cy < 256:
            cx = 4.0
            while cx < 256:
                draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 255, 255))
                cx += 8.5
            cy += 8.5
        result = ui_quality.texture_repetition_sheet(self._write(img))
        self.assertFalse(result["pass"], result)
        lum = result["channels"]["luminance"]
        self.assertEqual(lum["mode"], "pattern")
        self.assertGreater(lum["residue"], ui_quality.SHEET_RESIDUE_MAX)

    def test_coarse_dot_grid_fails(self):
        # A 32 px grid is not a designed micro-pattern (period cap 24), so
        # it is judged on visibility -- and it is plainly visible.
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (512, 512), (239, 226, 196))
        draw = ImageDraw.Draw(img)
        for yy in range(16, 512, 32):
            for xx in range(16, 512, 32):
                draw.rectangle([xx - 3, yy - 3, xx + 3, yy + 3], fill=(184, 50, 42))
        result = ui_quality.texture_repetition_sheet(self._write(img))
        self.assertFalse(result["pass"], result)

    def test_smooth_sheet_passes_on_visibility(self):
        import random
        from PIL import Image, ImageFilter

        rng = random.Random(11)
        noise = Image.new("L", (512, 512))
        noise.putdata([max(0, min(255, int(rng.gauss(128, 40)))) for _ in range(512 * 512)])
        base = Image.new("RGB", (512, 512), (239, 226, 196))
        img = Image.blend(base, noise.filter(ImageFilter.GaussianBlur(9)).convert("RGB"), 0.2)
        result = ui_quality.texture_repetition_sheet(self._write(img))
        self.assertTrue(result["pass"], result)
        self.assertEqual(result["channels"]["luminance"]["mode"], "visibility")


class CoverageTest(unittest.TestCase):
    def test_alpha_hole_fails(self):
        theme = good_theme()
        theme["types"]["PanelContainer"]["styleboxes"]["panel"] = {
            "class": "StyleBoxTexture", "center_color": [0.9, 0.1, 0.1, 1.0],
            "center_alpha_min": 0.0, "center_alpha_mean": 0.92,
            "content_margins": [16, 16, 16, 16]}
        self.assertFalse(ui_quality.texture_coverage(theme)["pass"])

    def test_opaque_centre_passes(self):
        theme = good_theme()
        theme["types"]["PanelContainer"]["styleboxes"]["panel"] = {
            "class": "StyleBoxTexture", "center_color": [0.9, 0.1, 0.1, 1.0],
            "center_alpha_min": 1.0, "center_alpha_mean": 1.0,
            "content_margins": [16, 16, 16, 16]}
        self.assertTrue(ui_quality.texture_coverage(theme)["pass"])

    def test_glass_panel_passes(self):
        # Translucent everywhere by design (the sf glass panel): no local
        # collapse, so no hole.
        theme = good_theme()
        theme["types"]["PanelContainer"]["styleboxes"]["panel"] = {
            "class": "StyleBoxTexture", "center_color": [0.1, 0.2, 0.3, 0.87],
            "center_alpha_min": 0.84, "center_alpha_mean": 0.865,
            "content_margins": [16, 16, 16, 16]}
        self.assertTrue(ui_quality.texture_coverage(theme)["pass"])


class ContainmentTest(unittest.TestCase):
    def _data(self, screens):
        return {"format": "uzu-ui-containment/1", "screens": screens}

    def test_all_inside_passes(self):
        result = ui_quality.check_containment(self._data(
            {"persona_menu": {"pass": True, "rest": [], "peak": []}}))
        self.assertTrue(result["pass"])

    def test_peak_violation_fails(self):
        bad = {"pass": False, "rest": [], "peak": [
            {"control": "Gauge", "panel": "Panel",
             "overflow": {"left": 0.0, "top": 0.0, "right": 12.5, "bottom": 0.0}}]}
        result = ui_quality.check_containment(self._data({"persona_hud": bad}))
        self.assertFalse(result["pass"])
        self.assertEqual(result["screens"]["persona_hud"]["peak_violations"], 1)

    def test_wrong_format_fails(self):
        self.assertFalse(ui_quality.check_containment({"format": "nope"})["pass"])

    def test_no_screens_fails(self):
        self.assertFalse(ui_quality.check_containment(self._data({}))["pass"])


class ReportTest(unittest.TestCase):
    def test_verdict_fail_for_current_shape(self):
        probe = {"format": ui_quality.PROBE_FORMAT,
                 "themes": {"wafu": current_wafu_like_theme()}}
        report = ui_quality.build_report(probe, "wafu", [])
        self.assertEqual(report["format"], "uzu-ui-quality/1")
        self.assertEqual(report["verdict"], "fail")
        self.assertFalse(report["checks"]["state_completeness"]["pass"])
        self.assertFalse(report["checks"]["coverage"]["pass"])
        self.assertFalse(report["checks"]["scale"]["pass"])
        json.dumps(report)  # must stay serialisable

    def test_unknown_theme_raises(self):
        probe = {"format": ui_quality.PROBE_FORMAT, "themes": {}}
        with self.assertRaises(ValueError):
            ui_quality.build_report(probe, "wafu", [])


if __name__ == "__main__":
    unittest.main()
