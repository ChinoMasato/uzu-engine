#!/usr/bin/env python3
"""U.ZU Engine agent tools: one cross-platform entry (BACKLOG B-801).

Runs on Linux, Windows and macOS with Python 3.8+ and the standard library.
The shell scripts (engine.sh, look.sh, selfplay.sh, screenshot.sh, publish.sh)
are thin wrappers around this file; on Windows call it directly:
    py ai_loop\\uzu.py engine my_game tree --scene res://main.tscn
or through ai_loop\\windows\\uzu.bat.

  uzu.py engine   <project> <command> [options]   scene, class and project operations (B-401, B-201..B-203, B-304)
  uzu.py look     <project> <command> [options]   the U.ZU look (B-7xx), shot / check / panorama
  uzu.py anim     <project> motion|align [options]   rigged character clips and sprite alignment (B-1220)
  uzu.py build    <project> --spec spec.json [--shot out.png] [--budget JSON] [--no-render] [--no-report]
                  [--spec-set [dir]]   a whole scene from one JSON spec (B-1207, see ai_loop/build_tool.gd),
                  with its richness report; --spec-set also writes the generation spec set (B-1509)
  uzu.py enrich   <project> --preset village_rich|meadow|ruins [--scene res://x.tscn] [--surface Ground] [--seed N]
                  [--density-scale 1] [--shot out.png] [--no-render]   a richness preset in one call (B-1208), with the
                  report before and after and the difference (presets: ai_loop/presets/rich/)
  uzu.py ui       <project> --spec ui.json [--shot out.png [--over res://game.tscn]] [--theme wafu|sf|fantasy]
                  [--world fantasy|wafu|sf|horror|persona|pixel] [--font-subset]   a UI screen (Control tree with layout and theme) from one JSON spec (B-1301,
                  see ai_loop/ui_tool.gd); genre themes (ai_loop/presets/ui/) and a bundled Japanese font
                  subset for web builds (B-1303, ai_loop/ui_font.py; needs fonttools and brotli)
  uzu.py map      <project> nature|city --scene res://main.tscn [--spec JSON-or-file] [--set key=value ...]
                  [--overview top.png] [--replace] [--camera] [--look golden_hour] [--shot out.png] [--inline]
                  [--spec-set [dir]]   a natural map or a city from a short spec (UZUWorldGen); every key is
                  optional (presets); --spec-set also writes the generation spec set (B-1509)
  uzu.py map      options [nature|city]           every map key with its default, range and meaning, and the presets
  uzu.py map      <project> walk --scene res://x.tscn [--from spawn] [--to plaza,gate_east] [--seconds 90]
                  a walker under physics walks the city's navigation mesh to each place; per-target result
  uzu.py map      <project> walk-graph --graph region_graph.json [--scene res://x.tscn] [--seconds 0]
                  [--block-node <id>] [--out report.json]   region-graph verification (B-1510): a walker
                  under physics walks every edge of a B-1509 region graph in both directions; per-edge
                  pass/fail JSON with frames, seconds and stuck points; --block-node fences one node in
                  to prove that exactly its edges fail
  uzu.py image-scene <project> --image illustration.png [--depth depth.png] [--out image_scene]
                  [--fov 50] [--backdrop-width 26] [--no-build] [--no-walk] [--shot out.png]
                  [--seconds 60]   image-first scaffold (B-1221, see ai_loop/image_scene.py): the
                  illustration becomes a B-1207 spec -- backdrop card, cut-out layer cards,
                  candidate interact markers, the reference camera -- plus a generation report;
                  the spec is built and a capsule walker walks its waypoints
  uzu.py spec-diff <project> --spec-image illustration.png [--report report.json] [--scene res://x.tscn]
                  [--shot-png shot.png] [--thresholds t.json] [--frames 8] [--out verdict.json]
                  spec-image diff verification (B-1223, see ai_loop/spec_diff.py): shoots the scene
                  from its reference camera (or reuses --shot-png) and diffs the frame against the
                  specification illustration -- composition (edge agreement), colour (histogram
                  distance) and per-element presence from the B-1221 generation report -- as one
                  pass/fail JSON with every measured number
  uzu.py audit-scene <project> --scene res://x.tscn [--spec-set DIR] [--out report.json]
                  re-read audit of a saved scene (B-1511): recounts triangles, textures (count and
                  dimensions), placed instances and collision from the artifact itself -- never from
                  the generator -- and compares them with the generation spec set (B-1509; default:
                  the spec_set folder next to the scene). Differences come back per check with the
                  expected and recounted values; families the artifact cannot express are reported
                  not_countable with the reason
  uzu.py collision-check <project> --scene res://x.tscn [--start x,z ...] [--cell 0.5]
                  [--step 0.25] [--char-width 0.7] [--body-height 1.8] [--out report.json]
                  [--heatmap map.png]   mechanical collision check of a saved scene (B-1224):
                  rasterizes the collision and the visuals onto a grid and checks them
                  geometrically -- visual footprints collision does not cover, collision no
                  visual explains, wall leaks (visual barrier, collision gap) and plugged
                  gaps, walkable connectivity from the starts under the step rule (unreachable
                  places, disconnected starts with the bottleneck and its required rise,
                  pockets), and overlapping collision of different bodies. Findings carry
                  coordinates; --heatmap writes a top-down PNG of the same raster. Static and
                  geometric; the dynamic proof is the physics walker (map walk-graph)
  uzu.py picture  <project> <command> [options]   Picture prototype: doctor, schema, analyze, snap, adopt, validate, shot, map, pbr
  uzu.py selfplay <project> --input replay.json [--frames 1800] [--seed N] [--out r.json] [--movie m.avi] [--log e.jsonl]
                  [--hash-every 30 [--compare earlier.json]]   state hashes for determinism checks (B-307)
                  [--packet DIR] [--expect-clear]   on failure, a diagnosis packet in DIR (B-308)
  uzu.py feel-report <project> [--seed 7] [--no-juice] [--out r.json] [--compare r2.json] [--watch k,...]
                  [--probe-selftest [--frames 1500]]   feel proxy metrics (B-1112, see ai_loop/feel_report.py
                  and ai_loop/selfplay/feel_probe.gd): a self-verifying play sampled per frame -- per game
                  event, the input -> reaction latency, hitstop / slowmo segments, shake and kick curves,
                  flash segments and UI easing samples. Numbers for comparing runs (juice on/off, presets),
                  never a "feels good" verdict; --no-juice measures the same play with the game's juice
                  calls disabled, --probe-selftest fires one effect per channel without gameplay
  uzu.py dialogue --spec PATH [--out PATH] [--max-chars N]   validate or build dialogue/quest data (B-406)
  uzu.py replay-compare --expected PATH --actual PATH [--snapshots]   compare JSON/JSONL logs (B-314)
  uzu.py audio-check <file.wav> [--manifest sprite.json] [--loop] [--out report.json]
                  [--silence-db -60] [--max-silence-ms 100] [--clip-level 0.999] [--max-clip-ratio 0.001]
                  [--max-seam-jump 0.05] [--seam-ratio 4]   mechanical audio checks (B-1111, see
                  ai_loop/audio_check.py): peak/RMS levels, clipping, unintended silence runs, the
                  loop seam and audio-sprite segment/gap consistency, as numbers in one JSON report.
                  Simultaneous-playback overlap is out of scope (it needs playback-side logs)
  uzu.py ui-quality [--probe probe.json] [--engine PATH] [--theme wafu] [--image shot.png]
                  [--region x,y,w,h] [--texture-image sheet.png] [--texture-region x,y,w,h]
                  [--out report.json]   AAA UI quality gate (B-1310, see
                  ai_loop/ui_quality.py): texture repetition index (autocorrelation peak at
                  tile lags), WCAG contrast (body >= 4.5, heading >= 3.0, slider groove/fill
                  >= 2.0), 5-state completeness (focus must not be StyleBoxEmpty), theme
                  coverage of the standard controls and spacing/radius/shadow scale
                  conformance, as one uzu-ui-quality/1 JSON verdict. With --texture-image
                  (an empty-panel sheet at native resolution) the texture is also scored on
                  its own: designed micro-patterns by period residue + cell uniformity,
                  other materials by a visibility index, plus frame centre-slice coverage.
                  Theme data comes from --probe or from running
                  ai_loop/ui_quality_probe.gd with --engine. Exit 0 = pass, 1 = fail
  uzu.py font-locale-check <font.ttf|otf|ttc> [--face N] [--list-faces] [--out report.json]
                  font locale check (B-1316, see ai_loop/font_locale_check.py): the ink top of
                  、 (U+3001) and 。 (U+3002) must sit in the lower half of the body band
                  measured from the same font's kana/kanji -- JP faces pass (top at 0.33..0.36
                  of the band), centred TC/HK faces fail (0.65..0.67). The face of a TTC is
                  chosen with the face flag; list-faces prints the face names. Needs
                  fontTools. Exit 0 = pass, 1 = fail, 2 = usage/input error
  uzu.py catalog  <word> [<word> ...] [--limit N] [--caps a,b] [--profile caps.json]
                  search the feature catalog (B-403): every command, MCP tool,
                  preset, tool script and UZU class, generated from their definitions by ai_loop/make_catalog.py
                  into ai_loop/catalog.json; use it to discover what exists before reading the docs.
                  With a capability profile (B-404), matches are annotated with missing_capabilities
  uzu.py caps     [--caps image_gen,gpu] [--profile caps.json]   the agent capability profile (B-404): the
                  capabilities this agent declares (image_gen, gpu, blender, browser), from --caps,
                  $UZU_AGENT_CAPS and/or a JSON profile file ($UZU_AGENT_PROFILE); tools adapt to it
  uzu.py texture-route [--caps image_gen] [--profile caps.json] [--image generated.png] [--preset wood]
                  pick how a texture is made, by agent capability (B-404): with image_gen, a generated image
                  goes through UZUPBRFromImage (B-902); without it, the procedural PBR presets (B-1209)
                  are used instead; the result says which route was picked and why
  uzu.py building --spec spec.json [--out DIR] [--check] [--blender PATH] [--timeout 1800]
                  [--tex-size 2048] [--samples 48]   procedural buildings (B-1219): houses and shops from
                  parameters (width, depth, floors, roof, wall, seed) with real openings, frames and
                  eaves in geometry, a high-density version baked down to a practical GLB with a PBR
                  texture set; prints per-building triangle counts, the bake miss rate and GLB paths,
                  and renders the street three ways (WorldGen-style, grey recipe, textured recipe)
  uzu.py rock --spec spec.json [--out DIR] [--check] [--blender PATH] [--timeout 1800]
                  [--tex-size 2048] [--samples 48]   procedural rocks (B-1219 stage 2): faceted rocks
                  from parameters (seed, radius, cuts, bevel) -- half-space cuts make the flat faces
                  and ridges noise displacement cannot -- baked down to a practical GLB with a PBR
                  texture set (albedo / normal / ORM); prints triangle counts and the bake miss rate
  uzu.py publish  <build | project> [options]     through the bridge API (B-505)
  uzu.py selftest [engine | selfplay | tools | all | bake]   (all = engine, selfplay, tools; bake runs the editor)

engine commands: run, check, validate, shot, import, export, templates, uids [--fix] (B-205),
map-estimate (B-903: an outside model, then map-import), vfx [--name explosion|laser | --recipe JSON]
and vfx-recipes (B-1109: visual-effect recipes validated and normalized as structured output),
and every command of ai_loop/engine_tool.gd
(tree, props, get, set, add, instance, remove, reparent, call, connect, script, new,
classes, describe, actions, res-new, res-props, res-get, res-set, setting-get,
setting-set, action-add, action-remove, import-get, import-set, export-preset, presets);
also export (--preset, B-804) and templates. look commands: shot, check, panorama, rich (B-1204:
the richness report, static and rendered, with a budget), pbr (B-1209: procedural PBR presets
for bare models, --scene --assign 'House*:plaster,Ground:grass'), ui-report (B-1305: the UI's density,
text, margins and problems, headless), and those of
ai_loop/look_tool.gd (apply, rig, lamp, camera, material, info), and bake (lightmaps, B-805:
--scene res://x.tscn [--node Path/To/LightmapGI] [--prepare]).
Every command prints one JSON line {"ok": bool, ...}; exit 0 on success.

Environment:
  GODOT                 editor binary (default: found in bin/ for this OS; on Windows the
                        .console.exe is preferred, since it keeps stdout/stdin)
  UZU_SOFTWARE_RENDER   1 forces software Vulkan on a virtual display (Linux; the default
                        when there is no DISPLAY). Elsewhere the real GPU is used.
  UZU_RENDERING_DRIVER  rendering driver for shots and movies (default: vulkan)
"""

import glob
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LAVAPIPE = "/usr/share/vulkan/icd.d/lvp_icd.json"


class ToolError(Exception):
    def __init__(self, message, code=1, **extra):
        super().__init__(message)
        self.message, self.code, self.extra = message, code, extra


# ---------------------------------------------------------------- helpers


def find_godot():
    """The editor binary: $GODOT, else the newest editor build in bin/ for this OS."""
    if os.environ.get("GODOT"):
        return os.environ["GODOT"]
    system = platform.system()
    if system == "Windows":
        patterns = ["godot.windows.editor*.console.exe", "godot.windows.editor*.exe"]
    elif system == "Darwin":
        patterns = ["godot.macos.editor*"]
    else:
        patterns = ["godot.linuxbsd.editor*"]
    for pattern in patterns:
        found = [p for p in glob.glob(os.path.join(ROOT, "bin", pattern)) if os.path.isfile(p)]
        if found:
            return max(found, key=os.path.getmtime)
    raise ToolError("editor binary not found in bin/; build with target=editor or set GODOT", code=2)


def opt(args, name, default=""):
    key = "--" + name
    for i, a in enumerate(args):
        if a == key and i + 1 < len(args):
            return args[i + 1]
    return default


def run(cmd, timeout=300, env=None, cwd=None):
    """(exit code, combined output). A timeout counts as exit code 124, like timeout(1)."""
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, env=env, cwd=cwd)
        return p.returncode, p.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode("utf-8", errors="replace") + "\n(timed out)"


def render_command(cmd, size="1280x720"):
    """(command, env) for a run that draws frames. On Linux without a display this uses
    software Vulkan (lavapipe) on a virtual X display; elsewhere the real GPU."""
    env = dict(os.environ)
    software = os.environ.get("UZU_SOFTWARE_RENDER") == "1" or (platform.system() == "Linux" and not os.environ.get("DISPLAY"))
    if software:
        if not shutil.which("xvfb-run"):
            raise ToolError("rendering without a display needs xvfb-run (install xvfb)", code=2)
        if not os.path.exists(LAVAPIPE):
            raise ToolError(f"software rendering needs lavapipe ({LAVAPIPE}; install mesa-vulkan-drivers)", code=2)
        env["VK_ICD_FILENAMES"] = LAVAPIPE
        cmd = ["xvfb-run", "-a", "-s", f"-screen 0 {size}x24"] + cmd
    return cmd, env


def driver():
    return ["--rendering-driver", os.environ.get("UZU_RENDERING_DRIVER", "vulkan")]


def tail(text, n=20):
    return "\n".join(text.splitlines()[-n:])


def result_line(output, prefix):
    for line in output.splitlines():
        if line.startswith(prefix):
            return json.loads(line[len(prefix):])
    return None


def read_jsonl(path):
    items = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except ValueError:
                        pass
    return items


def gd_tool(project, script, args, prefix, timeout=300):
    rc, out = run([find_godot(), "--headless", "--path", project, "--script", os.path.join(HERE, script), "--"] + args, timeout=timeout)
    result = result_line(out, prefix)
    if result is None:
        sys.stderr.write(out)
        raise ToolError("no result from the engine (see stderr)")
    return result, rc


# ---------------------------------------------------------------- engine


def engine(project, args):
    command = args[0] if args else ""
    godot = find_godot()
    if command == "run":
        frames = opt(args, "frames", "120")
        scene = opt(args, "scene")
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = os.path.join(tmp, "errors.jsonl")
            rc, out = run([godot, "--headless", "--path", project, "--log-json", jsonl, "--quit-after", frames] + ([scene] if scene else []))
            errors = read_jsonl(jsonl)
        return {"ok": rc == 0, "command": "run", "exit_code": rc, "frames": int(frames), "errors": errors, "log_tail": tail(out)}
    if command == "check":
        path = opt(args, "path")
        if not path:
            raise ToolError("check needs --path res://script.gd")
        rc, out = run([godot, "--headless", "--path", project, "--check-only", "--json", "--script", path], timeout=120)
        result = next((json.loads(l) for l in out.splitlines() if l.startswith('{"ok":')), None)
        if result is None:  # The script could not be loaded at all.
            result = {"ok": False, "file": path, "errors": [{"file": path, "line": -1, "column": -1, "code": "LOAD", "message": tail(out, 10).strip()}], "warnings": []}
        result["ok"] = result["ok"] and rc == 0
        return {"command": "check", "path": path, **result}
    if command == "validate":
        result, _ = gd_tool(project, "engine_tool.gd", ["validate"], "ENGINE_RESULT ")
        for issue in result.get("issues", []):
            if issue["kind"] == "script_error":
                issue["errors"] = engine(project, ["check", "--path", issue["file"]])["errors"]
        # Shaders are checked by the engine's shader compiler, without a renderer (B-803).
        for path in project_files(project, (".gdshader", ".gdshaderinc")):
            result["checked"] = result.get("checked", 0) + 1
            check = engine(project, ["check", "--path", path])
            if not check["ok"]:
                result["issues"].append({"kind": "shader_error", "file": path, "message": f"{path} has errors", "errors": check["errors"]})
        result["ok"] = not result["issues"]
        return result
    if command == "shot":
        return look(project, args)
    if command == "import":
        return import_assets(project)
    if command == "map-estimate":
        return estimate_map(project, args)
    if command == "uids":
        return check_uids(project, fix="--fix" in args)
    if command == "export":
        return export(project, opt(args, "preset"), opt(args, "out"), "--debug" in args)
    if command == "templates":
        return fetch_templates() if "--fetch" in args else templates(project)
    if command == "export-preset" and opt(args, "template") == "auto":
        path = shared_template(opt(args, "platform", "web"))
        args = [path if (i > 0 and args[i - 1] == "--template") else a for i, a in enumerate(args)]
    result, _ = gd_tool(project, "engine_tool.gd", args, "ENGINE_RESULT ")
    if command == "import-set" and result.get("ok"):
        imported = import_assets(project)  # The new setting takes effect only once the file is reimported.
        result["ok"] = imported["ok"]
        result["errors"] = imported["errors"]
    return result


def export(project, preset, out="", debug=False):
    """Exports the project with a preset (B-804) and lists what was written."""
    if not preset:
        raise ToolError("export needs --preset <name> (see: engine <project> presets)")
    presets = gd_tool(project, "engine_tool.gd", ["presets"], "ENGINE_RESULT ")[0]["presets"]
    chosen = next((p for p in presets if p["name"] == preset), None)
    if chosen is None:
        raise ToolError(f"no export preset named '{preset}'", presets=[p["name"] for p in presets])
    out = os.path.abspath(out) if out else os.path.join(project, chosen["export_path"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = os.path.join(tmp, "errors.jsonl")
        rc, log = run([find_godot(), "--headless", "--path", project, "--export-debug" if debug else "--export-release", preset, out, "--log-json", jsonl], timeout=1800)
        errors = [e for e in read_jsonl(jsonl) if e.get("level") != "warning"]
    folder = os.path.dirname(out)
    files = sorted(f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)))
    ok = rc == 0 and os.path.exists(out)
    result = {"ok": ok, "command": "export", "preset": preset, "out": out, "files": files, "size_mb": round(sum(os.path.getsize(os.path.join(folder, f)) for f in files) / 1048576, 3), "errors": errors}
    if not ok:
        result["log_tail"] = re.sub(r"\x1b\[[0-9;]*m", "", tail(log, 12))
        if any("template" in (e.get("message", "") + log).lower() for e in errors) or "template" in log.lower():
            result["hint"] = "export templates are missing: see `engine <project> templates`, or give the preset a --template zip"
    return result


TEMPLATES_BRANCH = "export-templates"
SHARED_TEMPLATES = os.path.join(ROOT, "bin", "templates")


def fetch_templates():
    """Gets this fork's export templates from the repository's export-templates branch
    (kept out of the main history) into bin/templates/, checking each sha256."""
    rc, out = run(["git", "-C", ROOT, "fetch", "origin", TEMPLATES_BRANCH], timeout=600)
    if rc != 0:
        raise ToolError("could not fetch the export-templates branch: " + tail(out, 3))
    fetched = []
    rc, listing = run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", "FETCH_HEAD"], timeout=60)
    for info_path in [l for l in listing.splitlines() if l.endswith("info.json")]:
        info = json.loads(subprocess.run(["git", "-C", ROOT, "show", "FETCH_HEAD:" + info_path], capture_output=True, check=True).stdout)
        folder = os.path.dirname(info_path)
        data = subprocess.run(["git", "-C", ROOT, "show", f"FETCH_HEAD:{folder}/{info['file']}"], capture_output=True, check=True).stdout
        if hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise ToolError(f"{info['file']}: sha256 does not match info.json")
        os.makedirs(os.path.join(SHARED_TEMPLATES, folder), exist_ok=True)
        with open(os.path.join(SHARED_TEMPLATES, folder, info["file"]), "wb") as f:
            f.write(data)
        with open(os.path.join(SHARED_TEMPLATES, folder, "info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f)
        fetched.append(dict(info, platform=folder, path=os.path.join(SHARED_TEMPLATES, folder, info["file"])))
    return {"ok": bool(fetched), "command": "templates", "fetched": fetched}


def shared_template(platform_name):
    """The path of the shared template for a platform, fetching it when missing (--template auto)."""
    folder = os.path.join(SHARED_TEMPLATES, platform_name)
    info_path = os.path.join(folder, "info.json")
    if not os.path.exists(info_path):
        fetch_templates()
    if not os.path.exists(info_path):
        raise ToolError(f"no shared export template for '{platform_name}' on the {TEMPLATES_BRANCH} branch")
    with open(info_path, encoding="utf-8") as f:
        return os.path.join(folder, json.load(f)["file"])


def templates(project):
    """Where the editor looks for export templates, which are there, and the presets' own templates."""
    rc, out = run([find_godot(), "--version"], timeout=60)
    version = out.strip().splitlines()[-1] if out.strip() else ""
    config = ".".join(version.split(".")[:3])  # e.g. 4.8.beta (+ .mono in .NET builds)
    if platform.system() == "Windows":
        data = os.environ.get("APPDATA", "")
    elif platform.system() == "Darwin":
        data = os.path.expanduser("~/Library/Application Support")
    else:
        data = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    folder = os.path.join(data, "godot", "export_templates", config)
    installed = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    presets = gd_tool(project, "engine_tool.gd", ["presets"], "ENGINE_RESULT ")[0]["presets"]
    for p in presets:
        p["custom_template_exists"] = bool(p["custom_template"]) and os.path.exists(p["custom_template"])
    shared = sorted(os.listdir(SHARED_TEMPLATES)) if os.path.isdir(SHARED_TEMPLATES) else []
    return {"ok": True, "command": "templates", "engine_version": version, "templates_dir": folder, "installed": installed, "shared": shared, "presets": presets}


# ---------------------------------------------------------------- outside maps (B-903)


def estimate_map(project, args):
    """Runs the outside model configured for --kind (no model ships with the engine), then
    brings its output in with map-import. The config (default res://estimators.json) is
    {"depth": "python my_depth.py {in} {out}", "normal": "..."}; {in} and {out} become
    quoted absolute paths."""
    kind, src, out = opt(args, "kind"), opt(args, "in"), opt(args, "out")
    config = opt(args, "config", "res://estimators.json")
    if kind not in ("normal", "depth") or not src.startswith("res://") or not out.startswith("res://"):
        raise ToolError("map-estimate needs --kind normal|depth --in res://picture.png --out res://map.png [--config res://estimators.json]")
    config_path = os.path.join(project, config[len("res://"):]) if config.startswith("res://") else config
    try:
        with open(config_path, encoding="utf-8") as f:
            commands = json.load(f)
    except (OSError, ValueError):
        commands = {}
    if kind not in commands:
        raise ToolError(f'no estimator for "{kind}" in {config}; add e.g. {{"{kind}": "python my_model.py {{in}} {{out}}"}}')
    src_abs = os.path.join(project, src[len("res://"):])
    raw_res = out[: -len(".png")] + "_raw.png" if out.endswith(".png") else out + "_raw.png"
    raw_abs = os.path.join(project, raw_res[len("res://"):])
    os.makedirs(os.path.dirname(raw_abs), exist_ok=True)
    command = commands[kind].replace("{in}", '"%s"' % src_abs).replace("{out}", '"%s"' % raw_abs)
    try:
        p = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800, cwd=project)
        rc, log = p.returncode, p.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        rc, log = 124, "(timed out)"
    if rc != 0 or not os.path.exists(raw_abs):
        return {"ok": False, "command": "map-estimate", "error": f"the estimator failed (exit {rc})", "estimator": command, "log_tail": tail(log, 15)}
    rest = ["map-import", "--kind", kind, "--in", raw_res, "--for", src, "--out", out]
    for name in ("depth-kind",):
        if opt(args, name):
            rest += ["--" + name, opt(args, name)]
    if "--no-align" in args:
        rest.append("--no-align")
    result = engine(project, rest)
    result["command"] = "map-estimate"
    result["estimator"] = command
    result["raw"] = raw_res
    return result


# ---------------------------------------------------------------- UIDs (B-205)

UID_CHARS = "abcdefghijklmnopqrstuvwxy012345678"  # As core/io/resource_uid.cpp.
UID_OWNER_EXTENSIONS = (".gd", ".gdshader", ".gdshaderinc")  # Files whose UID lives in a .uid file next to them.
HEADER_UID = re.compile(r'^(\[gd_(?:scene|resource)\b[^\]]*?\buid=")(uid://[a-y0-8]+)(")')
EXT_RESOURCE = re.compile(r'^\[ext_resource\b([^\]]*)\]', re.M)
ATTR = re.compile(r'(\w+)="([^"]*)"')


def new_uid(taken):
    import secrets

    while True:
        n = secrets.randbits(63)
        text = ""
        while True:
            text = UID_CHARS[n % 34] + text
            n //= 34
            if n == 0:
                break
        uid = "uid://" + text
        if uid not in taken:
            taken.add(uid)
            return uid


def _res_path(project, absolute):
    return "res://" + os.path.relpath(absolute, project).replace(os.sep, "/")


def _abs(project, res):
    return os.path.join(project, res[len("res://"):].replace("/", os.sep)) if res.startswith("res://") else None


def _scan_uids(project):
    owners = {}  # uid -> [res paths]
    uid_of = {}  # res path -> uid
    issues = []
    texts = {}  # .tscn/.tres res path -> text
    for dirpath, dirs, files in os.walk(project):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            absolute = os.path.join(dirpath, name)
            res = _res_path(project, absolute)
            uid, owner = None, None
            if name.endswith((".tscn", ".tres")):
                with open(absolute, encoding="utf-8", errors="replace") as f:
                    texts[res] = f.read()
                m = HEADER_UID.match(texts[res])
                uid, owner = (m.group(2) if m else None), res
            elif name.endswith(".uid"):
                owner = res[: -len(".uid")]
                with open(absolute, encoding="utf-8", errors="replace") as f:
                    uid = f.read().strip()
                if not os.path.exists(absolute[: -len(".uid")]):
                    issues.append({"kind": "orphan_uid_file", "file": res, "uid": uid, "fix": "delete it (its file is gone)"})
                    continue
            elif name.endswith(".import"):
                owner = res[: -len(".import")]
                with open(absolute, encoding="utf-8", errors="replace") as f:
                    m = re.search(r'^uid="(uid://[a-y0-8]+)"', f.read(), re.M)
                uid = m.group(1) if m else None
            elif name.endswith(UID_OWNER_EXTENSIONS) and not os.path.exists(absolute + ".uid"):
                issues.append({"kind": "missing_uid_file", "file": res, "fix": "create %s.uid with a new UID" % res})
            if uid and owner:
                owners.setdefault(uid, []).append(owner)
                uid_of[owner] = uid
    return owners, uid_of, issues, texts


def check_uids(project, fix=False):
    """Checks UIDs against the files (B-205): duplicates, missing and orphan .uid files,
    and ext_resource references whose UID is stale or whose path moved. Proposes a fix
    for each; --fix applies them (new UIDs for duplicates and missing .uid files, the
    owner's UID or path in references, orphan .uid files deleted)."""
    fixed = []
    for _ in range(2):  # Duplicates first: renaming them can make references stale.
        owners, uid_of, issues, texts = _scan_uids(project)
        taken = set(owners)
        # A missing .uid file is best recreated with the UID its references already use.
        referenced = {}
        for text in texts.values():
            for m in EXT_RESOURCE.finditer(text):
                attrs = dict(ATTR.findall(m.group(1)))
                if attrs.get("uid") and attrs.get("path"):
                    referenced.setdefault(attrs["path"], attrs["uid"])
        for issue in issues:
            ref_uid = referenced.get(issue["file"]) if issue["kind"] == "missing_uid_file" else None
            if ref_uid and ref_uid not in owners:
                issue["uid"] = ref_uid
                issue["fix"] = "recreate %s.uid with %s, the UID its references use" % (issue["file"], ref_uid)
                owners[ref_uid] = [issue["file"]]
                uid_of[issue["file"]] = ref_uid
                taken.add(ref_uid)
        for uid, files in sorted(owners.items()):
            if len(files) > 1:
                keep = files[0]
                for other in files[1:]:
                    issues.append({"kind": "duplicate_uid", "file": other, "uid": uid, "also": keep, "fix": "give %s a new UID (keep %s on %s)" % (other, uid, keep)})
        for res, text in texts.items():
            for m in EXT_RESOURCE.finditer(text):
                attrs = dict(ATTR.findall(m.group(1)))
                uid, path = attrs.get("uid"), attrs.get("path", "")
                path_ok = bool(path) and _abs(project, path) is not None and os.path.exists(_abs(project, path))
                owner = (owners.get(uid) or [None])[0] if uid else None
                if path_ok and (not uid or owner == path):
                    continue
                if path_ok:
                    right = uid_of.get(path)
                    issues.append({"kind": "stale_uid", "file": res, "path": path, "uid": uid, "fix": ("use %s, the UID of %s" % (right, path)) if right else "remove the UID (the path is right)", "new_uid": right})
                elif owner and os.path.exists(_abs(project, owner)):
                    issues.append({"kind": "moved_path", "file": res, "path": path, "uid": uid, "fix": "use the path %s (where %s is now)" % (owner, uid), "new_path": owner})
                else:
                    issues.append({"kind": "broken_reference", "file": res, "path": path, "uid": uid, "fix": "none: neither the path nor the UID leads to a file"})
        if not fix or not any(i["kind"] in ("duplicate_uid", "missing_uid_file", "orphan_uid_file", "stale_uid", "moved_path") for i in issues):
            break
        dup = [i for i in issues if i["kind"] == "duplicate_uid"]
        for issue in dup:
            absolute = _abs(project, issue["file"])
            new = new_uid(taken)
            if issue["file"].endswith((".tscn", ".tres")):
                with open(absolute, encoding="utf-8") as f:
                    text = f.read()
                with open(absolute, "w", encoding="utf-8") as f:
                    f.write(HEADER_UID.sub(lambda m: m.group(1) + new + m.group(3), text, count=1))
            else:
                with open(absolute + ".uid", "w", encoding="utf-8") as f:
                    f.write(new + "\n")
            fixed.append(dict(issue, applied=new))
        if dup:
            continue  # Rescan: references to the renamed files are judged again.
        for issue in issues:
            kind = issue["kind"]
            if kind == "missing_uid_file":
                new = issue.get("uid") or new_uid(taken)
                with open(_abs(project, issue["file"]) + ".uid", "w", encoding="utf-8") as f:
                    f.write(new + "\n")
                fixed.append(dict(issue, applied=new))
            elif kind == "orphan_uid_file":
                os.remove(_abs(project, issue["file"]))
                fixed.append(dict(issue, applied="deleted"))
            elif kind in ("stale_uid", "moved_path"):
                absolute = _abs(project, issue["file"])
                with open(absolute, encoding="utf-8") as f:
                    text = f.read()

                def repair(m, issue=issue):
                    attrs = m.group(1)
                    if 'path="%s"' % issue["path"] not in attrs or (issue["uid"] and 'uid="%s"' % issue["uid"] not in attrs):
                        return m.group(0)
                    if kind == "moved_path":
                        attrs = attrs.replace('path="%s"' % issue["path"], 'path="%s"' % issue["new_path"])
                    elif issue.get("new_uid"):
                        attrs = attrs.replace('uid="%s"' % issue["uid"], 'uid="%s"' % issue["new_uid"]) if issue["uid"] else attrs.replace(' path=', ' uid="%s" path=' % issue["new_uid"], 1)
                    else:
                        attrs = attrs.replace(' uid="%s"' % issue["uid"], "")
                    return "[ext_resource" + attrs + "]"

                with open(absolute, "w", encoding="utf-8") as f:
                    f.write(EXT_RESOURCE.sub(repair, text))
                fixed.append(dict(issue, applied=issue.get("new_path") or issue.get("new_uid") or "removed"))
    owners, uid_of, remaining, texts = _scan_uids(project) if fixed else (None, None, issues, None)
    if fixed:
        remaining = check_uids(project, fix=False)["issues"]
    return {"ok": not remaining, "command": "uids", "issues": remaining, "fixed": fixed}


def project_files(project, extensions):
    """res:// paths of the project's files with these extensions (hidden directories skipped)."""
    found = []
    for dirpath, dirs, files in os.walk(project):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for f in sorted(files):
            if f.endswith(tuple(extensions)):
                found.append("res://" + os.path.relpath(os.path.join(dirpath, f), project).replace(os.sep, "/"))
    return found


def import_assets(project):
    """Imports (or reimports) the project's assets: textures, sounds, models... (B-802)."""
    retried = False
    for attempt in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = os.path.join(tmp, "errors.jsonl")
            rc, out = run([find_godot(), "--headless", "--path", project, "--import", "--log-json", jsonl], timeout=1800)
            errors = [e for e in read_jsonl(jsonl) if e.get("level") != "warning"]
        # An engine race at exit (upstream; fixed in this fork by B-806: late updates reached the
        # freed editor, "Parameter singleton is null" in is_cmdline_mode, and aborted). The import
        # has finished by then, so a crash on exit is still retried once, as a safety net.
        crashed_on_exit = rc < 0 and all("is_cmdline_mode" in e.get("function", "") or "singleton" in e.get("message", "") for e in errors)
        if not crashed_on_exit or attempt == 1:
            break
        retried = True
    imported = []
    for dirpath, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".import"):
                rel = os.path.relpath(os.path.join(dirpath, f[: -len(".import")]), project).replace(os.sep, "/")
                imported.append("res://" + rel)
    return {"ok": rc == 0 and not errors, "command": "import", "exit_code": rc, "retried": retried, "imported": sorted(imported), "errors": errors, "log_tail": tail(out, 10) if rc != 0 else ""}


# ---------------------------------------------------------------- look


def screenshot(project, out, frames=8, size="1280x720", scene=""):
    """Renders the main scene (or scene) and saves the last frame (Movie Maker)."""
    godot = find_godot()
    with tempfile.TemporaryDirectory() as tmp:
        args = driver() + ["--write-movie", os.path.join(tmp, "frame.png"), "--fixed-fps", "10", "--quit-after", str(frames)]
        cmd, env = render_command([godot, "--path", project] + ([scene] if scene else []) + args, size)
        rc, log = run(cmd, timeout=600, env=env, cwd=project)
        frames_written = sorted(glob.glob(os.path.join(tmp, "frame*.png")))
        if not frames_written:
            sys.stderr.write(log)
            raise ToolError("render failed: no frame was written (see stderr)", command="shot")
        os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
        shutil.copyfile(frames_written[-1], out)
    return {"ok": True, "command": "shot", "image": out}


def look(project, args):
    command = args[0] if args else "info"
    if command == "shot":
        out = opt(args, "out")
        if not out:
            raise ToolError("shot needs --out file.png")
        return screenshot(project, os.path.abspath(out), int(opt(args, "frames", "8")), scene=opt(args, "scene") or "")
    if command == "check":
        image = opt(args, "image")
        if not image:
            raise ToolError("check needs --image file.png")
        rc, out = run([sys.executable, os.path.join(HERE, "palette_check.py"), image, "--json-only"], timeout=120)
        result = next((json.loads(l) for l in out.splitlines() if l.startswith("{")), None)
        if result is None:
            raise ToolError("image check failed: " + tail(out, 5))
        result.setdefault("ok", rc == 0)
        result.setdefault("command", "check")
        return result
    if command == "panorama":
        out = opt(args, "out")
        if not out:
            raise ToolError("panorama needs --out file.png")
        with tempfile.TemporaryDirectory() as faces:
            cmd, env = render_command([find_godot(), "--path", project] + driver() + ["--script", os.path.join(HERE, "panorama_capture.gd"), "--", faces])
            rc, log = run(cmd, timeout=900, env=env, cwd=project)
            if not os.path.exists(os.path.join(faces, "faces.json")):
                sys.stderr.write(log)
                raise ToolError("capture failed (see stderr)", command="panorama")
            rc, out_text = run([sys.executable, os.path.join(HERE, "panorama.py"), faces, os.path.abspath(out), "--width", opt(args, "width", "1024")], timeout=600)
        result = next((json.loads(l) for l in out_text.splitlines() if l.startswith("{")), None)
        return result or {"ok": rc == 0, "command": "panorama", "image": os.path.abspath(out), "log": tail(out_text, 5)}
    if command == "bake":
        return bake(project, opt(args, "scene"), opt(args, "node"), "--prepare" in args)
    if command == "rich":
        return rich(project, args)
    if command == "ui-report":
        return ui_report(project, args)
    if command == "pbr":
        return pbr_apply(project, args)
    result, _ = gd_tool(project, "look_tool.gd", args, "UZU_RESULT ")
    return result


RICH_PROBE = 'UZURichProbe="*res://addons/uzu_selfplay/rich_probe.gd"\n'


def _main_scene(project):
    with open(os.path.join(project, "project.godot"), encoding="utf-8") as f:
        m = re.search(r'^run/main_scene="([^"]+)"', f.read(), re.M)
    return m.group(1) if m else ""


def pbr_apply(project, args):
    """Procedural PBR for bare models (B-1209): makes the presets the --assign rules name (if
    missing), imports them, and assigns them ('House*:plaster,Roof*:tile,Ground:grass')."""
    scene = opt(args, "scene") or _main_scene(project)
    rules = opt(args, "assign")
    if not scene or not rules:
        raise ToolError("pbr needs --scene res://x.tscn and --assign 'NodePattern:preset,...'")
    out = opt(args, "dir", "res://materials/pbr")
    made = []
    for preset in sorted({r.split(":")[-1].strip() for r in rules.split(",") if ":" in r}):
        if not os.path.exists(os.path.join(project, out[len("res://"):], preset, "albedo.png")):
            r, _ = gd_tool(project, "engine_tool.gd", ["pbr-preset", "--name", preset, "--out", out, "--size", opt(args, "size", "256")], "ENGINE_RESULT ")
            if not r or not r.get("ok"):
                return {"ok": False, "command": "pbr", "error": (r or {}).get("error", "pbr-preset failed")}
            made.append(preset)
    run([find_godot(), "--headless", "--path", project, "--import"], timeout=1800)
    extra = ["--scale", opt(args, "scale")] if opt(args, "scale") else []
    result, _ = gd_tool(project, "engine_tool.gd", ["pbr-assign", "--scene", scene, "--assign", rules, "--dir", out] + extra + (["--no-tint"] if "--no-tint" in args else []), "ENGINE_RESULT ")
    result = result or {"ok": False, "error": "pbr-assign printed no result"}
    result["command"] = "pbr"
    result["made"] = made
    return result


UI_PROBE = 'UZUUIReportProbe="*res://addons/uzu_selfplay/ui_report_probe.gd"\n'


def ui_report(project, args):
    """UI richness report (B-1305): runs a UI scene headless (layout and text need no GPU),
    measures every visible Control, and returns a summary (controls, panels, buttons, text,
    smallest font, depth, screen coverage, edge inset, unstyled parts), the problems with a
    fix for each (small text, text overflow, small buttons, no margin, overlap, off screen,
    unstyled), hints, and the top-level panels. ok is false when there are problems.
    --shot adds a screenshot of the same scene."""
    scene = opt(args, "scene") or _main_scene(project)
    if not scene:
        raise ToolError("ui-report needs --scene res://ui/screen.tscn")
    size = opt(args, "resolution", "1280x720")
    with tempfile.TemporaryDirectory() as tmp:
        game = os.path.join(tmp, "game")
        shutil.copytree(project, game)
        install_addons(game, ["ui_report_probe.gd"], UI_PROBE)
        run([find_godot(), "--headless", "--path", game, "--import"], timeout=1800)
        out = os.path.join(tmp, "ui.json")
        rc, log = run([find_godot(), "--headless", "--path", game, scene, "--resolution", size, "--quit-after", str(int(opt(args, "frames", "5")) + 120), "--", "--uzu-ui-report", out, opt(args, "frames", "5"), "--uzu-ui-size", size], timeout=600, cwd=game)
        if not os.path.exists(out):
            sys.stderr.write(log)
            raise ToolError("the UI was not measured (see stderr)", command="ui-report")
        with open(out, encoding="utf-8") as f:
            report = json.load(f)
    result = {"ok": not report["problems"], "command": "ui-report", "scene": scene, **report}
    if opt(args, "shot"):
        w, h = size.split("x")
        result["shot"] = screenshot(project, os.path.abspath(opt(args, "shot")), int(opt(args, "frames", "8")), f"{w}x{h}", scene=scene)["image"]
    return result


def check_budget(metrics, budget):
    """Budget keys are max_<metric> or min_<metric> (a scene can be too heavy, or not rich
    enough). Returns the failures; an unknown key is an error listing the metrics."""
    failures = []
    for key, limit in budget.items():
        kind, _, metric = key.partition("_")
        if kind not in ("max", "min") or metric not in metrics:
            raise ToolError(f"unknown budget key '{key}': use max_<metric> or min_<metric> with one of {sorted(metrics)}")
        value = metrics[metric]
        if (kind == "max" and value > limit) or (kind == "min" and value < limit):
            failures.append({"metric": metric, "value": value, kind: limit})
    return failures


def rich(project, args):
    """Richness report (B-1204): the scene's static costs (engine rich), what one rendered
    frame really drew (unless --no-render), and a budget check (--budget JSON or
    --budget-file), with hints on what to change. A summary first, details after."""
    scene = opt(args, "scene") or _main_scene(project)
    if not scene:
        raise ToolError("rich needs --scene res://... (the project has no main scene)")
    static, _ = gd_tool(project, "engine_tool.gd", ["rich", "--scene", scene, "--top", opt(args, "top", "10")], "ENGINE_RESULT ")
    if not static or not static.get("ok"):
        return static or {"ok": False, "command": "rich", "error": "the static analysis failed"}
    metrics = dict(static["summary"])
    frame = None
    if "--no-render" not in args:
        with tempfile.TemporaryDirectory() as tmp:
            game = os.path.join(tmp, "game")
            shutil.copytree(project, game)
            install_addons(game, ["rich_probe.gd"], RICH_PROBE)
            run([find_godot(), "--headless", "--path", game, "--import"], timeout=1800)
            out = os.path.join(tmp, "frame.json")
            cmd, env = render_command([find_godot(), "--path", game, scene] + driver() + ["--resolution", "1280x720"], "1280x720")
            rc, log = run(cmd + ["--", "--uzu-rich", out, opt(args, "frames", "10")], timeout=900, env=env, cwd=game)
            if not os.path.exists(out):
                sys.stderr.write(log)
                raise ToolError("the rendered frame was not measured (see stderr)", command="rich")
            with open(out, encoding="utf-8") as f:
                frame = json.load(f)
        metrics.update({k: v for k, v in frame.items() if k != "frames"})
    quality = static.get("model_quality", {})
    for k in ("pbr_coverage", "bevel_share", "cheap_meshes"):
        if k in quality:
            metrics[k] = quality[k]  # Budget keys too: min_pbr_coverage, min_bevel_share, max_cheap_meshes (B-1219).
    budget = {}
    if opt(args, "budget-file"):
        path = opt(args, "budget-file")
        path = os.path.join(project, path[len("res://"):]) if path.startswith("res://") else path
        with open(path, encoding="utf-8") as f:
            budget = json.load(f)
    elif opt(args, "budget"):
        budget = json.loads(opt(args, "budget"))
    failures = check_budget(metrics, budget)
    # Hints: what to look at first (heavy props repeated many times, many surfaces, big textures).
    hints = []
    for n in static.get("top", []):
        per = n["triangles"] // max(n["instances"], 1)
        if n["instances"] > 1 and per > 500:
            hints.append(f"{n['node']}: {n['instances']} copies of a {per}-triangle mesh ({n['triangles']} triangles); a low-poly mesh or fewer copies cuts this most")
        if per > 1000 and not n.get("lods"):
            hints.append(f"{n['node']}: a {per}-triangle mesh without LOD levels; engine lod adds them (far copies then draw far fewer triangles)")
        elif n["draw_calls"] > 8:
            hints.append(f"{n['node']}: {n['draw_calls']} surfaces (draw calls); merging materials cuts them")
    if metrics.get("texture_mb", 0) > 256:
        hints.append(f"textures take {metrics['texture_mb']} MB; check the largest images and VRAM compression")
    if static["summary"].get("untextured_share", 0) > 0.5 and static["summary"].get("materials", 0) >= 3:
        hints.append(f"{round(static['summary']['untextured_share'] * 100)}% of the materials have no texture and look cheap; look pbr gives models procedural PBR presets (wood, stone, brick, dirt, grass, plaster, tile)")
    if frame and static["summary"]["objects"] == 0 and frame["frame_objects"] > 0:
        hints.append("the scene builds its content at run time (scripts), so the static numbers miss it; judge by the frame_* numbers")
    if quality.get("cheap_meshes", 0) > 0:
        hints.append(f"{quality['cheap_meshes']} big plain boxes without texture (e.g. {quality['cheap'][0]}); model them from parts with chamfered edges and a texture set (UZUWorldGen detail high shows the recipe)")
    if quality and quality.get("bevel_share", 1) < 0.05 and static["summary"]["triangles"] > 0:
        hints.append("almost every edge is sharp (no chamfers); chamfered edges catch the light and read as made, not as primitives")
    if frame and metrics["frame_draw_calls"] > 2000:
        hints.append(f"{metrics['frame_draw_calls']} draw calls in the frame; MultiMesh (scatter) or merging meshes helps")
    # B-1219 stage 2: Blender-route stats (uzu.py building's stats.json)
    # on the same model_quality scale, so a building baked outside the
    # engine and a scene measured inside it read on one ruler.
    blender_quality = None
    if opt(args, "blender-stats"):
        stats_path = opt(args, "blender-stats")
        stats_path = os.path.join(project, stats_path[len("res://"):]) if stats_path.startswith("res://") else stats_path
        with open(stats_path, encoding="utf-8") as f:
            blender_stats = json.load(f)
        blender_quality = []
        for b in blender_stats.get("buildings", []):
            entry = {"name": b.get("name"), "model_quality": b.get("model_quality", {}),
                     "triangles_high": b.get("triangles_high"),
                     "bake_miss_rate": b.get("bake_miss_rate"),
                     "sharp_edge_preservation": (b.get("reduction") or {}).get("sharp_edge_preservation"),
                     "orm_texture": b.get("orm_texture")}
            blender_quality.append(entry)
            mq = entry["model_quality"]
            if mq.get("bevel_share", 1) < 0.05 and mq.get("triangles", 0) > 0:
                hints.append(f"blender building {entry['name']}: bevel_share {mq['bevel_share']} -- almost every edge is sharp; the recipe's chamfers should show here")
            if (entry["bake_miss_rate"] or 0) > 0.01:
                hints.append(f"blender building {entry['name']}: bake miss rate {entry['bake_miss_rate']} -- rays are missing the high model (cage / ray distance)")
    return {"ok": not failures, "command": "rich", "scene": scene, "summary": static["summary"], "frame": frame,
            "budget": budget or None, "failures": failures, "hints": hints, "top": static.get("top", []), "by_type": static.get("by_type", {}),
            "model_quality": quality, "blender_model_quality": blender_quality, "note": static.get("note", "")}


def _flag_value(args, name):
    """(present, value) for a --name [value] flag: the value is taken only
    when the next token is not another flag."""
    key = "--" + name
    for i, a in enumerate(args):
        if a == key:
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                return True, args[i + 1]
            return True, None
    return False, None


def _spec_set_dir(project, scene, requested):
    """Where a --spec-set goes (B-1509): the requested folder (a plain path,
    or res:// inside the project), or <scene folder>/<scene name>_spec_set
    next to the generated scene."""
    if requested:
        if requested.startswith("res://"):
            return os.path.join(project, requested[len("res://"):])
        return os.path.abspath(requested)
    rel = scene[len("res://"):] if scene and scene.startswith("res://") else "main.tscn"
    base = os.path.splitext(os.path.basename(rel))[0] + "_spec_set"
    return os.path.join(project, os.path.dirname(rel), base)


def _attach_spec_set(result, record, project, requested):
    """Writes the generation spec set (B-1509: ai_loop/spec_set.py) for a
    finished generation and folds the paths into the result. A failure to
    write the set is reported in the result, never hidden, and does not
    undo the generation."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import spec_set
    out_dir = _spec_set_dir(project, record.get("scene"), requested)
    try:
        written = spec_set.spec_set_from_record(record, out_dir)
    except Exception as e:
        result["spec_set"] = {"ok": False, "dir": out_dir, "error": str(e)}
        return result
    result["spec_set"] = {"ok": True, **written}
    return result


def _map_input_spec(project, rest):
    """The map spec as the caller wrote it (--spec file or inline JSON,
    with the --set overrides applied), mirroring map_tool.gd's own reading,
    plus where it came from. The spec set records this intent next to the
    parameters the generator resolved."""
    spec, source = {}, None
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--spec" and i + 1 < len(rest):
            raw = rest[i + 1]
            if raw.lstrip().startswith("{"):
                spec, source = json.loads(raw), "inline"
            else:
                path = os.path.join(project, raw[len("res://"):]) if raw.startswith("res://") else os.path.abspath(raw)
                with open(path, encoding="utf-8") as f:
                    spec = json.load(f)
                source = raw
            i += 2
        elif a == "--set" and i + 1 < len(rest):
            pair = rest[i + 1]
            eq = pair.find("=")
            if eq > 0:
                text = pair[eq + 1:]
                try:
                    value = json.loads(text)
                except ValueError:
                    value = text
                if value is None and text != "null":
                    value = text
                spec[pair[:eq]] = value
            i += 2
        else:
            i += 1
    return spec, source


WALK_PROBE = 'UZUWalk="*res://addons/uzu_selfplay/walk.gd"\n'


def map_walk(project, args):
    """Walking self-check (B-1507): a walker with a capsule walks a generated map's places in
    turn along the navigation server's path under physics (the scene runs headless), and reports, per
    target, whether it arrived, how long it took, the distance walked against the straight
    one, and where it got stuck. ok when every target was reached."""
    scene = opt(args, "scene") or _main_scene(project)
    if not scene:
        raise ToolError("map walk needs --scene res://... with a generated map")
    with tempfile.TemporaryDirectory() as tmp:
        game = os.path.join(tmp, "game")
        shutil.copytree(project, game)
        install_addons(game, ["selfplay/walk.gd"], WALK_PROBE)
        run([find_godot(), "--headless", "--path", game, "--import"], timeout=1800)
        out = os.path.join(tmp, "walk.json")
        limit = opt(args, "seconds", "90")
        rc, log = run([find_godot(), "--headless", "--path", game, scene, "--fixed-fps", "60", "--quit-after", str(int(float(limit) * 60 * 8 + 600)),
                       "--", "--uzu-walk", out, opt(args, "from", "spawn"), opt(args, "to", ""), limit], timeout=1800, cwd=game)
        if not os.path.exists(out):
            sys.stderr.write(log)
            raise ToolError("the walk did not finish (see stderr)", command="walk")
        with open(out, encoding="utf-8") as f:
            report = json.load(f)
    return {"command": "walk", "scene": scene, **report}


GRAPHWALK_PROBE = 'UZUGraphWalk="*res://addons/uzu_selfplay/graph_walk.gd"\\n'


def load_region_graph(path):
    """Loads and validates a region graph (B-1509, format uzu-region-graph/1): nodes with
    unique ids and [x, y, z] centers, edges joining known nodes. Raises ToolError."""
    try:
        with open(path, encoding="utf-8") as f:
            graph = json.load(f)
    except (OSError, ValueError) as e:
        raise ToolError(f"could not read region graph {path}: {e}", command="walk-graph")
    if not isinstance(graph, dict) or graph.get("format") != "uzu-region-graph/1":
        raise ToolError("not a region graph (format must be uzu-region-graph/1)", command="walk-graph")
    nodes = {}
    for n in graph.get("nodes") or []:
        center = n.get("center") if isinstance(n, dict) else None
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not isinstance(center, list) or len(center) != 3:
            raise ToolError("region graph node without an id and a [x, y, z] center", command="walk-graph")
        if n["id"] in nodes:
            raise ToolError(f"region graph node id twice: {n['id']}", command="walk-graph")
        nodes[n["id"]] = n
    if not nodes:
        raise ToolError("region graph has no nodes", command="walk-graph")
    for e in graph.get("edges") or []:
        if not isinstance(e, dict) or e.get("a") not in nodes or e.get("b") not in nodes:
            raise ToolError("region graph edge joins an unknown node", command="walk-graph")
    return graph


def map_walk_graph(project, args):
    """Region-graph walking verification (B-1510): a walker under physics (capsule, gravity,
    collisions, curb steps) walks every edge of a B-1509 region graph in both directions —
    along the navigation mesh where the walker is on it, steering straight at the target
    where there is none (natural terrain) — and reports, per edge, whether both directions
    arrived, with frames, seconds, meters walked and the stuck point of a failed leg.
    ok when every edge passed both ways. --block-node fences one node in with walls, to
    prove that exactly its edges fail. The scene (the graph's own "scene", or --scene)
    must already contain the generated map; composing it is the caller's step."""
    graph_arg = opt(args, "graph")
    if not graph_arg:
        raise ToolError("map walk-graph needs --graph region_graph.json (B-1509)", command="walk-graph")
    graph_path = graph_arg if os.path.isfile(graph_arg) else os.path.join(project, graph_arg)
    if not os.path.isfile(graph_path):
        raise ToolError(f"region graph not found: {graph_arg}", command="walk-graph")
    graph_path = os.path.abspath(graph_path)
    graph = load_region_graph(graph_path)
    scene = opt(args, "scene") or graph.get("scene") or _main_scene(project)
    if not scene:
        raise ToolError("map walk-graph needs --scene res://... (or a scene named in the graph)", command="walk-graph")
    if scene.startswith("res://") and not os.path.isfile(os.path.join(project, scene[6:])):
        raise ToolError(f"the scene is not in the project: {scene} (generate or compose it first)", command="walk-graph")
    cap = opt(args, "seconds", "0")
    block = opt(args, "block-node")
    edges = graph.get("edges") or []

    def leg_cap(length):
        return float(cap) if float(cap or 0) > 0 else min(600.0, max(45.0, 30.0 + float(length or 0) * 1.25))

    budget = int(sum(2 * leg_cap(e.get("length", 0)) for e in edges) * 60 * 2 + 3600)
    with tempfile.TemporaryDirectory() as tmp:
        game = os.path.join(tmp, "game")
        shutil.copytree(project, game)
        install_addons(game, ["selfplay/graph_walk.gd"], GRAPHWALK_PROBE)
        run([find_godot(), "--headless", "--path", game, "--import"], timeout=1800)
        out = os.path.join(tmp, "walk_graph.json")
        rc, log = run([find_godot(), "--headless", "--path", game, scene, "--fixed-fps", "60", "--quit-after", str(budget),
                       "--", "--uzu-walk-graph", graph_path, out, cap or "0", block or "-"], timeout=1800, cwd=game)
        if not os.path.exists(out):
            sys.stderr.write(log)
            raise ToolError("the graph walk did not finish (see stderr)", command="walk-graph")
        with open(out, encoding="utf-8") as f:
            report = json.load(f)
    out_file = opt(args, "out")
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return {"command": "walk-graph", "scene": scene, "graph": graph_path, **report}


def audit_scene_cmd(project, args):
    """Re-read audit of a saved scene (B-1511): ai_loop/audit_tool.gd re-opens the saved
    scene through the resource loader and counts what is actually in the artifact --
    mesh triangles, textures with dimensions, placed instances, collision shapes and
    bodies, lights, navigation meshes -- and ai_loop/audit_scene.py compares the
    recount with the generation spec set (B-1509). Nothing is taken from the
    generator's own report. ok when every comparable check matches; families the
    artifact cannot express are reported not_countable, with the reason."""
    scene = opt(args, "scene")
    if not scene:
        raise ToolError("audit-scene needs --scene res://...", command="audit-scene")
    scene_file = os.path.join(project, scene[len("res://"):]) if scene.startswith("res://") else scene
    if not os.path.isfile(scene_file):
        raise ToolError(f"the scene is not in the project: {scene} (generate or compose it first)", command="audit-scene")
    recount, _ = gd_tool(project, "audit_tool.gd", ["--scene", scene], "AUDIT_RESULT ", timeout=900)
    if not recount.get("ok"):
        raise ToolError(recount.get("error", "the audit recount failed"), command="audit-scene")
    spec_dir = opt(args, "spec-set")
    if spec_dir:
        spec_dir = os.path.join(project, spec_dir[len("res://"):]) if spec_dir.startswith("res://") else os.path.abspath(spec_dir)
    else:
        scene_dir = os.path.dirname(scene_file)
        for candidate in (os.path.join(scene_dir, "spec_set"),
                          os.path.join(scene_dir, os.path.splitext(os.path.basename(scene_file))[0] + "_spec_set")):
            if os.path.isfile(os.path.join(candidate, "asset_registry.json")):
                spec_dir = candidate
                break
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import audit_scene
    stored = audit_scene.parse_tscn_multimeshes(scene_file)
    report = audit_scene.build_report(scene, recount, stored, audit_scene.load_spec_set(spec_dir))
    report["spec_set"] = spec_dir if spec_dir and os.path.isdir(spec_dir) else None
    out_file = opt(args, "out")
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return {"command": "audit-scene", **report}


IMAGEWALK_PROBE = 'UZUImageWalk="*res://addons/uzu_selfplay/image_walk.gd"\n'


def collision_check_cmd(project, args):
    """Mechanical collision check of a saved scene (B-1224): ai_loop/collision_tool.gd
    extracts the collision solids (AABBs, heightfields, concave faces, planes), the
    visual footprints and the uzu_places metadata from the artifact, and
    ai_loop/collision_check.py rasterizes them onto a grid and checks them
    geometrically: coverage of visuals by collision (and the reverse overhang),
    wall leaks and plugged gaps, walkable connectivity from the starts under the
    step rule (unreachable places, disconnected starts with the bottleneck and
    its required rise, pockets) and overlapping collision. ok when no finding
    has severity "error". Starts default to the places whose name says spawn."""
    scene = opt(args, "scene")
    if not scene:
        raise ToolError("collision-check needs --scene res://...", command="collision-check")
    scene_file = os.path.join(project, scene[len("res://"):]) if scene.startswith("res://") else scene
    if not os.path.isfile(scene_file):
        raise ToolError(f"the scene is not in the project: {scene} (generate or compose it first)",
                        command="collision-check")
    extract, _ = gd_tool(project, "collision_tool.gd", ["--scene", scene], "COLLISION_RESULT ", timeout=900)
    if not extract.get("ok"):
        raise ToolError(extract.get("error", "the collision extraction failed"), command="collision-check")
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import collision_check
    opts = {}
    for name in ("cell", "step", "char-width", "body-height", "max-slope",
                 "min-visual-area", "coverage-min", "overhang-max", "min-pocket-area"):
        value = opt(args, name)
        if value:
            opts[name.replace("-", "_")] = float(value)
    starts = []
    for i, a in enumerate(args):
        if a == "--start" and i + 1 < len(args):
            sx, sz = args[i + 1].split(",")
            starts.append((float(sx), float(sz), f"start[{len(starts)}]"))
    try:
        report, raster = collision_check.analyze(extract, opts, starts or None)
    except ValueError as e:
        raise ToolError(str(e), command="collision-check")
    heatmap = opt(args, "heatmap")
    if heatmap:
        report["heatmap"] = collision_check.write_heatmap(raster, heatmap)
    out_file = opt(args, "out")
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return {"command": "collision-check", **report}


def animation_cmd(project, args):
    """Generate reusable clips for an imported rig or align a sprite sequence."""
    import argparse
    import tempfile
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="uzu.py anim <project>")
    commands = parser.add_subparsers(dest="command", required=True)
    motion = commands.add_parser("motion")
    motion.add_argument("--model", required=True)
    motion.add_argument("--out", required=True)
    motion.add_argument("--bones", type=Path, help="JSON file of bone name overrides")
    motion.add_argument("--speed", type=float, default=1.0)
    motion.add_argument("--stride", type=float, default=1.0)
    motion.add_argument("--weight", type=float, default=0.5)
    align = commands.add_parser("align")
    align.add_argument("--frames-dir", required=True)
    align.add_argument("--out", required=True)
    options = vars(parser.parse_args(args))
    root = Path(project).resolve()

    def local_path(raw):
        path = (root / (raw[6:] if raw.startswith("res://") else raw)).resolve()
        relative = path.relative_to(root)
        if not relative.parts:
            raise ValueError("Expected a path inside the project.")
        return path, "res://" + relative.as_posix()

    try:
        output, options["out"] = local_path(options["out"])
        if output.exists():
            raise ValueError(f"Output already exists: {options['out']}")
        if not output.parent.is_dir():
            raise ValueError("Output parent directory must exist.")
        if options["command"] == "motion":
            if output.suffix != ".tscn":
                raise ValueError("Motion output must have a .tscn extension.")
            model, options["model"] = local_path(options["model"])
            if not model.is_file():
                raise ValueError(f"Model does not exist: {options['model']}")
            for name, minimum, maximum in (("speed", 0.25, 4), ("stride", 0.25, 2), ("weight", 0, 1)):
                if not minimum <= options[name] <= maximum:
                    raise ValueError(f"--{name} must be between {minimum} and {maximum}.")
            bones_file = options.pop("bones")
            if bones_file is not None:
                bones = json.loads(bones_file.read_text(encoding="utf-8-sig"))
                if not isinstance(bones, dict) or not all(isinstance(name, str) and name.strip() for name in bones.values()):
                    raise ValueError("Bone overrides must map roles to nonempty names.")
                options["bones"] = bones
        else:
            _, options["frames_dir"] = local_path(options["frames_dir"])
    except (OSError, ValueError) as error:
        return {"ok": False, "error": str(error)}

    def generate():
        status, output_log = run([
            find_godot(), "--headless", "--path", project, "--script", os.path.join(HERE, "animation_tool.gd"),
            "--", json.dumps(options),
        ])
        result = result_line(output_log, "UZU_ANIMATION ")
        if result is None or (status and result.get("ok")):
            raise ToolError("Animation tool failed: " + tail(output_log, 15))
        return result

    if options["command"] == "align":
        return generate()
    try:
        with tempfile.TemporaryDirectory(prefix="uzu-motion-", dir=output.parent) as staging:
            staged = Path(staging) / output.name
            _, options["out"] = local_path(str(staged))
            result = generate()
            if result["ok"]:
                payload = staged.read_bytes()
                with output.open("xb") as target:
                    try:
                        target.write(payload)
                    except OSError:
                        target.close()
                        output.unlink()
                        raise
                result["scene"] = "res://" + output.relative_to(root).as_posix()
            return result
    except OSError as error:
        return {"ok": False, "error": str(error)}


def image_scene_cmd(project, args):
    """Image-first scaffold (B-1221): a specification illustration becomes a
    B-1207 build spec (backdrop card, cut-out layer cards, candidate markers,
    the reference camera) plus a generation report, written into
    <project>/<out>/ (default image_scene/). Unless --no-build, the spec is
    built; unless --no-walk, a capsule walker then walks the scaffold's
    waypoints in a copy of the project and the per-waypoint result comes
    back. Everything derived is a candidate (basis: inferred) -- see
    ai_loop/image_scene.py."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import image_scene as image_scene_mod

    image = opt(args, "image")
    if not image:
        raise ToolError("image-scene needs --image illustration.png", command="image-scene")
    image = os.path.abspath(image)
    if not os.path.isfile(image):
        raise ToolError(f"no illustration at {image}", command="image-scene")
    out_name = opt(args, "out", "image_scene").strip("/")
    depth = opt(args, "depth")
    try:
        spec, report, assets = image_scene_mod.analyze(
            image,
            depth_path=os.path.abspath(depth) if depth else None,
            depth_white_far="--depth-black-far" not in args,
            fov=float(opt(args, "fov", "50")),
            backdrop_width=float(opt(args, "backdrop-width", "26")),
            out_res="res://" + out_name,
            scene_name=out_name,
        )
    except (OSError, ValueError, zlib.error) as e:
        raise ToolError(f"could not analyse the illustration: {e}", command="image-scene")
    out_dir = os.path.join(project, out_name)
    os.makedirs(out_dir, exist_ok=True)
    for fname, data in assets.items():
        target = os.path.join(out_dir, fname)
        if data is None:  # The backdrop is the illustration itself.
            shutil.copyfile(image, target)
        else:
            with open(target, "wb") as f:
                f.write(data)
    spec_path = os.path.join(out_dir, "spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "walk_targets.json"), "w", encoding="utf-8") as f:
        json.dump({"spawn": report["spawn"], "waypoints": report["waypoints"]}, f, ensure_ascii=False, indent=2)
    result = {"ok": True, "command": "image-scene", "spec": spec["scene"],
              "spec_file": spec_path, "report": report}
    if "--no-build" in args:
        return result
    run([find_godot(), "--headless", "--path", project, "--import"], timeout=900)
    build_args = ["--spec", spec_path, "--no-report"]
    if opt(args, "shot"):
        build_args += ["--shot", os.path.abspath(opt(args, "shot"))]
    built = build(project, build_args)
    result["built"] = {k: built.get(k) for k in ("ok", "scene", "built", "error", "problems", "shot")}
    result["ok"] = bool(built.get("ok"))
    if not result["ok"] or "--no-walk" in args:
        return result
    with tempfile.TemporaryDirectory() as tmp:
        game = os.path.join(tmp, "game")
        shutil.copytree(project, game)
        install_addons(game, ["selfplay/image_walk.gd"], IMAGEWALK_PROBE)
        run([find_godot(), "--headless", "--path", game, "--import"], timeout=1800)
        out = os.path.join(tmp, "image_walk.json")
        limit = opt(args, "seconds", "60")
        targets = os.path.join(game, out_name, "walk_targets.json")
        rc, log = run([find_godot(), "--headless", "--path", game, spec["scene"], "--fixed-fps", "60",
                       "--quit-after", str(int(float(limit) * 60 * 8 + 600)),
                       "--", "--uzu-image-walk", out, targets, limit], timeout=1800, cwd=game)
        if not os.path.exists(out):
            sys.stderr.write(log)
            raise ToolError("the image walk did not finish (see stderr)", command="image-scene")
        with open(out, encoding="utf-8") as f:
            walk = json.load(f)
    result["walk"] = walk
    result["ok"] = bool(walk.get("ok"))
    return result


def spec_diff_cmd(project, args):
    """Spec-image diff verification (B-1223): shoot the scene from its
    reference camera and diff the frame against the specification
    illustration with ai_loop/spec_diff.py -- composition (edge agreement),
    colour (histogram distance) and per-element presence, the elements
    taken from the B-1221 generation report (--report, default
    <project>/image_scene/report.json; the B-1222 registry will be able to
    feed the same shape later). --shot-png reuses an existing screenshot
    instead of rendering. Thresholds come from --thresholds (a JSON file
    with spec_diff.DEFAULT_THRESHOLDS keys) plus per-metric flags."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import spec_diff

    spec_image = opt(args, "spec-image")
    if not spec_image:
        raise ToolError("spec-diff needs --spec-image illustration.png", command="spec-diff")
    spec_image = _abs(project, spec_image) if spec_image.startswith("res://") else os.path.abspath(spec_image)
    if not os.path.isfile(spec_image):
        raise ToolError(f"no specification image at {spec_image}", command="spec-diff")
    report_path = opt(args, "report")
    if report_path:
        report_path = _abs(project, report_path) if report_path.startswith("res://") else os.path.abspath(report_path)
    else:
        report_path = os.path.join(project, "image_scene", "report.json")
    if not os.path.isfile(report_path):
        raise ToolError(f"no generation report at {report_path} (pass --report)", command="spec-diff")
    with open(report_path, encoding="utf-8") as f:
        elements = spec_diff.elements_from_report(json.load(f))
    overrides = {}
    for flag, key in (("composition-min", "composition_min"), ("color-max", "color_max"),
                      ("element-agreement-min", "element_agreement_min")):
        if opt(args, flag):
            overrides[key] = float(opt(args, flag))
    try:
        thresholds = spec_diff.load_thresholds(opt(args, "thresholds") or None, overrides)
    except (OSError, ValueError) as e:
        raise ToolError(f"bad thresholds: {e}", command="spec-diff")
    shot = opt(args, "shot-png")
    if shot:
        shot = os.path.abspath(shot)
        if not os.path.isfile(shot):
            raise ToolError(f"no screenshot at {shot}", command="spec-diff")
        shot_keep = None
    else:
        tmp = tempfile.mkdtemp(prefix="uzu-spec-diff-")
        shot = os.path.join(tmp, "shot.png")
        shot_keep = tmp
        screenshot(project, shot, int(opt(args, "frames", "8")), scene=opt(args, "scene") or "")
    try:
        verdict = spec_diff.compare(spec_image, shot, elements, thresholds)
    except (OSError, ValueError, zlib.error) as e:
        raise ToolError(f"could not diff the images: {e}", command="spec-diff")
    verdict["command"] = "spec-diff"
    verdict["scene"] = opt(args, "scene") or _main_scene(project)
    verdict["report"] = report_path
    if opt(args, "out"):
        with open(os.path.abspath(opt(args, "out")), "w", encoding="utf-8") as f:
            json.dump(verdict, f, ensure_ascii=False, indent=2)
    if shot_keep:
        shutil.rmtree(shot_keep, ignore_errors=True)
    return verdict


def map_(project, args):
    """Map generation (UZUWorldGen, ai_loop/map_tool.gd): a natural map or a city from a short
    spec. --spec is inline JSON ({...}) or a file; --set key=value overrides one key. --look
    applies the U.ZU look (an atmosphere) to the scene afterwards, --shot saves a screenshot.
    --spec-set [dir] also writes the generation spec set (B-1509: scene_spec, region_graph,
    asset_registry, validation_report) into dir, or <scene>_spec_set next to the scene."""
    spec_set_present, spec_set_value = _flag_value(args, "spec-set")
    if spec_set_present:
        kept, i = [], 0
        while i < len(args):
            if args[i] == "--spec-set":
                i += 2 if (i + 1 < len(args) and not args[i + 1].startswith("--")) else 1
                continue
            kept.append(args[i])
            i += 1
        args = kept
    command = args[0] if args and not args[0].startswith("--") else "options"
    if command == "walk":
        return map_walk(project, args[1:])
    if command == "walk-graph":
        return map_walk_graph(project, args[1:])
    tool_args = [command]
    rest = args[1:] if args and not args[0].startswith("--") else list(args)
    i = 0
    temp_spec = None
    while i < len(rest):
        a = rest[i]
        value = rest[i + 1] if i + 1 < len(rest) else None
        if a == "--spec" and value is not None:
            if value.lstrip().startswith("{"):
                try:
                    json.loads(value)
                except ValueError as e:
                    raise ToolError(f"--spec is not valid JSON: {e}")
                temp_spec = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
                temp_spec.write(value)
                temp_spec.close()
                value = temp_spec.name
            elif value.startswith("res://"):
                value = os.path.join(project, value[len("res://"):])
            else:
                value = os.path.abspath(value)
            if not os.path.exists(value):
                raise ToolError(f"no spec at {value}")
            tool_args += [a, value]
            i += 2
        elif a == "--overview" and value is not None:
            tool_args += [a, os.path.abspath(value)]
            i += 2
        elif a in ("--look", "--shot", "--frames"):
            i += 2
        else:
            tool_args.append(a)
            i += 1
    try:
        result, _ = gd_tool(project, "map_tool.gd", tool_args, "UZU_RESULT ", timeout=900)
    finally:
        if temp_spec:
            os.unlink(temp_spec.name)
    if not result.get("ok") or command == "options":
        return result
    if opt(args, "look"):
        applied, _ = gd_tool(project, "look_tool.gd", ["apply", "--scene", result["scene"], "--atmosphere", opt(args, "look")], "UZU_RESULT ")
        result["look"] = applied
        result["ok"] = bool(applied.get("ok"))
    if opt(args, "shot") and result["ok"]:
        result["shot"] = screenshot(project, os.path.abspath(opt(args, "shot")), int(opt(args, "frames", "8")), scene=result["scene"])["image"]
    if spec_set_present and result.get("ok") and command in ("nature", "city"):
        input_spec, spec_source = _map_input_spec(project, rest)
        record = {"kind": "map", "generator": f"UZUWorldGen.generate_{command} (ai_loop/map_tool.gd)",
                  "scene": result.get("scene"), "spec_source": spec_source,
                  "input_spec": input_spec, "result": result}
        _attach_spec_set(result, record, project, spec_set_value)
    return result


def map_options():
    """`map options` needs no project: run it in an empty one."""
    with tempfile.TemporaryDirectory() as project:
        with open(os.path.join(project, "project.godot"), "w") as f:
            f.write('config_version=5\n\n[application]\n\nconfig/name="map options"\n')
        result, _ = gd_tool(project, "map_tool.gd", ["options"] + [a for a in sys.argv[3:4] if a in ("nature", "city")], "UZU_RESULT ")
        return result


def build(project, args):
    """Declarative scene building (B-1207): ai_loop/build_tool.gd makes the scene from a JSON
    spec, then the richness report (B-1204) of the result comes back with it, and a
    screenshot with --shot. --budget / --budget-file go to the report; --no-render keeps
    the report static. --spec-set [dir] also writes the generation spec set (B-1509)
    into dir, or <scene>_spec_set next to the scene."""
    spec = opt(args, "spec")
    if not spec:
        raise ToolError("build needs --spec spec.json (res:// or a path)")
    path = os.path.join(project, spec[len("res://"):]) if spec.startswith("res://") else os.path.abspath(spec)
    if not os.path.exists(path):
        raise ToolError(f"no spec at {path}")
    result, _ = gd_tool(project, "build_tool.gd", ["--spec", path], "BUILD_RESULT ")
    if not result:
        raise ToolError("the build tool printed no result", command="build")
    result["command"] = "build"
    if not result.get("ok"):
        return result
    build_ok = bool(result.get("ok"))  # The report below overwrites result["ok"]; the spec set wants the build's own.
    if "--no-report" not in args:
        report_args = ["rich", "--scene", result["scene"]] + (["--no-render"] if "--no-render" in args else [])
        for name in ("budget", "budget-file", "frames", "top"):
            if opt(args, name):
                report_args += ["--" + name, opt(args, name)]
        report = rich(project, report_args)
        result["report"] = {k: report.get(k) for k in ("ok", "summary", "frame", "budget", "failures", "hints", "top")}
        result["ok"] = bool(report.get("ok"))
    spec_set_present, spec_set_value = _flag_value(args, "spec-set")
    if spec_set_present:
        with open(path, encoding="utf-8") as f:
            build_spec = json.load(f)
        record = {"kind": "build", "generator": "ai_loop/build_tool.gd (B-1207)",
                  "scene": result.get("scene"), "spec_source": spec,
                  "input_spec": build_spec, "result": {**result, "ok": build_ok},
                  "report": result.get("report")}
        _attach_spec_set(result, record, project, spec_set_value)
    if opt(args, "shot"):
        result["shot"] = screenshot(project, os.path.abspath(opt(args, "shot")), int(opt(args, "frames", "8")), scene=result["scene"])["image"]
    return result


def ui(project, args):
    """Declarative UI (B-1301): ai_loop/ui_tool.gd builds a Control scene from a JSON spec;
    --shot renders it (over a game scene with --over res://game.tscn, on a CanvasLayer)."""
    spec = opt(args, "spec")
    if not spec:
        raise ToolError("ui needs --spec ui.json (res:// or a path)")
    path = os.path.join(project, spec[len("res://"):]) if spec.startswith("res://") else os.path.abspath(spec)
    if not os.path.exists(path):
        raise ToolError(f"no spec at {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    extra = {}
    # B-1303: a genre theme preset over the spec's theme, and a Japanese font subset.
    theme_name = opt(args, "theme")
    if theme_name:
        presets = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(HERE, "presets", "ui", "*.json"))}
        if theme_name not in presets:
            return {"ok": False, "command": "ui", "error": f"--theme needs one of {sorted(presets)}"}
        with open(presets[theme_name], encoding="utf-8") as f:
            preset = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        data["theme"] = {**data.get("theme", {}), **preset}
        extra["theme"] = theme_name
    if opt(args, "world"):
        data["theme"] = {**data.get("theme", {}), "world": opt(args, "world")}  # B-1307: one name switches the world.
        extra["world"] = opt(args, "world")
    if "--font-subset" in args:
        import ui_font
        scene_name = os.path.splitext(os.path.basename(data.get("scene", "ui.tscn")))[0]
        fonts = ui_font.subset(ui_font.spec_text(data), os.path.join(project, "fonts"), scene_name)
        extra["fonts"] = fonts
        if not fonts.get("ok"):
            return {"ok": False, "command": "ui", "error": fonts.get("error"), "fonts": fonts}
        data["theme"] = {**data.get("theme", {}), "font": f"res://fonts/{scene_name}_latin.woff2", "font_fallback": f"res://fonts/{scene_name}_ja.woff2"}
        run([find_godot(), "--headless", "--path", project, "--import"], timeout=1800)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        tmp_spec = f.name
    try:
        result, _ = gd_tool(project, "ui_tool.gd", ["--spec", tmp_spec], "UI_RESULT ")
    finally:
        os.unlink(tmp_spec)
    if not result:
        raise ToolError("the UI tool printed no result", command="ui")
    result["command"] = "ui"
    result.update(extra)
    if not result.get("ok") or not opt(args, "shot"):
        return result
    scene = result["scene"]
    over = opt(args, "over")
    preview = os.path.join(project, "uzu_ui_preview.tscn")
    try:
        if over:
            with open(preview, "w", encoding="utf-8") as f:
                f.write('[gd_scene format=3]\n\n'
                        f'[ext_resource type="PackedScene" path="{over}" id="1"]\n'
                        f'[ext_resource type="PackedScene" path="{scene}" id="2"]\n\n'
                        '[node name="Preview" type="Node"]\n\n'
                        '[node name="Game" parent="." instance=ExtResource("1")]\n\n'
                        '[node name="UI" type="CanvasLayer" parent="."]\n\n'
                        '[node name="Screen" parent="UI" instance=ExtResource("2")]\n')
            run([find_godot(), "--headless", "--path", project, "--import"], timeout=1800)
        result["shot"] = screenshot(project, os.path.abspath(opt(args, "shot")), int(opt(args, "frames", "8")), scene="res://uzu_ui_preview.tscn" if over else scene)["image"]
    finally:
        for f in (preview, preview + ".uid"):
            if os.path.exists(f):
                os.remove(f)
    return result


PRESETS_DIR = os.path.join(HERE, "presets", "rich")


def rich_presets():
    out = {}
    for f in sorted(glob.glob(os.path.join(PRESETS_DIR, "*.json"))):
        with open(f, encoding="utf-8") as fh:
            out[os.path.splitext(os.path.basename(f))[0]] = json.load(fh)
    return out


def enrich(project, args):
    """Richness presets (B-1208): adds a preset's props, particles and look to an existing
    scene in one call (ai_loop/presets/rich/*.json, through build_tool.gd with "base"), and
    returns the richness report before and after with the difference. Applying again
    replaces the preset's earlier props. --surface names the ground (default Ground),
    --seed varies the layout, --density-scale multiplies every density."""
    presets = rich_presets()
    name = opt(args, "preset")
    if name not in presets:
        return {"ok": False, "command": "enrich", "error": f"--preset needs one of {sorted(presets)}", "presets": {k: v.get("_about", "") for k, v in presets.items()}}
    scene = opt(args, "scene") or _main_scene(project)
    if not scene:
        raise ToolError("enrich needs --scene res://... (the project has no main scene)")
    spec = {k: v for k, v in json.loads(json.dumps(presets[name])).items() if not k.startswith("_")}
    spec["base"] = scene
    seed_offset = int(opt(args, "seed", "0"))
    scale = float(opt(args, "density-scale", "1"))
    for item in spec.get("scatter", []):
        item["on"] = opt(args, "surface", "Ground")
        item["seed"] = int(item.get("seed", 1)) + seed_offset
        item["density"] = float(item.get("density", 1)) * scale
    report_args = ["rich", "--scene", scene] + (["--no-render"] if "--no-render" in args else [])
    for key in ("budget", "budget-file", "frames"):
        if opt(args, key):
            report_args += ["--" + key, opt(args, key)]
    before = rich(project, report_args)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(spec, f)
        spec_path = f.name
    try:
        built, _ = gd_tool(project, "build_tool.gd", ["--spec", spec_path], "BUILD_RESULT ")
    finally:
        os.unlink(spec_path)
    if not built or not built.get("ok"):
        return {"ok": False, "command": "enrich", "preset": name, **(built or {"error": "the build tool printed no result"})}
    after = rich(project, report_args)
    def flat(r):
        return {**(r.get("summary") or {}), **(r.get("frame") or {})}
    b, a = flat(before), flat(after)
    diff = {k: round(a[k] - b[k], 3) for k in a if k in b and isinstance(a[k], (int, float)) and a[k] != b[k]}
    result = {"ok": after.get("ok", False), "command": "enrich", "preset": name, "scene": scene, "built": built.get("built"),
              "diff": diff, "before": {"summary": before.get("summary"), "frame": before.get("frame")},
              "after": {"summary": after.get("summary"), "frame": after.get("frame"), "failures": after.get("failures"), "hints": after.get("hints")}}
    if opt(args, "shot"):
        result["shot"] = screenshot(project, os.path.abspath(opt(args, "shot")), int(opt(args, "frames", "8")), scene=scene)["image"]
    return result


BAKE_PLUGIN = "res://addons/uzu_bake/plugin.cfg"


def bake(project, scene, node="", prepare=False):
    """Bakes the scene's LightmapGI (B-805). Lightmap baking needs the editor's import
    system and a GPU-capable renderer, so the editor runs (drawing: software Vulkan
    without a display) with a temporary plugin that bakes and saves the scene. The
    project's project.godot is restored and the plugin removed afterwards."""
    if not scene:
        raise ToolError("bake needs --scene res://level.tscn")
    cfg = os.path.join(project, "project.godot")
    addon = os.path.join(project, "addons", "uzu_bake")
    if os.path.exists(addon):
        raise ToolError("addons/uzu_bake already exists in the project; remove it first")
    with open(cfg, encoding="utf-8") as f:
        original = f.read()
    enabled = re.search(r'^enabled=PackedStringArray\((.*)\)$', original, re.M)
    if "\n[editor_plugins]\n" in original and enabled:
        items = [x for x in enabled.group(1).split(",") if x.strip()]
        text = original.replace(enabled.group(0), "enabled=PackedStringArray(" + ", ".join(items + [f'"{BAKE_PLUGIN}"']) + ")", 1)
    else:
        text = original.rstrip("\n") + f'\n\n[editor_plugins]\n\nenabled=PackedStringArray("{BAKE_PLUGIN}")\n'
    shutil.copytree(os.path.join(HERE, "bake"), addon)
    try:
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(text)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "bake.json")
            user = ["--", "--uzu-bake-scene", scene, "--uzu-bake-out", out] + (["--uzu-bake-node", node] if node else []) + (["--uzu-bake-prepare"] if prepare else [])
            cmd, env = render_command([find_godot(), "-e", "--path", project] + driver() + user)
            rc, log = run(cmd, timeout=3600, env=env, cwd=project)
            result = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else None
    finally:
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(original)  # Exactly as it was.
        shutil.rmtree(addon, ignore_errors=True)
        for leftover in glob.glob(os.path.join(project, ".godot", "editor", "*uzu_bake*")):
            os.remove(leftover)
    if result is None:
        return {"ok": False, "command": "bake", "error": "the editor did not report a result", "log_tail": re.sub(r"\x1b\[[0-9;]*m", "", tail(log, 15))}
    result["command"] = "bake"
    return result


# ---------------------------------------------------------------- selfplay

AUTOLOADS_REPLAY = 'UZUReplay="*res://addons/uzu_selfplay/replay.gd"\nUZUTelemetry="*res://addons/uzu_selfplay/telemetry.gd"\n'


def install_addons(project_copy, files, autoloads):
    """Copies the given ai_loop files into res://addons/uzu_selfplay/ and prepends the
    autoloads, so they run before the game's own nodes. The original project is not touched."""
    addon = os.path.join(project_copy, "addons", "uzu_selfplay")
    os.makedirs(addon, exist_ok=True)
    for f in files:
        shutil.copy(os.path.join(HERE, f), addon)
    cfg = os.path.join(project_copy, "project.godot")
    with open(cfg, encoding="utf-8") as f:
        text = f.read()
    if "\n[autoload]\n" in text:
        text = text.replace("\n[autoload]\n", "\n[autoload]\n\n" + autoloads, 1)
    else:
        text += "\n[autoload]\n\n" + autoloads
    with open(cfg, "w", encoding="utf-8") as f:
        f.write(text)


def selfplay(project, args):
    replay = opt(args, "input")
    if not replay or not os.path.isfile(replay):
        raise ToolError("selfplay needs --input replay.json")
    replay = os.path.abspath(replay)
    frames, out, movie, events_out, seed = opt(args, "frames", "1800"), opt(args, "out"), opt(args, "movie"), opt(args, "log"), opt(args, "seed")
    hash_every, compare = opt(args, "hash-every"), opt(args, "compare")
    packet = opt(args, "packet")
    godot = find_godot()
    sys.path.insert(0, os.path.join(HERE, "telemetry"))
    import report as telemetry

    with tempfile.TemporaryDirectory() as work:
        game = os.path.join(work, "game")
        shutil.copytree(project, game)
        files, autoloads = ["telemetry/telemetry.gd", "selfplay/replay.gd"], AUTOLOADS_REPLAY
        if hash_every:  # State hashes for determinism checks (B-307).
            files.append("selfplay/state_hash.gd")
            autoloads += 'UZUStateHash="*res://addons/uzu_selfplay/state_hash.gd"\n'
        install_addons(game, files, autoloads)
        # B-311: a copy without .godot cannot load imported resources (a
        # preloading script fails to parse); import the copy first.
        if not os.path.exists(os.path.join(game, ".godot", "imported")):
            import_assets(game)
        log, errors_path = os.path.join(work, "events.jsonl"), os.path.join(work, "errors.jsonl")
        hash_path = os.path.join(work, "state_hash.json")
        base = ["--path", game, "--fixed-fps", "60", "--quit-after", frames, "--log-json", errors_path]
        user = ["--", "--uzu-telemetry", log, "--uzu-replay", replay] + (["--uzu-seed", seed] if seed else [])
        if hash_every:
            user += ["--uzu-state-hash", hash_path, "--uzu-hash-every", hash_every]
        env = None
        if movie:
            movie = os.path.abspath(movie)
            cmd, env = render_command([godot] + driver() + ["--resolution", "640x360", "--write-movie", movie] + base + user, "640x360")
        else:
            cmd = [godot, "--headless"] + base + user
        rc, out_text = run(cmd, timeout=900, env=env)
        if events_out and os.path.exists(log):
            shutil.copyfile(log, events_out)
        if not os.path.exists(log):
            return {"ok": False, "command": "selfplay", "error": "no telemetry was written", "log_tail": tail(out_text)}
        events = telemetry.read_events([log])
        rep = telemetry.report(events)
        errors = read_jsonl(errors_path)
        state_hashes = None
        if hash_every and os.path.exists(hash_path):
            with open(hash_path, encoding="utf-8") as f:
                state_hashes = json.load(f)
    quit_event = next((e for e in reversed(events) if e.get("type") == "quit"), {})
    result = {
        "ok": rc == 0,
        "command": "selfplay",
        "exit_code": rc,
        "cleared": rep["cleared"] == 1,
        "checkpoints": [c["id"] for c in rep["checkpoints"]],
        "deaths": rep["deaths"],
        "frames": max((e.get("frame", 0) for e in events), default=0),
        "fps": quit_event.get("fps"),
        "movie": movie or None,
        "errors": errors,
        "report": rep,
    }
    if "--expect-clear" in args and not result["cleared"]:
        result["ok"] = False
    if packet:
        failure = failure_reason(result, "--expect-clear" in args)
        if failure:
            result["ok"] = False  # With --packet, errors count as a failure (a script error does not stop the game).
            result["packet"] = write_failure_packet(packet, project, replay, seed, result, failure, events)
    if hash_every:
        result["state_hashes"] = state_hashes or {"error": "no state hashes were written"}
        if compare:
            result["comparison"] = compare_state_hashes(compare, result["state_hashes"])
            result["ok"] = result["ok"] and result["comparison"]["same"]
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    return result


def failure_reason(result, expect_clear=False):
    """Why a self-play counts as failed, or None (B-308)."""
    serious = [e for e in result["errors"] if e.get("level") in ("error", "script_error")]
    if serious:
        return "error"
    if result["exit_code"] != 0:
        return "exit_code"
    if expect_clear and not result["cleared"]:
        return "not_cleared"
    return None


def write_failure_packet(folder, project, replay, seed, result, reason, events):
    """Bundles what an agent needs to diagnose a failed self-play without running it
    again (B-308): the structured errors (first one first, with the script line), a
    frame and the declared state (B-307) at the failure, the input replay and seed with
    the command to re-run, and the telemetry. Writes <folder>/packet.json and files."""
    os.makedirs(folder, exist_ok=True)
    serious = [e for e in result["errors"] if e.get("level") in ("error", "script_error")]
    first = serious[0] if serious else None
    # The failure frame: the first error's, else the last frame played.
    frame = int(first.get("frame", 0)) if first else 0
    if frame <= 0:
        frame = max(result["frames"], 1)
    shutil.copyfile(replay, os.path.join(folder, "replay.json"))
    with open(os.path.join(folder, "errors.jsonl"), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e, ensure_ascii=False) + "\n" for e in result["errors"])
    with open(os.path.join(folder, "events.jsonl"), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e, ensure_ascii=False) + "\n" for e in events)
    # Replay through the failure frame (quit after the next one, so the state includes
    # what that frame did) with drawing and state hashing: the run is
    # deterministic (fixed input, fixed FPS, same seed), so it stops at the same point.
    shot, state = None, None
    with tempfile.TemporaryDirectory() as work:
        game = os.path.join(work, "game")
        shutil.copytree(project, game)
        install_addons(game, ["telemetry/telemetry.gd", "selfplay/replay.gd", "selfplay/state_hash.gd"], AUTOLOADS_REPLAY + 'UZUStateHash="*res://addons/uzu_selfplay/state_hash.gd"\n')
        hash_path = os.path.join(work, "state.json")
        movie = os.path.join(work, "frame.png")
        user = ["--", "--uzu-telemetry", os.path.join(work, "e.jsonl"), "--uzu-replay", replay, "--uzu-state-hash", hash_path, "--uzu-hash-every", "1"] + (["--uzu-seed", seed] if seed else [])
        try:
            cmd, env = render_command([find_godot(), "--path", game] + driver() + ["--resolution", "640x360", "--write-movie", movie, "--fixed-fps", "60", "--quit-after", str(frame + 1)] + user, "640x360")
            run(cmd, timeout=900, env=env)
        except ToolError:
            cmd = [find_godot(), "--headless", "--path", game, "--fixed-fps", "60", "--quit-after", str(frame + 1)] + user
            run(cmd, timeout=900)
        frames = sorted(glob.glob(os.path.join(work, "frame*.png")))
        if frames:
            shot = os.path.join(folder, "failure.png")
            shutil.copyfile(frames[-1], shot)
        if os.path.exists(hash_path):
            with open(hash_path, encoding="utf-8") as f:
                state = json.load(f).get("state")
    with open(os.path.join(folder, "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    where = None
    if first:
        # The script position: the script error's own, or the script line that raised an engine error.
        where = {"file": first.get("script_file") or first.get("file"), "line": first.get("script_line", first.get("line")), "function": first.get("script_function") or first.get("function")}
    rerun = ["python3", "ai_loop/uzu.py", "selfplay", project, "--input", os.path.join(folder, "replay.json"), "--frames", str(result["frames"] or 1800)] + (["--seed", seed] if seed else [])
    packet = {
        "reason": reason,
        "where": where,
        "first_error": first,
        "frame": frame,
        "errors": len(result["errors"]),
        "screenshot": "failure.png" if shot else None,
        "state": state,
        "checkpoints": result["checkpoints"],
        "deaths": result["deaths"],
        "cleared": result["cleared"],
        "report": result["report"],
        "replay": "replay.json",
        "seed": seed or None,
        "rerun": rerun,
        "files": sorted(os.listdir(folder)) + ["packet.json"],
    }
    with open(os.path.join(folder, "packet.json"), "w", encoding="utf-8") as f:
        json.dump(packet, f, ensure_ascii=False, indent=1)
    return {"folder": os.path.abspath(folder), "reason": reason, "where": where, "frame": frame}


def compare_state_hashes(baseline, current):
    """Compares state hashes with an earlier selfplay result (B-307): the first frame
    where they differ, and the declared state at the end of both runs."""
    if isinstance(baseline, str):
        with open(baseline, encoding="utf-8") as f:
            baseline = json.load(f)
    base = (baseline.get("state_hashes") or baseline).get("hashes", {})
    cur = current.get("hashes", {}) if isinstance(current, dict) else {}
    frames = sorted({int(k) for k in base} | {int(k) for k in cur})
    first = next((f for f in frames if base.get(str(f)) != cur.get(str(f))), None)
    result = {"same": first is None and bool(frames), "compared_frames": len(frames), "first_difference": first}
    if first is not None:
        before = (baseline.get("state_hashes") or baseline).get("state", {})
        after = current.get("state", {})
        result["state_differences"] = {path: {"baseline": before.get(path), "current": after.get(path)} for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)}
    return result


# ---------------------------------------------------------------- self-tests


class Checks:
    def __init__(self):
        self.failed = 0

    def expect(self, name, condition, detail=""):
        if condition:
            print(f"ok   {name}")
        else:
            print(f"FAIL {name}: {detail}")
            self.failed += 1


def _call(fn, *a):
    try:
        return fn(*a)
    except ToolError as e:
        return dict({"ok": False, "error": e.message}, **e.extra)


# A stand-in for an outside model in the self-test (B-903): writes a picture of a bumpy
# surface, or a DirectX normal map of it at half size. Standard library only.
FAKE_MODEL = r"""
import math, struct, sys, zlib
def png(path, w, h, pixel):
    raw = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))
    c = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + c(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + c(b"IDAT", zlib.compress(raw)) + c(b"IEND", b""))
def height(u, v):
    return 0.5 + 0.25 * math.sin(u * 19) * math.cos(v * 13) + 0.15 * math.sin(u * 7 + v * 5)
if sys.argv[1] == "picture":
    png(sys.argv[2], 256, 192, lambda x, y: [int(255 * min(max(height(x / 256, y / 192), 0), 1))] * 3)
else:
    W, H = 128, 96
    def normal(x, y):
        e = 1.0 / W
        dx = (height(x / W + e, y / H) - height(x / W - e, y / H)) / (2 * e) / W * 40
        dy = (height(x / W, y / H + e) - height(x / W, y / H - e)) / (2 * e) / H * 40
        n = [-dx, -dy, 1.0]  # DirectX: green is the other way.
        l = math.sqrt(sum(a * a for a in n))
        return [int(255 * (a / l * 0.5 + 0.5)) for a in n]
    png(sys.argv[3], W, H, normal)
"""


def selftest_engine():
    """The engine.sh self-test, in Python so it also runs on Windows."""
    c = Checks()
    with tempfile.TemporaryDirectory() as p:
        with open(os.path.join(p, "project.godot"), "w", encoding="utf-8") as f:
            f.write('config_version=5\n\n[application]\n\nconfig/name="engine selftest"\nrun/main_scene="res://main.tscn"\n')
            f.write('\n[input]\n\njump={\n"deadzone": 0.5,\n"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":32,"key_label":0,"unicode":32,"location":0,"echo":false,"script":null)\n]\n}\n')
        with open(os.path.join(p, "hello.gd"), "w", encoding="utf-8") as f:
            f.write('extends Node3D\nsignal poked\nfunc greet(who: String) -> String:\n\treturn "hello " + who\nfunc on_poked() -> void:\n\tpass\nfunc _ready() -> void:\n\tpush_error("selftest error from _ready")\n')
        with open(os.path.join(p, "broken.gd"), "w", encoding="utf-8") as f:
            f.write("extends Node\nfunc broken(:\n")
        e = lambda *a: _call(engine, p, list(a))  # noqa: E731
        S = ["--scene", "res://main.tscn"]
        c.expect("new", e("new", *S, "--type", "Node3D", "--name", "Main")["ok"])
        r = e("add", *S, "--parent", ".", "--type", "MeshInstance3D", "--name", "Box", "--set", '{"mesh": "BoxMesh", "position": "Vector3(0, 1, 0)"}')
        c.expect("add mesh", r["ok"] and r["node"]["type"] == "MeshInstance3D", r)
        r = e("get", *S, "--node", "Box", "--property", "position")
        c.expect("get", r.get("value") == "Vector3(0, 1, 0)", r)
        r = e("set", *S, "--node", "Box", "--property", "position", "--value", "Vector3(2, 0, -1)")
        c.expect("set", r["ok"] and r["value"] == "Vector3(2, 0, -1)", r)
        r = e("set", *S, "--node", "Box", "--property", "position:y", "--value", "3")
        c.expect("set indexed", r["ok"] and r["value"] == 3.0, r)
        c.expect("add group", e("add", *S, "--parent", ".", "--type", "Node3D", "--name", "Group")["ok"])
        r = e("reparent", *S, "--node", "Box", "--parent", "Group")
        c.expect("reparent", r["ok"] and r["node"]["path"] == "Group/Box", r)
        r = e("tree", *S)
        c.expect("tree", r["ok"] and [n["path"] for n in r["nodes"]] == [".", "Group", "Group/Box"], r)
        r = e("props", *S, "--node", "Group/Box")
        c.expect("props", r["ok"] and r["properties"]["mesh"] == {"class": "BoxMesh", "embedded": True} and r["properties"]["position"] == "Vector3(2, 3, -1)", r)
        r = e("script", *S, "--node", ".", "--path", "res://hello.gd")
        c.expect("script", r["ok"] and r["node"]["script"] == "res://hello.gd", r)
        r = e("call", *S, "--node", ".", "--method", "greet", "--args", '["agent"]')
        c.expect("call", r["ok"] and r["result"] == "hello agent", r)
        c.expect("connect", e("connect", *S, "--from", ".", "--signal", "poked", "--to", ".", "--method", "on_poked")["ok"])
        c.expect("connection saved", 'connection signal="poked"' in open(os.path.join(p, "main.tscn"), encoding="utf-8").read())
        r = e("classes", "--inherits", "Light3D")
        c.expect("classes", r["ok"] and "OmniLight3D" in r["classes"] and "Node2D" not in r["classes"], "")
        r = e("describe", "--class", "OmniLight3D")
        c.expect("describe", r["ok"] and any(x["name"] == "omni_range" for x in r["properties"]), "")
        c.expect("check good", e("check", "--path", "res://hello.gd")["ok"])
        r = e("check", "--path", "res://broken.gd")
        c.expect("check bad", not r["ok"] and r["errors"] and all(k in r["errors"][0] for k in ("file", "line", "column", "code", "message")) and r["errors"][0]["line"] > 0, r)
        r = e("run", "--frames", "5")
        c.expect("run", r["ok"] and any("selftest error from _ready" in x["message"] and x["code"].startswith("E") and x["file"] for x in r["errors"]), r)
        with open(os.path.join(p, "ref.tres"), "w", encoding="utf-8") as f:
            f.write('[gd_resource type="Resource" load_steps=2 format=3]\n\n[ext_resource type="Texture2D" path="res://missing.png" id="1"]\n\n[resource]\nmetadata/tex = ExtResource("1")\n')
        r = e("validate")
        c.expect("validate broken", not r["ok"] and {("script_error", "res://broken.gd"), ("missing_dependency", "res://ref.tres")} <= {(i["kind"], i["file"]) for i in r["issues"]} and any(x["line"] == 2 for i in r["issues"] for x in i.get("errors", [])), r)
        os.remove(os.path.join(p, "broken.gd"))
        os.remove(os.path.join(p, "ref.tres"))
        r = e("validate")
        c.expect("validate clean", r["ok"] and r["issues"] == [] and r["checked"] >= 2, r)
        r = e("actions")
        c.expect("actions", r["ok"] and [a["name"] for a in r["actions"]] == ["jump"] and r["actions"][0]["events"][0]["class"] == "InputEventKey" and "Space" in r["actions"][0]["events"][0]["text"], r)
        r = e("remove", *S, "--node", "Group/Box")
        c.expect("remove", r["ok"] and r["removed"] == "Group/Box", r)
        c.expect("bad node", not e("get", *S, "--node", "Nope", "--property", "position")["ok"])
        c.expect("bad scene", not e("tree", "--scene", "res://nope.tscn")["ok"])
        # B-802: resources, settings, input map, import settings.
        r = e("res-new", "--path", "res://mat/red.tres", "--type", "StandardMaterial3D", "--set", '{"albedo_color": "Color(1, 0, 0, 1)"}')
        c.expect("res-new", r["ok"] and os.path.exists(os.path.join(p, "mat", "red.tres")), r)
        r = e("res-set", "--path", "res://mat/red.tres", "--property", "roughness", "--value", "0.25")
        c.expect("res-set", r["ok"] and r["value"] == 0.25, r)
        r = e("res-props", "--path", "res://mat/red.tres")
        c.expect("res-props", r["ok"] and r["properties"]["albedo_color"] == "Color(1, 0, 0, 1)" and r["properties"]["roughness"] == 0.25, r)
        c.expect("res-get bad", not e("res-get", "--path", "res://mat/red.tres", "--property", "nope")["ok"])
        c.expect("res-new bad type", not e("res-new", "--path", "res://x.tres", "--type", "Node3D")["ok"])
        r = e("setting-set", "--name", "display/window/size/viewport_width", "--value", "1280")
        c.expect("setting-set", r["ok"] and e("setting-get", "--name", "display/window/size/viewport_width")["value"] == 1280, r)
        c.expect("setting kept", 'run/main_scene="res://main.tscn"' in open(os.path.join(p, "project.godot"), encoding="utf-8").read())
        r = e("action-add", "--name", "fire", "--mouse", "left", "--key", "F")
        fire = next((a for a in r.get("actions", []) if a["name"] == "fire"), {})
        c.expect("action-add", r["ok"] and [x["class"] for x in fire.get("events", [])] == ["InputEventKey", "InputEventMouseButton"], r)
        c.expect("action-add bad key", not e("action-add", "--name", "x", "--key", "NoSuchKey")["ok"])
        r = e("action-remove", "--name", "fire")
        c.expect("action-remove", r["ok"] and [a["name"] for a in r["actions"]] == ["jump"], r)
        with open(os.path.join(p, "tex.png"), "wb") as f:
            import struct
            import zlib

            raw = b"".join(b"\x00" + b"\xc8\x64\x32" * 4 for _ in range(4))
            chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)  # noqa: E731
            f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
        r = e("import")
        c.expect("import", r["ok"] and "res://tex.png" in r["imported"], r)
        r = e("import-set", "--path", "res://tex.png", "--param", "compress/mode", "--value", "2")
        c.expect("import-set", r["ok"] and e("import-get", "--path", "res://tex.png")["params"]["compress/mode"] == 2, r)
        c.expect("import-set bad", not e("import-set", "--path", "res://tex.png", "--param", "nope", "--value", "1")["ok"])
        # B-803: shaders are checked like scripts, and validate finds broken ones.
        with open(os.path.join(p, "ok.gdshader"), "w", encoding="utf-8") as f:
            f.write("shader_type spatial;\nvoid fragment() {\n\tALBEDO = vec3(1.0);\n}\n")
        c.expect("shader good", e("check", "--path", "res://ok.gdshader")["ok"])
        with open(os.path.join(p, "bad.gdshader"), "w", encoding="utf-8") as f:
            f.write("shader_type spatial;\n\nvoid fragment() {\n\tALBEDO = vec3(nope);\n}\n")
        r = e("check", "--path", "res://bad.gdshader")
        c.expect("shader bad", not r["ok"] and r["errors"][0]["line"] == 4 and r["errors"][0]["code"].startswith("SH"), r)
        r = e("validate")
        c.expect("validate shader", not r["ok"] and [(i["kind"], i["file"]) for i in r["issues"]] == [("shader_error", "res://bad.gdshader")] and r["issues"][0]["errors"][0]["line"] == 4, r)
        os.remove(os.path.join(p, "bad.gdshader"))
        # B-804: export presets and templates (the export itself needs a template; see the B-804 record).
        r = e("export-preset", "--platform", "web", "--template", "/nonexistent/web.zip")
        c.expect("export-preset", r["ok"] and r["platform"] == "Web" and r["export_path"] == "build/web/index.html", r)
        r = e("export-preset", "--platform", "linux", "--name", "Desk")
        c.expect("export-preset second", r["ok"] and [x["name"] for x in r["presets"]] == ["Web", "Desk"], r)
        r = e("export-preset", "--platform", "web", "--out", "out/index.html")
        c.expect("export-preset update", r["ok"] and len(r["presets"]) == 2 and r["presets"][0]["export_path"] == "out/index.html", r)
        c.expect("export-preset bad", not e("export-preset", "--platform", "ps9")["ok"])
        r = e("templates")
        c.expect("templates", r["ok"] and r["engine_version"] and r["presets"][0]["custom_template"] == "/nonexistent/web.zip" and not r["presets"][0]["custom_template_exists"], r)
        r = e("export", "--preset", "Nope")
        c.expect("export unknown preset", not r["ok"] and r.get("presets") == ["Web", "Desk"], r)
        # B-717: texel density of sprites, and the pixel discipline preset.
        with open(os.path.join(p, "sprites.tscn"), "w", encoding="utf-8") as f:
            f.write('[gd_scene format=3]\n\n[node name="S" type="Node3D"]\n\n'
                    '[node name="A" type="Sprite3D" parent="."]\npixel_size = 0.05\ntexture_filter = 0\n\n'
                    '[node name="B" type="Sprite3D" parent="."]\npixel_size = 0.05\ntexture_filter = 0\nscale = Vector3(1.5, 1.5, 1.5)\n\n'
                    '[node name="C" type="Sprite3D" parent="."]\npixel_size = 0.05\n')
        r = _call(look, p, ["texels", "--scene", "res://sprites.tscn"])
        c.expect("texels warns", not r["ok"] and {(w["kind"], w["node"]) for w in r["warnings"]} == {("texel_density", "B"), ("blurry_filter", "C")}, r)
        r = _call(look, p, ["pixel", "--scene", "res://sprites.tscn", "--snap"])
        c.expect("pixel preset", r["ok"] and r["texels"]["ok"] and abs(r["texel"] - 0.05) < 1e-6, r)
        r = _call(look, p, ["texels", "--scene", "res://sprites.tscn"])
        c.expect("texels clean", r["ok"] and r["warnings"] == [], r)
        # B-727: a water surface saved into the scene, and a bad option refused.
        r = _call(look, p, ["water", "--scene", "res://sprites.tscn", "--position", "0,-0.5,0", "--size", "8,4", "--deep", "#04182a", "--foam", "0.5"])
        with open(os.path.join(p, "sprites.tscn"), encoding="utf-8") as f:
            saved = f.read()
        c.expect("look water", r["ok"] and r["node"] == "Water" and r["size"] == [8, 4] and "foam_width" in saved and "hint_depth_texture" in saved, r)
        r = _call(look, p, ["water", "--scene", "res://sprites.tscn", "--deep", "blue-ish"])
        c.expect("look water bad color", not r["ok"] and "--deep" in r["error"], r)
        # Map generation (UZUWorldGen): a small island and a village into their own scenes,
        # with places to use next; a typo comes back with the closest key and builds nothing.
        r = _call(map_, p, ["nature", "--scene", "res://isle.tscn", "--spec", '{"preset": "island", "size": 64, "seed": 2}', "--set", "grass=3"])
        c.expect("map nature", r["ok"] and r["places"]["spawn"]["position"][1] > r["water_y"] and r["counts"]["grass"] > 0
                 and os.path.exists(os.path.join(p, "isle_maps", "Nature", "Terrain.res")), r)
        r = _call(map_, p, ["city", "--scene", "res://village.tscn", "--set", "preset=village", "--set", "seed=4"])
        city_r = r
        c.expect("map city", r["ok"] and r["counts"]["buildings"] > 0 and "plaza" in r["places"], r)
        # B-1507: the city's navigation mesh joins every place, and a walker (physics, collisions)
        # really gets from the spawn to the plaza and every gate.
        c.expect("map city navigation", r["ok"] and r["navigation"]["places_connected"] and r["counts"]["benches"] > 0, r)
        r = _call(map_, p, ["walk", "--scene", "res://village.tscn"])
        c.expect("map walk", r["ok"] and r["targets"] >= 3 and r["reached"] == r["targets"], r)
        # B-1219: buildings from parts with texture sets; the richness report's model quality sees it.
        c.expect("map city parts", city_r["ok"] and city_r["counts"]["parts"]["doors"] == city_r["counts"]["buildings"] and city_r["buildings_detail"]["textures"]
                 and os.path.exists(os.path.join(p, "village_maps", "City", "Roofs.res")), city_r)
        r = _call(look, p, ["rich", "--scene", "res://village.tscn", "--no-render"])
        q = r.get("model_quality", {})
        c.expect("look rich model quality", r["ok"] and q.get("pbr_coverage", 0) > 0.5 and q.get("bevel_share", 0) > 0.4 and "sharpest" in q, r)
        r = _call(map_, p, ["city", "--scene", "res://village.tscn", "--set", "preset=village"])
        c.expect("map city twice needs --replace", not r["ok"] and "--replace" in r.get("hint", ""), r)
        r = _call(map_, p, ["nature", "--scene", "res://isle2.tscn", "--set", "tress=2"])
        c.expect("map typo", not r["ok"] and r.get("key") == "tress" and '"trees"' in r.get("hint", "") and not os.path.exists(os.path.join(p, "isle2.tscn")), r)
        # B-204: the project map (a separate small project: scenes, an instanced scene, a
        # script with preload and class_name, signal connections, an autoload).
        with tempfile.TemporaryDirectory() as m:
            files = {
                "project.godot": 'config_version=5\n\n[application]\n\nrun/main_scene="res://main.tscn"\n\n[autoload]\n\nGame="*res://game.gd"\n',
                "game.gd": "extends Node\n",
                "coin.gd": 'class_name Coin\nextends Area3D\nconst SPARK = preload("res://spark.tres")\nsignal picked\n',
                "spark.tres": '[gd_resource type="StandardMaterial3D" format=3]\n\n[resource]\n',
                "coin.tscn": '[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://coin.gd" id="1"]\n\n[node name="Coin" type="Area3D"]\nscript = ExtResource("1")\n',
                "main.tscn": '[gd_scene load_steps=2 format=3]\n\n[ext_resource type="PackedScene" path="res://coin.tscn" id="1"]\n\n[node name="Main" type="Node3D"]\n\n[node name="Coin1" parent="." instance=ExtResource("1")]\n\n[connection signal="picked" from="Coin1" to="." method="_on_coin_picked"]\n',
            }
            for name, text in files.items():
                with open(os.path.join(m, name), "w", encoding="utf-8") as f:
                    f.write(text)
            r = _call(engine, m, ["map"])
            ok = r.get("ok") and r["depends_on"]["res://main.tscn"] == ["res://coin.tscn"] and r["depends_on"]["res://coin.gd"] == ["res://spark.tres"]
            ok = ok and r["used_by"]["res://coin.tscn"] == ["res://main.tscn"] and r["main_scene"] == "res://main.tscn"
            ok = ok and r["scenes"]["res://main.tscn"]["connections"] == [{"from": "Coin1", "signal": "picked", "to": ".", "method": "_on_coin_picked"}]
            ok = ok and r["scenes"]["res://main.tscn"]["instances"] == [{"node": "Coin1", "scene": "res://coin.tscn"}]
            ok = ok and r["scenes"]["res://coin.tscn"]["scripts"] == [{"node": ".", "script": "res://coin.gd"}]
            ok = ok and {"class": "Coin", "base": "Area3D", "path": "res://coin.gd"} in r["classes"] and r["autoloads"] == [{"name": "Game", "path": "res://game.gd", "singleton": True}]
            c.expect("map", ok, r)
        # B-205: UID problems are found, fixed, and validate (B-203) is clean afterwards.
        with tempfile.TemporaryDirectory() as q:
            os.makedirs(os.path.join(q, "sub"))
            taken = set()
            u = {k: new_uid(taken) for k in ("main", "child", "coin_gd", "main_gd")}
            files = {
                "project.godot": 'config_version=5\n\n[application]\n\nrun/main_scene="res://main.tscn"\n',
                "coin.gd": "extends Node3D\n", "coin.gd.uid": u["coin_gd"] + "\n",
                "main.gd": "extends Node3D\n",  # Its .uid file is missing.
                "ghost.gd.uid": "uid://abcdefg\n",  # An orphan.
                "sub/child.tscn": '[gd_scene load_steps=2 format=3 uid="%s"]\n\n[ext_resource type="Script" uid="uid://b2xstale" path="res://coin.gd" id="1"]\n\n[node name="Child" type="Node3D"]\nscript = ExtResource("1")\n' % u["child"],
                "main.tscn": '[gd_scene load_steps=3 format=3 uid="%s"]\n\n[ext_resource type="Script" uid="%s" path="res://main.gd" id="1"]\n[ext_resource type="PackedScene" uid="%s" path="res://child.tscn" id="2"]\n\n[node name="Main" type="Node3D"]\nscript = ExtResource("1")\n\n[node name="Coin" parent="." instance=ExtResource("2")]\n' % (u["main"], u["main_gd"], u["child"]),
            }
            files["main_copy.tscn"] = files["main.tscn"]  # A duplicate UID.
            for name, text in files.items():
                with open(os.path.join(q, name), "w", encoding="utf-8") as f:
                    f.write(text)
            r = _call(engine, q, ["uids"])
            kinds = sorted(i["kind"] for i in r.get("issues", []))
            c.expect("uids found", not r["ok"] and kinds == ["duplicate_uid", "missing_uid_file", "moved_path", "moved_path", "orphan_uid_file", "stale_uid"], kinds)
            c.expect("validate sees the breakage", not _call(engine, q, ["validate"])["ok"])
            r = _call(engine, q, ["uids", "--fix"])
            c.expect("uids fixed", r["ok"] and len(r["fixed"]) == 6, r)
            with open(os.path.join(q, "main.gd.uid"), encoding="utf-8") as f:
                c.expect("uid restored from references", f.read().strip() == u["main_gd"])
            r = _call(engine, q, ["validate"])
            c.expect("validate clean after uids --fix", r["ok"] and r["issues"] == [], r)
        # B-903: an outside "model" (a small script standing in for one) writes a DirectX normal
        # map at another size; map-estimate runs it and map-import fixes it.
        with tempfile.TemporaryDirectory() as q:
            with open(os.path.join(q, "project.godot"), "w", encoding="utf-8") as f:
                f.write("config_version=5\n")
            make_png = os.path.join(q, "fake_model.py")
            with open(make_png, "w", encoding="utf-8") as f:
                f.write(FAKE_MODEL)
            run([sys.executable, make_png, "picture", os.path.join(q, "pic.png")])
            with open(os.path.join(q, "estimators.json"), "w", encoding="utf-8") as f:
                json.dump({"normal": '"%s" "%s" normal {in} {out}' % (sys.executable, make_png)}, f)
            r = _call(engine, q, ["map-estimate", "--kind", "normal", "--in", "res://pic.png", "--out", "res://maps/normal.png", "--no-align"])
            found = r.get("found", {})
            c.expect("map-estimate", r.get("ok") and found.get("convention") == "directx" and any("resized" in x for x in r["changed"]) and os.path.exists(os.path.join(q, "maps", "normal.png")), r)
            r = _call(engine, q, ["map-estimate", "--kind", "depth", "--in", "res://pic.png", "--out", "res://maps/depth.png"])
            c.expect("map-estimate without a model", not r["ok"] and "no estimator" in r["error"], r)
            # B-1105: a synthesized sound effect saved as a WAV, described for an agent.
            r = _call(engine, q, ["sfx", "--preset", "coin", "--seed", "2", "--set", '{"decay": 0.4}', "--out", "res://sfx/coin.wav"])
            c.expect("sfx", r.get("ok") and os.path.getsize(os.path.join(q, "sfx", "coin.wav")) > 1000 and r["params"]["decay"] == 0.4 and r["sound"]["peak"] > 0.2 and r["sound"]["ends_silent"], r)
            r = _call(engine, q, ["sfx", "--preset", "coin", "--set", '{"decya": 1}', "--out", "res://sfx/x.wav"])
            c.expect("sfx unknown parameter", not r["ok"] and "decya" in r["error"], r)
            r = _call(engine, q, ["sfx-presets"])
            c.expect("sfx-presets", r.get("ok") and "explosion" in r["presets"] and "lowpass" in r["defaults"], r)
            # B-1108: several presets packed into ONE sprite WAV, with a JSON manifest of segments.
            r = _call(engine, q, ["sfx-sprite", "--names", "hit,jump,pickup,coin", "--gap-ms", "50", "--out", "res://sfx/sprite.wav"])
            segs = r.get("segments", {})
            manifest_ok = False
            if r.get("ok") and os.path.exists(os.path.join(q, "sfx", "sprite.json")):
                with open(os.path.join(q, "sfx", "sprite.json"), encoding="utf-8") as f:
                    saved = json.load(f)
                manifest_ok = saved["segments"] == segs and saved["total_samples"] == r["total_samples"]
            c.expect("sfx-sprite", r.get("ok") and os.path.getsize(os.path.join(q, "sfx", "sprite.wav")) > 10000 and set(segs) == {"hit", "jump", "pickup", "coin"} and segs["jump"]["start_sample"] > segs["hit"]["end_sample"] and segs["coin"]["end_sample"] == r["total_samples"] and manifest_ok, r)
            r = _call(engine, q, ["sfx-sprite", "--names", "hit,nope", "--out", "res://sfx/bad.wav"])
            c.expect("sfx-sprite unknown preset", not r["ok"] and "nope" in r["error"], r)
            # B-1109: VFX recipes validated and normalized as structured output.
            r = _call(engine, q, ["vfx", "--name", "explosion"])
            c.expect("vfx explosion", r.get("ok") and [p["type"] for p in r["parts"]] == ["debris", "sparks", "smoke", "ring", "light", "shake", "hitstop", "sfx"] and r["duration"] > 1.9, r)
            r = _call(engine, q, ["vfx", "--recipe", '{"parts": [{"type": "ring", "radius": 99}]}'])
            c.expect("vfx clamps with a warning", r.get("ok") and r["parts"][0]["radius"] == 50.0 and any("radius" in w for w in r["warnings"]), r)
            r = _call(engine, q, ["vfx", "--recipe", '{"parts": [{"type": "shockwave"}]}'])
            c.expect("vfx unknown part", not r["ok"] and "shockwave" in str(r["errors"]), r)
            r = _call(engine, q, ["vfx-recipes"])
            c.expect("vfx-recipes", r.get("ok") and "laser" in r["recipes"] and r["recipes"]["laser"]["parts"][0]["type"] == "beam", r)
            # B-1203: props scattered over a plane, saved with their transforms, the same for the same seed.
            with open(os.path.join(q, "field.tscn"), "w", encoding="utf-8") as f:
                f.write('[gd_scene format=3]\n\n[sub_resource type="PlaneMesh" id="p"]\nsize = Vector2(10, 10)\n\n[node name="F" type="Node3D"]\n\n[node name="Ground" type="MeshInstance3D" parent="."]\nmesh = SubResource("p")\n')
            r = _call(engine, q, ["scatter", "--scene", "res://field.tscn", "--surface", "Ground", "--mesh", "sphere", "--density", "2", "--seed", "5", "--exclude", '[{"center": [0, 0, 0], "radius": 2}]'])
            with open(os.path.join(q, "field.tscn"), encoding="utf-8") as f:
                field = f.read()
            c.expect("scatter", r.get("ok") and r["target"] == 200 and 0 < r["count"] < 200 and r["rejected_excluded"] > 0 and "MultiMeshInstance3D" in field and "buffer = PackedFloat32Array(" in field, r)
            r2 = _call(engine, q, ["scatter", "--scene", "res://field.tscn", "--surface", "Ground", "--mesh", "sphere", "--density", "2", "--seed", "5", "--exclude", '[{"center": [0, 0, 0], "radius": 2}]', "--name", "Again"])
            c.expect("scatter same seed", r2.get("ok") and r2["count"] == r["count"] and r2["bounds"] == r["bounds"], r2)
            r = _call(engine, q, ["scatter", "--scene", "res://field.tscn", "--surface", "Nope", "--mesh", "sphere"])
            c.expect("scatter no surface", not r["ok"] and "--surface" in r["error"], r)
            # B-1204: the richness report on that field (static part; rendering is covered by hand),
            # a budget it fails with a hint, one it passes, and a wrong budget key.
            r = rich(q, ["rich", "--scene", "res://field.tscn", "--no-render", "--budget", '{"max_triangles": 100000}'])
            c.expect("rich over budget", not r["ok"] and r["failures"][0]["metric"] == "triangles" and r["summary"]["props"] > 0 and any("low-poly" in h for h in r["hints"]), r)
            r = rich(q, ["rich", "--scene", "res://field.tscn", "--no-render", "--budget", '{"max_triangles": 10000000, "min_props_per_m2": 1}'])
            c.expect("rich within budget", r["ok"] and r["failures"] == [] and r["frame"] is None, r)
            # B-1205: LOD levels for the field's heavy spheres; the report then sees them.
            r = _call(engine, q, ["lod", "--scene", "res://field.tscn"])
            c.expect("lod", r.get("ok") and r["meshes"] and r["meshes"][0]["triangles"] > 1000 and len(r["meshes"][0]["levels"]) > 3 and r["meshes"][0]["levels"][-1] < r["meshes"][0]["triangles"] // 10, r)
            r2 = rich(q, ["rich", "--scene", "res://field.tscn", "--no-render"])
            c.expect("lod seen by rich", all(t["lods"] > 0 for t in r2["top"] if t["type"] == "MultiMeshInstance3D") and not any("without LOD" in h for h in r2["hints"]), r2)
            # B-1209: procedural PBR presets on bare models; the untextured share drops.
            with open(os.path.join(q, "hut.tscn"), "w", encoding="utf-8") as f:
                f.write('[gd_scene format=3]\n\n[sub_resource type="BoxMesh" id="b"]\n\n[sub_resource type="PlaneMesh" id="p"]\n\n'
                        '[sub_resource type="StandardMaterial3D" id="red"]\nalbedo_color = Color(0.6, 0.2, 0.15, 1)\n\n[node name="H" type="Node3D"]\n\n'
                        '[node name="Ground" type="MeshInstance3D" parent="."]\nmesh = SubResource("p")\n\n'
                        '[node name="Wall" type="MeshInstance3D" parent="."]\nmesh = SubResource("b")\n\n'
                        '[node name="Roof" type="MeshInstance3D" parent="."]\nmesh = SubResource("b")\nmaterial_override = SubResource("red")\n')
            before = rich(q, ["rich", "--scene", "res://hut.tscn", "--no-render"])["summary"]["untextured_share"]
            r = pbr_apply(q, ["--scene", "res://hut.tscn", "--assign", "Ground:grass,Wall:plaster,Roof:tile", "--size", "64"])
            after = rich(q, ["rich", "--scene", "res://hut.tscn", "--no-render"])["summary"]["untextured_share"]
            with open(os.path.join(q, "hut.tscn"), encoding="utf-8") as f:
                hut = f.read()
            c.expect("pbr", r.get("ok") and len(r["assigned"]) == 3 and sorted(r["made"]) == ["grass", "plaster", "tile"] and before == 1.0 and after == 0.0 and "uv1_triplanar = true" in hut and "res://materials/pbr/tile/normal.png" in hut, (r, before, after))
            r = _call(engine, q, ["pbr-assign", "--scene", "res://hut.tscn", "--assign", "Wall:marble"])
            c.expect("pbr unknown preset", not r["ok"] and "plaster" in r["error"], r)
            r = _call(engine, q, ["lod", "--scene", "res://field.tscn"])
            c.expect("lod again skips", r.get("ok") and r["meshes"] == [] and any("has LODs" in x["reason"] for x in r["skipped"]), r)
            try:
                rich(q, ["rich", "--scene", "res://field.tscn", "--no-render", "--budget", '{"max_polygons": 1}'])
                c.expect("rich bad budget key", False, "accepted")
            except ToolError as e:
                c.expect("rich bad budget key", "max_polygons" in str(e), str(e))
            # B-1207: a small scene from a spec (with its static report), and a spec with mistakes.
            spec = {"scene": "res://built.tscn", "look": {"quality": "low", "atmosphere": "humid"}, "ground": {"size": [20, 20], "color": "#5d7a3c"},
                    "camera": {"position": [0, 5, 12], "look_at": [0, 0, 0]}, "models": [{"mesh": "box", "name": "Hut", "position": [0, 1, 0], "scale": [3, 2, 3], "color": "#c9b28c"}],
                    "scatter": [{"name": "Stones", "mesh": "sphere", "density": 1, "seed": 4, "scale": [0.1, 0.3], "exclude": [{"center": [0, 0, 0], "radius": 3}]}],
                    "lamps": [[2, 2, 2]], "particles": [{"kind": "dust", "position": [0, 1, 0]}]}
            with open(os.path.join(q, "spec.json"), "w", encoding="utf-8") as f:
                json.dump(spec, f)
            r = build(q, ["--spec", "res://spec.json", "--no-render"])
            with open(os.path.join(q, "built.tscn"), encoding="utf-8") as f:
                built = f.read()
            c.expect("build", r.get("ok") and r["built"]["scatter"][0]["count"] > 300 and r["report"]["summary"]["props"] > 300 and all(n in built for n in ('name="Hut"', 'name="Stones"', 'type="WorldEnvironment"', 'type="Camera3D"', 'type="GPUParticles3D"')), r)
            spec["models"][0]["colour"] = "#ffffff"
            spec["scatter"][0]["on"] = "Lawn"
            spec["look"]["atmosphere"] = "foggy"
            with open(os.path.join(q, "spec.json"), "w", encoding="utf-8") as f:
                json.dump(spec, f)
            r = build(q, ["--spec", "res://spec.json", "--no-render"])
            problems = " | ".join(r.get("problems", []))
            c.expect("build spec mistakes", not r["ok"] and "models[0]: unknown key 'colour'" in problems and "scatter[0].on" in problems and "look.atmosphere" in problems, r)
            # B-1208: a richness preset on that hut scene, applied twice (the second time replaces), and an unknown preset.
            spec["models"][0].pop("colour"); spec["scatter"] = []; spec["look"] = {"quality": "low", "atmosphere": "clear"}
            with open(os.path.join(q, "spec.json"), "w", encoding="utf-8") as f:
                json.dump(spec, f)
            build(q, ["--spec", "res://spec.json", "--no-report"])
            r = enrich(q, ["--preset", "village_rich", "--scene", "res://built.tscn", "--no-render"])
            c.expect("enrich", r.get("ok") and r["diff"].get("props", 0) > 1000 and r["after"]["summary"]["lights"] >= r["before"]["summary"]["lights"] + 2 and len(r["built"]["scatter"]) == 4, r)
            r = enrich(q, ["--preset", "village_rich", "--scene", "res://built.tscn", "--no-render"])
            c.expect("enrich again replaces", r.get("ok") and r["diff"] == {}, r)
            r = enrich(q, ["--preset", "jungle", "--scene", "res://built.tscn", "--no-render"])
            c.expect("enrich unknown preset", not r["ok"] and "meadow" in r["error"], r)
            # B-1301: a UI screen from a spec, and a spec with mistakes.
            ui_spec = {"scene": "res://ui/screen.tscn", "theme": {"font_size": 18, "accent": "#d9a441"},
                       "root": {"type": "Screen", "children": [
                           {"type": "Panel", "name": "Status", "anchor": "top_left", "offset": [20, 20], "size": [240, 0], "children": [
                               {"type": "VBox", "children": [{"type": "Label", "name": "Name", "text": "Mina"}, {"type": "Bar", "name": "HP", "value": 70, "min_size": [0, 14]}]}]},
                           {"type": "Panel", "name": "Dialog", "anchor": "bottom_wide", "offset": [40, 20], "size": [0, 150], "children": [
                               {"type": "HBox", "children": [{"type": "Spacer"}, {"type": "Button", "name": "OK", "text": "OK"}]}]}]}}
            with open(os.path.join(q, "ui.json"), "w", encoding="utf-8") as f:
                json.dump(ui_spec, f)
            r = ui(q, ["--spec", "res://ui.json"])
            with open(os.path.join(q, "ui", "screen.tscn"), encoding="utf-8") as f:
                screen = f.read()
            c.expect("ui", r.get("ok") and r["nodes"].get("Panel") == 2 and all(n in screen for n in ('name="Status"', 'name="HP"', 'name="OK"', "StyleBoxFlat", "anchor_top = 1.0")), r)
            ui_spec["root"]["children"][0]["anchor"] = "middle"
            ui_spec["root"]["children"][1]["children"][0]["children"][1]["txt"] = "OK"
            ui_spec["root"]["children"][0]["children"][0]["children"][0]["offset"] = [1, 1]
            with open(os.path.join(q, "ui.json"), "w", encoding="utf-8") as f:
                json.dump(ui_spec, f)
            r = ui(q, ["--spec", "res://ui.json"])
            problems = " | ".join(r.get("problems", []))
            c.expect("ui spec mistakes", not r["ok"] and "root.children[0].anchor" in problems and "unknown key 'txt' for Button" in problems and "inside a container" in problems, r)
            # B-1303: a genre theme over the spec, an unknown theme, the text a font subset needs,
            # and (when fontTools is installed) the subset itself.
            ui_spec["root"]["children"][0]["anchor"] = "top_left"
            ui_spec["root"]["children"][1]["children"][0]["children"][1].pop("txt")
            ui_spec["root"]["children"][0]["children"][0]["children"][0].pop("offset")
            ui_spec["root"]["children"][0]["children"][0]["children"][0]["text"] = "ミナ Lv.7"
            with open(os.path.join(q, "ui.json"), "w", encoding="utf-8") as f:
                json.dump(ui_spec, f, ensure_ascii=False)
            r = ui(q, ["--spec", "res://ui.json", "--theme", "sf"])
            with open(os.path.join(q, "ui", "screen.tscn"), encoding="utf-8") as f:
                screen = f.read()
            c.expect("ui theme", r.get("ok") and r["theme"] == "sf" and "0.2196078" in screen, r)  # The sf accent, #38e1ff, in the bar fill.
            r = ui(q, ["--spec", "res://ui.json", "--theme", "steampunk"])
            c.expect("ui unknown theme", not r["ok"] and "wafu" in r["error"], r)
            import ui_font
            c.expect("ui font text", set(ui_font.spec_text(ui_spec)) >= {"ミナ Lv.7", "OK"}, ui_font.spec_text(ui_spec))
            try:
                import fontTools  # noqa: F401
                import brotli  # noqa: F401
                r = ui(q, ["--spec", "res://ui.json", "--font-subset"])
                c.expect("ui font subset", r.get("ok") and r["fonts"]["ok"] and r["fonts"]["size_kb"] < 100 and os.path.exists(os.path.join(q, "fonts", "screen_ja.woff2")), r)
            except ImportError:
                print("skip ui font subset (no fonttools/brotli)")
            # B-1307: one parameter switches the world; the game parts are saved with their variations.
            world_spec = {"scene": "res://ui/world.tscn", "root": {"type": "Screen", "children": [
                {"type": "Ribbon", "anchor": "top", "offset": [0, 20], "size": [300, 0], "text": "Title"},
                {"type": "Panel", "anchor": "top_left", "offset": [20, 20], "size": [260, 0], "children": [{"type": "VBox", "children": [
                    {"type": "Gauge", "value": 50, "segments": 8}, {"type": "Slot", "text": "A", "count": 2}, {"type": "Separator"}]}]},
                {"type": "Talk", "anchor": "bottom_wide", "offset": [30, 20], "size": [0, 160], "speaker": "Elder", "text": "Hello."}]}}
            with open(os.path.join(q, "world.json"), "w", encoding="utf-8") as f:
                json.dump(world_spec, f)
            saved = {}
            for world in ("fantasy", "sf"):
                r = ui(q, ["--spec", "res://world.json", "--world", world])
                with open(os.path.join(q, "ui", "world.tscn"), encoding="utf-8") as f:
                    saved[world] = f.read()
                c.expect(f"ui world {world}", r.get("ok") and r["world"] == world and all(v in saved[world] for v in ('"UZUGauge"', '"UZUTalk"', '"UZUSlot"', '"UZURibbon"', 'name="NameTag"')), r)
            c.expect("ui worlds differ", saved["fantasy"] != saved["sf"])
            # B-1307 stage 2: the world screen carries its motion node, and the UI report sees it move.
            c.expect("ui world motion node", 'type="UZUUIWorld"' in saved["sf"] and 'world = "sf"' in saved["sf"], saved["sf"][-400:])
            r = ui_report(q, ["--scene", "res://ui/world.tscn", "--frames", "20"])
            mo = r.get("motion", {})
            c.expect("ui-report motion", mo.get("moving_frames", 0) >= 3 and mo.get("worlds") and mo["worlds"][0]["opened"] >= 2 and any(k.startswith("open") for k in mo.get("events", {})) and not any(p["kind"] == "overlap" for p in r["problems"]), r)
            r = ui(q, ["--spec", "res://world.json", "--world", "steampunk"])
            c.expect("ui unknown world", not r["ok"] and "theme.world" in " ".join(r.get("problems", [])), r)
            # B-1305: the UI report finds the problems of a deliberately poor screen, and none of
            # them on the styled screen built above.
            shutil.copyfile(os.path.join(HERE, "look_samples", "specs", "poor_ui.tscn"), os.path.join(q, "ui", "poor.tscn"))
            r = ui_report(q, ["--scene", "res://ui/poor.tscn"])
            kinds = {p["kind"] for p in r["problems"]}
            c.expect("ui-report poor", not r["ok"] and r["screen"] == [1280, 720] and kinds >= {"small_text", "small_button", "no_margin", "overlap", "text_overflow", "unstyled"}, r)
            r = ui_report(q, ["--scene", "res://ui/screen.tscn"])
            c.expect("ui-report styled", r["summary"]["panels"] == 2 and r["summary"]["unstyled"] == 0 and not {"unstyled", "overlap", "no_margin", "off_screen"} & {p["kind"] for p in r["problems"]}, r)
        r = _call(look, p, ["info"])
        c.expect("look info", r["ok"] and "apply" in r["commands"], r)
    print("engine selftest: " + ("ok" if not c.failed else "FAILED"))
    return c.failed == 0


def selftest_selfplay():
    """The selfplay.sh self-test: same input, same play; seeds fix the random numbers."""
    game = os.path.join(HERE, "selfplay", "sample_game")
    replay = os.path.join(HERE, "selfplay", "sample_replay.json")
    with tempfile.TemporaryDirectory() as work:
        a = selfplay(game, ["--input", replay, "--frames", "600"])
        b = selfplay(game, ["--input", replay, "--frames", "600"])
        no_jump = os.path.join(work, "no_jump.json")
        with open(no_jump, "w") as f:
            f.write('{"events": [{"frame": 0, "action": "move_right", "pressed": true}]}\n')
        c = selfplay(game, ["--input", no_jump, "--frames", "600"])

        def main_items(r):
            rep = dict(r["report"])
            rep.pop("fps")  # Wall-clock speed differs between runs; nothing else may.
            return dict({k: r[k] for k in ("ok", "cleared", "checkpoints", "deaths", "frames", "errors")}, report=rep)

        assert a["ok"] and a["cleared"] and a["checkpoints"] == ["cp1", "cp2", "cp3"] and a["deaths"] == 1, a
        assert isinstance(a["fps"], (int, float)) and a["fps"] > 0, a
        assert main_items(a) == main_items(b), (main_items(a), main_items(b))
        assert not c["cleared"] and c["deaths"] > 1 and c["checkpoints"] == ["cp1"], c
        assert c["report"]["stuck_points"] and c["report"]["stuck_points"][0]["deaths"] == c["deaths"], c
        rand = os.path.join(work, "random_game")
        os.makedirs(rand)
        with open(os.path.join(rand, "project.godot"), "w") as f:
            f.write('config_version=5\n\n[application]\n\nrun/main_scene="res://main.tscn"\n')
        with open(os.path.join(rand, "main.tscn"), "w") as f:
            f.write('[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://main.gd" id="1"]\n\n[node name="Main" type="Node"]\nscript = ExtResource("1")\n')
        with open(os.path.join(rand, "main.gd"), "w") as f:
            f.write('extends Node\n\nfunc _ready() -> void:\n\tget_node("/root/UZUTelemetry").checkpoint("r%d" % (randi() % 1000000))\n')
        # B-307: state hashes. The same input gives the same hashes; a behavior change
        # (a faster player) changes them, and the comparison names the first frame and the state.
        h1 = selfplay(game, ["--input", replay, "--frames", "600", "--hash-every", "30", "--out", os.path.join(work, "h1.json")])
        assert h1["state_hashes"]["hashes"] and "/root/Main" in h1["state_hashes"]["state"], h1["state_hashes"]
        h2 = selfplay(game, ["--input", replay, "--frames", "600", "--hash-every", "30", "--compare", os.path.join(work, "h1.json")])
        assert h2["ok"] and h2["comparison"]["same"] and h2["comparison"]["compared_frames"] >= 5, h2["comparison"]
        changed = os.path.join(work, "changed_game")
        shutil.copytree(game, changed)
        with open(os.path.join(changed, "main.gd"), encoding="utf-8") as f:
            code = f.read()
        with open(os.path.join(changed, "main.gd"), "w", encoding="utf-8") as f:
            f.write(code.replace("const SPEED := 4.0", "const SPEED := 4.2"))
        h3 = selfplay(changed, ["--input", replay, "--frames", "600", "--hash-every", "30", "--compare", os.path.join(work, "h1.json")])
        assert not h3["ok"] and not h3["comparison"]["same"] and h3["comparison"]["first_difference"] == 30, h3["comparison"]
        assert h3["comparison"]["state_differences"], h3["comparison"]
        # B-308: a failure packet. A game that breaks at the second checkpoint: the packet
        # alone names the script and line, and holds a frame, the state and the replay.
        broken = os.path.join(work, "broken_game")
        shutil.copytree(game, broken)
        with open(os.path.join(broken, "main.gd"), encoding="utf-8") as f:
            lines = f.read().split("\n")
        at = next(i for i, l in enumerate(lines) if '_telemetry("checkpoint", CHECKPOINTS[cx])' in l)
        indent = lines[at][: len(lines[at]) - len(lines[at].lstrip())]
        lines[at + 1 : at + 1] = [indent + 'if CHECKPOINTS[cx] == "cp2":', indent + "\tvar broken_list := []", indent + "\tprint(broken_list[3])"]
        with open(os.path.join(broken, "main.gd"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        bad_line = at + 4  # 1-based line of print(broken_list[3]).
        packet_dir = os.path.join(work, "packet")
        p = selfplay(broken, ["--input", replay, "--frames", "600", "--packet", packet_dir, "--expect-clear"])
        assert not p["ok"] and p["packet"]["reason"] == "error", p.get("packet")
        with open(os.path.join(packet_dir, "packet.json"), encoding="utf-8") as f:
            pk = json.load(f)
        assert pk["where"] == {"file": "res://main.gd", "line": bad_line, "function": "_physics_process"}, pk["where"]
        # The state at the failure: just at the second checkpoint (the game itself plays on after a script error).
        assert "cp2" in pk["checkpoints"] and pk["state"]["/root/Main"]["respawn_x"] == "500.0", pk["state"]
        assert pk["screenshot"] in (None, "failure.png")
        assert os.path.exists(os.path.join(packet_dir, "replay.json")) and os.path.exists(os.path.join(packet_dir, "errors.jsonl"))
        assert pk["rerun"][:3] == ["python3", "ai_loop/uzu.py", "selfplay"]
        assert "packet" not in selfplay(game, ["--input", replay, "--frames", "600", "--packet", os.path.join(work, "none")]), "no packet when nothing fails"
        s1, s1b, s2 = (selfplay(rand, ["--input", no_jump, "--frames", "5", "--seed", s])["checkpoints"] for s in ("1", "1", "2"))
        assert s1 == s1b and s1 != s2 and len(s1) == 1, (s1, s1b, s2)
    print("selfplay selftest: ok")
    return True


BAKE_SCENE = """[gd_scene load_steps=4 format=3]

[sub_resource type="PlaneMesh" id="1"]
size = Vector2(8, 8)

[sub_resource type="BoxMesh" id="2"]

[sub_resource type="Environment" id="3"]
background_mode = 1
background_color = Color(0.4, 0.5, 0.7, 1)

[node name="Level" type="Node3D"]

[node name="Floor" type="MeshInstance3D" parent="."]
mesh = SubResource("1")

[node name="Box" type="MeshInstance3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.5, 0)
mesh = SubResource("2")

[node name="Sun" type="DirectionalLight3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 0.5, 0.866, 0, -0.866, 0.5, 0, 4, 0)
light_bake_mode = 2

[node name="WorldEnvironment" type="WorldEnvironment" parent="."]
environment = SubResource("3")

[node name="LightmapGI" type="LightmapGI" parent="."]
quality = 0
bounces = 1
"""


def selftest_bake():
    """Lightmap baking (B-805): runs the editor with a renderer, so it is slow and not part of 'all'."""
    with tempfile.TemporaryDirectory() as p:
        original = 'config_version=5\n\n[application]\n\nconfig/name="bake selftest"\nrun/main_scene="res://level.tscn"\n'
        with open(os.path.join(p, "project.godot"), "w", encoding="utf-8") as f:
            f.write(original)
        with open(os.path.join(p, "level.tscn"), "w", encoding="utf-8") as f:
            f.write(BAKE_SCENE)
        r = bake(p, "res://level.tscn", prepare=True)
        assert r["ok"] and r["error"] == "BAKE_ERROR_OK" and r["prepared"] == 2 and r["light_data"].endswith("level.lmbake"), r
        assert os.path.exists(os.path.join(p, "level.lmbake")) and glob.glob(os.path.join(p, "level*.exr")), os.listdir(p)
        text = open(os.path.join(p, "level.tscn"), encoding="utf-8").read()
        assert "level.lmbake" in text and "add_uv2 = true" in text, text
        assert open(os.path.join(p, "project.godot"), encoding="utf-8").read() == original, "project.godot must be restored"
        assert not os.path.exists(os.path.join(p, "addons", "uzu_bake")), "the plugin must be removed"
        # Without a LightmapGI: a clear error, and the project is still restored.
        with open(os.path.join(p, "empty.tscn"), "w", encoding="utf-8") as f:
            f.write('[gd_scene format=3]\n\n[node name="E" type="Node3D"]\n')
        r = bake(p, "res://empty.tscn")
        assert not r["ok"] and "LightmapGI" in r["error"], r
        assert open(os.path.join(p, "project.godot"), encoding="utf-8").read() == original
    print("bake selftest: ok")
    return True


def selftest_tools():
    """The self-tests of the Python tools; each runs in its own interpreter."""
    tools = ["mcp_server.py", "bench.py", "prepublish.py", "aiplayer.py", "telemetry/report.py", "feedback/to_backlog.py", "bridge/mock_server.py", "bridge/client.py"]
    commands = [(tool, ["--self-test"]) for tool in tools]
    commands.append(("tests/test_dialogue.py", []))
    commands.append(("tests/test_spec_set.py", []))
    commands.append(("tests/test_walk_graph.py", []))
    commands.append(("tests/test_audit_scene.py", []))
    commands.append(("tests/test_collision_check.py", []))
    commands.append(("tests/test_image_scene.py", []))
    commands.append(("tests/test_spec_diff.py", []))
    commands.append(("tests/test_animation.py", []))
    commands.append(("tests/test_audio_check.py", []))
    commands.append(("tests/test_ui_quality.py", []))
    commands.append(("tests/test_font_locale_check.py", []))
    commands.append(("tests/test_feel_report.py", []))
    ok = True
    for tool, args in commands:
        rc, out = run([sys.executable, os.path.join(HERE, tool), *args], timeout=900)
        print(("ok   " if rc == 0 else "FAIL ") + tool + ("" if rc == 0 else ": " + tail(out, 8)))
        ok = ok and rc == 0
    print("tools selftest: " + ("ok" if ok else "FAILED"))
    return ok


def selftest(which):
    steps = {"engine": selftest_engine, "selfplay": selftest_selfplay, "tools": selftest_tools, "bake": selftest_bake}
    names = ["engine", "selfplay", "tools"] if which == "all" else [which]  # bake is slow: run it on its own.
    ok = True
    for name in names:
        try:
            ok = steps[name]() and ok
        except (AssertionError, ToolError) as e:
            print(f"{name} selftest: FAILED: {e}")
            ok = False
    return 0 if ok else 1


# ---------------------------------------------------------------- main


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # Windows consoles default to a local code page.
        except (AttributeError, ValueError):
            pass
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 2
    tool, rest = argv[0], argv[1:]
    if tool == "dialogue":
        import dialogue

        return dialogue.main(rest)
    if tool == "feel-report":
        import feel_report

        return feel_report.main(rest)
    if tool == "replay-compare":
        import replay_compare

        return replay_compare.main(rest)
    if tool == "audio-check":
        import audio_check

        return audio_check.main(rest)
    if tool == "ui-quality":
        import ui_quality

        return ui_quality.main(rest)
    if tool == "font-locale-check":
        import font_locale_check

        return font_locale_check.main(rest)
    if tool == "catalog":
        import catalog

        return catalog.main(rest)
    if tool == "caps":
        import agent_caps

        return agent_caps.main(rest)
    if tool == "texture-route":
        import texture_route

        return texture_route.main(rest)
    if tool == "building":
        import building_recipe

        return building_recipe.main(rest)
    if tool == "rock":
        import rock_recipe

        return rock_recipe.main(rest)
    if tool == "selftest":
        return selftest(rest[0] if rest else "all")
    if tool == "picture":
        from prototypes.picture import picture

        return picture.main(rest)
    if tool == "publish":
        sys.path.insert(0, os.path.join(HERE, "bridge"))
        import client

        return client.main(["publish"] + rest)
    if tool == "map" and (not rest or rest[0] == "options"):
        try:
            result = map_options()
        except ToolError as e:
            result = {"ok": False, "error": e.message}
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if tool not in ("engine", "look", "selfplay", "build", "enrich", "ui", "map", "audit-scene", "collision-check", "image-scene", "spec-diff", "anim") or not rest:
        print(__doc__, file=sys.stderr)
        return 2
    project = os.path.abspath(rest[0])
    if not os.path.exists(os.path.join(project, "project.godot")):
        print(json.dumps({"ok": False, "error": f"{rest[0]} is not a project (no project.godot)"}))
        return 2
    try:
        result = {"engine": engine, "look": look, "selfplay": selfplay, "build": build, "enrich": enrich, "ui": ui, "map": map_, "audit-scene": audit_scene_cmd, "collision-check": collision_check_cmd, "image-scene": image_scene_cmd, "spec-diff": spec_diff_cmd, "anim": animation_cmd}[tool](project, rest[1:])
    except ToolError as e:
        result = {"ok": False, "error": e.message, **e.extra}
        print(json.dumps(result, ensure_ascii=False))
        return e.code
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
