"""Tests for ai_loop/debug_capture.py (B-316). Engine-free."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from debug_capture import CaptureGame, CapturePlanner, _parse_args


def _obs(frame, events=(), done=False, ended=False):
    return {"frame": frame, "events": list(events), "done": done, "ended": ended}


def _cp(name):
    return {"type": "checkpoint", "id": name}


class TestPlannerCheckpoints(unittest.TestCase):
    def test_checkpoint_reason_after_event(self):
        p = CapturePlanner()
        p.feed(_obs(31, [_cp("cp1")]))
        reasons = p.due(_obs(31))
        self.assertEqual(len(reasons), 1)
        self.assertEqual(reasons[0]["reason"], "checkpoint")
        self.assertEqual(reasons[0]["checkpoint"], "cp1")
        self.assertEqual(reasons[0]["checkpoint_frame"], 31)
        self.assertEqual(p.checkpoints, ["cp1"])

    def test_start_event_is_not_a_checkpoint(self):
        p = CapturePlanner()
        p.feed(_obs(0, [{"type": "start"}]))
        self.assertEqual(p.due(_obs(0)), [])
        self.assertEqual(p.checkpoints, [])

    def test_same_checkpoint_twice_fires_once(self):
        p = CapturePlanner()
        p.feed(_obs(31, [_cp("cp1")]))
        p.due(_obs(31))
        p.feed(_obs(50, [_cp("cp1")]))
        self.assertEqual(p.due(_obs(50)), [])
        self.assertEqual(p.checkpoints, ["cp1"])


class TestPlannerIntervalAndEnd(unittest.TestCase):
    def test_interval_frames(self):
        p = CapturePlanner(every_frames=30)
        self.assertEqual(p.due(_obs(0)), [])
        self.assertEqual(p.due(_obs(29)), [])
        reasons = p.due(_obs(30))
        self.assertEqual([r["reason"] for r in reasons], ["interval"])
        self.assertEqual(p.due(_obs(31)), [])
        reasons = p.due(_obs(60))
        self.assertEqual([r["reason"] for r in reasons], ["interval"])

    def test_end_reason_and_consumption(self):
        p = CapturePlanner()
        p.feed(_obs(90, ended=True))
        reasons = p.due(_obs(90))
        self.assertEqual([r["reason"] for r in reasons], ["end"])
        self.assertEqual(p.due(_obs(90)), [])

    def test_end_disabled(self):
        p = CapturePlanner(at_end=False)
        p.feed(_obs(90, done=True))
        self.assertEqual(p.due(_obs(90)), [])


class FakeGame:
    def __init__(self, script):
        self.script = list(script)
        self.project = "fake"
        self.seed = None
        self.closed = False

    def step(self, frames=1, press=(), release=(), state=None, image=None):
        obs = self.script.pop(0)
        if image:
            Path(image).write_bytes(b"png")
        return obs

    def observe(self, state=None, image=None):
        if image:
            Path(image).write_bytes(b"png")
        if self.script:
            return dict(self.script[0])
        return _obs(0)

    def close(self):
        self.closed = True


class TestCaptureGame(unittest.TestCase):
    def test_shots_and_manifest(self):
        script = [
            _obs(1, [{"type": "start"}]),
            _obs(30),
            _obs(31, [_cp("cp1")]),
            _obs(32),
            _obs(33, [_cp("cp2")], ended=True),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            cap = CaptureGame(FakeGame(script), tmp, planner=CapturePlanner(every_frames=30))
            for _ in range(5):
                cap.step()
            manifest = cap.manifest()
            self.assertEqual(manifest["format"], "uzu-debug-capture/1")
            self.assertEqual(manifest["checkpoints"], ["cp1", "cp2"])
            frames = [s["frame"] for s in manifest["shots"]]
            self.assertEqual(frames, [1, 30, 31, 33])
            names = [s["file"] for s in manifest["shots"]]
            self.assertEqual(names[0], "000001_start.png")
            self.assertEqual(names[1], "000030_interval.png")
            self.assertEqual(names[2], "000031_checkpoint_cp1.png")
            self.assertEqual(names[3], "000033_checkpoint_cp2.png")
            for name in names:
                self.assertTrue((Path(tmp) / name).is_file())
            end_shot_reasons = [r["reason"] for r in manifest["shots"][3]["reasons"]]
            self.assertIn("end", end_shot_reasons)
            cap.close()
            self.assertTrue(cap._target.closed)


class TestParseArgs(unittest.TestCase):
    def test_defaults_and_values(self):
        opts = _parse_args([])
        self.assertEqual(opts["every"], 0)
        self.assertIsNone(opts["log"])
        opts = _parse_args(["--every", "30", "--log", "x.jsonl", "--seed=7", "--no-end"])
        self.assertEqual(opts["every"], 30)
        self.assertEqual(opts["log"], "x.jsonl")
        self.assertEqual(opts["seed"], 7)
        self.assertTrue(opts["no_end"])

    def test_unknown_argument(self):
        with self.assertRaises(ValueError):
            _parse_args(["--bogus"])


if __name__ == "__main__":
    unittest.main()
