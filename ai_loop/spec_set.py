#!/usr/bin/env python3
"""The generation spec set (BACKLOG B-1509): four JSON documents that travel
with every generated map or built scene, so a later tool (the walking check
B-1510, the re-read audit B-1511, another agent) can see what was asked for,
what the generator actually did, and how much of it is verified.

  scene_spec.json       the intent (the input spec, verbatim) and the fixed
                        facts, split by how they are known:
                        - "parameters" lists every resolved parameter with
                          origin "given" (in the input spec) or "defaulted"
                          (the generator filled it from a preset/default);
                        - "observed" lists facts the generator measured and
                          reported (counts, place positions, the navigation
                          bake), each with the result field it came from;
                        - "inferred" lists what was filled in or presumed
                          (defaulted parameters, the region graph's edges),
                          each with the reason it is only an inference.
  region_graph.json     region nodes (the generator's named places, with
                        centers) and bidirectional edges with lengths. The
                        edges are a minimum spanning tree over the observed
                        centers: connectivity is inferred from the places
                        and the navigation bake, never observed -- B-1510
                        walks every edge and replaces the inference with
                        evidence.
  asset_registry.json   the part families that were used, where each came
                        from (generator, preset, seed, spec file) and how
                        many there are (observed counts where the generator
                        reports them).
  validation_report.json  one entry per check: a claim, a status of
                        Verified / Partial / Unverified (how strong the
                        evidence for the claim is), "holds" (true / false /
                        null: whether the evidence supports the claim,
                        contradicts it, or cannot say) and the evidence
                        itself -- a file reference or a measured value.
                        Nothing is upgraded silently: reachability by
                        walking stays Unverified here on purpose, because
                        only B-1510's walk can verify it.

uzu.py map / build write the set when --spec-set is passed (a folder, or
the default <scene>_spec_set next to the scene). This module is also a
small CLI for turning a saved generation record into a set:

  python3 ai_loop/spec_set.py --record record.json --out DIR

A record is {"kind": "map"|"build", "generator": str, "scene": res://...,
"spec_source": str|None, "input_spec": {...}, "result": {...},
"report": {...}|None (build only)}. A composite record
{"kind": "composite", "parts": [record, ...], ...} merges several map
generations (the hikari village is land + pond + city) into one set whose
ids are prefixed with the part's map name.
Standard library only.
"""

import json
import math
import os
import sys

SPEC_FORMAT = "uzu-scene-spec/1"
GRAPH_FORMAT = "uzu-region-graph/1"
REGISTRY_FORMAT = "uzu-asset-registry/1"
REPORT_FORMAT = "uzu-validation-report/1"

FILES = {
    "scene_spec": "scene_spec.json",
    "region_graph": "region_graph.json",
    "asset_registry": "asset_registry.json",
    "validation_report": "validation_report.json",
}

BASIS = {
    "observed": "measured and reported by the generator itself (its result JSON: counts, place positions, the navigation bake, timings)",
    "inferred": "filled in or presumed without a measurement: parameters the generator defaulted, and connections presumed from the reported places",
}


# ---------------------------------------------------------------- helpers


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _dist(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _places(result):
    """[(id, center, about)] from a map result's places dict. Single places
    are {"position": [x,y,z], "about": str}; clearings/villages are lists of
    them and get indexed ids (clearings_0, ...)."""
    out = []
    places = result.get("places") or {}
    for name in sorted(places):
        entry = places[name]
        if isinstance(entry, dict) and isinstance(entry.get("position"), list):
            out.append((name, entry["position"], entry.get("about", "")))
        elif isinstance(entry, list):
            for i, item in enumerate(entry):
                if isinstance(item, dict) and isinstance(item.get("position"), list):
                    out.append((f"{name}_{i}", item["position"], item.get("about", "")))
    return out


def _mst_edges(nodes):
    """Minimum spanning tree over [(id, center)] (Prim's, deterministic:
    ties broken by (length, a, b)). Every edge is bidirectional."""
    if len(nodes) < 2:
        return []
    ids = [n[0] for n in nodes]
    centers = {n[0]: n[1] for n in nodes}
    in_tree = {ids[0]}
    edges = []
    while len(in_tree) < len(ids):
        best = None
        for a in sorted(in_tree):
            for b in ids:
                if b in in_tree:
                    continue
                cand = (_dist(centers[a], centers[b]), min(a, b), max(a, b))
                if best is None or cand < best:
                    best = cand
        length, a, b = best
        edges.append({"a": a, "b": b, "length": round(length, 3), "bidirectional": True,
                      "basis": "inferred", "length_basis": "euclidean distance between the two centers"})
        in_tree.add(a if a not in in_tree else b)
    return edges


def _defaulted_parameters(input_spec, resolved):
    """Resolved parameters the input spec did not name: the generator
    filled them from the preset/defaults, so they are inferences."""
    return [k for k in sorted(resolved) if k not in (input_spec or {})]


def _attach_spec_image_to_scene_spec(scene_spec, record):
    """Record B-1222 specification image reference and element mappings
    (distinguishing observed vs inferred) into a B-1509 scene_spec."""
    spec_image = record.get("spec_image")
    elements = record.get("elements")
    if spec_image:
        ref = {
            "id": spec_image.get("id"),
            "path": spec_image.get("path"),
        }
        if spec_image.get("registry"):
            ref["registry"] = spec_image["registry"]
        if spec_image.get("working_size"):
            ref["working_size"] = list(spec_image["working_size"])
        scene_spec["spec_image"] = ref
        if spec_image.get("width") and spec_image.get("height"):
            scene_spec["observed"].append({
                "name": "spec_image.size",
                "value": [spec_image["width"], spec_image["height"]],
                "evidence": f"specification image header ({spec_image.get('path') or spec_image.get('id')})",
            })
    if elements:
        for elem in elements:
            val = {
                "id": elem.get("id"),
                "kind": elem.get("kind"),
                "node": elem.get("node"),
                "image_bbox": list(elem.get("image_bbox") or elem.get("bbox") or []),
            }
            if elem.get("basis") == "observed":
                scene_spec["observed"].append({
                    "name": f"element.{elem.get('id')}",
                    "value": val,
                    "evidence": elem.get("evidence") or "annotated in specification image registry",
                })
            else:
                scene_spec["inferred"].append({
                    "name": f"element.{elem.get('id')}",
                    "value": val,
                    "reason": elem.get("reason") or "inferred from specification illustration",
                })


def attach_registry_to_record(record, registry, scene=None, registry_ref=None):
    """Enrich a generation record with B-1222 spec_image and element mappings
    from `registry` for `scene` (defaults to record['scene'])."""
    import spec_registry
    target_scene = scene or record.get("scene")
    if not target_scene:
        return record
    binding = spec_registry.get_scene_binding(registry, target_scene)
    if not binding:
        return record
    img = binding.get("image") or {}
    spec_image = {
        "id": binding["spec_image"],
        "path": binding.get("spec_image_path"),
        "working_size": binding.get("working_size"),
        "width": img.get("width"),
        "height": img.get("height"),
    }
    if registry_ref:
        spec_image["registry"] = registry_ref
    out = dict(record)
    out["spec_image"] = spec_image
    out["elements"] = binding.get("elements") or []
    return out


# ---------------------------------------------------------------- scene_spec


def _map_scene_spec(record):
    result = record.get("result") or {}
    input_spec = record.get("input_spec") or {}
    resolved = result.get("options") or {}
    parameters = [{"name": k, "value": resolved[k], "origin": "given" if k in input_spec else "defaulted"}
                  for k in sorted(resolved)]
    if not resolved:
        parameters = [{"name": k, "value": input_spec[k], "origin": "given"} for k in sorted(input_spec)]

    observed = []

    def obs(name, value, source):
        observed.append({"name": name, "value": value, "evidence": f"generator result {source}"})

    for key in sorted(result.get("counts") or {}):
        obs(f"counts.{key}", result["counts"][key], f"counts.{key}")
    for pid, center, _about in _places(result):
        obs(f"places.{pid}.position", center, f"places.{pid}.position")
    for key in sorted(result.get("navigation") or {}):
        obs(f"navigation.{key}", result["navigation"][key], f"navigation.{key}")
    for key in ("size", "triangles", "terrain_triangles", "cells", "height_range", "water_y",
                "water_fraction", "streets_m", "tallest_m", "roads_connected", "generate_ms",
                "scene_created", "data_files"):
        if key in result:
            obs(key, result[key], key)

    inferred = [{"name": f"parameters.{k}", "value": resolved.get(k),
                 "reason": "not in the input spec; the generator filled it from the preset/default (resolved options)"}
                for k in _defaulted_parameters(input_spec, resolved)]
    inferred.append({"name": "region_graph.edges",
                     "reason": "a minimum spanning tree over the observed place centers; the navigation bake "
                               "supports the places being on one walkable area, but no edge was walked (B-1510 does that)"})
    if record.get("kind") == "map" and result.get("kind") == "nature" and "navigation" not in result:
        inferred.append({"name": "walkability",
                         "reason": "nature maps bake no navigation mesh; nothing here asserts the terrain can be walked"})

    scene_spec = {
        "format": SPEC_FORMAT, "kind": "map", "map_kind": result.get("kind"),
        "scene": record.get("scene"), "generator": record.get("generator"),
        "spec_source": record.get("spec_source"),
        "intent": input_spec, "basis": BASIS,
        "parameters": parameters, "observed": observed, "inferred": inferred,
    }
    _attach_spec_image_to_scene_spec(scene_spec, record)
    return scene_spec


def _build_scene_spec(record):
    spec = record.get("input_spec") or {}
    built = (record.get("result") or {}).get("built") or {}
    parameters = [{"name": k, "value": spec[k], "origin": "given"} for k in sorted(spec)]
    observed = []

    def obs(name, value):
        observed.append({"name": name, "value": value, "evidence": "build result (ai_loop/build_tool.gd)"})

    for key in sorted(built):
        obs(f"built.{key}", built[key])
    inferred = [
        {"name": "region_graph.edges",
         "reason": "a minimum spanning tree over the model positions taken from the input spec; "
                   "connectivity between built objects is presumed, not measured"},
        {"name": "per-item defaults",
         "reason": "build_tool.gd fills per-item defaults (mesh 'box', scale 1, position [0,0,0], ...) "
                   "that its result does not enumerate; they are not listed as parameters"},
        {"name": "scatter positions",
         "reason": "UZUScatter chose the individual positions from the seed; the build result reports "
                   "only the count per scatter entry, so positions are not observed here"},
    ]
    scene_spec = {
        "format": SPEC_FORMAT, "kind": record.get("kind") or "build",
        "scene": record.get("scene"), "generator": record.get("generator"),
        "spec_source": record.get("spec_source"),
        "intent": spec, "basis": BASIS,
        "parameters": parameters, "observed": observed, "inferred": inferred,
    }
    _attach_spec_image_to_scene_spec(scene_spec, record)
    return scene_spec


# ---------------------------------------------------------------- region_graph


def _map_region_graph(record, prefix=""):
    result = record.get("result") or {}
    nodes = [{"id": prefix + pid, "center": center, "about": about}
             for pid, center, about in _places(result)]
    edges = _mst_edges([(n["id"], n["center"]) for n in nodes])
    notes = ["edges are a minimum spanning tree over the place centers (basis: inferred); "
             "lengths are euclidean distances between centers"]
    if result.get("navigation"):
        nav = result["navigation"]
        notes.append(f"the generator's navigation bake reports places_connected={nav.get('places_connected')} "
                     f"with {nav.get('polygons')} polygons; walking the edges is B-1510's check")
    return {"format": GRAPH_FORMAT, "scene": record.get("scene"),
            "nodes": nodes, "edges": edges, "notes": notes}


def _build_region_graph(record):
    spec = record.get("input_spec") or {}
    nodes = []
    for i, model in enumerate(spec.get("models") or []):
        if isinstance(model, dict):
            nodes.append({"id": str(model.get("name", f"Model{i}")),
                          "center": model.get("position", [0, 0, 0]),
                          "about": f"model ({model.get('mesh', 'box')})", "basis": "given"})
    if isinstance(spec.get("ground"), dict):
        nodes.append({"id": "Ground", "center": [0, 0, 0],
                      "about": f"ground {spec['ground'].get('size', [40, 40])}", "basis": "given"})
    edges = _mst_edges([(n["id"], n["center"]) for n in nodes])
    return {"format": GRAPH_FORMAT, "scene": record.get("scene"), "nodes": nodes, "edges": edges,
            "notes": ["nodes are the spec's models and ground, at their given positions (basis: given); "
                      "edges are a minimum spanning tree over them (basis: inferred)"]}


# ---------------------------------------------------------------- asset_registry

_FAMILY_NOTES = {
    "buildings": "part-based building recipe with a PBR texture set (B-1219); detail=simple in the spec gives plain boxes",
    "windows": "window parts of the buildings family (frames shared as one mesh)",
    "benches": "street furniture with collision (B-1507/B-1508)",
    "lamps": "street lamps; 'lights' counts the ones carrying a real light",
    "street_trees": "trees planted along the streets",
    "trees": "scattered trees on the terrain",
}


def _map_registry(record, part=None):
    result = record.get("result") or {}
    resolved = result.get("options") or {}
    origin = {"generator": record.get("generator"), "preset": result.get("preset"),
              "seed": result.get("seed")}
    families = []
    for key in sorted(result.get("counts") or {}):
        fam = {"family": key, "count": result["counts"][key], "count_basis": "observed", "origin": dict(origin)}
        if key in _FAMILY_NOTES:
            fam["note"] = _FAMILY_NOTES[key]
        if part:
            fam["part"] = part
        families.append(fam)
    tris = result.get("triangles", result.get("terrain_triangles"))
    if tris is not None:
        fam = {"family": "terrain_mesh" if result.get("kind") == "nature" else "meshes",
               "count": tris, "measure": "triangles", "count_basis": "observed", "origin": dict(origin)}
        if part:
            fam["part"] = part
        families.append(fam)
    if result.get("buildings_detail"):
        fam = {"family": "buildings_detail", "count": len(result["buildings_detail"]),
               "count_basis": "observed", "origin": dict(origin),
               "note": "per-building detail entries the generator reported (floors, roof, size)"}
        if part:
            fam["part"] = part
        families.append(fam)
    return families


def _build_registry(record):
    spec = record.get("input_spec") or {}
    built = (record.get("result") or {}).get("built") or {}
    origin = {"generator": record.get("generator"), "spec": record.get("spec_source")}
    families = []
    if isinstance(spec.get("ground"), dict):
        families.append({"family": "ground", "count": 1, "count_basis": "observed", "origin": dict(origin),
                         "note": f"plane {spec['ground'].get('size', [40, 40])}"})
    models = [m for m in spec.get("models") or [] if isinstance(m, dict)]
    if "models" in built:
        families.append({"family": "models", "count": built["models"], "count_basis": "observed", "origin": dict(origin)})
    by_mesh = {}
    for m in models:
        by_mesh[str(m.get("mesh", "box"))] = by_mesh.get(str(m.get("mesh", "box")), 0) + 1
    for mesh in sorted(by_mesh):
        families.append({"family": f"models:{mesh}", "count": by_mesh[mesh], "count_basis": "given",
                         "origin": dict(origin), "note": "split by mesh from the input spec; the total above is the observed one"})
    for i, entry in enumerate(built.get("scatter") or []):
        sspec = (spec.get("scatter") or [{}])[i] if i < len(spec.get("scatter") or []) else {}
        families.append({"family": f"scatter:{sspec.get('mesh', 'sphere')}", "count": entry.get("count"),
                         "target": entry.get("target"), "count_basis": "observed",
                         "origin": {**origin, "seed": sspec.get("seed")},
                         "note": f"UZUScatter node {entry.get('node')}"})
    for key in ("cards", "markers", "lamps", "particles", "water", "godrays"):
        if key in built:
            families.append({"family": key, "count": built[key], "count_basis": "observed", "origin": dict(origin)})
    return families


# ---------------------------------------------------------------- validation_report


def _check(cid, claim, status, holds, evidence):
    if not evidence:
        status, holds = "Unverified", None
        evidence = [{"type": "value", "ref": "evidence", "value": None,
                     "note": "no evidence could be attached to this check"}]
    return {"id": cid, "claim": claim, "status": status, "holds": holds, "evidence": evidence}


def _val(ref, value, note=None):
    e = {"type": "value", "ref": ref, "value": value}
    if note:
        e["note"] = note
    return e


def _file(ref):
    return {"type": "file", "ref": ref}


def _map_checks(record):
    result = record.get("result") or {}
    checks = []
    ok = bool(result.get("ok"))
    checks.append(_check("generation_succeeded", "the generator reported success and the scene was saved",
                         "Verified" if ok else "Partial", ok,
                         [_val("result.ok", ok), _file(record.get("scene") or "")]))
    counts = result.get("counts") or {}
    checks.append(_check("counts_reported", "the generator reported how many of each part it placed",
                         "Verified" if counts else "Unverified", bool(counts) or None,
                         [_val("result.counts (keys)", len(counts)),
                          _val("result.counts (total items)", sum(v for v in counts.values() if _num(v) is not None))]))
    nodes = _places(result)
    checks.append(_check("places_reported", "the generator named the places of the map, with positions",
                         "Verified" if nodes else "Unverified", bool(nodes) or None,
                         [_val("result.places (nodes)", len(nodes))]))
    nav = result.get("navigation")
    if nav is not None:
        polys = nav.get("polygons") or 0
        checks.append(_check("navigation_baked", "a navigation mesh was baked for the map",
                             "Verified" if polys > 0 else "Partial", polys > 0,
                             [_val("result.navigation.polygons", polys),
                              _val("result.navigation.vertices", nav.get("vertices")),
                              _val("result.navigation.islands", nav.get("islands"))]))
        connected = nav.get("places_connected")
        unreached = nav.get("unreached") or []
        if connected is True and not unreached:
            status, holds = "Verified", True
        elif connected is None:
            status, holds = "Unverified", None
        else:
            status, holds = "Verified", bool(connected) and not unreached
        checks.append(_check("places_connected", "every named place is on one walkable navigation area",
                             status, holds,
                             [_val("result.navigation.places_connected", connected),
                              _val("result.navigation.unreached", unreached)]))
    if "roads_connected" in result:
        checks.append(_check("roads_connected", "every village is reachable from every other by road",
                             "Verified", bool(result["roads_connected"]),
                             [_val("result.roads_connected", result["roads_connected"]),
                              _val("result.counts.roads", (result.get("counts") or {}).get("roads"))]))
    checks.append(_check("collision_coverage", "the placed parts carry collision",
                         "Unverified", None,
                         [_val("result (collision summary)", None,
                               "the generator result carries no per-part collision summary; "
                               "B-1511 re-reads the saved scene to audit this")]))
    checks.append(_check("walk_reachability", "every region_graph edge can actually be walked, both ways",
                         "Unverified", None,
                         [_file("region_graph.json"),
                          _val("edges", len(_mst_edges([(p[0], p[1]) for p in nodes])),
                               "static spec set only; B-1510 walks the graph and reports per-edge results")]))
    return checks


def _build_checks(record):
    result = record.get("result") or {}
    spec = record.get("input_spec") or {}
    built = result.get("built") or {}
    report = record.get("report")
    checks = []
    ok = bool(result.get("ok"))
    checks.append(_check("scene_saved", "the build reported success and the scene was saved",
                         "Verified" if ok else "Partial", ok,
                         [_val("result.ok", ok), _file(record.get("scene") or "")]))
    models = [m for m in spec.get("models") or [] if isinstance(m, dict)]
    if models:
        placed = built.get("models")
        same = placed == len(models)
        checks.append(_check("models_placed", "every model in the spec was placed",
                             "Verified" if same else "Partial", same,
                             [_val("spec.models", len(models)), _val("result.built.models", placed)]))
    for i, entry in enumerate(built.get("scatter") or []):
        count, target = entry.get("count"), entry.get("target")
        if count is not None and target:
            full = count >= target
            checks.append(_check(f"scatter_placed_{i}", f"scatter entry {i} reached its target count",
                                 "Verified" if full else "Partial", full,
                                 [_val(f"result.built.scatter[{i}].count", count),
                                  _val(f"result.built.scatter[{i}].target", target)]))
    if report is not None:
        failures = report.get("failures") or []
        rok = bool(report.get("ok")) and not failures
        checks.append(_check("richness_report", "the built scene passes its richness report",
                             "Verified" if rok else "Partial", rok,
                             [_val("report.ok", report.get("ok")), _val("report.failures", failures),
                              _val("report.summary", report.get("summary"))]))
    else:
        checks.append(_check("richness_report", "the built scene passes its richness report",
                             "Unverified", None,
                             [_val("report", None, "no report was attached (build --no-report, or the set was made outside uzu.py build)")]))
    checks.append(_check("walk_reachability", "every region_graph edge can actually be walked, both ways",
                         "Unverified", None,
                         [_file("region_graph.json"),
                          _val("edges", len(_build_region_graph(record)["edges"]),
                               "a built scene has no navigation bake; walking it is B-1510's / the AI player's check")]))
    return checks


def _summary(checks):
    out = {"Verified": 0, "Partial": 0, "Unverified": 0}
    for c in checks:
        out[c["status"]] += 1
    return out


def _report(scene, checks):
    return {"format": REPORT_FORMAT, "scene": scene, "checks": checks, "summary": _summary(checks)}


# ---------------------------------------------------------------- assembly


def build_spec_set(record):
    """One generation record -> the four documents (a dict of dicts)."""
    kind = record.get("kind")
    if kind == "composite":
        return _composite_spec_set(record)
    if kind == "map":
        return {
            "scene_spec": _map_scene_spec(record),
            "region_graph": _map_region_graph(record),
            "asset_registry": {"format": REGISTRY_FORMAT, "scene": record.get("scene"),
                               "families": _map_registry(record)},
            "validation_report": _report(record.get("scene"), _map_checks(record)),
        }
    if kind in ("build", "image_scene"):
        return {
            "scene_spec": _build_scene_spec(record),
            "region_graph": _build_region_graph(record),
            "asset_registry": {"format": REGISTRY_FORMAT, "scene": record.get("scene"),
                               "families": _build_registry(record)},
            "validation_report": _report(record.get("scene"), _build_checks(record)),
        }
    raise ValueError(f"unknown record kind {kind!r} (want map, build, image_scene or composite)")


def _composite_spec_set(record):
    parts = record.get("parts") or []
    specs, graphs, families, checks = [], [], [], []
    all_ok = True
    for part in parts:
        result = part.get("result") or {}
        name = str((part.get("input_spec") or {}).get("name") or result.get("node") or "part")
        all_ok = all_ok and bool(result.get("ok"))
        sub = build_spec_set(part)
        specs.append({"part": name, **{k: sub["scene_spec"][k] for k in
                                       ("map_kind", "intent", "parameters", "observed", "inferred")}})
        prefix = f"{name}__"
        graph = _map_region_graph(part, prefix=prefix)
        graphs.append(graph)
        families.extend(_map_registry(part, part=name))
        for c in _map_checks(part):
            checks.append({**c, "id": f"{name}__{c['id']}"})
    nodes = [n for g in graphs for n in g["nodes"]]
    edges = [e for g in graphs for e in g["edges"]]
    checks.insert(0, _check("generation_succeeded", "every part of the composite reported success",
                            "Verified" if all_ok else "Partial", all_ok,
                            [_val("parts", [p.get("result", {}).get("ok") for p in parts]),
                             _file(record.get("scene") or "")]))
    checks.append(_check("cross_part_reachability", "a walker can travel between the parts of the composite",
                         "Unverified", None,
                         [_val("parts", len(parts),
                               "the parts were generated independently and no cross-part navigation was baked; "
                               "B-1510 / the game's own playthrough checks this")]))
    scene_spec = {
        "format": SPEC_FORMAT, "kind": "composite",
        "scene": record.get("scene"), "generator": record.get("generator"),
        "spec_source": record.get("spec_source"), "basis": BASIS,
        "context": record.get("context"),
        "parts": specs,
        "inferred": [{"name": "region_graph.cross_part_edges",
                      "reason": "no edges between parts are asserted: each part's places were reported in its own "
                                "generation, and cross-part walkability was not measured"}],
    }
    region_graph = {"format": GRAPH_FORMAT, "scene": record.get("scene"), "nodes": nodes, "edges": edges,
                    "notes": ["edges join places within one part only (minimum spanning tree per part, basis: inferred); "
                              "node ids are prefixed with the part's map name"]}
    return {
        "scene_spec": scene_spec,
        "region_graph": region_graph,
        "asset_registry": {"format": REGISTRY_FORMAT, "scene": record.get("scene"), "families": families},
        "validation_report": _report(record.get("scene"), checks),
    }


def write_spec_set(bundle, out_dir):
    """Writes the four documents into out_dir; returns {"dir", "files"}."""
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for key, filename in FILES.items():
        path = os.path.join(out_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bundle[key], f, ensure_ascii=False, indent=2, sort_keys=False)
            f.write("\n")
        files[key] = path
    return {"dir": out_dir, "files": files}


def spec_set_from_record(record, out_dir):
    return write_spec_set(build_spec_set(record), out_dir)


def main(argv):
    record_path = out_dir = registry_path = scene_ref = None
    i = 0
    while i < len(argv):
        if argv[i] == "--record" and i + 1 < len(argv):
            record_path, i = argv[i + 1], i + 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out_dir, i = argv[i + 1], i + 2
        elif argv[i] == "--registry" and i + 1 < len(argv):
            registry_path, i = argv[i + 1], i + 2
        elif argv[i] == "--scene" and i + 1 < len(argv):
            scene_ref, i = argv[i + 1], i + 2
        else:
            i += 1
    if not record_path or not out_dir:
        print(json.dumps({"ok": False, "error": "usage: spec_set.py --record record.json --out DIR [--registry REG --scene res://...]"}))
        return 1
    with open(record_path, encoding="utf-8") as f:
        record = json.load(f)
    if registry_path:
        import spec_registry
        reg = spec_registry.load_registry(registry_path)
        record = attach_registry_to_record(record, reg, scene=scene_ref, registry_ref=os.path.basename(registry_path))
    written = spec_set_from_record(record, out_dir)
    print(json.dumps({"ok": True, "spec_set": written}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
