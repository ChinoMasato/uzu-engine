#!/usr/bin/env python3
"""Headless verification of the Star Horse sample race (B-1329).

Runs the project with --starhorse-autoplay (fixed seed 1329, race at
30x, commentary queue in fast mode) and checks the JSON the game writes:

  * the race completes: 8 results, the winner has a finish time and
    the finishers are ordered by it;
  * the commentary fired in phase order (gate-in -> ready -> start ->
    start note -> early -> mid -> final straight -> the move -> 200m
    -> 100m -> goal -> win style -> upset -> crowd -> closing), with
    the mandatory lines present and 29_closing last.

Usage: python3 verify_race.py [project-dir] [out.json]
Exit code 0 on pass.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import uzu  # noqa: E402

PHASE_RANK = {
    "pre_gatein": 0, "pre_ready": 1, "start": 2, "start_note": 3,
    "early": 4, "mid": 5, "final_straight": 6, "final_move": 7,
    "final_200": 8, "final_100": 9, "goal": 10, "win_style": 11,
    "upset": 12, "crowd": 13, "closing": 14,
}


def main() -> int:
    project = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else HERE
    out = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(HERE, "verify_report.json")
    cmd = [uzu.find_godot(), "--headless", "--path", project,
           "--fixed-fps", "60", "--", "--starhorse-autoplay", out]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not os.path.exists(out):
        sys.stderr.write(run.stdout + run.stderr)
        print("FAIL: the game wrote no report")
        return 1
    with open(out, encoding="utf-8") as f:
        data = json.load(f)

    problems = []
    results = data["results"]
    if len(results) != 8:
        problems.append(f"expected 8 results, got {len(results)}")
    times = [r["finish_t"] for r in results if r["finish_t"] > 0]
    if not times:
        problems.append("no horse finished")
    if times != sorted(times):
        problems.append(f"finishers not ordered by time: {times}")
    if len(times) < 6:
        problems.append(f"only {len(times)} horses finished within the window")

    log = data["commentary"]
    voices = [e["voice"] for e in log]
    ranks = [PHASE_RANK[e["phase"]] for e in log]
    if ranks != sorted(ranks):
        problems.append(f"commentary phases out of order: {[e['phase'] for e in log]}")
    for mandatory in ("01_pre_gatein", "02_pre_ready", "03_start",
                      "13_final_straight", "17_final_200m", "18_final_100m",
                      "28_crowd", "29_closing"):
        if mandatory not in voices:
            problems.append(f"mandatory line missing: {mandatory}")
    if not any(v in voices for v in ("04_start_clean", "05_start_late")):
        problems.append("no start note (04/05)")
    if not any(v.startswith(("19_", "20_", "21_", "22_")) for v in voices):
        problems.append("no goal line (19-22)")
    if not any(v.startswith(("23_", "24_", "25_", "26_")) for v in voices):
        problems.append("no win-style line (23-26)")
    if voices and voices[-1] != "29_closing":
        problems.append(f"last line is {voices[-1]}, not 29_closing")
    if len(voices) != len(set(voices)):
        problems.append(f"a line fired twice: {voices}")

    print(json.dumps({"ok": not problems, "winner": results[0]["name"] if results else None,
                      "finishers": len(times), "voices": voices,
                      "problems": problems}, ensure_ascii=False, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
