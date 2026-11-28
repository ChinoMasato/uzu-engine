import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))

from uzu import find_godot  # noqa: E402

AUDIO_SCRIPT = LOOP / "uzu_game_audio.gd"
SAMPLE_PROJECT = LOOP / "samples" / "game_audio_check"


def _write_sine_wav(path: Path, freq_hz: float, duration_sec: float = 0.1, sample_rate: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(round(duration_sec * sample_rate))
    frames = bytearray()
    for i in range(frame_count):
        t = i / sample_rate
        val = int(round(math.sin(2.0 * math.pi * freq_hz * t) * 0.25 * 32767.0))
        val = max(-32768, min(32767, val))
        frames.extend(struct.pack("<h", val))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


class TestGameAudio(unittest.TestCase):
    def test_static_uzu_game_audio_contract(self) -> None:
        self.assertTrue(AUDIO_SCRIPT.is_file(), f"Missing {AUDIO_SCRIPT}")
        text = AUDIO_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("class_name UZUGameAudio", text)
        self.assertIn("extends Node", text)
        self.assertIn("MIT License", text)
        self.assertIn("Lumina SFX", text)
        self.assertIn("https://github.com/LuminaBench/lumina-sfx", text)
        self.assertNotIn("EXPECTED_VARIANTS", text)

        required_funcs = [
            "register_pool",
            "register_streams",
            "play_one_shot",
            "start_loop",
            "update_rpm",
            "update_weather",
            "set_loop_position",
            "stop_loop",
            "stop_all_loops",
            "is_loop_playing",
            "scene_pose",
            "register_event",
            "register_synth_event",
            "play_event",
            "start_event_loop",
            "describe_events",
        ]
        for fn in required_funcs:
            self.assertIn(f"func {fn}(", text, f"Missing function definition: {fn}")

    def test_runtime_game_audio_check(self) -> None:
        try:
            binary = find_godot()
        except Exception as exc:
            self.skipTest(f"Godot binary unavailable: {exc}")

        self.assertTrue(SAMPLE_PROJECT.is_dir(), f"Missing sample project at {SAMPLE_PROJECT}")

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "game_audio_check"
            shutil.copytree(SAMPLE_PROJECT, proj)
            shutil.copy2(AUDIO_SCRIPT, proj / "uzu_game_audio.gd")

            _write_sine_wav(proj / "audio" / "take_0.wav", 330.0)
            _write_sine_wav(proj / "audio" / "take_1.wav", 660.0)

            import_res = subprocess.run(
                [binary, "--headless", "--path", str(proj), "--import"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                import_res.returncode,
                0,
                f"--import failed ({import_res.returncode}):\n{import_res.stdout}\n{import_res.stderr}",
            )

            run_res = subprocess.run(
                [binary, "--headless", "--path", str(proj)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                run_res.returncode,
                0,
                f"Execution failed ({run_res.returncode}):\n{run_res.stdout}\n{run_res.stderr}",
            )

            payload = None
            for line in run_res.stdout.splitlines():
                if line.startswith("UZU_AUDIO_CHECK "):
                    payload = json.loads(line[len("UZU_AUDIO_CHECK "):])
                    break

            self.assertIsNotNone(payload, f"Missing UZU_AUDIO_CHECK line in stdout:\n{run_res.stdout}")

            bool_keys = [
                "pool_round_robin",
                "pool_position",
                "pool_attenuation",
                "pool_pitch_jitter",
                "pool_pitch_exact",
                "loop_playing_start",
                "loop_weather_monotonic",
                "loop_rpm_changes_pitch",
                "loop_stopped",
                "file_event_ok",
                "file_event_loop_ok",
                "synth_event_ok",
                "describe_events_ok",
            ]
            for key in bool_keys:
                self.assertTrue(payload.get(key), f"Check '{key}' failed in payload: {payload}")

            self.assertGreater(payload["weather_vol_1"], payload["weather_vol_0"])
            self.assertGreater(payload["rpm_pitch_1"], payload["rpm_pitch_0"])
            self.assertGreater(payload["synth_length"], 0.0)


if __name__ == "__main__":
    unittest.main()
