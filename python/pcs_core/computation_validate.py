"""Semantic validation for scientific computation reproducibility artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import PLACEHOLDER_DIGEST, SIGNATURE_FIELD, canonical_hash
from pcs_core.safe_paths import UnsafePathError, resolve_contained_file


RELEASE_WITNESS_STATUS = "CertificateChecked"

COMPUTATION_WORKFLOW_ID = "scientific_computation.reproducibility_v0"

DATASET_RECEIPT_FILE = "dataset_receipt.json"
ENVIRONMENT_RECEIPT_FILE = "environment_receipt.json"
COMPUTATION_RUN_RECEIPT_FILE = "computation_run_receipt.json"
RESULT_ARTIFACT_FILE = "result_artifact.json"
COMPUTATION_WITNESS_FILE = "computation_witness.json"

# Issue-code tokens embedded in semantic error strings (release-chain mappers parse these).
PAYLOAD_DIGEST_MISMATCH = "payload_digest_mismatch"
PAYLOAD_SIZE_MISMATCH = "payload_size_mismatch"
PAYLOAD_MISSING = "payload_missing"
PAYLOAD_PATH_UNSAFE = "payload_path_unsafe"
DUPLICATE_RESULT_DECLARATION = "duplicate_result_declaration"


@dataclass(frozen=True)
class VerifiedResultPayload:
    """Byte-verified ResultArtifact.v0 payload under a release root."""

    result_id: str
    result_artifact_relpath: str
    payload_relpath: str
    digest: str
    size_bytes: int


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


def _payload_digest(content: bytes) -> str:
    return f"sha256:{sha256(content).hexdigest()}"


def verify_result_artifact_payload(
    release_dir: Path,
    result: Mapping[str, Any],
    *,
    result_artifact_relpath: str = RESULT_ARTIFACT_FILE,
) -> VerifiedResultPayload:
    """Resolve, read, and bind ResultArtifact.v0 payload bytes under ``release_dir``.

    Rejects absolute paths, ``..`` traversal, symlinks, and Windows reparse-point
    escapes. Compares SHA-256 and ``size_bytes`` against the declared fields.
    """
    result_id = result.get("result_id")
    if not isinstance(result_id, str) or not result_id.strip():
        raise ValueError(
            f"{result_artifact_relpath}: ResultArtifact.v0 result_id is required "
            f"({DUPLICATE_RESULT_DECLARATION})",
        )
    payload_ref = result.get("path")
    if not isinstance(payload_ref, str) or not payload_ref.strip():
        raise ValueError(
            f"{result_artifact_relpath}: ResultArtifact.v0 path is required ({PAYLOAD_MISSING})",
        )
    declared_digest = result.get("sha256")
    if not isinstance(declared_digest, str) or not declared_digest.startswith("sha256:"):
        raise ValueError(
            f"{result_artifact_relpath}: ResultArtifact.v0 sha256 is required "
            f"({PAYLOAD_DIGEST_MISMATCH})",
        )
    declared_size = result.get("size_bytes")
    if not isinstance(declared_size, int) or isinstance(declared_size, bool) or declared_size < 0:
        raise ValueError(
            f"{result_artifact_relpath}: ResultArtifact.v0 size_bytes is required "
            f"({PAYLOAD_SIZE_MISMATCH})",
        )

    root = release_dir.resolve()
    try:
        payload_path = resolve_contained_file(root, payload_ref)
    except UnsafePathError as exc:
        message = str(exc).lower()
        if "does not resolve" in message or "not a regular file" in message:
            code = PAYLOAD_MISSING
        else:
            code = PAYLOAD_PATH_UNSAFE
        raise ValueError(
            f"{result_artifact_relpath}: unsafe or missing payload path {payload_ref!r} "
            f"({code}): {exc}",
        ) from exc

    payload_bytes = payload_path.read_bytes()
    actual_digest = _payload_digest(payload_bytes)
    actual_size = len(payload_bytes)
    if actual_digest != declared_digest:
        raise ValueError(
            f"{result_artifact_relpath}: payload digest mismatch for {payload_ref!r}: "
            f"declared {declared_digest}, got {actual_digest} ({PAYLOAD_DIGEST_MISMATCH})",
        )
    if actual_size != declared_size:
        raise ValueError(
            f"{result_artifact_relpath}: payload size mismatch for {payload_ref!r}: "
            f"declared {declared_size}, got {actual_size} ({PAYLOAD_SIZE_MISMATCH})",
        )

    # Normalize to forward-slash release-relative path for projection / obligations.
    rel = payload_path.relative_to(root).as_posix()
    return VerifiedResultPayload(
        result_id=result_id.strip(),
        result_artifact_relpath=result_artifact_relpath.replace("\\", "/"),
        payload_relpath=rel,
        digest=actual_digest,
        size_bytes=actual_size,
    )


def _iter_result_artifact_files(release_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(relpath, doc)`` for every ResultArtifact.v0 under the release root."""
    root = release_dir.resolve()
    found: list[tuple[str, dict[str, Any]]] = []
    seen_paths: set[str] = set()

    def _consider(path: Path) -> None:
        if not path.is_file():
            return
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            return
        if rel in seen_paths:
            return
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(doc, dict):
            return
        # Primary harness file is always treated as ResultArtifact.v0.
        if path.name == RESULT_ARTIFACT_FILE or path.name.startswith("result_artifact"):
            seen_paths.add(rel)
            found.append((rel, doc))
            return
        artifact_type = str(doc.get("artifact_type") or "")
        if artifact_type == "ResultArtifact.v0":
            seen_paths.add(rel)
            found.append((rel, doc))

    _consider(root / RESULT_ARTIFACT_FILE)
    for path in sorted(root.glob("result_artifact*.json")):
        _consider(path)

    manifest_path = root / "release_manifest.v0.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            manifest = None
        if isinstance(manifest, dict):
            artifacts = manifest.get("artifacts")
            if isinstance(artifacts, dict):
                for name, meta in artifacts.items():
                    if not isinstance(meta, dict):
                        continue
                    artifact_type = str(meta.get("artifact_type") or "")
                    if artifact_type != "ResultArtifact.v0" and not str(name).startswith(
                        "result_artifact",
                    ):
                        continue
                    _consider(root / str(name))

    return found


def verify_all_result_artifact_payloads(release_dir: Path) -> list[VerifiedResultPayload]:
    """Verify every ResultArtifact.v0 payload; reject duplicate declarations."""
    entries = _iter_result_artifact_files(release_dir)
    if not entries:
        raise ValueError(
            f"{release_dir}: no ResultArtifact.v0 files found ({PAYLOAD_MISSING})",
        )

    verified: list[VerifiedResultPayload] = []
    seen_ids: dict[str, str] = {}
    seen_payload_paths: dict[str, str] = {}

    for relpath, doc in entries:
        item = verify_result_artifact_payload(
            release_dir,
            doc,
            result_artifact_relpath=relpath,
        )
        prior_id = seen_ids.get(item.result_id)
        if prior_id is not None:
            raise ValueError(
                f"duplicate ResultArtifact result_id {item.result_id!r} in "
                f"{prior_id} and {relpath} ({DUPLICATE_RESULT_DECLARATION})",
            )
        prior_path = seen_payload_paths.get(item.payload_relpath)
        if prior_path is not None:
            raise ValueError(
                f"duplicate ResultArtifact payload path {item.payload_relpath!r} in "
                f"{prior_path} and {relpath} ({DUPLICATE_RESULT_DECLARATION})",
            )
        seen_ids[item.result_id] = relpath
        seen_payload_paths[item.payload_relpath] = relpath
        verified.append(item)
    return verified


def validate_result_payloads_in_release(directory: Path) -> list[str]:
    """Return semantic errors for ResultArtifact payload binding under ``directory``."""
    try:
        verify_all_result_artifact_payloads(directory)
    except ValueError as exc:
        return [str(exc)]
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
    if isinstance(result_hashes, list):
        normalized = [str(item) for item in result_hashes]
        if len(normalized) != len(set(normalized)):
            errors.append(
                "ComputationWitness.v0 result_hashes must not contain duplicates "
                "(duplicate_result_hash)",
            )
        if isinstance(result_sha, str):
            if result_sha not in normalized:
                errors.append(
                    "ComputationWitness.v0 result_hashes must include ResultArtifact sha256 "
                    "(result_hashes_match_result_artifacts)",
                )
            # Independent declared set for the single-artifact harness is {result.sha256}.
            undeclared = [item for item in normalized if item != result_sha]
            if undeclared:
                errors.append(
                    "ComputationWitness.v0 result_hashes contain digests not justified by "
                    "ResultArtifact.sha256 (witness_undeclared_extra_result)",
                )
    if witness.get("status") == RELEASE_WITNESS_STATUS:
        for field, value in (
            ("dataset_hash", dataset_hash),
            ("environment_hash", environment_hash),
            ("run_receipt_hash", run_hash),
        ):
            if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
                errors.append(
                    f"ComputationWitness.v0 {field} must be a non-empty sha256 digest "
                    f"(missing_{field})",
                )
        exit_code = run_receipt.get("exit_code")
        if exit_code not in (0, None):
            errors.append(
                f"ComputationRunReceipt.v0 exit_code {exit_code!r} forbids "
                "CertificateChecked witness (nonzero_exit_code)",
            )
    witness_code = witness.get("code_commit")
    run_code = run_receipt.get("code_commit")
    if isinstance(witness_code, str) and isinstance(run_code, str) and witness_code != run_code:
        errors.append("ComputationWitness.v0 code_commit does not match ComputationRunReceipt")
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
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def validate_computation_release_directory(directory: Path) -> list[str]:
    """Validate a computation release fixture directory (valid train)."""
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
    errors.extend(validate_result_payloads_in_release(directory))
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
    failures.extend(validate_result_payloads_in_release(directory))
    if not failures:
        return [f"{directory.name}: invalid fixture must fail semantic validation"]
    return []
