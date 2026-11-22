extends Control
## B-1315 showcase driver: shows one sample screen (built from a JSON
## spec by ai_loop/ui_tool.gd into screens/), the empty-panel sheet for
## the texture measurement, or the kit touch parts in a HUD corner.
## World and screen come from the environment (uzu.py look does not
## forward user args to the scene):
##   UZU_B1315_WORLD = persona | wafu        (default persona)
##   UZU_B1315_SCREEN = title | menu | settings | hud | talk | sheet | touch
##   UZU_B1315_FRAME_OUT = where the sheet mode saves the frame PNG
## The font is the checked JP font of the B-1316 rule (look_samples/README.md).

const FONT := preload("res://art/game_font.ttf")

var world := "persona"
var screen := "title"


func _ready() -> void:
	var w := OS.get_environment("UZU_B1315_WORLD")
	if w != "":
		world = w
	var s := OS.get_environment("UZU_B1315_SCREEN")
	if s != "":
		screen = s
	theme = UZUUI.create_world_theme(world, {"font": FONT})

	# The world's backdrop composition (B-1319): a generated graphic
	# field, not a flat color — persona gets its red diagonal halftone
	# band, wafu a mottled dark wall with a warm glow.
	add_child(UZUUI.make_backdrop(world))

	if screen == "sheet":
		_sheet()
	elif screen == "touch":
		_touch()
	else:
		var packed := load("res://screens/%s_%s.tscn" % [world, screen]) as PackedScene
		if packed == null:
			push_error("b1315 showcase: no built screen %s_%s (run uzu.py ui on its spec first)" % [world, screen])
			return
		add_child(packed.instantiate())


func _sheet() -> void:
	# One empty panel, wide enough that the frame's middle tiles several
	# times: the sheet the texture measurement reads.
	var panel := PanelContainer.new()
	panel.position = Vector2(64, 68)
	panel.custom_minimum_size = Vector2(1024, 512)
	add_child(panel)
	var out := OS.get_environment("UZU_B1315_FRAME_OUT")
	if out != "":
		var frame: Dictionary = UZUUI.get_world_options(world)["frame"]
		UZUUI.draw_frame(frame).save_png(out)


func _touch() -> void:
	# The kit touch parts in a HUD corner, following the world theme; the
	# stick is displaced so the knob state reads in the capture.
	var caption := UZUUI.make_label("タッチUI（キット部品）", "caption")
	caption.position = Vector2(48, 24)
	add_child(caption)
	var stick := UZUUI.make_touch_stick()
	stick.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	stick.offset_left = 48
	stick.offset_top = -216
	stick.offset_right = 216
	stick.offset_bottom = -48
	add_child(stick)
	var pad := UZUUI.make_touch_button("決定")
	pad.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	pad.offset_left = -168
	pad.offset_top = -168
	pad.offset_right = -48
	pad.offset_bottom = -48
	add_child(pad)
	await get_tree().process_frame
	await get_tree().process_frame
	(stick as UZUTouchStick).press_at(stick.size * Vector2(0.78, 0.34))
