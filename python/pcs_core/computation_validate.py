"""Semantic validation for scientific computation reproducibility artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, SIGNATURE_FIELD, canonical_hash

RELEASE_WITNESS_STATUS = "CertificateChecked"

COMPUTATION_WORKFLOW_ID = "scientific_computation.reproducibility_v0"

DATASET_RECEIPT_FILE = "dataset_receipt.json"
ENVIRONMENT_RECEIPT_FILE = "environment_receipt.json"
COMPUTATION_RUN_RECEIPT_FILE = "computation_run_receipt.json"
RESULT_ARTIFACT_FILE = "result_artifact.json"
COMPUTATION_WITNESS_FILE = "computation_witness.json"

def _is_zero_commit(commit: str) -> bool:
    return commit == "0" * 40


COMPUTATION_HANDOFF_FILES = (
    "handoff_to_certifyedge.json",
    "handoff_to_pf.json",
    "handoff_manifest.runtime_to_certificate.v0.json",
    "handoff_manifest.certificate_to_bundle.v0.json",
    "handoff_manifest.bundle_to_verifier.v0.json",
    "handoff_manifest.signed_bundle_to_memory.v0.json",
)


def receipt_body_digest(data: dict[str, Any]) -> str:
    """Canonical digest of a receipt-like artifact (signature stripped)."""
    body = dict(data)
    body[SIGNATURE_FIELD] = PLACEHOLDER_DIGEST
    return canonical_hash(body)


def dataset_aggregate_hash(files: list[dict[str, Any]]) -> str:
    return canonical_hash({"files": files})


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


def validate_dataset_receipt_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    files = data.get("files")
    aggregate_hash = data.get("aggregate_hash")
    if isinstance(files, list) and isinstance(aggregate_hash, str):
        expected = dataset_aggregate_hash(files)
        if aggregate_hash != expected:
            errors.append(
                "DatasetReceipt.v0 aggregate_hash does not match files binding",
            )
    errors.extend(_signature_or_digest_valid(data))
    return errors


def validate_environment_receipt_semantics(data: dict[str, Any]) -> list[str]:
    return _signature_or_digest_valid(data)


def validate_computation_run_receipt_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    code_commit = data.get("code_commit")
    if isinstance(code_commit, str) and _is_zero_commit(code_commit):
        errors.append(
            "ComputationRunReceipt.v0 code_commit must not be zero (missing_code_commit)",
        )
    errors.extend(_signature_or_digest_valid(data))
    return errors


def validate_result_artifact_semantics(data: dict[str, Any]) -> list[str]:
    return _signature_or_digest_valid(data)


def _validate_violation_object(item: Any, index: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"violations[{index}]: must be an object"]
    for key in ("violation_id", "violation_type", "explanation"):
        if not isinstance(item.get(key), str) or not item.get(key):
            errors.append(f"violations[{index}]: missing or invalid {key}")
    return errors


def validate_computation_witness_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = data.get("status")
    if status not in {"CertificateChecked", "Rejected", "Stale"}:
        errors.append(f"ComputationWitness.v0 invalid status {status!r}")
    violations = data.get("violations")
    if not isinstance(violations, list):
        errors.append("ComputationWitness.v0 violations must be an array")
        violations = []
    else:
        for index, item in enumerate(violations):
            errors.extend(_validate_violation_object(item, index))
    if status == RELEASE_WITNESS_STATUS and violations:
        errors.append(
            "ComputationWitness.v0 with status CertificateChecked requires empty violations",
        )
    elif status == "Rejected" and not violations:
        errors.append("ComputationWitness.v0 with status Rejected requires non-empty violations")
    code_commit = data.get("code_commit")
    if isinstance(code_commit, str) and _is_zero_commit(code_commit):
        errors.append(
            "ComputationWitness.v0 code_commit must not be zero (code_commit_present)",
        )
    errors.extend(_signature_or_digest_valid(data))
    return errors


def validate_computation_witness_alignment(
    *,
    dataset: dict[str, Any],
    environment: dict[str, Any],
    run_receipt: dict[str, Any],
    result: dict[str, Any],
    witness: dict[str, Any],
) -> list[str]:
    """Cross-artifact checks for the computation reproducibility trust loop."""
    errors: list[str] = []
    dataset_hash = witness.get("dataset_hash")
    expected_dataset = dataset.get("aggregate_hash")
    if isinstance(dataset_hash, str) and isinstance(expected_dataset, str):
        if dataset_hash != expected_dataset:
            errors.append(
                "ComputationWitness.v0 dataset_hash does not match DatasetReceipt aggregate_hash "
                "(dataset_hash_matches_receipt)",
            )
    environment_hash = witness.get("environment_hash")
    expected_environment = receipt_body_digest(environment)
    if isinstance(environment_hash, str) and environment_hash != expected_environment:
        errors.append(
            "ComputationWitness.v0 environment_hash does not match EnvironmentReceipt digest "
            "(environment_hash_matches_receipt)",
        )
    run_hash = witness.get("run_receipt_hash")
    expected_run = receipt_body_digest(run_receipt)
    if isinstance(run_hash, str) and run_hash != expected_run:
        errors.append(
            "ComputationWitness.v0 run_receipt_hash does not match ComputationRunReceipt digest "
            "(run_receipt_hash_matches_declared_run)",
        )
    result_hashes = witness.get("result_hashes")
    result_sha = result.get("sha256")
    if isinstance(result_hashes, list) and isinstance(result_sha, str):
        if result_sha not in result_hashes:
            errors.append(
                "ComputationWitness.v0 result_hashes must include ResultArtifact sha256 "
                "(result_hashes_match_result_artifacts)",
            )
    witness_code = witness.get("code_commit")
    run_code = run_receipt.get("code_commit")
    if isinstance(witness_code, str) and isinstance(run_code, str) and witness_code != run_code:
        errors.append("ComputationWitness.v0 code_commit does not match ComputationRunReceipt")
    if witness.get("status") == RELEASE_WITNESS_STATUS:
        exit_code = run_receipt.get("exit_code")
        if exit_code not in (0, None):
            errors.append(
                f"ComputationRunReceipt.v0 exit_code {exit_code!r} forbids CertificateChecked witness "
                "(nonzero_exit_code)",
            )
    return errors


def validate_computation_release_readiness(
    *,
    dataset: dict[str, Any],
    environment: dict[str, Any],
    run_receipt: dict[str, Any],
    result: dict[str, Any],
    witness: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_dataset_receipt_semantics(dataset))
    errors.extend(validate_environment_receipt_semantics(environment))
    errors.extend(validate_computation_run_receipt_semantics(run_receipt))
    errors.extend(validate_result_artifact_semantics(result))
    errors.extend(validate_computation_witness_semantics(witness))
    if witness.get("status") != RELEASE_WITNESS_STATUS:
        errors.append(
            f"ComputationWitness.v0 status must be {RELEASE_WITNESS_STATUS} for release",
        )
    errors.extend(
        validate_computation_witness_alignment(
            dataset=dataset,
            environment=environment,
            run_receipt=run_receipt,
            result=result,
            witness=witness,
        ),
    )
    return errors


def _load_release_json(directory: Path, name: str) -> dict[str, Any] | None:
    path = directory / name
    if not path.is_file():
        return None
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def validate_computation_release_directory(directory: Path) -> list[str]:
    """Validate a computation release fixture directory (valid train)."""
    import json

    from pcs_core.validate import ValidationError, validate_artifact, validate_file

    errors: list[str] = []
    required = (
        DATASET_RECEIPT_FILE,
        ENVIRONMENT_RECEIPT_FILE,
        COMPUTATION_RUN_RECEIPT_FILE,
        RESULT_ARTIFACT_FILE,
        COMPUTATION_WITNESS_FILE,
        "workflow_profile.v0.json",
    )
    for name in required:
        if not (directory / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        return errors
    dataset = json.loads((directory / DATASET_RECEIPT_FILE).read_text(encoding="utf-8"))
    environment = json.loads((directory / ENVIRONMENT_RECEIPT_FILE).read_text(encoding="utf-8"))
    run_receipt = json.loads((directory / COMPUTATION_RUN_RECEIPT_FILE).read_text(encoding="utf-8"))
    result = json.loads((directory / RESULT_ARTIFACT_FILE).read_text(encoding="utf-8"))
    witness = json.loads((directory / COMPUTATION_WITNESS_FILE).read_text(encoding="utf-8"))
    profile = json.loads((directory / "workflow_profile.v0.json").read_text(encoding="utf-8"))
    for doc, artifact_type in (
        (dataset, "DatasetReceipt.v0"),
        (environment, "EnvironmentReceipt.v0"),
        (run_receipt, "ComputationRunReceipt.v0"),
        (result, "ResultArtifact.v0"),
        (witness, "ComputationWitness.v0"),
        (profile, "WorkflowProfile.v0"),
    ):
        try:
            validate_artifact(doc, artifact_type)
        except ValidationError as exc:
            errors.append(str(exc))
            errors.extend(exc.errors)
    errors.extend(
        validate_computation_release_readiness(
            dataset=dataset,
            environment=environment,
            run_receipt=run_receipt,
            result=result,
            witness=witness,
        ),
    )
    if run_receipt.get("workflow_id") != profile.get("workflow_id"):
        errors.append("computation_run_receipt.workflow_id does not match workflow_profile")
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
        from pcs_core.computation_release_chain import (
            _validate_computation_scientific_memory_report,
        )

        try:
            sm_report = json.loads(sm_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"scientific_memory_import_report.json: invalid JSON: {exc}")
        else:
            if isinstance(sm_report, dict):
                errors.extend(
                    f"scientific_memory_import_report.json: {msg}"
                    for msg in _validate_computation_scientific_memory_report(sm_report)
                )
    for name in COMPUTATION_HANDOFF_FILES:
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


def validate_computation_invalid_case(directory: Path) -> list[str]:
    """Return errors if an invalid-case directory incorrectly passes validation."""
    import json

    from pcs_core.validate import ValidationError, validate_artifact

    paths = {
        "dataset": directory / DATASET_RECEIPT_FILE,
        "environment": directory / ENVIRONMENT_RECEIPT_FILE,
        "run": directory / COMPUTATION_RUN_RECEIPT_FILE,
        "result": directory / RESULT_ARTIFACT_FILE,
        "witness": directory / COMPUTATION_WITNESS_FILE,
    }
    if not all(path.is_file() for path in paths.values()):
        return [f"{directory.name}: missing computation release fixture files"]
    dataset = json.loads(paths["dataset"].read_text(encoding="utf-8"))
    environment = json.loads(paths["environment"].read_text(encoding="utf-8"))
    run_receipt = json.loads(paths["run"].read_text(encoding="utf-8"))
    result = json.loads(paths["result"].read_text(encoding="utf-8"))
    witness = json.loads(paths["witness"].read_text(encoding="utf-8"))
    failures: list[str] = []
    for doc, artifact_type in (
        (dataset, "DatasetReceipt.v0"),
        (environment, "EnvironmentReceipt.v0"),
        (run_receipt, "ComputationRunReceipt.v0"),
        (result, "ResultArtifact.v0"),
        (witness, "ComputationWitness.v0"),
    ):
        try:
            validate_artifact(doc, artifact_type)
        except ValidationError as exc:
            failures.append(f"{artifact_type}: {exc}")
            failures.extend(exc.errors)
    failures.extend(
        validate_computation_release_readiness(
            dataset=dataset,
            environment=environment,
            run_receipt=run_receipt,
            result=result,
            witness=witness,
        ),
    )
    if not failures:
        return [f"{directory.name}: invalid fixture must fail semantic validation"]
    return []
