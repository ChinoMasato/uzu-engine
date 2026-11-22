extends SceneTree
## B-1315: containment probe for the UI quality gate (ai_loop/ui_quality.py).
## Instantiates built sample screens and checks, for every leaf Control
## inside a structural panel, that its rect stays within the panel's safe
## area: the stylebox content rect, intersected -- for a textured frame --
## with the frame shape's own boundary, scanned from the stylebox's
## texture (a skew parallelogram's left edge leans right as y grows, so
## the safe left at a control's bottom row is the boundary at that row;
## the safe right is the boundary at its top row). Measured twice: at
## rest, and across the whole run of the screens' motions (the peak
## phase of an overshoot is where a part escapes).
##
## Scope: leaf controls (layout containers only place children; their
## leaves are measured) whose nearest panel surface is a plain
## PanelContainer or a UZUTalk window. Kit small-part internals (slots,
## name tags, ribbons) are the kit's own business -- their surfaces are
## checked by the kit's tests and the sample captures, not here.
##
## Run headless against a project with built screens:
##   godot --headless --path <project> --script ui_containment_probe.gd -- res://screens <out.json>
## Output format: uzu-ui-containment/1 (see ai_loop/ui_quality.py).

const TOLERANCE := 1.0 # px of slack for rounding in layout and transforms.
const PANEL_VARIATIONS := ["", "UZUTalk"]

var _screen_root: Node
var _bounds_cache: Dictionary = {} # stylebox instance id -> Dictionary


func _rel(node: Node) -> String:
	if _screen_root and node == _screen_root:
		return "."
	var path := str(node.get_path())
	var base := str(_screen_root.get_path())
	return path.trim_prefix(base + "/")


func _nearest_panel(c: Control) -> PanelContainer:
	var n := c.get_parent()
	while n:
		if n is PanelContainer:
			var p := n as PanelContainer
			# A kit part's surface: its internals are out of scope.
			return p if PANEL_VARIATIONS.has(p.get_theme_type_variation()) else null
		if n == _screen_root:
			return null
		n = n.get_parent()
	return null


## The rect a control actually *draws* in, in its own local coordinates.
## A non-wrapping Label only paints its text: the drawn box is the text
## extent placed by the alignment inside the control's rect (a
## right-aligned "next" marker paints at the right edge, however wide
## its row is). A wrapping Label can fill any line, so its whole rect
## counts; every other control paints its whole rect.
func _drawn_local_rect(c: Control) -> Rect2:
	if c is Label:
		var label := c as Label
		if label.autowrap_mode == TextServer.AUTOWRAP_OFF:
			var extent := label.get_minimum_size()
			var w := minf(label.size.x, extent.x)
			var h := minf(label.size.y, extent.y)
			var x := 0.0
			match label.horizontal_alignment:
				HORIZONTAL_ALIGNMENT_CENTER:
					x = (label.size.x - w) * 0.5
				HORIZONTAL_ALIGNMENT_RIGHT:
					x = label.size.x - w
			var y := 0.0
			match label.vertical_alignment:
				VERTICAL_ALIGNMENT_CENTER:
					y = (label.size.y - h) * 0.5
				VERTICAL_ALIGNMENT_BOTTOM:
					y = label.size.y - h
			return Rect2(Vector2(x, y), Vector2(w, h))
	return Rect2(Vector2.ZERO, c.size)


func _local_rect(c: Control, panel: PanelContainer) -> Rect2:
	var inv := panel.get_global_transform().affine_inverse()
	var g := c.get_global_transform()
	var drawn := _drawn_local_rect(c)
	var pts := [
		inv * (g * drawn.position),
		inv * (g * (drawn.position + Vector2(drawn.size.x, 0))),
		inv * (g * (drawn.position + Vector2(0, drawn.size.y))),
		inv * (g * (drawn.position + drawn.size)),
	]
	var lo: Vector2 = pts[0]
	var hi: Vector2 = pts[0]
	for p in pts:
		lo = lo.min(p)
		hi = hi.max(p)
	return Rect2(lo, hi - lo)


## The frame shape's boundary in panel px, from the stylebox texture:
## {left0, left1, right0, right1} -- the solid body's left/right edge x
## at the shape's top (0) and bottom (1) rows, mapped into panel space
## (the texture is drawn offset by the expand margins). Empty for a
## flat or textureless panel (no slant to model).
func _frame_bounds(panel: PanelContainer) -> Dictionary:
	var sb := panel.get_theme_stylebox("panel")
	var key := sb.get_instance_id()
	if _bounds_cache.has(key):
		return _bounds_cache[key]
	var out: Dictionary = {}
	var tex := sb as StyleBoxTexture
	if tex and tex.texture:
		var img := tex.texture.get_image()
		if img and img.get_width() > 0:
			var w := img.get_width()
			var h := img.get_height()
			var top := -1
			var bottom := -1
			var edges: Dictionary = {}
			for y in h:
				var first := -1
				var last := -1
				for x in w:
					if img.get_pixel(x, y).a >= 0.9:
						if first < 0:
							first = x
						last = x
				if first >= 0 and last - first > w * 0.5:
					if top < 0:
						top = y
					bottom = y
					edges[y] = [first, last]
			if top >= 0:
				var e := tex.get_expand_margin(SIDE_LEFT)
				var er := tex.get_expand_margin(SIDE_RIGHT)
				out = {
					"left0": float(edges[top][0]) - e, "left1": float(edges[bottom][0]) - e,
					"right0": float(edges[top][1]) - float(w) + er, "right1": float(edges[bottom][1]) - float(w) + er,
				}
	_bounds_cache[key] = out
	return out


func _measure(screen: Control) -> Array:
	var out: Array = []
	var stack: Array = [screen]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		for child in node.get_children():
			stack.push_back(child)
		if not node is Control:
			continue
		var c := node as Control
		if c == screen or not c.is_visible_in_tree() or c.size.x <= 0.0 or c.size.y <= 0.0:
			continue
		if c is Container and c.get_child_count() > 0:
			continue # Layout only: its leaves are measured, not the box.
		var panel := _nearest_panel(c)
		if panel == null:
			continue
		var sb := panel.get_theme_stylebox("panel")
		var safe := Rect2(
			sb.get_margin(SIDE_LEFT), sb.get_margin(SIDE_TOP),
			panel.size.x - sb.get_margin(SIDE_LEFT) - sb.get_margin(SIDE_RIGHT),
			panel.size.y - sb.get_margin(SIDE_TOP) - sb.get_margin(SIDE_BOTTOM))
		var local := _local_rect(c, panel)
		var bounds := _frame_bounds(panel)
		if not bounds.is_empty() and panel.size.y > 0.0:
			var f_top := clampf(local.position.y / panel.size.y, 0.0, 1.0)
			var f_bottom := clampf((local.position.y + local.size.y) / panel.size.y, 0.0, 1.0)
			var left_bound := lerpf(float(bounds["left0"]), float(bounds["left1"]), f_bottom)
			var right_bound := panel.size.x + lerpf(float(bounds["right0"]), float(bounds["right1"]), f_top)
			safe.position.x = maxf(safe.position.x, left_bound)
			var right := minf(safe.position.x + safe.size.x, right_bound)
			safe.size.x = right - safe.position.x
		var overflow := Vector4(
			safe.position.x - local.position.x,
			safe.position.y - local.position.y,
			local.position.x + local.size.x - safe.position.x - safe.size.x,
			local.position.y + local.size.y - safe.position.y - safe.size.y)
		if overflow.x > TOLERANCE or overflow.y > TOLERANCE or overflow.z > TOLERANCE or overflow.w > TOLERANCE:
			out.append({
				"control": _rel(c), "panel": _rel(panel),
				"overflow": {
					"left": snappedf(overflow.x, 0.1), "top": snappedf(overflow.y, 0.1),
					"right": snappedf(overflow.z, 0.1), "bottom": snappedf(overflow.w, 0.1),
				},
			})
	return out


func _collect_motion_nodes(node: Node, out: Array) -> void:
	if node is Control and node.has_meta("uzu_motion"):
		out.append(node)
	for child in node.get_children():
		_collect_motion_nodes(child, out)


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 2:
		push_error("ui_containment_probe: usage: -- <screens_dir> <out.json>")
		quit(2)
		return
	var dir := DirAccess.open(args[0])
	if dir == null:
		push_error("ui_containment_probe: cannot open " + args[0])
		quit(2)
		return
	var files: Array = []
	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		if entry.ends_with(".tscn"):
			files.append(entry)
		entry = dir.get_next()
	files.sort()
	var screens: Dictionary = {}
	for file in files:
		var name: String = str(file).trim_suffix(".tscn")
		var world: String = name.split("_")[0]
		var packed := load(args[0].path_join(file)) as PackedScene
		if packed == null:
			screens[name] = {"world": world, "pass": false, "reason": "scene failed to load"}
			continue
		var screen := packed.instantiate() as Control
		_screen_root = screen
		root.add_child(screen)
		for i in 3:
			await process_frame
		var rest := _measure(screen)
		# Peak phase: play every declared motion and measure across its
		# whole run, so the overshoot's worst frame is what is judged.
		var movers: Array = []
		_collect_motion_nodes(screen, movers)
		for node in movers:
			var meta: Dictionary = node.get_meta("uzu_motion")
			var options: Dictionary = {"world": world}
			for key in ["from", "to", "duration", "strength"]:
				if meta.has(key):
					options[key] = meta[key]
			UZUUIJuice.play_motion(node, str(meta.get("preset", "")), options)
		var peak: Dictionary = {}
		for step in 240:
			UZUUIJuice.apply_animations(1.0 / 60.0)
			if step % 2 == 0:
				for v in _measure(screen):
					var key := str(v["control"]) + "@" + str(v["panel"])
					if not peak.has(key):
						peak[key] = v
					else:
						var o: Dictionary = peak[key]["overflow"]
						var n: Dictionary = v["overflow"]
						for side in o:
							o[side] = maxf(float(o[side]), float(n[side]))
			await process_frame
			if movers.is_empty():
				break
			if step > 5:
				var any_animating := false
				for node in movers:
					if UZUUIJuice.is_animating(node):
						any_animating = true
						break
				if not any_animating:
					break
		UZUUIJuice.cancel_all()
		var peak_list: Array = peak.values()
		screens[name] = {
			"world": world,
			"rest": rest, "peak": peak_list,
			"pass": rest.is_empty() and peak_list.is_empty(),
		}
		root.remove_child(screen)
		screen.queue_free()
		for i in 2:
			await process_frame
	var f := FileAccess.open(args[1], FileAccess.WRITE)
	if f == null:
		push_error("ui_containment_probe: cannot write " + args[1])
		quit(2)
		return
	f.store_string(JSON.stringify({"format": "uzu-ui-containment/1", "screens": screens}, "\t"))
	f.close()
	quit(0)


func _init() -> void:
	_run.call_deferred()
