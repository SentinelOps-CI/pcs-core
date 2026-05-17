"""PCS ArtifactRegistry.v0 loading and CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.paths import examples_dir, schemas_dir
from pcs_core.registry_data import registry_entries
from pcs_core.validate import ValidationError, detect_artifact_type, validate_artifact

REGISTRY_ID = "pcs-artifact-registry-v0.1"
REGISTRY_VERSION = "0.1.0"


def build_artifact_registry() -> dict[str, Any]:
    body = {
        "schema_version": "v0",
        "registry_id": REGISTRY_ID,
        "registry_version": REGISTRY_VERSION,
        "entries": registry_entries(),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body


def default_registry_path() -> Path:
    return examples_dir() / "artifact_registry.valid.json"


def load_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_registry_path()
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"{registry_path}: registry root must be an object")
    validate_artifact(data, "ArtifactRegistry.v0")
    return data


def list_artifact_types(registry: dict[str, Any] | None = None) -> list[str]:
    reg = registry or load_registry()
    entries = reg.get("entries")
    if not isinstance(entries, dict):
        return []
    return sorted(entries.keys())


def explain_artifact_type(
    artifact_type: str, registry: dict[str, Any] | None = None
) -> dict[str, Any]:
    reg = registry or load_registry()
    entries = reg.get("entries")
    if not isinstance(entries, dict) or artifact_type not in entries:
        raise ValidationError(f"Unknown registry artifact type: {artifact_type}")
    return dict(entries[artifact_type])


def validate_registry_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = load_registry(path)
    except ValidationError as exc:
        return [str(exc), *exc.errors]
    canonical = build_artifact_registry()
    expected_types = set(canonical["entries"].keys())
    actual_types = set(data.get("entries", {}).keys())
    missing = sorted(expected_types - actual_types)
    extra = sorted(actual_types - expected_types)
    if missing:
        errors.append(f"registry missing entries: {missing}")
    if extra:
        errors.append(f"registry unexpected entries: {extra}")
    for artifact_type in sorted(expected_types & actual_types):
        expected = canonical["entries"][artifact_type]
        actual = data["entries"][artifact_type]
        if actual != expected:
            errors.append(f"registry entry drift for {artifact_type}")
    return errors


def check_artifact_against_registry(
    path: Path, registry: dict[str, Any] | None = None
) -> list[str]:
    errors: list[str] = []
    reg = registry or load_registry()
    entries = reg.get("entries")
    if not isinstance(entries, dict):
        return ["registry entries must be an object"]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return [f"{path}: artifact root must be an object"]
    artifact_type = detect_artifact_type(data)
    if not artifact_type:
        return [f"{path}: could not detect artifact type"]
    if artifact_type not in entries:
        errors.append(f"{path}: artifact type {artifact_type} not in registry")
        return errors
    entry = entries[artifact_type]
    try:
        validate_artifact(data, artifact_type)
    except ValidationError as exc:
        errors.extend(exc.errors)
    status = data.get("status")
    allowed = entry.get("allowed_statuses")
    if isinstance(status, str) and isinstance(allowed, list) and status not in allowed:
        errors.append(f"{path}: status {status!r} not in registry allowed_statuses")
    required = entry.get("required_release_fields")
    if isinstance(required, list):
        for field in required:
            if field not in data:
                errors.append(f"{path}: missing required release field {field}")
    schema_name = entry.get("schema")
    if isinstance(schema_name, str):
        schema_path = schemas_dir() / Path(schema_name).name
        if not schema_path.is_file():
            errors.append(f"{path}: registry schema file missing: {schema_name}")
    return errors
