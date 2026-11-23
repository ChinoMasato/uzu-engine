extends Node3D
## B-1321 trial: the persona screens of the 2D showcase (B-1315/B-1320,
## ai_loop/look_samples/b1315) rebuilt as a real 3D scene — the same
## content, but panels and bars are thick geometry with PBR materials,
## lit by real lights with shadows, text is Label3D, and the camera
## gives the layers true parallax. The point is the picture: this file
## exists so the owner can compare the rendered-3D route's look against
## the 2D Control route's, screen by screen.
##
##   UZU_B1321_SCREEN = title | menu   (default title)
##   UZU_B1321_STILL  = 1: settled pose, no reel (for still captures)
##
## B-1322: the rake light drifts and flares on focus changes, the rig
## holds a slight base angle, and the title watermark moves behind
## the bands (dimmer, higher) so it stops fighting the bars.
##
## Without STILL the scene plays a reel: a staggered slash-in on 3D
## transforms (the UZUUIJuice idea, re-done in 3D), focus walking the
## bars, a slow camera sway. Recorded with --write-movie.
## Layout mirrors the 2D specs: 1 unit = 100 px of the 1152x648 frame.

const FONT := preload("res://art/game_font.ttf")

const RED := Color(0.902, 0.0, 0.071)
const DEEP_RED := Color(0.561, 0.0, 0.047)
const YELLOW := Color(1.0, 0.882, 0.302)
const INK := Color(0.067, 0.067, 0.067)

var _still := false
var _t := 0.0
var _rig: Node3D
var _actors: Array = [] # {node, from, to, from_rot, to_rot, delay, dur}
var _bar_faces: Array = [] # MeshInstance3D of the title/menu bars
var _focus := -1
var _focus_since := 0.0
var _sparkles: Array = [] # {node, base, phase}
var _mat_red: StandardMaterial3D
var _mat_black: StandardMaterial3D
var _mat_white: StandardMaterial3D
var _sun: DirectionalLight3D
var _rake: OmniLight3D


func _wx(px: float) -> float:
	return (px - 576.0) * 0.01


func _wy(py: float) -> float:
	return (324.0 - py) * 0.01


# ---------------------------------------------------------------- parts

func _std(color: Color, rough: float, metallic := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metallic
	return m


func _label(text: String, size: int, color: Color, outline := 0) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.font = FONT
	l.font_size = size
	l.pixel_size = 0.01
	l.modulate = color
	l.outline_size = outline
	if outline > 0:
		l.outline_modulate = Color.BLACK
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return l


# A parallelogram prism (the persona slash as a solid): cross-section a
# slanted rectangle in XY, extruded along Z, flat faces with explicit
# normals so the light breaks cleanly on every side.
func _prism(w: float, h: float, d: float, slant: float) -> ArrayMesh:
	var s := slant * h
	var bl := Vector3(-w / 2, -h / 2, d / 2)
	var br := Vector3(w / 2, -h / 2, d / 2)
	var tr := Vector3(w / 2 + s, h / 2, d / 2)
	var tl := Vector3(-w / 2 + s, h / 2, d / 2)
	var bbl := Vector3(-w / 2, -h / 2, -d / 2)
	var bbr := Vector3(w / 2, -h / 2, -d / 2)
	var btr := Vector3(w / 2 + s, h / 2, -d / 2)
	var btl := Vector3(-w / 2 + s, h / 2, -d / 2)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_face(st, Vector3(0, 0, 1), bl, br, tr, tl)
	_face(st, Vector3(0, 0, -1), bbl, btl, btr, bbr)
	_face(st, Vector3(0, -1, 0), bl, bbl, bbr, br)
	_face(st, Vector3(0, 1, 0), tl, tr, btr, btl)
	var ln := Vector3(-h, s, 0).normalized()
	_face(st, ln, bl, tl, btl, bbl)
	var rn := Vector3(h, -s, 0).normalized()
	_face(st, rn, br, bbr, btr, tr)
	return st.commit()


func _face(st: SurfaceTool, n: Vector3, a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> void:
	st.set_normal(n)
	st.add_vertex(a)
	st.add_vertex(b)
	st.add_vertex(c)
	st.add_vertex(a)
	st.add_vertex(c)
	st.add_vertex(d)


func _solid(mesh: Mesh, mat: Material, pos := Vector3.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.set_surface_override_material(0, mat)
	mi.position = pos
	return mi


func _box(size: Vector3, mat: Material, pos := Vector3.ZERO) -> MeshInstance3D:
	var bm := BoxMesh.new()
	bm.size = size
	return _solid(bm, mat, pos)


# A menu bar: a white-edged slash prism with its text floating a hair
# in front of the face. The face instance is registered for the focus
# walk (its material flips to the signal red, like the 2D inversion).
func _bar(text: String, w: float, focused: bool) -> Node3D:
	var g := Node3D.new()
	g.add_child(_solid(_prism(w + 0.14, 0.72, 0.14, 0.25), _mat_white, Vector3(0, 0, -0.04)))
	var face := _solid(_prism(w, 0.58, 0.22, 0.25), _mat_red if focused else _mat_black, Vector3(0, 0, 0.02))
	g.add_child(face)
	_bar_faces.append(face)
	var l := _label(text, 34, Color.WHITE)
	l.position = Vector3(0.07, 0, 0.17)
	g.add_child(l)
	g.rotation_degrees.z = 2.0
	return g


func _sparkle_texture() -> Texture2D:
	# The same pinched four-point shape the 2D backdrop prints.
	var img := Image.create_empty(64, 64, false, Image.FORMAT_RGBA8)
	for y in range(64):
		for x in range(64):
			var d := Vector2(x - 31.5, y - 31.5) / 31.5
			var len := d.length()
			if len < 1.0:
				var t := absf(cos(2.0 * atan2(d.y, d.x)))
				var edge := 0.14 + 0.86 * pow(t, 2.2)
				var a := clampf((edge - len) / 0.25, 0.0, 1.0)
				img.set_pixel(x, y, Color(1, 1, 1, a))
	return ImageTexture.create_from_image(img)


# ---------------------------------------------------------------- stage

func _backdrop_and_bands() -> void:
	# The ground: the kit's persona backdrop with its graphic elements
	# removed — in this scene the bands and sparkles are geometry, and
	# only the mottled, vignetted ground stays a print.
	var o := UZUUI.get_backdrop_options("persona")
	for k in ["band", "band2", "stars", "line", "band_under", "band_halftone"]:
		o.erase(k)
	o["size"] = Vector2i(1600, 900)
	var ground_mat := StandardMaterial3D.new()
	ground_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ground_mat.albedo_texture = ImageTexture.create_from_image(UZUUI.draw_backdrop(o))
	var quad := QuadMesh.new()
	quad.size = Vector2(17.0, 9.6)
	add_child(_solid(quad, ground_mat, Vector3(0, 0, -2.4)))

	# The main slash: a matte red solid with its white rule and black
	# under-band as thinner solids riding the same slant.
	var band := Node3D.new()
	band.position = Vector3(0, _wy(389), -1.15)
	band.rotation_degrees.z = 16.7
	band.add_child(_box(Vector3(17, 1.18, 0.12), _std(RED, 0.55)))
	band.add_child(_box(Vector3(17, 0.05, 0.10), _mat_white, Vector3(0, 0.66, 0.01)))
	band.add_child(_box(Vector3(17, 0.22, 0.09), _std(Color(0.012, 0.008, 0.012), 0.7), Vector3(0, -0.72, -0.01)))
	add_child(band)
	_register(band, 0.05, Vector3(6.5, 0, -0.6), 0.0)
	# The counter-slash, deep red, higher and thinner.
	var band2 := Node3D.new()
	band2.position = Vector3(0, _wy(220), -1.45)
	band2.rotation_degrees.z = -16.7
	band2.add_child(_box(Vector3(17, 0.44, 0.10), _std(DEEP_RED, 0.6)))
	add_child(band2)
	_register(band2, 0.12, Vector3(-6.5, 0, -0.6), 0.0)

	# Sparkles as billboards at mixed depths: the camera's sway moves
	# them against the bands — parallax a flat overlay cannot do.
	var smat := StandardMaterial3D.new()
	smat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	smat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	smat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	smat.albedo_texture = _sparkle_texture()
	var spots := [
		[2.8, 1.9, -0.7, 0.50], [-4.6, 2.3, -1.3, 0.36], [4.9, 0.9, -0.5, 0.30],
		[-1.8, 2.6, -1.7, 0.42], [0.9, 1.2, -0.9, 0.26], [5.6, 2.2, -1.9, 0.34],
	]
	for i in range(spots.size()):
		var sp: Array = spots[i]
		var q := QuadMesh.new()
		q.size = Vector2(sp[3], sp[3])
		var mi := _solid(q, smat, Vector3(sp[0], sp[1], sp[2]))
		add_child(mi)
		_sparkles.append({"node": mi, "base": sp[3], "phase": float(i) * 1.37})

	# The red ring accent, a real torus catching the light.
	var torus := TorusMesh.new()
	torus.inner_radius = 0.40
	torus.outer_radius = 0.50
	torus.rings = 48
	torus.ring_segments = 24
	var ring := _solid(torus, _std(RED, 0.4, 0.15), Vector3(4.34, -1.46, -0.75))
	ring.rotation_degrees = Vector3(72, 0, 12)
	add_child(ring)
	_register(ring, 0.3, Vector3(1.5, -1.0, -1.0), 40.0)


func _title() -> void:
	_backdrop_and_bands()
	# The logo: white Label3D over a red copy offset down-right — the
	# 2D version's offset shadow, here a real second surface the light
	# and the camera treat as one.
	var logo := Node3D.new()
	logo.position = Vector3(_wx(494), _wy(126), 0)
	logo.rotation_degrees = Vector3(0, -4, 4)
	var shadow := _label("真夜中クエスト", 92, RED)
	shadow.position = Vector3(0.10, -0.10, -0.05)
	logo.add_child(shadow)
	var face := _label("真夜中クエスト", 92, Color.WHITE, 14)
	logo.add_child(face)
	var sub := _label("MIDNIGHT QUEST", 30, YELLOW)
	sub.position = Vector3(_wx(324) - _wx(494), _wy(224) - _wy(126), 0.02)
	logo.add_child(sub)
	var tag := _label("真夜中の図書館を取り戻せ", 20, Color.WHITE)
	tag.position = Vector3(_wx(356) - _wx(494), _wy(268) - _wy(126), 0.02)
	logo.add_child(tag)
	add_child(logo)
	_register(logo, 0.0, Vector3(0, 3.4, -2.0), -14.0)

	# The watermark behind the bars, huge and nearly lost in the dark.
	# B-1322: at z=-0.95 its glyphs struck through the bars at nearly
	# their own depth and fought them; it now sits behind the bands,
	# higher and dimmer — a texture in the dark, not a second title.
	var wm := _label("MIDNIGHT", 150, Color(0.35, 0.02, 0.05, 0.16))
	wm.position = Vector3(0.6, -0.05, -1.8)
	wm.rotation_degrees.z = 4
	add_child(wm)

	var texts := ["はじめから", "つづきから", "せってい"]
	var centers := [Vector3(_wx(294), _wy(423), 0), Vector3(_wx(322), _wy(491), 0), Vector3(_wx(350), _wy(559), 0)]
	for i in range(3):
		var bar := _bar(texts[i], 4.60, i == 0)
		bar.position = centers[i]
		add_child(bar)
		_register(bar, 0.15 + 0.07 * i, Vector3(-7.5, 0, -1.5), -10.0)

	var credit := _label("U.ZU Engine sample", 16, Color(0.8, 0.8, 0.85))
	credit.position = Vector3(4.35, -2.95, -0.3)
	add_child(credit)


func _menu() -> void:
	_backdrop_and_bands()
	# The pause panel: one thick slash prism, tilted in depth, its
	# items as small bars standing off its face.
	var panel := Node3D.new()
	panel.position = Vector3(0, 0.1, 0)
	panel.rotation_degrees = Vector3(0, 5, 1.2)
	panel.add_child(_solid(_prism(5.34, 4.66, 0.20, 0.15), _mat_white, Vector3(0, 0, -0.07)))
	var face_mat := _std(RED, 0.38, 0.1)
	face_mat.emission_enabled = true
	face_mat.emission = RED
	face_mat.emission_energy_multiplier = 0.22
	panel.add_child(_solid(_prism(5.20, 4.52, 0.30, 0.15), face_mat, Vector3.ZERO))
	var wm := _label("PAUSE", 150, Color(0.9, 0.9, 0.9, 0.13))
	wm.position = Vector3(0.2, -0.2, 0.16)
	panel.add_child(wm)
	var head := _label("ポーズ", 36, Color.WHITE)
	head.position = Vector3(0.07, 1.80, 0.24)
	panel.add_child(head)
	var cap := _label("PAUSE", 16, YELLOW)
	cap.position = Vector3(0.07, 1.47, 0.24)
	panel.add_child(cap)
	var status := _label("ユウキ　Lv.12", 20, Color.WHITE)
	status.position = Vector3(-1.30, 1.06, 0.24)
	panel.add_child(status)
	_gauge(panel, "HP", 1.75, 0.74, 0.65)
	_gauge(panel, "MP", 1.15, 0.40, 0.40)
	var items := ["ゲームにもどる", "アイテム", "せってい", "タイトルへ"]
	for i in range(items.size()):
		var bar := _bar(items[i], 3.90, i == 0)
		bar.position = Vector3(-0.10, -0.28 - 0.56 * i, 0.16)
		panel.add_child(bar)
	add_child(panel)
	_register(panel, 0.0, Vector3(0, -4.5, -2.5), -8.0)


func _gauge(parent: Node3D, name: String, fill_w: float, y: float, _ratio: float) -> void:
	var lab := _label(name, 16, Color.WHITE)
	lab.position = Vector3(-1.55, y, 0.24)
	parent.add_child(lab)
	parent.add_child(_box(Vector3(2.6, 0.16, 0.06), _std(Color(0.05, 0.05, 0.06), 0.5), Vector3(0.35, y, 0.20)))
	parent.add_child(_box(Vector3(fill_w, 0.16, 0.09), _std(YELLOW, 0.35), Vector3(0.35 - (2.6 - fill_w) / 2, y, 0.21)))


# ---------------------------------------------------------------- motion

func _register(node: Node3D, delay: float, from_offset: Vector3, from_rot_z: float) -> void:
	_actors.append({
		"node": node, "to": node.position, "from": node.position + from_offset,
		"to_rot": node.rotation_degrees.z, "from_rot": node.rotation_degrees.z + from_rot_z,
		"delay": delay, "dur": 0.55,
	})
	node.position += from_offset
	node.rotation_degrees.z += from_rot_z


func _ease_out_back(x: float) -> float:
	var c1 := 1.70158
	var c3 := c1 + 1.0
	return 1.0 + c3 * pow(x - 1.0, 3.0) + c1 * pow(x - 1.0, 2.0)


func _set_focus(idx: int, t: float) -> void:
	if idx == _focus:
		return
	_focus = idx
	_focus_since = t
	for i in range(_bar_faces.size()):
		_bar_faces[i].set_surface_override_material(0, _mat_red if i == idx else _mat_black)


func _update(t: float) -> void:
	for a in _actors:
		var node: Node3D = a["node"]
		var p := clampf((t - float(a["delay"])) / float(a["dur"]), 0.0, 1.0)
		var e := _ease_out_back(p) if p < 1.0 else 1.0
		node.position = (a["from"] as Vector3).lerp(a["to"], e)
		node.rotation_degrees.z = lerpf(float(a["from_rot"]), float(a["to_rot"]), e)
	# Focus walks the bars on the reel; a still keeps the first lit.
	var idx := 0
	if t >= 3.2 and t < 4.6:
		idx = 1 % _bar_faces.size()
	elif t >= 4.6 and t < 6.0:
		idx = 2 % _bar_faces.size()
	_set_focus(idx, t)
	if _focus >= 0 and _focus < _bar_faces.size():
		var pulse := 1.0
		var since := t - _focus_since
		if since < 0.24:
			pulse = 1.0 + 0.05 * sin(since / 0.24 * PI)
		var face: MeshInstance3D = _bar_faces[_focus]
		var holder := face.get_parent() as Node3D
		if holder:
			holder.scale = Vector3.ONE * pulse
	# The camera rig sways; layers at different depths answer
	# differently — that difference is the parallax. B-1322: the rig
	# also holds a slight base angle (a low three-quarter view), so
	# the bars' thickness and the bands' edges read in a still too,
	# not only while the sway moves them.
	_rig.position = Vector3(0.14 * sin(t * 0.45), 0.09 * sin(t * 0.62 + 1.3), 0.30 * sin(t * 0.21))
	_rig.rotation_degrees.y = -1.6 + 1.1 * sin(t * 0.30)
	_rig.rotation_degrees.x = 1.2 + 0.5 * sin(t * 0.24 + 0.7)
	# The rake light works (B-1322): it drifts slowly across the
	# stage, so the specular streaks on the black bars and the torus
	# crawl instead of sitting frozen, and it flares for a beat when
	# focus lands — the light answers the hand.
	if _rake:
		_rake.position = Vector3(-4.5 + 1.3 * sin(t * 0.35), 2.5 + 0.5 * sin(t * 0.5 + 1.0), 4.0)
		var boost := 0.0
		if _focus >= 0:
			boost = 0.7 * exp(-(t - _focus_since) * 3.0)
		_rake.light_energy = 0.8 + 0.18 * sin(t * 0.8) + boost
	if _sun:
		_sun.rotation_degrees.y = -28.0 + 3.0 * sin(t * 0.23)
	for s in _sparkles:
		var mi: Node3D = s["node"]
		var sc: float = float(s["base"]) * (1.0 + 0.16 * sin(t * 2.2 + float(s["phase"])))
		mi.scale = Vector3(sc / float(s["base"]), sc / float(s["base"]), 1.0)


func _process(delta: float) -> void:
	if _still:
		return
	_t += delta
	_update(_t)


# ---------------------------------------------------------------- build

func _ready() -> void:
	_still = OS.get_environment("UZU_B1321_STILL") == "1"
	_mat_red = _std(RED, 0.30, 0.18)
	# The focused bar must read at the 2D print's strength: its face
	# sits at a grazing angle to the key light, so a touch of emission
	# carries the signal red where the light cannot.
	_mat_red.emission_enabled = true
	_mat_red.emission = RED
	_mat_red.emission_energy_multiplier = 0.45
	_mat_black = _std(INK, 0.32, 0.25)
	_mat_white = _std(Color(0.96, 0.96, 0.97), 0.45)

	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.043, 0.020, 0.031)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.35, 0.12, 0.14)
	env.ambient_light_energy = 0.7
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.glow_enabled = true
	env.glow_intensity = 0.5
	env.glow_strength = 1.0
	env.glow_bloom = 0.15
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	_sun = DirectionalLight3D.new()
	_sun.rotation_degrees = Vector3(-38, -28, 0)
	_sun.light_color = Color(1.0, 0.95, 0.88)
	_sun.light_energy = 1.15
	_sun.shadow_enabled = true
	add_child(_sun)
	_rake = OmniLight3D.new()
	_rake.position = Vector3(-4.5, 2.5, 4.0)
	_rake.light_color = Color(1.0, 0.85, 0.75)
	_rake.light_energy = 0.8
	_rake.omni_range = 14.0
	add_child(_rake)

	_rig = Node3D.new()
	add_child(_rig)
	var cam := Camera3D.new()
	cam.fov = 36.0
	cam.position = Vector3(0, 0, 10)
	_rig.add_child(cam)
	cam.current = true

	if OS.get_environment("UZU_B1321_SCREEN") == "menu":
		_menu()
	else:
		_title()

	if _still:
		_update(3.0)
