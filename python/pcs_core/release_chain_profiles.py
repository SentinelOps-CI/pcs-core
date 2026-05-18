"""Release-chain profile detection for multi-domain PCS fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LABTRUST_WORKFLOW_PROFILE_ID = "labtrust.qc_release_v0.1"
TOOL_USE_WORKFLOW_PROFILE_ID = "agent_tool_use.safety_v0"
COMPUTATION_WORKFLOW_PROFILE_ID = "scientific_computation.reproducibility_v0"

TOOL_USE_TRACE_NAMES = ("tool_use_trace.valid.json", "tool_use_trace.json")
TOOL_USE_CERTIFICATE_NAMES = ("tool_use_certificate.valid.json", "tool_use_certificate.json")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def resolve_tool_use_artifact(directory: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = directory / name
        if path.is_file():
            return path
    return None


def detect_workflow_profile_id(directory: Path) -> str | None:
    profile_path = directory / "workflow_profile.v0.json"
    profile = _load_json(profile_path)
    if profile:
        workflow_id = profile.get("workflow_id")
        if isinstance(workflow_id, str) and workflow_id:
            return workflow_id
    manifest_v0 = _load_json(directory / "release_manifest.v0.json")
    if manifest_v0:
        workflow_id = manifest_v0.get("workflow_profile_id")
        if isinstance(workflow_id, str) and workflow_id:
            return workflow_id
    legacy_manifest = _load_json(directory / "RELEASE_FIXTURE_MANIFEST.json")
    if legacy_manifest:
        workflow_id = legacy_manifest.get("workflow_profile_id")
        if isinstance(workflow_id, str) and workflow_id:
            return workflow_id
    if resolve_tool_use_artifact(directory, TOOL_USE_TRACE_NAMES):
        return TOOL_USE_WORKFLOW_PROFILE_ID
    if (directory / "computation_witness.json").is_file():
        return COMPUTATION_WORKFLOW_PROFILE_ID
    if (directory / "trace.json").is_file():
        return LABTRUST_WORKFLOW_PROFILE_ID
    return None


def is_tool_use_release_directory(directory: Path) -> bool:
    return detect_workflow_profile_id(directory) == TOOL_USE_WORKFLOW_PROFILE_ID


def is_computation_release_directory(directory: Path) -> bool:
    return detect_workflow_profile_id(directory) == COMPUTATION_WORKFLOW_PROFILE_ID
