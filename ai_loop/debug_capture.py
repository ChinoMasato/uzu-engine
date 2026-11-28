"""Standard debug capture for autopilot runs (B-316).

Wraps a Game (or a play_log.Recorder) and saves screenshots at the
moments an AI debugger most needs them: the first frame, every
checkpoint, every N frames, and the final frame. A manifest
(uzu-debug-capture/1) maps each shot to its frame and the checkpoint
or log position it belongs to, so the images can be pulled up later
by frame number or checkpoint name.

Standard library only; the planner logic is engine-free and unit
tested. Actual captures need a renderer (Game(render=True)).
"""

from __future__ import annotations

import json
import os
import re

FORMAT = "uzu-debug-capture/1"


def _checkpoint_names(obs):
    """Checkpoint ids carried by one observation, in order."""
    names = []
    if not isinstance(obs, dict):
        return names
    for ev in obs.get("events") or ():
        if isinstance(ev, dict) and ev.get("type") == "checkpoint" and "id" in ev:
            names.append(ev["id"])
    return names


def _is_done(obs):
    return isinstance(obs, dict) and bool(obs.get("done") or obs.get("ended"))


class CapturePlanner:
    """Decides which steps should save a screenshot.

    Feed every observation with feed(); due() is asked twice per
    step: with the previous observation before the step, and with
    the step's own observation after it. Captures are per step (the
    image a step produces is its final frame), so a checkpoint shot
    shows the frame the checkpoint fired on.
    """

    def __init__(self, every_frames=0, at_checkpoints=True, at_end=True):
        self.every_frames = int(every_frames) if every_frames else 0
        self.at_checkpoints = bool(at_checkpoints)
        self.at_end = bool(at_end)
        self.checkpoints = []
        self._seen = set()
        self._pending = []
        self._interval_fired_for = None

    def add_pending(self, reason):
        self._pending.append(reason)

    def feed(self, obs):
        if not isinstance(obs, dict):
            return
        frame = obs.get("frame")
        if self.at_checkpoints:
            for name in _checkpoint_names(obs):
                if name not in self._seen:
                    self._seen.add(name)
                    self.checkpoints.append(name)
                    self._pending.append({
                        "reason": "checkpoint",
                        "checkpoint": name,
                        "checkpoint_frame": frame,
                    })
        if self.at_end and _is_done(obs):
            self._pending.append({
                "reason": "end",
                "checkpoint": None,
                "checkpoint_frame": None,
            })

    def due(self, obs):
        """Reasons to capture for this observation; consumes pending reasons."""
        reasons = list(self._pending)
        self._pending = []
        frame = obs.get("frame") if isinstance(obs, dict) else None
        if (
            self.every_frames > 0
            and isinstance(frame, int)
            and frame > 0
            and frame % self.every_frames == 0
            and frame != self._interval_fired_for
        ):
            self._interval_fired_for = frame
            reasons.append({
                "reason": "interval",
                "checkpoint": None,
                "checkpoint_frame": None,
            })
        return reasons


def _shot_name(frame, reasons):
    primary = reasons[0] if reasons else {"reason": "frame"}
    for r in reasons:
        if r.get("reason") == "checkpoint" and r.get("checkpoint"):
            safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(r["checkpoint"]))
            return f"{frame:06d}_checkpoint_{safe}.png"
    return f"{frame:06d}_{primary.get('reason', 'frame')}.png"


class CaptureGame:
    """Transparent Game wrapper that saves planned screenshots."""

    def __init__(self, target, out_dir, planner=None):
        self._target = target
        self._out_dir = str(out_dir)
        os.makedirs(self._out_dir, exist_ok=True)
        self._planner = planner if planner is not None else CapturePlanner()
        self._planner.add_pending({
            "reason": "start",
            "checkpoint": None,
            "checkpoint_frame": None,
        })
        self._last_obs = {"frame": 0, "events": [], "done": False, "ended": False}
        self._shots = []

    @property
    def shots(self):
        return list(self._shots)

    def _record_shot(self, tmp_path, frame, reasons):
        if not tmp_path or not os.path.exists(tmp_path):
            return
        name = _shot_name(frame, reasons)
        dest = os.path.join(self._out_dir, name)
        os.replace(tmp_path, dest)
        self._shots.append({"file": name, "frame": frame, "reasons": reasons})

    def step(self, frames=1, press=(), release=(), state=None):
        pre = self._planner.due(self._last_obs)
        tmp = os.path.join(self._out_dir, "shot_tmp.png")
        obs = self._target.step(
            frames=frames, press=press, release=release, state=state, image=tmp
        )
        if isinstance(obs, dict):
            self._last_obs = obs
        self._planner.feed(obs)
        post = self._planner.due(obs) if isinstance(obs, dict) else []
        reasons = pre + post
        if reasons:
            frame = int(obs.get("frame", 0)) if isinstance(obs, dict) else 0
            self._record_shot(tmp, frame, reasons)
        elif os.path.exists(tmp):
            os.remove(tmp)
        return obs

    def observe(self, state=None):
        obs = self._target.observe(state=state)
        if isinstance(obs, dict):
            self._last_obs = obs
        self._planner.feed(obs)
        return obs

    def manifest(self):
        return {
            "format": FORMAT,
            "shots": list(self._shots),
            "checkpoints": list(self._planner.checkpoints),
        }

    def close(self):
        close = getattr(self._target, "close", None)
        if close is not None:
            close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __getattr__(self, name):
        return getattr(self._target, name)


def _parse_args(argv):
    opts = {
        "every": 0,
        "no_checkpoints": False,
        "no_end": False,
        "log": None,
        "seed": None,
    }
    args = list(argv)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--every":
            if i + 1 >= len(args):
                raise ValueError("--every requires an integer argument")
            opts["every"] = int(args[i + 1])
            i += 2
        elif arg.startswith("--every="):
            opts["every"] = int(arg.split("=", 1)[1])
            i += 1
        elif arg == "--no-checkpoints":
            opts["no_checkpoints"] = True
            i += 1
        elif arg == "--no-end":
            opts["no_end"] = True
            i += 1
        elif arg == "--log":
            if i + 1 >= len(args):
                raise ValueError("--log requires a file path")
            opts["log"] = args[i + 1]
            i += 2
        elif arg.startswith("--log="):
            opts["log"] = arg.split("=", 1)[1]
            i += 1
        elif arg == "--seed":
            if i + 1 >= len(args):
                raise ValueError("--seed requires an integer argument")
            opts["seed"] = int(args[i + 1])
            i += 2
        elif arg.startswith("--seed="):
            opts["seed"] = int(arg.split("=", 1)[1])
            i += 1
        else:
            raise ValueError(f"unknown argument: {arg}")
    return opts


def run_cli(project, sequence_path, out_dir, argv):
    """Replay a sequence with standard debug capture; returns the manifest."""
    opts = _parse_args(argv)

    import autopilot
    import play_log
    from aiplayer import Game

    sequence = autopilot.load_sequence(sequence_path)
    game = Game(project, seed=opts["seed"], render=True)
    target = game
    recorder = None
    if opts["log"]:
        recorder = play_log.Recorder(game, opts["log"])
        target = recorder
    planner = CapturePlanner(
        every_frames=opts["every"],
        at_checkpoints=not opts["no_checkpoints"],
        at_end=not opts["no_end"],
    )
    cap = CaptureGame(target, out_dir, planner=planner)
    try:
        run = autopilot.run_sequence(cap, sequence)
    finally:
        if recorder is not None:
            recorder.close()
        game.close()

    manifest = cap.manifest()
    manifest.update({
        "project": str(project),
        "sequence": str(sequence_path),
        "log": opts["log"],
        "run": run,
        "ok": bool(run.get("completed") or run.get("ended")),
    })
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(str(out_dir), "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return manifest
