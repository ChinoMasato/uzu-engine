extends RefCounted
## Shared input actions, defined in code so the project.godot stays small.
## The engine's self-play tooling reads actions from the InputMap, so
## runtime-defined actions are discoverable the same way.

static func setup() -> void:
	_add("move_left", [KEY_LEFT, KEY_A])
	_add("move_right", [KEY_RIGHT, KEY_D])
	_add("move_up", [KEY_UP, KEY_W])
	_add("move_down", [KEY_DOWN, KEY_S])
	_add("interact", [KEY_E, KEY_SPACE, KEY_ENTER])

static func _add(action: StringName, keys: Array) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)
	for k in keys:
		var exists := false
		for e in InputMap.action_get_events(action):
			if e is InputEventKey and e.physical_keycode == k:
				exists = true
		if not exists:
			var ev := InputEventKey.new()
			ev.physical_keycode = k
			InputMap.action_add_event(action, ev)
