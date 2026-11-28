## B-1704: sound for 'hikari no kakera', wired only through the Phase 17
## path — Lumina renders placed by `uzu.py sfx-lumina` (credits manifest in
## audio/sfx/uzu_sfx_credits.json), played through the B-1702 UZUGameAudio
## helper. Foley and ambience are Lumina renders; the dialogue blip is a
## B-1105 UZUSfx synth event behind the same event-name API — the split
## the Phase 17 items were built for.
class_name HikariSound
extends Node

var audio: UZUGameAudio
## Set by Main: receives the firing-log name of every sound that plays
## (event names for one-shots, "footstep_start" / "ambient_<stage>" for
## loop starts), mirroring Main.juice_events for sound.
var on_play: Callable

var _walk_handle := -1
var _ambient_handle := -1
var _ambient_event := &""

const AMBIENT_BY_STAGE: Array[StringName] = [&"ambient_day", &"ambient_day", &"ambient_dusk", &"ambient_night"]
const CENTER := Vector3(0, 1.2, 0)


func _ready() -> void:
	audio = UZUGameAudio.new()
	add_child(audio)
	audio.register_event(&"footstep_grass", PackedStringArray(["res://audio/sfx/footstep_grass.wav"]),
		{"pitch_jitter": 0.03, "base_volume_db": -2.0, "unit_size": 6.0, "max_distance": 25.0})
	audio.register_event(&"pickup_shard", PackedStringArray(["res://audio/sfx/pickup_shard.wav"]),
		{"pitch_jitter": 0.04, "base_volume_db": 0.0, "unit_size": 8.0, "max_distance": 30.0})
	audio.register_event(&"lantern_ignite", PackedStringArray(["res://audio/sfx/lantern_ignite.wav"]),
		{"pitch_jitter": 0.0, "base_volume_db": 0.0, "unit_size": 8.0, "max_distance": 30.0})
	audio.register_event(&"ui_click", PackedStringArray(["res://audio/sfx/ui_click.wav"]),
		{"pitch_jitter": 0.03, "base_volume_db": -3.0})
	for ev in [&"ambient_day", &"ambient_dusk", &"ambient_night"]:
		audio.register_event(ev, PackedStringArray(["res://audio/sfx/%s.wav" % String(ev)]),
			{"pitch_jitter": 0.0, "base_volume_db": -12.0, "unit_size": 40.0, "max_distance": 220.0})
	audio.register_synth_event(&"talk_blip", &"pickup", {"seed": 7, "pitch_jitter": 0.08, "base_volume_db": -9.0})


func _log(name: String) -> void:
	if on_play.is_valid():
		on_play.call(name)


func play(event: StringName, pos: Vector3) -> void:
	if audio.play_event(event, pos) != null:
		_log(String(event))


## The footsteps render is a short multi-step take; loop it while the
## player moves and follow the player, stop when they stop.
func set_walking(walking: bool, pos: Vector3) -> void:
	if walking and _walk_handle < 0:
		_walk_handle = audio.start_event_loop(&"footstep_grass", pos)
		if _walk_handle > 0:
			_log("footstep_start")
	elif walking and _walk_handle > 0:
		audio.set_loop_position(_walk_handle, pos)
	elif not walking and _walk_handle > 0:
		audio.stop_loop(_walk_handle)
		_walk_handle = -1


## Ambience follows the time-of-day stage (indexed by shards collected):
## day birds, dusk marsh birds, night crickets.
func set_stage(stage: int) -> void:
	_log("ambient_%d" % stage)
	var ev: StringName = AMBIENT_BY_STAGE[clampi(stage, 0, 3)]
	if ev == _ambient_event:
		return
	if _ambient_handle > 0:
		audio.stop_loop(_ambient_handle)
		_ambient_handle = -1
	_ambient_event = ev
	_ambient_handle = audio.start_event_loop(ev, CENTER)
