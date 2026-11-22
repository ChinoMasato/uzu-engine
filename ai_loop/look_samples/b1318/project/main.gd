extends Control
## B-1318 showcase: one static screen per world (no motion), built to
## compare frame generations before/after the layering work and the
## skew wedge fix. Run with a world after "--":
##   godot --path . -- <wafu|persona> [frames_out_dir]
## With a frames directory, the world's frame texture and a
## layers-at-full-strength variant are saved there as PNGs (on a binary
## without B-1318 the layer keys are ignored, so the "before" run saves
## the plain frame twice — that is the honest baseline).
## The font is the checked JP font of the B-1316 rule (look_samples/README.md).

const FONT := preload("res://art/game_font.ttf")

var world := "wafu"


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		world = args[0]
	theme = UZUUI.create_world_theme(world, {"font": FONT})
	if args.size() > 1:
		_save_frames(args[1])

	var bg := ColorRect.new()
	bg.color = Color(0.07, 0.07, 0.09) if world == "persona" else Color(0.16, 0.15, 0.14)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var caption := Label.new()
	caption.text = "%s / 静止" % world
	caption.position = Vector2(28, 18)
	add_child(caption)

	if world == "persona":
		_persona()
	else:
		_wafu()


func _save_frames(dir: String) -> void:
	var frame: Dictionary = UZUUI.get_world_options(world)["frame"]
	UZUUI.draw_frame(frame).save_png(dir.path_join(world + "_frame.png"))
	var layered := frame.duplicate()
	layered["inner_shadow"] = 1.0
	layered["highlight"] = 1.0
	layered["glow"] = 0.8
	UZUUI.draw_frame(layered).save_png(dir.path_join(world + "_frame_layers_max.png"))


func _panel(pos: Vector2, size: Vector2) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.position = pos
	panel.custom_minimum_size = size
	add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 14)
	panel.add_child(box)
	return box


func _persona() -> void:
	# 900 px wide: the 9-slice middle tiles several times — the wedge
	# of B-1317 appeared at the seams of exactly this kind of panel.
	var box := _panel(Vector2(110, 120), Vector2(900, 320))
	box.add_child(UZUUI.make_label("クエスト受注", "title"))
	box.add_child(UZUUI.make_label("灯りの欠片を三つ集めてきておくれ。", "body"))
	box.add_child(UZUUI.make_label("HP", "caption"))
	var gauge := UZUUI.make_gauge(65, 100, 65)
	gauge.custom_minimum_size = Vector2(0, 28)
	box.add_child(gauge)
	var button := UZUUI.make_button("たたかう")
	button.position = Vector2(790, 500)
	button.custom_minimum_size = Vector2(240, 72)
	add_child(button)


func _wafu() -> void:
	var status := _panel(Vector2(61, 58), Vector2(350, 250))
	status.add_child(UZUUI.make_label("ミナ　Lv.7", "heading"))
	status.add_child(UZUUI.make_label("HP", "caption"))
	var hp := UZUUI.make_gauge(65, 100, 65)
	hp.custom_minimum_size = Vector2(0, 22)
	status.add_child(hp)
	status.add_child(UZUUI.make_label("MP", "caption"))
	var mp := UZUUI.make_gauge(40, 100, 40)
	mp.custom_minimum_size = Vector2(0, 22)
	status.add_child(mp)

	var talk := _panel(Vector2(61, 398), Vector2(1030, 190))
	talk.add_child(UZUUI.make_label("村の長老", "heading"))
	talk.add_child(UZUUI.make_label("祠のランタンが消えてしまった。夕暮れまでに、灯りの欠片を三つ集めてきておくれ。", "body"))
