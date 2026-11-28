# Based on game_audio_helper.gd from Lumina SFX (MIT License)
# Source: https://github.com/LuminaBench/lumina-sfx
#
# Copyright (c) Lumina SFX contributors (MIT License)
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# U.ZU Engine adaptations:
# - Renamed class to UZUGameAudio to avoid collisions with upstream GameAudioHelper.
# - Relaxed pool variant requirement to accept 1 or more takes without warning.
# - Added unified event API (register_event, register_synth_event, play_event,
#   start_event_loop, describe_events) integrating B-1105 UZUSfx synthesis.

class_name UZUGameAudio
extends Node


class _SoundPool extends RefCounted:
	var streams: Array[AudioStream] = []
	var next_index: int = 0
	var pitch_jitter: float = 0.05
	var base_volume_db: float = 0.0
	var unit_size: float = 10.0
	var max_distance: float = 50.0
	var attenuation_model: AudioStreamPlayer3D.AttenuationModel = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	var bus: StringName = &"Master"


class _LoopInstance extends RefCounted:
	var player: AudioStreamPlayer3D
	var pitch_variation: float = 1.0
	var base_volume_db: float = 0.0
	var volume_offset_db: float = 0.0


class _EventEntry extends RefCounted:
	var kind: String = "file"
	var preset: StringName = &""
	var seed: int = 1
	var options: Dictionary = {}


var _pools: Dictionary = {}
var _events: Dictionary = {}
var _active_loops: Dictionary = {}
var _next_loop_handle: int = 1
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()


func _init() -> void:
	_rng.randomize()


func register_pool(
	id: StringName,
	variant_paths: PackedStringArray,
	pitch_jitter: float = 0.05,
	unit_size: float = 10.0,
	max_distance: float = 50.0,
	attenuation_model: AudioStreamPlayer3D.AttenuationModel = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE,
	base_volume_db: float = 0.0,
	bus: StringName = &"Master"
) -> bool:
	var loaded: Array[AudioStream] = []
	for raw_path in variant_paths:
		var res_path: String = _to_res_path(raw_path)
		var stream: AudioStream = ResourceLoader.load(res_path) as AudioStream
		if stream == null:
			push_error("UZUGameAudio: failed to load AudioStream at '%s'." % res_path)
			continue
		loaded.append(stream)

	return register_streams(id, loaded, pitch_jitter, unit_size, max_distance, attenuation_model, base_volume_db, bus)


func register_streams(
	id: StringName,
	streams: Array[AudioStream],
	pitch_jitter: float = 0.05,
	unit_size: float = 10.0,
	max_distance: float = 50.0,
	attenuation_model: AudioStreamPlayer3D.AttenuationModel = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE,
	base_volume_db: float = 0.0,
	bus: StringName = &"Master"
) -> bool:
	if streams.is_empty():
		push_error("UZUGameAudio: cannot register empty pool '%s'." % id)
		return false

	var pool: _SoundPool = _SoundPool.new()
	pool.streams.assign(streams)
	pool.pitch_jitter = maxf(0.0, pitch_jitter)
	pool.unit_size = maxf(0.01, unit_size)
	pool.max_distance = maxf(0.0, max_distance)
	pool.attenuation_model = attenuation_model
	pool.base_volume_db = base_volume_db
	pool.bus = bus
	_pools[id] = pool
	return true


func register_event(event: StringName, variant_paths: PackedStringArray, options: Dictionary = {}) -> bool:
	var pitch_jitter: float = float(options.get("pitch_jitter", 0.05))
	var unit_size: float = float(options.get("unit_size", 10.0))
	var max_distance: float = float(options.get("max_distance", 50.0))
	var attenuation_model: AudioStreamPlayer3D.AttenuationModel = int(
		options.get("attenuation_model", AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE)
	) as AudioStreamPlayer3D.AttenuationModel
	var base_volume_db: float = float(options.get("base_volume_db", 0.0))
	var bus: StringName = StringName(options.get("bus", &"Master"))

	var ok: bool = register_pool(
		event,
		variant_paths,
		pitch_jitter,
		unit_size,
		max_distance,
		attenuation_model,
		base_volume_db,
		bus
	)
	if not ok:
		return false

	var entry := _EventEntry.new()
	entry.kind = "file"
	entry.options = options.duplicate(true)
	_events[event] = entry
	return true


func register_synth_event(event: StringName, preset: StringName, options: Dictionary = {}) -> bool:
	if String(event).is_empty() or String(preset).is_empty():
		push_error("UZUGameAudio: event and preset must be non-empty for synth event '%s'." % event)
		return false

	_pools.erase(event)
	var entry := _EventEntry.new()
	entry.kind = "synth"
	entry.preset = preset
	entry.seed = int(options.get("seed", 1))
	entry.options = options.duplicate(true)
	_events[event] = entry
	return true


func play_event(
	event: StringName,
	world_position: Vector3,
	volume_offset_db: float = 0.0,
	pitch_scale: float = 1.0
) -> AudioStreamPlayer3D:
	var entry: _EventEntry = _events.get(event) as _EventEntry
	if entry == null:
		push_error("UZUGameAudio: unknown event '%s'." % event)
		return null

	if entry.kind == "synth" and not _pools.has(event):
		var stream: AudioStream = UZUSfx.generate_preset(String(entry.preset), entry.seed)
		if stream == null:
			push_error("UZUGameAudio: failed to generate synth preset '%s' for event '%s'." % [entry.preset, event])
			return null
		var opts: Dictionary = entry.options
		var pitch_jitter: float = float(opts.get("pitch_jitter", 0.05))
		var unit_size: float = float(opts.get("unit_size", 10.0))
		var max_distance: float = float(opts.get("max_distance", 50.0))
		var attenuation_model: AudioStreamPlayer3D.AttenuationModel = int(
			opts.get("attenuation_model", AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE)
		) as AudioStreamPlayer3D.AttenuationModel
		var base_volume_db: float = float(opts.get("base_volume_db", 0.0))
		var bus: StringName = StringName(opts.get("bus", &"Master"))
		var streams: Array[AudioStream] = [stream]
		if not register_streams(event, streams, pitch_jitter, unit_size, max_distance, attenuation_model, base_volume_db, bus):
			return null

	return play_one_shot(event, world_position, volume_offset_db, pitch_scale)


func start_event_loop(
	event: StringName,
	world_position: Vector3,
	volume_offset_db: float = 0.0,
	initial_pitch: float = 1.0
) -> int:
	var entry: _EventEntry = _events.get(event) as _EventEntry
	if entry == null:
		push_error("UZUGameAudio: unknown event '%s'." % event)
		return -1
	if entry.kind != "file":
		push_error("UZUGameAudio: synth event '%s' cannot be started as a loop." % event)
		return -1
	return start_loop(event, world_position, volume_offset_db, initial_pitch)


func describe_events() -> Dictionary:
	var result: Dictionary = {}
	for event_key in _events.keys():
		var entry: _EventEntry = _events[event_key] as _EventEntry
		if entry == null:
			continue
		var pool: _SoundPool = _pools.get(event_key) as _SoundPool
		var variants: int = 0
		if pool != null:
			variants = pool.streams.size()
		elif entry.kind == "synth":
			variants = 1
		result[String(event_key)] = {
			"kind": entry.kind,
			"variants": variants,
		}
	return result


func play_one_shot(
	id: StringName,
	world_position: Vector3,
	volume_offset_db: float = 0.0,
	pitch_scale: float = 1.0
) -> AudioStreamPlayer3D:
	var pool: _SoundPool = _pools.get(id) as _SoundPool
	if pool == null or pool.streams.is_empty():
		push_error("UZUGameAudio: unknown or empty pool '%s'." % id)
		return null

	var stream: AudioStream = _next_variant(pool)
	var pitch_variation: float = _roll_pitch_variation(pool.pitch_jitter)
	var player: AudioStreamPlayer3D = _create_player(pool, stream)
	player.volume_db = pool.base_volume_db + volume_offset_db
	player.pitch_scale = maxf(0.01, pitch_scale * pitch_variation)
	player.finished.connect(player.queue_free)

	add_child(player)
	_set_player_position(player, world_position)
	player.play()
	return player


func start_loop(
	id: StringName,
	world_position: Vector3,
	volume_offset_db: float = 0.0,
	initial_pitch: float = 1.0
) -> int:
	var pool: _SoundPool = _pools.get(id) as _SoundPool
	if pool == null or pool.streams.is_empty():
		push_error("UZUGameAudio: unknown or empty pool '%s'." % id)
		return -1

	var stream: AudioStream = _prepare_loop_stream(_next_variant(pool))
	var pitch_variation: float = _roll_pitch_variation(pool.pitch_jitter)
	var player: AudioStreamPlayer3D = _create_player(pool, stream)
	player.volume_db = pool.base_volume_db + volume_offset_db
	player.pitch_scale = maxf(0.01, initial_pitch * pitch_variation)

	add_child(player)
	_set_player_position(player, world_position)
	player.play()

	var instance: _LoopInstance = _LoopInstance.new()
	instance.player = player
	instance.pitch_variation = pitch_variation
	instance.base_volume_db = pool.base_volume_db
	instance.volume_offset_db = volume_offset_db

	var handle: int = _next_loop_handle
	_next_loop_handle += 1
	_active_loops[handle] = instance
	return handle


func update_rpm(
	handle: int,
	rpm_normalized: float,
	world_position: Vector3 = Vector3.INF,
	min_pitch: float = 0.65,
	max_pitch: float = 2.0,
	min_db_offset: float = -6.0,
	max_db_offset: float = 2.0
) -> void:
	var instance: _LoopInstance = _get_valid_loop(handle)
	if instance == null:
		return

	var t: float = clampf(rpm_normalized, 0.0, 1.0)
	var rpm_pitch: float = lerpf(min_pitch, max_pitch, t)
	instance.player.pitch_scale = maxf(0.01, rpm_pitch * instance.pitch_variation)
	instance.player.volume_db = instance.base_volume_db + instance.volume_offset_db + lerpf(min_db_offset, max_db_offset, t)
	if world_position.is_finite():
		_set_player_position(instance.player, world_position)


func update_weather(
	handle: int,
	intensity: float,
	world_position: Vector3 = Vector3.INF,
	min_pitch: float = 0.85,
	max_pitch: float = 1.2,
	min_db_offset: float = -30.0,
	max_db_offset: float = 0.0
) -> void:
	var instance: _LoopInstance = _get_valid_loop(handle)
	if instance == null:
		return

	var t: float = clampf(intensity, 0.0, 1.0)
	var weather_pitch: float = lerpf(min_pitch, max_pitch, t)
	instance.player.pitch_scale = maxf(0.01, weather_pitch * instance.pitch_variation)
	instance.player.volume_db = instance.base_volume_db + instance.volume_offset_db + lerpf(min_db_offset, max_db_offset, t)
	if world_position.is_finite():
		_set_player_position(instance.player, world_position)


func set_loop_position(handle: int, world_position: Vector3) -> void:
	var instance: _LoopInstance = _get_valid_loop(handle)
	if instance == null:
		return
	_set_player_position(instance.player, world_position)


func stop_loop(handle: int) -> void:
	var instance: _LoopInstance = _active_loops.get(handle) as _LoopInstance
	if instance == null:
		return
	_active_loops.erase(handle)
	if is_instance_valid(instance.player):
		instance.player.stop()
		instance.player.queue_free()


func stop_all_loops() -> void:
	var handles: Array = _active_loops.keys()
	for handle in handles:
		stop_loop(int(handle))


func is_loop_playing(handle: int) -> bool:
	var instance: _LoopInstance = _get_valid_loop(handle)
	return instance != null and instance.player.playing


func _get_valid_loop(handle: int) -> _LoopInstance:
	var instance: _LoopInstance = _active_loops.get(handle) as _LoopInstance
	if instance == null:
		return null
	if not is_instance_valid(instance.player):
		_active_loops.erase(handle)
		return null
	return instance


func _next_variant(pool: _SoundPool) -> AudioStream:
	var stream: AudioStream = pool.streams[pool.next_index]
	pool.next_index = (pool.next_index + 1) % pool.streams.size()
	return stream


func _roll_pitch_variation(jitter: float) -> float:
	if jitter <= 0.0:
		return 1.0
	return maxf(0.01, 1.0 + _rng.randf_range(-jitter, jitter))


func _create_player(pool: _SoundPool, stream: AudioStream) -> AudioStreamPlayer3D:
	var player: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	player.top_level = true
	player.stream = stream
	player.unit_size = pool.unit_size
	player.max_distance = pool.max_distance
	player.attenuation_model = pool.attenuation_model
	player.bus = pool.bus
	return player


func _set_player_position(player: AudioStreamPlayer3D, world_position: Vector3) -> void:
	if player.is_inside_tree():
		player.global_position = world_position
	else:
		player.position = world_position


static func _to_res_path(path: String) -> String:
	if path.begins_with("res://") or path.begins_with("user://"):
		return path
	return "res://" + path.trim_prefix("/")


static func _prepare_loop_stream(stream: AudioStream) -> AudioStream:
	if stream is AudioStreamWAV:
		var wav: AudioStreamWAV = stream as AudioStreamWAV
		if wav.loop_mode == AudioStreamWAV.LOOP_DISABLED:
			var looping_wav: AudioStreamWAV = wav.duplicate() as AudioStreamWAV
			looping_wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
			if looping_wav.loop_end <= looping_wav.loop_begin:
				var sample_frames: int = roundi(looping_wav.get_length() * float(looping_wav.mix_rate))
				if sample_frames > 0:
					looping_wav.loop_begin = 0
					looping_wav.loop_end = sample_frames
			return looping_wav
	return stream


## Godot and Lumina use metres and -Z forward. Apply this to the emitter Node3D.
static func scene_pose(position_metres: Vector3, yaw_degrees: float, pitch_degrees: float) -> Transform3D:
	var basis := Basis(Vector3.UP, -deg_to_rad(yaw_degrees)) * Basis(Vector3.RIGHT, deg_to_rad(pitch_degrees))
	return Transform3D(basis, position_metres)
