"""Unit tests for ai_loop/play_log.py (B-313) using only stdlib unittest and a Game stub."""

import json
import os
import sys
import tempfile
import unittest

AI_LOOP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AI_LOOP_DIR not in sys.path:
    sys.path.insert(0, AI_LOOP_DIR)

import play_log  # noqa: E402


class StubGame:
    """Minimal stub implementing aiplayer.Game's step/observe and auxiliary methods."""

    def __init__(self, project="/tmp/demo_game", seed=42, step_script=None, state_values=None):
        self.project = project
        self.seed = seed
        self._step_script = list(step_script or [])
        self._state_values = dict(state_values or {"/root/Player:hp": 100, "/root/Player:x": 0})
        self.frame = 0
        self.last = {"frame": 0, "events": []}
        self.step_calls = []
        self.observe_calls = []
        self.saved_slots = []
        self.restored_slots = []

    def step(self, frames=1, press=(), release=(), state=None, image=None):
        self.step_calls.append(
            {
                "frames": frames,
                "press": list(press),
                "release": list(release),
                "state": list(state) if state is not None else None,
                "image": image,
            }
        )
        self.frame += frames
        scripted = self._step_script.pop(0) if self._step_script else {}
        if "state_updates" in scripted:
            self._state_values.update(scripted["state_updates"])

        obs = {
            "frame": scripted.get("frame", self.frame),
            "events": list(scripted.get("events", [])),
            "done": scripted.get("done", False),
        }
        if "token" in scripted:
            obs["token"] = scripted["token"]
        if state is not None:
            obs["state"] = {p: self._state_values.get(p) for p in state}
        self.last = obs
        return obs

    def observe(self, state=None, image=None):
        self.observe_calls.append(
            {
                "state": list(state) if state is not None else None,
                "image": image,
            }
        )
        if state is None and image is None:
            return self.last
        return self.step(frames=1, state=state, image=image)

    def save(self, slot):
        self.saved_slots.append(slot)
        return {"ok": True, "slot": slot}

    def restore(self, slot):
        self.restored_slots.append(slot)
        return {"ok": True, "slot": slot}

    def state_hash(self):
        return f"hash-{self.frame}"


class TestPlayLogWriterAndSummarize(unittest.TestCase):
    def test_writer_format_and_summarize_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "nested", "run.jsonl")
            state_paths = ["/root/Player:hp", "/root/Player:alive"]

            with play_log.PlayLogWriter(log_path) as writer:
                writer.session("/games/platformer", seed=123, state_paths=state_paths)
                writer.op(frame=1, frames=1, press=["right"], release=[])
                writer.state(frame=1, snapshot={"/root/Player:hp": 100, "/root/Player:alive": True})
                writer.op(frame=5, frames=4, press=["jump"], release=["right"])
                writer.state(frame=5, snapshot={"/root/Player:hp": 100, "/root/Player:alive": True})
                writer.checkpoint(frame=5, checkpoint_id="cp_1")
                writer.op(frame=10, frames=5, press=[], release=["jump"])
                writer.state(frame=10, snapshot={"/root/Player:hp": 80, "/root/Player:alive": True})
                writer.checkpoint(frame=12, checkpoint_id="cp_2")
                writer.state(frame=12, snapshot={"/root/Player:hp": 80, "/root/Player:alive": False})
                writer.end(frame=12, reason="goal")

            with open(log_path, "r", encoding="utf-8") as fp:
                lines = [json.loads(line) for line in fp if line.strip()]

            self.assertEqual(len(lines), 11)
            self.assertEqual(
                lines[0],
                {
                    "kind": "session",
                    "format": "uzu-play-log/1",
                    "game": "/games/platformer",
                    "seed": 123,
                    "state_paths": state_paths,
                },
            )
            self.assertEqual(
                lines[1],
                {"kind": "op", "frame": 1, "frames": 1, "press": ["right"], "release": []},
            )
            self.assertEqual(lines[-1], {"kind": "end", "frame": 12, "reason": "goal"})

            summary = play_log.summarize(log_path)
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["format"], "uzu-play-log/1")
            self.assertEqual(summary["game"], "/games/platformer")
            self.assertEqual(summary["seed"], 123)
            self.assertEqual(summary["ops"], 3)
            self.assertEqual(summary["frames"], 12)
            self.assertEqual(summary["checkpoints"], ["cp_1", "cp_2"])
            self.assertEqual(
                summary["state_transitions"],
                {
                    "/root/Player:hp": [100, 80],
                    "/root/Player:alive": [True, False],
                },
            )
            self.assertEqual(
                summary["final_state"],
                {"/root/Player:hp": 80, "/root/Player:alive": False},
            )
            self.assertTrue(summary["ended"])


class TestRecorder(unittest.TestCase):
    def test_recorder_ops_checkpoints_observe_state_and_passthrough(self):
        script = [
            {"token": "obs-1", "events": []},
            {
                "token": "obs-2",
                "events": [{"type": "checkpoint", "id": "shard_1"}],
                "state_updates": {"/root/Player:hp": 90},
            },
            {
                "token": "obs-3",
                "events": [{"type": "checkpoint", "id": "shard_2"}],
                "state_updates": {"/root/Player:hp": 75},
            },
        ]
        stub = StubGame(project="/proj/test", seed=77, step_script=script)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "recorded.jsonl")
            with play_log.record_game(
                stub,
                log_path,
                game_label="/proj/override",
                state_paths=["/root/Player:hp"],
            ) as rec:
                obs1 = rec.step(frames=2, press=["right"])
                self.assertEqual(obs1["token"], "obs-1")
                self.assertIs(obs1, stub.last)

                obs2 = rec.step(frames=3, press=["jump"], release=["right"])
                self.assertEqual(obs2["token"], "obs-2")
                self.assertIs(obs2, stub.last)

                # observe() with no args returns last without adding a state entry
                last_obs = rec.observe()
                self.assertIs(last_obs, obs2)

                # observe(state=...) advances 1 frame and records a state entry
                obs3 = rec.observe(state=["/root/Player:hp"])
                self.assertEqual(obs3["token"], "obs-3")
                self.assertEqual(obs3["state"], {"/root/Player:hp": 75})

                # __getattr__ passthrough for Game helper methods
                save_res = rec.save("slot_a")
                self.assertEqual(save_res, {"ok": True, "slot": "slot_a"})
                self.assertEqual(rec.state_hash(), f"hash-{stub.frame}")

            self.assertEqual(stub.saved_slots, ["slot_a"])

            summary = play_log.summarize(log_path)
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["game"], "/proj/override")
            self.assertEqual(summary["seed"], 77)
            self.assertEqual(summary["ops"], 2)
            self.assertEqual(summary["frames"], 6)
            self.assertEqual(summary["checkpoints"], ["shard_1", "shard_2"])
            self.assertEqual(summary["state_transitions"], {"/root/Player:hp": [75]})
            self.assertEqual(summary["final_state"], {"/root/Player:hp": 75})
            self.assertTrue(summary["ended"])

    def test_snapshot_every_records_periodic_state(self):
        script = [
            {"state_updates": {"/root/Player:x": 10}},
            {"state_updates": {"/root/Player:x": 20}},
            {},  # triggered by periodic observe(state=...) at frame >= 5
            {"state_updates": {"/root/Player:x": 30}},
            {"state_updates": {"/root/Player:x": 40}},
            {},  # triggered by periodic observe(state=...) at frame >= 11
        ]
        stub = StubGame(seed=9, step_script=script, state_values={"/root/Player:x": 0})

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "periodic.jsonl")
            with play_log.record_game(
                stub,
                log_path,
                state_paths=["/root/Player:x"],
                snapshot_every=5,
            ) as rec:
                rec.step(frames=3, press=["right"])
                rec.step(frames=3, press=["right"])
                rec.step(frames=3, press=["right"])
                rec.step(frames=3, press=["right"])

            self.assertEqual(len(stub.observe_calls), 2)
            summary = play_log.summarize(log_path)
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["ops"], 4)
            self.assertEqual(summary["state_transitions"], {"/root/Player:x": [20, 40]})
            self.assertEqual(summary["final_state"], {"/root/Player:x": 40})

    def test_snapshot_every_disabled_when_state_paths_empty(self):
        stub = StubGame()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "no_paths.jsonl")
            with play_log.record_game(stub, log_path, state_paths=(), snapshot_every=2) as rec:
                rec.step(frames=5, press=["right"])
            self.assertEqual(stub.observe_calls, [])


class TestMalformedLogAndCli(unittest.TestCase):
    def test_corrupted_json_line_returns_ok_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "broken.jsonl")
            with open(log_path, "w", encoding="utf-8") as fp:
                fp.write(
                    json.dumps(
                        {
                            "kind": "session",
                            "format": "uzu-play-log/1",
                            "game": "/g",
                            "seed": 1,
                            "state_paths": [],
                        }
                    )
                    + "\n"
                )
                fp.write(json.dumps({"kind": "op", "frame": 1, "frames": 1, "press": [], "release": []}) + "\n")
                fp.write("{this is not valid json\n")

            summary = play_log.summarize(log_path)
            self.assertFalse(summary["ok"])
            self.assertIn("error", summary)
            self.assertIn("line 3", summary["error"])

    def test_wrong_format_returns_ok_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "wrong_fmt.jsonl")
            with open(log_path, "w", encoding="utf-8") as fp:
                fp.write(
                    json.dumps(
                        {
                            "kind": "session",
                            "format": "uzu-play-log/999",
                            "game": "/g",
                            "seed": None,
                            "state_paths": [],
                        }
                    )
                    + "\n"
                )

            summary = play_log.summarize(log_path)
            self.assertFalse(summary["ok"])
            self.assertIn("error", summary)

    def test_run_cli_writes_summary_to_out_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "cli.jsonl")
            out_path = os.path.join(tmpdir, "out", "summary.json")

            with play_log.PlayLogWriter(log_path) as writer:
                writer.session("/games/cli_test", seed=5, state_paths=["/root:score"])
                writer.op(frame=2, frames=2, press=["action"], release=[])
                writer.checkpoint(frame=2, checkpoint_id="start")
                writer.state(frame=2, snapshot={"/root:score": 10})
                writer.end(frame=2, reason="done")

            result = play_log.run_cli(log_path, ["--out", out_path])
            self.assertTrue(result["ok"])
            self.assertTrue(os.path.isfile(out_path))

            with open(out_path, "r", encoding="utf-8") as fp:
                written = json.load(fp)
            self.assertEqual(written, result)
            self.assertEqual(written["checkpoints"], ["start"])
            self.assertEqual(written["final_state"], {"/root:score": 10})


if __name__ == "__main__":
    unittest.main()
