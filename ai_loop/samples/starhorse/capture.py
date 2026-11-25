#!/usr/bin/env python3
"""Screenshots of the Star Horse sample (B-1329/B-1330).

Runs a throwaway copy of the project with a small driver autoload
(the hikari capture pattern): the driver walks title -> farm ->
entries -> race (at 6x, saving the start / mid-race / final-stretch
frames) -> result, samples the race fps under the software renderer,
and writes stats.json next to the shots.

Rendering is the repo's software path (Xvfb + lavapipe Vulkan, via
ai_loop/uzu.py) -- the fps number is that path's, not a GPU's.

Usage: python3 capture.py [project-dir] [out-dir]
Writes title.png, farm.png, entries.png, race_start.png, race_mid.png,
race_final.png, result.png, stats.json into out-dir (default:
<project>/shots). Exit code 0 when every capture was written.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import uzu  # noqa: E402

DRIVER = r'''
extends Node
## Capture driver (B-1330): title -> farm -> entries -> race phases
## -> result, one PNG per stage.

var _frame := 0
var _stage := 0
var _out := ""
var _fps: Array = []
var _saved := {}

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var args := OS.get_cmdline_user_args()
	var i := args.find("--uzu-capture")
	if i >= 0 and i + 1 < args.size():
		_out = args[i + 1]

func _save(name: String) -> void:
	get_viewport().get_texture().get_image().save_png(_out + "/" + name)
	_saved[name] = true

func _main() -> Node:
	return get_tree().current_scene

func _process(_delta: float) -> void:
	if _out.is_empty():
		return
	_frame += 1
	if _frame == 3 and _stage == 0:
		# Capture is a verification harness: drain the commentary at
		# fast-forward speed like the autoplay path, or the result
		# stage waits for every clip's real length.
		var c = _main().get("_commentary")
		if c != null:
			c.fast = true
	match _stage:
		0: # title: let the logo/buttons finish their appear motion
			if _frame >= 80:
				_save("title.png")
				_main().goto("farm")
				_stage = 1
				_frame = 0
		1:
			if _frame >= 55:
				_save("farm.png")
				_main().goto("entries")
				_stage = 2
				_frame = 0
		2:
			if _frame >= 55:
				_save("entries.png")
				_main().goto_race()
				var race = _main().get("_race")
				# 12x: at 6x the slow-motion finish starved the
				# lavapipe frame budget and the run timed out.
				race.time_scale = 12.0
				race.start_race()
				_stage = 3
				_frame = 0
		3:
			var race = _main().get("_race")
			if _frame % 20 == 0:
				_fps.append(Engine.get_frames_per_second())
			if race != null:
				var lead: float = race._leader_pos()
				if lead > 60.0 and not _saved.has("race_start.png"):
					_save("race_start.png")
				if lead > 950.0 and not _saved.has("race_mid.png"):
					_save("race_mid.png")
				if lead > 1600.0 and not _saved.has("race_final.png"):
					_save("race_final.png")
				if str(_main().get("_screen")) == "result":
					_stage = 4
					_frame = 0
			if _frame > 60 * 300:
				get_tree().quit()
		4:
			if _frame >= 50:
				_save("result.png")
				var sum := 0.0
				for f in _fps:
					sum += float(f)
				var stats := {"fps_avg_race": snappedf(sum / max(_fps.size(), 1), 0.1),
					"fps_samples": _fps.size(), "renderer": "lavapipe (software Vulkan)"}
				var file := FileAccess.open(_out + "/stats.json", FileAccess.WRITE)
				file.store_string(JSON.stringify(stats, "\t"))
				file.close()
				get_tree().quit()
'''

SHOTS = ["title", "farm", "entries", "race_start", "race_mid",
         "race_final", "result"]


def main() -> int:
    project = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else HERE
    out_dir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(project, "shots")
    os.makedirs(out_dir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="uzu_capture_")
    try:
        game = os.path.join(work, "game")
        shutil.copytree(project, game, ignore=shutil.ignore_patterns(".godot", "shots"))
        addon = os.path.join(game, "addons", "uzu_capture")
        os.makedirs(addon, exist_ok=True)
        with open(os.path.join(addon, "driver.gd"), "w", encoding="utf-8") as f:
            f.write(DRIVER)
        cfg = os.path.join(game, "project.godot")
        with open(cfg, encoding="utf-8") as f:
            text = f.read()
        entry = 'UZUCapture="*res://addons/uzu_capture/driver.gd"\n'
        text = text.replace("\n[autoload]\n", "\n[autoload]\n\n" + entry, 1) if "\n[autoload]\n" in text else text + "\n[autoload]\n\n" + entry
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run([uzu.find_godot(), "--headless", "--path", game, "--import"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
        stage = os.path.join(work, "stage")
        os.makedirs(stage)
        cmd = [uzu.find_godot(), "--path", game, "--fixed-fps", "60", "--resolution", "1152x648"]
        cmd, env = uzu.render_command(cmd + uzu.driver(), "1152x648")
        cmd += ["--", "--uzu-capture", stage]
        with open(os.path.join(out_dir, "capture_run.log"), "w", encoding="utf-8") as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=2400, env=env)
        ok = True
        for name in SHOTS:
            src = os.path.join(stage, name + ".png")
            dst = os.path.join(out_dir, name + ".png")
            if os.path.exists(src):
                shutil.copyfile(src, dst)
                print("wrote", dst)
            else:
                ok = False
                print("MISSING", dst)
        stats = os.path.join(stage, "stats.json")
        if os.path.exists(stats):
            shutil.copyfile(stats, os.path.join(out_dir, "stats.json"))
            print("wrote", os.path.join(out_dir, "stats.json"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
