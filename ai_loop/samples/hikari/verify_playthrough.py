#!/usr/bin/env python3
"""B-1002: closed-loop AI-player verification of the sample game
'hikari no kakera' (灯りの欠片).

Drives the real game through ai_loop/aiplayer.py (B-306 lockstep control):
title -> walk to each shard -> collect -> light the lantern -> clear.
The judgement is mechanical, not visual:

  * telemetry checkpoints arrive in order: start, shard_1, shard_2,
    shard_3, lantern_lit
  * the declared state (B-307, Main.uzu_state) ends at shards=3,
    cleared=true
  * the state hash at game start is identical across two runs with the
    same seed (determinism probe)

Usage: python3 verify_playthrough.py [report.json]
Exit code 0 = all checks passed.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from aiplayer import Game  # noqa: E402

STATE = ["Main/Player:global_position", "Main:shards", "Main:cleared", "Main:juice_events", "Main:sfx_events"]
# (name, [waypoints (x, z) ..., target], shards expected after interacting)
# Waypoints follow the village's open lanes; every leg keeps clear of the
# obstacle radii in main.gd (houses 2.75, pond 2.65, trees 1.0, NPCs 0.85).
ROUTE = [
    ("shard_crate", [(6.1, 0.6)], 1),
    ("shard_pond", [(3.0, 3.2), (5.2, 6.9), (7.6, 6.4)], 2),
    ("shard_tree", [(0.5, 6.0), (0.5, -1.0), (-3.4, -6.2), (-7.6, -8.6), (-4.9, -8.6)], 3),
    ("lantern", [(-2.2, -8.2), (0.0, -8.0)], 3),
]
EXPECTED_EVENTS = ["start", "shard_1", "shard_2", "shard_3", "lantern_lit"]
EXPECTED_JUICE = ["pickup", "pickup", "pickup", "lantern"]


def _sfx_ok(events):
    """B-1704: the Lumina/SFX wiring fired for every formerly silent beat
    on the route: footsteps while walking, one pickup chime per shard,
    the lantern ignite, and the ambience reached the night stage."""
    if not isinstance(events, list):
        return False
    return (
        events.count("pickup_shard") == 3
        and events.count("lantern_ignite") == 1
        and events.count("footstep_start") >= 1
        and "ambient_0" in events
        and "ambient_3" in events
    )


def event_names(events):
    """Checkpoint ids from telemetry events ({"type": "checkpoint", "id": ...})."""
    names = []
    for e in events:
        if isinstance(e, dict) and e.get("type") == "checkpoint" and isinstance(e.get("id"), str):
            names.append(e["id"])
    return names


def pos_of(obs):
    v = obs.get("state", {}).get("Main/Player:global_position")
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return (float(v[0]), float(v[2]))
    return None


def _want_for(dx, dz):
    want = set()
    if abs(dx) > 0.25:
        want.add("move_right" if dx > 0 else "move_left")
    if abs(dz) > 0.25:
        want.add("move_down" if dz > 0 else "move_up")
    return want


def walk_to(game, target, max_steps=900, sink=None):
    """Steer by observed position. The world pushes the player out of round
    obstacles; steering straight at a target behind one deadlocks radially,
    so when progress stalls, detour tangentially for a while (the side
    flips if the first detour also stalls)."""
    tx, tz = target
    held = set()
    obs = game.observe(state=STATE)
    if sink is not None:
        sink += event_names(obs.get("events", []))
    best = float("inf")
    stall = 0
    detour_left = 0
    side = 1.0
    for _ in range(max_steps):
        p = pos_of(obs)
        if p is None:
            obs = game.step(frames=6, state=STATE)
            if sink is not None:
                sink += event_names(obs.get("events", []))
            continue
        dx, dz = tx - p[0], tz - p[1]
        dist = math.hypot(dx, dz)
        if dist < 1.3:
            if held:
                obs = game.step(frames=1, release=sorted(held), state=STATE)
            return obs
        if dist < best - 0.05:
            best = dist
            stall = 0
        else:
            stall += 1
        if detour_left > 0:
            detour_left -= 1
            n = max(dist, 0.001)
            ux, uz = dx / n, dz / n
            # Tangential heading: perpendicular to the target direction.
            want = _want_for(-uz * side, ux * side)
        else:
            want = _want_for(dx, dz)
            if stall >= 25:
                detour_left = 14
                stall = 0
                side = -side
        obs = game.step(
            frames=6,
            press=sorted(want - held),
            release=sorted(held - want),
            state=STATE,
        )
        if sink is not None:
            sink += event_names(obs.get("events", []))
        held = want
    raise RuntimeError("walk_to timed out heading for %s" % (target,))


def interact(game, sink=None):
    o = game.step(frames=2, press=["interact"])
    if sink is not None:
        sink += event_names(o.get("events", []))
    o = game.step(frames=10, release=["interact"], state=STATE)
    if sink is not None:
        sink += event_names(o.get("events", []))
    return o


def playthrough(seed):
    seen = []
    hashes = {}
    final = {}
    with Game(HERE, seed=seed) as game:
        o0 = game.observe(state=STATE)
        seen += event_names(o0.get("events", []))
        obs = game.step(frames=30, press=["interact"], state=STATE)
        seen += event_names(obs.get("events", []))
        o1 = game.step(frames=5, release=["interact"], state=STATE)
        seen += event_names(o1.get("events", []))
        hashes["start"] = game.state_hash()
        for name, waypoints, want_shards in ROUTE:
            obs = None
            for wp in waypoints:
                obs = walk_to(game, wp, sink=seen)
            for _try in range(4):
                obs = interact(game, sink=seen)
                if name == "lantern":
                    if obs.get("state", {}).get("Main:cleared"):
                        break
                elif obs.get("state", {}).get("Main:shards") == want_shards:
                    break
            hashes[name] = game.state_hash()
            final = obs.get("state", {})
    return {"events": seen, "hashes": hashes, "final_state": final}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "verify_report.json")
    runs = [playthrough(7), playthrough(7)]
    checks = []
    for i, run in enumerate(runs):
        subseq = [e for e in run["events"] if e in EXPECTED_EVENTS]
        checks.append({
            "run": i + 1,
            "checkpoints_in_order": subseq == EXPECTED_EVENTS,
            "final_shards": run["final_state"].get("Main:shards"),
            "final_cleared": run["final_state"].get("Main:cleared"),
            "juice_events": run["final_state"].get("Main:juice_events"),
            "juice_fired": run["final_state"].get("Main:juice_events") == EXPECTED_JUICE,
            "sfx_events": run["final_state"].get("Main:sfx_events"),
            "sfx_fired": _sfx_ok(run["final_state"].get("Main:sfx_events")),
        })
    report = {
        "game": "hikari no kakera (ai_loop/samples/hikari)",
        "tool": "ai_loop/aiplayer.py (B-306) + state hash (B-307)",
        "runs": runs,
        "checks": checks,
        "start_hash_deterministic": runs[0]["hashes"].get("start") == runs[1]["hashes"].get("start"),
    }
    report["passed"] = all(
        c["checkpoints_in_order"] and c["final_shards"] == 3 and c["final_cleared"] is True
        and c["juice_fired"] and c["sfx_fired"]
        for c in checks
    ) and report["start_hash_deterministic"]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("UZU_RESULT " + json.dumps({
        "passed": report["passed"],
        "checks": checks,
        "start_hash_deterministic": report["start_hash_deterministic"],
        "report": out_path,
    }, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
