"""Unit tests for ai_loop.autopilot."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

_AI_LOOP_DIR = Path(__file__).resolve().parent.parent
if str(_AI_LOOP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_AI_LOOP_DIR.parent))

try:
    from ai_loop import autopilot
    from ai_loop.autopilot import AutopilotError, FORMAT
except ImportError:
    if str(_AI_LOOP_DIR) not in sys.path:
        sys.path.insert(0, str(_AI_LOOP_DIR))
    import autopilot
    from autopilot import AutopilotError, FORMAT


class StubGame:
    """Fake Game matching aiplayer.Game step/observe surface."""

    def __init__(self, checkpoint_frames=None, end_at_frame=None, raise_after_steps=None):
        self.frame = 0
        self.calls = []
        self.checkpoint_frames = dict(checkpoint_frames or {})
        self.end_at_frame = end_at_frame
        self.raise_after_steps = raise_after_steps
        self.closed = False

    def observe(self, state=None, image=None):
        return {"frame": self.frame, "events": [], "ended": False}

    def step(self, frames=1, press=(), release=(), state=None, image=None):
        if self.raise_after_steps is not None and len(self.calls) >= self.raise_after_steps:
            raise RuntimeError("game has already ended")

        self.calls.append({
            "frames": frames,
            "press": list(press),
            "release": list(release),
            "state": state,
        })
        prev_frame = self.frame
        self.frame += frames

        events = []
        for cp_frame, cp_id in sorted(self.checkpoint_frames.items()):
            if prev_frame < cp_frame <= self.frame:
                events.append({"type": "checkpoint", "id": cp_id})

        ended = self.end_at_frame is not None and self.frame >= self.end_at_frame
        obs = {
            "frame": self.frame,
            "events": events,
            "ended": ended,
        }
        if state:
            obs["state"] = {path: f"val@{self.frame}" for path in state}
        return obs

    def close(self):
        self.closed = True


class AutopilotTest(unittest.TestCase):
    def test_load_save_roundtrip_and_normalization(self):
        seq = {
            "format": FORMAT,
            "game": "sample",
            "seed": 1,
            "steps": [
                {"frames": 72, "press": ["move_right"], "note": "start run"},
                {"frames": 1, "press": ["jump"]},
                {"frames": 1, "release": ["jump"]},
                {"frames": 148},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "seq.json"
            autopilot.save_sequence(path, seq)
            loaded = autopilot.load_sequence(path)

        self.assertEqual(loaded["format"], FORMAT)
        self.assertEqual(loaded["game"], "sample")
        self.assertEqual(loaded["seed"], 1)
        self.assertEqual(loaded["steps"][0], {
            "frames": 72,
            "press": ["move_right"],
            "release": [],
            "note": "start run",
        })
        self.assertEqual(loaded["steps"][3], {
            "frames": 148,
            "press": [],
            "release": [],
        })

    def test_validation_errors(self):
        cases = [
            {"format": "wrong/1", "steps": [{"frames": 1}]},
            {"format": FORMAT, "steps": [{"frames": 0}]},
            {"format": FORMAT, "steps": [{"frames": True}]},
            {"format": FORMAT, "steps": []},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for idx, bad in enumerate(cases):
                path = Path(tmp) / f"bad_{idx}.json"
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.subTest(idx=idx):
                    with self.assertRaises(AutopilotError):
                        autopilot.load_sequence(path)
                    with self.assertRaises(AutopilotError):
                        autopilot.save_sequence(Path(tmp) / f"out_{idx}.json", bad)

    def test_sequence_from_events_sample(self):
        events = {
            "events": [
                {"frame": 73, "action": "jump", "pressed": False},
                {"frame": 0, "action": "move_right", "pressed": True},
                {"frame": 72, "action": "jump", "pressed": True},
                {"frame": 222, "action": "jump", "pressed": True},
                {"frame": 223, "action": "jump", "pressed": False},
            ]
        }
        seq = autopilot.sequence_from_events(events, game="sample", seed=1)
        self.assertEqual(seq["format"], FORMAT)
        self.assertEqual(seq["game"], "sample")
        self.assertEqual(seq["seed"], 1)
        self.assertEqual(seq["steps"], [
            {"frames": 72, "press": ["move_right"], "release": []},
            {"frames": 1, "press": ["jump"], "release": []},
            {"frames": 149, "press": [], "release": ["jump"]},
            {"frames": 1, "press": ["jump"], "release": []},
            {"frames": 1, "press": [], "release": ["jump"]},
        ])

    def test_sequence_from_events_merges_same_frame_and_leading_wait(self):
        events = [
            {"frame": 10, "action": "move_right", "pressed": True},
            {"frame": 10, "action": "dash", "pressed": True},
            {"frame": 15, "action": "dash", "pressed": False},
        ]
        seq = autopilot.sequence_from_events(events)
        self.assertEqual(seq["steps"], [
            {"frames": 10, "press": [], "release": []},
            {"frames": 5, "press": ["move_right", "dash"], "release": []},
            {"frames": 1, "press": [], "release": ["dash"]},
        ])

    def test_sequence_from_play_log(self):
        rows = [
            {"kind": "session", "game": "sample", "seed": 7},
            {"kind": "op", "frame": 72, "frames": 72, "press": ["move_right"], "release": []},
            {"kind": "snapshot", "frame": 72, "state": {}},
            {"kind": "op", "frame": 73, "frames": 1, "press": ["jump"]},
            {"kind": "op", "frame": 74, "frames": 1, "release": ["jump"]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "play.jsonl"
            log_path.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n",
                encoding="utf-8",
            )
            seq = autopilot.sequence_from_play_log(log_path)

        self.assertEqual(seq["format"], FORMAT)
        self.assertEqual(seq["game"], "sample")
        self.assertEqual(seq["seed"], 7)
        self.assertEqual(seq["steps"], [
            {"frames": 72, "press": ["move_right"], "release": []},
            {"frames": 1, "press": ["jump"], "release": []},
            {"frames": 1, "press": [], "release": ["jump"]},
        ])

    def test_sequence_from_play_log_empty_ops_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "empty.jsonl"
            log_path.write_text(json.dumps({"kind": "session", "game": "g"}) + "\n", encoding="utf-8")
            with self.assertRaises(AutopilotError):
                autopilot.sequence_from_play_log(log_path)

    def test_run_sequence_completes_and_collects_checkpoints(self):
        seq = {
            "format": FORMAT,
            "game": "sample",
            "seed": 1,
            "steps": [
                {"frames": 10, "press": ["move_right"]},
                {"frames": 20, "press": ["jump"]},
                {"frames": 30, "release": ["jump"]},
            ],
        }
        game = StubGame(checkpoint_frames={10: "cp_1", 45: "cp_2"})
        res = autopilot.run_sequence(game, seq, state_paths=("player/x",))

        self.assertEqual(len(game.calls), 3)
        self.assertEqual(game.calls[0], {
            "frames": 10, "press": ["move_right"], "release": [], "state": ["player/x"]
        })
        self.assertEqual(res, {
            "format": FORMAT,
            "steps_executed": 3,
            "steps_total": 3,
            "frames": 60,
            "checkpoints": ["cp_1", "cp_2"],
            "ended": False,
            "completed": True,
            "final_state": {"player/x": "val@60"},
        })

    def test_run_sequence_stops_on_ended(self):
        seq = {
            "format": FORMAT,
            "steps": [
                {"frames": 10, "press": ["move_right"]},
                {"frames": 20, "press": ["jump"]},
                {"frames": 30},
            ],
        }
        game = StubGame(checkpoint_frames={5: "cp_start"}, end_at_frame=25)
        res = autopilot.run_sequence(game, seq)

        self.assertEqual(res["steps_executed"], 2)
        self.assertEqual(res["steps_total"], 3)
        self.assertEqual(res["frames"], 30)
        self.assertEqual(res["checkpoints"], ["cp_start"])
        self.assertTrue(res["ended"])
        self.assertFalse(res["completed"])
        self.assertEqual(res["final_state"], {})

    def test_run_sequence_stops_on_runtime_error(self):
        seq = {
            "format": FORMAT,
            "steps": [
                {"frames": 10},
                {"frames": 10},
            ],
        }
        game = StubGame(raise_after_steps=1)
        res = autopilot.run_sequence(game, seq)

        self.assertEqual(res["steps_executed"], 1)
        self.assertEqual(res["steps_total"], 2)
        self.assertEqual(res["frames"], 10)
        self.assertTrue(res["ended"])
        self.assertFalse(res["completed"])

    def test_run_cli_unknown_arg_raises_value_error(self):
        with self.assertRaises(ValueError):
            autopilot.run_cli("proj", "seq.json", ["--unknown"])


if __name__ == "__main__":
    unittest.main()
