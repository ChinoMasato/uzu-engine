class_name RaceScreen
extends Control
## The race screen (B-1329): a deliberately simple 2D simulation --
## eight silk-coloured runners on a straight course -- whose real job
## is the phase machine that drives the commentary. The sim records
## snapshots (ranks at 600m / 1200m, margins at the goal) and the
## commentary lines are chosen from those snapshots, mirroring the
## mapping table in audio/voice/README.md:
##
##   pre (fanfare -> gate-in -> ready) -> start (+clean/late note)
##   -> early (lead battle / leader / stretched / hold-back)
##   -> mid (front side / settled / corner)
##   -> final straight -> the move (holds on / outside / inside)
##   -> 200m -> 100m -> goal (win / push / close / photo)
##   -> win style (front-run / stalker / closer / runaway)
##   -> upset (long-shot winner) -> crowd -> closing.
##
## Everything is deterministic for a given `seed`, so the headless
## verifier can assert the firing order from the commentary log.

signal race_finished(results: Array)
signal exit_requested

const DIST := 1800.0
const TRACK_RECT := Rect2(12, 66, 800, 470)
const RANK_RECT := Rect2(824, 66, 316, 470)

var commentary: Commentary
var time_scale := 1.0
var seed_value := 1329

var _rng := RandomNumberGenerator.new()
var _runners: Array = [] # per gate: {data, draw, pos, delay, wobble, finish_t}
var _state := "idle" # idle | pre | run | done
var _clock := 0.0 # seconds since the gate opened (negative in pre)
var _fired := {}
var _results: Array = []
var _fps_samples: Array = []
var _fps_timer := 0.0

var _phase_label: Label
var _clock_label: Label
var _subtitle: Label
var _result_panel: PanelContainer
var _result_text: RichTextLabel
var _fanfare: AudioStreamPlayer


func _ready() -> void:
	_phase_label = _make_label(24, 14, 30)
	add_child(_phase_label)
	_clock_label = _make_label(880, 16, 24)
	_clock_label.size = Vector2(248, 34)
	_clock_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	add_child(_clock_label)
	_subtitle = _make_label(24, 556, 22)
	_subtitle.size = Vector2(1104, 34)
	_subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_subtitle)
	_fanfare = AudioStreamPlayer.new()
	_fanfare.bus = "BGM"
	_fanfare.stream = load("res://audio/fanfare.mp3")
	add_child(_fanfare)
	_build_result_panel()
	if commentary != null:
		commentary.line_changed.connect(func(text: String) -> void: _subtitle.text = text)


func _make_label(x: int, y: int, font_size: int) -> Label:
	var l := Label.new()
	l.position = Vector2(x, y)
	l.size = Vector2(700, 40)
	l.add_theme_font_size_override("font_size", font_size)
	return l


func _build_result_panel() -> void:
	_result_panel = PanelContainer.new()
	_result_panel.position = Vector2(276, 110)
	_result_panel.size = Vector2(600, 400)
	_result_panel.visible = false
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	_result_panel.add_child(v)
	var title := Label.new()
	title.text = "レース結果 — %s" % StarHorseData.RACE_NAME
	title.add_theme_font_size_override("font_size", 26)
	v.add_child(title)
	_result_text = RichTextLabel.new()
	_result_text.fit_content = true
	_result_text.custom_minimum_size = Vector2(560, 270)
	_result_text.add_theme_font_size_override("normal_font_size", 21)
	v.add_child(_result_text)
	var back := Button.new()
	back.text = "牧場へ戻る"
	back.pressed.connect(func() -> void: exit_requested.emit())
	v.add_child(back)
	add_child(_result_panel)


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
			"jitter": 0.0, "finish_t": -1.0,
			"rank600": 0, "rank1200": 0,
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
	_result_panel.visible = false
	_phase_label.text = "中山11R %s（芝 %dm）" % [StarHorseData.RACE_NAME, StarHorseData.RACE_DISTANCE]
	_fanfare.play()


func _process(delta: float) -> void:
	if _state != "pre" and _state != "run":
		return
	var dt := delta * time_scale
	_clock += dt
	_fps_timer += delta
	if _fps_timer >= 1.0:
		_fps_timer = 0.0
		_fps_samples.append(Engine.get_frames_per_second())
	if _state == "pre":
		_pre_events()
		if _clock >= 0.0:
			_state = "run"
			_say("start", "03_start")
	else:
		_step(dt)
		_run_events()
		_maybe_finish()
	_clock_label.text = "%.1f" % maxf(_clock, 0.0)
	queue_redraw()


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
		r["pos"] = float(r["pos"]) + v * dt
		if float(r["finish_t"]) < 0.0 and float(r["pos"]) >= DIST:
			r["finish_t"] = _clock


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
	var lines := PackedStringArray()
	for i in range(_results.size()):
		var r: Dictionary = _results[i]
		var gap := ""
		if i == 0:
			gap = "%.2f" % win_t
		elif float(r["finish_t"]) > 0.0:
			gap = "+%.2f秒" % (float(r["finish_t"]) - win_t)
		else:
			gap = "大差"
		lines.append("%d着  %d番 %s（%s）  %s" % [i + 1, int(r["gate"]), str(r["horse"]["name"]), str(r["draw"]["jockey"]), gap])
	_result_text.text = "\n".join(lines)
	_result_panel.visible = true
	race_finished.emit(_results)


func fps_average() -> float:
	if _fps_samples.is_empty():
		return 0.0
	var sum := 0.0
	for f in _fps_samples:
		sum += float(f)
	return sum / _fps_samples.size()


# ---------------------------------------------------------------- drawing

func _to_x(pos: float, cam: float, scale: float) -> float:
	return TRACK_RECT.position.x + (pos - cam) * scale



func _draw() -> void:
	if _runners.is_empty():
		return
	var font := get_theme_default_font()
	var font_size := 15
	# Track: turf bands, lanes, distance markers; camera follows leader.
	draw_rect(Rect2(0, 54, 1152, 594), Color("#0b1a10"))
	draw_rect(TRACK_RECT, Color("#2e6b34"))
	var leader := _leader_pos()
	var cam := clampf(leader - 130.0, -50.0, DIST - 330.0)
	var scale := TRACK_RECT.size.x / 430.0
	# Distance markers every 200 m.
	for m in range(0, 2001, 200):
		var x: float = _to_x(float(m), cam, scale)
		if x >= TRACK_RECT.position.x and x <= TRACK_RECT.end.x:
			draw_line(Vector2(x, TRACK_RECT.position.y), Vector2(x, TRACK_RECT.end.y), Color(1, 1, 1, 0.18), 1.0)
			draw_string(font, Vector2(x + 3, TRACK_RECT.end.y - 6), "%dm" % m, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 1, 1, 0.55))
	# Goal line.
	var gx: float = _to_x(DIST, cam, scale)
	if gx >= TRACK_RECT.position.x and gx <= TRACK_RECT.end.x:
		draw_line(Vector2(gx, TRACK_RECT.position.y), Vector2(gx, TRACK_RECT.end.y), Color("#ffd94d"), 3.0)
	var lane_h := TRACK_RECT.size.y / 8.0
	for i in range(8):
		var y := TRACK_RECT.position.y + lane_h * i
		draw_line(Vector2(TRACK_RECT.position.x, y + lane_h), Vector2(TRACK_RECT.end.x, y + lane_h), Color(1, 1, 1, 0.25), 1.0)
		draw_string(font, Vector2(TRACK_RECT.position.x + 4, y + 18), str(i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 1, 1, 0.6))
	# Horses, back lanes first.
	for gate in range(1, 9):
		var r: Dictionary = _runners[gate - 1]
		var x: float = _to_x(float(r["pos"]), cam, scale)
		if x < TRACK_RECT.position.x - 70.0 or x > TRACK_RECT.end.x + 10.0:
			continue
		var cy := TRACK_RECT.position.y + lane_h * (gate - 1) + lane_h * 0.5
		var silk := Color(str(StarHorseData.FRAME_COLORS[gate - 1]))
		var body := Rect2(x - 30, cy - 13, 52, 26)
		draw_rect(body, silk, true)
		draw_rect(body, Color(0, 0, 0, 0.55), false, 1.5)
		draw_circle(Vector2(x + 28, cy - 4), 8.0, silk)
		draw_circle(Vector2(x + 28, cy - 4), 8.0, Color(0, 0, 0, 0.35), false, 1.0)
		var num_col := Color(0.08, 0.08, 0.08) if silk.get_luminance() > 0.45 else Color.WHITE
		draw_string(font, Vector2(x - 16, cy + 6), str(gate), HORIZONTAL_ALIGNMENT_LEFT, -1, 18, num_col)
		draw_string(font, Vector2(x - 30, cy - 20), str(r["horse"]["name"]), HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.WHITE)
	# Leader progress.
	var prog := Rect2(TRACK_RECT.position.x, TRACK_RECT.end.y + 4, TRACK_RECT.size.x, 6)
	draw_rect(prog, Color(1, 1, 1, 0.15))
	prog.size.x *= clampf(leader / DIST, 0.0, 1.0)
	draw_rect(prog, Color("#d9a441"))
	_draw_ranking(font)


func _draw_ranking(font: Font) -> void:
	draw_rect(RANK_RECT, Color(0.04, 0.09, 0.05, 0.92))
	draw_rect(RANK_RECT, Color("#d9a441"), false, 1.5)
	draw_string(font, Vector2(RANK_RECT.position.x + 14, RANK_RECT.position.y + 30), "現在の順位", HORIZONTAL_ALIGNMENT_LEFT, -1, 19, Color("#f2d492"))
	var order := _order()
	var leader := _leader_pos()
	for i in range(8):
		var r: Dictionary = _runners[order[i]]
		var y := RANK_RECT.position.y + 62 + i * 48
		var gate := int(r["gate"])
		draw_rect(Rect2(RANK_RECT.position.x + 14, y - 16, 22, 22), Color(str(StarHorseData.FRAME_COLORS[gate - 1])))
		var gap := leader - float(r["pos"])
		var text := "%d. %s" % [i + 1, str(r["horse"]["name"])]
		if i > 0:
			text += "  (-%.0fm)" % gap
		if float(r["finish_t"]) > 0.0:
			text += " GOAL"
		draw_string(font, Vector2(RANK_RECT.position.x + 44, y), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color.WHITE)
	# Subtitle bar.
	draw_rect(Rect2(12, 546, 1128, 46), Color(0, 0, 0, 0.72))
