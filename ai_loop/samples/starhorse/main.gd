extends Control
## Star Horse Farm -- U.ZU Engine sample. B-1329 built the comparison
## mini-version (farm / entries / race); B-1330 raises it to the best
## the engine's current assets can do:
##
##   title    sunset key visual, outlined logo, appear motion (spec)
##   farm     morning-stable art with the kit table/detail embedded
##   entries  racecourse art with the race card embedded
##   race     side-view 2.5D broadcast (race.gd), commentary-synced
##   result   finishing order as a kit table + the winner's gallop
##
## The three menu screens are built from JSON specs by
## ai_loop/ui_tool.gd (specs/, see make_specs.py) and dressed by the
## racing world theme; main.gd owns the navigation, the transitions
## (UZUUIJuice.transition everywhere), the art parallax and the fx
## wiring (dust over the art, bursts on focus, flashes on press --
## the B-1322 showcase pattern). BGM ("The Hero's Journey", the same
## file as the Godot original) loops on the menu screens on its own
## bus and stops for the race, where the fanfare and the commentary
## own the soundscape.
##
## Machine modes (user args):
##   --starhorse-autoplay <out.json>  headless: run one race at high
##       speed with a fixed seed, write {results, commentary, fps}
##       as JSON and quit. Used by verify_race.py.

const FONT := preload("res://art/game_font_jp.ttf")
const RaceScreenScene := preload("res://race.gd")
const CommentaryScene := preload("res://commentary.gd")
const ResultScreenScene := preload("res://result.gd")
const FxLayer := preload("res://fx_layer.gd")

const DUST := {"title": 16, "farm": 14, "entries": 10}

var _commentary: Commentary
var _bgm: AudioStreamPlayer
var _current: Control
var _screen := ""
var _race: RaceScreen
var _result: ResultScreen
var _fx_front: Control
var _art_bg: Control
var _art_shade: Control
var _art_bg_base := Vector2.ZERO
var _art_shade_base := Vector2.ZERO
var _art_t := 0.0
var _switching := false
var _autoplay_out := ""
var _autoplay_done := false


func _ready() -> void:
	theme = UZUUI.create_world_theme("racing", {"font": FONT})
	var bg := ColorRect.new()
	bg.color = Color("#0b1a10")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	_commentary = CommentaryScene.new()
	add_child(_commentary)
	_bgm = AudioStreamPlayer.new()
	_bgm.bus = "BGM"
	var bgm_stream: AudioStreamMP3 = load("res://audio/bgm_hero.mp3")
	bgm_stream.loop = true
	_bgm.stream = bgm_stream
	add_child(_bgm)
	_fx_front = FxLayer.new()
	add_child(_fx_front)

	var args := OS.get_cmdline_user_args()
	var i := args.find("--starhorse-autoplay")
	if i >= 0 and i + 1 < args.size():
		_autoplay_out = args[i + 1]
		_commentary.fast = true
		goto_race()
		_race.time_scale = 30.0
		_race.seed_value = 1329
		_race.start_race()
		return
	goto("title")
	_bgm.play()


func _process(delta: float) -> void:
	# Art parallax: the backdrop drifts one way, the shade answers
	# with a smaller drift the other way (the B-1325 pattern).
	if _art_bg == null or not is_instance_valid(_art_bg):
		return
	_art_t += delta
	if _art_bg:
		_art_bg.position = _art_bg_base + Vector2(sin(_art_t * 0.16) * 9.0, sin(_art_t * 0.11) * 4.0)
	if _art_shade:
		_art_shade.position = _art_shade_base + Vector2(sin(_art_t * 0.16 + PI) * 4.0, 0.0)


## Shows a new screen over the current one with the shared
## transition, then frees the old screen.
func _show_screen(scr: Control, name: String) -> void:
	_race = scr if scr is RaceScreen else null
	_result = scr if scr is ResultScreen else null
	_screen = name
	if _current == null:
		add_child(scr)
		move_child(scr, _fx_front.get_index())
		_current = scr
		_bind_art(scr, name)
		return
	_switching = true
	var old := _current
	add_child(scr)
	move_child(scr, _fx_front.get_index())
	_current = scr
	_bind_art(scr, name)
	_fx_front.slash(Color(1, 1, 1, 0.9))
	var wm := scr.find_child("WorldMotion", true, false)
	if wm:
		wm.set("open_on_ready", false)
	await get_tree().process_frame
	await get_tree().process_frame
	UZUUIJuice.cancel_all()
	UZUUIJuice.transition(old, scr, 0.28, "ease_in", 1.0)
	await get_tree().create_timer(0.34).timeout
	old.queue_free()
	_switching = false


func _bind_art(scr: Control, name: String) -> void:
	_art_bg = scr.get_node_or_null("BgArt") as Control
	_art_shade = scr.get_node_or_null("Shade") as Control
	if _art_bg:
		_art_bg_base = _art_bg.position
	if _art_shade:
		_art_shade_base = _art_shade.position
	# Dust drifts over the art but under the panels: the back fx
	# layer goes into the screen itself, right after the shade.
	if DUST.has(name):
		var fx := FxLayer.new()
		fx.set("dust", int(DUST[name]))
		fx.set("dust_color", Color(1, 0.95, 0.85, 0.4))
		scr.add_child(fx)
		var anchor_node: Node = _art_shade if _art_shade else _art_bg
		if anchor_node:
			scr.move_child(fx, anchor_node.get_index() + 1)
	_wire_fx(scr)


## Focus bursts and press flashes for every button of a screen
## (the B-1322 wiring; colours stay warm for the racing world).
func _wire_fx(scr: Control) -> void:
	var stack: Array = [scr]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		for child in node.get_children():
			stack.append(child)
		var b := node as Button
		if b == null:
			continue
		b.focus_entered.connect(func() -> void:
			var r := b.get_global_rect()
			_fx_front.burst(r.position + Vector2(14, r.size.y * 0.5), Color(1, 0.9, 0.6, 0.9)))
		b.pressed.connect(func() -> void:
			var r := b.get_global_rect()
			_fx_front.flash(b.get_global_transform(), b.size, Color.WHITE)
			_fx_front.burst(r.get_center(), Color(1, 0.85, 0.5, 0.95)))


func goto(name: String) -> void:
	if _switching:
		return
	var packed := load("res://screens/%s.tscn" % name) as PackedScene
	if packed == null:
		push_error("starhorse: missing built screen %s (run uzu.py ui on specs/%s.json)" % [name, name])
		return
	var scr := packed.instantiate() as Control
	_show_screen(scr, name)
	if name == "title":
		_wire_title(scr)
	else:
		_wire_data(scr, name)
		_wire_nav(scr, name)


func goto_race() -> void:
	if _switching:
		return
	_bgm.stop()
	var race := RaceScreenScene.new()
	race.commentary = _commentary
	race.set_anchors_preset(Control.PRESET_FULL_RECT)
	race.exit_requested.connect(func() -> void:
		goto("farm")
		_bgm.play())
	race.race_finished.connect(_on_race_finished)
	_show_screen(race, "race")


func goto_result(results: Array) -> void:
	if _switching:
		return
	var scr := ResultScreenScene.new()
	scr.set_anchors_preset(Control.PRESET_FULL_RECT)
	scr.back_to_farm.connect(func() -> void:
		goto("farm")
		_bgm.play())
	scr.rematch.connect(func() -> void:
		goto_race()
		_race.start_race())
	_show_screen(scr, "result")
	scr.show_results(results)


func _on_race_finished(results: Array) -> void:
	if _autoplay_out != "":
		if _autoplay_done:
			return
		_autoplay_done = true
		# Let the commentary queue drain so the log is complete.
		while _commentary.is_speaking():
			await get_tree().create_timer(0.1).timeout
		var payload := {
			"results": results.map(func(r: Dictionary) -> Dictionary:
				return {"gate": int(r["gate"]), "name": str(r["horse"]["name"]),
					"finish_t": float(r["finish_t"]), "margin": str(r.get("margin", ""))}),
			"commentary": _commentary.event_log,
			"fps_avg": snappedf(_race.fps_average(), 0.1),
		}
		var f := FileAccess.open(_autoplay_out, FileAccess.WRITE)
		f.store_string(JSON.stringify(payload, "\t"))
		f.close()
		get_tree().quit()
		return
	goto_result(results)


func _wire_title(scr: Control) -> void:
	var start := scr.get_node_or_null("StartBtn") as Button
	if start:
		start.pressed.connect(func() -> void: goto("farm"))
		start.grab_focus.call_deferred()
	var race := scr.get_node_or_null("RaceBtn") as Button
	if race:
		race.pressed.connect(func() -> void: goto("entries"))


## Table <-> detail-panel wiring, the same shape as the B-1326
## showcase: rows carry a row_index meta; selection and focus both
## drive UZUUI.set_detail_panel.
func _wire_data(scr: Control, screen_name: String) -> void:
	var table := scr.get_node_or_null("Table") as Control
	var detail := scr.get_node_or_null("Detail") as Control
	if table == null or detail == null:
		return
	var initial := 2 # ホワイトオーシャン (farm row / entries gate 3)
	for child in table.get_children():
		var b := child as Button
		if b != null and b.has_meta("row_index"):
			var idx := int(b.get_meta("row_index"))
			b.pressed.connect(func() -> void:
				UZUUI.select_table_row(table, idx)
				_set_detail(detail, screen_name, idx))
			b.focus_entered.connect(func() -> void:
				UZUUI.select_table_row(table, idx)
				_set_detail(detail, screen_name, idx))
	UZUUI.select_table_row(table, initial)
	_set_detail(detail, screen_name, initial)
	var row := UZUUI.select_table_row(table, initial) as Control
	if row != null:
		row.grab_focus.call_deferred()


func _set_detail(detail: Control, screen_name: String, idx: int) -> void:
	if screen_name == "farm":
		UZUUI.set_detail_panel(detail, StarHorseData.farm_record(idx))
	else:
		UZUUI.set_detail_panel(detail, StarHorseData.entries_record(idx + 1))


func _wire_nav(scr: Control, screen_name: String) -> void:
	var commands := scr.get_node_or_null("Commands")
	if commands == null:
		return
	for child in commands.get_children():
		var b := child as Button
		if b == null:
			continue
		if screen_name == "farm" and b.text == "レース登録":
			b.pressed.connect(func() -> void: goto("entries"))
		elif screen_name == "entries" and b.text == "レース映像":
			b.pressed.connect(func() -> void:
				goto_race()
				_race.start_race())
		elif screen_name == "entries" and b.text == "戻る":
			b.pressed.connect(func() -> void: goto("farm"))
