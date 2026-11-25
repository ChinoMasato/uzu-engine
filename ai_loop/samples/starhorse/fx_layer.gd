extends Control
## The effect layer of the Star Horse sample (B-1330), ported from the
## B-1322 showcase fx layer: a slow drift of dust motes over the
## backdrop, a sparkle burst where focus lands, a white flash when a
## choice is pressed, and slash streaks across a screen change.
## Everything is drawn from plain state advanced in _process, so a
## --fixed-fps movie records it deterministically. Amounts stay low:
## effects underline the UI, they never compete with the text.
##
## Two instances dress a screen: a back one (dust only, over the
## backdrop, under the screen) and a front one (bursts, flashes and
## slashes, over everything). Set "dust" > 0 on the back one only.

const BURST_LIFE := 0.45
const FLASH_LIFE := 0.30
const SLASH_LIFE := 0.38

var dust := 0 # Motes drifting over the backdrop (0 = none).
var dust_color := Color(1, 1, 1, 0.5)

var _time := 0.0
var _motes: Array = [] # {pos, vel, r, phase}
var _bursts: Array = [] # {pos, color, age}
var _flashes: Array = [] # {xform, size, color, age}
var _slashes: Array = [] # {color, age}


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	# Deterministic motes (a small LCG on a fixed seed, like the
	# backdrop's sparkles): the same stage every run and every frame
	# of a movie.
	var rng := 1013904223
	var next01 := func() -> float:
		rng = int((int(rng) * 1664525 + 1013904223) & 0xFFFFFFFF)
		return float((rng >> 8) & 0xFFFFFF) / float(0x1000000)
	for i in dust:
		_motes.append({
			"pos": Vector2(next01.call() * 1152.0, next01.call() * 648.0),
			"vel": Vector2(-4.0 - 7.0 * next01.call(), 2.0 + 5.0 * next01.call()),
			"r": 1.6 + 2.6 * next01.call(),
			"phase": next01.call() * TAU,
		})


func burst(at: Vector2, color := Color.WHITE) -> void:
	_bursts.append({"pos": at, "color": color, "age": 0.0})


func flash(xform: Transform2D, size: Vector2, color := Color.WHITE) -> void:
	_flashes.append({"xform": xform, "size": size, "color": color, "age": 0.0})


func slash(color := Color.WHITE) -> void:
	_slashes.append({"color": color, "age": 0.0})


func _process(delta: float) -> void:
	_time += delta
	var dirty := not _motes.is_empty()
	for m in _motes:
		m["pos"] = (m["pos"] as Vector2) + (m["vel"] as Vector2) * delta
		var p: Vector2 = m["pos"]
		if p.x < -8.0:
			p.x = 1160.0
		if p.y > 656.0:
			p.y = -8.0
		m["pos"] = p
	for b in _bursts:
		b["age"] = float(b["age"]) + delta
		dirty = true
	_bursts = _bursts.filter(func(b) -> bool: return float(b["age"]) < BURST_LIFE)
	for f in _flashes:
		f["age"] = float(f["age"]) + delta
		dirty = true
	_flashes = _flashes.filter(func(f) -> bool: return float(f["age"]) < FLASH_LIFE)
	for s in _slashes:
		s["age"] = float(s["age"]) + delta
		dirty = true
	_slashes = _slashes.filter(func(s) -> bool: return float(s["age"]) < SLASH_LIFE)
	if dirty:
		queue_redraw()


func _sparkle(at: Vector2, r: float, color: Color) -> void:
	var pts := PackedVector2Array()
	for k in 8:
		var a := TAU * float(k) / 8.0
		var rad := r if k % 2 == 0 else r * 0.16
		pts.append(at + Vector2(cos(a), sin(a)) * rad)
	draw_colored_polygon(pts, color)


func _draw() -> void:
	for m in _motes:
		var c := dust_color
		c.a *= 0.35 + 0.30 * (0.5 + 0.5 * sin(_time * 1.3 + float(m["phase"])))
		_sparkle(m["pos"], float(m["r"]) * 2.2, c)
	for b in _bursts:
		var t := float(b["age"]) / BURST_LIFE
		var col: Color = b["color"]
		var ease := 1.0 - pow(1.0 - t, 2.0)
		for k in 6:
			var dir := Vector2(cos(TAU * float(k) / 6.0 + 0.4), sin(TAU * float(k) / 6.0 + 0.4))
			var c := col
			c.a *= (1.0 - t) * 0.9
			_sparkle((b["pos"] as Vector2) + dir * ease * 44.0, 9.0 * (1.0 - t * 0.6), c)
		var core := col
		core.a *= (1.0 - t) * 0.8
		_sparkle(b["pos"], 14.0 * (1.0 - t * 0.5), core)
	for f in _flashes:
		var t := float(f["age"]) / FLASH_LIFE
		var c: Color = f["color"]
		c.a *= (1.0 - t) * (1.0 - t) * 0.55
		draw_set_transform_matrix(f["xform"])
		draw_rect(Rect2(Vector2.ZERO, f["size"]), c)
		draw_set_transform_matrix(Transform2D.IDENTITY)
	for s in _slashes:
		# Three streaks on the transition's slant, staggered: the cut
		# sweeps left to right and is gone inside half a second.
		for k in 3:
			var t := clampf((float(s["age"]) - 0.05 * float(k)) / (SLASH_LIFE - 0.05 * float(k)), 0.0, 1.0)
			if t <= 0.0 or t >= 1.0:
				continue
			var x := lerpf(-360.0, 1420.0, 1.0 - pow(1.0 - t, 3.0))
			var c: Color = s["color"]
			c.a *= (1.0 - t) * 0.75
			var mid := Vector2(x, 120.0 + 190.0 * float(k))
			var rot := Transform2D(deg_to_rad(-16.0), Vector2.ZERO)
			var half := Vector2(230.0, 5.0 + 3.0 * float(k))
			draw_colored_polygon(PackedVector2Array([
				mid + rot * Vector2(-half.x, -half.y), mid + rot * Vector2(half.x, -half.y),
				mid + rot * Vector2(half.x, half.y), mid + rot * Vector2(-half.x, half.y)]), c)
