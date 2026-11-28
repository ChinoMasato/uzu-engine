extends Node
## Play telemetry recorder (BACKLOG B-301). Add as an autoload named UZUTelemetry.
## Writes the event log described in ai_loop/telemetry/FORMAT.md (JSON Lines).
## No personal identifiers: the session ID is random and thrown away after the play.
##
## The game calls checkpoint(id), death(cause) and clear(). A node in the group
## "uzu_player" gives the position cell and stall detection.
## Output: "--uzu-telemetry <file>" after "--" on the command line, else
## user://telemetry/<session>.jsonl.

signal event_recorded(event: Dictionary)  # For live readers such as the lockstep control (B-306).

const VERSION := 1
const CELL_SIZE := 4.0
const STALL_SECONDS := 10.0

var session := ""
var _file: FileAccess
var _start_frame := 0
var _start_usec := 0
var _stall_cell = null
var _stall_since := 0.0
var _stall_reported := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var rng := RandomNumberGenerator.new()
	rng.randomize()  # Session IDs must differ between plays even when the game seeds its own RNG.
	session = "s-%08x%08x" % [rng.randi(), rng.randi()]
	var path := "user://telemetry/%s.jsonl" % session
	var args := OS.get_cmdline_user_args()
	var i := args.find("--uzu-telemetry")
	if i >= 0 and i + 1 < args.size():
		path = args[i + 1]
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	_file = FileAccess.open(path, FileAccess.WRITE)
	_start_frame = Engine.get_physics_frames()
	_start_usec = Time.get_ticks_usec()
	_emit("start", {"game": ProjectSettings.get_setting("application/config/name", ""), "version": ProjectSettings.get_setting("application/config/version", "")})


func checkpoint(id: String) -> void:
	_emit("checkpoint", {"id": id})


func death(cause: String = "") -> void:
	_emit("death", {"cause": cause} if not cause.is_empty() else {})


func clear() -> void:
	_emit("clear", {})


func _frame() -> int:
	return Engine.get_physics_frames() - _start_frame


func _time() -> float:
	return _frame() / float(Engine.physics_ticks_per_second)


func _player() -> Node:
	return get_tree().get_first_node_in_group("uzu_player")


func _cell() -> Variant:
	var p := _player()
	var pos: Vector3
	if p is Node3D:
		pos = (p as Node3D).global_position
	elif p is Node2D:
		var v := (p as Node2D).global_position
		pos = Vector3(v.x, v.y, 0)
	else:
		return null
	return [floori(pos.x / CELL_SIZE), floori(pos.y / CELL_SIZE), floori(pos.z / CELL_SIZE)]


func _emit(type: String, extra: Dictionary) -> void:
	if _file == null:
		return
	var event := {"v": VERSION, "session": session, "type": type, "frame": _frame(), "time": snappedf(_time(), 0.001)}
	var scene := get_tree().current_scene
	event["scene"] = scene.scene_file_path if scene else ""
	var cell = _cell()
	if cell != null:
		event["cell"] = cell
	event.merge(extra)
	_file.store_line(JSON.stringify(event))
	_file.flush()
	event_recorded.emit(event)


func _physics_process(_delta: float) -> void:
	var cell = _cell()
	if cell == null:
		return
	if cell != _stall_cell:
		_stall_cell = cell
		_stall_since = _time()
		_stall_reported = false
	elif not _stall_reported and _time() - _stall_since >= STALL_SECONDS:
		_stall_reported = true
		_emit("stall", {"seconds": snappedf(_time() - _stall_since, 0.01)})


func _exit_tree() -> void:
	var seconds := (Time.get_ticks_usec() - _start_usec) / 1000000.0
	var frames := Engine.get_process_frames()
	_emit("quit", {"frames": frames, "fps": snappedf(frames / seconds, 0.1) if seconds > 0 else 0.0})
	_file = null
