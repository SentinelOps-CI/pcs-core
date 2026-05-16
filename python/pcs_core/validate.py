"""JSON Schema and semantic validation for PCS artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from pcs_core.artifact import ARTIFACT_SCHEMAS, detect_artifact_type, schemas_dir


class ValidationError(Exception):
    """Raised when artifact validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


def _load_schema(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_registry() -> Registry:
    schema_root = schemas_dir()
    resources: list[tuple[str, Resource]] = []
    for path in sorted(schema_root.glob("*.json")):
        schema = _load_schema(path)
        for key in ("$id",):
            schema_id = schema.get(key)
            if schema_id:
                resources.append(
                    (schema_id, Resource.from_contents(schema, default_specification=DRAFT202012))
                )
            # Also register by filename for relative $ref resolution
            file_uri = path.as_uri()
            resources.append(
                (file_uri, Resource.from_contents(schema, default_specification=DRAFT202012))
            )
            resources.append(
                (path.name, Resource.from_contents(schema, default_specification=DRAFT202012))
            )
    return Registry().with_resources(resources)


_REGISTRY: Registry | None = None


def get_registry() -> Registry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_registry()
    return _REGISTRY


def get_validator(artifact_type: str) -> Draft202012Validator:
    schema_name = ARTIFACT_SCHEMAS.get(artifact_type)
    if not schema_name:
        raise ValidationError(f"Unknown artifact type: {artifact_type}")
    schema_path = schemas_dir() / schema_name
    schema = _load_schema(schema_path)
    registry = get_registry()
    return Draft202012Validator(schema, registry=registry)


def validate_schema(data: dict[str, Any], artifact_type: str) -> list[str]:
    validator = get_validator(artifact_type)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [e.message for e in errors]


def validate_semantics(data: dict[str, Any], artifact_type: str) -> list[str]:
    errors: list[str] = []

    if artifact_type == "ClaimArtifact.v0":
        ref = data.get("assumption_set_ref")
        if not ref or not str(ref).strip():
            errors.append("ClaimArtifact.v0 requires non-empty assumption_set_ref")

    if artifact_type == "ScienceClaimBundle.v0":
        claim = data.get("claim_artifact", {})
        assumption = data.get("assumption_set", {})
        if not claim.get("assumption_set_ref"):
            errors.append("ScienceClaimBundle claim_artifact missing assumption_set_ref")
        elif claim.get("assumption_set_ref") != assumption.get("assumption_set_id"):
            errors.append(
                "claim_artifact.assumption_set_ref must match assumption_set.assumption_set_id"
            )

        receipts = data.get("runtime_receipts", [])
        certificates = data.get("certificates", [])
        for receipt in receipts:
            r_hash = receipt.get("trace_hash")
            for cert in certificates:
                c_hash = cert.get("trace_hash")
                if r_hash and c_hash and r_hash != c_hash:
                    errors.append(
                        f"trace_hash mismatch: receipt {receipt.get('receipt_id')} "
                        f"({r_hash}) vs certificate {cert.get('certificate_id')} ({c_hash})"
                    )

    return errors


def validate_artifact(data: dict[str, Any], artifact_type: str | None = None) -> None:
    artifact_type = artifact_type or detect_artifact_type(data)
    if not artifact_type:
        raise ValidationError("Could not detect artifact type from JSON content")

    schema_errors = validate_schema(data, artifact_type)
    semantic_errors = validate_semantics(data, artifact_type)
    all_errors = schema_errors + semantic_errors
    if all_errors:
        raise ValidationError(
            f"Validation failed for {artifact_type}",
            errors=all_errors,
        )


def validate_file(path: Path | str) -> str:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValidationError("Artifact root must be a JSON object")
    artifact_type = detect_artifact_type(data)
    if not artifact_type:
        raise ValidationError(f"Could not detect artifact type in {path}")
    validate_artifact(data, artifact_type)
    return artifact_type


def check_all_schemas() -> None:
    for artifact_type, schema_name in ARTIFACT_SCHEMAS.items():
        schema_path = schemas_dir() / schema_name
        schema = _load_schema(schema_path)
        Draft202012Validator.check_schema(schema)
        # Ensure validator can be constructed with cross-file refs
        get_validator(artifact_type)


def check_valid_examples(examples_dir: Path | None = None) -> None:
    examples_dir = examples_dir or (schemas_dir().parent / "examples")
    for path in sorted(examples_dir.glob("*.valid.json")):
        validate_file(path)


def check_invalid_examples(examples_dir: Path | None = None) -> None:
    examples_dir = examples_dir or (schemas_dir().parent / "examples")
    invalid_cases = {
        "invalid_unknown_status.json": "RuntimeReceipt.v0",
        "invalid_missing_assumption_set.json": "ClaimArtifact.v0",
        "invalid_mismatched_trace_hash.json": "ScienceClaimBundle.v0",
    }
    for filename, artifact_type in invalid_cases.items():
        path = examples_dir / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        schema_errors = validate_schema(data, artifact_type)
        semantic_errors = validate_semantics(data, artifact_type)
        if not schema_errors and not semantic_errors:
            raise ValidationError(f"Expected {filename} to fail validation")
