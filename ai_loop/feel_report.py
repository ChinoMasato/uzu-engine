#!/usr/bin/env python3
"""Feel proxy metrics for a self-verifying play (BACKLOG B-1112).

Game feel is a sensory judgement, and AI agents are bad at it -- but the
*effects* that make up feel are measurable. This tool hooks the feel probe
(ai_loop/selfplay/feel_probe.gd) into a lockstep playthrough and reports,
per game event, the measured proxies:

  * input -> reaction latency, in physics frames (the interact press the
    driver sent vs the first frame a juice channel deviates),
  * hitstop / slow motion: the applied Engine.time_scale segments, with
    their length in process frames, physics frames and wall milliseconds,
  * screen shake: the trauma curve -- peak, frames to half, settle time,
    the decay samples themselves,
  * camera kick: the spring displacement -- peak, settle, zero crossings,
  * flashes and other watched node properties (segments against the
    value first seen), e.g. the pickup flash on the player's modulate,
  * UI easing: UZUUIJuice's event log stamped with frames, plus the
    sample points of each easing curve that actually ran.

It does NOT judge whether anything "feels good". It returns numbers so an
agent can compare runs (before/after, preset A/B, juice on/off) -- the
comparison is the judgement's raw material, nothing more.

Usage (through uzu.py):
  uzu.py feel-report <project> [--seed 7] [--out feel_report.json]
                     [--no-juice] [--compare other_report.json]
                     [--watch Node:path:prop,...]
      The hikari playthrough (the route of verify_playthrough.py) with
      the probe installed. --no-juice passes "--uzu-no-juice" to the
      game (the hikari sample honours it; other games ignore it), so the
      same play can be measured with every juice call disabled.
  uzu.py feel-report <project> --probe-selftest [--frames 1500]
      No gameplay: the probe fires hitstop / shake / slowmo / kick on a
      schedule inside the project, proving every channel end to end.

Playthrough drivers (B-1113): the playthrough mode reads the project's
verify_playthrough.py. Two shapes are supported. The legacy shape (the
hikari sample) exports STATE / ROUTE / walk_to / interact / event_names
and is driven step for step as before. Any other game instead exports a
declarative FEEL_DRIVER:

    FEEL_DRIVER = {
        "state": ["Main:delivered", "Main:cleared",
                  "Main/Player:global_position"],   # required
        "watch": ["Main/Player:modulate"],         # optional, default []
        "position": "Main/Player:global_position", # optional: the state
                        # key _goto reads (default: the key ending in
                        # ":global_position")
        "actions": {"left": "move_left", "right": "move_right",
                    "up": "move_up", "down": "move_down"},  # optional
        "goto_tolerance": 0.45,                    # optional, metres
        "legs": [                                  # required, non-empty
            {"name": "mailbox_1", "goto": [-3.6, -11.35],
             "action": "interact", "expect": {"Main:delivered": 1}},
        ],
        "success": {"Main:cleared": True},         # required
    }

Each leg walks to its goto point (a grid-free steering walk on the
position state), presses its action, and retries until every expect
entry matches the observed state (at most 4 tries). The report then
carries "success" (the success expectations against the final state)
and "final_state"; the legacy-only "cleared" / "final_shards" keys are
absent for driver games.

Honest limits: UZUJuice's deadlines run on the wall clock while the
lockstep driver blocks on stdin between commands, so an effect's curve
is only sampled on process frames -- long driver pauses compress the
visible curve (durations are therefore reported in process frames AND
wall msec). The probe self-test runs in real time for the same reason:
unthrottled (--fixed-fps), wall time advances so slowly per frame that
a 60 ms hitstop outlives a 1500-frame run. Flash/squash on nodes other
than the watched ones, particle bursts and sound are not measured.
Standard library only.
"""

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FORMAT = "uzu-feel-report/1"
# The hikari driver's watched values: the pickup flash lives on the
# player's modulate, the count-up easing on the shard gauge's value.
# The gauge is found by name (find:): the containers above it are
# anonymous code-built nodes whose generated names are not stable.
HIKARI_WATCH = [
    "Main/Player:modulate",
    "find:ShardGauge:value",
]
FLASH_WATCH = "Main/Player:modulate"
GAUGE_WATCH = "find:ShardGauge:value"
ATTRIB_WINDOW = 240  # Physics frames after a press in which an onset belongs to that event.
SAMPLE_CAP = 240

DEFAULT_DRIVER_ACTIONS = {"left": "move_left", "right": "move_right",
                          "up": "move_up", "down": "move_down"}


def expect_met(state, expect):
    """True when every expected entry matches the observed state dict.
    Booleans only match booleans (True does not equal 1 here)."""
    state = state or {}
    for key, want in (expect or {}).items():
        got = state.get(key)
        if isinstance(want, bool) or isinstance(got, bool):
            if got is not want:
                return False
        elif got != want:
            return False
    return True


def validate_driver(spec):
    """Validate a FEEL_DRIVER dict; returns a list of error strings."""
    errors = []
    if not isinstance(spec, dict):
        return ["FEEL_DRIVER must be a dict"]
    state = spec.get("state")
    if not isinstance(state, list) or not state or not all(isinstance(p, str) for p in state):
        errors.append("FEEL_DRIVER['state'] must be a non-empty list of state paths")
    legs = spec.get("legs")
    if not isinstance(legs, list) or not legs:
        errors.append("FEEL_DRIVER['legs'] must be a non-empty list")
    else:
        for i, leg in enumerate(legs):
            if not isinstance(leg, dict):
                errors.append(f"FEEL_DRIVER['legs'][{i}] must be a dict")
                continue
            goto = leg.get("goto")
            if goto is not None and not (isinstance(goto, (list, tuple)) and len(goto) in (2, 3)
                                         and all(isinstance(v, (int, float)) for v in goto)):
                errors.append(f"FEEL_DRIVER['legs'][{i}]['goto'] must be [x, z] or [x, y, z]")
            if not isinstance(leg.get("expect"), dict) or not leg.get("expect"):
                errors.append(f"FEEL_DRIVER['legs'][{i}]['expect'] must be a non-empty dict")
    if not isinstance(spec.get("success"), dict) or not spec.get("success"):
        errors.append("FEEL_DRIVER['success'] must be a non-empty dict")
    watch = spec.get("watch")
    if watch is not None and not (isinstance(watch, list) and all(isinstance(w, str) for w in watch)):
        errors.append("FEEL_DRIVER['watch'] must be a list of watch strings")
    actions = spec.get("actions")
    if actions is not None and not isinstance(actions, dict):
        errors.append("FEEL_DRIVER['actions'] must be a dict of direction -> input action")
    tol = spec.get("goto_tolerance")
    if tol is not None and not (isinstance(tol, (int, float)) and tol > 0):
        errors.append("FEEL_DRIVER['goto_tolerance'] must be a positive number")
    return errors


def driver_kind(module):
    """Which playthrough shape a verify_playthrough module exports:
    "driver" (FEEL_DRIVER), "legacy" (STATE/ROUTE/...), or None."""
    if getattr(module, "FEEL_DRIVER", None) is not None:
        return "driver"
    if all(hasattr(module, name) for name in ("STATE", "ROUTE", "walk_to", "interact", "event_names")):
        return "legacy"
    return None


def _position_of(state, key):
    """(x, z) from a state value that is a list [x, y, z] or a dict."""
    value = (state or {}).get(key)
    if isinstance(value, dict):
        return float(value["x"]), float(value["z"])
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return float(value[0]), float(value[2])
    return None


def _goto(game, tx, tz, state_paths, actions, tol=0.45, position_key=None, budget=900):
    """Steering walk toward (tx, tz) on the position state, the way the
    moonpost verifier walks (B-1005): observe, press the direction
    actions toward the target, release, until within tol or out of
    budget. Returns True when the target was reached."""
    import math
    frames = 0
    while frames < budget:
        obs = game.observe(state=state_paths)
        state = obs.get("state", {})
        key = position_key
        if key is None:
            key = next((k for k in state if k.endswith(":global_position")), None)
        pos = _position_of(state, key) if key else None
        if pos is None:
            return False
        x, z = pos
        dx, dz = tx - x, tz - z
        if math.hypot(dx, dz) < tol:
            return True
        press = []
        if dx > 0.15:
            press.append(actions["right"])
        elif dx < -0.15:
            press.append(actions["left"])
        if dz < -0.15:
            press.append(actions["up"])
        elif dz > 0.15:
            press.append(actions["down"])
        if not press:
            press.append(actions["up"])
        game.step(frames=6, press=press, state=state_paths)
        game.step(frames=1, release=press)
        frames += 7
    return False


# ------------------------------------------------------------------ probe data

def load_records(path):
    """The probe's JSON Lines, as a list of dictionaries."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _r4(v):
    return round(float(v), 4)


def _holds(samples, end_pf):
    """Each change-only sample holds until the next sample's pf."""
    for i, s in enumerate(samples):
        nxt = samples[i + 1]["pf"] if i + 1 < len(samples) else end_pf
        yield s, max(nxt, s["pf"])


def time_scale_segments(samples, end_pf, end_msec=0):
    """Runs where the applied Engine.time_scale differs from the base
    (the first sample's scale). A segment is a hitstop when its minimum
    scale is 0, slow motion when below the base, a speedup above it."""
    if not samples:
        return []
    base = samples[0]["ts"]
    segments = []
    cur = None
    for s, nxt in _holds(samples, end_pf):
        if s["ts"] != base:
            if cur is None:
                cur = {"onset_pf": s["pf"], "onset_frame": s["frame"], "onset_msec": s["msec"],
                       "min_scale": s["ts"], "max_scale": s["ts"]}
            cur["min_scale"] = min(cur["min_scale"], s["ts"])
            cur["max_scale"] = max(cur["max_scale"], s["ts"])
            cur["end_pf"] = nxt
            cur["end_msec"] = end_msec
        elif cur is not None:
            cur["end_msec"] = s["msec"]  # The sample that returned to base closes it.
            segments.append(_finish_time_segment(cur, base))
            cur = None
    if cur is not None:
        cur["open"] = True  # Still in effect when the run ended.
        segments.append(_finish_time_segment(cur, base))
    return segments


def _finish_time_segment(cur, base):
    if cur["min_scale"] == 0.0:
        kind = "hitstop"
    elif cur["min_scale"] < base:
        kind = "slowmo"
    else:
        kind = "speedup"
    out = {
        "kind": kind,
        "onset_pf": cur["onset_pf"], "onset_frame": cur["onset_frame"],
        "frames": cur["end_pf"] - cur["onset_pf"],
        "msec": cur["end_msec"] - cur["onset_msec"],
        "min_scale": _r4(cur["min_scale"]), "max_scale": _r4(cur["max_scale"]),
        "base_scale": _r4(base),
    }
    if cur.get("open"):
        out["open"] = True
    return out


def scalar_segments(samples, end_pf, key, eps=1e-3, end_msec=0):
    """Runs where |samples[key]| rises above eps: trauma (shake) and the
    kick spring. Reports the peak, the decay to half the peak, the settle
    length and the curve samples themselves. The default eps is the
    engine's own settle threshold (UZUJuiceSpringState::settled), so a
    segment ends where the engine itself considers the effect over."""
    segments = []
    cur = None
    for s, nxt in _holds(samples, end_pf):
        v = float(s[key])
        if abs(v) > eps:
            if cur is None:
                cur = {"onset_pf": s["pf"], "onset_frame": s["frame"], "onset_msec": s["msec"],
                       "peak": v, "peak_pf": s["pf"], "end_pf": nxt, "end_msec": end_msec,
                       "half_pf": None, "crossings": 0, "samples": []}
            if abs(v) > abs(cur["peak"]):
                cur["peak"] = v
                cur["peak_pf"] = s["pf"]
            if cur["samples"] and cur["samples"][-1][1] * v < 0:
                cur["crossings"] += 1
            cur["samples"].append([s["pf"], _r4(v)])
            cur["end_pf"] = nxt
        elif cur is not None:
            cur["end_msec"] = s["msec"]  # The first settled sample closes it.
            segments.append(_finish_scalar(cur))
            cur = None
    if cur is not None:
        cur["open"] = True  # Still unsettled when the run ended.
        segments.append(_finish_scalar(cur))
    return segments


def _finish_scalar(cur):
    half = abs(cur["peak"]) / 2.0
    for pf, v in cur["samples"]:
        if pf > cur["peak_pf"] and abs(v) <= half:
            cur["half_pf"] = pf
            break
    samples = cur["samples"]
    if len(samples) > SAMPLE_CAP:
        stride = -(-len(samples) // SAMPLE_CAP)
        samples = samples[::stride]
    out = {
        "onset_pf": cur["onset_pf"], "onset_frame": cur["onset_frame"],
        "frames": cur["end_pf"] - cur["onset_pf"],
        "msec": cur["end_msec"] - cur["onset_msec"],
        "peak": _r4(cur["peak"]),
        "frames_to_half": (cur["half_pf"] - cur["onset_pf"]) if cur["half_pf"] is not None else None,
        "zero_crossings": cur["crossings"],
        "samples": samples,
    }
    if cur.get("open"):
        out["open"] = True
    return out


def _deviation(base, value):
    """Max absolute component difference for numbers / number lists."""
    if isinstance(base, (int, float)) and isinstance(value, (int, float)):
        return abs(float(value) - float(base))
    if isinstance(base, list) and isinstance(value, list) and len(base) == len(value):
        try:
            return max(abs(float(v) - float(b)) for b, v in zip(base, value))
        except (TypeError, ValueError):
            return None
    return None


def watch_segments(samples, end_pf, key, end_msec=0):
    """Runs where a watched NodePath:property differs from the first
    value seen (its base). Errors (unresolved path) are not segments."""
    base = None
    segments = []
    cur = None
    for s, nxt in _holds(samples, end_pf):
        value = s.get("watch", {}).get(key)
        if isinstance(value, dict):  # A resolution error, not a value.
            continue
        if base is None:
            base = value
        if value != base:
            if cur is None:
                cur = {"onset_pf": s["pf"], "onset_frame": s["frame"], "onset_msec": s["msec"],
                       "end_pf": nxt, "end_msec": end_msec, "peak_deviation": _deviation(base, value)}
            dev = _deviation(base, value)
            if dev is not None and (cur["peak_deviation"] is None or dev > cur["peak_deviation"]):
                cur["peak_deviation"] = dev
            cur["end_pf"] = nxt
        elif cur is not None:
            cur["end_msec"] = s["msec"]  # The sample back at base closes it.
            segments.append(_finish_watch(cur, key))
            cur = None
    if cur is not None:
        cur["open"] = True  # Still away from base when the run ended.
        segments.append(_finish_watch(cur, key))
    return segments


def _finish_watch(cur, key):
    out = {
        "watch": key,
        "onset_pf": cur["onset_pf"], "onset_frame": cur["onset_frame"],
        "frames": cur["end_pf"] - cur["onset_pf"],
        "msec": cur["end_msec"] - cur["onset_msec"],
        "peak_deviation": _r4(cur["peak_deviation"]) if cur["peak_deviation"] is not None else None,
    }
    if cur.get("open"):
        out["open"] = True
    return out


def analyze(records):
    """Probe records -> the channel analysis (no game knowledge)."""
    samples = [r for r in records if r.get("type") == "sample"]
    end = next((r for r in reversed(records) if r.get("type") == "end"), None)
    end_pf = end["pf"] if end else (samples[-1]["pf"] + 1 if samples else 0)
    end_msec = end["msec"] if end else (samples[-1]["msec"] if samples else 0)
    watch_keys = []
    for s in samples:
        for k in s.get("watch", {}):
            if k not in watch_keys:
                watch_keys.append(k)
    return {
        "samples": len(samples),
        "span_pf": end_pf,
        "channels": {
            "time_scale": time_scale_segments(samples, end_pf, end_msec),
            "shake": scalar_segments(samples, end_pf, "trauma", end_msec=end_msec),
            "kick": scalar_segments(samples, end_pf, "kick", end_msec=end_msec),
            "watch": {k: watch_segments(samples, end_pf, k, end_msec) for k in watch_keys},
        },
        "ui_events": [
            {k: r.get(k) for k in ("pf", "frame", "msec", "event", "phase", "preset", "target")}
            for r in records if r.get("type") == "ui_event"
        ],
        "curves": {r["preset"]: r["samples"] for r in records if r.get("type") == "curve"},
        "selftest": [
            {k: r.get(k) for k in ("action", "pf", "frame", "msec")}
            for r in records if r.get("type") == "selftest"
        ],
    }


# ------------------------------------------------------------------ attribution

def _channel_segments(analysis, channel):
    if channel == "watch":
        out = []
        for segs in analysis["channels"]["watch"].values():
            out += segs
        return out
    return analysis["channels"][channel]


def attribute(analysis, events):
    """Assigns each measured segment to the game event whose input
    caused it: the latest event pressed at or before the segment's
    onset, within ATTRIB_WINDOW physics frames. events are
    {"id", "frame", "press_frame"} in play order; segments outside
    every window stay unattributed. The latency of an event is its
    earliest attributed onset minus its press frame."""
    ordered = sorted(events, key=lambda e: e["frame"])
    per_event = {e["id"]: {"id": e["id"], "frame": e["frame"], "press_frame": e["press_frame"],
                           "latency_frames": None, "channels": {}, "ui_events": []}
                 for e in ordered}
    unattributed = {}

    def owner(onset_frame):
        best = None
        for e in ordered:
            if e["press_frame"] <= onset_frame <= e["press_frame"] + ATTRIB_WINDOW:
                if best is None or e["press_frame"] > best["press_frame"]:
                    best = e
        return best

    for channel in ("time_scale", "shake", "kick", "watch"):
        for seg in _channel_segments(analysis, channel):
            e = owner(seg["onset_frame"])
            bucket = per_event[e["id"]]["channels"] if e else unattributed
            name = "watch:" + seg["watch"] if channel == "watch" else channel
            bucket.setdefault(name, []).append(seg)
            if e:
                lat = seg["onset_frame"] - e["press_frame"]
                cur = per_event[e["id"]]["latency_frames"]
                per_event[e["id"]]["latency_frames"] = lat if cur is None else min(cur, lat)
    for ui in analysis["ui_events"]:
        e = owner(ui["frame"])
        if e:
            per_event[e["id"]]["ui_events"].append(ui)
    return {"events": [per_event[e["id"]] for e in ordered], "unattributed": unattributed}


def headline(event_entry):
    """The comparable numbers of one event: per channel, how many
    segments, how many process frames in total, the largest peak."""
    out = {}
    for name, segs in event_entry["channels"].items():
        peak = None
        for s in segs:
            v = s.get("peak", s.get("peak_deviation"))
            if v is not None:
                peak = abs(v) if peak is None else max(peak, abs(v))
        out[name] = {"segments": len(segs), "frames": sum(s["frames"] for s in segs), "peak": peak}
    return out


def compare_reports(base, other):
    """Side-by-side headline metrics of two feel reports (e.g. juice on
    vs off): for every event and channel, [base, other] -- in the CLI,
    base is the report just produced and other is the --compare file."""
    def by_id(rep):
        return {e["id"]: headline(e) for e in rep.get("events", [])}
    a, b = by_id(base), by_id(other)
    diff = {}
    for eid in sorted(set(a) | set(b)):
        channels = {}
        for name in sorted(set(a.get(eid, {})) | set(b.get(eid, {}))):
            ha, hb = a.get(eid, {}).get(name), b.get(eid, {}).get(name)
            channels[name] = {
                "segments": [ha["segments"] if ha else 0, hb["segments"] if hb else 0],
                "frames": [ha["frames"] if ha else 0, hb["frames"] if hb else 0],
                "peak": [ha["peak"] if ha else None, hb["peak"] if hb else None],
            }
        diff[eid] = {
            "latency_frames": [
                next((e["latency_frames"] for e in base.get("events", []) if e["id"] == eid), None),
                next((e["latency_frames"] for e in other.get("events", []) if e["id"] == eid), None),
            ],
            "channels": channels,
        }
    return diff


# ------------------------------------------------------------------ drivers

def _load_verify_playthrough(project):
    path = os.path.join(project, "verify_playthrough.py")
    spec = importlib.util.spec_from_file_location("hikari_verify_playthrough", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _settle(game, state_paths, seconds):
    """A real-time settle after an interaction: step one frame at a time
    with small sleeps, so wall-clock effects (the flash deadline, the
    kick spring) live out their real durations and are sampled as
    curves -- instead of being compressed into one dt jump, merged into
    the next event's segment, or cut off by the end of the run."""
    for _ in range(max(1, int(seconds / 0.012))):
        game.step(frames=1, state=state_paths)
        time.sleep(0.012)



def _run_driver_playthrough(project, vp, seed=7, juice=True, watch=None):
    """The FEEL_DRIVER route (B-1113): walk each leg, press its action,
    retry until the leg's expectations hold; same probe recording and
    event attribution as the legacy route."""
    from aiplayer import Game

    driver = vp.FEEL_DRIVER
    errors = validate_driver(driver)
    if errors:
        raise ValueError("invalid FEEL_DRIVER: " + "; ".join(errors))
    state_paths = list(driver["state"])
    if watch is None:
        watch = list(driver.get("watch") or [])
    actions = dict(DEFAULT_DRIVER_ACTIONS)
    actions.update(driver.get("actions") or {})
    tol = float(driver.get("goto_tolerance") or 0.45)
    work = tempfile.mkdtemp(prefix="uzu_feel_")
    feel_path = os.path.join(work, "feel.jsonl")
    extra_args = ["--uzu-feel", feel_path]
    if watch:
        extra_args += ["--uzu-feel-watch", ",".join(watch)]
    if not juice:
        extra_args.append("--uzu-no-juice")
    presses = []
    checkpoints = []

    with Game(project, seed=seed,
              extra_autoloads={"UZUFeelProbe": "selfplay/feel_probe.gd"},
              extra_user_args=extra_args) as game:
        orig_step = game.step

        def recording_step(frames=1, press=(), release=(), state=None, image=None):
            before = game.last.get("frame")
            obs = orig_step(frames=frames, press=press, release=release, state=state, image=image)
            presses.append({"frame_before": before, "press": list(press),
                            "frames": frames, "frame_after": obs.get("frame")})
            for e in obs.get("events", []):
                if isinstance(e, dict) and e.get("type") == "checkpoint":
                    checkpoints.append({"id": e.get("id"), "frame": obs.get("frame"),
                                        "telemetry_frame": e.get("frame")})
            return obs

        game.step = recording_step
        game.observe(state=state_paths)
        leg_results = []
        final = {}
        for leg in driver["legs"]:
            reached = None
            if leg.get("goto"):
                goto = leg["goto"]
                reached = _goto(game, float(goto[0]), float(goto[-1]), state_paths,
                                actions, tol=tol, position_key=driver.get("position"))
            action = leg.get("action")
            tries = 0
            met = False
            obs = game.observe(state=state_paths)
            final = obs.get("state", {})
            while tries < 4 and not met:
                if action:
                    game.step(frames=3, press=[action], state=state_paths)
                    game.step(frames=2, release=[action], state=state_paths)
                tries += 1
                obs = game.observe(state=state_paths)
                final = obs.get("state", {})
                met = expect_met(final, leg["expect"])
            leg_results.append({"name": leg.get("name", ""), "reached": reached,
                                "expect_met": met, "tries": tries})
            _settle(game, state_paths, 0.35)
        _settle(game, state_paths, 1.6)
        obs = game.observe(state=state_paths)
        final = obs.get("state", {}) or final

    events = []
    for cp in checkpoints:
        press_frame = None
        for p in presses:
            if p["press"] and p["frame_before"] is not None and cp["frame"] is not None \
                    and p["frame_before"] <= cp["frame"]:
                press_frame = p["frame_before"]
        events.append({"id": cp["id"], "frame": cp["frame"], "press_frame": press_frame})

    analysis = analyze(load_records(feel_path))
    attributed = attribute(analysis, [e for e in events if e["press_frame"] is not None])
    return {
        "format": FORMAT,
        "mode": "playthrough",
        "game": os.path.basename(os.path.abspath(project)),
        "conditions": {"seed": seed, "juice": juice, "watch": watch},
        "driver": {"legs": leg_results},
        "success": expect_met(final, driver["success"]),
        "final_state": final,
        "checkpoints": [c["id"] for c in checkpoints],
        "events": attributed["events"],
        "unattributed": attributed["unattributed"],
        "ui_events": analysis["ui_events"],
        "ui_curves": analysis["curves"],
        "probe_samples": analysis["samples"],
    }


def run_playthrough(project, seed=7, juice=True, watch=None):
    """Dispatch on the project's verify_playthrough.py shape (B-1113):
    FEEL_DRIVER modules take the generic route, legacy hikari-shaped
    modules the original step-for-step route."""
    vp = _load_verify_playthrough(project)
    kind = driver_kind(vp)
    if kind == "driver":
        return _run_driver_playthrough(project, vp, seed=seed, juice=juice, watch=watch)
    if kind == "legacy":
        return _run_legacy_playthrough(project, seed=seed, juice=juice, watch=watch)
    raise ValueError("verify_playthrough.py defines neither FEEL_DRIVER nor the "
                     "legacy STATE/ROUTE shape")


def _run_legacy_playthrough(project, seed=7, juice=True, watch=None):
    """The hikari route of verify_playthrough.py, with the feel probe
    installed and every step recorded. Returns the feel report."""
    from aiplayer import Game

    vp = _load_verify_playthrough(project)
    watch = watch or HIKARI_WATCH
    work = tempfile.mkdtemp(prefix="uzu_feel_")
    feel_path = os.path.join(work, "feel.jsonl")
    extra_args = ["--uzu-feel", feel_path, "--uzu-feel-watch", ",".join(watch)]
    if not juice:
        extra_args.append("--uzu-no-juice")
    presses = []      # {"frame_before", "press", "frames", "frame_after"}
    checkpoints = []  # {"id", "frame" (observation), "telemetry_frame"}
    seen = []

    with Game(project, seed=seed,
              extra_autoloads={"UZUFeelProbe": "selfplay/feel_probe.gd"},
              extra_user_args=extra_args) as game:
        orig_step = game.step

        def recording_step(frames=1, press=(), release=(), state=None, image=None):
            before = game.last.get("frame")
            obs = orig_step(frames=frames, press=press, release=release, state=state, image=image)
            presses.append({"frame_before": before, "press": list(press),
                            "frames": frames, "frame_after": obs.get("frame")})
            for e in obs.get("events", []):
                if isinstance(e, dict) and e.get("type") == "checkpoint":
                    checkpoints.append({"id": e.get("id"), "frame": obs.get("frame"),
                                        "telemetry_frame": e.get("frame")})
            return obs

        game.step = recording_step
        # The playthrough of verify_playthrough.py, step for step.
        o0 = game.observe(state=vp.STATE)
        seen += vp.event_names(o0.get("events", []))
        obs = game.step(frames=30, press=["interact"], state=vp.STATE)
        seen += vp.event_names(obs.get("events", []))
        game.step(frames=5, release=["interact"], state=vp.STATE)
        final = {}
        for name, waypoints, want_shards in vp.ROUTE:
            obs = None
            for wp in waypoints:
                obs = vp.walk_to(game, wp, sink=seen)
            for _try in range(4):
                obs = vp.interact(game, sink=seen)
                if name == "lantern":
                    if obs.get("state", {}).get("Main:cleared"):
                        break
                elif obs.get("state", {}).get("Main:shards") == want_shards:
                    break
            final = obs.get("state", {})
            _settle(game, vp.STATE, 0.35)  # Let this event's effects finish before the next leg.
        _settle(game, vp.STATE, 1.6)  # The lantern's kick spring needs the longest tail.

    # The press that caused each checkpoint: the newest interact press
    # issued at or before the observation the checkpoint arrived in.
    events = []
    for cp in checkpoints:
        press_frame = None
        for p in presses:
            if "interact" in p["press"] and p["frame_before"] is not None and cp["frame"] is not None \
                    and p["frame_before"] <= cp["frame"]:
                press_frame = p["frame_before"]
        events.append({"id": cp["id"], "frame": cp["frame"], "press_frame": press_frame})

    analysis = analyze(load_records(feel_path))
    attributed = attribute(analysis, [e for e in events if e["press_frame"] is not None])
    report = {
        "format": FORMAT,
        "mode": "playthrough",
        "game": os.path.basename(os.path.abspath(project)),
        "conditions": {"seed": seed, "juice": juice, "watch": watch},
        "cleared": final.get("Main:cleared") is True,
        "final_shards": final.get("Main:shards"),
        "checkpoints": [c["id"] for c in checkpoints],
        "events": attributed["events"],
        "unattributed": attributed["unattributed"],
        "ui_events": analysis["ui_events"],
        "ui_curves": analysis["curves"],
        "probe_samples": analysis["samples"],
    }
    return report


def run_probe_selftest(project, frames=1500):
    """Runs the project with no input while the probe fires one effect
    per channel on a schedule; checks each channel produced a segment."""
    import uzu

    work = tempfile.mkdtemp(prefix="uzu_feel_selftest_")
    game = os.path.join(work, "game")
    import shutil
    shutil.copytree(project, game, ignore=shutil.ignore_patterns(".godot"))
    uzu.install_addons(game, ["selfplay/feel_probe.gd"],
                       'UZUFeelProbe="*res://addons/uzu_selfplay/feel_probe.gd"\n')
    if not os.path.exists(os.path.join(game, ".godot", "imported")):
        uzu.import_assets(game)
    feel_path = os.path.join(work, "feel.jsonl")
    # No --fixed-fps here: that runs unthrottled, wall time barely
    # advances per frame, and the juice deadlines (wall clock) would
    # outlive the run -- a 60 ms hitstop can span the whole play. The
    # self-test runs in real time so each effect lives and dies inside
    # its schedule window.
    cmd = [uzu.find_godot(), "--headless", "--path", game,
           "--quit-after", str(frames), "--", "--uzu-feel", feel_path, "--uzu-feel-selftest"]
    rc, out = uzu.run(cmd, timeout=900)
    if not os.path.exists(feel_path):
        return {"format": FORMAT, "mode": "probe-selftest", "ok": False,
                "error": "the probe wrote nothing", "log_tail": uzu.tail(out)}
    analysis = analyze(load_records(feel_path))
    ts = analysis["channels"]["time_scale"]
    checks = {
        "hitstop": any(s["kind"] == "hitstop" for s in ts),
        "slowmo": any(s["kind"] == "slowmo" and 0.05 < s["min_scale"] < 0.9 for s in ts),
        "shake": any(s["peak"] >= 0.5 for s in analysis["channels"]["shake"]),
        "kick": any(abs(s["peak"]) >= 0.7 for s in analysis["channels"]["kick"]),
    }
    return {
        "format": FORMAT, "mode": "probe-selftest", "ok": rc == 0 and all(checks.values()),
        "exit_code": rc, "checks": checks,
        "selftest_actions": analysis["selftest"],
        "channels": analysis["channels"],
        "probe_samples": analysis["samples"],
    }


# ------------------------------------------------------------------ CLI

def main(argv):
    parser = argparse.ArgumentParser(description="Feel proxy metrics (B-1112)")
    parser.add_argument("project", help="the game project (hikari for the playthrough mode)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-juice", action="store_true",
                        help="measure with the game's juice calls disabled (--uzu-no-juice)")
    parser.add_argument("--watch", help="comma-separated NodePath:property list to sample")
    parser.add_argument("--out", help="write the full report here (default: <project>/feel_report.json)")
    parser.add_argument("--compare", help="another feel report JSON; adds the headline comparison")
    parser.add_argument("--probe-selftest", action="store_true",
                        help="fire one effect per channel from the probe instead of playing")
    parser.add_argument("--frames", type=int, default=1500, help="frames for --probe-selftest")
    args = parser.parse_args(argv)
    project = os.path.abspath(args.project)
    try:
        if not os.path.exists(os.path.join(project, "project.godot")):
            raise ValueError(f"{args.project} is not a project (no project.godot)")
        if args.probe_selftest:
            report = run_probe_selftest(project, frames=args.frames)
            ok = bool(report.get("ok"))
            summary = {"ok": ok, "command": "feel-report", "mode": "probe-selftest",
                       "checks": report.get("checks"), "error": report.get("error")}
        else:
            watch = [w.strip() for w in args.watch.split(",")] if args.watch else None
            report = run_playthrough(project, seed=args.seed, juice=not args.no_juice, watch=watch)
            if "success" in report:
                ok = bool(report["success"])
                summary = {"ok": ok, "command": "feel-report", "mode": "playthrough",
                           "juice": not args.no_juice, "success": report["success"],
                           "final_state": report["final_state"],
                           "legs": report["driver"]["legs"],
                           "events": {e["id"]: {"latency_frames": e["latency_frames"],
                                                "channels": headline(e)} for e in report["events"]}}
            else:
                ok = report["cleared"] and report["final_shards"] == 3
                summary = {"ok": ok, "command": "feel-report", "mode": "playthrough",
                           "juice": not args.no_juice, "cleared": report["cleared"],
                           "events": {e["id"]: {"latency_frames": e["latency_frames"],
                                                "channels": headline(e)} for e in report["events"]}}
        out_path = args.out or os.path.join(project, "feel_report.json")
        if args.compare:
            with open(args.compare, encoding="utf-8") as f:
                other = json.load(f)
            # Every compared pair is [this report, the --compare report].
            report["comparison"] = compare_reports(report, other)
            report["comparison_with"] = args.compare
            summary["comparison"] = report["comparison"]
            summary["comparison_sides"] = ["this report", args.compare]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        summary["report"] = out_path
    except Exception as e:  # The one-JSON-line contract: failures are data too.
        print(json.dumps({"ok": False, "command": "feel-report", "error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
