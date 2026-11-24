extends Control
## Star Horse Farm -- U.ZU Engine sample (B-1329), the comparison
## mini-version of the owner's Godot original. Three screens:
##
##   farm     title + owned-horses table (kit spec: specs/farm.json)
##   entries  the race card, 8 runners (kit spec: specs/entries.json)
##   race     the 2D simulation (race.gd) with phase-synced commentary
##
## The farm/entries screens are built from JSON specs by
## ai_loop/ui_tool.gd and dressed by the racing world theme; only the
## table/detail wiring and the navigation live here. BGM ("The Hero's
## Journey", the same file as the original) loops on the farm/entries
## screens on its own bus and stops for the race, where the fanfare
## and the commentary own the soundscape.
##
## Machine modes (user args):
##   --starhorse-autoplay <out.json>  headless: run one race at high
##       speed with a fixed seed, write {results, commentary, fps}
##       as JSON and quit. Used by verify_race.py.

const FONT := preload("res://art/game_font_jp.ttf")
const RaceScreenScene := preload("res://race.gd")
const CommentaryScene := preload("res://commentary.gd")

var _commentary: Commentary
var _bgm: AudioStreamPlayer
var _current: Control
var _screen := ""
var _race: RaceScreen
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
	goto("farm")
	_bgm.play()


func goto(name: String) -> void:
	if _current != null:
		_current.queue_free()
		_current = null
	_race = null
	_screen = name
	if name == "race":
		goto_race()
		return
	var packed := load("res://screens/%s.tscn" % name) as PackedScene
	if packed == null:
		push_error("starhorse: missing built screen %s (run uzu.py ui on specs/%s.json)" % [name, name])
		return
	_current = packed.instantiate()
	add_child(_current)
	_wire_data(_current, name)
	_wire_nav(_current, name)


func goto_race() -> void:
	if _current != null:
		_current.queue_free()
		_current = null
	_screen = "race"
	_bgm.stop()
	_race = RaceScreenScene.new()
	_race.commentary = _commentary
	_race.set_anchors_preset(Control.PRESET_FULL_RECT)
	_current = _race
	add_child(_race)
	_race.exit_requested.connect(func() -> void:
		goto("farm")
		_bgm.play())
	_race.race_finished.connect(_on_race_finished)


func _on_race_finished(_results: Array) -> void:
	if _autoplay_out == "" or _autoplay_done:
		return
	_autoplay_done = true
	# Let the commentary queue drain so the log is complete.
	while _commentary.is_speaking():
		await get_tree().create_timer(0.1).timeout
	var payload := {
		"results": _results.map(func(r: Dictionary) -> Dictionary:
			return {"gate": int(r["gate"]), "name": str(r["horse"]["name"]),
				"finish_t": float(r["finish_t"])}),
		"commentary": _commentary.event_log,
		"fps_avg": snappedf(_race.fps_average(), 0.1),
	}
	var f := FileAccess.open(_autoplay_out, FileAccess.WRITE)
	f.store_string(JSON.stringify(payload, "\t"))
	f.close()
	get_tree().quit()


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
