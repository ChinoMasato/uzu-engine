"""B-1112: the feel proxy metrics (ai_loop/feel_report.py).

Pins the analysis half of the BACKLOG item mechanically, on synthetic
probe records (no engine needed): the probe samples the applied juice
state once per process frame, and these functions turn the samples into
per-channel segments. What is pinned:

  * a time_scale dip to 0 is a hitstop segment, a dip below the base a
    slowmo, a rise a speedup -- with lengths in process frames,
  * a trauma curve yields its peak, the frames to half the peak and the
    settle length; a kick spring counts its zero crossings,
  * a watched property (the pickup flash on a modulate) yields a segment
    with the peak deviation from the base value,
  * segments are attributed to the game event whose press caused them,
    and the latency is onset minus press; stray segments stay
    unattributed,
  * comparing a juice-on and a juice-off report shows the difference as
    numbers (segments and frames drop to 0), never as a verdict.
"""

import sys
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))
import feel_report  # noqa: E402

FLASH = "Main/Player:modulate"


def sample(pf, ts=1.0, trauma=0.0, kick=0.0, watch=None, frame=None, msec=None):
    return {"type": "sample", "pf": pf, "frame": pf if frame is None else frame,
            "msec": pf * 16 if msec is None else msec, "ts": ts, "juice_ts": ts,
            "trauma": trauma, "kick": kick, "watch": watch or {}}


class TimeScaleTest(unittest.TestCase):
    def test_hitstop_and_slowmo_segments(self):
        samples = [
            sample(0), sample(10, ts=0.0), sample(16, ts=0.0), sample(20),
            sample(30, ts=0.3), sample(50), sample(60, ts=2.0), sample(70),
        ]
        segs = feel_report.time_scale_segments(samples, 80)
        self.assertEqual([s["kind"] for s in segs], ["hitstop", "slowmo", "speedup"])
        self.assertEqual(segs[0]["frames"], 10)  # pf 10..20.
        self.assertEqual(segs[0]["min_scale"], 0.0)
        self.assertEqual(segs[1]["frames"], 20)
        self.assertEqual(segs[1]["min_scale"], 0.3)
        self.assertEqual(segs[2]["max_scale"], 2.0)

    def test_idle_is_no_segment(self):
        self.assertEqual(feel_report.time_scale_segments([sample(0), sample(10)], 20), [])

    def test_segment_open_at_run_end_is_marked(self):
        samples = [sample(0), sample(10, ts=0.0)]
        segs = feel_report.time_scale_segments(samples, 40, end_msec=640)
        self.assertEqual(len(segs), 1)
        self.assertTrue(segs[0]["open"])  # Still frozen when the run ended.
        self.assertEqual(segs[0]["msec"], 640 - 160)


class ScalarTest(unittest.TestCase):
    def test_trauma_decay_metrics(self):
        samples = [sample(90), sample(100, trauma=0.6), sample(110, trauma=0.45),
                   sample(120, trauma=0.3), sample(130, trauma=0.1), sample(140)]
        segs = feel_report.scalar_segments(samples, 150, "trauma")
        self.assertEqual(len(segs), 1)
        seg = segs[0]
        self.assertEqual(seg["peak"], 0.6)
        self.assertEqual(seg["frames"], 40)          # pf 100..140.
        self.assertEqual(seg["frames_to_half"], 20)  # 0.3 at pf 120.
        self.assertEqual(seg["zero_crossings"], 0)
        self.assertEqual(seg["samples"][0], [100, 0.6])

    def test_kick_spring_crossings(self):
        samples = [sample(200, kick=0.7), sample(210, kick=0.3),
                   sample(220, kick=-0.1), sample(230)]
        segs = feel_report.scalar_segments(samples, 240, "kick")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["peak"], 0.7)
        self.assertEqual(segs[0]["zero_crossings"], 1)
        self.assertEqual(segs[0]["frames"], 30)


class WatchTest(unittest.TestCase):
    def test_flash_segment_and_deviation(self):
        gold = [1.0, 0.85, 0.3, 1.0]
        samples = [sample(0, watch={FLASH: [1, 1, 1, 1]}),
                   sample(300, watch={FLASH: gold}),
                   sample(310, watch={FLASH: [1.0, 0.925, 0.65, 1.0]}),
                   sample(320, watch={FLASH: [1, 1, 1, 1]})]
        segs = feel_report.watch_segments(samples, 330, FLASH)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["frames"], 20)
        self.assertAlmostEqual(segs[0]["peak_deviation"], 0.7)

    def test_resolution_errors_are_not_segments(self):
        samples = [sample(0, watch={FLASH: {"error": "no node"}}),
                   sample(10, watch={FLASH: [1, 1, 1, 1]})]
        self.assertEqual(feel_report.watch_segments(samples, 20, FLASH), [])


class AttributeTest(unittest.TestCase):
    def test_latency_and_unattributed(self):
        records = [
            sample(298, watch={FLASH: [1, 1, 1, 1]}),
            sample(300, watch={FLASH: [1.0, 0.85, 0.3, 1.0]}),
            sample(320, watch={FLASH: [1, 1, 1, 1]}),
            sample(1000, kick=0.7), sample(1030),
            {"type": "end", "pf": 1040, "frame": 1040, "msec": 16640},
        ]
        analysis = feel_report.analyze(records)
        events = [{"id": "shard_1", "frame": 305, "press_frame": 298}]
        out = feel_report.attribute(analysis, events)
        ev = out["events"][0]
        self.assertEqual(ev["latency_frames"], 2)  # Onset 300 - press 298.
        self.assertIn("watch:" + FLASH, ev["channels"])
        self.assertIn("kick", out["unattributed"])  # No press explains it.

    def test_ui_events_and_curves_pass_through(self):
        records = [
            sample(0),
            {"type": "ui_event", "pf": 5, "frame": 5, "msec": 80, "event": "count_up",
             "phase": "start", "preset": "ease_in", "target": "ShardGauge"},
            {"type": "curve", "preset": "ease_in", "samples": [[0.0, 0.0], [1.0, 1.0]]},
            {"type": "end", "pf": 10, "frame": 10, "msec": 160},
        ]
        analysis = feel_report.analyze(records)
        self.assertEqual(analysis["ui_events"][0]["preset"], "ease_in")
        self.assertEqual(analysis["curves"]["ease_in"], [[0.0, 0.0], [1.0, 1.0]])


class CompareTest(unittest.TestCase):
    def test_juice_on_off_difference_is_numeric(self):
        seg = {"watch": FLASH, "onset_pf": 300, "onset_frame": 300, "frames": 20,
               "msec": 320, "peak_deviation": 0.7}
        on = {"events": [{"id": "shard_1", "frame": 305, "press_frame": 298,
                          "latency_frames": 2, "channels": {"watch:" + FLASH: [seg]},
                          "ui_events": []}]}
        off = {"events": [{"id": "shard_1", "frame": 305, "press_frame": 298,
                           "latency_frames": None, "channels": {}, "ui_events": []}]}
        diff = feel_report.compare_reports(on, off)
        cell = diff["shard_1"]["channels"]["watch:" + FLASH]
        self.assertEqual(cell["segments"], [1, 0])
        self.assertEqual(cell["frames"], [20, 0])
        self.assertEqual(cell["peak"], [0.7, None])
        self.assertEqual(diff["shard_1"]["latency_frames"], [2, None])



class FeelDriverContractTest(unittest.TestCase):
    """B-1113: the FEEL_DRIVER contract's pure functions."""

    def test_expect_met(self):
        state = {"Main:delivered": 2, "Main:cleared": False}
        self.assertTrue(feel_report.expect_met(state, {"Main:delivered": 2}))
        self.assertFalse(feel_report.expect_met(state, {"Main:delivered": 3}))
        self.assertFalse(feel_report.expect_met(state, {"Main:cleared": True}))
        self.assertTrue(feel_report.expect_met(state, {"Main:cleared": False}))
        # Booleans do not match ints.
        self.assertFalse(feel_report.expect_met({"Main:x": 1}, {"Main:x": True}))
        self.assertFalse(feel_report.expect_met({"Main:x": True}, {"Main:x": 1}))
        self.assertFalse(feel_report.expect_met({}, {"Main:missing": 0}))

    def test_validate_driver(self):
        good = {"state": ["Main:a"], "legs": [{"name": "l", "goto": [1, 2],
                "action": "interact", "expect": {"Main:a": 1}}], "success": {"Main:b": True}}
        self.assertEqual(feel_report.validate_driver(good), [])
        self.assertTrue(feel_report.validate_driver({}))
        self.assertTrue(feel_report.validate_driver({"state": ["Main:a"], "legs": [], "success": {"Main:b": 1}}))
        bad_goto = dict(good, legs=[{"goto": [1], "expect": {"Main:a": 1}}])
        self.assertTrue(any("goto" in e for e in feel_report.validate_driver(bad_goto)))
        self.assertTrue(feel_report.validate_driver("nope"))

    def test_driver_kind(self):
        import types
        driver_mod = types.SimpleNamespace(FEEL_DRIVER={"state": []})
        self.assertEqual(feel_report.driver_kind(driver_mod), "driver")
        legacy_mod = types.SimpleNamespace(STATE=[], ROUTE=[], walk_to=None,
                                           interact=None, event_names=None)
        self.assertEqual(feel_report.driver_kind(legacy_mod), "legacy")
        self.assertIsNone(feel_report.driver_kind(types.SimpleNamespace()))

if __name__ == "__main__":
    unittest.main()
