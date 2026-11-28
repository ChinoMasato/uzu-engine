#!/usr/bin/env python3
"""Specification image registry (BACKLOG B-1222): maps scenes to their
specification illustrations and maintains a shared element correspondence table
(illustration regions <-> scene nodes) with observed/inferred provenance.

Both generation (B-1221, ai_loop/image_scene.py) and diff verification
(B-1223, ai_loop/spec_diff.py) read and update the same registry, and
B-1509 (ai_loop/spec_set.py) records the spec image reference and element
correspondences into scene_spec.json.

Coordinate system:
  All `image_bbox` coordinates ([x0, y0, x1, y1]) MUST be in working pixels
  (the `working_size` [w, h] recorded by `register-image`, downscaled to
  WORK_MAX_W=768 width when the source image is wider), NOT raw source image
  pixels. Values outside [0..w]x[0..h] trigger warnings in `map-element` and
  `validate`.

Registry format ("uzu-spec-registry/1", default <project>/spec_registry.json):
  {
    "format": "uzu-spec-registry/1",
    "images": {
      "<image_id>": {
        "id": "<image_id>",
        "path": "res://illustration.png",
        "title": "...",
        "width": 960,
        "height": 540,
        "working_size": [768, 432],
        "depth_path": null,
        "tags": []
      }
    },
    "scenes": {
      "res://image_scene/image_scene.tscn": {
        "scene": "res://image_scene/image_scene.tscn",
        "spec_image": "<image_id>",
        "spec_image_path": "res://illustration.png",
        "working_size": [768, 432],
        "report_path": "res://image_scene/report.json",
        "elements": [
          {
            "id": "door_0",
            "kind": "door",
            "image_bbox": [157, 298, 183, 359],
            "node": "Candidate_Door_0",
            "basis": "observed" | "inferred",
            "evidence": "..."  // when basis == "observed"
            "reason": "..."    // when basis == "inferred"
          }
        ]
      }
    }
  }

Standard library only.
"""

import json
import os
import re
import struct
import sys
import tempfile
try:
    import pathutil
except ImportError:
    from . import pathutil


FORMAT = "uzu-spec-registry/1"
DEFAULT_REGISTRY = "spec_registry.json"
VALID_BASES = ("observed", "inferred")
WORK_MAX_W = 768
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")

CAPABILITIES = {"required_capabilities": [], "fallback": None}


class RegistryError(ValueError):
    """Raised when a specification image registry or entry is invalid or missing."""


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_id(value, label="id"):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise RegistryError(f"{label} must match {ID_PATTERN.pattern}")
    return value


def working_size(width, height, max_w=WORK_MAX_W):
    """Working resolution used by B-1221 / B-1223 (mirrors image_scene.downscale)."""
    if width <= 0 or height <= 0:
        raise RegistryError(f"image dimensions must be positive, got {width}x{height}")
    if width <= max_w:
        return [int(width), int(height)]
    scale = max_w / width
    return [int(max_w), max(1, round(height * scale))]


def png_dimensions(path):
    """Read (width, height) from a PNG IHDR chunk without decoding pixels."""
    try:
        with open(path, "rb") as f:
            header = f.read(24)
    except OSError as e:
        raise RegistryError(f"cannot read PNG {path}: {e}") from e
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise RegistryError(f"not a valid PNG file: {path}")
    width, height = struct.unpack(">II", header[16:24])
    if width <= 0 or height <= 0:
        raise RegistryError(f"invalid PNG dimensions {width}x{height} in {path}")
    return width, height


def resolve_registry_path(project, registry_path=None):
    """Resolve the registry JSON path (project-relative first, res:// ok, cwd fallback)."""
    project_abs = os.path.abspath(project)
    if not registry_path:
        return os.path.join(project_abs, DEFAULT_REGISTRY)
    try:
        return pathutil.resolve_input_path(project_abs, registry_path, must_exist=False)["path"]
    except pathutil.PathResolutionError as e:
        raise RegistryError(str(e)) from e


def resolve_project_path(project, path):
    """Resolve a res://, project-relative, cwd-relative, or absolute path to an absolute path."""
    try:
        return pathutil.resolve_input_path(project, path, must_exist=False)["path"]
    except pathutil.PathResolutionError as e:
        raise RegistryError(str(e)) from e


def to_project_ref(project, path):
    """Normalize a path inside `project` to res://... when possible."""
    if not nonempty_string(path):
        raise RegistryError("path must be a non-empty string")
    if "\0" in path:
        raise RegistryError("path must not contain null bytes")
    if path.startswith("res://"):
        rel = path[len("res://"):].lstrip("/")
        parts = [p for p in rel.split("/") if p]
        if not parts or ".." in parts:
            raise RegistryError(f"invalid res:// path: {path}")
        return "res://" + "/".join(parts)
    project_abs = os.path.abspath(project)
    target = os.path.abspath(path if os.path.isabs(path) else os.path.join(project_abs, path))
    try:
        if os.path.commonpath([project_abs, target]) == project_abs:
            rel = os.path.relpath(target, project_abs).replace(os.sep, "/")
            return "res://" + rel
    except ValueError:
        pass
    return target


def normalize_scene_ref(scene):
    if not nonempty_string(scene):
        raise RegistryError("scene must be a non-empty string")
    if scene.startswith("res://"):
        rel = scene[len("res://"):].lstrip("/")
        parts = [p for p in rel.split("/") if p]
        if not parts or ".." in parts:
            raise RegistryError(f"invalid scene path: {scene}")
        return "res://" + "/".join(parts)
    return scene


def empty_registry():
    return {"format": FORMAT, "images": {}, "scenes": {}}


def load_registry(path, create=False):
    if not os.path.exists(path):
        if create:
            return empty_registry()
        raise RegistryError(f"no specification registry at {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise RegistryError(f"cannot read specification registry {path}: {e}") from e
    errors = validate_registry(data)
    if errors:
        raise RegistryError("; ".join(errors))
    return data


def save_registry(path, registry):
    errors = validate_registry(registry)
    if errors:
        raise RegistryError("; ".join(errors))
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".spec_registry_", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return path


def validate_element(elem, where="element"):
    """Validate and normalize one element correspondence entry."""
    if not isinstance(elem, dict):
        raise RegistryError(f"{where} must be an object")
    eid = elem.get("id")
    if not nonempty_string(eid):
        raise RegistryError(f"{where}.id must be a non-empty string")
    kind = elem.get("kind")
    if not nonempty_string(kind):
        raise RegistryError(f"{where}.kind must be a non-empty string")
    bbox = elem.get("image_bbox") if "image_bbox" in elem else elem.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise RegistryError(f"{where}.image_bbox must be [x0, y0, x1, y1]")
    try:
        x0, y0, x1, y1 = [int(v) for v in bbox]
    except (TypeError, ValueError) as e:
        raise RegistryError(f"{where}.image_bbox coordinates must be integers") from e
    if x1 <= x0 or y1 <= y0:
        raise RegistryError(f"{where}.image_bbox must have x1 > x0 and y1 > y0, got {[x0, y0, x1, y1]}")
    node = elem.get("node")
    if not nonempty_string(node):
        raise RegistryError(f"{where}.node must be a non-empty scene node name/path")
    basis = elem.get("basis")
    if basis not in VALID_BASES:
        raise RegistryError(f"{where}.basis must be 'observed' or 'inferred', got {basis!r}")
    out = {
        "id": str(eid).strip(),
        "kind": str(kind).strip(),
        "image_bbox": [x0, y0, x1, y1],
        "node": str(node).strip(),
        "basis": basis,
    }
    if basis == "observed":
        evidence = elem.get("evidence")
        if not nonempty_string(evidence):
            raise RegistryError(f"{where} (basis='observed') requires a non-empty 'evidence'")
        out["evidence"] = str(evidence).strip()
    else:
        reason = elem.get("reason")
        if not nonempty_string(reason):
            raise RegistryError(f"{where} (basis='inferred') requires a non-empty 'reason'")
        out["reason"] = str(reason).strip()
    for opt_str in ("label", "card", "node_type", "notes"):
        if nonempty_string(elem.get(opt_str)):
            out[opt_str] = str(elem[opt_str]).strip()
    if "confidence" in elem and elem["confidence"] is not None:
        out["confidence"] = float(elem["confidence"])
    if isinstance(elem.get("position"), list) and len(elem["position"]) == 3:
        out["position"] = [float(v) for v in elem["position"]]
    return out


def validate_registry(registry, project=None, check_files=False):
    """Return a list of validation errors (empty list when valid)."""
    errors = []
    if not isinstance(registry, dict):
        return ["registry must be a JSON object"]
    if registry.get("format") != FORMAT:
        errors.append(f"registry format must be {FORMAT!r}, got {registry.get('format')!r}")
    images = registry.get("images")
    if not isinstance(images, dict):
        errors.append("registry.images must be an object")
        images = {}
    for img_id, img in images.items():
        if not nonempty_string(img_id) or not isinstance(img, dict):
            errors.append(f"images[{img_id!r}] must be an object with a non-empty id")
            continue
        if not nonempty_string(img.get("path")):
            errors.append(f"images[{img_id!r}].path must be a non-empty string")
        elif check_files and project:
            p = resolve_project_path(project, img["path"])
            if not os.path.isfile(p):
                errors.append(f"images[{img_id!r}] file not found: {img['path']}")
        if check_files and project and nonempty_string(img.get("depth_path")):
            dp = resolve_project_path(project, img["depth_path"])
            if not os.path.isfile(dp):
                errors.append(f"images[{img_id!r}] depth file not found: {img['depth_path']}")
    scenes = registry.get("scenes")
    if not isinstance(scenes, dict):
        errors.append("registry.scenes must be an object")
        scenes = {}
    for scene_key, scene_entry in scenes.items():
        if not nonempty_string(scene_key) or not isinstance(scene_entry, dict):
            errors.append(f"scenes[{scene_key!r}] must be an object")
            continue
        spec_img = scene_entry.get("spec_image")
        if not nonempty_string(spec_img):
            errors.append(f"scenes[{scene_key!r}].spec_image is required")
        elif spec_img not in images:
            errors.append(f"scenes[{scene_key!r}].spec_image {spec_img!r} is not registered in images")
        elements = scene_entry.get("elements")
        if not isinstance(elements, list):
            errors.append(f"scenes[{scene_key!r}].elements must be a list")
            continue
        seen_ids = set()
        for idx, elem in enumerate(elements):
            try:
                norm = validate_element(elem, f"scenes[{scene_key!r}].elements[{idx}]")
            except RegistryError as e:
                errors.append(str(e))
                continue
            if norm["id"] in seen_ids:
                errors.append(f"scenes[{scene_key!r}] has duplicate element id {norm['id']!r}")
            seen_ids.add(norm["id"])
    return errors


def register_image(registry, image_id, image_path, project=None, title=None, depth_path=None, tags=None):
    """Register or update a specification image in `registry`."""
    validate_id(image_id, "image_id")
    if project:
        abs_img = resolve_project_path(project, image_path)
        if not os.path.isfile(abs_img):
            raise RegistryError(f"specification image not found: {image_path}")
        stored_path = to_project_ref(project, abs_img)
        w, h = png_dimensions(abs_img)
        ws = working_size(w, h)
        stored_depth = None
        if nonempty_string(depth_path):
            abs_depth = resolve_project_path(project, depth_path)
            if not os.path.isfile(abs_depth):
                raise RegistryError(f"depth map not found: {depth_path}")
            stored_depth = to_project_ref(project, abs_depth)
    else:
        stored_path = image_path
        w = h = None
        ws = None
        if os.path.isfile(image_path):
            w, h = png_dimensions(image_path)
            ws = working_size(w, h)
        stored_depth = depth_path if nonempty_string(depth_path) else None

    existing = registry.setdefault("images", {}).get(image_id, {})
    entry = {
        "id": image_id,
        "path": stored_path,
        "title": title.strip() if nonempty_string(title) else existing.get("title", ""),
        "width": w if w is not None else existing.get("width"),
        "height": h if h is not None else existing.get("height"),
        "working_size": ws if ws is not None else existing.get("working_size"),
        "depth_path": stored_depth if stored_depth is not None else existing.get("depth_path"),
        "tags": sorted({str(t).strip() for t in (tags if tags is not None else existing.get("tags", [])) if str(t).strip()}),
        "basis": "observed" if w is not None else existing.get("basis", "inferred"),
    }
    registry["images"][image_id] = entry
    return entry


def elements_from_report_data(report, spec=None):
    """Convert a B-1221 generation report (and optional B-1207 spec) into
    registry element correspondence entries (all carrying basis observed/inferred)."""
    elements = []
    markers_by_pos = {}
    if isinstance(spec, dict):
        for m in spec.get("markers") or []:
            if isinstance(m, dict) and isinstance(m.get("position"), list) and m.get("name"):
                markers_by_pos[tuple(round(float(v), 3) for v in m["position"])] = str(m["name"])

    cards = (report.get("layers") or {}).get("cards") or []
    bbox_to_card = {}
    for card in cards:
        bbox = card.get("image_bbox")
        name = card.get("name")
        if not name or not isinstance(bbox, list) or len(bbox) != 4:
            continue
        bbox_to_card[tuple(int(v) for v in bbox)] = name
        basis = card.get("basis", "inferred")
        entry = {
            "id": name,
            "kind": "card",
            "image_bbox": [int(v) for v in bbox],
            "node": card.get("node") or name,
            "node_type": "MeshInstance3D",
            "card": name,
            "basis": basis if basis in VALID_BASES else "inferred",
        }
        if isinstance(card.get("position"), list) and len(card["position"]) == 3:
            entry["position"] = [float(v) for v in card["position"]]
        if entry["basis"] == "observed":
            entry["evidence"] = card.get("evidence") or "recorded in generation report"
        else:
            band = card.get("band", "layer")
            entry["reason"] = card.get("reason") or f"cut-out {band} layer card segmented from the specification illustration"
        elements.append(validate_element(entry, f"card {name}"))

    for cand in (report.get("candidates") or {}).get("interact") or []:
        cid = cand.get("id")
        bbox = cand.get("image_bbox")
        if not cid or not isinstance(bbox, list) or len(bbox) != 4:
            continue
        pos = cand.get("position")
        node = cand.get("node")
        if not node and isinstance(pos, list) and len(pos) == 3:
            node = markers_by_pos.get(tuple(round(float(v), 3) for v in pos))
        if not node:
            node = "Candidate_%s" % str(cid).capitalize()
        basis = cand.get("basis", "inferred")
        entry = {
            "id": cid,
            "kind": cand.get("kind") or "interact",
            "image_bbox": [int(v) for v in bbox],
            "node": node,
            "node_type": "Area3D",
            "basis": basis if basis in VALID_BASES else "inferred",
        }
        matched_card = bbox_to_card.get(tuple(int(v) for v in bbox))
        if matched_card:
            entry["card"] = matched_card
        if isinstance(pos, list) and len(pos) == 3:
            entry["position"] = [float(v) for v in pos]
        if cand.get("confidence") is not None:
            entry["confidence"] = float(cand["confidence"])
        if entry["basis"] == "observed":
            entry["evidence"] = cand.get("evidence") or "annotated in specification image"
        else:
            entry["reason"] = cand.get("reason") or "heuristic interact candidate derived from the specification illustration"
        elements.append(validate_element(entry, f"candidate {cid}"))
    return elements


def merge_elements(existing, incoming, overwrite=False):
    """Merge incoming generated elements with existing registered elements.
    Preserves existing 'observed' entries (and any unmatched custom entries)
    unless `overwrite` is True."""
    if overwrite:
        return [validate_element(e) for e in incoming]
    by_id = {e["id"]: dict(e) for e in existing}
    ordered_ids = [e["id"] for e in existing]
    for elem in incoming:
        norm = validate_element(elem)
        eid = norm["id"]
        prev = by_id.get(eid)
        if prev and prev.get("basis") == "observed":
            continue
        if eid not in by_id:
            ordered_ids.append(eid)
        by_id[eid] = norm
    return [by_id[eid] for eid in ordered_ids]


def bind_scene(registry, scene, image_id, report=None, spec=None, report_path=None,
               overwrite_elements=False):
    """Bind a scene (res://...) to a registered specification image."""
    scene_ref = normalize_scene_ref(scene)
    images = registry.get("images") or {}
    if image_id not in images:
        raise RegistryError(f"unknown spec image {image_id!r} (register it first)")
    img = images[image_id]
    prev = (registry.get("scenes") or {}).get(scene_ref, {})
    elements = list(prev.get("elements") or []) if not overwrite_elements else []
    if report is not None:
        incoming = elements_from_report_data(report, spec=spec)
        elements = merge_elements(elements, incoming, overwrite=overwrite_elements)
    entry = {
        "scene": scene_ref,
        "spec_image": image_id,
        "spec_image_path": img["path"],
        "working_size": img.get("working_size") or prev.get("working_size"),
        "report_path": report_path if nonempty_string(report_path) else prev.get("report_path"),
        "elements": [validate_element(e) for e in elements],
    }
    registry.setdefault("scenes", {})[scene_ref] = entry
    return entry


def bbox_warnings(element, working_size):
    """Return warning strings if `element['image_bbox']` is degenerate or outside `working_size`."""
    if not isinstance(element, dict) or not working_size:
        return []
    if not isinstance(working_size, (list, tuple)) or len(working_size) != 2:
        return []
    try:
        w, h = int(working_size[0]), int(working_size[1])
    except (TypeError, ValueError):
        return []
    if w <= 0 or h <= 0:
        return []
    bbox = element.get("image_bbox") if "image_bbox" in element else element.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return []
    try:
        x0, y0, x1, y1 = [int(v) for v in bbox]
    except (TypeError, ValueError):
        return []

    eid = element.get("id") or "<unknown>"
    bbox_val = [x0, y0, x1, y1]
    ws_val = [w, h]
    warnings = []
    if x1 <= x0 or y1 <= y0:
        warnings.append(
            f"element {eid!r} has degenerate image_bbox {bbox_val} "
            f"for working_size {ws_val} (requires x1 > x0 and y1 > y0)"
        )
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        warnings.append(
            f"element {eid!r} image_bbox {bbox_val} exceeds working_size {ws_val} "
            f"(expected working pixels within [0..{w}]x[0..{h}])"
        )
    return warnings


def collect_warnings(registry, project=None):
    """Collect bbox warnings across all scenes and elements in `registry`."""
    if not isinstance(registry, dict):
        return []
    images = registry.get("images") or {}
    scenes = registry.get("scenes") or {}
    if not isinstance(images, dict) or not isinstance(scenes, dict):
        return []
    warnings = []
    for scene_key in sorted(scenes):
        scene_entry = scenes[scene_key]
        if not isinstance(scene_entry, dict):
            continue
        ws = scene_entry.get("working_size")
        if not ws:
            img = images.get(scene_entry.get("spec_image"))
            if isinstance(img, dict):
                ws = img.get("working_size")
        for elem in scene_entry.get("elements") or []:
            warnings.extend(bbox_warnings(elem, ws))
    return warnings


def upsert_element(registry, scene, element):
    """Insert or update one element correspondence on a bound scene.
    `image_bbox` uses working pixels (matching the bound image's `working_size`).
    """
    scene_ref = normalize_scene_ref(scene)
    scenes = registry.get("scenes") or {}
    if scene_ref not in scenes:
        raise RegistryError(f"scene {scene_ref!r} is not bound to a spec image")
    norm = validate_element(element)
    elements = scenes[scene_ref].setdefault("elements", [])
    for i, cur in enumerate(elements):
        if cur.get("id") == norm["id"]:
            elements[i] = norm
            return norm
    elements.append(norm)
    return norm


def remove_element(registry, scene, element_id):
    scene_ref = normalize_scene_ref(scene)
    scenes = registry.get("scenes") or {}
    if scene_ref not in scenes:
        raise RegistryError(f"scene {scene_ref!r} is not bound to a spec image")
    elements = scenes[scene_ref].get("elements") or []
    kept = [e for e in elements if e.get("id") != element_id]
    if len(kept) == len(elements):
        return False
    scenes[scene_ref]["elements"] = kept
    return True


def get_scene_binding(registry, scene):
    """Return resolved scene binding + image entry + basis counts, or None."""
    scene_ref = normalize_scene_ref(scene)
    entry = (registry.get("scenes") or {}).get(scene_ref)
    if not entry:
        return None
    img = (registry.get("images") or {}).get(entry["spec_image"])
    elements = entry.get("elements") or []
    obs = sum(1 for e in elements if e.get("basis") == "observed")
    inf = sum(1 for e in elements if e.get("basis") == "inferred")
    return {
        "scene": scene_ref,
        "spec_image": entry["spec_image"],
        "spec_image_path": img["path"] if img else entry.get("spec_image_path"),
        "image": img,
        "working_size": entry.get("working_size") or (img.get("working_size") if img else None),
        "report_path": entry.get("report_path"),
        "elements": list(elements),
        "counts": {"total": len(elements), "observed": obs, "inferred": inf},
    }


def find_scenes_for_image(registry, image_id_or_path, project=None):
    """Return bound scene entries whose spec_image matches `image_id_or_path`."""
    images = registry.get("images") or {}
    target_ids = set()
    if image_id_or_path in images:
        target_ids.add(image_id_or_path)
    norm_ref = to_project_ref(project, image_id_or_path) if (project and nonempty_string(image_id_or_path)) else image_id_or_path
    for img_id, img in images.items():
        if img.get("path") in (image_id_or_path, norm_ref):
            target_ids.add(img_id)
    out = []
    for scene_ref in sorted(registry.get("scenes") or {}):
        entry = registry["scenes"][scene_ref]
        if entry.get("spec_image") in target_ids:
            out.append(get_scene_binding(registry, scene_ref))
    return out


def list_entries(registry):
    images = [registry["images"][k] for k in sorted(registry.get("images") or {})]
    scenes = [get_scene_binding(registry, k) for k in sorted(registry.get("scenes") or {})]
    return {
        "format": registry.get("format", FORMAT),
        "image_count": len(images),
        "scene_count": len(scenes),
        "images": images,
        "scenes": scenes,
    }


def parse_bbox(text):
    parts = [p.strip() for p in str(text).split(",") if p.strip()]
    if len(parts) != 4:
        raise RegistryError(f"--bbox needs x0,y0,x1,y1, got {text!r}")
    try:
        return [int(p) for p in parts]
    except ValueError as e:
        raise RegistryError(f"--bbox coordinates must be integers: {text!r}") from e


def _opt(args, name, default=None):
    flag = "--" + name
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args) and not args[i + 1].startswith("--"):
            return args[i + 1]
    return default


def run_cli(project, args):
    """Execute `uzu.py spec-registry <project> <subcommand> [options]`."""
    project = os.path.abspath(project)
    if not args or args[0].startswith("--"):
        raise RegistryError("spec-registry needs a subcommand: register-image | bind-scene | map-element | remove-element | get | list | validate")
    sub = args[0]
    rest = args[1:]
    reg_path = resolve_registry_path(project, _opt(rest, "registry"))

    if sub == "list":
        reg = load_registry(reg_path, create=True)
        return {"ok": True, "command": "spec-registry", "subcommand": "list", "registry": reg_path, **list_entries(reg)}

    if sub == "validate":
        reg = load_registry(reg_path, create=False)
        errors = validate_registry(reg, project=project, check_files=True)
        warnings = collect_warnings(reg, project=project)
        total_elems = sum(len(s.get("elements") or []) for s in (reg.get("scenes") or {}).values())
        return {
            "ok": not errors,
            "command": "spec-registry",
            "subcommand": "validate",
            "registry": reg_path,
            "errors": errors,
            "warnings": warnings,
            "image_count": len(reg.get("images") or {}),
            "scene_count": len(reg.get("scenes") or {}),
            "element_count": total_elems,
        }

    if sub == "get":
        reg = load_registry(reg_path, create=False)
        scene = _opt(rest, "scene")
        image_id = _opt(rest, "image-id")
        basis_filter = _opt(rest, "basis")
        if basis_filter and basis_filter not in VALID_BASES:
            raise RegistryError(f"--basis must be observed or inferred, got {basis_filter!r}")
        if scene:
            binding = get_scene_binding(reg, scene)
            if not binding:
                raise RegistryError(f"scene {scene!r} is not registered in {reg_path}")
            if basis_filter:
                binding["elements"] = [e for e in binding["elements"] if e["basis"] == basis_filter]
            return {"ok": True, "command": "spec-registry", "subcommand": "get", "registry": reg_path, **binding}
        if image_id:
            img = (reg.get("images") or {}).get(image_id)
            if not img:
                raise RegistryError(f"image {image_id!r} is not registered in {reg_path}")
            bound = find_scenes_for_image(reg, image_id, project=project)
            return {"ok": True, "command": "spec-registry", "subcommand": "get", "registry": reg_path,
                    "image": img, "scenes": [b["scene"] for b in bound]}
        raise RegistryError("spec-registry get needs --scene res://... or --image-id ID")

    if sub == "register-image":
        image_id = _opt(rest, "id")
        image_path = _opt(rest, "image")
        if not image_id or not image_path:
            raise RegistryError("register-image needs --id ID and --image PATH")
        tags_raw = _opt(rest, "tags")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw is not None else None
        reg = load_registry(reg_path, create=True)
        entry = register_image(
            reg, image_id, image_path, project=project,
            title=_opt(rest, "title"), depth_path=_opt(rest, "depth"), tags=tags,
        )
        save_registry(reg_path, reg)
        return {"ok": True, "command": "spec-registry", "subcommand": "register-image",
                "registry": reg_path, "image": entry}

    if sub == "bind-scene":
        scene = _opt(rest, "scene")
        image_id = _opt(rest, "image-id")
        if not scene or not image_id:
            raise RegistryError("bind-scene needs --scene res://... and --image-id ID")
        reg = load_registry(reg_path, create=False)
        report_data = spec_data = None
        report_ref = _opt(rest, "report")
        if report_ref:
            rpath = resolve_project_path(project, report_ref)
            if not os.path.isfile(rpath):
                raise RegistryError(f"report not found: {report_ref}")
            with open(rpath, encoding="utf-8") as f:
                report_data = json.load(f)
            report_ref = to_project_ref(project, rpath)
        spec_ref = _opt(rest, "spec")
        if spec_ref:
            spath = resolve_project_path(project, spec_ref)
            if not os.path.isfile(spath):
                raise RegistryError(f"spec not found: {spec_ref}")
            with open(spath, encoding="utf-8") as f:
                spec_data = json.load(f)
        entry = bind_scene(
            reg, scene, image_id, report=report_data, spec=spec_data,
            report_path=report_ref, overwrite_elements="--overwrite" in rest,
        )
        save_registry(reg_path, reg)
        return {"ok": True, "command": "spec-registry", "subcommand": "bind-scene",
                "registry": reg_path, **get_scene_binding(reg, entry["scene"])}

    if sub == "map-element":
        scene = _opt(rest, "scene")
        if not scene:
            raise RegistryError("map-element needs --scene res://...")
        reg = load_registry(reg_path, create=False)
        binding = get_scene_binding(reg, scene)
        ws = binding.get("working_size") if binding else None
        batch_file = _opt(rest, "elements")
        if batch_file:
            bpath = resolve_project_path(project, batch_file)
            with open(bpath, encoding="utf-8") as f:
                items = json.load(f)
            if not isinstance(items, list):
                raise RegistryError("--elements file must contain a JSON array")
            updated = [upsert_element(reg, scene, item) for item in items]
            save_registry(reg_path, reg)
            res = {"ok": True, "command": "spec-registry", "subcommand": "map-element",
                   "registry": reg_path, "scene": normalize_scene_ref(scene), "updated": updated}
            warnings = []
            for item in updated:
                warnings.extend(bbox_warnings(item, ws))
            if warnings:
                res["warnings"] = warnings
            return res
        elem = {
            "id": _opt(rest, "id"),
            "kind": _opt(rest, "kind"),
            "image_bbox": parse_bbox(_opt(rest, "bbox", "")),
            "node": _opt(rest, "node"),
            "basis": _opt(rest, "basis", "observed"),
            "evidence": _opt(rest, "evidence"),
            "reason": _opt(rest, "reason"),
            "label": _opt(rest, "label"),
            "card": _opt(rest, "card"),
            "node_type": _opt(rest, "node-type"),
        }
        conf = _opt(rest, "confidence")
        if conf is not None:
            elem["confidence"] = float(conf)
        stored = upsert_element(reg, scene, elem)
        save_registry(reg_path, reg)
        res = {"ok": True, "command": "spec-registry", "subcommand": "map-element",
               "registry": reg_path, "scene": normalize_scene_ref(scene), "element": stored}
        warnings = bbox_warnings(stored, ws)
        if warnings:
            res["warnings"] = warnings
        return res

    if sub == "remove-element":
        scene = _opt(rest, "scene")
        eid = _opt(rest, "id")
        if not scene or not eid:
            raise RegistryError("remove-element needs --scene res://... and --id ID")
        reg = load_registry(reg_path, create=False)
        removed = remove_element(reg, scene, eid)
        if not removed:
            raise RegistryError(f"element {eid!r} not found on scene {scene!r}")
        save_registry(reg_path, reg)
        return {"ok": True, "command": "spec-registry", "subcommand": "remove-element",
                "registry": reg_path, "scene": normalize_scene_ref(scene), "removed": eid}

    raise RegistryError(f"unknown spec-registry subcommand {sub!r}")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 2
    project = argv[0]
    try:
        result = run_cli(project, argv[1:])
    except RegistryError as e:
        print(json.dumps({"ok": False, "command": "spec-registry", "error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
