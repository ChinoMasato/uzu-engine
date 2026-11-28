"""B-1225: unified CLI input path resolution (ai_loop/pathutil.py)."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))
import image_scene  # noqa: E402
import pathutil  # noqa: E402
import spec_registry  # noqa: E402
import uzu  # noqa: E402


def write_tiny_png(path, width=64, height=48):
    px = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 4
            if y < height // 2:
                px[i:i + 4] = bytes([70, 90, 140, 255])
            else:
                px[i:i + 4] = bytes([60, 70, 40, 255])
    image_scene.write_png(str(path), width, height, px)


class PathUtilTest(unittest.TestCase):
    def setUp(self):
        self.orig_cwd = os.getcwd()
        self.dir = Path(tempfile.mkdtemp(prefix="uzu_pathutil_"))
        self.project = self.dir / "project"
        self.cwd_dir = self.dir / "cwd"
        (self.project / "art").mkdir(parents=True)
        self.cwd_dir.mkdir(parents=True)
        (self.project / "project.godot").write_text(
            '[application]\nconfig/name="PathUtilTest"\n',
            encoding="utf-8",
        )
        self.proj_img = self.project / "art" / "spec.png"
        self.shared_proj = self.project / "shared.png"
        self.shared_cwd = self.cwd_dir / "shared.png"
        self.cwd_only = self.cwd_dir / "cwd_only.png"
        self.abs_img = self.dir / "outside.png"
        write_tiny_png(self.proj_img)
        write_tiny_png(self.shared_proj)
        write_tiny_png(self.shared_cwd)
        write_tiny_png(self.cwd_only)
        write_tiny_png(self.abs_img)
        os.chdir(self.cwd_dir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_res_path(self):
        res = pathutil.resolve_input_path(str(self.project), "res://art/spec.png")
        self.assertEqual(res, {"path": os.path.abspath(self.proj_img), "via": "res"})

    def test_absolute_path(self):
        abs_target = os.path.abspath(self.abs_img)
        res = pathutil.resolve_input_path(str(self.project), abs_target)
        self.assertEqual(res, {"path": abs_target, "via": "absolute"})

    def test_project_relative_wins_over_cwd(self):
        res = pathutil.resolve_input_path(str(self.project), "shared.png")
        self.assertEqual(res, {"path": os.path.abspath(self.shared_proj), "via": "project"})

    def test_cwd_relative_fallback(self):
        res = pathutil.resolve_input_path(str(self.project), "cwd_only.png")
        self.assertEqual(res, {"path": os.path.abspath(self.cwd_only), "via": "cwd"})

    def test_missing_raises_with_both_candidates(self):
        with self.assertRaises(pathutil.PathResolutionError) as ctx:
            pathutil.resolve_input_path(str(self.project), "missing.png")
        msg = str(ctx.exception)
        self.assertIsInstance(ctx.exception, ValueError)
        self.assertIn("missing.png", msg)
        self.assertIn(os.path.abspath(self.project / "missing.png"), msg)
        self.assertIn(os.path.abspath(self.cwd_dir / "missing.png"), msg)

    def test_must_exist_false_returns_project_relative(self):
        res = pathutil.resolve_input_path(str(self.project), "not_yet.png", must_exist=False)
        self.assertEqual(res, {"path": os.path.abspath(self.project / "not_yet.png"), "via": "project"})

    def test_res_escape_raises(self):
        for bad in ("res://../outside.png", "res://art/../../outside.png"):
            with self.assertRaises(pathutil.PathResolutionError):
                pathutil.resolve_input_path(str(self.project), bad)
            with self.assertRaises(pathutil.PathResolutionError):
                pathutil.resolve_input_path(str(self.project), bad, must_exist=False)

    def test_spec_registry_resolve_project_path_matches_pathutil(self):
        for raw in ("res://art/spec.png", os.path.abspath(self.abs_img), "shared.png", "cwd_only.png"):
            expected = pathutil.resolve_input_path(str(self.project), raw, must_exist=False)["path"]
            self.assertEqual(spec_registry.resolve_project_path(str(self.project), raw), expected)

        with self.assertRaises(spec_registry.RegistryError):
            spec_registry.resolve_project_path(str(self.project), "res://../outside.png")

        self.assertEqual(
            spec_registry.resolve_registry_path(str(self.project), None),
            os.path.abspath(self.project / "spec_registry.json"),
        )
        self.assertEqual(
            spec_registry.resolve_registry_path(str(self.project), "res://custom_reg.json"),
            os.path.abspath(self.project / "custom_reg.json"),
        )
        with self.assertRaises(spec_registry.RegistryError):
            spec_registry.resolve_registry_path(str(self.project), "res://../escape.json")

    def test_uzu_commands_report_resolved_and_error_candidates(self):
        thresh_file = self.project / "thresh.json"
        thresh_file.write_text(json.dumps({"composition_min": 0.1}), encoding="utf-8")

        gen = uzu.image_scene_cmd(str(self.project), [
            "--image", "art/spec.png", "--no-build", "--no-walk",
        ])
        self.assertTrue(gen["ok"], gen)
        self.assertEqual(
            gen["resolved"]["image"],
            {"path": os.path.abspath(self.proj_img), "via": "project"},
        )

        verdict = uzu.spec_diff_cmd(str(self.project), [
            "--spec-image", "art/spec.png",
            "--report", "image_scene/report.json",
            "--shot-png", "cwd_only.png",
            "--thresholds", "thresh.json",
        ])
        self.assertTrue(verdict["ok"], verdict)
        self.assertEqual(
            verdict["resolved"]["spec-image"],
            {"path": os.path.abspath(self.proj_img), "via": "project"},
        )
        self.assertEqual(
            verdict["resolved"]["report"],
            {"path": os.path.abspath(self.project / "image_scene" / "report.json"), "via": "project"},
        )
        self.assertEqual(
            verdict["resolved"]["shot-png"],
            {"path": os.path.abspath(self.cwd_only), "via": "cwd"},
        )
        self.assertEqual(
            verdict["resolved"]["thresholds"],
            {"path": os.path.abspath(thresh_file), "via": "project"},
        )

        with self.assertRaises(uzu.ToolError) as err_ctx:
            uzu.image_scene_cmd(str(self.project), [
                "--image", "no_such.png", "--no-build", "--no-walk",
            ])
        err_msg = str(err_ctx.exception)
        self.assertIn(os.path.abspath(self.project / "no_such.png"), err_msg)
        self.assertIn(os.path.abspath(self.cwd_dir / "no_such.png"), err_msg)


if __name__ == "__main__":
    unittest.main()
