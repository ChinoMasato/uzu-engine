"""B-1221: the image-first scaffold (ai_loop/image_scene.py).

Pins the judgement of the BACKLOG item mechanically, on synthetic
illustrations drawn in code (no engine needed):
  * one illustration yields a B-1207 spec with a backdrop card, cut-out
    layer cards, a reference camera and a walkable ground,
  * derived items are candidates: interact candidates carry
    basis "inferred", never a claim of fact,
  * a bright blob reads as a glow candidate and a tall ground-standing
    shape as a door candidate,
  * a supplied depth map is reported as observed (the heuristic is not),
  * the ground's own regions are floor, not cards.
"""

import sys
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))
import image_scene  # noqa: E402

SPEC_KEYS = {"scene", "base", "main", "look", "ground", "camera", "models",
             "scatter", "lamps", "particles", "water", "godrays", "cards", "markers"}


def draw(path, with_door=True):
    """A flat 320x180 landscape: sky, ground, a sun, a tree, a door."""
    w, h = 320, 180
    px = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 4
            px[i:i + 4] = bytes([70, 90, 140, 255]) if y < 110 else bytes([60, 70, 40, 255])
    for y in range(30, 55):  # The sun: a bright blob.
        for x in range(240, 265):
            i = (y * w + x) * 4
            px[i:i + 4] = bytes([255, 240, 200, 255])
    if with_door:  # A tall, dark, ground-standing rectangle.
        for y in range(95, 150):
            for x in range(60, 78):
                i = (y * w + x) * 4
                px[i:i + 4] = bytes([40, 30, 25, 255])
    for y in range(120, 175):  # A dark green tree, foreground right.
        for x in range(270, 310):
            i = (y * w + x) * 4
            px[i:i + 4] = bytes([25, 50, 25, 255])
    image_scene.write_png(str(path), w, h, px)


class ImageSceneTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.img = self.tmp / "illustration.png"
        draw(self.img)

    def test_png_roundtrip(self):
        w, h, rgba = image_scene.load_rgba(str(self.img))
        self.assertEqual((w, h), (320, 180))
        self.assertEqual(len(rgba), 320 * 180 * 4)

    def test_spec_shape(self):
        spec, report, assets = image_scene.analyze(str(self.img))
        self.assertTrue(set(spec) <= SPEC_KEYS, set(spec))
        self.assertEqual(spec["cards"][0]["name"], "Backdrop")
        self.assertIn("background.png", assets)
        self.assertGreaterEqual(len(spec["cards"]), 2)  # Backdrop + cut-outs.
        self.assertIn("camera", spec)
        self.assertEqual(report["camera"]["fov"], spec["camera"]["fov"])
        self.assertTrue(spec["ground"]["collision"])
        # The walk area holds the spawn and every waypoint.
        wx, wz = report["walk_area"]["x"], report["walk_area"]["z"]
        for point in [report["spawn"]] + report["waypoints"]:
            self.assertTrue(wx[0] <= point[0] <= wx[1], point)
            self.assertTrue(wz[0] <= point[2] <= wz[1], point)

    def test_candidates_are_inferred(self):
        spec, report, _ = image_scene.analyze(str(self.img))
        kinds = {(c["id"], c["kind"]) for c in report["candidates"]["interact"]}
        self.assertTrue(any(k == "glow" for _, k in kinds), kinds)
        self.assertTrue(any(k == "door" for _, k in kinds), kinds)
        for cand in report["candidates"]["interact"]:
            self.assertEqual(cand["basis"], "inferred")
            self.assertIn("position", cand)
        self.assertEqual(len(spec["markers"]), len(report["candidates"]["interact"]))
        # The ground itself never becomes a collision candidate.
        for col in report["candidates"]["collision"]:
            self.assertTrue(col["card"].startswith("Card_"), col)

    def test_depth_map_is_observed(self):
        depth = self.tmp / "depth.png"
        w, h = 320, 180
        px = bytearray(w * h * 4)
        for y in range(h):
            v = 255 - int(255 * y / h)  # White (far) at the top.
            for x in range(w):
                i = (y * w + x) * 4
                px[i:i + 4] = bytes([v, v, v, 255])
        image_scene.write_png(str(depth), w, h, px)
        _, report, _ = image_scene.analyze(str(self.img), depth_path=str(depth))
        self.assertEqual(report["depth"]["source"], "map")
        self.assertEqual(report["depth"]["basis"], "observed")
        _, report2, _ = image_scene.analyze(str(self.img))
        self.assertEqual(report2["depth"]["basis"], "inferred")


class RouteWaypointsTest(unittest.TestCase):
    def setUp(self):
        self.walk = {"x": [-7.8, 7.8], "z": [-17.0, -6.31]}
        self.spawn = [0.0, 0.0, -7.81]

    def _segment_clear_on_grid(self, a, b, footprints, clearance=0.45):
        steps = 200
        for s in range(steps + 1):
            t = s / steps
            px = a[0] + (b[0] - a[0]) * t
            pz = a[2] + (b[2] - a[2]) * t
            if not (self.walk["x"][0] <= px <= self.walk["x"][1]):
                return False
            if not (self.walk["z"][0] <= pz <= self.walk["z"][1]):
                return False
            for cx, cz, w in footprints:
                half_w = w * 0.5 + clearance
                if (cx - half_w) <= px <= (cx + half_w) and (cz - clearance) <= pz <= (cz + clearance):
                    return False
        return True

    def test_no_obstacles_keeps_waypoints_unchanged(self):
        waypoints = [
            [0.0, 0.0, -11.65],
            [-5.46, 0.0, -10.95],
            [5.46, 0.0, -10.95],
            [1.66, 0.0, -11.54],
            [0.0, 0.0, -7.81],
        ]
        routed, legs = image_scene.route_waypoints(self.spawn, waypoints, [], self.walk)
        self.assertEqual(routed, waypoints)
        self.assertEqual(len(legs), len(waypoints))
        for leg in legs:
            self.assertTrue(leg["routed"])
            self.assertEqual(leg["inserted"], 0)

    def test_center_wall_routes_through_side_gap_and_preserves_reachability(self):
        waypoints = [[0.0, 0.0, -11.65], [0.0, 0.0, -7.81]]
        footprints = [[0.0, -9.5, 4.0]]  # Blocks x in [-2.45, 2.45]; gaps exist on both sides.
        routed, legs = image_scene.route_waypoints(self.spawn, waypoints, footprints, self.walk)
        self.assertGreater(len(routed), len(waypoints))
        self.assertEqual(len(legs), 2)
        self.assertTrue(all(leg["routed"] for leg in legs))
        self.assertGreaterEqual(legs[0]["inserted"], 1)
        self.assertGreaterEqual(legs[1]["inserted"], 1)
        # Intermediate waypoints detour around the central wall through a side gap.
        self.assertTrue(any(abs(pt[0]) > 2.45 for pt in routed))
        # Every leg in the resulting path stays within walk_area and clear of expanded footprints.
        chain = [self.spawn] + routed
        for a, b in zip(chain, chain[1:]):
            self.assertTrue(self._segment_clear_on_grid(a, b, footprints), (a, b))
        # Deterministic across repeated calls.
        routed2, legs2 = image_scene.route_waypoints(self.spawn, waypoints, footprints, self.walk)
        self.assertEqual((routed, legs), (routed2, legs2))

    def test_completely_blocked_leg_leaves_target_with_routed_false(self):
        waypoints = [[0.0, 0.0, -11.65]]
        footprints = [[0.0, -9.5, 20.0]]  # Spans [-10.45, 10.45], blocking the full walk width.
        routed, legs = image_scene.route_waypoints(self.spawn, waypoints, footprints, self.walk)
        self.assertEqual(routed, waypoints)
        self.assertEqual(len(legs), 1)
        self.assertFalse(legs[0]["routed"])
        self.assertEqual(legs[0]["inserted"], 0)
        self.assertEqual(legs[0]["from"], self.spawn)
        self.assertEqual(legs[0]["to"], waypoints[0])

if __name__ == "__main__":
    unittest.main()
