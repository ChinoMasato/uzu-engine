class_name RaceScreen
extends Control
## The race screen. B-1329's simulation and commentary phase machine
## are unchanged -- snapshots (ranks at 600m / 1200m, margins at the
## goal) still choose the lines, and everything stays deterministic
## for a given `seed_value`. B-1330 presented the race as a 2.5D
## composite of generated pictures; the owner's verdict was that
## pasted-together art breaks down as screen structure, so B-1332
## rebuilds the presentation as a real 3D scene (Forward+):
##
##   * the course is geometry -- mowed turf stripes, white rails
##     (the racecourse props' own meshes, MultiMesh'd down both
##     sides), distance markers, a hedge line, grandstands and
##     trees from the supplied GLB props, two starting-gate units;
##   * the horses are the rigged GLB (Gallop clip, 0.708 s) with
##     the seated jockey GLB riding the spine bone through a
##     BoneAttachment3D; coat tints, silk tints and a frame-colour
##     saddle cloth with the gate number tell the eight apart.
##     Gallop playback speed is locked to the sim speed so the
##     stride length stays constant (~6 m);
##   * a broadcast camera follows the pack from the near side,
##     pushes in over the last 400 m and settles on the winner;
##     the sim's slow-motion goal beat, a restrained flash and a
##     small camera shake carry over from B-1330;
##   * the HUD (title, clock, live ranking, remaining distance,
##     leader progress, commentary subtitles) stays 2D, drawn as
##     ordinary controls over the SubViewport.
##
## The 3D world lives in a SubViewport with its own World3D: the
## menu screens' full-rect backdrop rect would otherwise paint
## over any 3D drawn into the root viewport.
##
## Commentary mapping (audio/voice/README.md):
##   pre (fanfare -> gate-in -> ready) -> start (+clean/late note)
##   -> early (lead battle / leader / stretched / hold-back)
##   -> mid (front side / settled / corner)
##   -> final straight -> the move (holds on / outside / inside)
##   -> 200m -> 100m -> goal (win / push / close / photo)
##   -> win style (front-run / stalker / closer / runaway)
##   -> upset (long-shot winner) -> crowd -> closing.

signal race_finished(results: Array)
signal exit_requested

const DIST := 1800.0
const RANK_RECT := Rect2(868, 60, 272, 404)

# -- 3D layout (metres; the sim's `pos` is metres from the gate) --
const HORSE_SCALE := 2.3
const FOOT_LIFT := 0.404325 # horse model origin height, feet at 0
const START_BACK := 0.45 # horse origin sits this far behind pos
const GOAL_X := DIST - START_BACK
const LANE_DZ := 1.15 # the gate model's stall pitch
const GALLOP_REF := 8.5 # speed_scale = vel / this -> ~6 m stride

# Coat tints (multiplied over the bay base texture), per horse.
const COATS := [
	Color(1.00, 1.00, 1.00), # bay, as authored
	Color(0.52, 0.44, 0.40), # dark bay / brown
	Color(0.30, 0.27, 0.27), # near black
	Color(1.18, 0.72, 0.45), # chestnut
	Color(0.74, 0.72, 0.70), # grey
	Color(1.06, 0.88, 0.62), # palomino-ish
	Color(0.80, 0.52, 0.38), # liver chestnut
	Color(0.94, 0.84, 0.76), # light bay
]
# Gentle silk tints per gate (the base silk is red with white
# sleeves; kept mild so skin stays skin at broadcast distance).
const SILKS := [
	Color(1.00, 1.00, 1.00), Color(0.80, 0.85, 1.10),
	Color(1.05, 0.80, 0.55), Color(0.70, 0.95, 0.80),
	Color(1.05, 1.00, 0.60), Color(0.75, 0.90, 1.05),
	Color(1.08, 0.70, 0.75), Color(0.90, 0.80, 1.05),
]

var commentary: Commentary
var time_scale := 1.0
var seed_value := 1329

var _rng := RandomNumberGenerator.new()
var _runners: Array = [] # per gate: {horse, draw, pos, delay, wobble, jitter, vel, phase, finish_t, rank600, rank1200}
var _state := "idle" # idle | pre | run | done
var _clock := 0.0 # seconds since the gate opened (negative in pre)
var _fired := {}
var _results: Array = []
var _fps_samples: Array = []
var _fps_timer := 0.0

var _slowmo := 1.0
var _winner_at := -1.0 # real seconds when the winner crossed
var _flash := 0.0
var _shake := 0.0
var _elapsed := 0.0

var _phase_label: Label
var _clock_label: Label
var _subtitle: Label
var _subtitle_pill: Panel
var _fanfare: AudioStreamPlayer
var _remain_label: Label
var _row_labels: Array = []
var _row_chips: Array = []
var _progress_fill: ColorRect
var _flash_rect: ColorRect

var _world: Node3D
var _camera: Camera3D
var _cam_pos := Vector3(10.5, 2.6, 12.5)
var _cam_look := Vector3(0.0, 1.2, 0.0)
var _visuals: Array = [] # per gate: {root, anim, skel, dust, launched, coat_mat, silk_mat}


func _ready() -> void:
	_build_world()
	_build_hud()
	if commentary != null:
		commentary.line_changed.connect(func(text: String) -> void: _subtitle.text = text)


# ------------------------------------------------------------------ HUD

func _make_label(x: int, y: int, font_size: int) -> Label:
	var l := Label.new()
	l.position = Vector2(x, y)
	l.size = Vector2(700, 40)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_outline_color", Color(0.04, 0.08, 0.03, 0.9))
	l.add_theme_constant_override("outline_size", 6)
	return l


func _shade(rect: Rect2, color: Color) -> ColorRect:
	var r := ColorRect.new()
	r.position = rect.position
	r.size = rect.size
	r.color = color
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(r)
	return r


func _build_hud() -> void:
	# Header shades behind the title / clock labels.
	_shade(Rect2(10, 6, 660, 46), Color(0.02, 0.06, 0.03, 0.55))
	_shade(Rect2(862, 6, 280, 46), Color(0.02, 0.06, 0.03, 0.55))
	_phase_label = _make_label(24, 12, 27)
	add_child(_phase_label)
	_clock_label = _make_label(880, 14, 23)
	_clock_label.size = Vector2(248, 34)
	_clock_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	add_child(_clock_label)
	# Live ranking panel.
	var panel_box := StyleBoxFlat.new()
	panel_box.bg_color = Color(0.03, 0.09, 0.05, 0.88)
	panel_box.border_color = Color("#d9a441")
	panel_box.set_border_width_all(2)
	var panel := Panel.new()
	panel.position = RANK_RECT.position
	panel.size = RANK_RECT.size
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", panel_box)
	add_child(panel)
	var title := _make_label(882, 74, 19)
	title.text = "現在の順位"
	title.add_theme_color_override("font_color", Color("#f2d492"))
	add_child(title)
	_remain_label = _make_label(1018, 78, 15)
	_remain_label.add_theme_color_override("font_color", Color(1, 1, 1, 0.75))
	add_child(_remain_label)
	for i in range(8):
		var chip := ColorRect.new()
		chip.position = Vector2(882, 108 + i * 40)
		chip.size = Vector2(20, 20)
		chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(chip)
		_row_chips.append(chip)
		var row := _make_label(910, 105 + i * 40, 15)
		row.size = Vector2(218, 24)
		add_child(row)
		_row_labels.append(row)
	# Leader progress along the bottom of the turf.
	_shade(Rect2(12, 640, 1128, 5), Color(1, 1, 1, 0.16))
	_progress_fill = _shade(Rect2(12, 640, 0, 5), Color("#d9a441"))
	# Commentary subtitle on its pill.
	var pill_box := StyleBoxFlat.new()
	pill_box.bg_color = Color(0.0, 0.0, 0.0, 0.62)
	pill_box.set_corner_radius_all(10)
	_subtitle_pill = Panel.new()
	_subtitle_pill.position = Vector2(116, 498)
	_subtitle_pill.size = Vector2(920, 46)
	_subtitle_pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_subtitle_pill.add_theme_stylebox_override("panel", pill_box)
	_subtitle_pill.visible = false
	add_child(_subtitle_pill)
	_subtitle = _make_label(126, 503, 21)
	_subtitle.size = Vector2(900, 38)
	_subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_subtitle.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	add_child(_subtitle)
	# Goal flash, topmost.
	_flash_rect = _shade(Rect2(0, 0, 1152, 648), Color(1, 1, 1, 0))
	# Fanfare (the race owns the soundscape; BGM stops upstream).
	_fanfare = AudioStreamPlayer.new()
	_fanfare.bus = "BGM"
	_fanfare.stream = load("res://audio/fanfare.mp3")
	add_child(_fanfare)


func _update_hud() -> void:
	_flash_rect.color = Color(1, 1, 1, _flash * 0.45)
	_subtitle_pill.visible = _subtitle.text != ""
	if _runners.size() < 8:
		return
	var leader := _leader_pos()
	_remain_label.text = "残り %.0fm" % maxf(DIST - leader, 0.0)
	_progress_fill.size.x = 1128.0 * clampf(leader / DIST, 0.0, 1.0)
	var order := _order()
	for i in range(8):
		var r: Dictionary = _runners[order[i]]
		var gate := int(r["gate"])
		(_row_chips[i] as ColorRect).color = Color(str(StarHorseData.FRAME_COLORS[gate - 1]))
		var text := "%d. %s" % [i + 1, str(r["horse"]["name"])]
		if float(r["finish_t"]) > 0.0:
			text += " GOAL"
		elif i > 0:
			text += " (-%.0f)" % (leader - float(r["pos"]))
		(_row_labels[i] as Label).text = text


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and (event as InputEventKey).keycode == KEY_ESCAPE:
		exit_requested.emit()


# ------------------------------------------------------------------ 3D world

func _lane_z(gate: int) -> float:
	return (float(gate) - 4.5) * LANE_DZ


func _mat(color: Color, roughness := 0.95) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	return m


var _unit_box := BoxMesh.new()


func _box(size: Vector3, pos: Vector3, mat: Material, parent: Node) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = _unit_box
	mi.material_override = mat
	mi.scale = size
	mi.position = pos
	parent.add_child(mi)
	return mi


func _build_world() -> void:
	_unit_box.size = Vector3.ONE
	var container := SubViewportContainer.new()
	container.set_anchors_preset(Control.PRESET_FULL_RECT)
	container.stretch = true
	container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(container)
	var vp := SubViewport.new()
	vp.own_world_3d = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	container.add_child(vp)
	_world = Node3D.new()
	vp.add_child(_world)

	var we := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color("#2f5fb3")
	sky_mat.sky_horizon_color = Color("#bcd9e8")
	sky_mat.ground_bottom_color = Color("#2c4a2e")
	sky_mat.ground_horizon_color = Color("#bcd9e8")
	sky.sky_material = sky_mat
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 1.05
	env.fog_enabled = true
	env.fog_light_color = Color("#c3d9e2")
	env.fog_light_energy = 0.7
	env.fog_density = 0.0011
	env.fog_sky_affect = 0.35
	we.environment = env
	_world.add_child(we)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -35, 0)
	sun.light_energy = 1.25
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 170.0
	sun.shadow_blur = 1.3
	_world.add_child(sun)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-25, 140, 0)
	fill.light_color = Color("#bfd4ff")
	fill.light_energy = 0.3
	fill.shadow_enabled = false
	_world.add_child(fill)

	_camera = Camera3D.new()
	_camera.far = 1200.0
	_camera.fov = 50.0
	_camera.position = _cam_pos
	_world.add_child(_camera)
	_camera.current = true

	_build_course()
	_build_runners()


func _build_course() -> void:
	var course := Node3D.new()
	course.name = "Course"
	_world.add_child(course)
	# Base ground, then the turf strip as mowing stripes (60 m
	# bands alternating shade -- the stripes make speed readable).
	_box(Vector3(2500, 0.1, 600), Vector3(850, -0.07, 0), _mat(Color("#3a7a38")), course)
	var turf_a := _mat(Color("#55a24b"))
	var turf_b := _mat(Color("#4c9843"))
	for i in range(34):
		var x0 := -100.0 + i * 60.0
		_box(Vector3(60, 0.1, 12.6), Vector3(x0 + 30.0, -0.05, 0),
			turf_a if i % 2 == 0 else turf_b, course)
	# Finish line across the turf.
	_box(Vector3(0.6, 0.012, 12.6), Vector3(GOAL_X, 0.006, 0), _mat(Color("#f2f2ee"), 0.5), course)
	# Hedge line behind the far rail: a clean horizon for the pack.
	_box(Vector3(2000, 1.0, 1.0), Vector3(850, 0.5, -8.6), _mat(Color("#2e6b31")), course)

	var props_tpl := (load("res://models/racecourse_props.glb") as PackedScene).instantiate()
	_build_rails(props_tpl, course)
	_build_goal_and_markers(props_tpl, course)
	_build_stands(course)
	_build_trees(props_tpl, course)
	props_tpl.free()

	# Two 4-stall gate units; stall centres land exactly on the
	# sim's lanes ((gate - 4.5) * 1.15).
	var gate_ps := load("res://models/starting_gate.glb") as PackedScene
	for side in [2.3, -2.3]:
		var gate := gate_ps.instantiate() as Node3D
		gate.position = Vector3(0, 0, side)
		course.add_child(gate)


func _build_rails(props_tpl: Node, course: Node) -> void:
	var post_mesh := (props_tpl.get_node("Rail_Post_1") as MeshInstance3D).mesh
	var rail_mesh := (props_tpl.get_node("Rail_Rail_1") as MeshInstance3D).mesh
	# Posts every 4 m down both sides.
	var posts := MultiMesh.new()
	posts.transform_format = MultiMesh.TRANSFORM_3D
	posts.mesh = post_mesh
	var post_xf: Array = []
	for side in [-6.0, 6.0]:
		var x := -56.0
		while x <= 1864.0:
			post_xf.append(Transform3D(Basis(), Vector3(x, 0.52, side)))
			x += 4.0
	posts.instance_count = post_xf.size()
	for i in range(post_xf.size()):
		posts.set_instance_transform(i, post_xf[i])
	var post_mmi := MultiMeshInstance3D.new()
	post_mmi.multimesh = posts
	post_mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	post_mmi.custom_aabb = AABB(Vector3(-80, -1, -10), Vector3(2000, 4, 20))
	course.add_child(post_mmi)
	# The prop's rail bar runs along its local Y; its node basis
	# (from the GLB) turns it onto X. Two heights, both sides.
	var rail_basis := Basis(Vector3(0, -1, 0), Vector3(1, 0, 0), Vector3(0, 0, 1))
	var rails := MultiMesh.new()
	rails.transform_format = MultiMesh.TRANSFORM_3D
	rails.mesh = rail_mesh
	var rail_xf: Array = []
	for side in [-6.0, 6.0]:
		for h in [0.95, 0.55]:
			var cx := -54.6
			while cx <= 1866.0:
				rail_xf.append(Transform3D(rail_basis, Vector3(cx, h, side)))
				cx += 8.4
	rails.instance_count = rail_xf.size()
	for i in range(rail_xf.size()):
		rails.set_instance_transform(i, rail_xf[i])
	var rail_mmi := MultiMeshInstance3D.new()
	rail_mmi.multimesh = rails
	rail_mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	rail_mmi.custom_aabb = AABB(Vector3(-80, -1, -10), Vector3(2000, 4, 20))
	course.add_child(rail_mmi)


func _prop_dup(props_tpl: Node, node_name: String, pos: Vector3, parent: Node) -> Node3D:
	var n := props_tpl.get_node(node_name).duplicate() as Node3D
	n.position = pos
	parent.add_child(n)
	return n


func _build_goal_and_markers(props_tpl: Node, course: Node) -> void:
	var font := load("res://art/game_font_jp.ttf") as Font
	# The winning-post assembly stands at the far rail.
	_prop_dup(props_tpl, "GoalPost_L", Vector3(GOAL_X, 1.3, -6.35), course)
	_prop_dup(props_tpl, "GoalPost_R", Vector3(GOAL_X, 1.3, -4.65), course)
	_prop_dup(props_tpl, "Goal_CrossBoard", Vector3(GOAL_X, 2.55, -5.5), course)
	_prop_dup(props_tpl, "Goal_TopBall", Vector3(GOAL_X, 2.78, -5.5), course)
	# Distance markers every 200 m, labelled with the distance
	# remaining (the JRA convention).
	for m in range(200, 1800, 200):
		_prop_dup(props_tpl, "DistanceMarker", Vector3(m, 0.5, -5.55), course)
		_prop_dup(props_tpl, "DistanceMarker_Top", Vector3(m, 1.05, -5.55), course)
		var label := Label3D.new()
		label.text = str(1800 - m)
		label.font = font
		label.font_size = 128
		label.pixel_size = 0.0075
		label.modulate = Color(1, 1, 1, 0.95)
		label.outline_size = 16
		label.outline_modulate = Color(0.05, 0.1, 0.05, 0.9)
		label.position = Vector3(m, 1.8, -5.55)
		course.add_child(label)


func _build_stands(course: Node) -> void:
	var stand_ps := load("res://models/grandstand.glb") as PackedScene
	# The stand model faces its local -X; a quarter turn puts the
	# front to the track and its 11 m length along the course.
	# Scaled x2.2 so it reads as a stand, not a toy (24 m long,
	# 13 m tall). Four span the finish, two back the start.
	for sx in [1666.0, 1690.6, 1715.2, 1739.8, -52.0, -27.4]:
		var st := stand_ps.instantiate() as Node3D
		st.rotation.y = PI / 2.0
		st.scale = Vector3.ONE * 2.2
		st.position = Vector3(sx, 0, -26.0)
		course.add_child(st)


func _build_trees(props_tpl: Node, course: Node) -> void:
	var parts := {
		"Tree_Trunk": Vector3(-3.2, 0.75, 1.6),
		"Tree_Leaf_1": Vector3(-3.2, 2.15, 1.6),
		"Tree_Leaf_2": Vector3(-2.65, 1.75, 1.25),
		"Tree_Leaf_3": Vector3(-3.75, 1.8, 1.95),
	}
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var x := -30.0
	while x < 1850.0:
		if not (x > 1620.0 and x < 1790.0): # keep the stands clear
			var tree := Node3D.new()
			tree.position = Vector3(x + rng.randf_range(-14.0, 14.0), 0, -14.5 + rng.randf_range(-2.5, 2.5))
			tree.rotation.y = rng.randf_range(0.0, TAU)
			var s := rng.randf_range(1.4, 2.1)
			tree.scale = Vector3.ONE * s
			for part_name in parts:
				var dup := props_tpl.get_node(part_name).duplicate() as Node3D
				dup.position = (parts[part_name] as Vector3) - Vector3(-3.2, 0, 1.6)
				tree.add_child(dup)
			course.add_child(tree)
		x += rng.randf_range(95.0, 150.0)
	# Bushes dotted along the hedge.
	x = 30.0
	while x < 1800.0:
		var bush := props_tpl.get_node("Bush_1").duplicate() as Node3D
		bush.position = Vector3(x, 0.3, -7.6)
		bush.scale = Vector3.ONE * rng.randf_range(1.2, 1.9)
		course.add_child(bush)
		x += rng.randf_range(120.0, 220.0)


func _build_runners() -> void:
	var horse_ps := load("res://models/horse.glb") as PackedScene
	var jockey_ps := load("res://models/jockey.glb") as PackedScene
	var font := load("res://art/game_font_jp.ttf") as Font
	# Soft puff sprite generated in code: art/dust.png is an
	# alpha-only black mask (RGB all zero), which tints to solid
	# black as a 3D billboard -- the puff needs real RGB with a
	# radial alpha falloff instead.
	var puff := Image.create(64, 64, false, Image.FORMAT_RGBA8)
	for py in range(64):
		for px in range(64):
			var d := Vector2(px - 31.5, py - 31.5).length() / 31.5
			var a := clampf(1.0 - d, 0.0, 1.0)
			puff.set_pixel(px, py, Color(1, 1, 1, a * a))
	var dust_tex := ImageTexture.create_from_image(puff)
	for gate in range(1, 9):
		var root := Node3D.new()
		root.name = "Runner%d" % gate
		root.rotation.y = PI / 2.0 # the model faces +Z; run along +X
		root.position = Vector3(-START_BACK, 0, _lane_z(gate))
		_world.add_child(root)
		var mount := Node3D.new()
		mount.scale = Vector3.ONE * HORSE_SCALE
		root.add_child(mount)
		var horse := horse_ps.instantiate() as Node3D
		horse.position.y = FOOT_LIFT
		mount.add_child(horse)
		var skel := horse.find_child("Skeleton3D") as Skeleton3D
		var anim := horse.find_child("AnimationPlayer") as AnimationPlayer
		# Coat tint: a private copy of the authored material.
		var horse_mi := horse.find_child("Mesh_0") as MeshInstance3D
		var coat_mat := horse_mi.get_surface_override_material(0)
		if coat_mat == null:
			coat_mat = horse_mi.mesh.surface_get_material(0)
		coat_mat = coat_mat.duplicate() as Material
		horse_mi.set_surface_override_material(0, coat_mat)
		# The jockey and the saddle cloth ride the spine bone.
		var spine := skel.find_bone("spine")
		var rest := skel.get_bone_global_rest(spine)
		var attach := BoneAttachment3D.new()
		attach.bone_name = "spine"
		skel.add_child(attach)
		var jockey := jockey_ps.instantiate() as Node3D
		jockey.transform = rest.affine_inverse() * Transform3D(Basis(), Vector3(0, 0.27, -0.03))
		attach.add_child(jockey)
		var jockey_mi := jockey.find_child("Mesh_0") as MeshInstance3D
		var silk_mat := jockey_mi.get_surface_override_material(0)
		if silk_mat == null:
			silk_mat = jockey_mi.mesh.surface_get_material(0)
		silk_mat = silk_mat.duplicate() as Material
		jockey_mi.set_surface_override_material(0, silk_mat)
		# Saddle cloth in the frame colour + the gate number on
		# both flanks, in the same bone space as the jockey.
		var cloth := MeshInstance3D.new()
		cloth.mesh = _unit_box
		cloth.material_override = _mat(Color(str(StarHorseData.FRAME_COLORS[gate - 1])), 0.85)
		cloth.transform = rest.affine_inverse() * Transform3D(
			Basis().scaled(Vector3(0.40, 0.26, 0.30)), Vector3(0, 0.17, -0.03))
		attach.add_child(cloth)
		for side_sign in [1.0, -1.0]:
			var num := Label3D.new()
			num.text = str(gate)
			num.font = font
			num.font_size = 160
			num.pixel_size = 0.0011
			num.modulate = Color(0.08, 0.08, 0.08) if gate == 1 else Color.WHITE
			num.outline_size = 20
			num.outline_modulate = Color.WHITE if gate == 1 else Color(0.05, 0.05, 0.05)
			var basis := Basis.from_euler(Vector3(0, side_sign * PI / 2.0, 0))
			num.transform = rest.affine_inverse() * Transform3D(
				basis, Vector3(side_sign * 0.215, 0.17, -0.03))
			attach.add_child(num)
		# Name tag floating over the back (kept off the scaled
		# mount so the text size is in plain metres).
		var tag := Label3D.new()
		tag.name = "NameTag"
		tag.font = font
		tag.font_size = 64
		tag.pixel_size = 0.0055
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		tag.modulate = Color(1, 1, 1, 0.92)
		tag.outline_size = 10
		tag.outline_modulate = Color(0.02, 0.05, 0.03, 0.85)
		# Stagger the tag height by gate so a bunched field does
		# not pile every name onto the same line.
		tag.position = Vector3(0, 2.5 + float(gate % 3) * 0.24, 0)
		root.add_child(tag)
		# Turf dust at the hooves.
		var dust := CPUParticles3D.new()
		dust.amount = 18
		dust.lifetime = 0.8
		dust.local_coords = false
		dust.emitting = false
		dust.direction = Vector3(-1, 0.35, 0)
		dust.spread = 25.0
		dust.gravity = Vector3(0, -0.3, 0)
		dust.initial_velocity_min = 1.5
		dust.initial_velocity_max = 3.5
		dust.scale_amount_min = 0.6
		dust.scale_amount_max = 1.4
		var quad := QuadMesh.new()
		quad.size = Vector2(0.55, 0.55)
		var dust_mat := StandardMaterial3D.new()
		dust_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		dust_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		dust_mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
		dust_mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		dust_mat.albedo_texture = dust_tex
		dust_mat.albedo_color = Color(0.87, 0.82, 0.66, 0.5)
		quad.material = dust_mat
		dust.mesh = quad
		dust.position = Vector3(-1.5, 0.3, 0)
		root.add_child(dust)
		_visuals.append({
			"root": root, "anim": anim, "skel": skel, "dust": dust,
			"tag": tag, "launched": false,
			"coat_mat": coat_mat, "silk_mat": silk_mat,
		})


func _update_world(dt: float) -> void:
	for i in range(_runners.size()):
		var r: Dictionary = _runners[i]
		var v: Dictionary = _visuals[i]
		var root := v["root"] as Node3D
		root.position.x = float(r["pos"]) - START_BACK
		var anim := v["anim"] as AnimationPlayer
		var vel := float(r["vel"])
		if _state == "run" and float(r["delay"]) <= 0.0:
			if not v["launched"]:
				v["launched"] = true
				anim.play("Gallop")
			# Lock the stride to the *ground* speed: under the
			# goal slow-motion (or a fast-forward time_scale) the
			# legs must slow with the world, not run in place.
			anim.speed_scale = clampf(vel * _slowmo * time_scale / GALLOP_REF, 0.0, 3.0)
		(v["dust"] as CPUParticles3D).emitting = _state == "run" and vel > 6.0
	_update_camera(dt)


func _update_camera(dt: float) -> void:
	var target_pos: Vector3
	var target_look: Vector3
	if _state == "run":
		var leader := _leader_pos()
		var focus := leader - START_BACK
		if _fired.has("goal"):
			focus = float(_runners[_order()[0]]["pos"]) - START_BACK
		var t := clampf((leader - 1400.0) / 400.0, 0.0, 1.0)
		target_pos = Vector3(focus - 3.0, lerpf(2.8, 2.25, t), lerpf(16.5, 11.0, t))
		target_look = Vector3(focus + 8.0, 1.15, -0.8)
	else:
		# Gate view: doors and heads from the front quarter,
		# the start stands behind the field.
		target_pos = Vector3(10.5, 2.6, 12.5)
		target_look = Vector3(0.0, 1.2, 0.0)
	var k := 1.0 - exp(-dt * 3.2)
	_cam_pos = _cam_pos.lerp(target_pos, k)
	_cam_look = _cam_look.lerp(target_look, k)
	_camera.position = _cam_pos + Vector3(sin(_elapsed * 91.0), cos(_elapsed * 77.0), 0) * _shake * 0.03
	if _camera.position.distance_squared_to(_cam_look) > 0.01:
		_camera.look_at(_cam_look, Vector3.UP)


# ------------------------------------------------------------------ sim

## Starts (or restarts) the race: fanfare, gate-in, ready, then run.
func start_race() -> void:
	_rng.seed = seed_value
	_runners.clear()
	for gate in range(1, 9):
		var draw: Dictionary = StarHorseData.DRAW[gate - 1]
		var horse: Dictionary = StarHorseData.HORSES[int(draw["horse"])]
		_runners.append({
			"gate": gate, "horse": horse, "draw": draw,
			"pos": 0.0, "delay": 0.0, "wobble": _rng.randf_range(0.0, TAU),
			"jitter": 0.0, "vel": 0.0, "phase": _rng.randf_range(0.0, TAU),
			"finish_t": -1.0, "rank600": 0, "rank1200": 0,
		})
		var v: Dictionary = _visuals[gate - 1]
		(v["coat_mat"] as StandardMaterial3D).albedo_color = COATS[int(draw["horse"])]
		(v["silk_mat"] as StandardMaterial3D).albedo_color = SILKS[gate - 1]
		(v["tag"] as Label3D).text = "%d %s" % [gate, str(horse["name"])]
		(v["anim"] as AnimationPlayer).stop()
		(v["skel"] as Skeleton3D).reset_bone_poses()
		v["launched"] = false
		(v["root"] as Node3D).position.x = -START_BACK
	# One horse may break late; with the sample field it is the
	# deep closer in gate 4 about half the time -- decided by the seed.
	if _rng.randf() < 0.55:
		var late: Dictionary = _runners[_rng.randi_range(0, 7)]
		late["delay"] = _rng.randf_range(0.4, 0.7)
	_state = "pre"
	_cam_pos = Vector3(10.5, 2.6, 12.5)
	_cam_look = Vector3(0.0, 1.2, 0.0)
	_clock = -6.5
	_fired.clear()
	_results.clear()
	_fps_samples.clear()
	_slowmo = 1.0
	_winner_at = -1.0
	_flash = 0.0
	_shake = 0.0
	_phase_label.text = "中山11R %s（芝 %dm）" % [StarHorseData.RACE_NAME, StarHorseData.RACE_DISTANCE]
	_fanfare.play()


func _process(delta: float) -> void:
	_elapsed += delta
	_flash = maxf(_flash - delta * 1.6, 0.0)
	_shake = maxf(_shake - delta * 9.0, 0.0)
	if _state != "pre" and _state != "run":
		_update_hud()
		return
	# Slow motion over the last metres, released once the winner is in.
	var leader := _leader_pos()
	var target := 1.0
	if leader >= 1690.0 and _winner_at < 0.0:
		target = 0.32
	_slowmo = lerpf(_slowmo, target, clampf(delta * 2.2, 0.0, 1.0))
	var dt := delta * time_scale * _slowmo
	_clock += dt
	_fps_timer += delta
	if _fps_timer >= 1.0:
		_fps_timer = 0.0
		_fps_samples.append(Engine.get_frames_per_second())
	if _state == "pre":
		_pre_events()
		if _clock >= 0.0:
			_state = "run"
			_say("start", "03_start")
	else:
		_step(dt)
		_run_events()
		_maybe_finish()
	# The camera smooths on *race* time (dt), not wall time: under a
	# fast-forward time_scale the broadcast pan must keep up with the
	# field instead of lagging a fixed number of frames behind it.
	_update_world(dt)
	_clock_label.text = "%.1f" % maxf(_clock, 0.0)
	_update_hud()


func _pre_events() -> void:
	if _clock >= -5.6 and not _fired.has("gatein"):
		_fired["gatein"] = true
		_say("pre_gatein", "01_pre_gatein")
	if _clock >= -2.8 and not _fired.has("ready"):
		_fired["ready"] = true
		_say("pre_ready", "02_pre_ready")


func _base_speed(horse: Dictionary) -> float:
	return 14.6 + float(horse["speed"]) * 0.030


func _step(dt: float) -> void:
	for r in _runners:
		if r["delay"] > 0.0:
			r["delay"] = float(r["delay"]) - dt
			r["vel"] = 0.0
			continue
		var horse: Dictionary = r["horse"]
		var p := clampf(float(r["pos"]) / DIST, 0.0, 1.0)
		var style := str(horse["style"])
		var factor := 1.0
		if p < 0.55:
			factor = {"逃げ": 1.045, "先行": 1.02, "差し": 0.985, "追込": 0.965}[style]
		else:
			factor = {"逃げ": 0.985, "先行": 1.0, "差し": 1.025, "追込": 1.045}[style]
		if p > 0.66:
			factor *= 1.0 - (1.0 - float(horse["stamina"]) / 100.0) * 0.16 * ((p - 0.66) / 0.34)
		r["wobble"] = float(r["wobble"]) + dt * 0.7
		r["jitter"] = lerpf(float(r["jitter"]), _rng.randf_range(-0.012, 0.012), dt * 2.0)
		var ramp := clampf(maxf(_clock, 0.0) / 2.5, 0.25, 1.0)
		var v := _base_speed(horse) * factor * ramp * (1.0 + 0.008 * sin(float(r["wobble"])) + float(r["jitter"]))
		if float(r["finish_t"]) > 0.0:
			v *= 0.92 # easing down past the goal
		r["vel"] = v
		r["pos"] = float(r["pos"]) + v * dt
		r["phase"] = float(r["phase"]) + dt * v * 0.8
		if float(r["finish_t"]) < 0.0 and float(r["pos"]) >= DIST:
			r["finish_t"] = _clock
			if _winner_at < 0.0:
				_winner_at = _elapsed


func _order() -> Array:
	var idx := range(8)
	idx.sort_custom(func(a: int, b: int) -> bool: return float(_runners[a]["pos"]) > float(_runners[b]["pos"]))
	return idx


func _leader_pos() -> float:
	var best := 0.0
	for r in _runners:
		best = maxf(best, float(r["pos"]))
	return best


func _say(phase: String, voice_id: String) -> void:
	if commentary != null:
		commentary.say(phase, voice_id, _clock)


func _once(key: String, at: float) -> bool:
	if _leader_pos() >= at and not _fired.has(key):
		_fired[key] = true
		return true
	return false


func _run_events() -> void:
	var order := _order()
	var leader: Dictionary = _runners[order[0]]
	var second: Dictionary = _runners[order[1]]
	# Start note.
	if _clock >= 0.9 and not _fired.has("start_note"):
		_fired["start_note"] = true
		var late := false
		for r in _runners:
			if float(r["pos"]) < 2.0 and _clock > 0.9:
				late = true
		# A horse still near the gate at 0.9 s broke late.
		_say("start_note", "05_start_late" if late else "04_start_clean")
	# Early.
	if _once("lead_battle", 200.0):
		if float(leader["pos"]) - float(second["pos"]) <= 2.5:
			_say("early", "06_early_lead_battle")
	if _once("leader_intro", 400.0):
		_say("early", "07_early_leader")
	if _once("snap600", 600.0):
		for i in range(8):
			_runners[order[i]]["rank600"] = i + 1
		var spread := float(leader["pos"]) - float(_runners[order[7]]["pos"])
		if spread >= 30.0:
			_say("early", "08_early_stretched")
	if _once("holdback", 700.0):
		for i in range(6, 8):
			if str(_runners[order[i]]["horse"]["style"]) == "追込":
				_say("early", "09_early_holdback")
				break
	# Mid.
	if _once("frontside", 900.0):
		_say("mid", "10_mid_frontside")
	if _once("settled", 1100.0):
		_say("mid", "11_mid_settled")
	if _once("snap1200", 1200.0):
		for i in range(8):
			_runners[order[i]]["rank1200"] = i + 1
		_say("mid", "12_mid_corner")
	# Final.
	if _once("straight", 1400.0):
		_say("final_straight", "13_final_straight")
	if _once("move", 1500.0):
		if int(leader["rank1200"]) >= 4:
			_say("final_move", "15_final_outside")
		elif int(leader["rank600"]) == 1 and int(leader["rank1200"]) == 1:
			_say("final_move", "14_final_leader")
		else:
			_say("final_move", "16_final_inside")
	if _once("200m", 1600.0):
		_say("final_200", "17_final_200m")
	if _once("100m", 1700.0):
		_say("final_100", "18_final_100m")
	# Goal: the commentary fires as the winner crosses; the field
	# keeps running so the result board gets real times.
	if not _fired.has("goal") and float(leader["finish_t"]) > 0.0:
		_fired["goal"] = true
		_flash = 1.0
		_shake = 6.0
		_goal_commentary(leader, second)


func _goal_commentary(winner: Dictionary, second: Dictionary) -> void:
	var margin := float(winner["pos"]) - float(second["pos"])
	if margin < 1.2:
		_say("goal", "22_goal_photo")
	elif margin < 4.0:
		_say("goal", "21_goal_close")
	elif int(winner["rank600"]) == 1 and int(winner["rank1200"]) == 1:
		_say("goal", "20_goal_push")
	else:
		_say("goal", "19_goal_win")
	if margin >= 25.0:
		_say("win_style", "26_win_runaway")
	elif int(winner["rank600"]) == 1:
		_say("win_style", "23_win_frontrun")
	elif str(winner["horse"]["style"]) == "追込":
		_say("win_style", "25_win_closer")
	else:
		_say("win_style", "24_win_stalker")
	if int(winner["draw"]["popularity"]) >= 6:
		_say("upset", "27_upset")
	_say("crowd", "28_crowd")
	_say("closing", "29_closing")


## Ends the race once the whole field is in, or 6 s after the winner.
## Results carry a "margin" string for the result screen's table.
func _maybe_finish() -> void:
	if not _fired.has("goal"):
		return
	var win_t := -1.0
	var all_in := true
	for r in _runners:
		if float(r["finish_t"]) > 0.0:
			win_t = float(r["finish_t"]) if win_t < 0.0 else minf(win_t, float(r["finish_t"]))
		else:
			all_in = false
	if not all_in and _clock < win_t + 6.0:
		return
	_state = "done"
	# Results: finishers by time, the rest by position.
	var done := _runners.filter(func(r: Dictionary) -> bool: return float(r["finish_t"]) > 0.0)
	done.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["finish_t"]) < float(b["finish_t"]))
	var rest := _runners.filter(func(r: Dictionary) -> bool: return float(r["finish_t"]) <= 0.0)
	rest.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["pos"]) > float(b["pos"]))
	_results = done + rest
	for i in range(_results.size()):
		var r: Dictionary = _results[i]
		if i == 0:
			r["margin"] = "%.2f" % win_t
		elif float(r["finish_t"]) > 0.0:
			r["margin"] = "+%.2f秒" % (float(r["finish_t"]) - win_t)
		else:
			r["margin"] = "大差"
	race_finished.emit(_results)


func fps_average() -> float:
	if _fps_samples.is_empty():
		return 0.0
	var sum := 0.0
	for f in _fps_samples:
		sum += float(f)
	return sum / _fps_samples.size()
