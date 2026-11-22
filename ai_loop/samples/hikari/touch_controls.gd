extends Control
## Touch controls (B-1004; UZUUI kit parts since B-1315): the virtual
## stick (bottom-left) and the interact button (bottom-right) shown on
## touch devices, or when forced for checks (see main.gd's
## _touch_ui_enabled). Both are kit parts (UZUUI.make_touch_stick /
## make_touch_button), so they follow the UI root's world theme like
## every other part instead of being hand-drawn per game; this node only
## translates the stick's value into the game's move actions and mirrors
## the prompt into the button's label.

signal interact_pressed

var stick: UZUTouchStick
var interact_button: Button

func _init() -> void:
	name = "TouchControls"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _ready() -> void:
	# Placement is anchors + offsets, set before adding: setting position
	# after add_child does not land where the anchors suggest (the same
	# pattern as the dialogue window in main.gd).
	stick = UZUUI.make_touch_stick() as UZUTouchStick
	stick.name = "Stick"
	stick.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	stick.offset_left = 36
	stick.offset_top = -204
	stick.offset_right = 204
	stick.offset_bottom = -36
	stick.value_changed.connect(_on_stick_value)
	add_child(stick)

	interact_button = UZUUI.make_touch_button("決定") as Button
	interact_button.name = "InteractButton"
	interact_button.focus_mode = Control.FOCUS_NONE # Space/Enter stay the game's interact key.
	interact_button.add_theme_font_size_override("font_size", 20)
	interact_button.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	interact_button.offset_left = -140
	interact_button.offset_top = -140
	interact_button.offset_right = -36
	interact_button.offset_bottom = -36
	interact_button.pressed.connect(func() -> void: interact_pressed.emit())
	add_child(interact_button)

## The stick reports an analog value; the game polls the move actions,
## so translate here (the kit part itself stays input-map agnostic).
func _on_stick_value(value: Vector2) -> void:
	_set_action("move_right", value.x)
	_set_action("move_left", -value.x)
	_set_action("move_down", value.y)
	_set_action("move_up", -value.y)

func _set_action(action: StringName, strength: float) -> void:
	if strength > 0.05:
		Input.action_press(action, strength)
	else:
		Input.action_release(action)

## The button's label mirrors the prompt ("話す", "欠片を拾う", ...). With
## nothing in reach it falls back to a dimmed 決定.
func set_interact_text(text: String) -> void:
	if not interact_button:
		return
	interact_button.text = text if not text.is_empty() else "決定"
	interact_button.modulate.a = 1.0 if not text.is_empty() else 0.55
