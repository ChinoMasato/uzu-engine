"""B-1223: spec-image diff verification (ai_loop/spec_diff.py).

Pins the judgement of the BACKLOG item mechanically, on synthetic image
pairs (no engine needed):
  * a shot identical to the spec passes every metric and every element,
  * a shot with one element repainted away fails exactly that element
    (the others still pass) and the overall verdict,
  * a channel-swapped shot fails the colour metric,
  * a couple of pixels of shift are absorbed by the tolerances,
  * thresholds are data: an unknown key is an error, an override applies,
  * the element list comes out of a B-1221 generation report's shape.
"""

import sys
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))
import image_scene  # noqa: E402
import spec_diff  # noqa: E402

W, H = 320, 180
SKY = (70, 90, 140)
GROUND = (60, 70, 40)
WALL = (150, 120, 90)
DOOR = (40, 30, 25)
WINDOW = (255, 220, 130)
TREE = (25, 60, 25)

ELEMENTS = [
    {"id": "door", "kind": "door", "bbox": [60, 95, 78, 150], "basis": "inferred"},
    {"id": "window", "kind": "glow", "bbox": [110, 75, 135, 95], "basis": "inferred"},
    {"id": "tree", "kind": "card", "bbox": [240, 90, 290, 175], "basis": "inferred"},
]


def draw(path, erase_door=False, swap=False, shift=0):
    px = bytearray(W * H * 4)
    for y in range(H):
        for x in range(W):
            i = (y * W + x) * 4
            px[i:i + 4] = bytes([*SKY, 255]) if y < 110 else bytes([*GROUND, 255])
    for y in range(60, 150):  # The house wall.
        for x in range(40, 160):
            i = (y * W + x) * 4
            px[i:i + 4] = bytes([*WALL, 255])
    if not erase_door:
        for y in range(95, 150):
            for x in range(60, 78):
                i = (y * W + x) * 4
                px[i:i + 4] = bytes([*DOOR, 255])
    for y in range(75, 95):  # The lit window.
        for x in range(110, 135):
            i = (y * W + x) * 4
            px[i:i + 4] = bytes([*WINDOW, 255])
    for y in range(90, 175):  # The tree.
        for x in range(240, 290):
            i = (y * W + x) * 4
            px[i:i + 4] = bytes([*TREE, 255])
    if swap:
        for p in range(W * H):
            i = p * 4
            px[i], px[i + 2] = px[i + 2], px[i]
    if shift:
        moved = bytearray(W * H * 4)
        for y in range(H):
            for x in range(W):
                sx = min(max(x - shift, 0), W - 1)
                moved[(y * W + x) * 4:(y * W + x) * 4 + 4] = px[(y * W + sx) * 4:(y * W + sx) * 4 + 4]
        px = moved
    image_scene.write_png(str(path), W, H, px)


class SpecDiffTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = Path(tempfile.mkdtemp())
        self.spec = self.dir / "spec.png"
        draw(self.spec)

    def verdict(self, name, **kw):
        shot = self.dir / name
        draw(shot, **kw)
        return spec_diff.compare(str(self.spec), str(shot), ELEMENTS)

    def test_identical_shot_passes(self):
        v = self.verdict("same.png")
        self.assertTrue(v["ok"], v)
        self.assertEqual(v["metrics"]["composition"]["score"], 1.0)
        self.assertEqual(v["metrics"]["color"]["distance"], 0.0)
        self.assertTrue(all(e["pass"] for e in v["elements"]))

    def test_erased_element_fails_alone(self):
        v = self.verdict("erased.png", erase_door=True)
        by_id = {e["id"]: e for e in v["elements"]}
        self.assertFalse(by_id["door"]["pass"], by_id["door"])
        self.assertTrue(by_id["window"]["pass"], by_id["window"])
        self.assertTrue(by_id["tree"]["pass"], by_id["tree"])
        self.assertFalse(v["ok"])

    def test_channel_swap_fails_colour(self):
        v = self.verdict("swap.png", swap=True)
        self.assertFalse(v["metrics"]["color"]["pass"], v["metrics"])
        self.assertGreater(v["metrics"]["color"]["distance"],
                           v["metrics"]["color"]["threshold"])
        self.assertFalse(v["ok"])

    def test_small_shift_is_tolerated(self):
        v = self.verdict("shift.png", shift=2)
        self.assertTrue(v["metrics"]["composition"]["pass"], v["metrics"])
        self.assertTrue(all(e["pass"] for e in v["elements"]), v["elements"])
        self.assertTrue(v["ok"], v)

    def test_thresholds_are_data(self):
        with self.assertRaises(ValueError):
            spec_diff.load_thresholds(None, {"nope": 1.0})
        import json
        path = self.dir / "t.json"
        path.write_text(json.dumps({"color_max": 0.99}), encoding="utf-8")
        th = spec_diff.load_thresholds(str(path))
        self.assertEqual(th["color_max"], 0.99)
        shot = self.dir / "swap2.png"
        draw(shot, swap=True)
        v = spec_diff.compare(str(self.spec), str(shot), ELEMENTS, th)
        self.assertTrue(v["metrics"]["color"]["pass"], v["metrics"])

    def test_elements_from_report_shape(self):
        report = {
            "layers": {"cards": [{"name": "Card_A", "image_bbox": [1, 2, 30, 40],
                                  "basis": "inferred"}]},
            "candidates": {"interact": [{"id": "glow_0", "kind": "glow",
                                         "image_bbox": [5, 6, 9, 10], "basis": "inferred"}]},
        }
        elements = spec_diff.elements_from_report(report)
        self.assertEqual([(e["id"], e["kind"]) for e in elements],
                         [("Card_A", "card"), ("glow_0", "glow")])
        self.assertEqual(elements[0]["bbox"], [1, 2, 30, 40])


class SpecDiffAdvisoryTest(unittest.TestCase):
    """B-1227: glow candidates are advisory; they never gate the verdict."""

    def setUp(self):
        import tempfile
        self.dir = Path(tempfile.mkdtemp())
        self.spec = self.dir / "spec.png"
        draw(self.spec)

    def _erase_window(self, path):
        draw(path)
        _, _, raw = image_scene.load_rgba(str(path))
        px = bytearray(raw)
        for y in range(75, 95):
            for x in range(110, 135):
                i = (y * W + x) * 4
                px[i:i + 4] = bytes([*WALL, 255])
        image_scene.write_png(str(path), W, H, px)

    def test_glow_failure_is_advisory_only(self):
        shot = self.dir / "no_window.png"
        self._erase_window(shot)
        v = spec_diff.compare(str(self.spec), str(shot), ELEMENTS)
        by_id = {e["id"]: e for e in v["elements"]}
        self.assertFalse(by_id["window"]["pass"], by_id["window"])
        self.assertTrue(by_id["window"]["candidate"])
        self.assertFalse(by_id["door"]["candidate"])
        self.assertFalse(by_id["tree"]["candidate"])
        self.assertEqual(v["advisory"], {"checked": 1, "passed": 0, "failed": ["window"]})
        self.assertEqual(v["gating"], {"checked": 2, "passed": 2, "failed": []})
        self.assertTrue(v["ok"], v)

    def test_gating_failure_still_fails(self):
        shot = self.dir / "no_door.png"
        draw(shot, erase_door=True)
        v = spec_diff.compare(str(self.spec), str(shot), ELEMENTS)
        self.assertEqual(v["gating"], {"checked": 2, "passed": 1, "failed": ["door"]})
        self.assertEqual(v["advisory"], {"checked": 1, "passed": 1, "failed": []})
        self.assertFalse(v["ok"])

    def test_candidate_flags_from_report_and_registry(self):
        report = {
            "layers": {"cards": [{"name": "Card_A", "image_bbox": [1, 2, 30, 40],
                                  "basis": "inferred"}]},
            "candidates": {"interact": [
                {"id": "door_0", "kind": "door", "image_bbox": [10, 20, 30, 50], "basis": "inferred"},
                {"id": "glow_0", "kind": "glow", "image_bbox": [5, 6, 9, 10], "basis": "inferred"}]},
        }
        from_report = spec_diff.elements_from_report(report)
        self.assertEqual([(e["id"], e["candidate"]) for e in from_report],
                         [("Card_A", False), ("door_0", False), ("glow_0", True)])
        binding = {"elements": [
            {"id": "house_red", "kind": "house", "image_bbox": [0, 0, 50, 50], "basis": "observed"},
            {"id": "lamp_glow", "kind": "glow", "image_bbox": [12, 12, 20, 20], "basis": "inferred"}]}
        from_registry = spec_diff.elements_from_registry(binding)
        self.assertEqual([(e["id"], e["candidate"]) for e in from_registry],
                         [("house_red", False), ("lamp_glow", True)])



if __name__ == "__main__":
    unittest.main()
