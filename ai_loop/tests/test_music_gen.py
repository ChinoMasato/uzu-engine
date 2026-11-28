"""Unit tests for ai_loop.music_gen."""

import os
import tempfile
import unittest
import wave

from ai_loop import music_gen


class TestMusicGen(unittest.TestCase):
    def test_music_theory_helpers(self):
        self.assertAlmostEqual(music_gen.note_freq(69), 440.0, places=6)

        c_major = music_gen.scale_notes(60, "major")
        self.assertEqual(len(c_major), 7)
        self.assertEqual(c_major, [60, 62, 64, 65, 67, 69, 71])
        self.assertTrue(all(a < b for a, b in zip(c_major, c_major[1:])))

        d_minor = music_gen.scale_notes(62, "minor")
        self.assertEqual(len(d_minor), 7)
        self.assertTrue(all(a < b for a, b in zip(d_minor, d_minor[1:])))

        self.assertEqual(music_gen.chord_notes(60, "major", 1, octave=4), [60, 64, 67])
        self.assertEqual(music_gen.chord_notes(60, "major", 6, octave=4), [69, 72, 76])
        self.assertEqual(music_gen.chord_notes(62, "minor", 1, octave=4), [62, 65, 69])
        self.assertEqual(music_gen.chord_notes(62, "minor", 7, octave=4), [72, 76, 79])

    def test_determinism_by_seed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "v1.wav")
            p2 = os.path.join(tmpdir, "v2.wav")
            p3 = os.path.join(tmpdir, "v3.wav")

            r1 = music_gen.generate("village", seed=7, bars=2, out_path=p1)
            r2 = music_gen.generate("village", seed=7, bars=2, out_path=p2)
            r3 = music_gen.generate("village", seed=8, bars=2, out_path=p3)

            self.assertEqual(r1["sha256"], r2["sha256"])
            self.assertNotEqual(r1["sha256"], r3["sha256"])
            with open(p1, "rb") as f1, open(p2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())

    def test_wav_format_and_frame_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_wav = os.path.join(tmpdir, "battle.wav")
            report = music_gen.generate("battle", seed=11, bars=2, out_path=out_wav)

            with wave.open(out_wav, "rb") as wf:
                self.assertEqual(wf.getframerate(), 44100)
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getsampwidth(), 2)
                expected_frames = round(report["seconds"] * 44100)
                self.assertLessEqual(abs(wf.getnframes() - expected_frames), 1)

    def test_seam_wrap_jump_with_pad(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_wav = os.path.join(tmpdir, "village_seam.wav")
            report = music_gen.generate("village", seed=7, bars=2, out_path=out_wav)
            self.assertLess(report["seam"]["wrap_jump"], 0.05)
            self.assertGreaterEqual(report["seam"]["wrap_rms"], 0.0)

    def test_presets_structure_and_progression_range(self):
        required_keys = {
            "key",
            "mode",
            "bpm",
            "bars",
            "progression",
            "density",
            "drum_style",
            "pad",
            "bass_pattern",
            "seed_offset",
        }
        for name in ("village", "battle", "title"):
            self.assertIn(name, music_gen.PRESETS)
            preset = music_gen.PRESETS[name]
            self.assertTrue(required_keys.issubset(preset.keys()))
            scale_len = len(music_gen.SCALES[preset["mode"]])
            self.assertTrue(all(1 <= deg <= scale_len for deg in preset["progression"]))

    def test_run_cli_unknown_arg_and_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                music_gen.run_cli(tmpdir, ["--unknown-flag"])

            res = music_gen.run_cli(tmpdir, ["--all", "--bars", "2", "--seed", "5"])
            self.assertIn("results", res)
            self.assertEqual(len(res["results"]), 3)
            for item in res["results"]:
                self.assertEqual(item["format"], "uzu-music/1")
                self.assertEqual(item["bars"], 2)
                self.assertTrue(os.path.isfile(item["file"]))


if __name__ == "__main__":
    unittest.main()
