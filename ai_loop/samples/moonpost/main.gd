extends Node3D
## Moonpost (B-1005): a tiny playable game built on the B-1221 image-scene
## scaffold of one specification illustration. Walk the moonlit street and
## deliver one letter to each of the three mailboxes (red, blue, green).

const InputSetup := preload("res://input_setup.gd")

const SPEED := 3.4
const STREET_X := Vector2(-7.6, 7.6)  # walkable band on the cobbled street
const STREET_Z := Vector2(-11.7, -9.1)
const INTERACT_RADIUS := 1.8

# Mailbox spots on the street edge in front of the three houses of the
# illustration (red-roof house left, stone tower centre, green-roof house
# right). The card mapping is recorded in the spec registry as inferred.
const MAILBOXES := [
	{"id": "red", "pos": Vector3(-3.6, 0.0, -11.35), "color": Color(0.85, 0.2, 0.15)},
	{"id": "blue", "pos": Vector3(0.95, 0.0, -11.35), "color": Color(0.2, 0.35, 0.9)},
	{"id": "green", "pos": Vector3(5.25, 0.0, -11.35), "color": Color(0.2, 0.7, 0.3)},
]

var delivered := 0
var cleared := false
var play_seconds := 0.0
var _delivered_flags: Array[bool] = [false, false, false]
var _mailbox_nodes: Array[Node3D] = []

@onready var _player: CharacterBody3D = $Player
@onready var _count_label: Label = $HUD/CountLabel
@onready var _hint_label: Label = $HUD/HintLabel
@onready var _clear_panel: PanelContainer = $HUD/ClearPanel
@onready var _deliver_player: AudioStreamPlayer = $DeliverPlayer
@onready var _clear_player: AudioStreamPlayer = $ClearPlayer


func _ready() -> void:
	InputSetup.setup()
	for spec in MAILBOXES:
		_mailbox_nodes.append(_make_mailbox(spec["pos"], spec["color"]))
	_update_hud()
	UZUTelemetry.checkpoint("start")


func _make_mailbox(pos: Vector3, color: Color) -> Node3D:
	var root := Node3D.new()
	root.position = pos
	var post := MeshInstance3D.new()
	var post_mesh := BoxMesh.new()
	post_mesh.size = Vector3(0.12, 0.8, 0.12)
	post.mesh = post_mesh
	post.position = Vector3(0, 0.4, 0)
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.35, 0.22, 0.12)
	post.material_override = wood
	root.add_child(post)
	var box := MeshInstance3D.new()
	var box_mesh := BoxMesh.new()
	box_mesh.size = Vector3(0.55, 0.4, 0.4)
	box.mesh = box_mesh
	box.position = Vector3(0, 1.0, 0)
	var paint := StandardMaterial3D.new()
	paint.albedo_color = color
	box.material_override = paint
	box.name = "Box"
	root.add_child(box)
	add_child(root)
	return root


func _physics_process(delta: float) -> void:
	if not cleared:
		play_seconds += delta
	var input_dir := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	var vel := Vector3(input_dir.x, 0, input_dir.y) * SPEED
	_player.velocity = Vector3(vel.x, _player.velocity.y - 9.8 * delta, vel.z)
	_player.move_and_slide()
	var p := _player.global_position
	p.x = clampf(p.x, STREET_X.x, STREET_X.y)
	p.z = clampf(p.z, STREET_Z.x, STREET_Z.y)
	_player.global_position = p


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("interact"):
		_try_deliver()


func _try_deliver() -> void:
	for i in MAILBOXES.size():
		if _delivered_flags[i]:
			continue
		var spot: Vector3 = MAILBOXES[i]["pos"]
		if _player.global_position.distance_to(spot) <= INTERACT_RADIUS:
			_delivered_flags[i] = true
			delivered += 1
			var box := _mailbox_nodes[i].get_node("Box") as MeshInstance3D
			var mat := box.material_override as StandardMaterial3D
			mat.emission_enabled = true
			mat.emission = mat.albedo_color
			mat.emission_energy_multiplier = 0.7
			_deliver_player.play()
			UZUTelemetry.checkpoint("deliver_%d" % delivered)
			_update_hud()
			if delivered >= MAILBOXES.size():
				cleared = true
				_clear_panel.visible = true
				_clear_player.play()
				UZUTelemetry.checkpoint("cleared")
				UZUTelemetry.clear()
			return


func _update_hud() -> void:
	_count_label.text = "配達 %d/%d" % [delivered, MAILBOXES.size()]
	_hint_label.text = "" if cleared else "郵便受けの近くで E / Space： 配達"
