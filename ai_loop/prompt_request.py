#!/usr/bin/env python3
"""Project-side prompt exchange and deterministic composition (B-1327)."""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from string import Template

REQUEST_FORMAT = "uzu-prompt-request/1"
RESULT_FORMAT = "uzu-prompt-result/1"
DEFAULT_STORE = ".uzu/prompt-requests"
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


class RequestStateError(Exception):
    """The requested ID does not exist or has already been written."""


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_id(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError("id must match [a-z0-9][a-z0-9_-]{0,63}")


def validate_request(request):
    if not isinstance(request, dict) or request.get("format") != REQUEST_FORMAT:
        raise ValueError(f"request format must be {REQUEST_FORMAT}")
    validate_id(request.get("id"))
    if not nonempty_string(request.get("kind")):
        raise ValueError("kind must be a non-empty string")
    if request.get("expect") not in ("file", "json", "text"):
        raise ValueError("expect must be file, json or text")
    if not isinstance(request.get("context"), dict):
        raise ValueError("context must be an object")
    mode = request.get("mode")
    if mode == "fixed":
        if not nonempty_string(request.get("prompt")) or "brief" in request:
            raise ValueError("fixed requests require prompt and must omit brief")
    elif mode == "design":
        brief = request.get("brief")
        if "prompt" in request or not isinstance(brief, dict):
            raise ValueError("design requests require brief and must omit prompt")
        if not nonempty_string(brief.get("objective")):
            raise ValueError("brief.objective must be a non-empty string")
        constraints = brief.get("constraints")
        if not isinstance(constraints, list) or not all(map(nonempty_string, constraints)):
            raise ValueError("brief.constraints must be an array of non-empty strings")
    else:
        raise ValueError("mode must be fixed or design")


def validate_result(request, result):
    if not isinstance(result, dict) or result.get("format") != RESULT_FORMAT:
        raise ValueError(f"result format must be {RESULT_FORMAT}")
    if result.get("id") != request["id"]:
        raise ValueError("result id must match the request id")
    if result.get("type") != request["expect"] or "value" not in result:
        raise ValueError("result type must match expect and value is required")
    if request["mode"] == "design" or "used_prompt" in result:
        if not nonempty_string(result.get("used_prompt")):
            raise ValueError("used_prompt must contain the actual prompt")
        if request["mode"] == "fixed" and result["used_prompt"] != request["prompt"]:
            raise ValueError("used_prompt must match the fixed prompt exactly")
    if result["type"] == "text" and not isinstance(result["value"], str):
        raise ValueError("text result value must be a string")
    if result["type"] == "file":
        value = result["value"]
        if not nonempty_string(value) or any(char in value for char in "\\:\0"):
            raise ValueError("file result value must be a project-relative file path")
        path = Path(value)
        if path.anchor or ".." in path.parts:
            raise ValueError("file result value must be a project-relative file path")


def compose(template, elements):
    """Substitute literal element text in one pass, preserving whitespace."""
    if not isinstance(elements, dict) or not all(isinstance(v, str) for v in elements.values()):
        raise ValueError("elements must be an object of string values")
    try:
        return Template(template).substitute(elements)
    except KeyError as e:
        raise ValueError(f"missing prompt element {e.args[0]!r}") from e


def json_text(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def read_json(path):
    with Path(path).open(encoding="utf-8") as f:
        value = json.load(f)
    # Check for values the wire format cannot represent, including NaN and overflow.
    json_text(value).encode("utf-8")
    return value


def write_new_json(path, value):
    """Publish a complete JSON file without overwriting an existing record."""
    f = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                    suffix=".tmp", delete=False)
    temp = Path(f.name)
    try:
        with f:
            f.write(json_text(value) + "\n")
        os.link(temp, path)
    finally:
        temp.unlink()


class PromptStore:
    def __init__(self, project, store=DEFAULT_STORE):
        self.project = Path(project).resolve()
        if not (self.project / "project.godot").is_file():
            raise ValueError(f"{project} is not a project (no project.godot)")
        self.store = self.project / store

    def paths(self, request_id):
        validate_id(request_id)
        return (self.store / f"request-{request_id}.json",
                self.store / f"result-{request_id}.json")

    def issue(self, request):
        validate_request(request)
        path, _ = self.paths(request["id"])
        self.store.mkdir(parents=True, exist_ok=True)
        try:
            write_new_json(path, request)
        except FileExistsError as e:
            raise RequestStateError(f"request {request['id']!r} already exists") from e

    def get(self, request_id):
        path, result_path = self.paths(request_id)
        try:
            request = read_json(path)
        except FileNotFoundError as e:
            raise RequestStateError(f"unknown request {request_id!r}") from e
        validate_request(request)
        if request["id"] != request_id:
            raise ValueError(f"request id does not match filename: {path}")
        try:
            result = read_json(result_path)
        except FileNotFoundError:
            return {"state": "pending", "request": request}
        validate_result(request, result)
        return {"state": "done", "request": request, "result": result}

    def pending(self):
        try:
            paths = sorted(self.store.iterdir())
        except FileNotFoundError:
            return []
        requests = []
        for path in paths:
            if path.name.startswith("request-") and path.suffix == ".json":
                entry = self.get(path.stem[len("request-"):])
                if entry["state"] == "pending":
                    requests.append(entry["request"])
        return requests

    def submit(self, request_id, result):
        entry = self.get(request_id)
        if entry["state"] == "done":
            raise RequestStateError(f"request {request_id!r} already has a result")
        validate_result(entry["request"], result)
        if result["type"] == "file":
            file = (self.project / result["value"]).resolve()
            if self.project not in file.parents or not file.is_file():
                raise ValueError("file result must name an existing file inside the project")
        _, path = self.paths(request_id)
        try:
            write_new_json(path, result)
        except FileExistsError as e:
            raise RequestStateError(f"request {request_id!r} already has a result") from e


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv):
    parser = JsonArgumentParser(prog="uzu.py prompt-request", description=__doc__, allow_abbrev=False)
    parser.add_argument("project", help="Godot project directory")
    actions = parser.add_subparsers(dest="action", required=True)
    project_options = JsonArgumentParser(add_help=False, allow_abbrev=False)
    project_options.add_argument("--store", default=DEFAULT_STORE, help="absolute or project-relative store directory")
    issue = actions.add_parser("issue", parents=[project_options], allow_abbrev=False)
    issue.add_argument("--request", required=True, help="request JSON file")
    actions.add_parser("list", parents=[project_options], allow_abbrev=False)
    get = actions.add_parser("get", parents=[project_options], allow_abbrev=False)
    get.add_argument("id")
    submit = actions.add_parser("submit", parents=[project_options], allow_abbrev=False)
    submit.add_argument("id")
    submit.add_argument("--result", required=True, help="result JSON file")
    synthesis = actions.add_parser("compose", allow_abbrev=False)
    synthesis.add_argument("--elements", required=True, help="element table JSON file")
    synthesis.add_argument("--template", required=True, help="UTF-8 template file")

    output = {"command": "prompt-request"}
    try:
        args = parser.parse_args(argv)
        output["action"] = args.action
        if args.action == "compose":
            elements = read_json(args.elements)
            template = Path(args.template).read_bytes().decode("utf-8")
            output["prompt"] = compose(template, elements)
        else:
            store = PromptStore(args.project, args.store)
            if args.action == "issue":
                request = read_json(args.request)
                store.issue(request)
                output.update(state="pending", request=request)
            elif args.action == "list":
                output["requests"] = store.pending()
            elif args.action == "get":
                output.update(store.get(args.id))
            else:
                result = read_json(args.result)
                store.submit(args.id, result)
                output.update(state="done", result=result)
        output["ok"] = True
        code = 0
    except RequestStateError as e:
        output.update(ok=False, error=str(e))
        code = 1
    except (OSError, ValueError, RuntimeError) as e:
        output.update(ok=False, error=str(e))
        code = 2
    print(json_text(output))
    return code


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
