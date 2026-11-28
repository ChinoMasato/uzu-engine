"""Standard autopilot sequence loader, converter, and runner for ai_loop."""

import json
from pathlib import Path

FORMAT = "uzu-autopilot/1"


class AutopilotError(Exception):
    """Raised when an autopilot sequence or log is invalid."""


def _import_aiplayer():
    try:
        from . import aiplayer
        return aiplayer
    except ImportError:
        import aiplayer
        return aiplayer


def _import_play_log():
    try:
        from . import play_log
        return play_log
    except ImportError:
        import play_log
        return play_log


def _normalize_actions(step, field, index):
    if field not in step:
        return []
    val = step[field]
    if not isinstance(val, list) or not all(isinstance(item, str) for item in val):
        raise AutopilotError(f"step {index}: '{field}' must be a list of strings")
    return list(val)


def _normalize_sequence(sequence):
    if not isinstance(sequence, dict):
        raise AutopilotError("sequence must be a dict")

    fmt = sequence.get("format")
    if fmt != FORMAT:
        raise AutopilotError(f"invalid format: {fmt!r} (expected {FORMAT!r})")

    game = sequence.get("game", "")
    if not isinstance(game, str):
        raise AutopilotError("'game' must be a string")

    seed = sequence.get("seed", None)
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise AutopilotError("'seed' must be an int or None")

    steps = sequence.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        raise AutopilotError("'steps' must be a non-empty list")

    norm_steps = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise AutopilotError(f"step {i}: must be a dict")

        frames = step.get("frames")
        if isinstance(frames, bool) or not isinstance(frames, int) or frames <= 0:
            raise AutopilotError(f"step {i}: 'frames' must be a positive integer")

        norm_step = {
            "frames": frames,
            "press": _normalize_actions(step, "press", i),
            "release": _normalize_actions(step, "release", i),
        }
        if "note" in step:
            note = step["note"]
            if not isinstance(note, str):
                raise AutopilotError(f"step {i}: 'note' must be a string")
            norm_step["note"] = note

        norm_steps.append(norm_step)

    return {
        "format": FORMAT,
        "game": game,
        "seed": seed,
        "steps": norm_steps,
    }


def load_sequence(path):
    """Load, validate, and normalize an autopilot sequence JSON file."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise AutopilotError(f"failed to read sequence file '{path}': {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AutopilotError(f"invalid JSON in '{path}': {exc}") from exc

    return _normalize_sequence(data)


def save_sequence(path, sequence):
    """Validate and save an autopilot sequence as JSON."""
    normalized = _normalize_sequence(sequence)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(normalized, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sequence_from_events(events, game="", seed=None):
    """Convert a selfplay event log dict/list into an autopilot sequence."""
    if isinstance(events, dict):
        if "events" not in events:
            raise AutopilotError("events dict must contain 'events' key")
        raw_events = events["events"]
    elif isinstance(events, list):
        raw_events = events
    else:
        raise AutopilotError("events must be a dict or list")

    if not isinstance(raw_events, list) or len(raw_events) == 0:
        raise AutopilotError("events list must be non-empty")

    parsed = []
    for i, ev in enumerate(raw_events):
        if not isinstance(ev, dict):
            raise AutopilotError(f"event {i}: must be a dict")
        frame = ev.get("frame")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise AutopilotError(f"event {i}: 'frame' must be a non-negative integer")
        action = ev.get("action")
        if not isinstance(action, str):
            raise AutopilotError(f"event {i}: 'action' must be a string")
        pressed = ev.get("pressed")
        if not isinstance(pressed, bool):
            raise AutopilotError(f"event {i}: 'pressed' must be a bool")
        parsed.append((frame, i, action, pressed))

    parsed.sort(key=lambda item: (item[0], item[1]))

    groups = []
    for frame, _, action, pressed in parsed:
        if not groups or groups[-1][0] != frame:
            groups.append((frame, [], []))
        if pressed:
            groups[-1][1].append(action)
        else:
            groups[-1][2].append(action)

    steps = []
    first_frame = groups[0][0]
    if first_frame > 0:
        steps.append({"frames": first_frame, "press": [], "release": []})

    for i, (frame, press, release) in enumerate(groups):
        if i + 1 < len(groups):
            duration = groups[i + 1][0] - frame
        else:
            duration = 1
        steps.append({"frames": duration, "press": press, "release": release})

    return _normalize_sequence({
        "format": FORMAT,
        "game": game,
        "seed": seed,
        "steps": steps,
    })


def sequence_from_play_log(path):
    """Convert a play_log JSONL file into an autopilot sequence."""
    p = Path(path)
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AutopilotError(f"failed to read play log '{path}': {exc}") from exc

    game = ""
    seed = None
    steps = []

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise AutopilotError(f"invalid JSON at line {lineno} of '{path}': {exc}") from exc

        if not isinstance(obj, dict):
            raise AutopilotError(f"line {lineno} of '{path}' must be a JSON object")

        kind = obj.get("kind")
        if kind == "session":
            if isinstance(obj.get("game"), str):
                game = obj["game"]
            elif isinstance(obj.get("game_label"), str):
                game = obj["game_label"]
            if "seed" in obj:
                seed = obj["seed"]
        elif kind == "op":
            step = {
                "frames": obj.get("frames"),
                "press": obj.get("press", []),
                "release": obj.get("release", []),
            }
            if "note" in obj:
                step["note"] = obj["note"]
            steps.append(step)

    if not steps:
        raise AutopilotError(f"no playable 'op' entries found in '{path}'")

    return _normalize_sequence({
        "format": FORMAT,
        "game": game,
        "seed": seed,
        "steps": steps,
    })


def run_sequence(game, sequence, state_paths=()):
    """Execute an autopilot sequence against a Game or Recorder instance."""
    seq = _normalize_sequence(sequence)
    steps = seq["steps"]
    steps_total = len(steps)
    state_arg = list(state_paths) if state_paths else None

    steps_executed = 0
    last_frame = 0
    checkpoints = []
    ended = False
    final_state = {}

    for step in steps:
        try:
            obs = game.step(
                frames=step["frames"],
                press=step["press"],
                release=step["release"],
                state=state_arg,
            )
        except RuntimeError:
            ended = True
            break

        steps_executed += 1

        if isinstance(obs, dict):
            if "frame" in obs:
                last_frame = obs["frame"]
            for ev in obs.get("events") or ():
                if isinstance(ev, dict) and ev.get("type") == "checkpoint" and "id" in ev:
                    checkpoints.append(ev["id"])
            if state_arg and isinstance(obs.get("state"), dict):
                final_state = obs["state"]
            if obs.get("ended"):
                ended = True
                break

    return {
        "format": FORMAT,
        "steps_executed": steps_executed,
        "steps_total": steps_total,
        "frames": last_frame,
        "checkpoints": checkpoints,
        "ended": ended,
        "completed": steps_executed == steps_total,
        "final_state": final_state,
    }


def play(project, sequence, seed=None, state_paths=(), log_path=None):
    """Open a Game, run an autopilot sequence, optionally record play_log, and close."""
    seq = _normalize_sequence(sequence)
    effective_seed = seed if seed is not None else seq.get("seed")

    aiplayer = _import_aiplayer()
    game = aiplayer.Game(project, seed=effective_seed)
    try:
        if log_path is not None:
            play_log = _import_play_log()
            with play_log.record_game(
                game,
                log_path,
                game_label=seq.get("game", ""),
                state_paths=tuple(state_paths),
            ) as rec:
                result = run_sequence(rec, seq, state_paths=state_paths)
        else:
            result = run_sequence(game, seq, state_paths=state_paths)
    finally:
        game.close()

    result["game"] = seq.get("game", "")
    if log_path is not None:
        play_log = _import_play_log()
        result["play_log"] = play_log.summarize(log_path)
    return result


def run_cli(project, sequence_path, argv):
    """Parse CLI options (--seed, --state, --log) and run autopilot play."""
    seed = None
    state_paths = ()
    log_path = None

    args = list(argv)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--seed":
            if i + 1 >= len(args):
                raise ValueError("--seed requires an integer argument")
            seed = _parse_int(args[i + 1], "--seed")
            i += 2
        elif arg.startswith("--seed="):
            seed = _parse_int(arg.split("=", 1)[1], "--seed")
            i += 1
        elif arg == "--state":
            if i + 1 >= len(args):
                raise ValueError("--state requires a comma-separated path list")
            state_paths = _parse_state(args[i + 1])
            i += 2
        elif arg.startswith("--state="):
            state_paths = _parse_state(arg.split("=", 1)[1])
            i += 1
        elif arg == "--log":
            if i + 1 >= len(args):
                raise ValueError("--log requires a file path")
            log_path = args[i + 1]
            i += 2
        elif arg.startswith("--log="):
            log_path = arg.split("=", 1)[1]
            i += 1
        else:
            raise ValueError(f"unknown argument: {arg}")

    sequence = load_sequence(sequence_path)
    return play(project, sequence, seed=seed, state_paths=state_paths, log_path=log_path)


def _parse_int(value, flag):
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{flag} requires an integer, got {value!r}") from exc


def _parse_state(value):
    return tuple(item for item in value.split(",") if item)
