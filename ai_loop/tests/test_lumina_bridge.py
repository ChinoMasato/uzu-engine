import json
import math
import os
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


class LuminaBridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "game"
        self.project.mkdir()
        self.lumina_dir = self.root / "lumina-sfx"
        self.lumina_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_sfx_set_places_all_with_credits_and_measured_wav(self):
        calls = []

        def stub_runner(argv, cwd):
            calls.append((list(argv), Path(cwd)))
            script = argv[1]
            if script == "scripts/search.mjs":
                return 0, json.dumps({
                    "results": [
                        {
                            "id": "click-switch-01",
                            "credits": [
                                {
                                    "title": "Plastic Switch Click",
                                    "author": "Alice",
                                    "license": "CC0 1.0",
                                    "url": "https://example.com/click",
                                }
                            ],
                        }
                    ]
                }), ""
            if script == "scripts/remix.mjs":
                dest = Path(argv[argv.index("--dest") + 1])
                event = argv[argv.index("--id") + 1]
                out_wav = dest / f"{event}.wav"
                if event in ("menu_click", "menu-click"):
                    write_wav(out_wav, tone_samples(seconds=0.2, amp=0.5))
                    credits = [
                        {
                            "title": "Plastic Switch Click",
                            "author": "Alice",
                            "license": "CC0 1.0",
                            "url": "https://example.com/click",
                        }
                    ]
                else:
                    write_wav(out_wav, tone_samples(seconds=0.5, amp=0.25))
                    credits = [
                        {
                            "title": "Old Wooden Door",
                            "author": "Bob",
                            "license": "CC-BY 4.0",
                            "url": "https://example.com/door",
                        }
                    ]
                return 0, json.dumps({"file": str(out_wav), "credits": credits}), ""
            if script == "scripts/footsteps.mjs":
                out_wav = Path(argv[argv.index("--out") + 1])
                write_wav(out_wav, [0] * int(0.1 * RATE))
                return 0, json.dumps({
                    "file": str(out_wav),
                    "credits": [
                        {
                            "title": "Hardwood Footsteps",
                            "author": "Carol",
                            "license": "CC0 1.0",
                            "url": "https://example.com/steps",
                        }
                    ],
                }), ""
            return 1, "", f"unexpected script: {script}"

        request = {
            "format": "uzu-sfx-request/1",
            "dest": "res://audio/sfx",
            "sounds": [
                {"event": "menu_click", "intent": "clicky switch settings tabs"},
                {
                    "event": "inn_door",
                    "id": "wooden-door-creak",
                    "params": {"force": 0.4},
                    "space": "small_room",
                    "wetness": 0.25,
                },
                {
                    "event": "walk_hardwood",
                    "kind": "footsteps",
                    "surface": "hardwood",
                    "steps": 8,
                    "gait": "walk",
                },
            ],
        }

        res = lumina_bridge.generate_sfx(
            self.project, request, lumina_dir=self.lumina_dir, runner=stub_runner
        )
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["command"], "sfx-lumina")
        self.assertEqual(res["errors"], [])
        self.assertEqual(len(res["placed"]), 3)

        remix_calls = [c for c in calls if c[0][1] == "scripts/remix.mjs"]
        remix_ids = [c[0][c[0].index("--id") + 1] for c in remix_calls]
        self.assertEqual(sorted(remix_ids), ["inn-door", "menu-click"])

        search_calls = [c for c in calls if c[0][1] == "scripts/search.mjs"]
        self.assertEqual(len(search_calls), 1)
        self.assertEqual(search_calls[0][1], self.lumina_dir)

        by_event = {item["event"]: item for item in res["placed"]}
        self.assertEqual(by_event["menu_click"]["file"], "res://audio/sfx/menu_click.wav")
        self.assertEqual(by_event["menu_click"]["lumina_id"], "click-switch-01")
        self.assertAlmostEqual(by_event["menu_click"]["duration_sec"], 0.2, places=3)
        self.assertAlmostEqual(by_event["menu_click"]["peak_db"], 20.0 * math.log10(0.5), delta=0.1)

        self.assertEqual(by_event["inn_door"]["file"], "res://audio/sfx/inn_door.wav")
        self.assertEqual(by_event["inn_door"]["lumina_id"], "wooden-door-creak")
        self.assertAlmostEqual(by_event["inn_door"]["duration_sec"], 0.5, places=3)
        self.assertAlmostEqual(by_event["inn_door"]["peak_db"], 20.0 * math.log10(0.25), delta=0.1)

        self.assertEqual(by_event["walk_hardwood"]["file"], "res://audio/sfx/walk_hardwood.wav")
        self.assertAlmostEqual(by_event["walk_hardwood"]["duration_sec"], 0.1, places=3)
        self.assertTrue(math.isfinite(by_event["walk_hardwood"]["peak_db"]))
        self.assertLessEqual(by_event["walk_hardwood"]["peak_db"], -100.0)

        for item in res["placed"]:
            self.assertTrue(item["credits"])
            self.assertNotIn("credits_missing", item)
            for c in item["credits"]:
                self.assertEqual(set(c.keys()), {"title", "author", "license", "url"})
            rel = item["file"].replace("res://", "")
            self.assertTrue((self.project / rel).is_file())

    def test_single_sound_failure_does_not_stop_others_and_missing_credits_flagged(self):
        def stub_runner(argv, cwd):
            script = argv[1]
            if script == "scripts/search.mjs":
                intent = argv[argv.index("--intent") + 1]
                if "missing" in intent:
                    return 0, json.dumps({"results": []}), ""
                return 0, json.dumps({"results": [{"id": "rain-loop"}]}), ""
            if script == "scripts/remix.mjs":
                dest = Path(argv[argv.index("--dest") + 1])
                event = argv[argv.index("--id") + 1]
                out_wav = dest / f"{event}.wav"
                write_wav(out_wav, tone_samples(seconds=0.1, amp=0.5))
                return 0, json.dumps({"file": str(out_wav)}), ""
            return 1, "", "unknown"

        request = {
            "format": "uzu-sfx-request/1",
            "dest": "res://audio/sfx",
            "sounds": [
                {"event": "broken_sfx", "intent": "missing sound"},
                {"event": "rain_loop", "intent": "light rain loop", "fit_seconds": 6.0},
            ],
        }
        res = lumina_bridge.generate_sfx(
            self.project, request, lumina_dir=self.lumina_dir, runner=stub_runner
        )
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["errors"]), 1)
        self.assertEqual(res["errors"][0]["event"], "broken_sfx")
        self.assertEqual(len(res["placed"]), 1)
        placed = res["placed"][0]
        self.assertEqual(placed["event"], "rain_loop")
        self.assertEqual(placed["credits"], [])
        self.assertIs(placed["credits_missing"], True)
        self.assertTrue((self.project / "audio/sfx/rain_loop.wav").is_file())

    def test_missing_lumina_dir_returns_structured_error(self):
        request = {
            "format": "uzu-sfx-request/1",
            "dest": "res://audio/sfx",
            "sounds": [{"event": "click", "id": "click-01"}],
        }
        res = lumina_bridge.generate_sfx(
            self.project,
            request,
            lumina_dir=self.root / "does-not-exist",
            runner=lambda argv, cwd: (0, "{}", ""),
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["command"], "sfx-lumina")
        self.assertEqual(res["placed"], [])
        self.assertTrue(res["errors"])

    def test_request_validation_errors(self):
        bad_requests = [
            {"format": "wrong/1", "sounds": [{"event": "a", "id": "x"}]},
            {"format": "uzu-sfx-request/1", "sounds": []},
            {
                "format": "uzu-sfx-request/1",
                "sounds": [
                    {"event": "dup", "id": "x"},
                    {"event": "dup", "id": "y"},
                ],
            },
            {
                "format": "uzu-sfx-request/1",
                "sounds": [{"event": "../bad_name", "id": "x"}],
            },
        ]
        for req in bad_requests:
            res = lumina_bridge.generate_sfx(
                self.project,
                req,
                lumina_dir=self.lumina_dir,
                runner=lambda argv, cwd: (0, "{}", ""),
            )
            self.assertFalse(res["ok"], req)
            self.assertEqual(res["placed"], [])
            self.assertTrue(res["errors"])


if __name__ == "__main__":
    unittest.main()
