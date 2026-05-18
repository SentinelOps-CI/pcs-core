"""PCS v0.1 scientific computation release-chain validation (profile-scoped)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pcs_core.computation_validate import (
    COMPUTATION_RUN_RECEIPT_FILE,
    COMPUTATION_WITNESS_FILE,
    DATASET_RECEIPT_FILE,
    ENVIRONMENT_RECEIPT_FILE,
    RESULT_ARTIFACT_FILE,
    validate_computation_witness_alignment,
    validate_dataset_receipt_semantics,
    validate_environment_receipt_semantics,
    validate_computation_run_receipt_semantics,
    validate_result_artifact_semantics,
    validate_computation_witness_semantics,
)
from pcs_core.release_chain import (
    ReleaseChainIssue,
    _expect_certificate_id,
    _expect_certificate_ref_contains,
    _first_certificate_id,
    _issue,
    _validate_scientific_memory_report_json,
)
from pcs_core.release_chain_profiles import COMPUTATION_WORKFLOW_PROFILE_ID
from pcs_core.release_fixtures import (
    MANIFEST_NAME,
    _load_json,
    _scan_forbidden_values,
    file_digest,
    is_release_pattern_placeholder,
    is_zero_commit,
)
from pcs_core.validate import ValidationError, validate_file

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMPUTATION_RUNNER_SOURCE_REPO = "https://github.com/example/scientific-computation-runner"

COMPUTATION_MANIFEST_ARTIFACTS = (
    DATASET_RECEIPT_FILE,
    ENVIRONMENT_RECEIPT_FILE,
    COMPUTATION_RUN_RECEIPT_FILE,
    RESULT_ARTIFACT_FILE,
    COMPUTATION_WITNESS_FILE,
    "science_claim_bundle.certified.json",
    "verification_result.json",
    "signed_science_claim_bundle.json",
    "scientific_memory_import_report.json",
)

COMPUTATION_RELEASE_PCS_ARTIFACTS = (
    DATASET_RECEIPT_FILE,
    ENVIRONMENT_RECEIPT_FILE,
    COMPUTATION_RUN_RECEIPT_FILE,
    RESULT_ARTIFACT_FILE,
    COMPUTATION_WITNESS_FILE,
    "science_claim_bundle.certified.json",
    "verification_result.json",
    "signed_science_claim_bundle.json",
)

COMPUTATION_COMMIT_KEYS = (
    "pcs_core_commit",
    "scientific_computation_commit",
    "certifyedge_commit",
    "provability_fabric_commit",
    "scientific_memory_commit",
)

COMPUTATION_HANDOFF_FILES = (
    "handoff_to_certifyedge.json",
    "handoff_to_pf.json",
    "handoff_manifest.runtime_to_certificate.v0.json",
    "handoff_manifest.certificate_to_bundle.v0.json",
    "handoff_manifest.bundle_to_verifier.v0.json",
    "handoff_manifest.signed_bundle_to_memory.v0.json",
)


def _validate_computation_scientific_memory_report(doc: dict[str, Any]) -> list[str]:
    errors = _validate_scientific_memory_report_json(doc)
    for key in ("workflow_profile_id", "workflow_profile_render_path"):
        if key not in doc:
            errors.append(f"scientific_memory_import_report.json: missing required field {key}")
    workflow_id = doc.get("workflow_profile_id")
    if workflow_id != COMPUTATION_WORKFLOW_PROFILE_ID:
        errors.append(
            "scientific_memory_import_report.json: workflow_profile_id must match release profile",
        )
    return errors


def _validate_computation_alignment(base: Path, errors: list[str]) -> None:
    dataset = _load_json(base / DATASET_RECEIPT_FILE)
    environment = _load_json(base / ENVIRONMENT_RECEIPT_FILE)
    run_receipt = _load_json(base / COMPUTATION_RUN_RECEIPT_FILE)
    result = _load_json(base / RESULT_ARTIFACT_FILE)
    witness = _load_json(base / COMPUTATION_WITNESS_FILE)
    if not all(isinstance(doc, dict) for doc in (dataset, environment, run_receipt, result, witness)):
        return
    errors.extend(
        validate_computation_witness_alignment(
            dataset=dataset,  # type: ignore[arg-type]
            environment=environment,  # type: ignore[arg-type]
            run_receipt=run_receipt,  # type: ignore[arg-type]
            result=result,  # type: ignore[arg-type]
            witness=witness,  # type: ignore[arg-type]
        ),
    )


def validate_computation_release_chain(directory: Path) -> list[ReleaseChainIssue]:
    """Validate a scientific computation release directory."""
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
    if profile_id != COMPUTATION_WORKFLOW_PROFILE_ID:
        issues.append(
            _issue(
                "schema_validation_failed",
                f"manifest workflow_profile_id must be {COMPUTATION_WORKFLOW_PROFILE_ID!r}",
                actual=profile_id,
            ),
        )

    commits = {key: manifest.get(key) for key in COMPUTATION_COMMIT_KEYS}
    for key in COMPUTATION_COMMIT_KEYS:
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

    if set(artifacts) != set(COMPUTATION_MANIFEST_ARTIFACTS):
        missing = sorted(set(COMPUTATION_MANIFEST_ARTIFACTS) - set(artifacts))
        extra = sorted(set(artifacts) - set(COMPUTATION_MANIFEST_ARTIFACTS))
        if missing:
            issues.append(
                _issue("schema_validation_failed", f"manifest artifacts missing keys: {missing}"),
            )
        if extra:
            issues.append(
                _issue("schema_validation_failed", f"manifest artifacts unexpected keys: {extra}"),
            )

    for name in COMPUTATION_MANIFEST_ARTIFACTS:
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
    for name in COMPUTATION_MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        doc = _load_json(path)
        if doc is None:
            issues.append(
                _issue("schema_validation_failed", f"{name}: invalid JSON", artifact=name),
            )
            continue
        if name == DATASET_RECEIPT_FILE:
            for msg in validate_dataset_receipt_semantics(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        elif name == ENVIRONMENT_RECEIPT_FILE:
            for msg in validate_environment_receipt_semantics(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        elif name == COMPUTATION_RUN_RECEIPT_FILE:
            for msg in validate_computation_run_receipt_semantics(doc):
                if "missing_code_commit" in msg or "zero" in msg:
                    issues.append(_issue("missing_code_commit", msg, artifact=name))
                elif "exit_code" in msg:
                    issues.append(_issue("nonzero_exit_code", msg, artifact=name))
                else:
                    issues.append(_issue("schema_validation_failed", msg, artifact=name))
        elif name == RESULT_ARTIFACT_FILE:
            for msg in validate_result_artifact_semantics(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        elif name == COMPUTATION_WITNESS_FILE:
            for msg in validate_computation_witness_semantics(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        elif name == "scientific_memory_import_report.json":
            for msg in _validate_computation_scientific_memory_report(doc):
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

    align_errors: list[str] = []
    _validate_computation_alignment(base, align_errors)
    for msg in align_errors:
        if "dataset_hash" in msg:
            issues.append(_issue("dataset_hash_mismatch", msg))
        elif "environment_hash" in msg:
            issues.append(_issue("environment_hash_mismatch", msg))
        elif "result_hashes" in msg:
            issues.append(_issue("result_hash_mismatch", msg))
        elif "run_receipt_hash" in msg:
            issues.append(_issue("run_receipt_hash_mismatch", msg))
        elif "nonzero_exit_code" in msg or "exit_code" in msg:
            issues.append(_issue("nonzero_exit_code", msg))
        elif "code_commit" in msg:
            issues.append(_issue("missing_code_commit", msg))
        else:
            issues.append(_issue("schema_validation_failed", msg))

    for name in COMPUTATION_RELEASE_PCS_ARTIFACTS:
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

    for handoff_name in COMPUTATION_HANDOFF_FILES:
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

    runner_commit = commits.get("scientific_computation_commit")
    ce_commit = commits.get("certifyedge_commit")
    pf_commit = commits.get("provability_fabric_commit")
    sm_commit = commits.get("scientific_memory_commit")

    runtime_docs = (
        DATASET_RECEIPT_FILE,
        ENVIRONMENT_RECEIPT_FILE,
        COMPUTATION_RUN_RECEIPT_FILE,
        RESULT_ARTIFACT_FILE,
    )
    if isinstance(runner_commit, str):
        for name in runtime_docs:
            doc = _load_json(base / name)
            if isinstance(doc, dict) and doc.get("source_commit") != runner_commit:
                issues.append(
                    _issue(
                        "scientific_computation_commit_mismatch",
                        f"{name}.source_commit {doc.get('source_commit')!r} "
                        f"!= manifest.scientific_computation_commit {runner_commit}",
                    ),
                )

    witness = _load_json(base / COMPUTATION_WITNESS_FILE)
    if isinstance(ce_commit, str) and witness and witness.get("source_commit") != ce_commit:
        issues.append(
            _issue(
                "certifyedge_commit_mismatch",
                f"computation_witness.source_commit {witness.get('source_commit')!r} "
                f"!= manifest.certifyedge_commit {ce_commit}",
            ),
        )

    verification = _load_json(base / "verification_result.json")
    signed = _load_json(base / "signed_science_claim_bundle.json")
    certified = _load_json(base / "science_claim_bundle.certified.json")
    sm_report = _load_json(base / "scientific_memory_import_report.json")

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

    witness_id = witness.get("witness_id") if witness else None
    certified_cert_id = _first_certificate_id(certified) if certified else None
    if witness_id and certified and isinstance(certified, dict):
        _expect_certificate_id(
            issues,
            expected=witness_id,
            actual=certified_cert_id,
            label="science_claim_bundle.certified.certificates[0].certificate_id",
            artifact="science_claim_bundle.certified.json",
        )
        _expect_certificate_ref_contains(
            issues,
            bundle=certified,
            part_key="claim_artifact",
            certificate_id=witness_id,
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

    if witness and witness.get("status") != "CertificateChecked":
        violation_type = "rejected_computation_witness"
        if witness.get("status") == "Rejected":
            issues.append(
                _issue(
                    violation_type,
                    "computation_witness.status is Rejected",
                ),
            )
        else:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    "computation_witness.status must be CertificateChecked",
                ),
            )

    manifest_v0 = _load_json(base / "release_manifest.v0.json")
    if manifest_v0:
        if manifest_v0.get("workflow_profile_id") != COMPUTATION_WORKFLOW_PROFILE_ID:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    "release_manifest.v0.json workflow_profile_id must match computation profile",
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
