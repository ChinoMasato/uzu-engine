#!/usr/bin/env python3
"""B-1330 race video: title -> farm -> entries -> race (8x) -> result,
recorded frame by frame at a fixed 30 fps and encoded to
shots/motion_race.mp4 (about 22 s). Same staging approach as
capture.py; find the engine with $GODOT or PATH."""
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

var _frame := 0
var _out := ""
var _phase := 0
var _result_frame := 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var args := OS.get_cmdline_user_args()
	var i := args.find("--uzu-capture")
	if i >= 0 and i + 1 < args.size():
		_out = args[i + 1]

func _save() -> void:
	get_viewport().get_texture().get_image().save_png(
		_out + "/frame_%04d.png" % _frame)

func _process(_delta: float) -> void:
	if _out.is_empty():
		return
	_frame += 1
	var main = get_tree().current_scene
	if _frame == 3:
		var c = main.get("_commentary")
		if c != null:
			c.fast = true
	match _phase:
		0:  # title, 2.5 s
			if _frame >= 60:
				main.goto("farm")
				_phase = 1
		1:  # farm, 2 s
			if _frame >= 105:
				main.goto("entries")
				_phase = 2
		2:  # entries, 2 s
			if _frame >= 150:
				main.goto_race()
				var race = main.get("_race")
				race.time_scale = 8.0
				race.start_race()
				_phase = 3
		3:  # race at 8x until the result screen is up
			if main.get("_screen") == "result":
				_result_frame = _frame
				_phase = 4
		4:  # result, 1.5 s, then stop
			if _frame >= _result_frame + 45:
				get_tree().quit()
				return
	_save()
	if _frame > 1500:
		get_tree().quit()
'''


def main() -> int:
    godot = uzu.find_godot()
    work = tempfile.mkdtemp(prefix="uzu_video_")
    try:
        game = os.path.join(work, "game")
        shutil.copytree(HERE, game, ignore=shutil.ignore_patterns(".godot", "shots"))
        addon = os.path.join(game, "addons", "uzu_capture")
        os.makedirs(addon, exist_ok=True)
        with open(os.path.join(addon, "driver.gd"), "w", encoding="utf-8") as f:
            f.write(DRIVER)
        cfg = os.path.join(game, "project.godot")
        with open(cfg, encoding="utf-8") as f:
            text = f.read()
        entry = 'UZUCapture="*res://addons/uzu_capture/driver.gd"\n'
        if "\n[autoload]\n" in text:
            text = text.replace("\n[autoload]\n", "\n[autoload]\n\n" + entry, 1)
        else:
            text += "\n[autoload]\n\n" + entry
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run([godot, "--headless", "--path", game, "--import"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
        frames = os.path.join(work, "frames")
        os.makedirs(frames)
        cmd = [godot, "--path", game, "--fixed-fps", "30",
               "--resolution", "1152x648"]
        cmd, env = uzu.render_command(cmd + uzu.driver(), "1152x648")
        cmd += ["--", "--uzu-capture", frames]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
        with open(os.path.join(HERE, "shots", "video_run.log"), "w", encoding="utf-8") as f:
            f.write(run.stdout + "\n" + run.stderr)
        names = sorted(n for n in os.listdir(frames) if n.endswith(".png"))
        count = len(names)
        if count < 100:
            print("too few frames:", count)
            return 1
        # Renumber contiguously: a single missing frame number would
        # make ffmpeg's image2 demuxer stop the encode there.
        for i, name in enumerate(names):
            os.rename(os.path.join(frames, name),
                      os.path.join(frames, "seq_%04d.png" % (i + 1)))
        for i in range(count):
            os.rename(os.path.join(frames, "seq_%04d.png" % (i + 1)),
                      os.path.join(frames, "frame_%04d.png" % (i + 1)))
        out_mp4 = os.path.join(HERE, "shots", "motion_race.mp4")
        subprocess.run(["ffmpeg", "-y", "-framerate", "30",
                        "-i", os.path.join(frames, "frame_%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                        out_mp4], check=True, capture_output=True, timeout=900)
        print("frames:", count, "->", out_mp4)
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
