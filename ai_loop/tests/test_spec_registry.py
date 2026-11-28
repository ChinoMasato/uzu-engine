"""B-1222: specification image registry (ai_loop/spec_registry.py).

Pins the judgement of the BACKLOG item mechanically without an engine:
  * two screens can be registered, bound, saved, reloaded, listed and validated,
  * observed/inferred element correspondences survive save/load and merge
    round-trips with evidence/reason intact,
  * elements imported from image_scene's report are referenced identically by
    spec_diff, and registered elements override/inject into image_scene.analyze,
  * B-1509 scene_spec records the spec_image reference and separates observed
    and inferred element correspondences,
  * uzu.py CLI wiring (spec-registry, image-scene --registry, spec-diff --registry)
    operates on a project cleanly.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))
import image_scene  # noqa: E402
import spec_diff  # noqa: E402
import spec_registry  # noqa: E402
import spec_set  # noqa: E402
import uzu  # noqa: E402

SKY = (70, 90, 140)
GROUND = (60, 70, 40)
WALL = (150, 120, 90)
DOOR = (40, 30, 25)
WINDOW = (255, 220, 130)
TREE = (25, 60, 25)


def draw_scene_png(path, width=320, height=180, erase_door=False):
    px = bytearray(width * height * 4)
    horizon = int(height * 0.61)
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 4
            px[i:i + 4] = bytes([*SKY, 255]) if y < horizon else bytes([*GROUND, 255])
    for y in range(int(height * 0.33), int(height * 0.83)):
        for x in range(int(width * 0.125), int(width * 0.5)):
            i = (y * width + x) * 4
            px[i:i + 4] = bytes([*WALL, 255])
    if not erase_door:
        for y in range(int(height * 0.53), int(height * 0.83)):
            for x in range(int(width * 0.1875), int(width * 0.245)):
                i = (y * width + x) * 4
                px[i:i + 4] = bytes([*DOOR, 255])
    for y in range(int(height * 0.42), int(height * 0.53)):
        for x in range(int(width * 0.34), int(width * 0.42)):
            i = (y * width + x) * 4
            px[i:i + 4] = bytes([*WINDOW, 255])
    for y in range(int(height * 0.50), int(height * 0.97)):
        for x in range(int(width * 0.75), int(width * 0.90)):
            i = (y * width + x) * 4
            px[i:i + 4] = bytes([*TREE, 255])
    image_scene.write_png(str(path), width, height, px)


class SpecRegistryTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="uzu_spec_reg_"))
        self.project = self.dir / "game"
        (self.project / "art").mkdir(parents=True)
        (self.project / "project.godot").write_text(
            '[application]\nconfig/name="RegTest"\nrun/main_scene="res://scenes/title.tscn"\n',
            encoding="utf-8",
        )
        self.title_png = self.project / "art" / "title_spec.png"
        self.village_png = self.project / "art" / "village_spec.png"
        draw_scene_png(self.title_png, 640, 360)
        draw_scene_png(self.village_png, 960, 540)
        self.reg_path = self.project / "spec_registry.json"

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_two_screens_register_bind_and_validate(self):
        res_t = spec_registry.run_cli(str(self.project), [
            "register-image", "--id", "title_screen", "--image", "res://art/title_spec.png",
            "--title", "Title Screen", "--tags", "title,gate",
        ])
        res_v = spec_registry.run_cli(str(self.project), [
            "register-image", "--id", "village_square", "--image", str(self.village_png),
            "--title", "Village Square", "--tags", "village",
        ])
        self.assertTrue(res_t["ok"])
        self.assertTrue(res_v["ok"])
        self.assertEqual(res_t["image"]["working_size"], [640, 360])
        self.assertEqual(res_v["image"]["working_size"], [768, 432])
        self.assertEqual(res_v["image"]["path"], "res://art/village_spec.png")

        spec_registry.run_cli(str(self.project), [
            "bind-scene", "--scene", "res://scenes/title.tscn", "--image-id", "title_screen",
        ])
        spec_registry.run_cli(str(self.project), [
            "bind-scene", "--scene", "res://scenes/village.tscn", "--image-id", "village_square",
        ])

        listed = spec_registry.run_cli(str(self.project), ["list"])
        self.assertEqual(listed["image_count"], 2)
        self.assertEqual(listed["scene_count"], 2)
        self.assertEqual([s["scene"] for s in listed["scenes"]],
                         ["res://scenes/title.tscn", "res://scenes/village.tscn"])

        got = spec_registry.run_cli(str(self.project), ["get", "--image-id", "village_square"])
        self.assertEqual(got["scenes"], ["res://scenes/village.tscn"])

        validated = spec_registry.run_cli(str(self.project), ["validate"])
        self.assertTrue(validated["ok"], validated)
        self.assertEqual(validated["errors"], [])

    def test_observed_and_inferred_round_trip_and_merge(self):
        reg = spec_registry.empty_registry()
        spec_registry.register_image(reg, "village_square", str(self.village_png), project=str(self.project))
        spec_registry.bind_scene(reg, "res://scenes/village.tscn", "village_square")

        obs_elem = {
            "id": "inn_door",
            "kind": "door",
            "image_bbox": [140, 230, 190, 340],
            "node": "InnFrontDoor",
            "node_type": "Area3D",
            "basis": "observed",
            "evidence": "wooden door painted on the inn facade",
        }
        inf_elem = {
            "id": "alley_sign",
            "kind": "sign",
            "image_bbox": [520, 250, 580, 320],
            "node": "AlleySignpost",
            "node_type": "Area3D",
            "basis": "inferred",
            "reason": "placed along the alley entrance for player navigation",
            "confidence": 0.75,
        }
        spec_registry.upsert_element(reg, "res://scenes/village.tscn", obs_elem)
        spec_registry.upsert_element(reg, "res://scenes/village.tscn", inf_elem)
        spec_registry.save_registry(str(self.reg_path), reg)

        reloaded = spec_registry.load_registry(str(self.reg_path))
        binding = spec_registry.get_scene_binding(reloaded, "res://scenes/village.tscn")
        self.assertEqual(binding["counts"], {"total": 2, "observed": 1, "inferred": 1})

        by_id = {e["id"]: e for e in binding["elements"]}
        self.assertEqual(by_id["inn_door"]["basis"], "observed")
        self.assertEqual(by_id["inn_door"]["evidence"], "wooden door painted on the inn facade")
        self.assertNotIn("reason", by_id["inn_door"])
        self.assertEqual(by_id["alley_sign"]["basis"], "inferred")
        self.assertEqual(by_id["alley_sign"]["reason"], "placed along the alley entrance for player navigation")
        self.assertEqual(by_id["alley_sign"]["confidence"], 0.75)
        self.assertNotIn("evidence", by_id["alley_sign"])

        # Incoming inferred update must preserve existing observed element unless overwrite=True.
        incoming_report = {
            "layers": {"cards": []},
            "candidates": {"interact": [
                {"id": "inn_door", "kind": "door", "image_bbox": [145, 235, 195, 345],
                 "basis": "inferred", "reason": "heuristic doorway"},
                {"id": "street_lamp", "kind": "lamp", "image_bbox": [260, 180, 290, 230],
                 "basis": "inferred", "reason": "bright highlight"},
            ]},
        }
        spec_registry.bind_scene(reloaded, "res://scenes/village.tscn", "village_square",
                                 report=incoming_report, overwrite_elements=False)
        merged = {e["id"]: e for e in spec_registry.get_scene_binding(reloaded, "res://scenes/village.tscn")["elements"]}
        self.assertEqual(merged["inn_door"]["basis"], "observed")
        self.assertEqual(merged["inn_door"]["node"], "InnFrontDoor")
        self.assertEqual(merged["street_lamp"]["basis"], "inferred")

        with self.assertRaises(spec_registry.RegistryError):
            spec_registry.validate_element({
                "id": "bad_obs", "kind": "door", "image_bbox": [10, 10, 30, 30],
                "node": "Door", "basis": "observed",
            })
        with self.assertRaises(spec_registry.RegistryError):
            spec_registry.validate_element({
                "id": "bad_inf", "kind": "lamp", "image_bbox": [10, 10, 30, 30],
                "node": "Lamp", "basis": "inferred",
            })

    def test_image_scene_and_spec_diff_share_registry_elements(self):
        spec_png = self.project / "art" / "shared_village.png"
        draw_scene_png(spec_png, 320, 180)
        spec, report, _ = image_scene.analyze(
            str(spec_png), out_res="res://village", scene_name="village"
        )

        reg = spec_registry.empty_registry()
        spec_registry.register_image(reg, "shared_village", str(spec_png), project=str(self.project))
        spec_registry.bind_scene(reg, "res://village/village.tscn", "shared_village",
                                 report=report, spec=spec)
        spec_registry.save_registry(str(self.reg_path), reg)

        reloaded = spec_registry.load_registry(str(self.reg_path))
        from_report = spec_diff.elements_from_report(report)
        from_registry = spec_diff.elements_from_registry(reloaded, "res://village/village.tscn")
        self.assertGreater(len(from_report), 0)
        self.assertEqual(
            [(e["id"], e["kind"], e["bbox"], e["basis"]) for e in from_registry],
            [(e["id"], e["kind"], e["bbox"], e["basis"]) for e in from_report],
        )
        self.assertTrue(all(e.get("node") for e in from_registry))

        same_verdict = spec_diff.compare(str(spec_png), str(spec_png), from_registry)
        self.assertTrue(same_verdict["ok"], same_verdict)
        self.assertEqual([e["node"] for e in same_verdict["elements"]],
                         [e["node"] for e in from_registry])

        # Annotate an element as observed and inject an extra sign, then re-run image_scene.analyze.
        first_id = from_registry[0]["id"]
        spec_registry.upsert_element(reloaded, "res://village/village.tscn", {
            "id": first_id,
            "kind": from_registry[0]["kind"],
            "image_bbox": from_registry[0]["bbox"],
            "node": "Custom_Main_Facade",
            "basis": "observed",
            "evidence": "human-verified facade correspondence",
        })
        spec_registry.upsert_element(reloaded, "res://village/village.tscn", {
            "id": "custom_sign",
            "kind": "sign",
            "image_bbox": [20, 115, 45, 145],
            "node": "VillageSignboard",
            "basis": "observed",
            "evidence": "wooden signboard on the left roadside",
        })
        binding = spec_registry.get_scene_binding(reloaded, "res://village/village.tscn")
        spec2, report2, _ = image_scene.analyze(
            str(spec_png), out_res="res://village", scene_name="village",
            registry_elements=binding["elements"],
        )
        self.assertIn("registry", report2)
        self.assertGreaterEqual(report2["registry"]["matched"], 1)
        self.assertEqual(report2["registry"]["injected"], 1)
        marker_names = [m["name"] for m in spec2["markers"]]
        self.assertIn("VillageSignboard", marker_names)

    def test_scene_spec_records_spec_image_and_provenance(self):
        spec, report, _ = image_scene.analyze(
            str(self.village_png), out_res="res://village", scene_name="village"
        )
        reg = spec_registry.empty_registry()
        spec_registry.register_image(reg, "village_square", str(self.village_png), project=str(self.project))
        spec_registry.bind_scene(reg, "res://village/village.tscn", "village_square",
                                 report=report, spec=spec)
        spec_registry.upsert_element(reg, "res://village/village.tscn", {
            "id": "inn_door",
            "kind": "door",
            "image_bbox": [144, 286, 188, 358],
            "node": "InnDoor",
            "basis": "observed",
            "evidence": "inn entrance door visible in specification painting",
        })
        spec_registry.upsert_element(reg, "res://village/village.tscn", {
            "id": "lantern_inferred",
            "kind": "lamp",
            "image_bbox": [262, 226, 322, 286],
            "node": "InnLantern",
            "basis": "inferred",
            "reason": "warm highlight inferred as an overhanging lantern",
        })

        record = {
            "kind": "image_scene",
            "scene": "res://village/village.tscn",
            "generator": "image_scene",
            "spec_source": "res://village/spec.json",
            "spec": spec,
            "built": {
                "cards": len(spec["cards"]),
                "markers": len(spec["markers"]),
                "lamps": len(spec["lamps"]),
            },
        }
        enriched = spec_set.attach_registry_to_record(record, reg, registry_ref="spec_registry.json")
        out_dir = self.project / "village" / "spec_set"
        written = spec_set.spec_set_from_record(enriched, str(out_dir))
        scene_spec = json.loads(Path(written["files"]["scene_spec"]).read_text(encoding="utf-8"))

        self.assertEqual(scene_spec["spec_image"], {
            "id": "village_square",
            "path": "res://art/village_spec.png",
            "registry": "spec_registry.json",
            "working_size": [768, 432],
        })
        obs_by_name = {o["name"]: o for o in scene_spec["observed"]}
        inf_by_name = {i["name"]: i for i in scene_spec["inferred"]}
        self.assertEqual(obs_by_name["spec_image.size"]["value"], [960, 540])
        self.assertIn("element.inn_door", obs_by_name)
        self.assertEqual(obs_by_name["element.inn_door"]["value"]["node"], "InnDoor")
        self.assertEqual(obs_by_name["element.inn_door"]["evidence"],
                         "inn entrance door visible in specification painting")
        self.assertIn("element.lantern_inferred", inf_by_name)
        self.assertEqual(inf_by_name["element.lantern_inferred"]["value"]["node"], "InnLantern")
        self.assertEqual(inf_by_name["element.lantern_inferred"]["reason"],
                         "warm highlight inferred as an overhanging lantern")

    def test_uzu_cli_wiring_end_to_end(self):
        shot_png = self.project / "shot.png"
        draw_scene_png(shot_png, 640, 360)

        r1 = uzu.spec_registry_cmd(str(self.project), [
            "register-image", "--id", "title_screen", "--image", "res://art/title_spec.png",
        ])
        self.assertTrue(r1["ok"])
        r2 = uzu.spec_registry_cmd(str(self.project), [
            "bind-scene", "--scene", "res://title/title.tscn", "--image-id", "title_screen",
        ])
        self.assertTrue(r2["ok"])
        r3 = uzu.spec_registry_cmd(str(self.project), [
            "map-element", "--scene", "res://title/title.tscn",
            "--id", "gate_door", "--kind", "door", "--bbox", "120,190,156,298",
            "--node", "TitleGateDoor", "--basis", "observed",
            "--evidence", "gate doorway visible in title specification",
        ])
        self.assertTrue(r3["ok"])

        gen = uzu.image_scene_cmd(str(self.project), [
            "--out", "title", "--registry", "spec_registry.json", "--no-build", "--no-walk",
        ])
        self.assertTrue(gen["ok"], gen)
        self.assertEqual(gen["registry"], str(self.reg_path))
        self.assertIn("TitleGateDoor", [m["name"] for m in json.loads(Path(gen["spec_file"]).read_text(encoding="utf-8"))["markers"]])

        verdict = uzu.spec_diff_cmd(str(self.project), [
            "--registry", "spec_registry.json", "--scene", "res://title/title.tscn",
            "--shot-png", str(shot_png),
        ])
        self.assertTrue(verdict["ok"], verdict)
        self.assertEqual(verdict["element_source"], "registry")
        self.assertEqual(verdict["elements"][0]["node"], "TitleGateDoor")


if __name__ == "__main__":
    unittest.main()
class SpecRegistryBboxWarningsTest(unittest.TestCase):
    """B-1226: working-pixel coordinate system documentation and bbox range warnings."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="uzu_spec_reg_bbox_"))
        self.project = self.dir / "game"
        (self.project / "art").mkdir(parents=True)
        (self.project / "project.godot").write_text(
            '[application]\nconfig/name="RegBboxTest"\nrun/main_scene="res://scenes/village.tscn"\n',
            encoding="utf-8",
        )
        # 960x540 downscales to working_size [768, 432].
        self.village_png = self.project / "art" / "village_spec.png"
        draw_scene_png(self.village_png, 960, 540)
        self.reg_path = self.project / "spec_registry.json"

        spec_registry.run_cli(str(self.project), [
            "register-image", "--id", "village_square", "--image", "res://art/village_spec.png",
        ])
        spec_registry.run_cli(str(self.project), [
            "bind-scene", "--scene", "res://scenes/village.tscn", "--image-id", "village_square",
        ])

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_validate_warns_on_out_of_bounds_bbox(self):
        reg = spec_registry.load_registry(str(self.reg_path))
        # Raw-pixel bbox exceeding working_size [768, 432].
        spec_registry.upsert_element(reg, "res://scenes/village.tscn", {
            "id": "street_raw",
            "kind": "ground",
            "image_bbox": [0, 266, 960, 540],
            "node": "StreetMesh",
            "basis": "observed",
            "evidence": "street along the lower frame",
        })
        spec_registry.save_registry(str(self.reg_path), reg)

        validated = spec_registry.run_cli(str(self.project), ["validate"])
        self.assertTrue(validated["ok"], validated)
        self.assertEqual(validated["errors"], [])
        self.assertEqual(len(validated["warnings"]), 1)
        msg = validated["warnings"][0]
        self.assertIn("street_raw", msg)
        self.assertIn("[0, 266, 960, 540]", msg)
        self.assertIn("[768, 432]", msg)

    def test_validate_no_warnings_when_bbox_within_working_size(self):
        reg = spec_registry.load_registry(str(self.reg_path))
        spec_registry.upsert_element(reg, "res://scenes/village.tscn", {
            "id": "street_working",
            "kind": "ground",
            "image_bbox": [0, 266, 768, 432],
            "node": "StreetMesh",
            "basis": "observed",
            "evidence": "street along the lower frame in working pixels",
        })
        spec_registry.save_registry(str(self.reg_path), reg)

        validated = spec_registry.run_cli(str(self.project), ["validate"])
        self.assertTrue(validated["ok"], validated)
        self.assertEqual(validated["errors"], [])
        self.assertEqual(validated["warnings"], [])

    def test_map_element_includes_warnings_for_out_of_bounds_bbox(self):
        single = spec_registry.run_cli(str(self.project), [
            "map-element", "--scene", "res://scenes/village.tscn",
            "--id", "wide_sky", "--kind", "sky", "--bbox", "0,0,960,240",
            "--node", "SkyBackdrop", "--basis", "observed",
            "--evidence", "sky recorded in source image pixels",
        ])
        self.assertTrue(single["ok"], single)
        self.assertIn("warnings", single)
        self.assertEqual(len(single["warnings"]), 1)
        self.assertIn("wide_sky", single["warnings"][0])
        self.assertIn("[0, 0, 960, 240]", single["warnings"][0])
        self.assertIn("[768, 432]", single["warnings"][0])

        in_bounds = spec_registry.run_cli(str(self.project), [
            "map-element", "--scene", "res://scenes/village.tscn",
            "--id", "inn_door", "--kind", "door", "--bbox", "140,230,190,340",
            "--node", "InnDoor", "--basis", "observed",
            "--evidence", "door within working_size bounds",
        ])
        self.assertTrue(in_bounds["ok"], in_bounds)
        self.assertNotIn("warnings", in_bounds)

        batch_path = self.project / "batch_elements.json"
        batch_path.write_text(json.dumps([
            {
                "id": "batch_oob",
                "kind": "tree",
                "image_bbox": [700, 100, 820, 450],
                "node": "EdgeTree",
                "basis": "observed",
                "evidence": "tree extending past working_size",
            },
            {
                "id": "batch_ok",
                "kind": "lamp",
                "image_bbox": [200, 150, 240, 220],
                "node": "StreetLamp",
                "basis": "inferred",
                "reason": "lamp along street",
            },
        ]), encoding="utf-8")
        batch = spec_registry.run_cli(str(self.project), [
            "map-element", "--scene", "res://scenes/village.tscn",
            "--elements", str(batch_path),
        ])
        self.assertTrue(batch["ok"], batch)
        self.assertIn("warnings", batch)
        self.assertEqual(len(batch["warnings"]), 1)
        self.assertIn("batch_oob", batch["warnings"][0])
        self.assertIn("[700, 100, 820, 450]", batch["warnings"][0])
        self.assertIn("[768, 432]", batch["warnings"][0])

    def test_degenerate_bbox_produces_warning(self):
        w_x = spec_registry.bbox_warnings(
            {"id": "flat_x", "image_bbox": [200, 100, 200, 250]},
            [768, 432],
        )
        self.assertEqual(len(w_x), 1)
        self.assertIn("flat_x", w_x[0])
        self.assertIn("[200, 100, 200, 250]", w_x[0])
        self.assertIn("[768, 432]", w_x[0])

        w_y = spec_registry.bbox_warnings(
            {"id": "inverted_y", "image_bbox": [100, 300, 220, 200]},
            [768, 432],
        )
        self.assertEqual(len(w_y), 1)
        self.assertIn("inverted_y", w_y[0])
        self.assertIn("[100, 300, 220, 200]", w_y[0])
        self.assertIn("[768, 432]", w_y[0])

        self.assertEqual(
            spec_registry.bbox_warnings({"id": "no_ws", "image_bbox": [100, 300, 220, 200]}, None),
            [],
        )
        self.assertEqual(
            spec_registry.bbox_warnings({"id": "no_bbox"}, [768, 432]),
            [],
        )
