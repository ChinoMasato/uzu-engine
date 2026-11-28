"""Lumina SFX bridge, credit manifest generator, and export guard.

Usage:
  uzu.py sfx-lumina <project> --request <file> [--lumina-dir <dir>] [--dest <res://...>]
  uzu.py sfx-lumina <project> --check-export <dir>
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from . import audio_check
except ImportError:
    import audio_check

REQUEST_FORMAT = "uzu-sfx-request/1"
MANIFEST_FORMAT = "uzu-sfx-credits/1"
MANIFEST_FILENAME = "uzu_sfx_credits.json"
DEFAULT_DEST = "res://audio/sfx"
DEFAULT_LUMINA_SUBPATH = Path("workspace") / "custom-skills" / "lumina-sfx"
DEFAULT_TIMEOUT_SEC = 120
SILENCE_PEAK_DB = -120.0
EVENT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
CATALOG_RECIPE_THRESHOLD = 50
LUMINA_SKILL_FILES = frozenset({
    "sources/recordings.json",
    "qa/release-masters.json",
    "scripts/search.mjs",
    "scripts/remix.mjs",
})


class LuminaBridgeError(Exception):
    """Raised on CLI argument or fatal request-loading failures."""


def _default_runner(argv, cwd, timeout=DEFAULT_TIMEOUT_SEC):
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", str(exc)


def resolve_lumina_dir(lumina_dir=None):
    if lumina_dir:
        return Path(lumina_dir).expanduser()
    env_dir = os.environ.get("UZU_LUMINA_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / DEFAULT_LUMINA_SUBPATH


def _error_result(errors, placed=None):
    return {
        "ok": False,
        "command": "sfx-lumina",
        "placed": list(placed or []),
        "errors": list(errors),
    }


def _parse_json_output(stdout):
    if not stdout or not stdout.strip():
        return None
    text = stdout.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except ValueError:
                continue
    return None


def _resolve_dest(project, dest_value):
    project_root = Path(project).resolve()
    raw = DEFAULT_DEST if dest_value is None else str(dest_value).strip()
    if not raw:
        raw = DEFAULT_DEST
    if raw.startswith("res://"):
        rel = raw[len("res://"):].strip("/")
    elif os.path.isabs(raw):
        raise ValueError(f"dest must be a res:// or project-relative path: {raw}")
    else:
        rel = raw.strip("/")
    dest_abs = (project_root / rel).resolve() if rel else project_root
    try:
        dest_abs.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"dest escapes project directory: {raw}") from exc
    res_prefix = f"res://{rel}" if rel else "res://"
    return dest_abs, res_prefix


def _res_file_path(res_prefix, filename):
    if res_prefix == "res://":
        return f"res://{filename}"
    return f"{res_prefix.rstrip('/')}/{filename}"


def _validate_request(req):
    if not isinstance(req, dict):
        return ["request must be a JSON object"]
    if req.get("format") != REQUEST_FORMAT:
        return [f"unsupported request format: {req.get('format')!r} (expected {REQUEST_FORMAT!r})"]
    sounds = req.get("sounds")
    if not isinstance(sounds, list) or len(sounds) == 0:
        return ["request 'sounds' must be a non-empty list"]
    errors = []
    seen = set()
    for idx, item in enumerate(sounds):
        if not isinstance(item, dict):
            errors.append(f"sounds[{idx}] must be an object")
            continue
        event = item.get("event")
        if not isinstance(event, str) or not event or not EVENT_NAME_RE.match(event):
            errors.append(f"sounds[{idx}] has invalid event name: {event!r}")
            continue
        if event in seen:
            errors.append(f"duplicate event name: {event!r}")
            continue
        seen.add(event)
    return errors


def _normalize_credits(*sources):
    normalized = []
    seen = set()

    def _collect(obj):
        if not obj:
            return
        if isinstance(obj, dict):
            items = [obj]
        elif isinstance(obj, list):
            items = obj
        else:
            return
        for entry in items:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or entry.get("name") or entry.get("recording") or "").strip()
            author = str(
                entry.get("author")
                or entry.get("creator")
                or entry.get("artist")
                or entry.get("recordist")
                or entry.get("by")
                or ""
            ).strip()
            license_val = str(entry.get("license") or entry.get("licence") or "").strip()
            url = str(entry.get("url") or entry.get("href") or entry.get("link") or entry.get("source_url") or "").strip()
            if not (title or author or license_val or url):
                continue
            key = (title, author, license_val, url)
            if key not in seen:
                seen.add(key)
                normalized.append({
                    "title": title,
                    "author": author,
                    "license": license_val,
                    "url": url,
                })

    for src in sources:
        _collect(src)
    return normalized


def _is_free_license(license_str):
    if not isinstance(license_str, str):
        return False
    norm = re.sub(r"\s+", "", license_str.upper())
    if not norm:
        return False
    if norm.startswith("CC0"):
        return True
    if "PUBLICDOMAIN" in norm:
        return True
    if norm == "PD":
        return True
    return False


def _collect_license_warnings(placed):
    warnings = []
    for entry in placed:
        event = entry.get("event")
        credits = entry.get("credits") or []
        if entry.get("credits_missing") or not credits:
            warnings.append({
                "event": event,
                "license": None,
                "reason": "credits missing; license cannot be verified as CC0/Public Domain",
            })
            continue
        for credit in credits:
            lic = credit.get("license", "")
            if not _is_free_license(lic):
                warnings.append({
                    "event": event,
                    "license": lic if lic else None,
                    "reason": (
                        f"license {lic!r} is not CC0 or Public Domain (attribution or restrictions may apply)"
                        if lic
                        else "credit license is empty; cannot verify CC0 or Public Domain"
                    ),
                })
    return warnings


def _update_manifest(dest_abs, placed):
    manifest_path = dest_abs / MANIFEST_FILENAME
    warnings = []
    manifest = {"format": MANIFEST_FORMAT, "sounds": {}}

    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            warnings.append({
                "event": None,
                "license": None,
                "reason": f"failed to read existing credit manifest {MANIFEST_FILENAME}: {exc}",
            })
            return warnings
        if (
            not isinstance(existing, dict)
            or existing.get("format") != MANIFEST_FORMAT
            or not isinstance(existing.get("sounds"), dict)
        ):
            warnings.append({
                "event": None,
                "license": None,
                "reason": f"existing credit manifest {MANIFEST_FILENAME} has invalid structure; not overwriting",
            })
            return warnings
        manifest = {
            "format": MANIFEST_FORMAT,
            "sounds": dict(existing["sounds"]),
        }

    for entry in placed:
        manifest["sounds"][entry["event"]] = {
            "file": entry["file"],
            "lumina_id": entry.get("lumina_id"),
            "credits": list(entry.get("credits") or []),
        }

    try:
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        warnings.append({
            "event": None,
            "license": None,
            "reason": f"failed to write credit manifest {MANIFEST_FILENAME}: {exc}",
        })
    return warnings


def _is_lumina_catalog_json(file_path):
    if file_path.name != "catalog.json":
        return False
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    if isinstance(data, dict):
        # The real Lumina catalog keeps its entries under "sounds"
        # ({"schemaVersion": 1, "count": 2882, "sounds": [...]}).
        for key in ("recipes", "sounds"):
            entries = data.get(key)
            if isinstance(entries, list) and len(entries) > CATALOG_RECIPE_THRESHOLD:
                return True
        return False
    if isinstance(data, list) and len(data) > CATALOG_RECIPE_THRESHOLD:
        return any(
            isinstance(item, dict)
            and "id" in item
            and isinstance(item.get("file"), str)
            and item["file"].startswith("recipes/")
            for item in data
        )
    return False


def _is_lumina_recipe_ts(rel_path):
    return rel_path.suffix.lower() == ".ts" and "recipes" in rel_path.parts[:-1]


def _is_lumina_skill_file(rel_path):
    return rel_path.as_posix() in LUMINA_SKILL_FILES


EXPORT_RULES = (
    {
        "name": "lumina-catalog",
        "description": "Lumina catalog.json containing more than 50 recipes",
        "match": lambda file_path, rel_path: _is_lumina_catalog_json(file_path),
    },
    {
        "name": "lumina-recipes",
        "description": "TypeScript recipe source file under a recipes directory",
        "match": lambda file_path, rel_path: _is_lumina_recipe_ts(rel_path),
    },
    {
        "name": "lumina-skill-file",
        "description": "Lumina skill metadata or script file",
        "match": lambda file_path, rel_path: _is_lumina_skill_file(rel_path),
    },
)


def check_export(path):
    target = Path(path)
    if not target.is_dir():
        return {
            "ok": False,
            "command": "sfx-lumina",
            "checked": str(path),
            "violations": [],
            "errors": [f"export directory not found: {path}"],
        }

    violations = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames.sort()
        filenames.sort()
        dir_p = Path(dirpath)
        for filename in filenames:
            file_path = dir_p / filename
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(target)
            for rule in EXPORT_RULES:
                try:
                    matched = rule["match"](file_path, rel_path)
                except OSError:
                    matched = False
                if matched:
                    violations.append({
                        "path": rel_path.as_posix(),
                        "rule": rule["name"],
                    })

    return {
        "ok": len(violations) == 0,
        "command": "sfx-lumina",
        "checked": str(path),
        "violations": violations,
    }


def _extract_candidates(search_data):
    if isinstance(search_data, list):
        return [c for c in search_data if isinstance(c, dict)]
    if isinstance(search_data, dict):
        for key in ("results", "candidates", "items", "recipes", "hits", "matches"):
            val = search_data.get(key)
            if isinstance(val, list):
                return [c for c in val if isinstance(c, dict)]
        if search_data.get("id") or search_data.get("slug"):
            return [search_data]
    return []


def _extract_generated_path(result_data, dest_abs, lumina_path, event):
    candidates = []
    if isinstance(result_data, dict):
        for key in ("file", "path", "wav", "output", "out"):
            val = result_data.get(key)
            if isinstance(val, str) and val.strip():
                candidates.append(val.strip())
        for key in ("files", "outputs"):
            val = result_data.get(key)
            if isinstance(val, list):
                for entry in val:
                    if isinstance(entry, str) and entry.strip():
                        candidates.append(entry.strip())
                    elif isinstance(entry, dict):
                        p = entry.get("path") or entry.get("file") or entry.get("wav")
                        if isinstance(p, str) and p.strip():
                            candidates.append(p.strip())
    for raw in candidates:
        p = Path(raw)
        if p.is_absolute() and p.is_file():
            return p
        in_dest = dest_abs / raw
        if in_dest.is_file():
            return in_dest
        in_lumina = lumina_path / raw
        if in_lumina.is_file():
            return in_lumina
    expected = dest_abs / f"{event}.wav"
    if expected.is_file():
        return expected
    return None


def _measure_wav(wav_path):
    info = audio_check.read_wav(str(wav_path))
    rate = info["rate"]
    frames = info["frames"]
    samples = info["samples"]
    duration_sec = round(frames / rate, 6) if rate > 0 else 0.0
    max_amp = max((abs(s) for s in samples), default=0.0)
    if max_amp <= 0.0:
        peak_db = SILENCE_PEAK_DB
    else:
        peak_db = round(20.0 * math.log10(max_amp), 3)
    return duration_sec, peak_db


def _append_macro_args(argv, sound):
    if sound.get("params") is not None:
        params = sound["params"]
        params_str = params if isinstance(params, str) else json.dumps(params, ensure_ascii=False)
        argv.extend(["--params", params_str])
    if sound.get("space") is not None:
        argv.extend(["--space", str(sound["space"])])
    if sound.get("wetness") is not None:
        argv.extend(["--wetness", str(sound["wetness"])])
    if sound.get("fit_seconds") is not None:
        argv.extend(["--fit-seconds", str(sound["fit_seconds"])])


def _process_sound(sound, dest_abs, res_prefix, lumina_path, run):
    event = sound["event"]
    kind = sound.get("kind") or "recipe"
    target_wav = dest_abs / f"{event}.wav"
    search_credits = []
    lumina_id = None

    if kind == "recipe":
        lumina_id = sound.get("id")
        if not lumina_id:
            intent = sound.get("intent")
            if not isinstance(intent, str) or not intent.strip():
                raise ValueError("recipe sound requires 'intent' or 'id'")
            rc, out, err = run(
                ["node", "scripts/search.mjs", "--intent", intent.strip(), "--json"],
                lumina_path,
            )
            if rc != 0:
                raise RuntimeError(f"search failed (exit {rc}): {(err or out).strip()}")
            search_json = _parse_json_output(out)
            candidates = _extract_candidates(search_json)
            if not candidates:
                raise RuntimeError(f"no search candidates found for intent: {intent!r}")
            first = candidates[0]
            lumina_id = first.get("id") or first.get("slug") or first.get("recipe_id")
            if not lumina_id:
                raise RuntimeError(f"top search candidate missing id for intent: {intent!r}")
            search_credits = first.get("credits") or first.get("credit") or []

        argv = [
            "node",
            "scripts/remix.mjs",
            str(lumina_id),
            "--id",
            event.replace("_", "-"),  # remix requires a hyphenated output id
            "--format",
            "wav",
            "--dest",
            str(dest_abs),
        ]
        _append_macro_args(argv, sound)
        rc, out, err = run(argv, lumina_path)
        if rc != 0:
            raise RuntimeError(f"remix failed (exit {rc}): {(err or out).strip()}")
        result_json = _parse_json_output(out)
        if isinstance(result_json, dict) and result_json.get("errors"):
            raise RuntimeError(f"remix returned errors: {result_json['errors']}")

    elif kind == "footsteps":
        surface = sound.get("surface")
        if not isinstance(surface, str) or not surface.strip():
            raise ValueError("footsteps sound requires 'surface'")
        steps = sound.get("steps", 4)
        if not isinstance(steps, int) or isinstance(steps, bool) or steps <= 0:
            raise ValueError("footsteps 'steps' must be a positive integer")
        gait = sound.get("gait") or "walk"
        lumina_id = f"footsteps:{surface.strip()}"
        argv = [
            "node",
            "scripts/footsteps.mjs",
            "--surface",
            surface.strip(),
            "--steps",
            str(steps),
            "--gait",
            str(gait),
            "--out",
            str(target_wav),
        ]
        rc, out, err = run(argv, lumina_path)
        if rc != 0:
            raise RuntimeError(f"footsteps failed (exit {rc}): {(err or out).strip()}")
        result_json = _parse_json_output(out)
        if isinstance(result_json, dict) and result_json.get("id"):
            lumina_id = str(result_json["id"])

    elif kind == "scene":
        spec = sound.get("spec")
        if not isinstance(spec, dict):
            raise ValueError("scene sound requires 'spec' JSON object")
        lumina_id = "scene"
        spec_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", encoding="utf-8", delete=False
            ) as tmp:
                json.dump(spec, tmp, ensure_ascii=False)
                spec_path = tmp.name
            argv = [
                "node",
                "scripts/remix.mjs",
                "--spec",
                spec_path,
                "--format",
                "wav",
                "--dest",
                str(dest_abs),
            ]
            _append_macro_args(argv, sound)
            rc, out, err = run(argv, lumina_path)
        finally:
            if spec_path and os.path.exists(spec_path):
                try:
                    os.unlink(spec_path)
                except OSError:
                    pass
        if rc != 0:
            raise RuntimeError(f"scene remix failed (exit {rc}): {(err or out).strip()}")
        result_json = _parse_json_output(out)
        if isinstance(result_json, dict):
            if result_json.get("errors"):
                raise RuntimeError(f"scene remix returned errors: {result_json['errors']}")
            if result_json.get("id"):
                lumina_id = str(result_json["id"])

    else:
        raise ValueError(f"unsupported sound kind: {kind!r}")

    produced_path = _extract_generated_path(result_json, dest_abs, lumina_path, event)
    if produced_path is None:
        raise RuntimeError(f"generated WAV not found for event {event!r}")
    if produced_path.resolve() != target_wav.resolve():
        shutil.move(str(produced_path), str(target_wav))

    duration_sec, peak_db = _measure_wav(target_wav)

    result_credits = []
    if isinstance(result_json, dict):
        result_credits = result_json.get("credits") or result_json.get("credit") or []
    credits = _normalize_credits(result_credits, search_credits)

    entry = {
        "event": event,
        "file": _res_file_path(res_prefix, f"{event}.wav"),
        "duration_sec": duration_sec,
        "peak_db": peak_db,
        "lumina_id": lumina_id,
        "credits": credits,
    }
    if not credits:
        entry["credits_missing"] = True
    return entry


def generate_sfx(project, request, lumina_dir=None, runner=None):
    if isinstance(request, (str, Path)):
        try:
            req_data = json.loads(Path(request).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return _error_result([{"event": None, "error": f"cannot load request file: {exc}"}])
    else:
        req_data = request

    validation_errors = _validate_request(req_data)
    if validation_errors:
        return _error_result([{"event": None, "error": msg} for msg in validation_errors])

    try:
        dest_abs, res_prefix = _resolve_dest(project, req_data.get("dest"))
    except ValueError as exc:
        return _error_result([{"event": None, "error": str(exc)}])

    lumina_path = resolve_lumina_dir(lumina_dir)
    if not lumina_path.is_dir():
        return _error_result([{"event": None, "error": f"lumina skill directory not found: {lumina_path}"}])

    if runner is None:
        if shutil.which("node") is None:
            return _error_result([{"event": None, "error": "node executable not found in PATH"}])
        run = _default_runner
    else:
        run = runner

    dest_abs.mkdir(parents=True, exist_ok=True)

    placed = []
    errors = []
    for sound in req_data["sounds"]:
        event = sound["event"]
        try:
            entry = _process_sound(sound, dest_abs, res_prefix, lumina_path, run)
            placed.append(entry)
        except Exception as exc:
            errors.append({"event": event, "error": str(exc)})

    warnings = _collect_license_warnings(placed)
    if placed:
        warnings.extend(_update_manifest(dest_abs, placed))

    return {
        "ok": len(errors) == 0,
        "command": "sfx-lumina",
        "placed": placed,
        "manifest": _res_file_path(res_prefix, MANIFEST_FILENAME) if placed else None,
        "warnings": warnings,
        "errors": errors,
    }


def run_cli(project, args):
    request_path = None
    lumina_dir = None
    dest_override = None
    check_export_dir = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--request":
            if i + 1 >= len(args):
                raise LuminaBridgeError("--request requires a file path")
            request_path = args[i + 1]
            i += 2
        elif arg == "--lumina-dir":
            if i + 1 >= len(args):
                raise LuminaBridgeError("--lumina-dir requires a directory path")
            lumina_dir = args[i + 1]
            i += 2
        elif arg == "--dest":
            if i + 1 >= len(args):
                raise LuminaBridgeError("--dest requires a destination path")
            dest_override = args[i + 1]
            i += 2
        elif arg == "--check-export":
            if i + 1 >= len(args):
                raise LuminaBridgeError("--check-export requires a directory path")
            check_export_dir = args[i + 1]
            i += 2
        else:
            raise LuminaBridgeError(f"unknown argument: {arg}")

    if check_export_dir is not None:
        return check_export(check_export_dir)

    if not request_path:
        raise LuminaBridgeError("--request <file> is required")

    try:
        req_data = json.loads(Path(request_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LuminaBridgeError(f"cannot read request {request_path}: {exc}") from exc

    if dest_override is not None:
        if not isinstance(req_data, dict):
            raise LuminaBridgeError("request JSON must be an object")
        req_data["dest"] = dest_override

    return generate_sfx(project, req_data, lumina_dir=lumina_dir)
