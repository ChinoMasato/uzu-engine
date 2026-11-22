extends SceneTree
## B-1310: theme probe for the UI quality gate (ai_loop/ui_quality.py).
## Dumps everything the gate scores from UZUUI themes as JSON: per theme type,
## the styleboxes (class + the numbers the scale check reads + a sampled fill
## colour), colours, constants and font sizes, plus the world options the
## values came from. Run headless:
##   godot --headless --path <project> --script <this file> -- <out.json>
## The project only needs to exist; UZUUI is an engine class.

const TYPES: Array[String] = [
	"PanelContainer", "Button", "CheckBox", "OptionButton", "HSlider", "VSlider",
	"LineEdit", "SpinBox", "HScrollBar", "VScrollBar", "PopupMenu", "Tree",
	"TabContainer", "ItemList", "ProgressBar", "TooltipPanel", "TooltipLabel",
	"Label", "RichTextLabel", "UZUNameTag", "UZUTalk", "UZUSlot", "UZURibbon", "UZUGauge",
	"UZUTouchStick", "UZUTouchButton",
]


func _col(c: Color) -> Array:
	return [c.r, c.g, c.b, c.a]


func _stylebox(sb: StyleBox, with_alpha: bool = false) -> Dictionary:
	var d: Dictionary = {"class": sb.get_class()}
	d["content_margins"] = [
		sb.get_margin(SIDE_LEFT), sb.get_margin(SIDE_TOP),
		sb.get_margin(SIDE_RIGHT), sb.get_margin(SIDE_BOTTOM),
	]
	if sb is StyleBoxFlat:
		var f := sb as StyleBoxFlat
		d["bg_color"] = _col(f.bg_color)
		d["corner_radius"] = [
			f.corner_radius_top_left, f.corner_radius_top_right,
			f.corner_radius_bottom_right, f.corner_radius_bottom_left,
		]
		d["border_width"] = [
			f.border_width_left, f.border_width_top,
			f.border_width_right, f.border_width_bottom,
		]
		d["shadow_size"] = f.shadow_size
		d["shadow_offset"] = [f.shadow_offset.x, f.shadow_offset.y]
		d["shadow_color"] = _col(f.shadow_color)
	elif sb is StyleBoxTexture:
		var t := sb as StyleBoxTexture
		d["texture_margins"] = [
			t.texture_margin_left, t.texture_margin_top,
			t.texture_margin_right, t.texture_margin_bottom,
		]
		d["expand_margins"] = [
			t.expand_margin_left, t.expand_margin_top,
			t.expand_margin_right, t.expand_margin_bottom,
		]
		if t.texture != null:
			var img := t.texture.get_image()
			if img != null and img.get_width() > 0 and img.get_height() > 0:
				# The centre of the 9-slice tile is the panel fill.
				d["center_color"] = _col(img.get_pixel(img.get_width() / 2, img.get_height() / 2))
				d["texture_size"] = [img.get_width(), img.get_height()]
				if with_alpha:
					# Frame coverage (B-1315): the alpha of the centre
					# slice -- the part of the texture that repeats. A
					# wedge-shaped hole (B-1318) is an alpha hole here.
					var ml := int(t.texture_margin_left)
					var mt := int(t.texture_margin_top)
					var mr := int(t.texture_margin_right)
					var mb := int(t.texture_margin_bottom)
					var amin := 1.0
					var asum := 0.0
					var n := 0
					for y in range(mt, img.get_height() - mb):
						for x in range(ml, img.get_width() - mr):
							var a := img.get_pixel(x, y).a
							amin = minf(amin, a)
							asum += a
							n += 1
					if n > 0:
						d["center_alpha_min"] = amin
						d["center_alpha_mean"] = asum / n
	return d


func _theme_dump(theme: Theme) -> Dictionary:
	var out: Dictionary = {"types": {}, "default_font_size": theme.default_font_size}
	for type_name in TYPES:
		var td: Dictionary = {}
		var styleboxes: Dictionary = {}
		for name in theme.get_stylebox_list(type_name):
			styleboxes[name] = _stylebox(theme.get_stylebox(name, type_name),
					type_name == "PanelContainer" and name == "panel")
		if not styleboxes.is_empty():
			td["styleboxes"] = styleboxes
		var colors: Dictionary = {}
		for name in theme.get_color_list(type_name):
			colors[name] = _col(theme.get_color(name, type_name))
		if not colors.is_empty():
			td["colors"] = colors
		var constants: Dictionary = {}
		for name in theme.get_constant_list(type_name):
			constants[name] = theme.get_constant(name, type_name)
		if not constants.is_empty():
			td["constants"] = constants
		var font_sizes: Dictionary = {}
		for name in theme.get_font_size_list(type_name):
			font_sizes[name] = theme.get_font_size(name, type_name)
		if not font_sizes.is_empty():
			td["font_sizes"] = font_sizes
		if not td.is_empty():
			out["types"][type_name] = td
	return out


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 1:
		push_error("ui_quality_probe: usage: -- <out.json>")
		quit(2)
		return
	var data: Dictionary = {"format": "uzu-ui-probe/1", "themes": {}}
	data["themes"]["default"] = _theme_dump(UZUUI.create_theme({}))
	data["themes"]["default"]["options"] = UZUUI.get_theme_defaults()
	for world in UZUUI.get_world_names():
		var dump := _theme_dump(UZUUI.create_world_theme(world))
		dump["options"] = UZUUI.get_world_options(world)
		data["themes"][world] = dump
	var f := FileAccess.open(args[0], FileAccess.WRITE)
	if f == null:
		push_error("ui_quality_probe: cannot write " + args[0])
		quit(2)
		return
	f.store_string(JSON.stringify(data))
	f.close()
	quit(0)
