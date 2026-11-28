extends Node3D
## Title screen: a U.ZU Picture (one illustration + depth map, turned into a
## lit parallax relief by the engine) with the game title over it.
## Any interact input starts the game.
##
## The overlay is a declarative UI build (B-1301): ui/title_ui.json is the
## source, ui/title_ui.tscn is generated from it with
##   python3 ai_loop/uzu.py ui <this project> --spec ui/title_ui.json
## It uses the wafu world theme (B-1307), the same world as the game's UI,
## and its UZUUIWorld opens the plaques with the world's quiet motion.

const InputSetup := preload("res://input_setup.gd")
const FONT := preload("res://art/game_font.ttf")
const MAIN_SCENE := "res://main.tscn"

var _hint: Control # The start prompt plaque; it pulses quietly until pressed.
var _loading_label: Label
var _loading := false
var _audio: UZUGameAudio # B-1704: title click through the Phase 17 helper.

func _ready() -> void:
	InputSetup.setup()
	_audio = UZUGameAudio.new()
	add_child(_audio)
	_audio.register_event(&"ui_click", PackedStringArray(["res://audio/sfx/ui_click.wav"]), {"base_volume_db": -3.0, "pitch_jitter": 0.03})
	# Fallback: the flat illustration on a quad behind the UZUPicture relief,
	# so the title still shows the art on GPUs/browsers where the picture's
	# shaders do not run (seen on iOS Safari).
	var flat := Sprite3D.new()
	flat.texture = load("res://title/art.png")
	flat.pixel_size = 0.0354
	flat.position = Vector3(0, 0, -0.6)
	add_child(flat)
	var layer := CanvasLayer.new()
	add_child(layer)
	var packed := load("res://ui/title_ui.tscn") as PackedScene
	if packed:
		var ui := packed.instantiate() as Control
		layer.add_child(ui)
		# Taps anywhere must reach _unhandled_input: nothing in the overlay
		# may swallow them.
		ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
		for c in ui.find_children("*", "Control", true, false):
			(c as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE
		_hint = ui.get_node_or_null("Hint") as Control
	else:
		# The generated scene is committed next to its spec; this is only a
		# guard so the title never comes up blank.
		var title := Label.new()
		title.text = "灯りの欠片"
		title.add_theme_font_override("font", FONT)
		title.add_theme_font_size_override("font_size", 64)
		title.set_anchors_preset(Control.PRESET_CENTER_TOP)
		title.position = Vector2(-160, 90)
		title.size = Vector2(320, 80)
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		layer.add_child(title)
	# Shown the moment a start input lands, while the village loads on a
	# loader thread: without it the title just sits still for seconds and
	# reads as a freeze (owner playtest, 2026-11-20).
	_loading_label = Label.new()
	_loading_label.text = "読み込み中…"
	_loading_label.add_theme_font_override("font", FONT)
	_loading_label.add_theme_font_size_override("font_size", 30)
	_loading_label.add_theme_color_override("font_color", Color(0.98, 0.94, 0.85))
	_loading_label.add_theme_color_override("font_shadow_color", Color(0.05, 0.04, 0.03, 0.9))
	_loading_label.add_theme_constant_override("shadow_offset_x", 2)
	_loading_label.add_theme_constant_override("shadow_offset_y", 2)
	_loading_label.set_anchors_preset(Control.PRESET_CENTER)
	_loading_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	# Offsets are relative to the centre anchor point; position would be a
	# parent-space coordinate and park the label half off-screen (the same
	# mistake the clear panel had).
	_loading_label.offset_left = -160
	_loading_label.offset_top = 150
	_loading_label.offset_right = 160
	_loading_label.offset_bottom = 194
	_loading_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_loading_label.visible = false
	layer.add_child(_loading_label)
	# Warm the loader while the title is on screen: the main scene's bytes
	# are read in the background here, so a start press only pays for the
	# (frame-split) build, not the read as well. _process picks the load
	# up when the press lands, whatever state it is in by then.
	ResourceLoader.load_threaded_request(MAIN_SCENE)

func _process(_delta: float) -> void:
	if _loading:
		# Poll the threaded load; the title keeps drawing (and this label
		# keeps showing) until the main scene is ready to take over.
		match ResourceLoader.load_threaded_get_status(MAIN_SCENE):
			ResourceLoader.THREAD_LOAD_LOADED:
				var packed := ResourceLoader.load_threaded_get(MAIN_SCENE) as PackedScene
				_loading = false
				if packed:
					get_tree().change_scene_to_packed(packed)
				else:
					get_tree().change_scene_to_file(MAIN_SCENE)
			ResourceLoader.THREAD_LOAD_FAILED, ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
				_loading = false
				get_tree().change_scene_to_file(MAIN_SCENE)
	elif _hint:
		# The start prompt breathes quietly so it reads as "press me",
		# not as another line of help text.
		var pulse := 0.62 + 0.38 * sin(Time.get_ticks_msec() / 420.0)
		_hint.modulate.a = pulse

func _input(event: InputEvent) -> void:
	# Keys, taps and clicks all start the game (phones have no keyboard).
	# _input, not _unhandled_input: it runs before GUI consumption, so a
	# click starts the game even if an overlay Control would swallow it
	# before _unhandled_input (seen in the Web build: clicks did nothing).
	if _loading:
		return
	var start := event.is_action_pressed("interact")
	if event is InputEventScreenTouch and (event as InputEventScreenTouch).pressed:
		start = true
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		start = true
	if start:
		_loading = true
		if _audio:
			_audio.play_event(&"ui_click", Vector3.ZERO)
		if _hint:
			_hint.modulate.a = 1.0
			_hint.visible = false
		_loading_label.visible = true
		# The load was already requested in _ready (the warm-up above); only
		# request here when that never got going.
		if ResourceLoader.load_threaded_get_status(MAIN_SCENE) == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
			if ResourceLoader.load_threaded_request(MAIN_SCENE) != OK:
				_loading = false
				get_tree().change_scene_to_file(MAIN_SCENE)
