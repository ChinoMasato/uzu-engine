extends Control
## B-1315 showcase driver, grown into the stage director (B-1320):
## shows one sample screen (built from a JSON spec by ai_loop/ui_tool.gd
## into screens/) dressed with the world's backdrop (B-1319) and a
## decoration layer (deco_layer.gd), or the empty-panel sheet for the
## texture measurement, or the kit touch parts in a HUD corner.
## B-1322 adds the effect layers (fx_layer.gd): drifting dust behind,
## focus bursts / press flashes / transition slashes in front.
## World and screen come from the environment (uzu.py look does not
## forward user args to the scene):
##   UZU_B1315_WORLD = persona | wafu        (default persona)
##   UZU_B1315_SCREEN = title | menu | settings | hud | talk | sheet | touch
##   UZU_B1315_FRAME_OUT = where the sheet mode saves the frame PNG
##   UZU_B1315_FOCUS = 1: after the opening, focus the first button
##        (a still then shows the focused state -- persona's red flip)
##   UZU_B1315_FLOW = 1: run the choreography reel -- the title opens
##        with a staggered slash-in, focus walks the menu, a press
##        transitions to the pause menu, more focus play, then the
##        talk screen. Recorded with --write-movie for the owner.
## The font is the checked JP font of the B-1316 rule (look_samples/README.md).

const FONT := preload("res://art/game_font.ttf")
const DecoLayer := preload("res://deco_layer.gd")
const FxLayer := preload("res://fx_layer.gd")

const RED := Color(0.902, 0.0, 0.071)
const YELLOW := Color(1.0, 0.882, 0.302)

var world := "persona"
var screen := "title"
var _current: Control
var _deco_back: Control
var _deco_front: Control
var _fx_back: Control
var _fx_front: Control


func _ready() -> void:
	var w := OS.get_environment("UZU_B1315_WORLD")
	if w != "":
		world = w
	var s := OS.get_environment("UZU_B1315_SCREEN")
	if s != "":
		screen = s
	theme = UZUUI.create_world_theme(world, {"font": FONT})

	# The world's backdrop composition (B-1319): a generated graphic
	# field, not a flat color -- persona gets its red diagonal halftone
	# band, wafu a mottled dark wall with a warm glow.
	add_child(UZUUI.make_backdrop(world))

	if screen == "sheet":
		_sheet()
		return
	if screen == "touch":
		_touch()
		return

	# Effect layers (B-1322): dust drifts over the backdrop behind
	# everything; bursts, flashes and slashes play in front.
	_fx_back = FxLayer.new()
	if world == "persona":
		_fx_back.dust = 26
		_fx_back.dust_color = Color(1, 1, 1, 0.5)
	elif world == "wafu":
		_fx_back.dust = 12
		_fx_back.dust_color = Color(1.0, 0.85, 0.6, 0.35)
	add_child(_fx_back)
	_deco_back = DecoLayer.new()
	_deco_back.font = FONT
	add_child(_deco_back)
	_current = _make_screen(screen)
	if _current == null:
		return
	add_child(_current)
	_deco_front = DecoLayer.new()
	_deco_front.font = FONT
	add_child(_deco_front)
	_fx_front = FxLayer.new()
	add_child(_fx_front)
	_dress(screen)
	_wire_fx(_current)

	if OS.get_environment("UZU_B1315_FLOW") == "1":
		_flow()
	elif OS.get_environment("UZU_B1315_FOCUS") == "1":
		_settle_focus()


func _make_screen(name: String) -> Control:
	var packed := load("res://screens/%s_%s.tscn" % [world, name]) as PackedScene
	if packed == null:
		push_error("b1315 showcase: no built screen %s_%s (run uzu.py ui on its spec first)" % [world, name])
		return null
	return packed.instantiate()


## The decoration recipes: a back layer (a huge tilted word, rings,
## slashes -- the mid-ground the panels sit on) and a front layer
## (sparkles that breathe over everything). Persona dresses heavily;
## wafu gets one faint enso ring and nothing else (B-1320).
func _dress(name: String) -> void:
	var back: Array = []
	var front: Array = []
	if world == "persona":
		match name:
			"title":
				back = [
					{"kind": "word", "text": "MIDNIGHT", "at": Vector2(600, 300), "size": 140, "angle": -8.0, "color": Color(RED, 0.10)},
					{"kind": "ring", "at": Vector2(1022, 478), "r": 56.0, "width": 7.0, "color": Color(RED, 0.85)},
					{"kind": "slash", "at": Vector2(985, 148), "len": 210.0, "h": 13.0, "angle": -12.0, "color": RED},
					{"kind": "slash", "at": Vector2(1015, 182), "len": 130.0, "h": 13.0, "angle": -12.0, "color": Color(1, 1, 1, 0.9)},
				]
				front = [
					{"kind": "sparkle", "at": Vector2(140, 300), "r": 15.0, "color": Color.WHITE, "pulse": true},
					{"kind": "sparkle", "at": Vector2(1006, 88), "r": 24.0, "color": Color.WHITE, "pulse": true, "phase": 1.3},
					{"kind": "sparkle", "at": Vector2(884, 540), "r": 13.0, "color": Color(1, 1, 1, 0.8)},
				]
			"menu":
				back = [
					{"kind": "word", "text": "PAUSE", "at": Vector2(576, 330), "size": 250, "angle": -8.0, "color": Color(RED, 0.13)},
					{"kind": "slash", "at": Vector2(150, 120), "len": 150.0, "h": 10.0, "angle": -12.0, "color": Color(1, 1, 1, 0.5)},
				]
				front = [
					{"kind": "sparkle", "at": Vector2(952, 120), "r": 18.0, "color": Color.WHITE, "pulse": true},
					{"kind": "sparkle", "at": Vector2(210, 540), "r": 13.0, "color": Color(1, 1, 1, 0.8)},
				]
			"settings":
				back = [
					{"kind": "word", "text": "CONFIG", "at": Vector2(810, 555), "size": 200, "angle": -8.0, "color": Color(RED, 0.12)},
				]
				front = [
					{"kind": "sparkle", "at": Vector2(140, 110), "r": 15.0, "color": Color.WHITE, "pulse": true},
				]
			"hud":
				back = [
					{"kind": "word", "text": "QUEST", "at": Vector2(700, 380), "size": 150, "angle": -6.0, "color": Color(RED, 0.10)},
					{"kind": "slash", "at": Vector2(170, 330), "len": 170.0, "h": 11.0, "angle": -12.0, "color": Color(RED, 0.8)},
				]
				front = [
					{"kind": "sparkle", "at": Vector2(560, 120), "r": 13.0, "color": Color(1, 1, 1, 0.7)},
				]
			"talk":
				# B-1322: the talk screen's upper field was mostly
				# empty air. The watermark grows and a second ring and
				# a slash fill the mid-field, so the window sits in a
				# composed scene instead of a void.
				back = [
					{"kind": "word", "text": "CHAPTER", "at": Vector2(330, 190), "size": 130, "angle": -6.0, "color": Color(RED, 0.13)},
					{"kind": "ring", "at": Vector2(118, 128), "r": 46.0, "width": 8.0, "color": Color(0.561, 0.0, 0.047, 0.8)},
					{"kind": "ring", "at": Vector2(1012, 216), "r": 68.0, "width": 6.0, "color": Color(0.561, 0.0, 0.047, 0.45)},
					{"kind": "slash", "at": Vector2(150, 336), "len": 190.0, "h": 10.0, "angle": -12.0, "color": Color(RED, 0.5)},
				]
				front = [
					{"kind": "sparkle", "at": Vector2(905, 64), "r": 16.0, "color": Color.WHITE, "pulse": true},
					{"kind": "sparkle", "at": Vector2(1120, 400), "r": 12.0, "color": Color(1, 1, 1, 0.8)},
				]
	elif world == "wafu":
		back = [
			{"kind": "ring", "at": Vector2(990, 150), "r": 88.0, "width": 11.0, "gap": 0.5, "color": Color(0.937, 0.886, 0.769, 0.10)},
		]
	_deco_back.set_items(back)
	_deco_front.set_items(front)


# ------------------------------------------------------------------ motion

## The screen's actors, in reading order: the logo, the ribbon, the
## talk window, the top-level panels, and every button.
func _actors(scr: Control) -> Array:
	var found: Array = []
	var stack: Array = [scr]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for child in n.get_children():
			stack.push_back(child)
		if not n is Control or n == scr:
			continue
		var c := n as Control
		var is_actor := c is BaseButton \
			or (c is PanelContainer and c.get_parent() == scr) \
			or c.name in ["Logo", "Talk", "Ribbon"]
		if is_actor:
			found.append(c)
	found.sort_custom(func(a: Control, b: Control) -> bool:
		var pa := a.get_global_rect().position
		var pb := b.get_global_rect().position
		return pa.y < pb.y - 4.0 or (absf(pa.y - pb.y) <= 4.0 and pa.x < pb.x))
	return found


func _buttons(scr: Control) -> Array:
	var out: Array = []
	var stack: Array = [scr]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for child in n.get_children():
			stack.push_back(child)
		if n is BaseButton:
			out.append(n)
	out.sort_custom(func(a: Control, b: Control) -> bool:
		var pa := a.get_global_rect().position
		var pb := b.get_global_rect().position
		return pa.y < pb.y - 4.0 or (absf(pa.y - pb.y) <= 4.0 and pa.x < pb.x))
	return out


## Effects wiring (B-1322): focus landing on a button bursts a small
## sparkle at its tip; a press flashes the bar and bursts again. The
## reel's grab_focus / pressed.emit reach the same signals, so the
## movie shows the effects exactly where a player's hand would.
func _wire_fx(scr: Control) -> void:
	for b in _buttons(scr):
		var btn := b as BaseButton
		if not btn.focus_entered.is_connected(_on_button_focus.bind(btn)):
			btn.focus_entered.connect(_on_button_focus.bind(btn))
		if not btn.pressed.is_connected(_on_button_press.bind(btn)):
			btn.pressed.connect(_on_button_press.bind(btn))


func _on_button_focus(btn: BaseButton) -> void:
	if _fx_front:
		var r := btn.get_global_rect()
		_fx_front.burst(r.position + Vector2(14, r.size.y * 0.5), Color(1, 0.95, 0.75))


func _on_button_press(btn: BaseButton) -> void:
	if _fx_front:
		_fx_front.flash(btn.get_global_transform(), btn.size, Color.WHITE)
		var r := btn.get_global_rect()
		_fx_front.burst(r.get_center(), Color(1, 0.9, 0.6))


## The opening choreography: whatever the world's own opening played
## is cancelled back to the natural state, the value_change motions
## are replayed as declared, and the actors slash in one by one.
func _choreograph(scr: Control, frames_first := true) -> void:
	if frames_first:
		await get_tree().process_frame
		await get_tree().process_frame
	UZUUIJuice.cancel_all()
	# Declared value changes (the gauges) run as specified.
	var stack: Array = [scr]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for child in n.get_children():
			stack.push_back(child)
		if n is Control and n.has_meta("uzu_motion"):
			var meta: Dictionary = n.get_meta("uzu_motion")
			if str(meta.get("preset", "")) == "value_change":
				var options: Dictionary = meta.duplicate()
				options.erase("preset")
				options["world"] = world
				UZUUIJuice.play_motion(n, "value_change", options)
	var actors := _actors(scr)
	for i in actors.size():
		if i > 0:
			await get_tree().create_timer(0.07).timeout
		UZUUIJuice.play_motion(actors[i], "appear", {"world": world})


func _focus_button(scr: Control, idx: int) -> void:
	var btns := _buttons(scr)
	if btns.is_empty():
		return
	var b: BaseButton = btns[clampi(idx, 0, btns.size() - 1)]
	b.grab_focus()
	UZUUIJuice.play_motion(b, "hover", {"world": world})


func _press_button(scr: Control, idx: int) -> void:
	var btns := _buttons(scr)
	if btns.is_empty():
		return
	var b: BaseButton = btns[clampi(idx, 0, btns.size() - 1)]
	UZUUIJuice.play_motion(b, "press", {"world": world})
	b.pressed.emit()


func _goto(next: String) -> void:
	var old := _current
	var scr := _make_screen(next)
	if scr == null:
		return
	add_child(scr)
	move_child(scr, old.get_index())
	_current = scr
	_dress(next)
	_wire_fx(scr)
	if _fx_front:
		_fx_front.slash(Color(1, 1, 1, 0.9))
	# The new screen's own opening is superseded by the transition and
	# the choreography below; its world motion node must not open it.
	var wm := scr.find_child("WorldMotion", true, false)
	if wm:
		wm.set("open_on_ready", false)
	await get_tree().process_frame
	await get_tree().process_frame
	UZUUIJuice.cancel_all()
	UZUUIJuice.transition(old, scr, 0.28, "ease_in", 1.0)
	await get_tree().create_timer(0.34).timeout
	old.queue_free()
	await _choreograph(scr, false)


func _settle_focus() -> void:
	await get_tree().create_timer(0.6).timeout
	_focus_button(_current, 0)


## The reel (UZU_B1315_FLOW=1): title opening, focus play, a press
## into the pause menu, more focus play, a press back into the talk
## screen. Timed in movie seconds under --write-movie --fixed-fps.
func _flow() -> void:
	await _choreograph(_current)
	await get_tree().create_timer(0.5).timeout
	_focus_button(_current, 0)
	await get_tree().create_timer(0.9).timeout
	_focus_button(_current, 1)
	await get_tree().create_timer(0.9).timeout
	_focus_button(_current, 0)
	await get_tree().create_timer(0.8).timeout
	_press_button(_current, 0)
	await get_tree().create_timer(0.25).timeout
	await _goto("menu")
	await get_tree().create_timer(0.6).timeout
	_focus_button(_current, 0)
	await get_tree().create_timer(0.9).timeout
	_focus_button(_current, 1)
	await get_tree().create_timer(0.9).timeout
	_focus_button(_current, 0)
	await get_tree().create_timer(0.8).timeout
	_press_button(_current, 0)
	await get_tree().create_timer(0.25).timeout
	await _goto("talk")
	await get_tree().create_timer(2.4).timeout


# ------------------------------------------------------------------ modes

func _sheet() -> void:
	# One empty panel, wide enough that the frame's middle tiles several
	# times: the sheet the texture measurement reads. Its height is set
	# from the frame stylebox so the texture's middle maps 1:1 -- the
	# measurement reads the print at native resolution (B-1321: at an
	# arbitrary height the skew frame's vertical stretch rescaled a
	# 4 px halftone cell to a non-integer 7.5 px, and the sheet scored
	# the rescale, not the print).
	var panel := PanelContainer.new()
	panel.position = Vector2(64, 68)
	panel.custom_minimum_size = Vector2(1024, 512)
	add_child(panel)
	await get_tree().process_frame
	var sb := panel.get_theme_stylebox("panel") as StyleBoxTexture
	if sb and sb.texture:
		var native_h := sb.texture.get_height() \
			- int(sb.get_expand_margin(SIDE_TOP)) - int(sb.get_expand_margin(SIDE_BOTTOM))
		panel.custom_minimum_size = Vector2(1024, native_h)
		panel.size = Vector2(1024, native_h)
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
