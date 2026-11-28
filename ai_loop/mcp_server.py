#!/usr/bin/env python3
"""MCP server for U.ZU Engine (BACKLOG B-402): engine and look operations as tools.

Speaks the Model Context Protocol over stdio (JSON-RPC 2.0, one message per
line) and runs ai_loop/uzu.py (engine and look) for each tool call, so an
MCP client (for example Claude Code) can operate a project directly.

Usage: ai_loop/mcp_server.py --project <project-dir>
       ai_loop/mcp_server.py --self-test

Register with Claude Code, for example:
  claude mcp add uzu-engine -- python3 /path/to/ai_loop/mcp_server.py --project /path/to/game
Standard library only.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(HERE, "skills")
PROTOCOL_VERSION = "2025-06-18"
DISCOVER_PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "uzu-engine", "version": "0.1"}
CAPABILITIES = {
    "tools": {},
    "resources": {},
    "extensions": {"io.modelcontextprotocol/skills": {}},
}


def _str(description):
    return {"type": "string", "description": description}


SCENE = _str("Scene path, e.g. res://main.tscn")
NODE = _str('Node path relative to the scene root ("." is the root)')

# name: (script, command, description, properties, required)
TOOLS = {
    "animation_motion": (
        "anim", "motion", "Generate looping idle, walk and run clips for a rigged model and report clip lengths and loop seams.",
        {"model": _str("Imported rigged model path"), "out": _str("New .tscn path"), "bones": _str("Optional JSON file of bone overrides"),
         "speed": _str("Playback rate multiplier"), "stride": _str("Limb swing multiplier"), "weight": _str("0 to 1 body weight feel")},
        ["model", "out"],
    ),
    "animation_align": (
        "anim", "align", "Align transparent PNG sprite frames to a common canvas and bottom-center anchor without resampling.",
        {"frames-dir": _str("Input PNG directory"), "out": _str("New output directory")}, ["frames-dir", "out"],
    ),
    "dialogue_validate": (
        "dialogue",
        "",
        "Validate a dialogue and quest-flag graph. Report unreachable nodes, missing branches, flag errors and text lengths. Optionally write the verified graph.",
        {
            "spec": _str("Dialogue source JSON path"),
            "out": _str("Optional validated JSON output path"),
            "max-chars": _str("Character budget per text field (default 160)"),
        },
        ["spec"],
    ),
    "sfx_generate": (
        "sfx-lumina",
        "",
        "Search, render, and place Lumina SFX WAV files into the Godot project from a uzu-sfx-request/1 JSON file.",
        {
            "request": _str("Path to uzu-sfx-request/1 JSON file"),
            "lumina-dir": _str("Optional path to Lumina skill directory (overrides UZU_LUMINA_DIR)"),
            "dest": _str("Optional destination res:// directory overriding request.dest"),
        },
        ["request"],
    ),
    "catalog_search": ("catalog", "", "Search the feature catalog (BACKLOG B-403): every uzu.py command, MCP tool, preset, tool script and UZU class with its description, tags and place of implementation, generated from their definitions. Use it to discover what the agent tools can do before reading the docs.", {"query": _str("Keyword(s); every word must match an entry's name, description or tags"), "caps": _str("Agent capability profile (BACKLOG B-404): comma-separated names (image_gen, gpu, blender, browser); matches are annotated with the capabilities the profile is missing"), "profile": _str("Path to a JSON capability profile file (BACKLOG B-404)")}, ["query"]),
    "replay_compare": ("replay-compare", "", "Compare replay JSON or JSONL and report the first differing field. Snapshots matches expected fields at each frame or time.", {"expected": _str("Expected log or snapshot file path"), "actual": _str("Actual log file path"), "snapshots": {"type": "boolean"}}, ["expected", "actual"]),
    "scene_new": ("engine", "new", "Create a new scene file with a root node.", {"scene": SCENE, "type": _str("Root node class, e.g. Node3D"), "name": _str("Root node name")}, ["scene"]),
    "scene_tree": ("engine", "tree", "List the nodes of a scene with their types and scripts.", {"scene": SCENE, "depth": _str("Maximum depth (optional)")}, ["scene"]),
    "node_props": ("engine", "props", "List a node's inspector properties and their values.", {"scene": SCENE, "node": NODE}, ["scene", "node"]),
    "node_get": ("engine", "get", "Read a node property (supports indexed paths like position:y).", {"scene": SCENE, "node": NODE, "property": _str("Property name")}, ["scene", "node", "property"]),
    "node_set": ("engine", "set", 'Set a node property and save. Values use Godot text format: 1.5, "text", Vector3(1, 2, 3); res:// paths load resources; resource class names (BoxMesh) create one.', {"scene": SCENE, "node": NODE, "property": _str("Property name"), "value": _str("Value in Godot text format")}, ["scene", "node", "property", "value"]),
    "node_add": ("engine", "add", "Add a node of a class under a parent and save; 'set' is a JSON object of initial property values.", {"scene": SCENE, "parent": NODE, "type": _str("Node class"), "name": _str("Node name"), "set": _str('JSON object, e.g. {"mesh": "BoxMesh", "position": "Vector3(0, 1, 0)"}')}, ["scene", "type"]),
    "scatter": ("engine", "scatter", "Spread props (stones, tufts, flowers) over a surface node as one MultiMesh and save: even by area, the same layout for the same seed, filtered by slope, exclusion zones and spacing. Returns how many, where (bounds) and why some were rejected.", {"scene": SCENE, "surface": _str("The MeshInstance3D to scatter on, e.g. Ground"), "mesh": _str("box | sphere | cylinder | capsule | prism, or res:// mesh or scene (GLB)"), "material": _str("res:// material for the props"), "density": _str("Props per square meter (1)"), "seed": _str("Layout seed (1)"), "scale": _str("min,max scale (0.8,1.2)"), "align": _str("0..1, how much props lean with the surface (0)"), "max-slope": _str("Degrees; steeper ground gets none (90)"), "min-distance": _str("Meters between props (0)"), "sink": _str("Meters pushed into the ground (0)"), "max-count": _str("Upper limit (100000)"), "exclude": _str('JSON array of zones: [{"center": [x, y, z], "radius": r}, {"aabb": [x, y, z, sx, sy, sz]}]'), "name": _str("Node name (Scatter)"), "no-yaw": {"type": "boolean", "description": "Do not turn props randomly"}}, ["scene", "surface", "mesh"]),
    "lod": ("engine", "lod", "Add distance LOD levels to a scene's heavy meshes (MeshInstance3D and MultiMesh, simplified by meshoptimizer; the renderer picks a level by on-screen size) and save. Returns triangles per level; --imports also turns on LOD generation for imported 3D models.", {"scene": SCENE, "node": NODE, "min-triangles": _str("Only meshes with at least this many triangles (300)"), "merge-angle": _str("Normal merge angle in degrees (25)"), "split-angle": _str("Normal split angle in degrees (60)"), "imports": {"type": "boolean", "description": "Also enable LODs in the project's model imports"}}, ["scene"]),
    "pbr_presets_apply": ("look", "pbr", "Give bare models procedural PBR materials (wood, stone, brick, dirt, grass, plaster, tile: seamless textures made here, then albedo/normal/ORM), triplanar and tinted by each model's own color; untextured models look cheap.", {"scene": SCENE, "assign": _str("Rules 'NodePattern:preset,...', e.g. House*:plaster,Roof*:tile,Ground:grass"), "scale": _str("Texture repeats per meter (0.5)"), "size": _str("Texture size in pixels (256)"), "no-tint": {"type": "boolean", "description": "Do not tint by the model's color"}}, ["scene", "assign"]),
    "node_instance": ("engine", "instance", "Instance another scene under a parent and save.", {"scene": SCENE, "parent": NODE, "path": _str("Scene to instance, res://..."), "name": _str("Node name")}, ["scene", "path"]),
    "node_remove": ("engine", "remove", "Remove a node (not the root) and save.", {"scene": SCENE, "node": NODE}, ["scene", "node"]),
    "node_reparent": ("engine", "reparent", "Move a node under another parent and save.", {"scene": SCENE, "node": NODE, "parent": NODE}, ["scene", "node", "parent"]),
    "node_call": ("engine", "call", "Call a method on a node and return the result; 'args' is an array in Godot text format.", {"scene": SCENE, "node": NODE, "method": _str("Method name"), "args": _str('e.g. [1, "a"]')}, ["scene", "node", "method"]),
    "signal_connect": ("engine", "connect", "Connect a signal to a method persistently and save.", {"scene": SCENE, "from": NODE, "signal": _str("Signal name"), "to": NODE, "method": _str("Method name")}, ["scene", "from", "signal", "to", "method"]),
    "script_attach": ("engine", "script", "Attach a script to a node and save.", {"scene": SCENE, "node": NODE, "path": _str("Script path, res://...")}, ["scene", "node", "path"]),
    "script_check": ("engine", "check", "Check a GDScript, .gdshader or .gdshaderinc file without a renderer; returns errors and warnings with file, line, column, code and message.", {"path": _str("Script path, res://...")}, ["path"]),
    "class_list": ("engine", "classes", "List engine classes, optionally only those inheriting a class.", {"inherits": _str("Base class (optional)")}, []),
    "class_describe": ("engine", "describe", "Describe a class: properties, methods, signals and constants.", {"class": _str("Class name")}, ["class"]),
    "project_run": ("engine", "run", "Run the project headless for some frames; returns errors and the log tail.", {"frames": _str("Frames to run (default 120)")}, []),
    "input_actions": ("engine", "actions", "List the project's input actions (InputMap) and their key/button events.", {}, []),
 "resource_new": ("engine", "res-new", "Create a resource file (.tres) of a class, with optional initial values.", {"path": _str("res://path.tres"), "type": _str("Resource class, e.g. StandardMaterial3D"), "set": _str('JSON object of values in Godot text format')}, ["path", "type"]),
    "resource_props": ("engine", "res-props", "List a resource file's inspector properties and values.", {"path": _str("res://path.tres")}, ["path"]),
    "resource_get": ("engine", "res-get", "Read a property of a resource file.", {"path": _str("res://path.tres"), "property": _str("Property name")}, ["path", "property"]),
    "resource_set": ("engine", "res-set", "Set a property of a resource file and save.", {"path": _str("res://path.tres"), "property": _str("Property name"), "value": _str("Value in Godot text format")}, ["path", "property", "value"]),
    "setting_get": ("engine", "setting-get", "Read a project setting.", {"name": _str("Setting path, e.g. application/config/name")}, ["name"]),
    "setting_set": ("engine", "setting-set", "Change a project setting and save project.godot.", {"name": _str("Setting path"), "value": _str("Value in Godot text format")}, ["name", "value"]),
    "action_add": ("engine", "action-add", "Add an input action or add events to it (key, mouse button, joypad button).", {"name": _str("Action name"), "key": _str("Key name, e.g. Space"), "mouse": _str("left | right | middle | wheel_up | wheel_down"), "joy-button": _str("Joypad button index"), "deadzone": _str("Deadzone"), "replace": {"type": "boolean", "description": "Replace the existing events"}}, ["name"]),
    "action_remove": ("engine", "action-remove", "Remove an input action.", {"name": _str("Action name")}, ["name"]),
    "assets_import": ("engine", "import", "Import (or reimport) the project's assets: textures, sounds, models.", {}, []),
    "import_get": ("engine", "import-get", "Read an asset's import settings.", {"path": _str("res://asset path")}, ["path"]),
    "import_set": ("engine", "import-set", "Change one import setting of an asset and reimport it.", {"path": _str("res://asset path"), "param": _str("Import parameter, e.g. compress/mode"), "value": _str("Value")}, ["path", "param", "value"]),
    "export_preset": ("engine", "export-preset", "Create or update an export preset (export_presets.cfg).", {"platform": _str("web | linux | windows | macos | android"), "name": _str("Preset name"), "out": _str("Export path, relative to the project"), "template": _str("Custom export template zip (absolute path)")}, ["platform"]),
    "export_presets": ("engine", "presets", "List the project's export presets.", {}, []),
    "export_templates": ("engine", "templates", "Where export templates are looked for, which are installed, and the presets' custom templates.", {}, []),
    "project_export": ("engine", "export", "Export the project with a preset; lists the files written.", {"preset": _str("Preset name"), "out": _str("Output file (default: the preset's path)")}, ["preset"]),
    "frame_benchmark": ("bench", "run", "Measure runtime frame work average/p95/worst and startup times in a project copy. Marks are in seconds. Headless measures CPU work; render also measures wall time.", {"frames": _str("Run frames, at least 12 including 10 warmup frames (default 60)"), "repeat": _str("Measured runs (default 3), plus one discarded warmup run"), "render": {"type": "boolean", "description": "Include rendering using the existing rendering setup"}}, []),
    "project_map": ("engine", "map", "A static map of the project for understanding it: files by kind, dependencies both ways (incl. preload/extends), scenes with nodes, scripts, instanced scenes and signal connections, autoloads, global classes.", {}, []),
    "project_uids": ("engine", "uids", "Check UIDs against the files: duplicates, missing or orphan .uid files, references whose UID is stale or whose path moved; each with a proposed fix. 'fix' applies them.", {"fix": {"type": "boolean", "description": "Apply the fixes"}}, []),
    "map_import": ("engine", "map-import", "Bring in a normal or depth map made by an outside model: fixes size, offset, DirectX vs OpenGL, vector length, white = near or far and range against the picture, and reports what it changed.", {"kind": _str("normal | depth"), "in": _str("The model's map, res://..."), "for": _str("The picture, res://..."), "out": _str("Output PNG, res://..."), "depth-kind": _str("auto | disparity | linear"), "no-align": {"type": "boolean", "description": "Skip the offset search"}}, ["kind", "in", "for", "out"]),
    "map_estimate": ("engine", "map-estimate", "Run the outside model configured in estimators.json for a picture, then map_import its output. No model ships with the engine.", {"kind": _str("normal | depth"), "in": _str("The picture, res://..."), "out": _str("Output PNG, res://..."), "config": _str("Estimator config (default res://estimators.json)"), "depth-kind": _str("auto | disparity | linear"), "no-align": {"type": "boolean", "description": "Skip the offset search"}}, ["kind", "in", "out"]),
    "sfx_make": ("engine", "sfx", "Synthesize a sound effect (no sound files needed) and save it as a WAV: a preset (hit, jump, pickup, coin, explosion, laser, powerup, blip, land), varied by seed, with parameters changed by set. Returns its length, peak, loudness and pitch at the start and end, so you can judge it without listening.", {"out": _str("Output WAV, res://..."), "preset": _str("hit | jump | pickup | coin | explosion | laser | powerup | blip | land"), "seed": _str("Variation of the preset (0 = as is)"), "set": _str('JSON object of parameters to change, e.g. {"decay": 0.3, "frequency": 600}')}, ["out"]),
    "sfx_presets": ("engine", "sfx-presets", "List the sound effect presets with their parameters, and every parameter with its default.", {}, []),
    "sfx_sprite": ("engine", "sfx-sprite", "Pack several preset sound effects into ONE audio sprite WAV plus a JSON manifest of segments (name -> start/length in samples and seconds), so a game ships and loads one audio file instead of many. Play one segment in code with UZUSfx.play_sprite(parent, sprite, manifest, name). Returns the manifest, the totals and a description of the packed sound.", {"out": _str("Output WAV, res://..."), "names": _str("Comma-separated presets, e.g. hit,jump,pickup,coin (default)"), "gap-ms": _str("Silence between sounds in milliseconds (default 50)"), "seed": _str("Variation of the presets (0 = as is)"), "manifest-out": _str("Manifest JSON path (default: the WAV path with .json)")}, ["out"]),
    "vfx_describe": ("engine", "vfx", "Validate and normalize a visual-effect recipe (BACKLOG B-1109): parts (sparks, smoke, debris, ring, beam, light, shake, hitstop, kick, sfx) with every parameter filled in, out-of-range values clamped (listed as warnings), unknown parts rejected, and the total duration. Give a built-in name (explosion, laser) or a full recipe JSON. Fire a recipe in code with UZUVfx.fire / fire_named.", {"name": _str("Built-in recipe: explosion | laser"), "recipe": _str('Recipe JSON object, e.g. {"name": "pop", "parts": [{"type": "ring", "radius": 4}, {"type": "sfx", "preset": "hit"}]}')}, []),
    "vfx_recipes": ("engine", "vfx-recipes", "List the built-in visual-effect recipes (explosion, laser), each validated and normalized: their parts, parameters and total durations.", {}, []),
    "project_validate": ("engine", "validate", "Load every scene, resource and script of the project; list problems (missing files, broken scripts with errors, missing main scene or autoloads).", {}, []),
    "screenshot": ("look", "shot", "Render the main scene without a GPU and save a PNG.", {"out": _str("Output PNG path"), "frames": _str("Frames before capture (default 8)")}, ["out"]),
    "panorama": ("look", "panorama", "Capture a 360-degree equirectangular panorama around the main camera and save a PNG.", {"out": _str("Output PNG path"), "width": _str("Width in pixels (default 1024)")}, ["out"]),
    "image_check": ("look", "check", "Check a screenshot: color balance, muddiness, detail by height and composition.", {"image": _str("PNG path")}, ["image"]),
    "look_apply": ("look", "apply", "Apply the U.ZU look (sky, light, aerial perspective, color grade) and configure the sun.", {"scene": SCENE, "quality": _str("high | standard | low"), "atmosphere": _str("clear | humid | golden_hour | night"), "clouds": {"type": "boolean", "description": "Sky with clouds"}}, ["scene"]),
    "look_hd2d": ("look", "hd2d", "Apply the HD-2D preset in one go: the look, tilt-shift blur, lit outlined pixel-art sprites with blob shadows, one texel size, and a telephoto camera looking down.", {"scene": SCENE, "atmosphere": _str("clear | humid | golden_hour | night (default golden_hour)"), "no-camera": {"type": "boolean", "description": "Leave the camera as it is"}}, ["scene"]),
    "look_particles": ("look", "particles", "Add sparkle particles: light dust, fireflies, snow or embers.", {"scene": SCENE, "kind": _str("dust | fireflies | snow | embers"), "position": _str("x,y,z (default 0,1,0)"), "extents": _str("Half size of the emission box, x,y,z (default 4,2,4)")}, ["scene", "kind"]),
    "look_godrays": ("look", "godrays", "Add fake god rays: an additive shaft of light along the sun's direction through a position.", {"scene": SCENE, "position": _str("x,y,z the shaft passes through"), "width": _str("Width (default 3)"), "length": _str("Length (default 8)")}, ["scene"]),
    "look_water": ("look", "water", "Add a water surface: color and see-through by depth, moving waves, refraction of the bottom, foam at shores, and reflections at grazing angles. Works on every renderer (Web too).", {"scene": SCENE, "position": _str("x,y,z of the surface center (default 0,0,0)"), "size": _str("x,z in meters (default 10,10)"), "shallow": _str("Color of thin water, e.g. #339e94"), "deep": _str("Color of deep water, e.g. #04182a"), "clarity": _str("Meters of water the bottom stays visible through (2)"), "waves": _str("Wave slope strength (0.6)"), "wave-scale": _str("Wave size in meters (1.5)"), "wave-speed": _str("Wave speed (1)"), "swell": _str("Height of the surface swell in meters (0.04)"), "foam": _str("Foam band width in meters where water is shallow; 0 = none (0.3)"), "refraction": _str("Refraction strength (0.03)"), "reflection": _str("Screen-space reflection of the scene, 0..1 (1)")}, ["scene"]),
    "look_rich": ("look", "rich", "Richness report of a scene: static costs (triangles, draw calls, objects, texture memory, props per square meter, lights, the heaviest nodes), model quality (PBR coverage, chamfered edges, triangle density, cheap plain boxes; budget keys min_pbr_coverage, min_bevel_share, max_cheap_meshes), what one rendered frame drew (triangles and draw calls, shadows, video memory), a budget check and hints on what to change. Budget keys are max_<metric> or min_<metric>.", {"scene": _str("Scene (default: the main scene)"), "budget": _str('JSON, e.g. {"max_triangles": 500000, "max_frame_draw_calls": 1500, "min_props_per_m2": 0.5}'), "budget-file": _str("res:// or path to a budget JSON"), "frames": _str("Frames before measuring (10)"), "top": _str("How many of the heaviest nodes (10)"), "no-render": {"type": "boolean", "description": "Static part only (no drawing)"}}, []),
    "ui_report": ("look", "ui-report", "UI richness report of a UI scene (headless): how many controls, panels, buttons and texts, the smallest font, the depth, screen coverage and edge inset, and the problems with a fix for each (small text, text overflow, buttons too small for touch, no margin at the screen edge, overlapping panels, off screen, unstyled default look). ok is false when there are problems.", {"scene": _str("The UI scene, res://..."), "resolution": _str("Screen size to measure at (1280x720)"), "shot": _str("Also save a screenshot here (PNG path)")}, ["scene"]),
    "map_nature": ("map", "nature", "Generate a natural map into a scene in one call: terrain with water (lakes, sea, river), meadows, rock, snow, forests with clearings, rocks and grass, plus collision. Everything is optional: pick a preset (plains, hills, mountains, island, valley, lakes) and override any key. The result names places to use next (spawn, peak, lake, clearings) with positions, and counts. Same spec, same map. A wrong key comes back with the closest valid one; call map_options for every key.", {"scene": SCENE, "spec": _str('JSON object, e.g. {"preset": "island", "seed": 7, "size": 256, "trees": 2}'), "overview": _str("Save a 256 px top-down picture of the map here (PNG path)"), "replace": {"type": "boolean", "description": "Rebuild a map of the same name"}, "camera": {"type": "boolean", "description": "Add a camera that sees the whole map"}, "look": _str("Also light the scene: clear | humid | golden_hour | night"), "shot": _str("Also save a screenshot here (PNG path)"), "spec-set": _str("Also write the generation spec set (B-1509: scene_spec with observed/inferred, region_graph, asset_registry, validation_report) into this folder (a path or res://); pass true for <scene>_spec_set next to the scene")}, ["scene"]),
    "map_city": ("map", "city", "Generate a city into a scene in one call: streets (grid or organic), sidewalks, blocks with buildings made of parts (stone plinth, string courses, pilasters, a door, framed windows that glow, roofs with eaves and chimneys or cornices and parapets) with PBR texture sets (detail simple: plain boxes), a plaza with a fountain, street lamps, trees and benches, plus collision and a baked navigation mesh (NavigationRegion3D) that joins every place. Everything is optional: pick a preset (village, town, city) and override any key. The result names places (spawn, plaza, gates, tallest roof) with positions, and counts. Same spec, same city. Call map_options for every key.", {"scene": SCENE, "spec": _str('JSON object, e.g. {"preset": "village", "seed": 3, "palette": "warm"}'), "overview": _str("Save a 256 px top-down picture of the city here (PNG path)"), "replace": {"type": "boolean", "description": "Rebuild a city of the same name"}, "camera": {"type": "boolean", "description": "Add a camera that sees the whole city"}, "look": _str("Also light the scene: clear | humid | golden_hour | night"), "shot": _str("Also save a screenshot here (PNG path)"), "spec-set": _str("Also write the generation spec set (B-1509: scene_spec with observed/inferred, region_graph, asset_registry, validation_report) into this folder (a path or res://); pass true for <scene>_spec_set next to the scene")}, ["scene"]),
    "map_walk": ("map", "walk", "Self-verifying walk on a generated city: a walker under physics (capsule, gravity, collisions, curb steps) follows the navigation mesh from one place to each target in turn. Per target: reached or not, seconds, meters walked against the straight distance, and where it got stuck (position, what it hit). ok when every target was reached.", {"scene": SCENE, "from": _str("Start place (spawn)"), "to": _str("Targets, comma separated (default: the plaza and every gate)"), "seconds": _str("Most seconds per target (90)")}, ["scene"]),
    "map_walk_graph": ("map", "walk-graph", "Region-graph walking verification (B-1510): a walker under physics (capsule, gravity, collisions, curb steps) walks every edge of a B-1509 region graph (uzu-region-graph/1) in both directions — along the navigation mesh where it is on it, steering straight at the target where there is none — and returns per-edge pass/fail with frames, seconds, meters walked and stuck points. ok when every edge passed both ways. block-node fences one node in with walls, to prove exactly its edges fail. The scene must already contain the generated map the graph describes.", {"graph": _str("Path to the region graph JSON (B-1509)"), "scene": SCENE, "seconds": _str("Most seconds per leg (0 = from each edge's length)"), "block-node": _str("Fence this node in so its edges fail (counter-check)")}, ["graph"]),
    "scene_audit": ("audit-scene", None, "Re-read audit of a saved scene (BACKLOG B-1511): re-opens the saved .tscn through the resource loader and recounts what is actually in the artifact -- mesh triangles, textures (count and dimensions), placed instances, collision shapes and bodies, lights, navigation meshes -- then compares the recount with the generation spec set (B-1509: asset_registry / scene_spec), never with the generator's own claims. Per check: match, difference (expected and recounted values) or not_countable with the reason. Also reports MultiMesh instances that are stored in the file but dropped on load. spec-set defaults to the spec_set folder next to the scene.", {"scene": SCENE, "spec-set": _str("Path to the B-1509 spec set folder (default: spec_set next to the scene)"), "out": _str("Also write the full report JSON here")}, ["scene"]),
    "collision_check": ("collision-check", None, "Mechanical collision check of a saved scene (BACKLOG B-1224): rasterizes the scene's collision solids and visual footprints onto a grid (cell ~ the character's width) and checks them geometrically -- visual footprints the collision does not cover, collision no visual explains (invisible walls), wall leaks (a visual barrier with a collision gap a walker slips through) and plugged gaps (invisible collision sealing an open passage), walkable connectivity from the start places under a step rule (unreachable places, disconnected starts with the bottleneck position and its required rise, pockets with no start and no place), and collision AABBs of different bodies overlapping by volume. Every finding carries coordinates and a severity; ok when no finding is an error. --heatmap also writes a top-down PNG of the raster. Static and geometric; the dynamic counterpart is map_walk_graph (B-1510). Starts default to the places whose name says spawn.", {"scene": SCENE, "start": _str("Extra start point x,z (repeatable; default: the spawn places)"), "cell": _str("Grid resolution in metres (0.5)"), "step": _str("Max rise across a surface change in metres (0.25)"), "char-width": _str("The walker's width in metres (0.7)"), "body-height": _str("Headroom a stand surface needs in metres (1.8)"), "out": _str("Also write the full report JSON here"), "heatmap": _str("Also write the top-down raster PNG here")}, ["scene"]),
    "map_options": ("map", "options", "List every key of map_nature and map_city with its default, what it accepts and what it does, and the presets.", {}, []),
    "scene_build": ("build", None, "Build a whole scene from one JSON spec (ground, models, scattered props, look, camera, lamps, particles, water, god rays) and get its richness report back; see ai_loop/look_samples/specs/village.json for an example and ai_loop/build_tool.gd for every key. Mistakes in the spec come back as a list of problems that name where they are.", {"spec": _str("res:// or path to the spec JSON"), "shot": _str("Also save a screenshot here (PNG path)"), "budget": _str("Budget JSON for the report, max_/min_ keys"), "no-render": {"type": "boolean", "description": "Static report only"}, "no-report": {"type": "boolean", "description": "Skip the report"}, "spec-set": _str("Also write the generation spec set (B-1509: scene_spec with observed/inferred, region_graph, asset_registry, validation_report) into this folder (a path or res://); pass true for <scene>_spec_set next to the scene")}, ["spec"]),
    "scene_enrich": ("enrich", None, "Make an existing scene richer in one call with a preset (village_rich, meadow, ruins: grass, flowers, stones, dust and a matching look; props keep off existing objects and stay near the camera on huge grounds). Returns the richness report before and after and the difference; applying again replaces the earlier props.", {"preset": _str("village_rich | meadow | ruins"), "scene": _str("Scene (default: the main scene)"), "surface": _str("The ground node (Ground)"), "seed": _str("Vary the layout"), "density-scale": _str("Multiply every density (1)"), "shot": _str("Also save a screenshot here (PNG path)"), "no-render": {"type": "boolean", "description": "Static report only"}}, ["preset"]),
    "ui_build": ("ui", None, "Build a UI screen (HUD, dialogs, menus) from one JSON spec: a Control tree with anchors, containers and a theme (rounded panels, borders, shadows, buttons, bars), and optionally render it over a game scene. See ai_loop/look_samples/specs/hud.json for an example and ai_loop/ui_tool.gd for every key; mistakes come back as a list that names where they are.", {"spec": _str("res:// or path to the UI spec JSON"), "shot": _str("Also save a screenshot here (PNG path)"), "over": _str("Render the UI over this scene, res://..."), "frames": _str("Frames before the shot (8)"), "theme": _str("Genre theme preset over the spec's theme: wafu | sf | fantasy"), "world": _str("World UI in one name (textured game frames and parts): fantasy | wafu | sf | horror | persona | pixel"), "font-subset": {"type": "boolean", "description": "Bundle a Latin + Japanese font subset of the UI's text (needed for web builds; needs fonttools)"}}, ["spec"]),
    "look_palette": ("look", "palette", "Add palette quantization with ordered dithering (a modern retro finish) after the look's post effects.", {"scene": SCENE, "levels": _str("Steps per color channel, 2-64 (default 6)"), "strength": _str("Dither strength 0-1 (default 1)"), "scale": _str("Pixels per dither cell 1-8 (default 1)")}, ["scene"]),
    "look_rig": ("look", "rig", "Add fill and rim lights (three-point lighting with the sun as key).", {"scene": SCENE, "atmosphere": _str("clear | humid | golden_hour | night")}, ["scene"]),
    "look_lamp": ("look", "lamp", "Add a warm lamp with a glowing bulb.", {"scene": SCENE, "position": _str("x,y,z"), "quality": _str("high | standard | low")}, ["scene", "position"]),
    "look_camera": ("look", "camera", "Set a camera's lens, eye height and vertical shift.", {"scene": SCENE, "node": NODE, "lens": _str("wide | standard | telephoto"), "eye": _str("standing | low"), "shift": _str("Fraction of view height, positive is up")}, ["scene"]),
    "lightmap_bake": ("look", "bake", "Bake the scene's LightmapGI (runs the editor with a renderer; can take minutes). 'prepare' turns on UV2 for primitive meshes.", {"scene": SCENE, "node": NODE, "prepare": {"type": "boolean", "description": "Turn on UV2 for primitive meshes"}}, ["scene"]),
    "look_sprite": ("look", "sprite", "Make Sprite3D nodes lit pixel-art sprites (light, shadows, fog; crisp texels), with optional normal map, outline and blob shadow.", {"scene": SCENE, "node": NODE, "normal": _str("Normal map, res://..."), "outline": _str("Outline width in texels (0-4)"), "blob": _str("Blob shadow radius (0 = none)")}, ["scene"]),
    "look_texels": ("look", "texels", "Check the texel density of the scene's sprites: warns on sprites whose pixels are bigger or smaller than the others', and on blurry filtering.", {"scene": SCENE, "tolerance": _str("Allowed difference, default 0.05")}, ["scene"]),
    "look_pixel": ("look", "pixel", "Pixel discipline preset: one texel size for all sprites, nearest filtering, optional snapping to the texel grid.", {"scene": SCENE, "texel": _str("Texel size in meters (default: the sprites' median)"), "snap": {"type": "boolean", "description": "Snap sprite positions to the texel grid"}}, ["scene"]),
    "look_material": ("look", "material", "Create a preset material (save to 'out', or assign to 'node' in 'scene').", {"kind": _str("skin | foliage | glass | water | lamp"), "out": _str("res://path.tres"), "scene": SCENE, "node": NODE}, ["kind"]),
}


# Capability requirements (BACKLOG B-404), declared next to the tools they
# describe: the agent capabilities a tool needs beyond what the engine
# provides itself, and what to do instead when the agent lacks one.
# ai_loop/make_catalog.py copies these onto the matching "mcp" catalog
# entries (and onto a "command" entry when exactly one tool maps to it);
# catalog search annotates entries with the capabilities a profile is
# missing instead of hiding them. Capability names: ai_loop/agent_caps.py.
TOOL_CAPABILITIES = {
    "frame_benchmark": {"required_capabilities": ["gpu"], "fallback": "Without a GPU, run the benchmark headless (omit render): it still measures CPU frame work and startup; only the render wall-time marks need a GPU."},
}


def _parse_frontmatter(text, fallback_name):
    name = fallback_name
    description = ""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {"name": name, "description": description}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key == "name" and value:
            name = value
        elif key == "description":
            description = value
    return {"name": name, "description": description}


def _load_skills():
    skills = []
    resources = {}
    if not os.path.isdir(SKILLS_DIR):
        return skills, resources
    for entry_name in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry_name)
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isdir(skill_dir) or not os.path.isfile(skill_md_path):
            continue
        with open(skill_md_path, "rb") as f:
            skill_md_raw = f.read()
        frontmatter = _parse_frontmatter(skill_md_raw.decode("utf-8", errors="replace"), entry_name)
        skill_uri = f"skill://{entry_name}/SKILL.md"
        skill_resources = []

        file_paths = []
        for root, _, files in os.walk(skill_dir):
            for fname in sorted(files):
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, skill_dir).replace(os.sep, "/")
                file_paths.append((rel_path, full_path))
        file_paths.sort(key=lambda item: (0 if item[0] == "SKILL.md" else 1, item[0]))

        for rel_path, full_path in file_paths:
            uri = f"skill://{entry_name}/{rel_path}"
            mime = "text/markdown" if rel_path.endswith(".md") else "text/plain"
            with open(full_path, "rb") as f:
                raw = f.read()
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            skill_resources.append({
                "uri": uri,
                "digest": digest,
                "size": len(raw),
            })
            resources[uri] = {
                "uri": uri,
                "name": rel_path,
                "mimeType": mime,
                "text": raw.decode("utf-8", errors="replace"),
            }

        skills.append({
            "uri": skill_uri,
            "frontmatter": frontmatter,
            "resources": skill_resources,
        })
    return skills, resources


def call_tool(project, name, arguments):
    script, command, _, _, _ = TOOLS[name]
    if script in ("replay-compare", "catalog", "dialogue"):
        argv = [sys.executable, os.path.join(HERE, "uzu.py"), script]
    elif script == "bench":
        argv = [sys.executable, os.path.join(HERE, "bench.py"), command, "--project", project]
    else:
        argv = [sys.executable, os.path.join(HERE, "uzu.py"), script, project] + ([command] if command else [])  # Cross-platform entry (B-801).
    for key, value in (arguments or {}).items():
        if value is None or value == "" or value is False:
            continue
        argv += [f"--{key}"] if value is True else [f"--{key}", str(value)]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    lines = [l for l in proc.stdout.splitlines() if l.startswith("{")]
    text = lines[-1] if lines else json.dumps({"ok": False, "error": (proc.stderr or proc.stdout)[-2000:]})
    try:
        ok = json.loads(text).get("ok", False)
    except ValueError:
        ok = False
    return {"content": [{"type": "text", "text": text}], "isError": not ok}


def handle(project, message):
    method, mid = message.get("method"), message.get("id")
    if method == "initialize":
        result = {"protocolVersion": PROTOCOL_VERSION, "capabilities": CAPABILITIES, "serverInfo": SERVER_INFO}
    elif method == "server/discover":
        result = {"protocolVersion": DISCOVER_PROTOCOL_VERSION, "capabilities": CAPABILITIES, "serverInfo": SERVER_INFO}
    elif method == "skills/list":
        skills, _ = _load_skills()
        result = {"skills": skills, "ttlMs": 60000, "cacheScope": "private"}
    elif method == "skills/get":
        params = message.get("params") or {}
        uri = params.get("uri")
        skills, _ = _load_skills()
        skill = next((s for s in skills if s["uri"] == uri), None)
        if skill is None:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "unknown skill uri"}}
        result = {"skill": skill}
    elif method == "resources/list":
        _, resources = _load_skills()
        result = {"resources": [{"uri": r["uri"], "name": r["name"], "mimeType": r["mimeType"]} for r in resources.values()]}
    elif method == "resources/read":
        params = message.get("params") or {}
        uri = params.get("uri")
        _, resources = _load_skills()
        resource = resources.get(uri)
        if resource is None:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "unknown resource uri"}}
        result = {"contents": [{"uri": resource["uri"], "mimeType": resource["mimeType"], "text": resource["text"]}]}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": p, "required": r}} for n, (_, _, d, p, r) in TOOLS.items()]}
    elif method == "tools/call":
        params = message.get("params", {})
        if params.get("name") not in TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {params.get('name')}"}}
        result = call_tool(project, params["name"], params.get("arguments"))
    elif method == "ping":
        result = {}
    elif mid is None:
        return None  # Notifications (e.g. notifications/initialized) get no response.
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(project):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle(project, json.loads(line))
        except Exception as e:  # Keep serving; report the failure to the client.
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


def self_test():
    with tempfile.TemporaryDirectory() as project:
        with open(os.path.join(project, "project.godot"), "w") as f:
            f.write('config_version=5\n\n[application]\n\nconfig/name="mcp selftest"\nrun/main_scene="res://main.tscn"\n')
        with open(os.path.join(project, "bad.gdshader"), "w") as f:
            f.write("shader_type canvas_item;\nvoid fragment() { COLOR = nope; }\n")
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "selftest", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "scene_new", "arguments": {"scene": "res://main.tscn", "type": "Node3D"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "node_add", "arguments": {"scene": "res://main.tscn", "parent": ".", "type": "OmniLight3D", "name": "Light"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "look_apply", "arguments": {"scene": "res://main.tscn", "atmosphere": "humid"}}},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "scene_tree", "arguments": {"scene": "res://main.tscn"}}},
            {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "node_get", "arguments": {"scene": "res://main.tscn", "node": "Nope", "property": "position"}}},
            {"jsonrpc": "2.0", "id": 8, "method": "nope"},
            {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "script_check", "arguments": {"path": "res://bad.gdshader"}}},
            {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "frame_benchmark", "arguments": {"frames": "40", "repeat": "1"}}},
            {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "frame_benchmark", "arguments": {"frames": "0"}}},
            {"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {"name": "catalog_search", "arguments": {"query": "sfx"}}},
            {"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {"name": "catalog_search", "arguments": {"query": "no-such-feature-zzz"}}},
            {"jsonrpc": "2.0", "id": 14, "method": "tools/call", "params": {"name": "catalog_search", "arguments": {"query": "benchmark", "caps": "image_gen"}}},
            {"jsonrpc": "2.0", "id": 15, "method": "tools/call", "params": {"name": "vfx_describe", "arguments": {"name": "laser"}}},
            {"jsonrpc": "2.0", "id": 16, "method": "tools/call", "params": {"name": "vfx_describe", "arguments": {"recipe": "{\"parts\": [{\"type\": \"shockwave\"}]}"}}},
        ]
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--project", project], input="\n".join(json.dumps(r) for r in requests) + "\n", capture_output=True, text=True, timeout=600)
        responses = {r["id"]: r for r in map(json.loads, proc.stdout.splitlines())}
        assert responses[1]["result"]["serverInfo"]["name"] == "uzu-engine", responses[1]
        assert len(responses[2]["result"]["tools"]) == len(TOOLS), responses[2]
        for i in (3, 4, 5, 6):
            assert not responses[i]["result"]["isError"], responses[i]
        tree = json.loads(responses[6]["result"]["content"][0]["text"])
        paths = [n["path"] for n in tree["nodes"]]
        assert "Light" in paths and "WorldEnvironment" in paths and "Sun" in paths, tree
        assert responses[7]["result"]["isError"], responses[7]
        assert responses[8]["error"]["code"] == -32601, responses[8]
        shader = json.loads(responses[9]["result"]["content"][0]["text"])
        assert responses[9]["result"]["isError"] and shader["errors"][0]["line"] == 2, shader
        timing = json.loads(responses[10]["result"]["content"][0]["text"])
        assert not responses[10]["result"]["isError"], timing
        assert timing["marks"]["[Frame] work worst"] >= timing["marks"]["[Frame] work average"] > 0, timing
        assert responses[11]["result"]["isError"], responses[11]
        found = json.loads(responses[12]["result"]["content"][0]["text"])
        assert not responses[12]["result"]["isError"] and any(m["name"] == "sfx_make" for m in found["matches"]), found
        missed = json.loads(responses[13]["result"]["content"][0]["text"])
        assert not responses[13]["result"]["isError"] and missed["count"] == 0, missed
        capped = json.loads(responses[14]["result"]["content"][0]["text"])
        assert not responses[14]["result"]["isError"] and capped["profile"] == ["image_gen"], capped
        bench = next(m for m in capped["matches"] if m["name"] == "frame_benchmark")
        assert bench["missing_capabilities"] == ["gpu"], bench
        laser = json.loads(responses[15]["result"]["content"][0]["text"])
        assert not responses[15]["result"]["isError"] and laser["parts"][0]["type"] == "beam" and laser["duration"] > 0, laser
        bad = json.loads(responses[16]["result"]["content"][0]["text"])
        assert responses[16]["result"]["isError"] and "shockwave" in str(bad["errors"]), bad
        assert len(responses) == 16, "notifications must not get a response"
    print("mcp selftest: ok")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    if "--project" not in sys.argv:
        print(__doc__, file=sys.stderr)
        return 2
    serve(os.path.abspath(sys.argv[sys.argv.index("--project") + 1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

