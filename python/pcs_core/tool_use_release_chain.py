"""PCS v0.1 tool-use release-chain validation (profile-scoped)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pcs_core.release_chain import (
    ReleaseChainIssue,
    _expect_certificate_id,
    _expect_certificate_ref_contains,
    _first_certificate_id,
    _issue,
    _validate_scientific_memory_report_json,
)
from pcs_core.release_chain_profiles import (
    TOOL_USE_WORKFLOW_PROFILE_ID,
    resolve_tool_use_artifact,
)
from pcs_core.release_fixtures import (
    MANIFEST_NAME,
    _load_json,
    _scan_forbidden_values,
    file_digest,
    is_release_pattern_placeholder,
    is_zero_commit,
)
from pcs_core.tool_use_validate import (
    validate_tool_use_trace_certificate_alignment,
    validate_tool_use_trace_semantics,
)
from pcs_core.validate import ValidationError, validate_file

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
AGENT_RUNTIME_SOURCE_REPO = "https://github.com/example/agent-runtime"

TOOL_USE_MANIFEST_ARTIFACTS = (
    "tool_use_trace.valid.json",
    "runtime_receipt.json",
    "tool_use_certificate.valid.json",
    "science_claim_bundle.certified.json",
    "verification_result.json",
    "signed_science_claim_bundle.json",
    "scientific_memory_import_report.json",
)

TOOL_USE_RELEASE_PCS_ARTIFACTS = (
    "runtime_receipt.json",
    "tool_use_certificate.valid.json",
    "science_claim_bundle.certified.json",
    "verification_result.json",
    "signed_science_claim_bundle.json",
)

TOOL_USE_COMMIT_KEYS = (
    "pcs_core_commit",
    "agent_runtime_commit",
    "certifyedge_commit",
    "provability_fabric_commit",
    "scientific_memory_commit",
)

TOOL_USE_HANDOFF_FILES = (
    "handoff_to_certifyedge.json",
    "handoff_to_pf.json",
    "handoff_manifest.runtime_to_certificate.v0.json",
    "handoff_manifest.certificate_to_bundle.v0.json",
    "handoff_manifest.bundle_to_verifier.v0.json",
    "handoff_manifest.signed_bundle_to_memory.v0.json",
)

def _validate_tool_use_trace_json(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    trace_hash = doc.get("trace_hash")
    if not isinstance(trace_hash, str) or not _DIGEST_RE.fullmatch(trace_hash):
        errors.append("tool_use_trace: trace_hash must be a sha256 digest")
    policy_hash = doc.get("policy_hash")
    if not isinstance(policy_hash, str) or not _DIGEST_RE.fullmatch(policy_hash):
        errors.append("tool_use_trace: policy_hash must be a sha256 digest")
    errors.extend(validate_tool_use_trace_semantics(doc))
    return errors


def _validate_tool_use_scientific_memory_report(doc: dict[str, Any]) -> list[str]:
    errors = _validate_scientific_memory_report_json(doc)
    for key in ("workflow_profile_id", "workflow_profile_render_path"):
        if key not in doc:
            errors.append(f"scientific_memory_import_report.json: missing required field {key}")
    workflow_id = doc.get("workflow_profile_id")
    if workflow_id != TOOL_USE_WORKFLOW_PROFILE_ID:
        errors.append(
            "scientific_memory_import_report.json: workflow_profile_id must match release profile",
        )
    return errors


def _validate_tool_use_trace_hash_alignment(base: Path, errors: list[str]) -> None:
    trace_path = resolve_tool_use_artifact(base, ("tool_use_trace.valid.json", "tool_use_trace.json"))
    cert_path = resolve_tool_use_artifact(
        base,
        ("tool_use_certificate.valid.json", "tool_use_certificate.json"),
    )
    if not trace_path or not cert_path:
        return
    trace = _load_json(trace_path)
    receipt = _load_json(base / "runtime_receipt.json")
    cert = _load_json(cert_path)
    if not trace or not receipt or not cert:
        return
    trace_hash = trace.get("trace_hash")
    if trace_hash != receipt.get("trace_hash"):
        errors.append(
            f"trace_hash mismatch: trace {trace_hash} != runtime_receipt {receipt.get('trace_hash')}",
        )
    if trace_hash != cert.get("trace_hash"):
        errors.append(
            f"trace_hash mismatch: trace {trace_hash} != certificate {cert.get('trace_hash')}",
        )
    align_errors = validate_tool_use_trace_certificate_alignment(trace, cert)
    errors.extend(align_errors)


def validate_tool_use_release_chain(directory: Path) -> list[ReleaseChainIssue]:
    """Validate a tool-use release directory for single-run atomic consistency."""
    issues: list[ReleaseChainIssue] = []
    base = directory.resolve()

    manifest_path = base / MANIFEST_NAME
    if not manifest_path.is_file():
        issues.append(_issue("manifest_missing", f"{MANIFEST_NAME} not found in {base}"))
        return issues

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(_issue("schema_validation_failed", f"manifest JSON parse error: {exc}"))
        return issues

    if not isinstance(manifest, dict):
        issues.append(_issue("schema_validation_failed", "manifest root must be a JSON object"))
        return issues

    profile_id = manifest.get("workflow_profile_id")
    if profile_id != TOOL_USE_WORKFLOW_PROFILE_ID:
        issues.append(
            _issue(
                "schema_validation_failed",
                f"manifest workflow_profile_id must be {TOOL_USE_WORKFLOW_PROFILE_ID!r}",
                actual=profile_id,
            ),
        )

    commits = {key: manifest.get(key) for key in TOOL_USE_COMMIT_KEYS}
    for key in TOOL_USE_COMMIT_KEYS:
        commit = commits[key]
        if not isinstance(commit, str) or len(commit) != 40:
            issues.append(_issue("schema_validation_failed", f"manifest missing or invalid {key}"))
        elif is_zero_commit(commit):
            issues.append(
                _issue(
                    "placeholder_commit_detected",
                    f"manifest {key} uses zero provenance: {commit}",
                    artifact=MANIFEST_NAME,
                ),
            )
        elif is_release_pattern_placeholder(commit):
            issues.append(
                _issue(
                    "placeholder_commit_detected",
                    f"manifest {key} uses pattern placeholder provenance: {commit}",
                    artifact=MANIFEST_NAME,
                ),
            )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        issues.append(_issue("schema_validation_failed", "manifest artifacts must be an object"))
        return issues

    if set(artifacts) != set(TOOL_USE_MANIFEST_ARTIFACTS):
        missing = sorted(set(TOOL_USE_MANIFEST_ARTIFACTS) - set(artifacts))
        extra = sorted(set(artifacts) - set(TOOL_USE_MANIFEST_ARTIFACTS))
        if missing:
            issues.append(
                _issue("schema_validation_failed", f"manifest artifacts missing keys: {missing}"),
            )
        if extra:
            issues.append(
                _issue("schema_validation_failed", f"manifest artifacts unexpected keys: {extra}"),
            )

    for name in TOOL_USE_MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            issues.append(_issue("artifact_missing", f"missing artifact file {name}"))
            continue
        expected = artifacts.get(name)
        actual = file_digest(path.read_bytes())
        if expected != actual:
            issues.append(
                _issue(
                    "manifest_hash_mismatch",
                    f"{name}: manifest digest mismatch (expected {expected}, got {actual})",
                    artifact=name,
                    expected=expected,
                    actual=actual,
                ),
            )

    scan_errors: list[str] = []
    trace_name = "tool_use_trace.valid.json"
    for name in TOOL_USE_MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        doc = _load_json(path)
        if doc is None:
            issues.append(
                _issue("schema_validation_failed", f"{name}: invalid JSON", artifact=name),
            )
            continue
        if name in ("tool_use_trace.valid.json", "tool_use_trace.json"):
            trace_name = name
            for msg in _validate_tool_use_trace_json(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        elif name == "scientific_memory_import_report.json":
            for msg in _validate_tool_use_scientific_memory_report(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        _scan_forbidden_values(doc, label=name, errors=scan_errors)
    for msg in scan_errors:
        artifact = msg.split(":", 1)[0] if ":" in msg else None
        if "local_dev" in msg:
            issues.append(_issue("local_dev_detected", msg, artifact=artifact))
        elif "zero" in msg or "placeholder" in msg:
            issues.append(_issue("placeholder_commit_detected", msg, artifact=artifact))
        else:
            issues.append(_issue("schema_validation_failed", msg, artifact=artifact))

    trace_errors: list[str] = []
    _validate_tool_use_trace_hash_alignment(base, trace_errors)
    for msg in trace_errors:
        if "policy_hash" in msg:
            issues.append(_issue("policy_hash_mismatch", msg))
        else:
            issues.append(_issue("trace_hash_mismatch", msg))

    for name in TOOL_USE_RELEASE_PCS_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"{name}: pcs validate failed: {exc}",
                    artifact=name,
                ),
            )

    for handoff_name in TOOL_USE_HANDOFF_FILES:
        handoff_path = base / handoff_name
        if handoff_path.is_file():
            try:
                validate_file(handoff_path)
            except ValidationError as exc:
                issues.append(
                    _issue(
                        "schema_validation_failed",
                        f"{handoff_name}: pcs validate failed: {exc}",
                        artifact=handoff_name,
                    ),
                )

    agent_commit = commits.get("agent_runtime_commit")
    ce_commit = commits.get("certifyedge_commit")
    pf_commit = commits.get("provability_fabric_commit")
    sm_commit = commits.get("scientific_memory_commit")

    trace_path = resolve_tool_use_artifact(base, ("tool_use_trace.valid.json", "tool_use_trace.json"))
    cert_path = resolve_tool_use_artifact(
        base,
        ("tool_use_certificate.valid.json", "tool_use_certificate.json"),
    )
    trace = _load_json(trace_path) if trace_path else None
    tool_cert = _load_json(cert_path) if cert_path else None
    receipt = _load_json(base / "runtime_receipt.json")
    certified = _load_json(base / "science_claim_bundle.certified.json")
    verification = _load_json(base / "verification_result.json")
    signed = _load_json(base / "signed_science_claim_bundle.json")
    sm_report = _load_json(base / "scientific_memory_import_report.json")

    if isinstance(agent_commit, str) and trace and trace.get("source_commit") != agent_commit:
        issues.append(
            _issue(
                "agent_runtime_commit_mismatch",
                f"tool_use_trace.source_commit {trace.get('source_commit')!r} "
                f"!= manifest.agent_runtime_commit {agent_commit}",
            ),
        )
    if isinstance(agent_commit, str) and receipt and receipt.get("source_commit") != agent_commit:
        issues.append(
            _issue(
                "agent_runtime_commit_mismatch",
                f"runtime_receipt.source_commit {receipt.get('source_commit')!r} "
                f"!= manifest.agent_runtime_commit {agent_commit}",
            ),
        )

    if isinstance(ce_commit, str) and tool_cert and tool_cert.get("source_commit") != ce_commit:
        issues.append(
            _issue(
                "certifyedge_commit_mismatch",
                f"tool_use_certificate.source_commit {tool_cert.get('source_commit')!r} "
                f"!= manifest.certifyedge_commit {ce_commit}",
            ),
        )

    if isinstance(pf_commit, str):
        if verification and verification.get("source_commit") != pf_commit:
            issues.append(
                _issue(
                    "pf_commit_mismatch",
                    f"verification_result.source_commit {verification.get('source_commit')!r} "
                    f"!= manifest.provability_fabric_commit {pf_commit}",
                ),
            )
        if signed and signed.get("source_commit") != pf_commit:
            issues.append(
                _issue(
                    "pf_commit_mismatch",
                    f"signed_science_claim_bundle.source_commit {signed.get('source_commit')!r} "
                    f"!= manifest.provability_fabric_commit {pf_commit}",
                ),
            )

    if isinstance(sm_commit, str) and sm_report:
        if sm_report.get("source_commit") != sm_commit:
            issues.append(
                _issue(
                    "scientific_memory_commit_mismatch",
                    f"scientific_memory_import_report.source_commit "
                    f"{sm_report.get('source_commit')!r} != manifest.scientific_memory_commit "
                    f"{sm_commit}",
                ),
            )
        if sm_report.get("verification_status") != "passed":
            issues.append(
                _issue(
                    "scientific_memory_import_failed",
                    "scientific_memory_import_report.verification_status must be passed",
                ),
            )

    tool_cert_id = tool_cert.get("certificate_id") if tool_cert else None
    certified_cert_id = _first_certificate_id(certified) if certified else None
    signed_scb = signed.get("science_claim_bundle") if signed else None

    if tool_cert_id and certified and isinstance(certified, dict):
        _expect_certificate_id(
            issues,
            expected=tool_cert_id,
            actual=certified_cert_id,
            label="science_claim_bundle.certified.certificates[0].certificate_id",
            artifact="science_claim_bundle.certified.json",
        )
        _expect_certificate_ref_contains(
            issues,
            bundle=certified,
            part_key="claim_artifact",
            certificate_id=tool_cert_id,
            artifact="science_claim_bundle.certified.json",
        )

    if verification and verification.get("status") != "ProofChecked":
        issues.append(
            _issue(
                "schema_validation_failed",
                "verification_result.status must be ProofChecked",
            ),
        )

    certified_hash = artifacts.get("science_claim_bundle.certified.json") if isinstance(artifacts, dict) else None
    if certified_hash and verification:
        verified = verification.get("verified_input")
        if isinstance(verified, dict):
            bundle_hash = verified.get("bundle_hash")
            if bundle_hash and bundle_hash != certified_hash:
                issues.append(
                    _issue(
                        "verified_input_hash_mismatch",
                        f"verified_input.bundle_hash {bundle_hash} != manifest certified bundle hash",
                    ),
                )

    if tool_cert and tool_cert.get("status") != "CertificateChecked":
        issues.append(
            _issue(
                "schema_validation_failed",
                "tool_use_certificate.status must be CertificateChecked",
            ),
        )

    manifest_v0 = _load_json(base / "release_manifest.v0.json")
    if manifest_v0:
        if manifest_v0.get("workflow_profile_id") != TOOL_USE_WORKFLOW_PROFILE_ID:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    "release_manifest.v0.json workflow_profile_id must match tool-use profile",
                ),
            )
        try:
            validate_file(base / "release_manifest.v0.json")
        except ValidationError as exc:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"release_manifest.v0.json: pcs validate failed: {exc}",
                    artifact="release_manifest.v0.json",
                ),
            )

    return issues
