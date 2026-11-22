extends Control
## B-1320: the showcase's decoration layer -- graphic accents drawn
## around a built screen (behind it or in front of it): four-point
## sparkles, slash strips, rings, and one huge tilted word set in the
## project font. This is the persona screens' foreground/background
## dressing; it lives in the sample, not the kit (the kit composes
## the backdrop itself, UZUUI.make_backdrop). Items are plain
## dictionaries so a recipe reads like the composition it draws:
##   {"kind": "sparkle", "at": Vector2, "r": 24.0, "color": Color, "pulse": true}
##   {"kind": "slash", "at": Vector2, "len": 200.0, "h": 14.0, "angle": -12.0, "color": Color}
##   {"kind": "ring", "at": Vector2, "r": 60.0, "width": 6.0, "color": Color, "gap": 0.0}
##   {"kind": "word", "text": "PAUSE", "at": Vector2, "size": 130, "angle": -8.0, "color": Color}
## Sparkles flagged "pulse" breathe (an idle motion); everything is
## placed to stay inside the 1152x648 screen.

var items: Array = []
var font: Font
var _time := 0.0
var _words: Array = [] # [{label, item}]


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)


## Replaces the recipe (a screen change re-dresses the stage) and
## rebuilds the word labels; the drawn items just redraw.
func set_items(p_items: Array) -> void:
	items = p_items
	for w in _words:
		(w["label"] as Label).queue_free()
	_words.clear()
	for item in items:
		if item.get("kind") == "word":
			var label := Label.new()
			label.text = str(item["text"])
			label.add_theme_font_override("font", font)
			label.add_theme_font_size_override("font_size", int(item.get("size", 96)))
			label.add_theme_color_override("font_color", item.get("color", Color.WHITE))
			label.mouse_filter = Control.MOUSE_FILTER_IGNORE
			add_child(label)
			_words.append({"label": label, "item": item})
	queue_redraw()
	if is_inside_tree():
		await get_tree().process_frame
		_place_words()


func _place_words() -> void:
	for w in _words:
		var label: Label = w["label"]
		var item: Dictionary = w["item"]
		label.position = Vector2(item["at"]) - label.size * 0.5
		label.pivot_offset = label.size * 0.5
		label.rotation_degrees = float(item.get("angle", 0.0))


func _process(delta: float) -> void:
	_time += delta
	for item in items:
		if item.get("pulse", false):
			queue_redraw()
			return


func _alpha(item: Dictionary, base: float) -> float:
	if item.get("pulse", false):
		return base * (0.72 + 0.28 * sin(_time * 2.4 + float(item.get("phase", 0.0))))
	return base


func _draw() -> void:
	for item in items:
		var color: Color = item.get("color", Color.WHITE)
		color.a *= _alpha(item, color.a)
		match str(item.get("kind", "")):
			"sparkle":
				var at: Vector2 = item["at"]
				var r := float(item.get("r", 20.0))
				var pts := PackedVector2Array()
				for k in 8:
					var a := TAU * float(k) / 8.0
					var rad := r if k % 2 == 0 else r * 0.16
					pts.append(at + Vector2(cos(a), sin(a)) * rad)
				draw_colored_polygon(pts, color)
			"slash":
				var at: Vector2 = item["at"]
				var half := Vector2(float(item.get("len", 160.0)), float(item.get("h", 12.0))) * 0.5
				var rot := Transform2D(deg_to_rad(float(item.get("angle", 0.0))), Vector2.ZERO)
				var corners := PackedVector2Array([
					at + rot * Vector2(-half.x, -half.y), at + rot * Vector2(half.x, -half.y),
					at + rot * Vector2(half.x, half.y), at + rot * Vector2(-half.x, half.y)])
				draw_colored_polygon(corners, color)
			"ring":
				var gap := float(item.get("gap", 0.0))
				draw_arc(item["at"], float(item.get("r", 60.0)), gap, TAU - gap, 72, color, float(item.get("width", 6.0)), true)
