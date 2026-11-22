extends Control
## B-1317 showcase: one screen whose panel appears, whose button is caught
## mid-press and whose gauge is mid value_change, in the motion of one
## world. Run with a world and a phase after "--":
##   godot --path . -- <world> <start|mid|end>
## The phase pins every animation to that fraction of its own duration
## with UZUUIJuice.seek_animation on every frame, so the Movie Maker
## frames show exactly that moment (no real-time waiting).
## The font is the checked JP font of the B-1316 rule (look_samples/README.md).

const FONT := preload("res://art/game_font.ttf")
const FRACTIONS := {"start": 0.0, "mid": 0.5, "end": 1.0}

var world := "persona"
var fraction := 0.5
var started := false
var runs: Array = []  # [{control, duration}] started on the first frame.


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		world = args[0]
	if args.size() > 1:
		fraction = FRACTIONS.get(args[1], 0.5)
	theme = UZUUI.create_world_theme(world, {"font": FONT})

	var bg := ColorRect.new()
	bg.color = Color(0.07, 0.07, 0.09) if world == "persona" else Color(0.13, 0.12, 0.11)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var caption := Label.new()
	caption.text = "%s / %s" % [world, {"start": "出現直後", "mid": "中間", "end": "完了"}[args[1] if args.size() > 1 else "mid"]]
	caption.position = Vector2(28, 20)
	add_child(caption)

	# The panel that appears: a framed box with a title and a line of text.
	var panel := PanelContainer.new()
	panel.name = "QuestPanel"
	panel.position = Vector2(120, 110)
	panel.custom_minimum_size = Vector2(560, 300)
	add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 16)
	# B-1315 containment: in a skew world the frame leans across the
	# panel's rows (travel 79 px over a 316 px panel), so the content is
	# inset past the slant at its own rows -- the same fix the B-1315
	# sample screens apply. Other shapes keep the frame's own padding.
	var frame_options: Dictionary = UZUUI.get_world_options(world).get("frame", {})
	if String(frame_options.get("shape", "")) == "skew":
		var margin := MarginContainer.new()
		margin.add_theme_constant_override("margin_left", 68)
		margin.add_theme_constant_override("margin_right", 68)
		margin.add_child(box)
		panel.add_child(margin)
	else:
		panel.add_child(box)
	var title := UZUUI.make_label("クエスト受注", "title")
	box.add_child(title)
	var body := UZUUI.make_label("灯りの欠片を三つ集めてきておくれ。", "body")
	box.add_child(body)
	var gauge_label := UZUUI.make_label("HP", "caption")
	box.add_child(gauge_label)
	var gauge := UZUUI.make_gauge(10, 100, 10)
	gauge.name = "HpGauge"
	gauge.custom_minimum_size = Vector2(0, 28)
	box.add_child(gauge)

	# The button caught mid-press.
	var button := UZUUI.make_button("たたかう")
	button.name = "FightButton"
	button.position = Vector2(760, 180)
	button.custom_minimum_size = Vector2(240, 72)
	add_child(button)

	runs = [
		{"control": panel, "motion": "appear", "options": {"world": world}},
		{"control": button, "motion": "press", "options": {"world": world}},
		{"control": gauge, "motion": "value_change", "options": {"world": world, "to": 90.0}},
	]


func _process(_delta: float) -> void:
	if not started:
		started = true
		for run in runs:
			UZUUIJuice.play_motion(run.control, run.motion, run.options)
			run["duration"] = float(UZUUIJuice.get_animation_state(run.control).get("duration", 0.25))
	# Pin every running animation to the phase's moment, deferred: the
	# juice runtime advances animations in its own _process, so the pin
	# must land after it, inside the same frame. Once an animation has
	# finished (the "end" phase) seek reports false and the exact end
	# state stays, which is what the shot should show.
	_pin.call_deferred()


func _pin() -> void:
	for run in runs:
		UZUUIJuice.seek_animation(run.control, run.duration * fraction)
