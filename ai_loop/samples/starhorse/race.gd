class_name RaceScreen
extends Control
## The race screen. B-1329's simulation and commentary phase machine
## are unchanged -- snapshots (ranks at 600m / 1200m, margins at the
## goal) still choose the lines, and everything stays deterministic
## for a given `seed_value`. B-1330 replaces the presentation: a
## side-view 2.5D broadcast over the racecourse art, split into
## parallax layers (stand / turf / near rail), with the galloping
## horse cut-outs (prep_assets.py) doing the running -- gallop bob
## and pitch from the stride phase, turf dust, speed streaks and
## afterimages at full stretch, a camera that follows the leader,
## pushes in over the last 200 m, and drops into slow motion at the
## goal for a photo-finish beat, with a restrained flash and shake.
##
## Commentary mapping (audio/voice/README.md):
##   pre (fanfare -> gate-in -> ready) -> start (+clean/late note)
##   -> early (lead battle / leader / stretched / hold-back)
##   -> mid (front side / settled / corner)
##   -> final straight -> the move (holds on / outside / inside)
##   -> 200m -> 100m -> goal (win / push / close / photo)
##   -> win style (front-run / stalker / closer / runaway)
##   -> upset (long-shot winner) -> crowd -> closing.

signal race_finished(results: Array)
signal exit_requested

const DIST := 1800.0
const VIEW_W := 1152.0
const FAR_Y := 336.0 # far layer (sky + stand) fills 0..FAR_Y
const GROUND_Y := 596.0 # hoof line of the middle lane
const RANK_RECT := Rect2(868, 60, 272, 404)

var commentary: Commentary
var time_scale := 1.0
var seed_value := 1329

var _rng := RandomNumberGenerator.new()
var _runners: Array = [] # per gate: {horse, draw, pos, delay, wobble, jitter, vel, phase, finish_t, rank600, rank1200}
var _state := "idle" # idle | pre | run | done
var _clock := 0.0 # seconds since the gate opened (negative in pre)
var _fired := {}
var _results: Array = []
var _fps_samples: Array = []
var _fps_timer := 0.0

var _cam_m := -36.0 # world metres at the left edge
var _px_m := 8.6 # pixels per metre (grows over the last 200 m)
var _slowmo := 1.0
var _winner_at := -1.0 # real seconds when the winner crossed
var _flash := 0.0
var _shake := 0.0
var _shake_off := Vector2.ZERO # this frame's shake offset, set in _draw
var _elapsed := 0.0
var _dust: Array = [] # {x (m), h (px above ground), vx, vh, age, life, size}
var _dust_acc := 0.0

var _phase_label: Label
var _clock_label: Label
var _subtitle: Label
var _fanfare: AudioStreamPlayer

var _tex_far: Texture2D
var _tex_turf: Texture2D
var _tex_rail: Texture2D
var _tex_shadow: Texture2D
var _tex_dust: Texture2D
var _tex_horses: Array = []
var _chip_box: StyleBoxFlat
var _pill_box: StyleBoxFlat


func _ready() -> void:
	_tex_far = load("res://art/race_far.jpg")
	_tex_turf = load("res://art/race_turf.jpg")
	_tex_rail = load("res://art/race_rail.png")
	_tex_shadow = load("res://art/shadow.png")
	_tex_dust = load("res://art/dust.png")
	for gate in range(8):
		_tex_horses.append(load("res://art/horse_var%d.png" % gate))
	_chip_box = StyleBoxFlat.new()
	_chip_box.bg_color = Color(0.97, 0.97, 0.97, 0.95)
	_chip_box.border_color = Color(0.05, 0.05, 0.05, 0.8)
	_chip_box.set_border_width_all(1)
	_chip_box.set_corner_radius_all(4)
	_pill_box = StyleBoxFlat.new()
	_pill_box.bg_color = Color(0.0, 0.0, 0.0, 0.62)
	_pill_box.set_corner_radius_all(10)
	_phase_label = _make_label(24, 12, 27)
	add_child(_phase_label)
	_clock_label = _make_label(880, 14, 23)
	_clock_label.size = Vector2(248, 34)
	_clock_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	add_child(_clock_label)
	_subtitle = _make_label(126, 503, 21)
	_subtitle.size = Vector2(900, 38)
	_subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_subtitle)
	_fanfare = AudioStreamPlayer.new()
	_fanfare.bus = "BGM"
	_fanfare.stream = load("res://audio/fanfare.mp3")
	add_child(_fanfare)
	if commentary != null:
		commentary.line_changed.connect(func(text: String) -> void: _subtitle.text = text)


func _make_label(x: int, y: int, font_size: int) -> Label:
	var l := Label.new()
	l.position = Vector2(x, y)
	l.size = Vector2(700, 40)
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_outline_color", Color(0.04, 0.08, 0.03, 0.9))
	l.add_theme_constant_override("outline_size", 6)
	return l


## Starts (or restarts) the race: fanfare, gate-in, ready, then run.
func start_race() -> void:
	_rng.seed = seed_value
	_runners.clear()
	for gate in range(1, 9):
		var draw: Dictionary = StarHorseData.DRAW[gate - 1]
		var horse: Dictionary = StarHorseData.HORSES[int(draw["horse"])]
		_runners.append({
			"gate": gate, "horse": horse, "draw": draw,
			"pos": 0.0, "delay": 0.0, "wobble": _rng.randf_range(0.0, TAU),
			"jitter": 0.0, "vel": 0.0, "phase": _rng.randf_range(0.0, TAU),
			"finish_t": -1.0, "rank600": 0, "rank1200": 0,
		})
	# One horse may break late; with the sample field it is the
	# deep closer in gate 4 about half the time -- decided by the seed.
	if _rng.randf() < 0.55:
		var late: Dictionary = _runners[_rng.randi_range(0, 7)]
		late["delay"] = _rng.randf_range(0.4, 0.7)
	_state = "pre"
	_clock = -6.5
	_fired.clear()
	_results.clear()
	_fps_samples.clear()
	_cam_m = -36.0
	_px_m = 8.6
	_slowmo = 1.0
	_winner_at = -1.0
	_flash = 0.0
	_shake = 0.0
	_dust.clear()
	_phase_label.text = "中山11R %s（芝 %dm）" % [StarHorseData.RACE_NAME, StarHorseData.RACE_DISTANCE]
	_fanfare.play()


func _process(delta: float) -> void:
	_elapsed += delta
	_flash = maxf(_flash - delta * 1.6, 0.0)
	_shake = maxf(_shake - delta * 9.0, 0.0)
	if _state != "pre" and _state != "run":
		queue_redraw()
		return
	# Slow motion over the last metres, released once the winner is in.
	var leader := _leader_pos()
	var target := 1.0
	if leader >= 1690.0 and _winner_at < 0.0:
		target = 0.32
	_slowmo = lerpf(_slowmo, target, clampf(delta * 2.2, 0.0, 1.0))
	var dt := delta * time_scale * _slowmo
	_clock += dt
	_fps_timer += delta
	if _fps_timer >= 1.0:
		_fps_timer = 0.0
		_fps_samples.append(Engine.get_frames_per_second())
	if _state == "pre":
		_pre_events()
		for r in _runners:
			r["phase"] = float(r["phase"]) + dt * 2.0 # idle sway
		if _clock >= 0.0:
			_state = "run"
			_say("start", "03_start")
	else:
		_step(dt)
		_run_events()
		_maybe_finish()
	_update_camera(dt)
	_update_dust(dt)
	_clock_label.text = "%.1f" % maxf(_clock, 0.0)
	queue_redraw()


func _update_camera(dt: float) -> void:
	var leader := _leader_pos()
	var t := clampf((leader - 1400.0) / 350.0, 0.0, 1.0)
	var px_target := 8.6 + 2.4 * (t * t * (3.0 - 2.0 * t))
	_px_m = lerpf(_px_m, px_target, clampf(dt * 1.5, 0.0, 1.0))
	var cam_target := leader - (0.60 * VIEW_W) / _px_m
	cam_target = clampf(cam_target, -36.0, 1740.0)
	_cam_m = lerpf(_cam_m, cam_target, clampf(dt * 2.6, 0.0, 1.0))


func _sx(pos: float) -> float:
	return (pos - _cam_m) * _px_m


func _ground_y(gate: int) -> float:
	return GROUND_Y + (float(gate) - 4.5) * 6.0


func _pre_events() -> void:
	if _clock >= -5.6 and not _fired.has("gatein"):
		_fired["gatein"] = true
		_say("pre_gatein", "01_pre_gatein")
	if _clock >= -2.8 and not _fired.has("ready"):
		_fired["ready"] = true
		_say("pre_ready", "02_pre_ready")


func _base_speed(horse: Dictionary) -> float:
	return 14.6 + float(horse["speed"]) * 0.030


func _step(dt: float) -> void:
	for r in _runners:
		if r["delay"] > 0.0:
			r["delay"] = float(r["delay"]) - dt
			r["vel"] = 0.0
			continue
		var horse: Dictionary = r["horse"]
		var p := clampf(float(r["pos"]) / DIST, 0.0, 1.0)
		var style := str(horse["style"])
		var factor := 1.0
		if p < 0.55:
			factor = {"逃げ": 1.045, "先行": 1.02, "差し": 0.985, "追込": 0.965}[style]
		else:
			factor = {"逃げ": 0.985, "先行": 1.0, "差し": 1.025, "追込": 1.045}[style]
		if p > 0.66:
			factor *= 1.0 - (1.0 - float(horse["stamina"]) / 100.0) * 0.16 * ((p - 0.66) / 0.34)
		r["wobble"] = float(r["wobble"]) + dt * 0.7
		r["jitter"] = lerpf(float(r["jitter"]), _rng.randf_range(-0.012, 0.012), dt * 2.0)
		var ramp := clampf(maxf(_clock, 0.0) / 2.5, 0.25, 1.0)
		var v := _base_speed(horse) * factor * ramp * (1.0 + 0.008 * sin(float(r["wobble"])) + float(r["jitter"]))
		if float(r["finish_t"]) > 0.0:
			v *= 0.92 # easing down past the goal
		r["vel"] = v
		r["pos"] = float(r["pos"]) + v * dt
		r["phase"] = float(r["phase"]) + dt * v * 0.8
		if float(r["finish_t"]) < 0.0 and float(r["pos"]) >= DIST:
			r["finish_t"] = _clock
			if _winner_at < 0.0:
				_winner_at = _elapsed


func _order() -> Array:
	var idx := range(8)
	idx.sort_custom(func(a: int, b: int) -> bool: return float(_runners[a]["pos"]) > float(_runners[b]["pos"]))
	return idx


func _leader_pos() -> float:
	var best := 0.0
	for r in _runners:
		best = maxf(best, float(r["pos"]))
	return best


func _say(phase: String, voice_id: String) -> void:
	if commentary != null:
		commentary.say(phase, voice_id, _clock)


func _once(key: String, at: float) -> bool:
	if _leader_pos() >= at and not _fired.has(key):
		_fired[key] = true
		return true
	return false


func _run_events() -> void:
	var order := _order()
	var leader: Dictionary = _runners[order[0]]
	var second: Dictionary = _runners[order[1]]
	# Start note.
	if _clock >= 0.9 and not _fired.has("start_note"):
		_fired["start_note"] = true
		var late := false
		for r in _runners:
			if float(r["pos"]) < 2.0 and _clock > 0.9:
				late = true
		# A horse still near the gate at 0.9 s broke late.
		_say("start_note", "05_start_late" if late else "04_start_clean")
	# Early.
	if _once("lead_battle", 200.0):
		if float(leader["pos"]) - float(second["pos"]) <= 2.5:
			_say("early", "06_early_lead_battle")
	if _once("leader_intro", 400.0):
		_say("early", "07_early_leader")
	if _once("snap600", 600.0):
		for i in range(8):
			_runners[order[i]]["rank600"] = i + 1
		var spread := float(leader["pos"]) - float(_runners[order[7]]["pos"])
		if spread >= 30.0:
			_say("early", "08_early_stretched")
	if _once("holdback", 700.0):
		for i in range(6, 8):
			if str(_runners[order[i]]["horse"]["style"]) == "追込":
				_say("early", "09_early_holdback")
				break
	# Mid.
	if _once("frontside", 900.0):
		_say("mid", "10_mid_frontside")
	if _once("settled", 1100.0):
		_say("mid", "11_mid_settled")
	if _once("snap1200", 1200.0):
		for i in range(8):
			_runners[order[i]]["rank1200"] = i + 1
		_say("mid", "12_mid_corner")
	# Final.
	if _once("straight", 1400.0):
		_say("final_straight", "13_final_straight")
	if _once("move", 1500.0):
		if int(leader["rank1200"]) >= 4:
			_say("final_move", "15_final_outside")
		elif int(leader["rank600"]) == 1 and int(leader["rank1200"]) == 1:
			_say("final_move", "14_final_leader")
		else:
			_say("final_move", "16_final_inside")
	if _once("200m", 1600.0):
		_say("final_200", "17_final_200m")
	if _once("100m", 1700.0):
		_say("final_100", "18_final_100m")
	# Goal: the commentary fires as the winner crosses; the field
	# keeps running so the result board gets real times.
	if not _fired.has("goal") and float(leader["finish_t"]) > 0.0:
		_fired["goal"] = true
		_flash = 1.0
		_shake = 6.0
		_goal_commentary(leader, second)


func _goal_commentary(winner: Dictionary, second: Dictionary) -> void:
	var margin := float(winner["pos"]) - float(second["pos"])
	if margin < 1.2:
		_say("goal", "22_goal_photo")
	elif margin < 4.0:
		_say("goal", "21_goal_close")
	elif int(winner["rank600"]) == 1 and int(winner["rank1200"]) == 1:
		_say("goal", "20_goal_push")
	else:
		_say("goal", "19_goal_win")
	if margin >= 25.0:
		_say("win_style", "26_win_runaway")
	elif int(winner["rank600"]) == 1:
		_say("win_style", "23_win_frontrun")
	elif str(winner["horse"]["style"]) == "追込":
		_say("win_style", "25_win_closer")
	else:
		_say("win_style", "24_win_stalker")
	if int(winner["draw"]["popularity"]) >= 6:
		_say("upset", "27_upset")
	_say("crowd", "28_crowd")
	_say("closing", "29_closing")


## Ends the race once the whole field is in, or 6 s after the winner.
## Results carry a "margin" string for the result screen's table.
func _maybe_finish() -> void:
	if not _fired.has("goal"):
		return
	var win_t := -1.0
	var all_in := true
	for r in _runners:
		if float(r["finish_t"]) > 0.0:
			win_t = float(r["finish_t"]) if win_t < 0.0 else minf(win_t, float(r["finish_t"]))
		else:
			all_in = false
	if not all_in and _clock < win_t + 6.0:
		return
	_state = "done"
	# Results: finishers by time, the rest by position.
	var done := _runners.filter(func(r: Dictionary) -> bool: return float(r["finish_t"]) > 0.0)
	done.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["finish_t"]) < float(b["finish_t"]))
	var rest := _runners.filter(func(r: Dictionary) -> bool: return float(r["finish_t"]) <= 0.0)
	rest.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["pos"]) > float(b["pos"]))
	_results = done + rest
	for i in range(_results.size()):
		var r: Dictionary = _results[i]
		if i == 0:
			r["margin"] = "%.2f" % win_t
		elif float(r["finish_t"]) > 0.0:
			r["margin"] = "+%.2f秒" % (float(r["finish_t"]) - win_t)
		else:
			r["margin"] = "大差"
	race_finished.emit(_results)


func fps_average() -> float:
	if _fps_samples.is_empty():
		return 0.0
	var sum := 0.0
	for f in _fps_samples:
		sum += float(f)
	return sum / _fps_samples.size()


# ------------------------------------------------------------------ dust

func _update_dust(dt: float) -> void:
	if _state == "run":
		for r in _runners:
			var v := float(r["vel"])
			if v < 5.0:
				continue
			_dust_acc += dt * v * 0.85
			while _dust_acc >= 1.0:
				_dust_acc -= 1.0
				if _dust.size() < 240:
					_dust.append({
						"x": float(r["pos"]) - 1.6 + _rng.randf_range(-0.5, 0.5),
						"gate": int(r["gate"]),
						"h": _rng.randf_range(0.0, 5.0),
						"vx": _rng.randf_range(-4.5, -2.0),
						"vh": _rng.randf_range(9.0, 24.0),
						"age": 0.0, "life": _rng.randf_range(0.5, 0.95),
						"size": _rng.randf_range(9.0, 15.0),
					})
	for p in _dust:
		p["age"] = float(p["age"]) + dt
		p["x"] = float(p["x"]) + float(p["vx"]) * dt
		p["h"] = float(p["h"]) + float(p["vh"]) * dt
		p["vh"] = float(p["vh"]) - 14.0 * dt
	_dust = _dust.filter(func(p: Dictionary) -> bool: return float(p["age"]) < float(p["life"]))


# ---------------------------------------------------------------- drawing

func _draw_tiled(tex: Texture2D, y: float, h: float, offset_px: float, alpha := 1.0) -> void:
	# Mirror tiling: alternate tiles are flipped, so the edges meet
	# by construction. A crossfade wrap ghosts the grandstand into
	# visible doubled slices; a mirror only reverses the scenery.
	var tw := tex.get_width() * h / tex.get_height()
	var first := int(floor(offset_px / tw))
	var x := -fmod(offset_px, tw)
	if x > 0.0:
		x -= tw
		first -= 1
	var i := 0
	while x < VIEW_W:
		if (first + i) % 2 != 0:
			draw_set_transform(_shake_off + Vector2(x + tw, y), 0.0, Vector2(-1, 1))
			draw_texture_rect(tex, Rect2(0, 0, tw, h), false, Color(1, 1, 1, alpha))
			draw_set_transform(_shake_off, 0.0, Vector2.ONE)
		else:
			draw_texture_rect(tex, Rect2(x, y, tw, h), false, Color(1, 1, 1, alpha))
		x += tw
		i += 1


func _draw() -> void:
	_shake_off = Vector2(sin(_elapsed * 91.0), cos(_elapsed * 77.0)) * _shake
	draw_set_transform(_shake_off, 0.0, Vector2.ONE)
	# Layers: stand (far, slow) -> turf (track speed) -> horses ->
	# near rail (fast, in front of the hooves).
	_draw_tiled(_tex_far, 0.0, FAR_Y, _cam_m * _px_m * 0.30)
	_draw_tiled(_tex_turf, FAR_Y, 648.0 - FAR_Y, _cam_m * _px_m)
	_draw_markers()
	_draw_dust(false)
	_draw_horses()
	_draw_dust(true)
	_draw_tiled(_tex_rail, 556.0, 118.0, _cam_m * _px_m * 1.55)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	_draw_hud()
	if _flash > 0.0:
		draw_rect(Rect2(0, 0, VIEW_W, 648), Color(1, 1, 1, _flash * 0.45))


func _draw_markers() -> void:
	var font := get_theme_default_font()
	for m in range(0, 2001, 200):
		var x := _sx(float(m))
		if x < -30.0 or x > VIEW_W + 30.0:
			continue
		if m == 1800:
			# The winning post: red/white stripes + a gold line.
			for i in range(6):
				var col := Color("#e60012") if i % 2 == 0 else Color.WHITE
				draw_rect(Rect2(x - 4, 330 + i * 44, 8, 44), col)
			draw_line(Vector2(x, 330), Vector2(x, 640), Color(1.0, 0.85, 0.3, 0.5), 2.0)
			draw_string(font, Vector2(x - 24, 322), "ゴール", HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color(1, 0.9, 0.5, 0.95))
		elif m > 0:
			draw_line(Vector2(x, 486), Vector2(x, 566), Color(1, 1, 1, 0.4), 2.0)
			draw_string(font, Vector2(x + 5, 560), "%dm" % m, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 1, 1, 0.65))


func _draw_dust(front: bool) -> void:
	for p in _dust:
		var gate := int(p["gate"])
		if (gate >= 5) != front:
			continue
		var t := float(p["age"]) / float(p["life"])
		var size := float(p["size"]) * (1.0 + t * 1.8)
		var at := Vector2(_sx(float(p["x"])), _ground_y(gate) - float(p["h"]))
		var col := Color(0.88, 0.84, 0.66, 0.30 * (1.0 - t))
		draw_texture_rect(_tex_dust, Rect2(at - Vector2(size, size) * 0.5, Vector2(size, size)), false, col)


func _draw_horses() -> void:
	if _runners.is_empty():
		return
	var font := get_theme_default_font()
	# Painter order: the far lanes (small gates) first.
	var sorted := range(8)
	for idx in sorted:
		var r: Dictionary = _runners[idx]
		var gate := int(r["gate"])
		var scale := 0.94 + (float(gate) - 1.0) * 0.017
		var w := 330.0 * scale
		var h := w * 582.0 / 1150.0
		var sx := _sx(float(r["pos"]))
		if sx < -w or sx > VIEW_W + w:
			continue
		var gy := _ground_y(gate)
		var phase := float(r["phase"])
		var v := float(r["vel"])
		var speed_k := clampf(v / 17.5, 0.0, 1.0)
		var bob := (sin(phase) * 4.5 - 2.0) * (0.25 + 0.75 * speed_k)
		var pitch := sin(phase + 0.7) * 0.030 * speed_k
		var tex: Texture2D = _tex_horses[gate - 1]
		# Ground shadow (stays on the turf while the body bounces).
		draw_texture_rect(_tex_shadow,
			Rect2(sx - w * 0.42, gy - 11, w * 0.84, 22), false, Color(0, 0, 0, 0.40))
		var center := Vector2(sx, gy - h * 0.52 + bob)
		# Afterimages at full stretch (unrotated rects; the ghost of a
		# gallop does not need the pitch).
		if v > 15.3:
			for k in range(2):
				var back := 0.55 * float(k + 1)
				var a := 0.13 if k == 0 else 0.06
				var gc := Vector2(_sx(float(r["pos"]) - back), center.y)
				draw_texture_rect(tex, Rect2(gc - Vector2(w, h) * 0.5, Vector2(w, h)), false, Color(1, 1, 1, a))
		# Speed streaks behind the front runners in the straight.
		if v > 15.3 and _leader_pos() > 1350.0:
			for i in range(3):
				var yy := gy - h * (0.30 + 0.22 * float(i))
				var x0 := _sx(float(r["pos"]) - 6.5)
				var x1 := _sx(float(r["pos"]) - 2.4)
				draw_line(Vector2(x0, yy), Vector2(x1, yy), Color(1, 1, 1, 0.10), 3.0)
		# The horse: pivot at the body centre, feet near the ground.
		# draw_texture paints at native size, so the transform carries
		# the scale from texture pixels to the display size.
		var tex_size := tex.get_size()
		draw_set_transform(center, pitch, Vector2(w / tex_size.x, h / tex_size.y))
		draw_texture(tex, -tex_size * 0.5)
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		# The number chip rides on the saddle cloth.
		var saddle := center + Vector2(0.045 * w, -0.10 * h)
		draw_style_box(_chip_box, Rect2(saddle - Vector2(13, 13), Vector2(26, 26)))
		var num_col := Color(0.08, 0.08, 0.08)
		draw_string(font, saddle + Vector2(-13, 7), str(gate), HORIZONTAL_ALIGNMENT_CENTER, 26, 19, num_col)
		# Name tag above the back.
		var name := str(r["horse"]["name"])
		var tw := font.get_string_size(name, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		var tag := Rect2(sx - tw * 0.5 - 7, gy - h - 26 + bob * 0.5 - float(gate % 2) * 24.0, tw + 14, 21)
		draw_style_box(_pill_box, tag)
		draw_string(font, tag.position + Vector2(7, 15), name, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(1, 1, 1, 0.92))


func _draw_hud() -> void:
	var font := get_theme_default_font()
	# Header shade behind the title / clock labels.
	draw_rect(Rect2(10, 6, 660, 46), Color(0.02, 0.06, 0.03, 0.55))
	draw_rect(Rect2(862, 6, 280, 46), Color(0.02, 0.06, 0.03, 0.55))
	if _subtitle.text != "":
		draw_style_box(_pill_box, Rect2(116, 498, 920, 46))
	if _runners.is_empty():
		return
	# Live ranking, dressed to sit inside the racecourse world.
	draw_rect(RANK_RECT, Color(0.03, 0.09, 0.05, 0.88))
	draw_rect(RANK_RECT, Color("#d9a441"), false, 1.5)
	draw_string(font, Vector2(RANK_RECT.position.x + 14, RANK_RECT.position.y + 30), "現在の順位", HORIZONTAL_ALIGNMENT_LEFT, -1, 19, Color("#f2d492"))
	var leader := _leader_pos()
	var remain := maxf(DIST - leader, 0.0)
	draw_string(font, Vector2(RANK_RECT.position.x + 150, RANK_RECT.position.y + 30), "残り %.0fm" % remain, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(1, 1, 1, 0.75))
	var order := _order()
	for i in range(8):
		var r: Dictionary = _runners[order[i]]
		var y := RANK_RECT.position.y + 62 + i * 40
		var gate := int(r["gate"])
		draw_rect(Rect2(RANK_RECT.position.x + 14, y - 15, 20, 20), Color(str(StarHorseData.FRAME_COLORS[gate - 1])))
		var gap := leader - float(r["pos"])
		var text := "%d. %s" % [i + 1, str(r["horse"]["name"])]
		if float(r["finish_t"]) > 0.0:
			text += " GOAL"
		elif i > 0:
			text += " (-%.0f)" % gap
		draw_string(font, Vector2(RANK_RECT.position.x + 42, y), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color.WHITE)
	# Leader progress along the bottom of the turf.
	var prog := Rect2(12, 640, 1128, 5)
	draw_rect(prog, Color(1, 1, 1, 0.16))
	prog.size.x *= clampf(leader / DIST, 0.0, 1.0)
	draw_rect(prog, Color("#d9a441"))
