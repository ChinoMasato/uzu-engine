"""B-1327: an agent reads requests and returns results through the public CLI."""

import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOOP))
import image_scene  # noqa: E402
import spec_diff  # noqa: E402


def draw_illustration(path):
    sky = bytes((70, 100, 145, 255))
    ground = bytes((50, 70, 40, 255))
    tower = bytes((230, 165, 75, 255))
    pixels = bytearray(sky * (64 * 36) + ground * (64 * 12))
    for y in range(15, 37):
        start = (y * 64 + 26) * 4
        pixels[start:start + 12 * 4] = tower * 12
    image_scene.write_png(path, 64, 48, pixels)


def stub_agent(project, request, design_prompt=None):
    """Use the supplied fixed prompt or the stub's own design, then run the fixture."""
    used_prompt = request["prompt"] if request["mode"] == "fixed" else design_prompt(request["brief"])
    context = request["context"]
    if request["kind"] == "image":
        value = context["output"]
        draw_illustration(project / value)
    else:
        comparison = spec_diff.compare(project / context["reference"], project / context["shot"], [])
        value = {"passed": comparison["ok"], "metrics": comparison["metrics"]}
    result = {"format": "uzu-prompt-result/1", "id": request["id"], "type": request["expect"], "value": value}
    if request["mode"] == "design":
        result["used_prompt"] = used_prompt
    return result, used_prompt


class PromptRequestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)
        (self.project / "project.godot").write_text("config_version=5\n", encoding="utf-8")

    def json_file(self, name, value):
        path = self.project / (name + ".json")
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def cli(self, tool, *args, code=0):
        completed = subprocess.run(
            [sys.executable, str(LOOP / "uzu.py"), tool, str(self.project), *map(str, args)],
            capture_output=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(completed.returncode, code, (completed.stdout, completed.stderr))
        data = json.loads(completed.stdout)
        self.assertIs(data["ok"], code == 0)
        return data

    def call(self, *args, code=0):
        return self.cli("prompt-request", *args, code=code)

    def compose(self, elements, template):
        template_file = self.project / "prompt.txt"
        template_file.write_bytes(template.encode("utf-8"))
        return self.call("compose", "--elements", elements, "--template", template_file)["prompt"]

    def issue(self, request, *args, code=0):
        path = self.json_file("incoming-request", request)
        return self.call("issue", "--request", path, *args, code=code)

    def submit(self, request_id, result, *args, code=0):
        path = self.json_file("incoming-result", result)
        return self.call("submit", request_id, "--result", path, *args, code=code)

    def request(self, request_id="sample", **changes):
        return {"format": "uzu-prompt-request/1", "id": request_id, "kind": "text",
                "mode": "fixed", "expect": "text", "context": {}, "prompt": "  こんにちは\n", **changes}

    def result(self, request_id="sample", **changes):
        return {"format": "uzu-prompt-result/1", "id": request_id, "type": "text",
                "value": "  おかえり\n", **changes}

    def round_trip(self, kind, mode, objective, constraint, expect, context):
        request_id = f"{kind}-{mode}"
        template = "  ${objective}\r\n条件: ${constraint}\n"
        expected_prompt = f"  {objective}\r\n条件: {constraint}\n"

        def design_prompt(brief):
            elements = self.json_file("elements", {
                "objective": brief["objective"], "constraint": brief["constraints"][0],
            })
            prompt = self.compose(elements, template)
            self.assertEqual(self.compose(elements, template), prompt)
            return prompt

        brief = {"objective": objective, "constraints": [constraint]}
        request = self.request(request_id, kind=kind, mode=mode, expect=expect, context=context)
        if mode == "fixed":
            request["prompt"] = design_prompt(brief)
        else:
            del request["prompt"]
            request["brief"] = brief
        self.assertEqual(self.call("list")["requests"], [])
        self.assertEqual(self.issue(request)["state"], "pending")
        self.assertEqual(self.call("list")["requests"], [request])
        entry = self.call("get", request_id)
        self.assertEqual(entry["state"], "pending")
        result, used_prompt = stub_agent(self.project, entry["request"], design_prompt)
        self.assertEqual(used_prompt, expected_prompt)
        if mode == "design":
            missing_prompt = dict(result)
            del missing_prompt["used_prompt"]
            self.submit(request_id, missing_prompt, code=2)
            self.assertEqual(self.call("list")["requests"], [request])
        self.assertEqual(self.submit(request_id, result)["state"], "done")
        self.assertEqual(self.call("list")["requests"], [])
        entry = self.call("get", request_id)
        self.assertEqual((entry["state"], entry["request"], entry["result"]), ("done", request, result))
        disk = self.project / ".uzu/prompt-requests" / f"result-{request_id}.json"
        self.assertEqual(json.loads(disk.read_text(encoding="utf-8")), result)
        if mode == "design":
            self.assertEqual(entry["result"]["used_prompt"], expected_prompt)
        return entry["result"]["value"]

    def image_round_trip(self, mode):
        value = self.round_trip("image", mode, "灯台のある仕様イラストを描く", "PNG 64×48", "file",
                                {"output": "illustration.png"})
        image = self.project / value
        scaffold = self.cli("image-scene", "--image", image, "--no-build")
        self.assertEqual(scaffold["report"]["image"]["working_size"], [64, 48])
        self.assertEqual((self.project / "image_scene/background.png").read_bytes(), image.read_bytes())

    def eval_round_trip(self, mode):
        reference = self.project / "reference.png"
        shot = self.project / "screenshot.png"
        draw_illustration(reference)
        if mode == "fixed":
            shot.write_bytes(reference.read_bytes())
        else:
            image_scene.write_png(shot, 64, 48, bytes((0, 0, 0, 255)) * (64 * 48))
        value = self.round_trip("eval", mode, "撮影結果を仕様イラストと比較する",
                                "構図と色の測定値を返す", "json",
                                {"reference": reference.name, "shot": shot.name})
        self.assertIs(value["passed"], mode == "fixed")
        self.assertEqual(set(value["metrics"]), {"composition", "color"})

    def test_fixed_image(self):
        self.image_round_trip("fixed")

    def test_design_image(self):
        self.image_round_trip("design")

    def test_fixed_screenshot_evaluation(self):
        self.eval_round_trip("fixed")

    def test_design_screenshot_evaluation(self):
        self.eval_round_trip("design")

    def test_composition_is_literal(self):
        elements = self.json_file("elements", {"a": "  ${b}\r\n", "b": "日本語"})
        self.assertEqual(self.compose(elements, "${a}${b} $$ ${a}\r\n"), "  ${b}\r\n日本語 $   ${b}\r\n\r\n")
        template = self.project / "prompt.txt"
        for invalid in ("${unknown}", "${}"):
            template.write_text(invalid, encoding="utf-8")
            self.call("compose", "--elements", elements, "--template", template, code=2)

    def test_text_and_store_override(self):
        custom = self.project / "exchange"
        self.issue(self.request("zeta"), "--store", custom)
        self.issue(self.request("alpha"), "--store", "exchange")
        self.assertEqual([r["id"] for r in self.call("list", "--store", custom)["requests"]], ["alpha", "zeta"])
        self.assertEqual(self.call("list")["requests"], [])
        self.submit("alpha", self.result("alpha"), "--store", custom)
        self.assertEqual(self.call("get", "alpha", "--store", custom)["result"]["value"], "  おかえり\n")

    def test_invalid_requests_and_results_leave_state_intact(self):
        self.call("get", "unknown", code=1)
        self.call("issue", code=2)
        for changes in ({"format": "uzu-prompt-request/2"}, {"id": "../bad"}, {"expect": "png"},
                        {"prompt": " "}, {"mode": "design"}, {"brief": {}}, {"context": []}):
            with self.subTest(request=changes):
                self.issue(dict(self.request(), **changes), code=2)
        self.assertEqual(self.call("list")["requests"], [])
        self.issue(self.request())
        self.issue(self.request(prompt="replacement"), code=1)
        for changes in ({"format": "uzu-prompt-result/2"}, {"id": "other"}, {"type": "json"},
                        {"value": 5}, {"used_prompt": "rewritten"}):
            with self.subTest(result=changes):
                self.submit("sample", dict(self.result(), **changes), code=2)
        malformed = self.project / "malformed.json"
        malformed.write_text('{"value": NaN}', encoding="utf-8")
        self.call("submit", "sample", "--result", malformed, code=2)
        self.assertEqual(self.call("list")["requests"], [self.request()])
        self.submit("sample", self.result())
        self.submit("sample", self.result(value="replacement"), code=1)
        self.assertEqual(self.call("get", "sample")["result"], self.result())

    def test_file_must_exist_inside_project(self):
        self.issue(self.request(expect="file"))
        for path in ("missing.png", "../outside.png", str(self.project / "project.godot"), ".", "res://a.png"):
            self.submit("sample", self.result(type="file", value=path), code=2)
        self.assertEqual(self.call("get", "sample")["state"], "pending")

    def test_concurrent_submissions_keep_one_complete_result(self):
        self.issue(self.request())
        candidates = [self.result(value="first"), self.result(value="second")]
        files = [self.json_file(f"candidate-{i}", result) for i, result in enumerate(candidates)]

        def submit(path):
            return subprocess.run(
                [sys.executable, str(LOOP / "uzu.py"), "prompt-request", str(self.project),
                 "submit", "sample", "--result", str(path)],
                capture_output=True, encoding="utf-8", timeout=30,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(submit, files))
        self.assertEqual(sorted(reply.returncode for reply in replies), [0, 1])
        winner = next(i for i, reply in enumerate(replies) if reply.returncode == 0)
        self.assertEqual(self.call("get", "sample")["result"], candidates[winner])
        self.assertEqual(list(self.project.glob(".uzu/prompt-requests/*.tmp")), [])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PromptRequestTests)
    result = unittest.TextTestRunner().run(suite)
    print(json.dumps({"ok": result.wasSuccessful(), "command": "prompt-request-check",
                      "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)}))
    sys.exit(0 if result.wasSuccessful() else 1)
