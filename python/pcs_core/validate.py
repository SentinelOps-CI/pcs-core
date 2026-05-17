"""JSON Schema and semantic validation for PCS artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from pcs_core.paths import examples_dir as default_examples_dir
from pcs_core.paths import schemas_dir
from pcs_core.status import ARTIFACT_STATUSES, TRACE_CERTIFICATE_STATUSES

ARTIFACT_SCHEMAS: dict[str, str] = {
    "AssumptionSet.v0": "AssumptionSet.v0.schema.json",
    "SourceSpan.v0": "SourceSpan.v0.schema.json",
    "ClaimArtifact.v0": "ClaimArtifact.v0.schema.json",
    "RuntimeReceipt.v0": "RuntimeReceipt.v0.schema.json",
    "TraceCertificate.v0": "TraceCertificate.v0.schema.json",
    "EvidenceBundle.v0": "EvidenceBundle.v0.schema.json",
    "ScienceClaimBundle.v0": "ScienceClaimBundle.v0.schema.json",
    "VerificationResult.v0": "VerificationResult.v0.schema.json",
    "SignedScienceClaimBundle.v0": "SignedScienceClaimBundle.v0.schema.json",
}

CERTIFIED_CLAIM_STATUSES = frozenset(
    {
        "CertificateChecked",
        "ProofChecked",
        "RuntimeChecked",
    }
)

_ZERO_COMMIT_RE = re.compile(r"^0+$")


class ValidationError(Exception):
    """Raised when artifact validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


def detect_artifact_type(data: dict[str, Any]) -> str | None:
    if "signed_bundle_id" in data and "science_claim_bundle" in data:
        return "SignedScienceClaimBundle.v0"
    if "bundle_id" in data and "claim_artifact" in data:
        return "ScienceClaimBundle.v0"
    if "verification_id" in data:
        return "VerificationResult.v0"
    if "receipt_id" in data:
        return "RuntimeReceipt.v0"
    if "certificate_id" in data:
        return "TraceCertificate.v0"
    if "assumption_set_id" in data:
        return "AssumptionSet.v0"
    if "source_span_id" in data:
        return "SourceSpan.v0"
    if data.get("artifact_type") == "ClaimArtifact.v0":
        return "ClaimArtifact.v0"
    if "bundle_id" in data and "claim_refs" in data:
        return "EvidenceBundle.v0"
    return None


def _load_schema(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_registry() -> Registry:
    schema_root = schemas_dir()
    resources: list[tuple[str, Resource]] = []
    for path in sorted(schema_root.glob("*.json")):
        schema = _load_schema(path)
        schema_id = schema.get("$id")
        if schema_id:
            resources.append(
                (schema_id, Resource.from_contents(schema, default_specification=DRAFT202012))
            )
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
    return Draft202012Validator(schema, registry=get_registry())


def validate_schema(data: dict[str, Any], artifact_type: str) -> list[str]:
    validator = get_validator(artifact_type)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [e.message for e in errors]


def _is_zero_source_commit(value: str) -> bool:
    return bool(_ZERO_COMMIT_RE.match(value.strip()))


def _local_dev_enabled(obj: dict[str, Any], inherited: bool) -> bool:
    if inherited:
        return True
    if obj.get("local_dev") is True:
        return True
    return False


def _check_source_commits(
    obj: Any,
    path: str,
    errors: list[str],
    *,
    inherited_local_dev: bool = False,
) -> None:
    if isinstance(obj, dict):
        local_dev = _local_dev_enabled(obj, inherited_local_dev)
        commit = obj.get("source_commit")
        if isinstance(commit, str) and _is_zero_source_commit(commit) and not local_dev:
            errors.append(
                f"{path or 'root'}: zero source_commit not allowed without local_dev=true"
            )
        for key, value in obj.items():
            child = f"{path}.{key}" if path else key
            _check_source_commits(value, child, errors, inherited_local_dev=local_dev)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _check_source_commits(
                item,
                f"{path}[{index}]",
                errors,
                inherited_local_dev=inherited_local_dev,
            )


def _validate_status_fields(obj: Any, path: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        if "check_id" not in obj:
            status = obj.get("status")
            if isinstance(status, str):
                if "certificate_id" in obj:
                    if status not in TRACE_CERTIFICATE_STATUSES:
                        errors.append(f"{path}: invalid TraceCertificate status {status!r}")
                elif status not in ARTIFACT_STATUSES:
                    errors.append(f"{path}: unknown status {status!r}")
        for key, value in obj.items():
            child = f"{path}.{key}" if path else key
            _validate_status_fields(value, child, errors)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _validate_status_fields(item, f"{path}[{index}]", errors)


def _validate_science_claim_bundle(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    assumption_set = data.get("assumption_set")
    if not isinstance(assumption_set, dict):
        errors.append("ScienceClaimBundle.v0 requires assumption_set")
    else:
        assumptions = assumption_set.get("assumptions")
        if not assumptions:
            errors.append("ScienceClaimBundle.v0 requires non-empty assumption_set.assumptions")

    receipts = data.get("runtime_receipts")
    if not isinstance(receipts, list) or len(receipts) == 0:
        errors.append("ScienceClaimBundle.v0 requires non-empty runtime_receipts")

    claim = data.get("claim_artifact")
    if isinstance(claim, dict):
        ref = claim.get("assumption_set_ref")
        if not ref or not str(ref).strip():
            errors.append("claim_artifact requires non-empty assumption_set_ref")
        elif isinstance(assumption_set, dict):
            if ref != assumption_set.get("assumption_set_id"):
                errors.append(
                    "claim_artifact.assumption_set_ref must match assumption_set.assumption_set_id"
                )

    certificates = data.get("certificates")
    if not isinstance(certificates, list):
        certificates = []

    claim_status = str(claim.get("status") or "") if isinstance(claim, dict) else ""
    if claim_status in CERTIFIED_CLAIM_STATUSES and len(certificates) == 0:
        errors.append("certified ScienceClaimBundle requires at least one TraceCertificate")

    if isinstance(receipts, list):
        for receipt in receipts:
            if not isinstance(receipt, dict):
                continue
            r_hash = receipt.get("trace_hash")
            for cert in certificates:
                if not isinstance(cert, dict):
                    continue
                c_status = str(cert.get("status") or "")
                if c_status and c_status not in TRACE_CERTIFICATE_STATUSES:
                    errors.append(
                        f"TraceCertificate {cert.get('certificate_id')}: "
                        f"invalid status {c_status!r}"
                    )
                c_hash = cert.get("trace_hash")
                if r_hash and c_hash and r_hash != c_hash:
                    errors.append(
                        f"trace_hash mismatch: receipt {receipt.get('receipt_id')} "
                        f"({r_hash}) vs certificate {cert.get('certificate_id')} ({c_hash})"
                    )

    return errors


def _validate_signed_bundle(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scb = data.get("science_claim_bundle")
    if isinstance(scb, dict):
        errors.extend(_validate_science_claim_bundle(scb))
    vr = data.get("verification_result")
    if isinstance(vr, dict):
        _validate_status_fields(vr, "verification_result", errors)
    return errors


def validate_semantics(data: dict[str, Any], artifact_type: str) -> list[str]:
    errors: list[str] = []

    _check_source_commits(data, "", errors)
    _validate_status_fields(data, "", errors)

    if artifact_type == "ClaimArtifact.v0":
        ref = data.get("assumption_set_ref")
        if not ref or not str(ref).strip():
            errors.append("ClaimArtifact.v0 requires non-empty assumption_set_ref")

    if artifact_type == "ScienceClaimBundle.v0":
        errors.extend(_validate_science_claim_bundle(data))

    if artifact_type == "SignedScienceClaimBundle.v0":
        errors.extend(_validate_signed_bundle(data))

    if artifact_type == "TraceCertificate.v0":
        status = str(data.get("status") or "")
        if status and status not in TRACE_CERTIFICATE_STATUSES:
            errors.append(f"TraceCertificate.v0 invalid status {status!r}")

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


def _is_valid_example(path: Path) -> bool:
    return path.suffix == ".json" and ".valid." in path.name


def iter_example_json_files(examples_dir: Path) -> list[Path]:
    return sorted(p for p in examples_dir.rglob("*.json") if p.is_file())


def check_all_schemas() -> None:
    for artifact_type, schema_name in ARTIFACT_SCHEMAS.items():
        schema_path = schemas_dir() / schema_name
        schema = _load_schema(schema_path)
        Draft202012Validator.check_schema(schema)
        get_validator(artifact_type)


def check_valid_examples(examples_dir: Path | None = None) -> None:
    examples_dir = examples_dir or default_examples_dir()
    for path in iter_example_json_files(examples_dir):
        if _is_valid_example(path):
            validate_file(path)


def check_invalid_examples(examples_dir: Path | None = None) -> None:
    examples_dir = examples_dir or default_examples_dir()
    invalid_cases: dict[str, str | None] = {
        "invalid_unknown_status.json": "RuntimeReceipt.v0",
        "invalid_missing_assumption_set.json": "ScienceClaimBundle.v0",
        "invalid_mismatched_trace_hash.json": "ScienceClaimBundle.v0",
        "invalid_zero_source_commit.release.json": "RuntimeReceipt.v0",
        "labtrust/invalid_singular_runtime_receipt_bundle.json": "ScienceClaimBundle.v0",
        "labtrust/invalid_signed_schema_version_artifact_name.json": "SignedScienceClaimBundle.v0",
    }
    for filename, artifact_type in invalid_cases.items():
        path = examples_dir / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        detected = detect_artifact_type(data)
        use_type = artifact_type or detected
        if not use_type:
            raise ValidationError(f"Could not detect type for {filename}")
        schema_errors = validate_schema(data, use_type)
        semantic_errors = validate_semantics(data, use_type)
        if not schema_errors and not semantic_errors:
            raise ValidationError(f"Expected {filename} to fail validation")
