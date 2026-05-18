"""WorkflowProfile.v0 loading for profile-scoped validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.paths import examples_dir
from pcs_core.registry import registry_entries
from pcs_core.registry_semantics import collect_required_release_blocking_refs_for_artifact_types


def workflow_profiles_dir() -> Path:
    return examples_dir() / "workflow_profiles"


def load_workflow_profile(workflow_id: str) -> dict[str, Any] | None:
    for path in workflow_profiles_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("workflow_id") == workflow_id:
            return data
    for release_name in ("tool-use-release", "computation-release"):
        release_profile = examples_dir() / release_name / "workflow_profile.v0.json"
        if release_profile.is_file():
            data = json.loads(release_profile.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("workflow_id") == workflow_id:
                return data
    return None


def audit_workflow_profile_files() -> list[str]:
    """Ensure checked-in workflow profiles reference only registered artifact types."""
    errors: list[str] = []
    known_types = set(registry_entries().keys())
    for path in sorted(workflow_profiles_dir().glob("*.valid.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{path.name}: root must be an object")
            continue
        workflow_id = data.get("workflow_id")
        for field in ("runtime_artifacts", "certificate_artifacts", "required_registry_entries"):
            values = data.get(field)
            if not isinstance(values, list):
                continue
            for artifact_type in values:
                if isinstance(artifact_type, str) and artifact_type not in known_types:
                    errors.append(
                        f"{path.name}: {field} references unknown type {artifact_type!r}",
                    )
        required = data.get("required_registry_entries")
        if isinstance(required, list) and "WorkflowProfile.v0" not in required:
            errors.append(
                f"{path.name}: required_registry_entries must include WorkflowProfile.v0",
            )
        if workflow_id == "agent_tool_use.safety_v0":
            for artifact_type in ("ToolUseTrace.v0", "ToolUseCertificate.v0"):
                if isinstance(required, list) and artifact_type not in required:
                    errors.append(
                        f"{path.name}: tool-use profile must require {artifact_type}",
                    )
        if workflow_id == "scientific_computation.reproducibility_v0":
            for artifact_type in (
                "DatasetReceipt.v0",
                "EnvironmentReceipt.v0",
                "ComputationRunReceipt.v0",
                "ResultArtifact.v0",
                "ComputationWitness.v0",
            ):
                if isinstance(required, list) and artifact_type not in required:
                    errors.append(
                        f"{path.name}: computation profile must require {artifact_type}",
                    )
    return errors


def required_release_blocking_refs_for_profile(workflow_profile_id: str | None) -> set[str]:
    if not workflow_profile_id:
        from pcs_core.registry_semantics import collect_required_release_blocking_refs

        return collect_required_release_blocking_refs()
    profile = load_workflow_profile(workflow_profile_id)
    if profile is None:
        from pcs_core.registry_semantics import collect_required_release_blocking_refs

        return collect_required_release_blocking_refs()
    entries = profile.get("required_registry_entries")
    if not isinstance(entries, list):
        from pcs_core.registry_semantics import collect_required_release_blocking_refs

        return collect_required_release_blocking_refs()
    return collect_required_release_blocking_refs_for_artifact_types(set(entries))
