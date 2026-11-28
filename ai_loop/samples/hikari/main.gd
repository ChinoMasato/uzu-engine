extends Node3D
## 灯りの欠片 (Shards of Light) — U.ZU Engine all-features sample game.
##
## A five-minute HD-2D mini game: dusk falls on a small village, three light
## shards are scattered around it, and the player returns them to the shrine
## lantern. Built entirely from code (no editor GUI), lit by UZULook's HD-2D
## preset, with telemetry checkpoints and a time-of-day progression driven
## by the quest state.

const InputSetup := preload("res://input_setup.gd")
const TouchControls := preload("res://touch_controls.gd")
const FONT := preload("res://art/game_font.ttf")
## The UI's world (B-1307): wafu — parchment frames, dark-brown edges and a
## vermilion accent, for a village of wooden houses, a shrine and paper
## lanterns; its motion is a quiet quart ease-out (no overshoot).
const WORLD := "wafu"

const WORLD_X := 15.5
const WORLD_Z := 11.5
const PLAYER_SPEED := 3.4

## The village layout is generated (B-1508): a UZUWorldGen city (houses,
## streets, plaza, fountain) standing on a UZUWorldGen nature map, with a
## second small nature map whose bowl is the pond. Fixed seeds keep the
## village identical on every run, and the specs are static functions so
## compose_village.gd builds the very same village for walking checks and
## captures. The shrine, its lantern, the crates and the cast stay
## hand-placed below: their positions are the game's fixed conditions.
const CITY_CENTRE := Vector2(-21, -2)
const CITY_EDGE := 26.5 # Half the city size plus half a road width.
const LAND_SEED := 172
const POND_SEED := 61
const CITY_SEED := 1
## The generated village is deterministic, so it is also baked ahead of
## time into a binary scene (bake_world.gd -> res://baked_village.scn)
## and adopted at start when its fingerprint matches the specs below;
## generation at runtime is the fallback, not the normal path. Bump
## WORLD_BUILD_VERSION whenever the build steps change shape (levelling,
## trims, the foundation), so a stale bake can never be served.
const WORLD_BUILD_VERSION := 1
const BAKED_WORLD_PATH := "res://baked_village.scn"
const POND_POS := Vector3(5.5, -0.37, 1.0)
const POND_CENTRE := Vector2(9.5, 4.5)
const POND_WATER_Y := -0.139 # POND_POS.y + the pond spec's water_level * height.

var land_map: Node3D
var pond_map: Node3D
var city_map: Node3D

static func land_spec() -> Dictionary:
	return {
		"size": 256.0, "cell": 4.0, "seed": LAND_SEED, "height": 2.2, "roughness": 0.3,
		"water": false, "snow_line": 2.0, "trees": 2.0, "rocks": 0.4, "grass": 6.0,
		"name": "Land", "position": [0, 0, 0],
	}

static func pond_spec() -> Dictionary:
	return {
		"size": 32.0, "cell": 1.0, "seed": POND_SEED, "height": 0.7, "roughness": 0.35,
		"water_level": 0.33, "snow_line": 2.0, "trees": 0.0, "rocks": 0.0, "grass": 0.0,
		"name": "Pond", "position": [POND_POS.x, POND_POS.y, POND_POS.z],
	}

static func city_spec() -> Dictionary:
	return {
		"preset": "village", "size": 48.0, "block": 16.0, "seed": CITY_SEED, "ground": false,
		"name": "Village", "position": [CITY_CENTRE.x, 0, CITY_CENTRE.y],
	}

var player: Sprite3D
var camera: Camera3D
var sun: DirectionalLight3D
var env: Environment
var lantern_light: OmniLight3D
var lantern_pos := Vector3(0, 0, -9.0)

var shards := 0
## Juice events fired so far (B-1107): the verification reads this back to
## prove UZUJuice actually fired during a playthrough.
var juice_events: Array = []
## Juice on/off for feel measurement (B-1112): the user arg
## "--uzu-no-juice" disables every UZUJuice / UZUUIJuice effect call in
## this file, so the same playthrough can be measured with and without
## them. The game's own record (juice_events) is kept either way, and
## panel visibility ends up the same (see _juice_motion).
var juice_enabled := true
var cleared := false
var play_seconds := 0.0
var sfx_events: Array = [] # Sound firing log (B-1704), mirrors juice_events.
var sound: HikariSound # B-1704: Lumina/SFX wiring (see sound.gd).
var dialogue_lines: Array = []
var lantern_glow := 0.0

var obstacles: Array = [] # {pos: Vector2, r: float}
var interactables: Array = [] # {pos: Vector3, kind: String, id: String, label: String, node: Node3D}
var nearest_interactable: Dictionary = {}

var ui_root: Control
var hud_panel: PanelContainer
var hud_shards: Label
var hud_shard_icons: Array[TextureRect] = [] # One shard icon per shard (B-1315).
var hud_objective: Label
var help_label: Label
var prompt_panel: PanelContainer
var prompt_label: Label
var dialogue_panel: Control # A UZUUI talk window (B-1302): name tag + window.
var dialogue_name: Label
var dialogue_text: Label
var dialogue_open := false
var clear_panel: PanelContainer
var clear_text: Label
var touch_controls: TouchControls # Only on touch devices (B-1004).

# Time-of-day stages, indexed by shards collected (0..3).
var stages: Array = [
	{"sun_rot": Vector3(-38, -30, 0), "sun_color": Color(1.0, 0.78, 0.55), "sun_energy": 1.15, "bg": Color(0.62, 0.55, 0.45), "amb": Color(0.55, 0.52, 0.48), "amb_e": 0.55},
	{"sun_rot": Vector3(-24, -42, 0), "sun_color": Color(1.0, 0.6, 0.38), "sun_energy": 0.95, "bg": Color(0.45, 0.36, 0.38), "amb": Color(0.45, 0.4, 0.45), "amb_e": 0.5},
	{"sun_rot": Vector3(-14, -55, 0), "sun_color": Color(0.85, 0.5, 0.45), "sun_energy": 0.7, "bg": Color(0.28, 0.24, 0.38), "amb": Color(0.36, 34.0 / 100.0, 0.45), "amb_e": 0.48},
	{"sun_rot": Vector3(-10, -65, 0), "sun_color": Color(0.55, 0.65, 0.95), "sun_energy": 0.4, "bg": Color(0.1, 0.12, 0.24), "amb": Color(0.3, 0.34, 0.48), "amb_e": 0.45},
]
var stage_current := {}
var stage_target := {}

## Set when the phased start-up build has finished; _process, physics
## and input stay out of the half-built world until then.
var _built := false
var _loading_layer: CanvasLayer
var _loading_text: Label

func _ready() -> void:
	add_to_group("uzu_state")
	juice_enabled = not OS.get_cmdline_user_args().has("--uzu-no-juice")
	InputSetup.setup()
	# The build is spread over frames behind a progress note instead of
	# one synchronous block: measured on the dev VM, the old _ready did
	# ~1 s of work (village generation ~740 ms, the UI ~210 ms) before
	# the first frame could draw, which reads as a freeze — worst on the
	# single-threaded Web build (owner playtest, 2026-11-21). The steps
	# run the same calls in the same order, so the village, the state
	# hash and the playthrough are unchanged.
	_build_loading()
	await get_tree().process_frame # The loading note draws before the first step.
	await _build_world_phased()
	var report := UZULook.apply_hd2d(self, UZULook.ATMOSPHERE_GOLDEN_HOUR, false)
	print("UZU_SAMPLE look report: ", JSON.stringify(report))
	_find_sun_and_env()
	_web_perf_tuning()
	await get_tree().process_frame
	_build_ui()
	stage_current = stages[0].duplicate()
	stage_target = stages[0].duplicate()
	_apply_stage(stage_current, 1.0)
	sound = HikariSound.new()
	sound.on_play = func(name: String) -> void: sfx_events.append(name)
	add_child(sound)
	sound.set_stage(0)
	_built = true
	_loading_layer.queue_free()
	UZUTelemetry.checkpoint("start")
	_set_objective("村に落ちた灯りの欠片を集めよう（0/3）")

## A plain progress note shown while the village builds in steps. Built
## before anything heavy, updated between steps, freed once the HUD is
## up. (The title screen's own "読み込み中…" covers the scene load that
## happens before this.)
func _build_loading() -> void:
	_loading_layer = CanvasLayer.new()
	_loading_layer.name = "Loading"
	add_child(_loading_layer)
	_loading_text = Label.new()
	_loading_text.add_theme_font_override("font", FONT)
	_loading_text.add_theme_font_size_override("font_size", 26)
	_loading_text.add_theme_color_override("font_color", Color(0.98, 0.94, 0.85))
	_loading_text.add_theme_color_override("font_shadow_color", Color(0.05, 0.04, 0.03, 0.9))
	_loading_text.add_theme_constant_override("shadow_offset_x", 2)
	_loading_text.add_theme_constant_override("shadow_offset_y", 2)
	_loading_text.set_anchors_preset(Control.PRESET_CENTER)
	_loading_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_loading_text.offset_left = -280
	_loading_text.offset_top = -20
	_loading_text.offset_right = 280
	_loading_text.offset_bottom = 24
	_loading_text.text = "読み込み中…"
	_loading_layer.add_child(_loading_text)

## Declared state for the engine's state hash (B-307): what "the same game
## state" means for this game. The AI player / self-play tooling hashes this
## to judge a playthrough mechanically.
func uzu_state() -> Dictionary:
	var p: Array = []
	if player:
		p = [snappedf(player.global_position.x, 0.01), snappedf(player.global_position.z, 0.01)]
	return {"shards": shards, "cleared": cleared, "player": p}

func _process(delta: float) -> void:
	if not _built:
		return
	_update_camera(delta)
	_update_stage(delta)
	_update_interactable()
	if sound:
		var moving := not dialogue_open and Input.get_vector("move_left", "move_right", "move_up", "move_down").length() > 0.0
		sound.set_walking(moving, player.global_position)
	if lantern_glow > 0.0 and lantern_light:
		lantern_light.light_energy = lerpf(lantern_light.light_energy, 2.6, delta * 1.5)

# Gameplay state advances on the fixed physics step, not the render frame:
# the AI player / self-play tooling steps physics frames in lockstep, and a
# fixed step keeps movement (and the state hash) deterministic.
func _physics_process(delta: float) -> void:
	if not _built:
		return # Play time must not run while the world is still building.
	if not cleared:
		play_seconds += delta
	_update_player(delta)

# ---------------------------------------------------------------- world

func _mat(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	return m

func _box(name: String, pos: Vector3, size: Vector3, color: Color, obstacle_r := 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = name
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.set_surface_override_material(0, _mat(color))
	mi.position = pos
	add_child(mi)
	if obstacle_r > 0.0:
		obstacles.append({"pos": Vector2(pos.x, pos.z), "r": obstacle_r})
	return mi

func _sprite(texture_path: String, pos: Vector3) -> Sprite3D:
	var s := Sprite3D.new()
	s.texture = load(texture_path)
	s.pixel_size = 0.06
	s.position = pos
	add_child(s)
	return s

## Builds the generated village in steps over frames (the progress note
## names the step that runs next), then derives the game's obstacle
## circles from what was generated: building and bench footprints from
## the city's collision shapes, street trees from its multimesh, the
## fountain from the plaza place, and the pond from the water's edge on
## the combined nature fields. Finishes with the hand-placed set.
func _build_world_phased() -> void:
	# The baked village first: one scene load instead of the generator
	# steps. Only a missing or stale bake falls through to generating.
	var built: Dictionary = _try_adopt_baked_world()
	if built.is_empty():
		var state := {}
		_loading_text.text = "読み込み中… 地形を作っています"
		while not build_generated_world_step(self, state):
			_loading_text.text = "読み込み中… " + String(state.get("label", ""))
			await get_tree().process_frame
		built = state["result"]
	land_map = built["land"]
	pond_map = built["pond"]
	city_map = built["city"]
	_derive_city_obstacles(built["city_result"])
	_derive_pond_obstacle()
	_build_hand_placed()

func _build_hand_placed() -> void:
	# Shrine at the north edge: two pillars, a beam, and the lantern.
	_box("ShrinePillarL", Vector3(-1.3, 1.5, -9.6), Vector3(0.4, 3.0, 0.4), Color(0.45, 0.25, 0.2), 0.45)
	_box("ShrinePillarR", Vector3(1.3, 1.5, -9.6), Vector3(0.4, 3.0, 0.4), Color(0.45, 0.25, 0.2), 0.45)
	_box("ShrineBeam", Vector3(0, 3.1, -9.6), Vector3(3.6, 0.35, 0.5), Color(0.5, 0.28, 0.22))
	_box("LanternBase", Vector3(0, 0.3, -9.0), Vector3(0.7, 0.6, 0.7), Color(0.5, 0.5, 0.54), 0.8)
	_box("LanternBox", Vector3(0, 0.85, -9.0), Vector3(0.55, 0.5, 0.55), Color(0.85, 0.7, 0.4))
	lantern_light = OmniLight3D.new()
	lantern_light.position = Vector3(0, 1.0, -9.0)
	lantern_light.light_color = Color(1.0, 0.72, 0.38)
	lantern_light.light_energy = 0.0
	lantern_light.omni_range = 7.0
	add_child(lantern_light)
	interactables.append({"pos": lantern_pos, "kind": "lantern", "id": "lantern", "label": "E： ランタンに灯す", "node": null})

	# Crates on the pond shore; one shard sits by them.
	var crate_y := _ground_height(7.2, -0.8)
	_box("Crate1", Vector3(7.2, crate_y + 0.5, -0.8), Vector3(1.0, 1.0, 1.0), Color(0.62, 0.48, 0.33), 0.85)
	_box("Crate2", Vector3(7.3, crate_y + 1.45, -0.9), Vector3(0.85, 0.85, 0.85), Color(0.58, 0.44, 0.3), 0.0)

	# Player.
	var flat_normal: Texture2D = load("res://art/flat_normal.png")
	player = _sprite("res://art/hero.png", Vector3(0, _ground_height(0, 4.5) + 0.72, 4.5))
	player.name = "Player"
	UZULook.configure_lit_sprite(player, flat_normal, 1.5)
	UZULook.add_blob_shadow(player, 0.5)

	# NPCs.
	_npc("npc_red", Vector3(2.2, _ground_height(2.2, -7.6) + 0.72, -7.6), "村長", [
		"おお、旅の子か。村の灯りが消えて三日になる。",
		"灯りの欠片が三つ、村に落ちたんじゃ。光っておるから分かるはず。",
		"集めたら祠のランタンに戻しておくれ。祭りが開ける。"])
	_npc("npc_green", Vector3(6.8, _ground_height(6.8, 2.6) + 0.72, 2.6), "ミドリ", [
		"池のほとりで何か光ってたよ。水辺は足元に気をつけてね。"])
	_npc("npc_purple", Vector3(-4.6, _ground_height(-4.6, 0.8) + 0.72, 0.8), "スミレ", [
		"木の陰って暗いけど、よーく見ると光るものがあるんだ。",
		"北西の大きな木の裏、あやしいと思うなあ。"])

	# Light shards.
	_shard("shard_tree", Vector3(-4.9, _ground_height(-4.9, -8.6) + 0.55, -8.6))
	_shard("shard_pond", Vector3(7.6, _ground_height(7.6, 6.4) + 0.55, 6.4))
	_shard("shard_crate", Vector3(6.1, _ground_height(6.1, 0.6) + 0.55, 0.6))

	camera = Camera3D.new()
	camera.name = "Camera3D"
	camera.fov = 50.0
	add_child(camera)
	camera.global_position = player.global_position + Vector3(0, 7.2, 9.2)
	camera.look_at(player.global_position + Vector3(0, 0.9, 0), Vector3.UP)

## Builds the generated village (B-1508) under parent and returns the
## three map holders with the city's generate result. Shared by the game
## and compose_village.gd, so both build the very same village.
##
## The build runs as steps (build_generated_world_step): the game spreads
## them over frames so starting is a short progress note instead of one
## long freeze (owner playtest, 2026-11-21), while compose_village.gd
## runs the same steps back to back. Step boundaries sit between the
## three generator calls — the expensive parts, measured at roughly
## 300 / 240 / 160 ms on the dev VM — and every step runs the same calls
## in the same order, so the village (fixed seeds) is identical either
## way. state["label"] names the step that runs next, for the progress
## note; state["result"] holds the return value once a step reports done.
static func build_generated_world_step(parent: Node, state: Dictionary) -> bool:
	var step := int(state.get("step", 0))
	if step == 0:
		state["label"] = "池を掘っています"
		var rl := UZUWorldGen.generate_nature(parent, land_spec())
		var land := parent.get_node(NodePath(String(rl["node"]))) as Node3D
		# Level the village by the land itself: the highest terrain under the
		# city tiling becomes y = 0, the city's level, and the land falls away
		# from the streets on every side.
		var peak := -1.0e9
		var gx := CITY_CENTRE.x - CITY_EDGE
		while gx <= CITY_CENTRE.x + CITY_EDGE:
			var gz := CITY_CENTRE.y - CITY_EDGE
			while gz <= CITY_CENTRE.y + CITY_EDGE:
				peak = maxf(peak, UZUWorldGen.height_at(land, gx, gz))
				gz += 1.0
			gx += 1.0
		land.position.y = -peak - 0.05
		# The land's own woods and rocks stay scenery: clear them out of the
		# ground the game is played on (the player's clamp, with a margin).
		_trim_scatter(land, Rect2(-WORLD_X - 2.0, -WORLD_Z - 2.0, 2.0 * WORLD_X + 4.0, 2.0 * WORLD_Z + 4.0))
		state["land"] = land
	if step == 1:
		state["label"] = "村を建てています"
		var rp := UZUWorldGen.generate_nature(parent, pond_spec())
		var pond := parent.get_node(NodePath(String(rp["node"]))) as Node3D
		# The pond map reaches west under the city; cut its terrain at the
		# city's east border, where the land map continues underneath. (The
		# cut is visual only: height_at is analytic and unaffected.)
		_trim_terrain(pond, CITY_CENTRE.x + CITY_EDGE)
		state["pond"] = pond
	if step >= 2:
		var rc := UZUWorldGen.generate_city(parent, city_spec())
		var city := parent.get_node(NodePath(String(rc["node"]))) as Node3D

		# A foundation slab under the tiling, its top just below street
		# level: with ground=false the streets have no floor of their own, so
		# physics walkers (the walking check, any future body) stand on this.
		# It ends where the tiling ends; beyond it, the land is the ground.
		var foundation := MeshInstance3D.new()
		foundation.name = "CityFoundation"
		var fmesh := BoxMesh.new()
		fmesh.size = Vector3(2.0 * CITY_EDGE, 0.5, 2.0 * CITY_EDGE)
		foundation.mesh = fmesh
		var fmat := StandardMaterial3D.new()
		fmat.albedo_color = Color(0.4, 0.34, 0.24)
		foundation.set_surface_override_material(0, fmat)
		foundation.position = Vector3(CITY_CENTRE.x, -0.28, CITY_CENTRE.y)
		parent.add_child(foundation)
		foundation.owner = parent
		var fbody := StaticBody3D.new()
		fbody.name = "CityFoundationBody"
		fbody.position = foundation.position
		var fcs := CollisionShape3D.new()
		var fshape := BoxShape3D.new()
		fshape.size = fmesh.size
		fcs.shape = fshape
		fbody.add_child(fcs)
		parent.add_child(fbody)
		fbody.owner = parent
		fcs.owner = parent
		state["result"] = {"land": state["land"], "pond": state["pond"], "city": city, "city_result": rc}
		return true
	state["step"] = step + 1
	return false

## The synchronous build (compose_village.gd and the checks): the same
## steps run back to back, so the village is the very same.
static func build_generated_world(parent: Node) -> Dictionary:
	var state := {}
	while not build_generated_world_step(parent, state):
		pass
	return state["result"]

## Fingerprint of everything that decides the generated village: the
## three specs plus the build version of the steps themselves.
## bake_world.gd stamps it on the baked scene; the game adopts the
## scene only when the stamp matches, so a spec or build change can
## never silently serve a stale village.
static func world_fingerprint() -> String:
	var payload := {
		"build": WORLD_BUILD_VERSION,
		"land": land_spec(),
		"pond": pond_spec(),
		"city": city_spec(),
	}
	return JSON.stringify(payload).md5_text()

## Adopts the pre-baked village (bake_world.gd) when one is shipped and
## its fingerprint matches the current specs: the whole generated world
## — terrain, pond, city and its baked navigation mesh — then costs one
## scene load (~10 ms measured on the dev VM) instead of ~700 ms of
## generator calls. Any doubt (no file, stale stamp, broken scene)
## returns {} and the caller generates in steps as before. The returned
## dictionary has the same shape as the build steps' result; the city
## result is reduced to the places, which is all the game reads from it
## (the rest is derived from the city node tree itself).
func _try_adopt_baked_world() -> Dictionary:
	if not ResourceLoader.exists(BAKED_WORLD_PATH):
		return {}
	var packed := load(BAKED_WORLD_PATH) as PackedScene
	if packed == null:
		return {}
	var holder := packed.instantiate() as Node3D
	if holder == null:
		return {}
	if String(holder.get_meta("uzu_baked_fingerprint", "")) != world_fingerprint():
		holder.free()
		return {}
	var land := holder.get_node_or_null(NodePath(String(land_spec()["name"]))) as Node3D
	var pond := holder.get_node_or_null(NodePath(String(pond_spec()["name"]))) as Node3D
	var city := holder.get_node_or_null(NodePath(String(city_spec()["name"]))) as Node3D
	if land == null or pond == null or city == null:
		holder.free()
		return {}
	# Move the generated nodes under the game root, in build order.
	var ordered: Array = []
	for child in holder.get_children():
		ordered.append(child)
	for child in ordered:
		holder.remove_child(child)
		add_child(child)
		child.owner = self
	holder.free()
	var places: Dictionary = {}
	if city.has_meta("uzu_places"):
		places = city.get_meta("uzu_places")
	return {"land": land, "pond": pond, "city": city, "city_result": {"places": places, "baked": true}}

func _derive_city_obstacles(rc: Dictionary) -> void:
	var body := city_map.get_node_or_null(NodePath("CityBody")) as StaticBody3D
	if body:
		for child in body.get_children():
			var cs := child as CollisionShape3D
			if cs == null or not (cs.name.begins_with("Building") or cs.name.begins_with("Bench")):
				continue
			var conv := cs.shape as ConvexPolygonShape3D
			if conv == null:
				continue
			var pts := conv.get_points()
			var c := Vector3.ZERO
			for q in pts:
				c += q
			c = c / pts.size() + cs.position
			var rad := 0.0
			for q in pts:
				rad = maxf(rad, Vector2(q.x + cs.position.x - c.x, q.z + cs.position.z - c.z).length())
			# The movement code adds the player's radius (0.35) back on.
			obstacles.append({"pos": Vector2(c.x + CITY_CENTRE.x, c.z + CITY_CENTRE.y), "r": rad - 0.35})
	var trees := city_map.get_node_or_null(NodePath("StreetTrees")) as MultiMeshInstance3D
	if trees and trees.multimesh:
		for i in trees.multimesh.instance_count:
			var o := trees.multimesh.get_instance_transform(i).origin
			obstacles.append({"pos": Vector2(o.x + CITY_CENTRE.x, o.z + CITY_CENTRE.y), "r": 0.35})
	var places: Dictionary = rc.get("places", {})
	if places.has("plaza"):
		var pp: Array = places["plaza"]["position"]
		# The plaza place sits beside the fountain; the fountain's centre
		# is 4.5 m north of it.
		obstacles.append({"pos": Vector2(pp[0], pp[2] - 4.5), "r": 2.85})

func _derive_pond_obstacle() -> void:
	var pts: Array[Vector2] = []
	var gx := POND_CENTRE.x - 4.2
	while gx <= POND_CENTRE.x + 4.2:
		var gz := POND_CENTRE.y - 4.2
		while gz <= POND_CENTRE.y + 4.2:
			if _nature_height(gx, gz) < POND_WATER_Y:
				pts.append(Vector2(gx, gz))
			gz += 0.6
		gx += 0.6
	if pts.size() < 12:
		obstacles.append({"pos": POND_CENTRE, "r": 2.3})
		return
	var c := Vector2.ZERO
	for q in pts:
		c += q
	c /= pts.size()
	var rad := 0.0
	for q in pts:
		rad = maxf(rad, c.distance_to(q))
	obstacles.append({"pos": c, "r": rad + 0.45 - 0.35})

## The combined nature height at a point (the higher field wins); the
## pond field is trimmed visually at the city border, but east of it the
## analytic field is the visible surface, so this stays exact there.
func _nature_height(x: float, z: float) -> float:
	var g := -1.0e9
	if land_map:
		var a := UZUWorldGen.height_at(land_map, x, z)
		if not is_nan(a):
			g = maxf(g, a)
	if pond_map:
		var b := UZUWorldGen.height_at(pond_map, x, z)
		if not is_nan(b):
			g = maxf(g, b)
	return g

## The ground a character stands on: the city tiling is flat at y = 0;
## outside it, the nature fields.
func _ground_height(x: float, z: float) -> float:
	if absf(x - CITY_CENTRE.x) <= CITY_EDGE and absf(z - CITY_CENTRE.y) <= CITY_EDGE:
		return 0.0
	var g := _nature_height(x, z)
	return g if g > -1.0e8 else 0.0

## Removes a nature map's scattered instances (trees, rocks, grass) whose
## position falls inside rect (x/z, holder-local = game coordinates for
## the land map), by compacting the multimesh buffers.
static func _trim_scatter(holder: Node3D, rect: Rect2) -> void:
	for child in holder.get_children():
		var mmi := child as MultiMeshInstance3D
		if mmi == null or mmi.multimesh == null:
			continue
		var mm := mmi.multimesh
		var kept: Array[Transform3D] = []
		for i in mm.instance_count:
			var t := mm.get_instance_transform(i)
			if not rect.has_point(Vector2(t.origin.x, t.origin.z)):
				kept.append(t)
		if kept.size() == mm.instance_count:
			continue
		for i in kept.size():
			mm.set_instance_transform(i, kept[i])
		mm.instance_count = kept.size()

## Cuts a nature map's terrain mesh west of keep_game_x (faces whose
## centroid is below it are dropped).
static func _trim_terrain(holder: Node3D, keep_game_x: float) -> void:
	var terrain := holder.get_node(NodePath("Terrain")) as MeshInstance3D
	if terrain == null or not (terrain.mesh is ArrayMesh):
		return
	var mesh := terrain.mesh as ArrayMesh
	var arrays := mesh.surface_get_arrays(0)
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	var faces: Array = []
	if index.size() > 0:
		for i in range(0, index.size() - 2, 3):
			faces.append([index[i], index[i + 1], index[i + 2]])
	else:
		for i in range(0, verts.size() - 2, 3):
			faces.append([i, i + 1, i + 2])
	var out_v := PackedVector3Array()
	var out_n := PackedVector3Array()
	var out_c := PackedColorArray()
	var ox := holder.position.x
	for f in faces:
		var cx := (verts[f[0]].x + verts[f[1]].x + verts[f[2]].x) / 3.0 + ox
		if cx < keep_game_x:
			continue
		for k in 3:
			out_v.append(verts[f[k]])
			if normals.size() == verts.size():
				out_n.append(normals[f[k]])
			if colors.size() == verts.size():
				out_c.append(colors[f[k]])
	var new_arrays: Array = []
	new_arrays.resize(Mesh.ARRAY_MAX)
	new_arrays[Mesh.ARRAY_VERTEX] = out_v
	if out_n.size() > 0:
		new_arrays[Mesh.ARRAY_NORMAL] = out_n
	if out_c.size() > 0:
		new_arrays[Mesh.ARRAY_COLOR] = out_c
	var new_mesh := ArrayMesh.new()
	new_mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, new_arrays)
	if mesh.get_surface_count() > 0 and mesh.surface_get_material(0) != null:
		new_mesh.surface_set_material(0, mesh.surface_get_material(0))
	terrain.mesh = new_mesh

func _npc(texture_name: String, pos: Vector3, npc_name: String, lines: Array) -> void:
	var s := _sprite("res://art/" + texture_name + ".png", pos)
	s.name = "NPC_" + npc_name
	obstacles.append({"pos": Vector2(pos.x, pos.z), "r": 0.5})
	interactables.append({"pos": pos, "kind": "npc", "id": npc_name, "label": "E： 話す", "node": s, "lines": lines, "npc_name": npc_name})

func _shard(id: String, pos: Vector3) -> void:
	var s := _sprite("res://art/shard.png", pos)
	s.name = id
	s.pixel_size = 0.05
	var glow := OmniLight3D.new()
	glow.light_color = Color(0.55, 0.9, 1.0)
	glow.light_energy = 0.8
	glow.omni_range = 2.4
	glow.position = pos
	add_child(glow)
	var sparkles := UZULook.create_particles(UZULook.PARTICLES_EMBERS, Vector3(0.6, 0.8, 0.6))
	sparkles.position = pos
	add_child(sparkles)
	interactables.append({"pos": pos, "kind": "shard", "id": id, "label": "E： 欠片を拾う", "node": s, "glow": glow, "sparkles": sparkles})

## Web builds run on WebGL through the Compatibility renderer, where the
## full-window resolution and the village-wide shadow map dominate the cost.
## Trim both on web only; the desktop build keeps the full quality.
func _web_perf_tuning() -> void:
	# "editor" exclusion: the AI-player harness runs the editor binary,
	# where has_feature("web") can read true; tuning must apply only to a
	# real Web export. (A runtime directional_shadow_atlas_set_size() here
	# also broke lockstep verification, so the atlas is left alone.)
	if not OS.has_feature("web") or OS.has_feature("editor"):
		return
	get_viewport().scaling_3d_scale = 0.7
	if sun:
		sun.directional_shadow_max_distance = 70.0

# ---------------------------------------------------------------- runtime

func _find_sun_and_env() -> void:
	var stack: Array = [self]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is DirectionalLight3D and sun == null and n.shadow_enabled:
			sun = n
		for c in n.get_children():
			stack.append(c)
	env = get_world_3d().environment
	if env == null:
		var we := get_node_or_null("WorldEnvironment") as WorldEnvironment
		if we:
			env = we.environment

func _update_player(delta: float) -> void:
	if dialogue_open:
		return
	var input_vec := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if input_vec.length() > 0.0:
		var dir := Vector3(input_vec.x, 0, input_vec.y)
		player.global_position += dir * PLAYER_SPEED * delta
		player.global_position.y = _ground_height(player.global_position.x, player.global_position.z) + 0.72 + abs(sin(Time.get_ticks_msec() / 90.0)) * 0.05
	else:
		player.global_position.y = _ground_height(player.global_position.x, player.global_position.z) + 0.72
	var p := player.global_position
	p.x = clampf(p.x, -WORLD_X, WORLD_X)
	p.z = clampf(p.z, -WORLD_Z, WORLD_Z)
	for o in obstacles:
		var op: Vector2 = o["pos"]
		var d := Vector2(p.x, p.z) - op
		var min_d: float = o["r"] + 0.35
		if d.length() < min_d and d.length() > 0.001:
			d = d.normalized() * min_d
			p.x = op.x + d.x
			p.z = op.y + d.y
	player.global_position = p

func _update_camera(delta: float) -> void:
	var target := player.global_position + Vector3(0, 7.2, 9.2)
	camera.global_position = camera.global_position.lerp(target, minf(delta * 4.0, 1.0))
	camera.look_at(player.global_position + Vector3(0, 0.9, 0), Vector3.UP)

func _apply_stage(st: Dictionary, _w: float) -> void:
	if sun:
		sun.rotation_degrees = st["sun_rot"]
		sun.light_color = st["sun_color"]
		sun.light_energy = st["sun_energy"]
	if env:
		env.background_color = st["bg"]
		env.ambient_light_color = st["amb"]
		env.ambient_light_energy = st["amb_e"]

func _update_stage(delta: float) -> void:
	var w := minf(delta * 1.2, 1.0)
	for key in ["sun_energy", "amb_e"]:
		stage_current[key] = lerpf(float(stage_current[key]), float(stage_target[key]), w)
	for key in ["sun_color", "bg", "amb"]:
		stage_current[key] = (stage_current[key] as Color).lerp(stage_target[key], w)
	stage_current["sun_rot"] = (stage_current["sun_rot"] as Vector3).lerp(stage_target["sun_rot"], w)
	_apply_stage(stage_current, w)

func _update_interactable() -> void:
	nearest_interactable = {}
	var best := 1.7
	for it in interactables:
		if it["kind"] == "shard" and it["node"] == null:
			continue
		var d: float = player.global_position.distance_to(it["pos"])
		if d < best:
			best = d
			nearest_interactable = it
	var label := ""
	if not dialogue_open and not nearest_interactable.is_empty():
		label = nearest_interactable.get("label", "")
	prompt_label.text = label
	prompt_panel.visible = not label.is_empty()
	if prompt_panel.visible:
		_fit(prompt_panel)
		prompt_panel.position = Vector2(-prompt_panel.size.x / 2.0, -128)
	if touch_controls:
		# The touch button mirrors the prompt, without the keyboard key.
		touch_controls.set_interact_text(label.trim_prefix("E： "))

func _unhandled_input(event: InputEvent) -> void:
	if not _built:
		return
	if event.is_action_pressed("interact"):
		_do_interact()

## One interact press, from the keyboard, a tap on the title, or the touch
## button (B-1004): advance an open dialogue, else use what is in reach.
func _do_interact() -> void:
	if dialogue_open:
		_advance_dialogue()
		return
	if nearest_interactable.is_empty():
		return
	match nearest_interactable["kind"]:
		"npc":
			_open_dialogue(nearest_interactable["npc_name"], nearest_interactable["lines"])
		"shard":
			_collect_shard(nearest_interactable)
		"lantern":
			_touch_lantern()

## A world-motion panel open/close, or just the end-state visibility
## when juice is disabled (B-1112): the panel ends up shown or hidden
## exactly as the motion would leave it, only without the animation.
func _juice_motion(panel: Control, open: bool) -> void:
	if juice_enabled:
		UZUUIJuice.apply_world_motion(panel, WORLD, open)
	else:
		panel.visible = open

func _open_dialogue(speaker: String, lines: Array) -> void:
	dialogue_lines = lines.duplicate()
	dialogue_name.text = speaker
	dialogue_open = true
	_juice_motion(dialogue_panel, true)
	_advance_dialogue()

func _advance_dialogue() -> void:
	if dialogue_lines.is_empty():
		dialogue_open = false
		_juice_motion(dialogue_panel, false)
		return
	dialogue_text.text = dialogue_lines.pop_front()
	if sound:
		sound.play(&"talk_blip", player.global_position)

func _collect_shard(it: Dictionary) -> void:
	shards += 1
	UZUTelemetry.checkpoint("shard_%d" % shards)
	juice_events.append("pickup")
	if sound:
		sound.play(&"pickup_shard", player.global_position)
	if juice_enabled:
		UZUJuice.impact(player, "pickup")
	if it["node"]:
		(it["node"] as Node).queue_free()
		it["node"] = null
	if it.get("glow"):
		(it["glow"] as Node).queue_free()
	if it.get("sparkles"):
		(it["sparkles"] as Node).queue_free()
	stage_target = stages[mini(shards, 3)].duplicate()
	if sound:
		sound.set_stage(mini(shards, 3))
	hud_shards.text = "%d / 3" % shards
	var icon := hud_shard_icons[shards - 1]
	icon.modulate = Color.WHITE # Collected: the shard lights up.
	if juice_enabled:
		UZUUIJuice.play_motion(icon, "press")
		UZUUIJuice.hover_pulse(hud_panel, 0.6, 0.25)
	if shards >= 3:
		_set_objective("祠のランタンに欠片を戻そう")
	else:
		_set_objective("村に落ちた灯りの欠片を集めよう（%d/3）" % shards)

func _touch_lantern() -> void:
	if cleared:
		return
	if shards < 3:
		_open_dialogue("ランタン", ["まだ暗い。欠片が %d つ足りない。" % (3 - shards)])
		return
	cleared = true
	lantern_glow = 1.0
	UZUTelemetry.checkpoint("lantern_lit")
	juice_events.append("lantern")
	if sound:
		sound.play(&"lantern_ignite", lantern_pos + Vector3(0, 1.0, 0))
	if juice_enabled:
		UZUJuice.impact(player, "pickup", 1.5)
		UZUJuice.kick(0.7)
		UZUJuice.burst3d(self, lantern_pos + Vector3(0, 1.0, 0), Color(1.0, 0.8, 0.4), 1.4)
	UZUTelemetry.clear()
	var fireflies := UZULook.create_particles(UZULook.PARTICLES_FIREFLIES, Vector3(9, 2.5, 9))
	fireflies.position = Vector3(0, 1.2, -6.5)
	add_child(fireflies)
	_set_objective("村に灯りが戻った！")
	await get_tree().create_timer(1.4).timeout
	clear_text.text = "村に灯りが戻った！\nクリア時間 %d 分 %d 秒\n\n遊んでくれてありがとう。" % [int(play_seconds) / 60, int(play_seconds) % 60]
	_fit(clear_panel)
	# Centre on the PRESET_CENTER anchor point via offsets. position is a
	# parent-space coordinate, so position = -size / 2 parked the panel in
	# the top-left corner with half of it off-screen (owner playtest,
	# 2026-11-20; reproduced in captures before this fix).
	clear_panel.offset_left = -clear_panel.size.x / 2.0
	clear_panel.offset_top = -clear_panel.size.y / 2.0
	clear_panel.offset_right = clear_panel.size.x / 2.0
	clear_panel.offset_bottom = clear_panel.size.y / 2.0
	_juice_motion(clear_panel, true)

func _set_objective(text: String) -> void:
	hud_objective.text = text
	_fit(hud_panel)

# ---------------------------------------------------------------- UI
#
# The UI is built with the UZUUI kit (B-1302) in the wafu world theme
# (B-1307): parchment frames with a vermilion accent, the segmented gauge
# for the shards, and the talk window with its name tag and blinking next
# mark. UZUUIWorld (open_on_ready off — the dialogue and clear panels start
# hidden and are opened by hand) gives the frames their moving sheen, and
# UZUUIJuice (B-1304) runs the opens, closes and the gauge count-up.

func _label(text: String, size: int) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	return l

## A floating panel outside a container keeps the size it is given; fit it
## to its content.
func _fit(panel: PanelContainer) -> void:
	if panel:
		panel.size = panel.get_combined_minimum_size()

## Touch UI (B-1004) shows on touch devices; --uzu-touch-ui (a user arg) or
## the UZU_TOUCH_UI environment variable forces it, so the touch layout can
## be checked on a desktop and in captures.
func _touch_ui_enabled() -> bool:
	if OS.get_cmdline_user_args().has("--uzu-touch-ui"):
		return true
	if OS.get_environment("UZU_TOUCH_UI") == "1":
		return true
	return DisplayServer.is_touchscreen_available()

func _build_ui() -> void:
	var layer := CanvasLayer.new()
	layer.name = "UI"
	add_child(layer)
	ui_root = Control.new()
	ui_root.name = "UIRoot"
	ui_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui_root.mouse_filter = Control.MOUSE_FILTER_IGNORE # Clicks fall through to the game.
	ui_root.theme = UZUUI.create_world_theme(WORLD, {"font": FONT, "font_size": 19})
	layer.add_child(ui_root)

	# HUD: shard gauge and the objective, in one parchment frame.
	hud_panel = PanelContainer.new()
	hud_panel.name = "HUD"
	hud_panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	hud_panel.position = Vector2(16, 12)
	ui_root.add_child(hud_panel)
	var hud_box := VBoxContainer.new()
	hud_box.add_theme_constant_override("separation", 4)
	hud_panel.add_child(hud_box)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	hud_box.add_child(row)
	row.add_child(_label("灯りの欠片", 20))
	# Shard icons, not a segmented gauge (B-1315): the gauge's segments
	# rendered as tofu blocks in the subset font. Each icon is the shard
	# sprite itself, dimmed until collected.
	var icons := HBoxContainer.new()
	icons.name = "ShardIcons"
	icons.add_theme_constant_override("separation", 4)
	icons.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(icons)
	var shard_tex := load("res://art/shard.png") as Texture2D
	for i in 3:
		var icon := TextureRect.new()
		icon.texture = shard_tex
		icon.custom_minimum_size = Vector2(24, 24)
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.modulate = Color(0.3, 0.3, 0.3, 0.6) # Not collected yet: a dim silhouette.
		icons.add_child(icon)
		hud_shard_icons.append(icon)
	hud_shards = _label("0 / 3", 20)
	row.add_child(hud_shards)
	hud_objective = _label("", 17)
	hud_box.add_child(hud_objective)

	help_label = _label("矢印 / WASD： 移動　E： 話す・拾う・灯す", 15)
	help_label.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	help_label.position = Vector2(18, -32)
	help_label.size = Vector2(480, 22)
	help_label.add_theme_color_override("font_color", Color(0.98, 0.94, 0.85))
	help_label.add_theme_color_override("font_shadow_color", Color(0.05, 0.04, 0.03, 0.9))
	help_label.add_theme_constant_override("shadow_offset_x", 1)
	help_label.add_theme_constant_override("shadow_offset_y", 1)
	ui_root.add_child(help_label)

	# The prompt: a small frame chip over the village, centred at the bottom.
	prompt_panel = PanelContainer.new()
	prompt_panel.name = "Prompt"
	prompt_panel.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	prompt_panel.visible = false
	ui_root.add_child(prompt_panel)
	prompt_label = _label("", 20)
	prompt_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	prompt_panel.add_child(prompt_label)

	# Dialogue: the kit's talk window (name tag, framed window, next mark).
	dialogue_panel = UZUUI.make_talk_window("", "")
	dialogue_panel.name = "Dialogue"
	dialogue_panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	dialogue_panel.offset_left = 60
	dialogue_panel.offset_right = -60
	dialogue_panel.offset_top = -152
	dialogue_panel.offset_bottom = -24
	dialogue_panel.visible = false
	ui_root.add_child(dialogue_panel)
	dialogue_name = dialogue_panel.get_node("TagMargin/NameTag/Speaker") as Label
	dialogue_text = dialogue_panel.get_node("Window/Body/Line") as Label
	dialogue_text.add_theme_font_size_override("font_size", 21)

	clear_panel = PanelContainer.new()
	clear_panel.name = "Clear"
	clear_panel.set_anchors_preset(Control.PRESET_CENTER)
	clear_panel.visible = false
	ui_root.add_child(clear_panel)
	clear_text = _label("", 24)
	clear_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	clear_panel.add_child(clear_text)

	if _touch_ui_enabled():
		touch_controls = TouchControls.new()
		ui_root.add_child(touch_controls)
		touch_controls.interact_pressed.connect(_do_interact)
		help_label.text = "左スティック： 移動　ボタン： 話す・拾う・灯す"

	# The world's motion, without the ready-opening (the HUD opens itself
	# below; dialogue and clear open from the game events).
	var motion := UZUUIWorld.new()
	motion.name = "WorldMotion"
	motion.world = WORLD
	motion.open_on_ready = false
	ui_root.add_child(motion)
	_open_hud()

func _open_hud() -> void:
	await get_tree().process_frame
	if hud_panel:
		_juice_motion(hud_panel, true)
