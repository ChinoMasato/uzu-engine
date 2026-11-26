extends SceneTree
## Map generation for agents (UZUWorldGen): a natural map or a city from a short spec, saved
## into a scene. Run through `ai_loop/uzu.py map <project> nature|city|options ...`.
##
##   godot --headless --path P --script map_tool.gd -- nature|city --scene res://main.tscn
##         [--spec /abs/spec.json] [--set key=value ...] [--overview /abs/top.png]
##         [--replace] [--camera] [--inline]
##   godot --headless --path P --script map_tool.gd -- options [nature|city]
##
## - The spec is a JSON object (see `options`); --set adds or overrides one key (the value is
##   read as JSON when it can be: --set trees=2 --set water=false --set position=[0,0,0]).
## - The scene is created (a Node3D "Main") when it does not exist yet.
## - A node with the map's name already in the scene is an error; --replace rebuilds it.
## - --camera adds (or moves) a camera "MapCamera" that sees the whole map.
## - The big generated data (meshes, prop lists, collision) is saved next to the scene in
##   res://<scene>_maps/<name>/ as binary resources, so the .tscn stays small; --inline
##   keeps everything inside the .tscn.
## Prints one line "UZU_RESULT {json}".


func _initialize() -> void:
	var result := _run(OS.get_cmdline_user_args())
	print("UZU_RESULT " + JSON.stringify(result))
	quit(0 if result.get("ok", false) else 1)


func _option(args: PackedStringArray, name: String, default: String = "") -> String:
	var i := args.find("--" + name)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default


func _error(message: String, extra: Dictionary = {}) -> Dictionary:
	var r := {"ok": false, "error": message}
	r.merge(extra)
	return r


func _run(args: PackedStringArray) -> Dictionary:
	var command := args[0] if args.size() > 0 else "options"
	if command == "options":
		var kinds := [args[1]] if args.size() > 1 and not args[1].begins_with("--") else ["nature", "city"]
		var out := {"ok": true, "command": "options"}
		for kind in kinds:
			if kind != "nature" and kind != "city":
				return _error("options takes nature or city, not \"%s\"" % kind)
			out[kind] = {"options": UZUWorldGen.get_options(kind), "presets": UZUWorldGen.get_presets(kind)}
		out["usage"] = "uzu.py map <project> nature|city --scene res://main.tscn [--spec spec.json] [--set key=value ...] [--overview top.png] [--replace] [--camera]"
		return out
	if command != "nature" and command != "city":
		return _error("unknown map command \"%s\"" % command, {"hint": "use nature, city or options"})

	# The spec: a file, then --set over it.
	var spec := {}
	var spec_path := _option(args, "spec")
	if not spec_path.is_empty():
		var text := FileAccess.get_file_as_string(spec_path)
		var parsed: Variant = JSON.parse_string(text)
		if typeof(parsed) != TYPE_DICTIONARY:
			return _error("the spec at %s is not a JSON object" % spec_path)
		spec = parsed
	# Keys starting with "_" are file metadata (a preset's "_about", say),
	# not generator options: drop them here so a preset file can be fed to
	# map as-is. UZUWorldGen.resolve itself stays strict about real keys.
	for key in spec.keys():
		if String(key).begins_with("_"):
			spec.erase(key)
	for i in args.size():
		if args[i] != "--set" or i + 1 >= args.size():
			continue
		var pair := args[i + 1]
		var eq := pair.find("=")
		if eq <= 0:
			return _error("--set needs key=value, got \"%s\"" % pair)
		var value_text := pair.substr(eq + 1)
		var value: Variant = JSON.parse_string(value_text)
		spec[pair.substr(0, eq)] = value_text if value == null and value_text != "null" else value
	var resolved := UZUWorldGen.resolve(command, spec)
	if not resolved.ok:
		resolved["command"] = command
		return resolved
	var options: Dictionary = resolved.options

	# The scene: load it, or start a new one.
	var scene_path := _option(args, "scene", "res://main.tscn")
	var root: Node
	var created := false
	if ResourceLoader.exists(scene_path):
		var packed := load(scene_path) as PackedScene
		if packed == null:
			return _error("could not load %s" % scene_path)
		root = packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	else:
		root = Node3D.new()
		root.name = "Main"
		created = true
	var name: String = options.name
	var old := root.get_node_or_null(NodePath(name))
	if old:
		if args.find("--replace") < 0:
			root.free()
			return _error("%s already has a node named \"%s\"" % [scene_path, name], {"hint": "pass --replace to rebuild it, or --set name=Another to add a second map"})
		root.remove_child(old)
		old.free()

	var started := Time.get_ticks_msec()
	var result: Dictionary = UZUWorldGen.generate_nature(root, spec) if command == "nature" else UZUWorldGen.generate_city(root, spec)
	if not result.ok:
		root.free()
		result["command"] = command
		return result
	result["generate_ms"] = Time.get_ticks_msec() - started
	var holder := root.get_node(NodePath(result.node)) as Node3D

	var overview: Image = result.overview
	result.erase("overview")
	var overview_path := _option(args, "overview")
	if not overview_path.is_empty():
		DirAccess.make_dir_recursive_absolute(overview_path.get_base_dir())
		if overview.save_png(overview_path) != OK:
			root.free()
			return _error("could not write the overview to %s" % overview_path)
		result["overview"] = overview_path
	else:
		result.erase("overview_about")

	if args.find("--camera") >= 0:
		result["camera"] = _add_camera(root, holder, float(result.size))

	if args.find("--inline") < 0:
		var folder := scene_path.get_basename() + "_maps/" + name
		var saved := _save_external(holder, folder)
		if saved.has("error"):
			root.free()
			return _error(saved.error)
		result["data_folder"] = folder
		result["data_files"] = saved.count

	var packed_scene := PackedScene.new()
	var err := packed_scene.pack(root)
	if err == OK:
		err = ResourceSaver.save(packed_scene, scene_path)
	root.free()
	if err != OK:
		return _error("could not save %s (error %d)" % [scene_path, err])
	result["command"] = command
	result["scene"] = scene_path
	result["scene_created"] = created
	result["next"] = "look apply --scene %s (light and sky), then look shot / uzu.py build; place things at result.places" % scene_path
	return result


# A camera that sees the whole map from the south, above.
func _add_camera(root: Node, holder: Node3D, size: float) -> Dictionary:
	var camera := root.get_node_or_null(^"MapCamera") as Camera3D
	if camera == null:
		camera = Camera3D.new()
		camera.name = "MapCamera"
		root.add_child(camera)
		camera.owner = root
	var center := holder.position
	camera.position = center + Vector3(0, size * 0.42, size * 0.62)
	camera.far = maxf(1000.0, size * 4.0)
	camera.current = true
	# look_at needs the node in a tree; set the basis directly.
	camera.basis = Basis.looking_at(center - camera.position, Vector3.UP)
	return {"node": "MapCamera", "position": [camera.position.x, camera.position.y, camera.position.z]}


# Saves the generated meshes, prop lists and shapes as binary files, so the scene refers to them.
func _save_external(holder: Node, folder: String) -> Dictionary:
	var dir := ProjectSettings.globalize_path(folder)
	DirAccess.make_dir_recursive_absolute(dir)
	var count := 0
	# Textures and meshes used by several nodes (B-1219: the buildings' texture sets, the
	# window frame shared by every block) go out once, so each node's file points at them.
	var shared := {}
	for node in holder.find_children("*", "", true, false):
		var mesh: Mesh = node.mesh if node is MeshInstance3D else (node.multimesh.mesh if node is MultiMeshInstance3D and node.multimesh else null)
		if mesh == null:
			continue
		if node is MultiMeshInstance3D:
			shared[mesh] = "mesh_" + String(node.name).get_slice("_", 0)
		for si in mesh.get_surface_count():
			var mat := mesh.surface_get_material(si) as BaseMaterial3D
			if mat == null:
				continue
			for slot in [BaseMaterial3D.TEXTURE_ALBEDO, BaseMaterial3D.TEXTURE_NORMAL, BaseMaterial3D.TEXTURE_ROUGHNESS]:
				var tex := mat.get_texture(slot)
				if tex != null and tex.resource_path.is_empty() and not shared.has(tex):
					shared[tex] = "tex_%d" % shared.size()
	var order: Array = shared.keys().filter(func(r): return not r is Mesh) + shared.keys().filter(func(r): return r is Mesh)
	for res in order:  # Textures first, so the meshes that use them point at their files.
		var path := "%s/%s.res" % [folder, shared[res]]
		var err := ResourceSaver.save(res, path, ResourceSaver.FLAG_COMPRESS)
		if err != OK:
			return {"error": "could not save %s (error %d)" % [path, err]}
		res.take_over_path(path)
		count += 1
	for node in holder.find_children("*", "", true, false):
		var res: Resource = null
		if node is MeshInstance3D:
			res = node.mesh
		elif node is MultiMeshInstance3D:
			res = node.multimesh
		elif node is CollisionShape3D:
			# Small shapes (one box per building) stay in the scene; the terrain's height map goes out.
			res = node.shape if node.shape is HeightMapShape3D else null
		elif node is NavigationRegion3D:
			res = node.navigation_mesh
		if res == null or (node is MeshInstance3D and node.name == "Water"):
			continue
		var path := "%s/%s.res" % [folder, String(holder.get_path_to(node)).replace("/", "_")]
		var err := ResourceSaver.save(res, path, ResourceSaver.FLAG_COMPRESS)
		if err != OK:
			return {"error": "could not save %s (error %d)" % [path, err]}
		res.take_over_path(path)
		count += 1
	return {"count": count}
