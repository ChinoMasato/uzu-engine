extends SceneTree
## Declarative UI building (BACKLOG B-1301): a Control tree (layout, anchors, theme) from
## one JSON spec, so an agent describes the screen instead of stacking node operations.
## Run through `ai_loop/uzu.py ui <project> --spec ui.json [--shot out.png] [--over res://game.tscn]`.
##
##   godot --headless --path P --script ui_tool.gd -- --spec /abs/ui.json
##
## Spec (colors "#rrggbb" or "#rrggbbaa"; an unknown key is an error that names where it is):
##   {"scene": "res://ui/hud.tscn",
##    "theme": {"world": "fantasy" | "wafu" | "sf" | "horror" | "persona" | "pixel" (B-1307: textured game
##              frames, colors and parts in one name; then panel/button/bar are not used),
##              "font": "res://fonts/x.ttf", "font_fallback": "res://fonts/ja.woff2" (glyphs the font lacks),
##              "font_size": 20, "font_color": "#f4ead2", "accent": "#d9a441",
##              "panel": {"top": "#1d2740ee", "bottom": "#10162add", "radius": 12, "border": "#d9a441", "shadow": 8, "padding": 12},
##              "button": {"bg": "#2b3550", "hover": "#3a4870", "pressed": "#1d2438", "radius": 8, "padding": 8},
##              "bar": {"bg": "#00000080", "fill": "#d9a441", "radius": 6}},
##    "root": {"type": "Screen", "children": [ ...nodes... ]}}
## A node: {"type": T, "name": "...", "children": [...], and the keys of its type}
##   types: Screen (full-screen root), Panel, VBox, HBox, Grid, Margin, Center, Scroll, Label,
##          RichText (BBCode), Button, Bar (progress), Image (TextureRect), Color (ColorRect), Spacer,
##          Tabs (each child is a page; its name is the tab title), List (ItemList, "items": [...]),
##          Slider (HSlider: "value", "min", "max", "step"), Check (CheckBox: "text", "pressed"),
##          Option (OptionButton: "items": [...], "selected"),
##          game parts (B-1307, styled by the world): Gauge ("value", "max", "segments"),
##          Talk ("speaker", "text": a talk window with a name tag and a next mark),
##          Slot ("text", "count"), Ribbon ("text"), Separator,
##          touch parts (B-1315, styled by the theme): Stick (a UZUTouchStick),
##          TouchButton ("text": a round pad button)
##   placement (outside containers): "anchor": top_left | top | top_right | left | center | right |
##          bottom_left | bottom | bottom_right | full | top_wide | bottom_wide | left_wide | right_wide,
##          "offset": [x, y] (inset from the anchored edges; for centers, a shift), "size": [w, h]
##   inside containers: "min_size": [w, h], "expand": true (take the free space)
##   common: "visible", "tooltip", "style" (a panel style for this node through UZUUI: bg or a
##          top/bottom gradient, radius, border, border_width, shadow, padding), "font_size",
##          "font_color", "align" (left | center | right)
##   Lengths follow the UZUUI layout scale (B-1314, UZUUI.get_layout_scale()): a style's
##          "shadow" snaps to an elevation level and "elevation" (0..4) names the level
##          instead; "padding" and a box's "separation" take a step name ("xs" | "s" | "m" |
##          "l" | "xl" | "xxl" = 4 | 8 | 12 | 16 | 24 | 32) instead of a number. Raw numbers
##          still work everywhere (the kit snaps them to the scale).
##   Motion (B-1317): any node may carry "motion": a UZUUIJuice motion preset name
##          ("appear" | "disappear" | "hover" | "press" | "value_change") or an object
##          {"preset": name, "duration": seconds, "strength": 0..3, "from": n, "to": n}
##          ("to" is the value_change target). The spec is validated here and stored as
##          the node's "uzu_motion" metadata; on a world-themed screen the UZUUIWorld
##          node plays it with that world's motion when the screen opens. Without a
##          world theme the metadata is saved but nothing plays it.
##   Label / RichText / Button: "text";  Bar: "value", "max", "show_percent"
##   Label: "text_style" names a step of the theme's type scale (B-1312: display | title |
##          heading | body | caption) instead of a raw "font_size"; the theme gives the
##          label that step's size, line/letter spacing and decoration. A numeric
##          "font_size" still wins when both are given.
##   VBox / HBox / Grid: "separation", Grid "columns";  Margin: "padding" (n or [l, t, r, b])
##   Image: "texture" (res://), "stretch" (keep | cover | scale);  Color: "color"
## Prints "UI_RESULT {json}" with what was built.

const TYPES := {
	"Screen": "Control", "Panel": "PanelContainer", "VBox": "VBoxContainer", "HBox": "HBoxContainer",
	"Grid": "GridContainer", "Margin": "MarginContainer", "Center": "CenterContainer", "Scroll": "ScrollContainer",
	"Label": "Label", "RichText": "RichTextLabel", "Button": "Button", "Bar": "ProgressBar",
	"Image": "TextureRect", "Color": "ColorRect", "Spacer": "Control",
	"Tabs": "TabContainer", "List": "ItemList",
	"Slider": "HSlider", "Check": "CheckBox", "Option": "OptionButton",
	"Gauge": "", "Talk": "", "Slot": "", "Ribbon": "", "Separator": "",
	"Stick": "", "TouchButton": "",
}
const COMMON := ["type", "name", "children", "anchor", "offset", "size", "min_size", "expand", "visible", "tooltip", "style", "font_size", "font_color", "align", "motion"]
const MOTION_KEYS := ["preset", "duration", "strength", "from", "to"]
const EXTRA := {
	"Label": ["text", "text_style"], "RichText": ["text"], "Button": ["text"], "Bar": ["value", "max", "show_percent"],
	"VBox": ["separation"], "HBox": ["separation"], "Grid": ["separation", "columns"], "Margin": ["padding"],
	"Image": ["texture", "stretch"], "Color": ["color"], "List": ["items"],
	"Gauge": ["value", "max", "segments"], "Talk": ["speaker", "text"], "Slot": ["text", "count"], "Ribbon": ["text"],
	"Slider": ["value", "min", "max", "step"], "Check": ["text", "pressed"], "Option": ["items", "selected"],
	"TouchButton": ["text"],
}
const ANCHORS := {
	"top_left": Control.PRESET_TOP_LEFT, "top": Control.PRESET_CENTER_TOP, "top_right": Control.PRESET_TOP_RIGHT,
	"left": Control.PRESET_CENTER_LEFT, "center": Control.PRESET_CENTER, "right": Control.PRESET_CENTER_RIGHT,
	"bottom_left": Control.PRESET_BOTTOM_LEFT, "bottom": Control.PRESET_CENTER_BOTTOM, "bottom_right": Control.PRESET_BOTTOM_RIGHT,
	"full": Control.PRESET_FULL_RECT, "top_wide": Control.PRESET_TOP_WIDE, "bottom_wide": Control.PRESET_BOTTOM_WIDE,
	"left_wide": Control.PRESET_LEFT_WIDE, "right_wide": Control.PRESET_RIGHT_WIDE,
}
const STYLE_KEYS := ["bg", "top", "bottom", "radius", "border", "border_width", "shadow", "elevation", "padding", "hover", "pressed", "fill"]
## The named steps of the UZUUI layout scale (B-1314), for "padding" and
## "separation" values that would rather name a step than count px. The
## same names are in UZUUI.get_layout_scale()["spacing_steps"].
const SPACING_STEPS := {"xs": 4, "s": 8, "m": 12, "l": 16, "xl": 24, "xxl": 32}
const THEME_KEYS := ["world", "font", "font_fallback", "font_size", "font_color", "accent", "panel", "button", "bar"]

var errors := []
var counts := {}


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var i := args.find("--spec")
	var result := {"ok": false, "error": "ui needs --spec ui.json"} if i < 0 or i + 1 >= args.size() else _build(args[i + 1])
	print("UI_RESULT " + JSON.stringify(result))
	quit(0 if result.get("ok", false) else 1)


func _err(where: String, message: String) -> void:
	errors.append("%s: %s" % [where, message])


func _color(where: String, v, fallback := Color.WHITE) -> Color:
	if v is String and Color.html_is_valid(v):
		return Color.html(v)
	_err(where, "needs a color like \"#d9a441\" or \"#141b2bdd\"")
	return fallback


func _vec2(where: String, v, fallback := Vector2.ZERO) -> Vector2:
	if v is Array and v.size() == 2:
		return Vector2(v[0], v[1])
	_err(where, "needs [x, y]")
	return fallback


## A spacing value: a number of px, or a layout-scale step name.
func _spacing(where: String, v, fallback := 0) -> int:
	if v is String:
		if SPACING_STEPS.has(v):
			return SPACING_STEPS[v]
		_err(where, "needs a step name (%s) or a number" % ", ".join(SPACING_STEPS.keys()))
		return fallback
	if v is int or v is float:
		return int(v)
	_err(where, "needs a step name (%s) or a number" % ", ".join(SPACING_STEPS.keys()))
	return fallback


## A motion spec (B-1317): a preset name, or an object with a "preset" and
## numeric overrides. Returns the normalized dictionary stored as the node's
## "uzu_motion" metadata (empty when invalid; the error is recorded).
func _motion(where: String, v) -> Dictionary:
	var names := UZUUIJuice.get_motion_names()
	if v is String:
		if not names.has(v):
			_err(where, "needs one of %s" % ", ".join(names))
			return {}
		return {"preset": v}
	if not v is Dictionary:
		_err(where, "needs a preset name (%s) or an object" % ", ".join(names))
		return {}
	var out := {}
	for key in v:
		if not key in MOTION_KEYS:
			_err(where, "unknown key '%s' (allowed: %s)" % [key, ", ".join(MOTION_KEYS)])
		elif key == "preset":
			if not names.has(str(v[key])):
				_err(where + ".preset", "needs one of %s" % ", ".join(names))
			else:
				out["preset"] = str(v[key])
		elif key == "duration":
			if not (v[key] is int or v[key] is float) or float(v[key]) < 0.01 or float(v[key]) > 10.0:
				_err(where + ".duration", "needs a number of seconds between 0.01 and 10")
			else:
				out["duration"] = float(v[key])
		elif key == "strength":
			if not (v[key] is int or v[key] is float) or float(v[key]) < 0.0 or float(v[key]) > 3.0:
				_err(where + ".strength", "needs a number between 0 and 3")
			else:
				out["strength"] = float(v[key])
		else:  # "from" / "to": plain numbers (the value_change endpoints).
			if not (v[key] is int or v[key] is float):
				_err(where + "." + key, "needs a number")
			else:
				out[key] = float(v[key])
	if not out.has("preset"):
		if not v.has("preset"):
			_err(where, "an object motion needs a \"preset\"")
		return {}
	return out


## A panel style through UZUUI (B-1302): a gradient ("top"/"bottom") or a flat "bg",
## rounded corners, a border and a soft shadow.
func _stylebox(where: String, d) -> StyleBox:
	if not d is Dictionary:
		_err(where, "must be an object")
		return StyleBoxEmpty.new()
	for key in d:
		if not key in STYLE_KEYS:
			_err(where, "unknown key '%s' (allowed: %s)" % [key, ", ".join(STYLE_KEYS)])
		elif key in ["bg", "top", "bottom", "border", "hover", "pressed", "fill"]:
			_color("%s.%s" % [where, key], d[key])
		elif key == "elevation":
			if not (d[key] is int or d[key] is float) or int(d[key]) < 0 or int(d[key]) > 4:
				_err(where + ".elevation", "needs a level 0..4")
		elif key == "padding":
			_spacing(where + ".padding", d[key])  # Validates the step name, if any.
	return UZUUI.create_panel_style(d)


## The screen's theme through UZUUI.create_theme (B-1302): panels, buttons, bars, tabs,
## lists and tooltips in one look.
func _theme(d) -> Theme:
	if not d is Dictionary:
		_err("theme", "must be an object")
		return UZUUI.create_theme()
	var options := {}
	for key in d:
		if not key in THEME_KEYS:
			_err("theme", "unknown key '%s' (allowed: %s)" % [key, ", ".join(THEME_KEYS)])
	if d.has("font"):
		var font = load(d.font) if d.font is String and ResourceLoader.exists(d.font) else null
		if font is Font:
			options["font"] = font
		else:
			_err("theme.font", "needs a res:// font file")
	if d.has("font_fallback"):
		# Glyphs the main font lacks (Japanese, with a Latin main font) come from this one.
		var fallback = load(d.font_fallback) if d.font_fallback is String and ResourceLoader.exists(d.font_fallback) else null
		if not fallback is Font or not options.has("font"):
			_err("theme.font_fallback", "needs a res:// font file, and theme.font")
		else:
			var both := FontVariation.new()
			both.base_font = options["font"]
			both.fallbacks = [fallback]
			options["font"] = both
	if d.has("font_size"):
		options["font_size"] = int(d.font_size)
	if d.has("font_color"):
		options["text"] = _color("theme.font_color", d.font_color)
	if d.has("accent"):
		options["accent"] = _color("theme.accent", d.accent)
	if d.has("world"):
		# A world (B-1307): textured frames, colors and game parts in one name.
		if not UZUUI.get_world_names().has(d.world):
			_err("theme.world", "needs one of %s" % ", ".join(UZUUI.get_world_names()))
			return UZUUI.create_theme()
		var world_overrides := {}
		for key in ["font", "font_size", "accent"]:
			if options.has(key):
				world_overrides[key] = options[key]
		if options.has("text"):
			world_overrides["text"] = options["text"]
		return UZUUI.create_world_theme(d.world, world_overrides)
	for key in ["panel", "button", "bar"]:
		if d.has(key):
			_stylebox("theme." + key, d[key])  # Checks the keys and colors.
			options[key] = d[key]
	return UZUUI.create_theme(options)


## Anchors the control to an edge, corner or the center of its parent, size w x h, inset
## by the offset (shifted, for the centered axes).
func _place(c: Control, where: String, d: Dictionary) -> void:
	var anchor: String = d.get("anchor", "top_left")
	if not ANCHORS.has(anchor):
		_err(where + ".anchor", "needs one of %s" % ", ".join(ANCHORS.keys()))
		return
	var off := _vec2(where + ".offset", d.offset) if d.has("offset") else Vector2.ZERO
	var size := _vec2(where + ".size", d.size) if d.has("size") else Vector2.ZERO
	c.set_anchors_preset(ANCHORS[anchor])
	# Horizontal: anchored left, right, centered or stretched.
	var ax := c.anchor_left
	if anchor.ends_with("_wide") and anchor in ["top_wide", "bottom_wide"] or anchor == "full":
		c.offset_left = off.x
		c.offset_right = -off.x
	elif ax == 0.0:
		c.offset_left = off.x
		c.offset_right = off.x + size.x
	elif ax == 1.0:
		c.offset_left = -off.x - size.x
		c.offset_right = -off.x
		c.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	else:
		c.offset_left = off.x - size.x / 2.0
		c.offset_right = off.x + size.x / 2.0
		c.grow_horizontal = Control.GROW_DIRECTION_BOTH
	# Vertical.
	var ay := c.anchor_top
	if anchor in ["left_wide", "right_wide", "full"]:
		c.offset_top = off.y
		c.offset_bottom = -off.y
	elif ay == 0.0:
		c.offset_top = off.y
		c.offset_bottom = off.y + size.y
	elif ay == 1.0:
		c.offset_top = -off.y - size.y
		c.offset_bottom = -off.y
		c.grow_vertical = Control.GROW_DIRECTION_BEGIN
	else:
		c.offset_top = off.y - size.y / 2.0
		c.offset_bottom = off.y + size.y / 2.0
		c.grow_vertical = Control.GROW_DIRECTION_BOTH


func _node(where: String, d, parent: Control, owner_root: Control) -> Control:
	if not d is Dictionary:
		_err(where, "must be an object")
		return null
	var type: String = d.get("type", "")
	if not TYPES.has(type):
		_err(where + ".type", "needs one of %s" % ", ".join(TYPES.keys()))
		return null
	for key in d:
		if not key in COMMON and not key in EXTRA.get(type, []):
			_err(where, "unknown key '%s' for %s (allowed: %s)" % [key, type, ", ".join(COMMON + EXTRA.get(type, []))])
	var c: Control
	match type:
		"Gauge":
			c = UZUUI.make_gauge(float(d.get("value", 50)), float(d.get("max", 100)), int(d.get("segments", 10)))
		"Talk":
			c = UZUUI.make_talk_window(str(d.get("speaker", "")), str(d.get("text", "")))
		"Slot":
			c = UZUUI.make_item_slot(str(d.get("text", "")), int(d.get("count", 0)))
		"Ribbon":
			c = UZUUI.make_ribbon(str(d.get("text", "")))
		"Separator":
			c = UZUUI.make_separator()
		"Stick":
			c = UZUUI.make_touch_stick()
		"TouchButton":
			c = UZUUI.make_touch_button(str(d.get("text", "")))
		_:
			c = ClassDB.instantiate(TYPES[type])
	c.name = d.get("name", type)
	counts[type] = counts.get(type, 0) + 1
	match type:
		"Label":
			c.text = str(d.get("text", ""))
			if d.has("text_style"):
				var step := str(d.text_style)
				if not step in ["display", "title", "heading", "body", "caption"]:
					_err(where + ".text_style", "needs one of display, title, heading, body, caption")
				else:
					c.theme_type_variation = "UZU" + step.capitalize() + "Label"
			c.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART if d.has("size") or d.has("min_size") else TextServer.AUTOWRAP_OFF
		"RichText":
			c.bbcode_enabled = true
			c.text = str(d.get("text", ""))
			c.fit_content = true
			c.scroll_active = false
		"Button":
			c.text = str(d.get("text", ""))
		"Bar":
			c.max_value = float(d.get("max", 100))
			c.value = float(d.get("value", 50))
			c.show_percentage = bool(d.get("show_percent", false))
		"Slider":
			c.min_value = float(d.get("min", 0))
			c.max_value = float(d.get("max", 100))
			c.step = float(d.get("step", 1))
			c.value = float(d.get("value", 50))
		"Check":
			c.text = str(d.get("text", ""))
			c.button_pressed = bool(d.get("pressed", false))
		"Option":
			for item in d.get("items", []):
				c.add_item(str(item))
			if c.item_count > 0:
				c.select(clampi(int(d.get("selected", 0)), 0, c.item_count - 1))
		"VBox", "HBox", "Grid":
			if d.has("separation"):
				var sep := _spacing(where + ".separation", d.separation)
				c.add_theme_constant_override("separation" if type != "Grid" else "h_separation", sep)
				if type == "Grid":
					c.add_theme_constant_override("v_separation", sep)
			if type == "Grid":
				c.columns = int(d.get("columns", 2))
		"Margin":
			var p = d.get("padding", 12)
			var pads: Array = p if p is Array and p.size() == 4 else [p, p, p, p]
			for k in 4:
				c.add_theme_constant_override(["margin_left", "margin_top", "margin_right", "margin_bottom"][k], _spacing(where + ".padding", pads[k], 12))
		"Image":
			var tex = load(d.texture) if d.has("texture") and ResourceLoader.exists(str(d.texture)) else null
			if d.has("texture") and not tex is Texture2D:
				_err(where + ".texture", "needs a res:// image")
			c.texture = tex
			c.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			c.stretch_mode = {"keep": TextureRect.STRETCH_KEEP_ASPECT_CENTERED, "cover": TextureRect.STRETCH_KEEP_ASPECT_COVERED, "scale": TextureRect.STRETCH_SCALE}.get(d.get("stretch", "keep"), TextureRect.STRETCH_KEEP_ASPECT_CENTERED)
		"Color":
			c.color = _color(where + ".color", d.get("color", "#00000080"))
		"List":
			for item in d.get("items", []):
				c.add_item(str(item))
			c.auto_height = true
		"Spacer":
			c.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			c.size_flags_vertical = Control.SIZE_EXPAND_FILL
	if d.has("style"):
		var sb := _stylebox(where + ".style", d.style)
		match type:
			"Button":
				c.add_theme_stylebox_override("normal", sb)
			"Bar":
				c.add_theme_stylebox_override("background", sb)
			_:
				if c is PanelContainer or c is TabContainer or c is ItemList:
					c.add_theme_stylebox_override("panel", sb)
				else:
					_err(where + ".style", "only Panel, Tabs, List, Button and Bar take a style")
	if d.has("font_size"):
		c.add_theme_font_size_override("font_size" if type != "RichText" else "normal_font_size", int(d.font_size))
	if d.has("font_color"):
		c.add_theme_color_override("font_color" if type != "RichText" else "default_color", _color(where + ".font_color", d.font_color))
	if d.has("align"):
		var a = {"left": HORIZONTAL_ALIGNMENT_LEFT, "center": HORIZONTAL_ALIGNMENT_CENTER, "right": HORIZONTAL_ALIGNMENT_RIGHT}.get(d.align, -1)
		if a < 0:
			_err(where + ".align", "needs left, center or right")
		elif "horizontal_alignment" in c:
			c.horizontal_alignment = a
		elif type == "Button":
			c.alignment = a
	if d.has("min_size"):
		c.custom_minimum_size = _vec2(where + ".min_size", d.min_size)
	if d.get("expand", false):
		c.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		c.size_flags_vertical = Control.SIZE_EXPAND_FILL
	if d.has("visible"):
		c.visible = bool(d.visible)
	if d.has("tooltip"):
		c.tooltip_text = str(d.tooltip)
	if d.has("motion"):
		var motion := _motion(where + ".motion", d.motion)
		if not motion.is_empty():
			c.set_meta("uzu_motion", motion)
			counts["Motion"] = counts.get("Motion", 0) + 1
	if parent:
		parent.add_child(c, true)
		c.owner = owner_root
		for inner in c.find_children("*", "", true, false):  # The inside of made parts (Talk, Slot, ...).
			if inner.owner == null:
				inner.owner = owner_root
		if not parent is Container:
			_place(c, where, d)
		elif d.has("anchor") or d.has("offset") or d.has("size"):
			_err(where, "inside a container (%s) use min_size and expand, not anchor/offset/size" % parent.name)
	var kids = d.get("children", [])
	if not kids is Array:
		_err(where + ".children", "must be a list")
	else:
		for k in kids.size():
			_node("%s.children[%d]" % [where, k], kids[k], c, owner_root if parent else c)
	return c


func _build(spec_path: String) -> Dictionary:
	var spec = JSON.parse_string(FileAccess.get_file_as_string(spec_path))
	if not spec is Dictionary:
		return {"ok": false, "error": "the spec is not a JSON object (%s)" % spec_path}
	for key in spec:
		if not key in ["scene", "theme", "root"]:
			_err("spec", "unknown key '%s' (allowed: scene, theme, root)" % key)
	var out: String = spec.get("scene", "")
	if not out.begins_with("res://") or not out.ends_with(".tscn"):
		_err("scene", "needs a res://...tscn path")
	var root_spec = spec.get("root", {"type": "Screen"})
	if root_spec is Dictionary and not root_spec.has("type"):
		root_spec["type"] = "Screen"
	var root := _node("root", root_spec, null, null)
	if root == null:
		return {"ok": false, "error": "the spec has %d problem(s)" % errors.size(), "problems": errors}
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE  # A HUD over a game lets clicks through where it is empty.
	root.theme = _theme(spec.get("theme", {}))
	var theme_spec = spec.get("theme", {})
	if theme_spec is Dictionary and theme_spec.has("world") and UZUUI.get_world_names().has(theme_spec.world):
		# The world's motion (B-1307 stage 2): moving frames, opening, hover, ambient sway.
		var motion := UZUUIWorld.new()
		motion.name = "WorldMotion"
		motion.world = theme_spec.world
		root.add_child(motion)
		motion.owner = root
		counts["WorldMotion"] = 1
	if not errors.is_empty():
		root.free()
		return {"ok": false, "error": "the spec has %d problem(s)" % errors.size(), "problems": errors}
	var packed := PackedScene.new()
	var err := packed.pack(root)
	if err == OK:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out.get_base_dir()))
		err = ResourceSaver.save(packed, out)
	root.free()
	if err != OK:
		return {"ok": false, "error": "could not save %s (%s)" % [out, error_string(err)]}
	return {"ok": true, "scene": out, "nodes": counts}
