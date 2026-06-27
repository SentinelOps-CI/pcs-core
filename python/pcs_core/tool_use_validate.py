"""Semantic validation for tool-use workflow artifacts (domain-agnostic trust boundary)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, SIGNATURE_FIELD, canonical_hash
from pcs_core.registry_data import registry_entries

AUTHORIZED = "authorized"
RELEASE_CERTIFICATE_STATUS = "CertificateChecked"

TOOL_USE_TRACE_FILES = ("tool_use_trace.valid.json", "tool_use_trace.json")
TOOL_USE_CERTIFICATE_FILES = ("tool_use_certificate.valid.json", "tool_use_certificate.json")

TOOL_USE_HANDOFF_FILES = (
    "handoff_to_certifyedge.json",
    "handoff_to_pf.json",
    "handoff_manifest.runtime_to_certificate.v0.json",
    "handoff_manifest.certificate_to_bundle.v0.json",
    "handoff_manifest.bundle_to_verifier.v0.json",
    "handoff_manifest.signed_bundle_to_memory.v0.json",
)


def policy_hash_from_policy_id(policy_id: str) -> str:
    """Canonical digest of a workflow policy identifier (v0.1 convention)."""
    return canonical_hash({"policy_id": policy_id})


def _resolve_release_file(directory: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = directory / name
        if path.is_file():
            return path
    return None


def _signature_or_digest_valid(data: dict[str, Any]) -> list[str]:
    digest = data.get(SIGNATURE_FIELD)
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return [f"{SIGNATURE_FIELD} must be a sha256 digest"]
    body = dict(data)
    body[SIGNATURE_FIELD] = PLACEHOLDER_DIGEST
    expected = canonical_hash(body)
    if digest != expected:
        return [f"{SIGNATURE_FIELD} does not match canonical digest (signature_or_digest_valid)"]
    return []


def validate_tool_use_trace_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    trace_hash = data.get("trace_hash")
    if not isinstance(trace_hash, str) or not trace_hash.startswith("sha256:"):
        errors.append("ToolUseTrace.v0 requires trace_hash (trace_hash_present)")
    else:
        body = dict(data)
        body["trace_hash"] = PLACEHOLDER_DIGEST
        body[SIGNATURE_FIELD] = PLACEHOLDER_DIGEST
        expected = canonical_hash(body)
        if trace_hash != expected:
            errors.append(
                "ToolUseTrace.v0 trace_hash does not match canonical digest (trace_hash_present)",
            )
    policy_id = data.get("policy_id")
    policy_hash = data.get("policy_hash")
    if not isinstance(policy_hash, str) or not policy_hash.startswith("sha256:"):
        errors.append("ToolUseTrace.v0 requires policy_hash in release mode")
    elif isinstance(policy_id, str):
        expected_policy = policy_hash_from_policy_id(policy_id)
        if policy_hash != expected_policy:
            errors.append(
                "ToolUseTrace.v0 policy_hash does not match canonical policy_id digest",
            )
    tool_calls = data.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        errors.append("ToolUseTrace.v0 requires non-empty tool_calls")
        return errors
    for index, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            continue
        status = call.get("authorization_status")
        if status not in {"authorized", "rejected", "unknown", "policy_missing"}:
            errors.append(
                f"tool_calls[{index}]: invalid authorization_status {status!r}",
            )
        if status in {"unknown", "policy_missing"}:
            errors.append(
                f"tool_calls[{index}]: authorization_status {status!r} forbidden in "
                "release-mode traces (no_unknown_authorization_status)",
            )
    return errors


def _validate_violation_object(item: Any, index: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"violations[{index}]: must be an object"]
    for key in (
        "violation_id",
        "event_id",
        "violation_type",
        "tool_name",
        "policy_ref",
        "explanation",
    ):
        if not isinstance(item.get(key), str) or not item.get(key):
            errors.append(f"violations[{index}]: missing or invalid {key}")
    return errors


def validate_tool_use_certificate_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = data.get("status")
    if status not in {"CertificateChecked", "Rejected", "Stale"}:
        errors.append(f"ToolUseCertificate.v0 invalid status {status!r}")
    violations = data.get("violations")
    if not isinstance(violations, list):
        errors.append("ToolUseCertificate.v0 violations must be an array")
        violations = []
    else:
        for index, item in enumerate(violations):
            errors.extend(_validate_violation_object(item, index))
    if status == RELEASE_CERTIFICATE_STATUS and violations:
        errors.append(
            "ToolUseCertificate.v0 with status CertificateChecked requires empty violations",
        )
    elif status == "Rejected" and not violations:
        errors.append("ToolUseCertificate.v0 with status Rejected requires non-empty violations")
    errors.extend(_signature_or_digest_valid(data))
    return errors


def validate_tool_use_trace_certificate_alignment(
    trace: dict[str, Any],
    certificate: dict[str, Any],
) -> list[str]:
    """Cross-artifact checks for the tool-use trust loop."""
    errors: list[str] = []
    trace_hash = trace.get("trace_hash")
    cert_trace = certificate.get("trace_hash")
    if isinstance(trace_hash, str) and isinstance(cert_trace, str) and trace_hash != cert_trace:
        errors.append(
            "ToolUseCertificate.v0 trace_hash does not match ToolUseTrace.v0 trace_hash "
            "(tool_trace_hash_matches_certificate)",
        )
    trace_policy_hash = trace.get("policy_hash")
    policy_hash = certificate.get("policy_hash")
    if isinstance(trace_policy_hash, str) and isinstance(policy_hash, str):
        if policy_hash != trace_policy_hash:
            errors.append(
                "ToolUseCertificate.v0 policy_hash does not match ToolUseTrace.v0 policy_hash "
                "(policy_hash_matches_certificate)",
            )
    elif isinstance(trace.get("policy_id"), str) and isinstance(policy_hash, str):
        expected = policy_hash_from_policy_id(str(trace["policy_id"]))
        if policy_hash != expected:
            errors.append(
                "ToolUseCertificate.v0 policy_hash does not match ToolUseTrace.v0 policy_id "
                "(policy_hash_matches_certificate)",
            )
    status = certificate.get("status")
    if status == RELEASE_CERTIFICATE_STATUS:
        tool_calls = trace.get("tool_calls")
        if isinstance(tool_calls, list):
            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict):
                    continue
                if call.get("authorization_status") != AUTHORIZED:
                    errors.append(
                        f"tool_calls[{index}]: authorization_status must be authorized "
                        "when certificate status is CertificateChecked",
                    )
    return errors


def validate_workflow_profile_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    handoff_kinds = {
        "runtime_to_certificate",
        "certificate_to_bundle",
        "bundle_to_verifier",
        "signed_bundle_to_memory",
        "release_chain",
    }
    sequence = data.get("handoff_sequence")
    if isinstance(sequence, list):
        for index, kind in enumerate(sequence):
            if isinstance(kind, str) and kind not in handoff_kinds:
                errors.append(f"handoff_sequence[{index}]: unknown handoff_kind {kind!r}")
    known_types = set(registry_entries().keys())
    for field in ("runtime_artifacts", "certificate_artifacts", "required_registry_entries"):
        values = data.get(field)
        if not isinstance(values, list):
            continue
        for artifact_type in values:
            if isinstance(artifact_type, str) and artifact_type not in known_types:
                errors.append(
                    f"{field}: unknown artifact type {artifact_type!r} (not in registry)",
                )
    required = data.get("required_registry_entries")
    runtime = data.get("runtime_artifacts")
    certs = data.get("certificate_artifacts")
    if isinstance(required, list) and isinstance(runtime, list):
        for artifact_type in runtime:
            if artifact_type not in required:
                errors.append(
                    f"runtime_artifacts: {artifact_type} missing from required_registry_entries",
                )
    if isinstance(required, list) and isinstance(certs, list):
        for artifact_type in certs:
            if artifact_type not in required:
                errors.append(
                    f"certificate_artifacts: {artifact_type} missing from "
                    "required_registry_entries",
                )
    admission = data.get("required_admission_profile")
    if not isinstance(admission, str) or not admission:
        errors.append("WorkflowProfile.v0 requires required_admission_profile")
    return errors


def validate_tool_use_release_directory(directory: Path) -> list[str]:
    """Validate a tool-use release fixture directory (valid train)."""
    import json

    errors: list[str] = []
    from pcs_core.validate import ValidationError, validate_artifact, validate_file

    trace_path = _resolve_release_file(directory, TOOL_USE_TRACE_FILES)
    cert_path = _resolve_release_file(directory, TOOL_USE_CERTIFICATE_FILES)
    profile_path = directory / "workflow_profile.v0.json"
    for label, path in (
        ("tool_use_trace", trace_path),
        ("tool_use_certificate", cert_path),
        ("workflow_profile.v0.json", profile_path if profile_path.is_file() else None),
    ):
        if path is None:
            errors.append(f"missing {label}")
    if errors:
        return errors
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        certificate = json.loads(cert_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    for doc, artifact_type in (
        (trace, "ToolUseTrace.v0"),
        (certificate, "ToolUseCertificate.v0"),
        (profile, "WorkflowProfile.v0"),
    ):
        try:
            validate_artifact(doc, artifact_type)
        except ValidationError as exc:
            errors.append(str(exc))
            errors.extend(exc.errors)
    errors.extend(validate_tool_use_release_readiness(trace, certificate))
    workflow_id = trace.get("workflow_id")
    if workflow_id != profile.get("workflow_id"):
        errors.append("tool_use_trace.workflow_id does not match workflow_profile.workflow_id")
    for name in (
        "science_claim_bundle.certified.json",
        "verification_result.json",
        "signed_science_claim_bundle.json",
        "release_manifest.v0.json",
        "release_chain_validation_result.v0.json",
    ):
        path = directory / name
        if path.is_file():
            try:
                validate_file(path)
            except ValidationError as exc:
                errors.append(f"{name}: {exc}")
                errors.extend(exc.errors)
        else:
            errors.append(f"missing {name}")
    sm_report_path = directory / "scientific_memory_import_report.json"
    if not sm_report_path.is_file():
        errors.append("missing scientific_memory_import_report.json")
    else:
        import json

        from pcs_core.tool_use_release_chain import _validate_tool_use_scientific_memory_report

        try:
            sm_report = json.loads(sm_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"scientific_memory_import_report.json: invalid JSON: {exc}")
        else:
            if isinstance(sm_report, dict):
                errors.extend(
                    f"scientific_memory_import_report.json: {msg}"
                    for msg in _validate_tool_use_scientific_memory_report(sm_report)
                )
    for name in TOOL_USE_HANDOFF_FILES:
        path = directory / name
        if not path.is_file():
            errors.append(f"missing {name}")
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{name}: {exc}")
            errors.extend(exc.errors)
    legacy_manifest = directory / "RELEASE_FIXTURE_MANIFEST.json"
    if not legacy_manifest.is_file():
        errors.append(f"missing {legacy_manifest.name}")
    return errors


def validate_tool_use_release_readiness(
    trace: dict[str, Any],
    certificate: dict[str, Any],
) -> list[str]:
    """Release-mode readiness beyond schema validation."""
    errors: list[str] = []
    if certificate.get("status") != RELEASE_CERTIFICATE_STATUS:
        errors.append(
            f"ToolUseCertificate.v0 status must be {RELEASE_CERTIFICATE_STATUS} for release",
        )
    errors.extend(validate_tool_use_trace_certificate_alignment(trace, certificate))
    return errors


def validate_tool_use_invalid_case(directory: Path) -> list[str]:
    """Return errors if an invalid-case directory incorrectly passes validation."""
    import json

    from pcs_core.validate import ValidationError, validate_artifact

    trace_path = _resolve_release_file(directory, TOOL_USE_TRACE_FILES)
    cert_path = _resolve_release_file(directory, TOOL_USE_CERTIFICATE_FILES)
    if trace_path is None or cert_path is None:
        return [f"{directory.name}: missing trace or certificate fixture"]
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    certificate = json.loads(cert_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for doc, artifact_type in (
        (trace, "ToolUseTrace.v0"),
        (certificate, "ToolUseCertificate.v0"),
    ):
        try:
            validate_artifact(doc, artifact_type)
        except ValidationError as exc:
            failures.append(f"{artifact_type}: {exc}")
            failures.extend(exc.errors)
    failures.extend(validate_tool_use_trace_certificate_alignment(trace, certificate))
    failures.extend(validate_tool_use_release_readiness(trace, certificate))
    if not failures:
        return [f"{directory.name}: invalid fixture must fail semantic validation"]
    return []
