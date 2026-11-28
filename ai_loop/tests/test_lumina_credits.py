import json
import math
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))

import lumina_bridge  # noqa: E402

RATE = 44100


def write_wav(path, samples, rate=RATE):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setparams((1, 2, rate, len(samples), "NONE", ""))
        handle.writeframes(struct.pack("<%dh" % len(samples), *samples))


def tone_samples(seconds=0.25, amp=0.5, freq=440.0, rate=RATE):
    count = int(seconds * rate)
    return [int(amp * 32767 * math.sin(2 * math.pi * freq * i / rate)) for i in range(count)]


def _arg_value(argv, flag):
    idx = argv.index(flag)
    return argv[idx + 1]


class LuminaCreditsAndGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "game"
        self.project.mkdir()
        self.lumina_dir = self.root / "lumina-sfx"
        self.lumina_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _make_stub_runner(self, credits_by_id):
        def stub_runner(argv, cwd):
            script = argv[1]
            if script == "scripts/remix.mjs":
                recipe_id = argv[2]
                out_id = _arg_value(argv, "--id")
                dest = Path(_arg_value(argv, "--dest"))
                wav_path = dest / f"{out_id}.wav"
                write_wav(wav_path, tone_samples())
                credits = credits_by_id.get(recipe_id, [])
                return 0, json.dumps({
                    "pass": True,
                    "file": str(wav_path),
                    "credits": credits,
                }), ""
            return 1, "", f"unexpected script: {script}"

        return stub_runner

    def test_manifest_created_and_merged_across_runs(self):
        runner = self._make_stub_runner({
            "click-01": [{
                "title": "Plastic Click",
                "author": "Alice",
                "license": "CC0-1.0",
                "url": "https://example.com/click",
            }],
            "coin-01": [{
                "title": "Metal Coin",
                "author": "Bob",
                "license": "Public Domain",
                "url": "https://example.com/coin",
            }],
            "jump-01": [{
                "title": "Spring Jump",
                "author": "Carol",
                "license": "PD",
                "url": "https://example.com/jump",
            }],
        })

        req1 = {
            "format": "uzu-sfx-request/1",
            "sounds": [
                {"event": "ui_click", "id": "click-01"},
                {"event": "pickup_coin", "id": "coin-01"},
            ],
        }
        res1 = lumina_bridge.generate_sfx(
            self.project, req1, lumina_dir=self.lumina_dir, runner=runner
        )
        self.assertTrue(res1["ok"])
        self.assertEqual(res1["manifest"], "res://audio/sfx/uzu_sfx_credits.json")
        self.assertEqual(res1["warnings"], [])

        manifest_path = self.project / "audio" / "sfx" / "uzu_sfx_credits.json"
        self.assertTrue(manifest_path.is_file())
        data1 = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(data1["format"], "uzu-sfx-credits/1")
        self.assertEqual(set(data1["sounds"].keys()), {"ui_click", "pickup_coin"})
        self.assertEqual(data1["sounds"]["ui_click"]["file"], "res://audio/sfx/ui_click.wav")
        self.assertEqual(data1["sounds"]["ui_click"]["lumina_id"], "click-01")
        self.assertEqual(data1["sounds"]["ui_click"]["credits"][0]["author"], "Alice")

        req2 = {
            "format": "uzu-sfx-request/1",
            "sounds": [
                {"event": "player_jump", "id": "jump-01"},
            ],
        }
        res2 = lumina_bridge.generate_sfx(
            self.project, req2, lumina_dir=self.lumina_dir, runner=runner
        )
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["warnings"], [])

        data2 = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(set(data2["sounds"].keys()), {"ui_click", "pickup_coin", "player_jump"})
        self.assertEqual(data2["sounds"]["ui_click"]["credits"][0]["title"], "Plastic Click")
        self.assertEqual(data2["sounds"]["player_jump"]["credits"][0]["license"], "PD")

    def test_corrupt_manifest_warns_without_overwriting(self):
        dest = self.project / "audio" / "sfx"
        dest.mkdir(parents=True)
        manifest_path = dest / "uzu_sfx_credits.json"
        manifest_path.write_text("{broken json", encoding="utf-8")

        runner = self._make_stub_runner({
            "click-01": [{
                "title": "Click",
                "author": "Alice",
                "license": "CC0-1.0",
                "url": "",
            }],
        })
        req = {
            "format": "uzu-sfx-request/1",
            "sounds": [{"event": "ui_click", "id": "click-01"}],
        }
        res = lumina_bridge.generate_sfx(
            self.project, req, lumina_dir=self.lumina_dir, runner=runner
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["errors"], [])
        self.assertEqual(len(res["warnings"]), 1)
        self.assertEqual(manifest_path.read_text(encoding="utf-8"), "{broken json")

    def test_license_warnings_for_cc_by_and_credits_missing(self):
        runner = self._make_stub_runner({
            "cc0-item": [{
                "title": "Free Hit",
                "author": "Alice",
                "license": "CC0 1.0",
                "url": "",
            }],
            "ccby-item": [{
                "title": "Synth Zap",
                "author": "Dave",
                "license": "CC-BY 4.0",
                "url": "https://example.com/zap",
            }],
            "nocred-item": [],
        })
        req = {
            "format": "uzu-sfx-request/1",
            "sounds": [
                {"event": "hit_free", "id": "cc0-item"},
                {"event": "laser_zap", "id": "ccby-item"},
                {"event": "mystery_sfx", "id": "nocred-item"},
            ],
        }
        res = lumina_bridge.generate_sfx(
            self.project, req, lumina_dir=self.lumina_dir, runner=runner
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["errors"], [])

        warnings_by_event = {w["event"]: w for w in res["warnings"]}
        self.assertEqual(set(warnings_by_event.keys()), {"laser_zap", "mystery_sfx"})
        self.assertEqual(warnings_by_event["laser_zap"]["license"], "CC-BY 4.0")
        self.assertIsNone(warnings_by_event["mystery_sfx"]["license"])
        self.assertIn("missing", warnings_by_event["mystery_sfx"]["reason"].lower())

    def test_check_export_detects_catalog_and_recipes_and_allows_clean_dir(self):
        clean_dir = self.root / "export_clean"
        (clean_dir / "audio" / "sfx").mkdir(parents=True)
        write_wav(clean_dir / "audio" / "sfx" / "click.wav", tone_samples())
        (clean_dir / "audio" / "sfx" / "uzu_sfx_credits.json").write_text(
            json.dumps({"format": "uzu-sfx-credits/1", "sounds": {}}),
            encoding="utf-8",
        )
        (clean_dir / "catalog.json").write_text(
            json.dumps({"recipes": [{"id": "item-1"}]}),
            encoding="utf-8",
        )
        clean_res = lumina_bridge.check_export(clean_dir)
        self.assertTrue(clean_res["ok"])
        self.assertEqual(clean_res["command"], "sfx-lumina")
        self.assertEqual(clean_res["violations"], [])

        catalog_dir = self.root / "export_catalog"
        catalog_dir.mkdir()
        (catalog_dir / "catalog.json").write_text(
            json.dumps({"recipes": [{"id": f"r-{i}"} for i in range(51)]}),
            encoding="utf-8",
        )
        catalog_res = lumina_bridge.check_export(catalog_dir)
        self.assertFalse(catalog_res["ok"])
        self.assertEqual(
            catalog_res["violations"],
            [{"path": "catalog.json", "rule": "lumina-catalog"}],
        )

        recipes_dir = self.root / "export_recipes"
        (recipes_dir / "recipes").mkdir(parents=True)
        (recipes_dir / "recipes" / "laser.ts").write_text("export default {};\n", encoding="utf-8")
        recipes_res = lumina_bridge.check_export(recipes_dir)
        self.assertFalse(recipes_res["ok"])
        self.assertEqual(
            recipes_res["violations"],
            [{"path": "recipes/laser.ts", "rule": "lumina-recipes"}],
        )

        skill_dir = self.root / "export_skill"
        (skill_dir / "scripts").mkdir(parents=True)
        (skill_dir / "scripts" / "remix.mjs").write_text("// remix\n", encoding="utf-8")
        skill_res = lumina_bridge.check_export(skill_dir)
        self.assertFalse(skill_res["ok"])
        self.assertEqual(
            skill_res["violations"],
            [{"path": "scripts/remix.mjs", "rule": "lumina-skill-file"}],
        )

        missing_res = lumina_bridge.check_export(self.root / "does_not_exist")
        self.assertFalse(missing_res["ok"])
        self.assertTrue(missing_res.get("errors"))

    def test_run_cli_check_export_mode(self):
        export_dir = self.root / "cli_export"
        (export_dir / "recipes").mkdir(parents=True)
        (export_dir / "recipes" / "click.ts").write_text("export {};\n", encoding="utf-8")

        res = lumina_bridge.run_cli(self.project, ["--check-export", str(export_dir)])
        self.assertFalse(res["ok"])
        self.assertEqual(res["command"], "sfx-lumina")
        self.assertEqual(res["checked"], str(export_dir))
        self.assertEqual(
            res["violations"],
            [{"path": "recipes/click.ts", "rule": "lumina-recipes"}],
        )


if __name__ == "__main__":
    unittest.main()
