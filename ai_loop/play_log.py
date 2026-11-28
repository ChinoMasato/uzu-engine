"""Standardized play log writer, transparent Game recorder, summarizer, and CLI (B-313).

Log format ``uzu-play-log/1`` (JSONL, one JSON object per line):
- ``{"kind": "session", "format": "uzu-play-log/1", "game": <str>, "seed": <int|null>, "state_paths": [...]}``
- ``{"kind": "op", "frame": <int>, "frames": <int>, "press": [...], "release": [...]}``
- ``{"kind": "state", "frame": <int>, "state": {<path>: <value>, ...}}``
- ``{"kind": "checkpoint", "frame": <int>, "id": <str>}``
- ``{"kind": "end", "frame": <int>, "reason": <str>}``
"""

from __future__ import annotations

import json
import os

FORMAT = "uzu-play-log/1"


class PlayLogError(Exception):
    """Raised on play_log CLI or writer errors."""


def _same_value(a, b) -> bool:
    return a == b and (isinstance(a, bool) is isinstance(b, bool))


class PlayLogWriter:
    """Append-only JSONL writer for uzu-play-log/1 with immediate flush per entry."""

    def __init__(self, path):
        self.path = os.fspath(path)
        parent = os.path.dirname(os.path.abspath(self.path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._fp = open(self.path, "w", encoding="utf-8")
        self._closed = False

    def _write(self, entry: dict) -> None:
        if self._closed:
            raise PlayLogError("cannot write to a closed PlayLogWriter")
        self._fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._fp.flush()

    def session(self, game, seed=None, state_paths=()) -> None:
        game_str = os.fspath(game) if isinstance(game, os.PathLike) else ("" if game is None else str(game))
        self._write(
            {
                "kind": "session",
                "format": FORMAT,
                "game": game_str,
                "seed": seed,
                "state_paths": list(state_paths) if state_paths is not None else [],
            }
        )

    def op(self, frame: int, frames: int, press=(), release=()) -> None:
        self._write(
            {
                "kind": "op",
                "frame": int(frame),
                "frames": int(frames),
                "press": list(press),
                "release": list(release),
            }
        )

    def state(self, frame: int, snapshot: dict) -> None:
        self._write(
            {
                "kind": "state",
                "frame": int(frame),
                "state": dict(snapshot),
            }
        )

    def checkpoint(self, frame: int, checkpoint_id: str) -> None:
        self._write(
            {
                "kind": "checkpoint",
                "frame": int(frame),
                "id": str(checkpoint_id),
            }
        )

    def end(self, frame: int, reason: str = "done") -> None:
        self._write(
            {
                "kind": "end",
                "frame": int(frame),
                "reason": str(reason),
            }
        )

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._fp.close()

    def __enter__(self) -> "PlayLogWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class Recorder:
    """Transparent wrapper around ``aiplayer.Game`` that records operations, states, and checkpoints."""

    def __init__(
        self,
        game,
        log_path,
        game_label: str = "",
        state_paths=(),
        snapshot_every: int = 0,
    ):
        self._game = game
        self._state_paths = list(state_paths) if state_paths is not None else []
        self._snapshot_every = int(snapshot_every) if snapshot_every else 0
        self._frame = 0
        self._last_snapshot_frame = 0
        self._closed = False

        label = game_label
        if not label:
            label = getattr(game, "project", "") or getattr(game, "game", "") or ""
        seed = getattr(game, "seed", None)

        self._writer = PlayLogWriter(log_path)
        self._writer.session(label, seed, self._state_paths)

    def _update_frame(self, obs, delta: int = 0) -> int:
        if isinstance(obs, dict) and obs.get("frame") is not None:
            self._frame = int(obs["frame"])
        else:
            self._frame += int(delta)
        return self._frame

    def _record_events(self, frame: int, obs) -> None:
        if not isinstance(obs, dict):
            return
        events = obs.get("events")
        if not isinstance(events, (list, tuple)):
            return
        for ev in events:
            if isinstance(ev, dict) and ev.get("type") == "checkpoint" and "id" in ev:
                self._writer.checkpoint(frame, ev["id"])

    def step(self, frames: int = 1, press=(), release=(), state=None, image=None):
        obs = self._game.step(
            frames=frames,
            press=press,
            release=release,
            state=state,
            image=image,
        )
        frame = self._update_frame(obs, delta=frames)
        self._writer.op(frame, frames, press, release)
        self._record_events(frame, obs)

        wrote_state = False
        if state is not None and isinstance(obs, dict) and obs.get("state") is not None:
            self._writer.state(frame, obs["state"])
            self._last_snapshot_frame = frame
            wrote_state = True

        if (
            not wrote_state
            and self._snapshot_every > 0
            and self._state_paths
            and (frame - self._last_snapshot_frame) >= self._snapshot_every
        ):
            snap_obs = self._game.observe(state=list(self._state_paths))
            snap_frame = self._update_frame(snap_obs, delta=1)
            self._record_events(snap_frame, snap_obs)
            if isinstance(snap_obs, dict) and snap_obs.get("state") is not None:
                self._writer.state(snap_frame, snap_obs["state"])
            self._last_snapshot_frame = snap_frame

        return obs

    def observe(self, state=None, image=None):
        obs = self._game.observe(state=state, image=image)
        advances = state is not None or image is not None
        frame = self._update_frame(obs, delta=1 if advances else 0)
        if advances:
            self._record_events(frame, obs)
        if state is not None and isinstance(obs, dict) and obs.get("state") is not None:
            self._writer.state(frame, obs["state"])
            self._last_snapshot_frame = frame
        return obs

    def close(self, reason: str = "done") -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.end(self._frame, reason=reason)
        finally:
            self._writer.close()

    def __enter__(self) -> "Recorder":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        reason = "done" if exc_type is None else f"error:{exc_type.__name__}"
        self.close(reason=reason)

    def __getattr__(self, name: str):
        return getattr(self._game, name)


def record_game(
    game,
    log_path,
    game_label: str = "",
    state_paths=(),
    snapshot_every: int = 0,
) -> Recorder:
    """Wrap an ``aiplayer.Game`` instance and record play to ``log_path``."""
    return Recorder(
        game=game,
        log_path=log_path,
        game_label=game_label,
        state_paths=state_paths,
        snapshot_every=snapshot_every,
    )


def summarize(path) -> dict:
    """Read a ``uzu-play-log/1`` JSONL file and return a structured summary dict.

    Never raises on malformed logs; returns ``ok=False`` and an ``error`` message instead.
    """
    game = ""
    seed = None
    ops = 0
    frames = 0
    checkpoints = []
    state_transitions = {}
    final_state = {}
    ended = False
    has_session = False

    def _error(msg: str) -> dict:
        return {
            "format": FORMAT,
            "ok": False,
            "error": msg,
            "game": game,
            "seed": seed,
            "ops": ops,
            "frames": frames,
            "checkpoints": checkpoints,
            "state_transitions": state_transitions,
            "final_state": final_state,
            "ended": ended,
        }

    try:
        log_path = os.fspath(path)
    except TypeError as exc:
        return _error(f"invalid path: {exc}")

    try:
        with open(log_path, "r", encoding="utf-8") as fp:
            for lineno, raw in enumerate(fp, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    return _error(f"line {lineno}: invalid JSON: {exc}")

                if not isinstance(entry, dict):
                    return _error(f"line {lineno}: entry must be a JSON object")

                kind = entry.get("kind")
                if not isinstance(kind, str) or not kind:
                    return _error(f"line {lineno}: missing or invalid 'kind'")

                if not has_session:
                    if kind != "session":
                        return _error(f"line {lineno}: first entry must be 'session', got {kind!r}")
                    fmt = entry.get("format")
                    if fmt != FORMAT:
                        return _error(f"line {lineno}: unsupported format {fmt!r}, expected {FORMAT!r}")
                    has_session = True
                    game = entry.get("game", "")
                    seed = entry.get("seed", None)
                    continue

                entry_frame = entry.get("frame")
                if isinstance(entry_frame, int) and not isinstance(entry_frame, bool):
                    if entry_frame > frames:
                        frames = entry_frame

                if kind == "session":
                    fmt = entry.get("format")
                    if fmt != FORMAT:
                        return _error(f"line {lineno}: unsupported format {fmt!r}, expected {FORMAT!r}")
                    game = entry.get("game", game)
                    seed = entry.get("seed", seed)
                elif kind == "op":
                    ops += 1
                elif kind == "state":
                    snap = entry.get("state")
                    if not isinstance(snap, dict):
                        return _error(f"line {lineno}: state entry missing 'state' object")
                    for spath, val in snap.items():
                        final_state[spath] = val
                        seq = state_transitions.setdefault(spath, [])
                        if not seq or not _same_value(seq[-1], val):
                            seq.append(val)
                elif kind == "checkpoint":
                    if "id" not in entry:
                        return _error(f"line {lineno}: checkpoint entry missing 'id'")
                    checkpoints.append(entry["id"])
                elif kind == "end":
                    ended = True
                else:
                    return _error(f"line {lineno}: unknown entry kind {kind!r}")
    except OSError as exc:
        return _error(f"failed to read log: {exc}")
    except UnicodeDecodeError as exc:
        return _error(f"invalid UTF-8 in log: {exc}")

    if not has_session:
        return _error("empty play log: missing 'session' entry")

    return {
        "format": FORMAT,
        "ok": True,
        "game": game,
        "seed": seed,
        "ops": ops,
        "frames": frames,
        "checkpoints": checkpoints,
        "state_transitions": state_transitions,
        "final_state": final_state,
        "ended": ended,
    }


def run_cli(log_path, argv) -> dict:
    """CLI entrypoint called by uzu.py: ``uzu.py play-log <log.jsonl> [--out <summary.json>]``."""
    out_path = None
    args = list(argv or ())
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "--out":
            if i + 1 >= len(args):
                raise ValueError("--out requires a file path")
            out_path = args[i + 1]
            i += 2
        elif tok.startswith("--out="):
            out_path = tok.split("=", 1)[1]
            if not out_path:
                raise ValueError("--out requires a file path")
            i += 1
        else:
            raise ValueError(f"unknown argument: {tok}")

    summary = summarize(log_path)
    if out_path is not None:
        out_abs = os.path.abspath(out_path)
        parent = os.path.dirname(out_abs)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_abs, "w", encoding="utf-8") as fp:
            json.dump(summary, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
    return summary
