extends Node3D


func _make_sine_wav(freq_hz: float, duration_sec: float = 0.1, mix_rate: int = 22050) -> AudioStreamWAV:
	var sample_count: int = int(round(duration_sec * float(mix_rate)))
	var data := PackedByteArray()
	data.resize(sample_count * 2)
	for i in sample_count:
		var t: float = float(i) / float(mix_rate)
		var sample_f: float = sin(TAU * freq_hz * t) * 0.25
		var sample_i: int = clampi(int(round(sample_f * 32767.0)), -32768, 32767)
		data.encode_s16(i * 2, sample_i)

	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = mix_rate
	wav.stereo = false
	wav.data = data
	return wav


func _load_uzu_game_audio() -> GDScript:
	if ResourceLoader.exists("res://uzu_game_audio.gd"):
		return load("res://uzu_game_audio.gd") as GDScript
	var fallback_path: String = ProjectSettings.globalize_path("res://").path_join("../../uzu_game_audio.gd").simplify_path()
	if FileAccess.file_exists(fallback_path):
		return ResourceLoader.load(fallback_path) as GDScript
	return null


func _ready() -> void:
	var audio_script: GDScript = _load_uzu_game_audio()
	var audio: Node = audio_script.new() as Node
	add_child(audio)

	# 1. プール再生・位置・減衰設定・ピッチゆらぎの検証
	var s0: AudioStreamWAV = _make_sine_wav(440.0)
	var s1: AudioStreamWAV = _make_sine_wav(880.0)
	var streams: Array[AudioStream] = [s0, s1]
	var pool_reg_ok: bool = audio.register_streams(&"pool_test", streams, 0.05, 12.5, 75.0)

	var target_pos := Vector3(4.5, 1.5, -6.0)
	var p0: AudioStreamPlayer3D = audio.play_one_shot(&"pool_test", target_pos, 0.0, 1.2)
	var p1: AudioStreamPlayer3D = audio.play_one_shot(&"pool_test", target_pos, 0.0, 1.2)
	var p2: AudioStreamPlayer3D = audio.play_one_shot(&"pool_test", target_pos, 0.0, 1.2)

	var pool_round_robin: bool = (
		pool_reg_ok
		and p0 != null and p1 != null and p2 != null
		and p0.stream == s0
		and p1.stream == s1
		and p2.stream == s0
	)
	var pool_position: bool = (
		p0 != null
		and p0.global_position.is_equal_approx(target_pos)
	)
	var pool_attenuation: bool = (
		p0 != null
		and is_equal_approx(p0.unit_size, 12.5)
		and is_equal_approx(p0.max_distance, 75.0)
	)
	var measured_pitches: Array[float] = []
	var pool_pitch_jitter: bool = true
	for p in [p0, p1, p2]:
		if p == null:
			pool_pitch_jitter = false
		else:
			measured_pitches.append(p.pitch_scale)
			if p.pitch_scale < 1.2 * 0.95 - 0.0001 or p.pitch_scale > 1.2 * 1.05 + 0.0001:
				pool_pitch_jitter = false

	var exact_reg_ok: bool = audio.register_streams(&"pool_exact", streams, 0.0, 10.0, 50.0)
	var p_exact: AudioStreamPlayer3D = audio.play_one_shot(&"pool_exact", target_pos, 0.0, 1.25)
	var measured_exact_pitch: float = p_exact.pitch_scale if p_exact != null else 0.0
	var pool_pitch_exact: bool = exact_reg_ok and p_exact != null and is_equal_approx(measured_exact_pitch, 1.25)

	# 2. ループ・天候／RPM 連動・停止の検証
	var loop_handle: int = audio.start_loop(&"pool_test", Vector3(0.0, 2.0, -3.0), 0.0, 1.0)
	var loop_playing_start: bool = loop_handle > 0 and audio.is_loop_playing(loop_handle)
	var loop_player: AudioStreamPlayer3D = audio.get_child(audio.get_child_count() - 1) as AudioStreamPlayer3D

	audio.update_weather(loop_handle, 0.0)
	var weather_vol_0: float = loop_player.volume_db if loop_player != null else 0.0
	audio.update_weather(loop_handle, 1.0)
	var weather_vol_1: float = loop_player.volume_db if loop_player != null else 0.0
	var loop_weather_monotonic: bool = loop_player != null and weather_vol_1 > weather_vol_0

	audio.update_rpm(loop_handle, 0.0)
	var rpm_pitch_0: float = loop_player.pitch_scale if loop_player != null else 0.0
	audio.update_rpm(loop_handle, 1.0)
	var rpm_pitch_1: float = loop_player.pitch_scale if loop_player != null else 0.0
	var loop_rpm_changes_pitch: bool = (
		loop_player != null
		and rpm_pitch_1 > rpm_pitch_0
		and not is_equal_approx(rpm_pitch_0, rpm_pitch_1)
	)

	audio.stop_loop(loop_handle)
	var loop_stopped: bool = not audio.is_loop_playing(loop_handle)

	# 3. file イベント口の検証
	var event_paths := PackedStringArray(["res://audio/take_0.wav", "res://audio/take_1.wav"])
	var file_reg_ok: bool = audio.register_event(
		&"footstep",
		event_paths,
		{"pitch_jitter": 0.0, "unit_size": 8.0, "max_distance": 40.0, "base_volume_db": -2.0}
	)
	var file_pos := Vector3(1.0, 2.0, 3.0)
	var file_player: AudioStreamPlayer3D = audio.play_event(&"footstep", file_pos)
	var file_event_ok: bool = (
		file_reg_ok
		and file_player != null
		and file_player.stream != null
		and file_player.global_position.is_equal_approx(file_pos)
		and is_equal_approx(file_player.unit_size, 8.0)
		and is_equal_approx(file_player.max_distance, 40.0)
	)
	var file_loop_handle: int = audio.start_event_loop(&"footstep", file_pos)
	var file_event_loop_ok: bool = file_loop_handle > 0 and audio.is_loop_playing(file_loop_handle)
	audio.stop_loop(file_loop_handle)

	# 4. synth イベント口の検証
	var synth_reg_ok: bool = audio.register_synth_event(&"coin", &"coin", {"seed": 42, "pitch_jitter": 0.0})
	var synth_pos := Vector3(-2.0, 0.5, 4.0)
	var synth_player: AudioStreamPlayer3D = audio.play_event(&"coin", synth_pos)
	var synth_length: float = synth_player.stream.get_length() if (synth_player != null and synth_player.stream != null) else 0.0
	var synth_event_ok: bool = (
		synth_reg_ok
		and synth_player != null
		and synth_player.stream != null
		and synth_length > 0.0
		and synth_player.global_position.is_equal_approx(synth_pos)
	)

	# 5. describe_events の検証
	var desc: Dictionary = audio.describe_events()
	var describe_events_ok: bool = (
		desc.has("footstep")
		and desc.has("coin")
		and desc["footstep"].get("kind", "") == "file"
		and int(desc["footstep"].get("variants", 0)) == 2
		and desc["coin"].get("kind", "") == "synth"
		and int(desc["coin"].get("variants", 0)) == 1
	)

	var result: Dictionary = {
		"pool_round_robin": pool_round_robin,
		"pool_position": pool_position,
		"pool_attenuation": pool_attenuation,
		"pool_pitch_jitter": pool_pitch_jitter,
		"pool_pitch_exact": pool_pitch_exact,
		"loop_playing_start": loop_playing_start,
		"loop_weather_monotonic": loop_weather_monotonic,
		"loop_rpm_changes_pitch": loop_rpm_changes_pitch,
		"loop_stopped": loop_stopped,
		"file_event_ok": file_event_ok,
		"file_event_loop_ok": file_event_loop_ok,
		"synth_event_ok": synth_event_ok,
		"describe_events_ok": describe_events_ok,
		"measured_pitches": measured_pitches,
		"measured_exact_pitch": measured_exact_pitch,
		"measured_unit_size": p0.unit_size if p0 != null else 0.0,
		"measured_max_distance": p0.max_distance if p0 != null else 0.0,
		"weather_vol_0": weather_vol_0,
		"weather_vol_1": weather_vol_1,
		"rpm_pitch_0": rpm_pitch_0,
		"rpm_pitch_1": rpm_pitch_1,
		"synth_length": synth_length,
	}

	audio.stop_all_loops()
	print("UZU_AUDIO_CHECK " + JSON.stringify(result))
	get_tree().quit()
