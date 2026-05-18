"""PCS ArtifactRegistry.v0 loading and CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.paths import examples_dir, schemas_dir
from pcs_core.registry_data import registry_entries
from pcs_core.registry_semantics import enrich_semantic_check
from pcs_core.registry_semantics import audit_registry_catalog
from pcs_core.validate import ValidationError, detect_artifact_type, validate_artifact

REGISTRY_ID = "pcs-artifact-registry-v0.1"
REGISTRY_VERSION = "0.1.0"


def build_artifact_registry() -> dict[str, Any]:
    entries: dict[str, Any] = {}
    for key, entry in registry_entries().items():
        copy = dict(entry)
        checks = copy.get("semantic_checks")
        if isinstance(checks, list):
            copy["semantic_checks"] = [enrich_semantic_check(dict(c)) for c in checks]
        entries[key] = copy
    body = {
        "schema_version": "v0",
        "registry_id": REGISTRY_ID,
        "registry_version": REGISTRY_VERSION,
        "entries": entries,
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


def validate_registry_file(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(audit_registry_catalog())
    try:
        data = load_registry(path)
    except ValidationError as exc:
        return [str(exc), *exc.errors], warnings
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
    warnings.extend(audit_registry_producer_fields(data))
    return errors, warnings


def audit_registry_producer_fields(registry: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    entries = registry.get("entries")
    if not isinstance(entries, dict):
        return warnings
    for artifact_type, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        producer = entry.get("producer")
        runtime_producer = entry.get("runtime_producer")
        if (
            isinstance(producer, str)
            and isinstance(runtime_producer, str)
            and producer != runtime_producer
        ):
            warnings.append(
                f"registry warning: entries.{artifact_type}.producer ({producer!r}) "
                f"differs from runtime_producer ({runtime_producer!r}); "
                "producer is deprecated — use runtime_producer",
            )
    return warnings


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
    producer = str(data.get("producer") or "")
    allowed_producers = entry.get("allowed_runtime_producers")
    runtime_producer = str(entry.get("runtime_producer") or entry.get("producer") or "")
    if producer and isinstance(allowed_producers, list):
        if producer not in allowed_producers:
            errors.append(
                f"{path}: producer {producer!r} not in registry "
                f"allowed_runtime_producers {allowed_producers!r}",
            )
    elif producer and runtime_producer and producer != runtime_producer:
        errors.append(
            f"{path}: warning: artifact producer {producer!r} differs from registry "
            f"runtime_producer {runtime_producer!r} (legacy producer field is deprecated)",
        )
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
