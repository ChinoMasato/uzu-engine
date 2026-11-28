"""Unified input path resolution for ai_loop / uzu.py (B-1225).

Resolution order for an input path against `project`:
  1. res://... -> resolved inside `project` (escaping `project` raises PathResolutionError).
  2. Absolute path -> used as-is.
  3. Relative path -> project-relative first (if it exists), then CWD-relative fallback.
  4. If neither exists (and `must_exist=True`), raise PathResolutionError listing both candidates.
When `must_exist=False`, non-existent relative paths resolve project-relative.
"""

import os


class PathResolutionError(ValueError):
    """Raised when an input path cannot be resolved or escapes the project."""


def resolve_input_path(project, value, *, must_exist=True):
    """Resolve an input path to {'path': <abs>, 'via': 'res'|'absolute'|'project'|'cwd'}."""
    if not isinstance(value, str) or not value.strip():
        raise PathResolutionError("input path must be a non-empty string")
    if "\0" in value:
        raise PathResolutionError("input path must not contain null bytes")

    project_abs = os.path.abspath(project)

    if value.startswith("res://"):
        rel = value[len("res://"):].lstrip("/").replace("/", os.sep)
        resolved = os.path.abspath(os.path.join(project_abs, rel))
        try:
            common = os.path.commonpath([project_abs, resolved])
        except ValueError:
            common = ""
        if common != project_abs:
            raise PathResolutionError(f"res:// path escapes project: {value}")
        if must_exist and not os.path.exists(resolved):
            raise PathResolutionError(f"input not found: {value!r} (tried res: {resolved})")
        return {"path": resolved, "via": "res"}

    if os.path.isabs(value):
        resolved = os.path.abspath(value)
        if must_exist and not os.path.exists(resolved):
            raise PathResolutionError(f"input not found: {value!r} (tried absolute: {resolved})")
        return {"path": resolved, "via": "absolute"}

    rel = value.replace("/", os.sep)
    project_cand = os.path.abspath(os.path.join(project_abs, rel))
    cwd_cand = os.path.abspath(rel)

    if os.path.exists(project_cand):
        return {"path": project_cand, "via": "project"}
    if os.path.exists(cwd_cand):
        return {"path": cwd_cand, "via": "cwd"}
    if not must_exist:
        return {"path": project_cand, "via": "project"}
    raise PathResolutionError(
        f"input not found: {value!r} (tried project: {project_cand}; cwd: {cwd_cand})"
    )
