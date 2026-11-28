#!/usr/bin/env python3
"""Playthrough verification for the moonpost sample (B-1005).

Drives the postman with the aiplayer harness to the three mailboxes,
delivers at each, and checks the clear state. The run is recorded with
the B-313 play log (ai_loop/play_log.py) and the log's summary is part
of the verdict.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from aiplayer import Game  # noqa: E402
import play_log  # noqa: E402

STATE = ["Main:delivered", "Main:cleared", "Main/Player:global_position"]
TARGETS = [(-3.6, -11.35), (0.95, -11.35), (5.25, -11.35)]


def _pos(obs):
    p = obs["state"]["Main/Player:global_position"]
    if isinstance(p, dict):
        return p["x"], p["z"]
    return p[0], p[2]


def _goto(rec, tx, tz, budget=900):
    frames = 0
    while frames < budget:
        obs = rec.observe(state=STATE)
        x, z = _pos(obs)
        dx, dz = tx - x, tz - z
        if math.hypot(dx, dz) < 0.45:
            return True
        press = []
        if dx > 0.15:
            press.append("move_right")
        elif dx < -0.15:
            press.append("move_left")
        if dz < -0.15:
            press.append("move_up")
        elif dz > 0.15:
            press.append("move_down")
        rec.step(frames=6, press=press, state=STATE)
        rec.step(frames=1, release=press)
        frames += 7
    return False


def main():
    log_path = os.path.join(HERE, "play_log.jsonl")
    checks = {}
    with Game(HERE, seed=7) as game:
        with play_log.record_game(game, log_path, game_label="moonpost",
                                   state_paths=STATE, snapshot_every=120) as rec:
            obs = rec.observe(state=STATE)
            checks["spawn_delivered_0"] = obs["state"]["Main:delivered"] == 0
            for i, (tx, tz) in enumerate(TARGETS, start=1):
                checks[f"reach_{i}"] = _goto(rec, tx, tz)
                rec.step(frames=3, press=["interact"], state=STATE)
                rec.step(frames=2, release=["interact"])
                obs = rec.observe(state=STATE)
                checks[f"delivered_{i}"] = obs["state"]["Main:delivered"] == i
            final = rec.observe(state=STATE)
            checks["cleared"] = final["state"]["Main:cleared"] is True
    summary = play_log.summarize(log_path)
    checks["play_log_ok"] = summary["ok"] and summary["checkpoints"] == ["deliver_1", "deliver_2", "deliver_3", "cleared"]
    ok = all(checks.values())
    print(json.dumps({"ok": ok, "checks": checks, "play_log": summary}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
