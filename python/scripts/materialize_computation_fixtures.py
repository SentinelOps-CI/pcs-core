#!/usr/bin/env python3
"""Write scientific computation workflow profiles and conformance release fixtures."""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from pcs_core.computation_validate import (  # noqa: E402
    COMPUTATION_WORKFLOW_ID,
    dataset_aggregate_hash,
    receipt_body_digest,
)
from pcs_core.computation_release_chain import COMPUTATION_MANIFEST_ARTIFACTS  # noqa: E402
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash  # noqa: E402
from pcs_core.paths import examples_dir  # noqa: E402
from pcs_core.protocol_fixtures import (  # noqa: E402
    CERTIFYEDGE_REPO,
    PF_REPO,
    PCS_CORE_REPO,
    SM_REPO,
)
from pcs_core.registry import build_artifact_registry  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402

RUNNER_REPO = "https://github.com/example/scientific-computation-runner"
RUNNER_COMMIT = "e555555555555555555555555555555555555555"
CERTIFYEDGE_COMMIT = "b222222222222222222222222222222222222222"
PF_COMMIT = "c333333333333333333333333333333333333333"
PCS_COMMIT = "d444444444444444444444444444444444444444"

WITNESS_ID = "witness-sci-comp-repro-001"
DATASET_ID = "dataset-input-001"
ENV_ID = "env-repro-001"
RUN_ID = "run-sci-comp-001"
RESULT_ID = "result-metric-001"
RESULT_SHA = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

_PLACEHOLDER_COMMITS = {
    "a" * 40: RUNNER_COMMIT,
    "b" * 40: CERTIFYEDGE_COMMIT,
    "c" * 40: PF_COMMIT,
    "d" * 40: PCS_COMMIT,
}


def _normalize_fixture_commits(obj: Any) -> None:
    if isinstance(obj, dict):
        commit = obj.get("source_commit")
        if isinstance(commit, str) and commit in _PLACEHOLDER_COMMITS:
            obj["source_commit"] = _PLACEHOLDER_COMMITS[commit]
        for value in obj.values():
            _normalize_fixture_commits(value)
    elif isinstance(obj, list):
        for item in obj:
            _normalize_fixture_commits(item)


def _with_digest(body: dict[str, Any]) -> dict[str, Any]:
    copy_body = dict(body)
    copy_body["signature_or_digest"] = PLACEHOLDER_DIGEST
    copy_body["signature_or_digest"] = canonical_hash(copy_body)
    return copy_body


def _violation(*, violation_id: str, violation_type: str, explanation: str) -> dict[str, str]:
    return {
        "violation_id": violation_id,
        "violation_type": violation_type,
        "explanation": explanation,
    }


def _dataset_body() -> dict[str, Any]:
    files = [
        {
            "path": "data/input.csv",
            "sha256": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "size_bytes": 123456,
            "media_type": "text/csv",
        },
    ]
    body: dict[str, Any] = {
        "schema_version": "v0",
        "dataset_id": DATASET_ID,
        "dataset_name": "conformance-input",
        "dataset_version": "1.0.0",
        "files": files,
        "aggregate_hash": dataset_aggregate_hash(files),
        "source_uri": "https://example.org/datasets/conformance-input/1.0.0",
        "source_repo": RUNNER_REPO,
        "source_commit": RUNNER_COMMIT,
        "license": "CC-BY-4.0",
        "created_at": "2026-05-18T00:00:00Z",
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return body


def _environment_body() -> dict[str, Any]:
    return {
        "schema_version": "v0",
        "environment_id": ENV_ID,
        "environment_kind": "uv",
        "os": "linux",
        "architecture": "x86_64",
        "language_runtimes": ["python==3.12.3"],
        "packages": ["numpy==2.1.0", "pandas==2.2.2"],
        "container_image": "",
        "container_digest": "",
        "hardware_summary": "conformance-runner",
        "source_repo": RUNNER_REPO,
        "source_commit": RUNNER_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }


def _run_body(*, exit_code: int = 0, code_commit: str = RUNNER_COMMIT) -> dict[str, Any]:
    return {
        "schema_version": "v0",
        "run_id": RUN_ID,
        "workflow_id": COMPUTATION_WORKFLOW_ID,
        "command": "python -m experiment.run --seed 42",
        "code_repo": RUNNER_REPO,
        "code_commit": code_commit,
        "dataset_receipt_ref": DATASET_ID,
        "environment_receipt_ref": ENV_ID,
        "started_at": "2026-05-18T00:00:01Z",
        "completed_at": "2026-05-18T00:00:10Z",
        "exit_code": exit_code,
        "stdout_hash": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "stderr_hash": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        "result_artifact_refs": [RESULT_ID],
        "source_repo": RUNNER_REPO,
        "source_commit": RUNNER_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }


def _result_body() -> dict[str, Any]:
    return {
        "schema_version": "v0",
        "result_id": RESULT_ID,
        "result_kind": "metric",
        "path": "outputs/metrics.json",
        "sha256": RESULT_SHA,
        "size_bytes": 2048,
        "media_type": "application/json",
        "description": "Primary reproducibility metric output",
        "produced_by_run": RUN_ID,
        "source_repo": RUNNER_REPO,
        "source_commit": RUNNER_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }


def _witness_body(
    *,
    dataset: dict[str, Any],
    environment: dict[str, Any],
    run_receipt: dict[str, Any],
    result: dict[str, Any],
    status: str = "CertificateChecked",
    violations: list[dict[str, str]] | None = None,
    dataset_hash: str | None = None,
    environment_hash: str | None = None,
    run_receipt_hash: str | None = None,
    result_hashes: list[str] | None = None,
    code_commit: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "v0",
        "witness_id": WITNESS_ID,
        "workflow_id": COMPUTATION_WORKFLOW_ID,
        "dataset_hash": dataset["aggregate_hash"] if dataset_hash is None else dataset_hash,
        "environment_hash": (
            receipt_body_digest(environment) if environment_hash is None else environment_hash
        ),
        "run_receipt_hash": (
            receipt_body_digest(run_receipt) if run_receipt_hash is None else run_receipt_hash
        ),
        "result_hashes": result_hashes
        if result_hashes is not None
        else [str(result["sha256"])],
        "code_repo": RUNNER_REPO,
        "code_commit": code_commit if code_commit is not None else run_receipt["code_commit"],
        "checker": "certifyedge",
        "checker_version": "0.1.0",
        "status": status,
        "violations": violations if violations is not None else [],
        "source_repo": CERTIFYEDGE_REPO,
        "source_commit": CERTIFYEDGE_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }


def workflow_profile_computation() -> dict[str, Any]:
    body = {
        "schema_version": "v0",
        "workflow_id": COMPUTATION_WORKFLOW_ID,
        "domain": "scientific_computation",
        "description": "Proof-carrying computational reproducibility for declared inputs, environment, command, and results.",
        "runtime_artifacts": [
            "DatasetReceipt.v0",
            "EnvironmentReceipt.v0",
            "ComputationRunReceipt.v0",
            "ResultArtifact.v0",
        ],
        "certificate_artifacts": ["ComputationWitness.v0"],
        "handoff_sequence": [
            "runtime_to_certificate",
            "certificate_to_bundle",
            "bundle_to_verifier",
            "signed_bundle_to_memory",
        ],
        "required_registry_entries": [
            "DatasetReceipt.v0",
            "EnvironmentReceipt.v0",
            "ComputationRunReceipt.v0",
            "ResultArtifact.v0",
            "ComputationWitness.v0",
            "ScienceClaimBundle.v0",
            "VerificationResult.v0",
            "SignedScienceClaimBundle.v0",
            "ReleaseManifest.v0",
            "HandoffManifest.v0",
            "ReleaseChainValidationResult.v0",
            "WorkflowProfile.v0",
        ],
        "required_admission_profile": "scientific_computation_reproducibility",
        "status_policy": {
            "policy_id": "pcs-v0.1-scientific-computation-lifecycle",
            "description": "Computation witnesses require hash alignment before CertificateChecked export.",
            "allowed_terminal_statuses": ["Rejected", "Stale"],
            "forbidden_transitions": [
                {"from_status": "Rejected", "to_status": "ProofChecked"},
            ],
        },
        "failure_modes": [
            "dataset_hash_mismatch",
            "environment_hash_mismatch",
            "result_hash_mismatch",
            "missing_code_commit",
            "unreproducible_command",
        ],
        "limitations_notice": (
            "This artifact is a proof-carrying computational reproducibility result. It verifies that "
            "declared inputs, environment metadata, code provenance, execution command, and result "
            "artifact hashes are internally consistent. It does not prove that the scientific model is "
            "true, that the dataset is unbiased, or that the result is externally valid."
        ),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def _valid_train() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    dataset = _with_digest(_dataset_body())
    environment = _with_digest(_environment_body())
    run_receipt = _with_digest(_run_body())
    result = _with_digest(_result_body())
    witness = _with_digest(
        _witness_body(
            dataset=dataset,
            environment=environment,
            run_receipt=run_receipt,
            result=result,
        ),
    )
    return dataset, environment, run_receipt, result, witness


def _patch_provenance(obj: Any, *, repo_substring: str, commit: str) -> None:
    if isinstance(obj, dict):
        repo = obj.get("source_repo")
        if isinstance(repo, str) and repo_substring.lower() in repo.lower():
            obj["source_commit"] = commit
        for value in obj.values():
            _patch_provenance(value, repo_substring=repo_substring, commit=commit)
    elif isinstance(obj, list):
        for item in obj:
            _patch_provenance(item, repo_substring=repo_substring, commit=commit)


def _adapt_science_bundle(
    witness_id: str,
    *,
    run_receipt_hash: str,
    dataset_hash: str,
) -> dict[str, Any]:
    src = examples_dir() / "science_claim_bundle.certified.valid.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    claim = data["claim_artifact"]
    claim["certificate_refs"] = [witness_id]
    claim["claim_text"] = (
        "The computation run reproduces declared inputs, environment, command, and result hashes."
    )
    claim["claim_kind"] = "temporal_claim"
    evidence = data["evidence_bundle"]
    evidence["certificate_refs"] = [witness_id]
    certs = data.get("certificates")
    if isinstance(certs, list) and certs and isinstance(certs[0], dict):
        certs[0]["certificate_id"] = witness_id
        certs[0]["trace_hash"] = run_receipt_hash
        certs[0]["spec_hash"] = dataset_hash
        certs[0]["property_id"] = "scientific_computation.reproducibility"
        _patch_provenance(certs[0], repo_substring="certifyedge", commit=CERTIFYEDGE_COMMIT)
    receipts = data.get("runtime_receipts")
    if isinstance(receipts, list) and receipts and isinstance(receipts[0], dict):
        receipts[0]["trace_hash"] = run_receipt_hash
        receipts[0]["receipt_id"] = f"receipt-{RUN_ID}"
        _patch_provenance(receipts[0], repo_substring="runner", commit=RUNNER_COMMIT)
        _patch_provenance(receipts[0], repo_substring="labtrust", commit=RUNNER_COMMIT)
    data["verification_policy"] = {
        "policy_id": COMPUTATION_WORKFLOW_ID,
        "required_checks": [
            "schema-valid",
            "computation-hash-alignment",
            "witness-status-checked",
        ],
    }
    _patch_provenance(data, repo_substring="labtrust", commit=RUNNER_COMMIT)
    _patch_provenance(data, repo_substring="certifyedge", commit=CERTIFYEDGE_COMMIT)
    return _with_digest(data)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    from pcs_core.release_fixtures import file_digest

    profiles = examples_dir() / "workflow_profiles"
    release = examples_dir() / "computation-release"
    invalid_root = examples_dir() / "computation-release-invalid"
    release.mkdir(parents=True, exist_ok=True)
    invalid_root.mkdir(parents=True, exist_ok=True)

    profile = workflow_profile_computation()
    _write_json(profiles / "scientific_computation_reproducibility.valid.json", profile)
    dataset, environment, run_receipt, result, witness = _valid_train()
    _write_json(release / "workflow_profile.v0.json", profile)
    _write_json(release / "dataset_receipt.json", dataset)
    _write_json(release / "environment_receipt.json", environment)
    _write_json(release / "computation_run_receipt.json", run_receipt)
    _write_json(release / "result_artifact.json", result)
    _write_json(release / "computation_witness.json", witness)
    _write_json(
        release / "science_claim_bundle.certified.json",
        _adapt_science_bundle(
            WITNESS_ID,
            run_receipt_hash=str(witness["run_receipt_hash"]),
            dataset_hash=str(witness["dataset_hash"]),
        ),
    )

    for name in ("verification_result.json", "signed_science_claim_bundle.json"):
        src = examples_dir() / f"{name.replace('.json', '')}.valid.json"
        if src.is_file():
            doc = json.loads(src.read_text(encoding="utf-8"))
            _normalize_fixture_commits(doc)
            _patch_provenance(doc, repo_substring="provability", commit=PF_COMMIT)
            if name == "verification_result.json":
                verified = doc.get("verified_input")
                if isinstance(verified, dict):
                    verified["certificate_id"] = WITNESS_ID
            if name == "signed_science_claim_bundle.json":
                scb = doc.get("science_claim_bundle")
                if isinstance(scb, dict):
                    claim = scb.get("claim_artifact")
                    if isinstance(claim, dict):
                        claim["certificate_refs"] = [WITNESS_ID]
                    certs = scb.get("certificates")
                    if isinstance(certs, list) and certs and isinstance(certs[0], dict):
                        certs[0]["certificate_id"] = WITNESS_ID
                        certs[0]["trace_hash"] = witness["run_receipt_hash"]
                    receipts = scb.get("runtime_receipts")
                    if isinstance(receipts, list) and receipts and isinstance(receipts[0], dict):
                        receipts[0]["trace_hash"] = witness["run_receipt_hash"]
                vrf = doc.get("verification_result")
                if isinstance(vrf, dict):
                    verified = vrf.get("verified_input")
                    if isinstance(verified, dict):
                        verified["certificate_id"] = WITNESS_ID
            _write_json(release / name, _with_digest(doc))

    certified = json.loads((release / "science_claim_bundle.certified.json").read_text(encoding="utf-8"))
    certified_digest = file_digest((release / "science_claim_bundle.certified.json").read_bytes())
    vrf_path = release / "verification_result.json"
    if vrf_path.is_file():
        vrf = json.loads(vrf_path.read_text(encoding="utf-8"))
        verified = vrf.get("verified_input")
        if not isinstance(verified, dict):
            verified = {}
            vrf["verified_input"] = verified
        verified["certificate_id"] = WITNESS_ID
        verified["trace_hash"] = witness.get("run_receipt_hash")
        verified["bundle_hash"] = certified_digest
        _write_json(vrf_path, _with_digest(vrf))
    signed_path = release / "signed_science_claim_bundle.json"
    if signed_path.is_file():
        signed = json.loads(signed_path.read_text(encoding="utf-8"))
        signed["signed_input_bundle_hash"] = certified_digest
        _write_json(signed_path, _with_digest(signed))

    certified = json.loads((release / "science_claim_bundle.certified.json").read_text(encoding="utf-8"))
    signed = json.loads((release / "signed_science_claim_bundle.json").read_text(encoding="utf-8"))

    manifest_body: dict[str, Any] = {
        "schema_version": "v0",
        "release_id": "release-pcs-v0.1-scientific-computation",
        "release_candidate": "pcs-v0.1-scientific-computation-conformance",
        "generated_at": "2026-05-18T12:00:00Z",
        "validation_profile": COMPUTATION_WORKFLOW_ID,
        "workflow_profile_id": COMPUTATION_WORKFLOW_ID,
        "chain_root": {
            "trace_hash": witness["run_receipt_hash"],
            "certificate_id": WITNESS_ID,
            "certified_bundle_hash": certified_digest,
            "signed_bundle_hash": file_digest(
                (release / "signed_science_claim_bundle.json").read_bytes(),
            ),
        },
        "release_chain_validation_result": {
            "path": "release_chain_validation_result.v0.json",
            "sha256": PLACEHOLDER_DIGEST,
        },
        "canonical_signed_bundle": {
            "path": "signed_science_claim_bundle.json",
            "sha256": file_digest(
                (release / "signed_science_claim_bundle.json").read_bytes(),
            ),
        },
        "canonical_claim_id": str(certified["claim_artifact"]["artifact_id"]),
        "limitations_notice": profile["limitations_notice"],
        "producer_repos": {
            "pcs_core": {"repo": PCS_CORE_REPO, "commit": PCS_COMMIT},
            "scientific_computation": {"repo": RUNNER_REPO, "commit": RUNNER_COMMIT},
            "certifyedge": {"repo": CERTIFYEDGE_REPO, "commit": CERTIFYEDGE_COMMIT},
            "provability_fabric": {"repo": PF_REPO, "commit": PF_COMMIT},
            "scientific_memory": {"repo": SM_REPO, "commit": PCS_COMMIT},
        },
        "artifacts": {},
        "release_status": "Validated",
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }

    validation: dict[str, Any] = {
        "schema_version": "v0",
        "validation_id": "validation-pcs-v0.1-scientific-computation",
        "release_id": manifest_body["release_id"],
        "release_candidate": manifest_body["release_candidate"],
        "workflow_profile_id": COMPUTATION_WORKFLOW_ID,
        "validator": "pcs-core",
        "validator_version": "0.1.0",
        "checked_at": manifest_body["generated_at"],
        "status": "ProofChecked",
        "checks": [
            {
                "check_id": "computation_dataset_hash_alignment",
                "description": "ComputationWitness dataset_hash matches DatasetReceipt",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ComputationWitness.v0.dataset_hash_matches_receipt",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "computation_environment_hash_alignment",
                "description": "ComputationWitness environment_hash matches EnvironmentReceipt",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ComputationWitness.v0.environment_hash_matches_receipt",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "computation_run_receipt_hash_alignment",
                "description": "ComputationWitness run_receipt_hash matches ComputationRunReceipt",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ComputationWitness.v0.run_receipt_hash_matches_declared_run",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "computation_result_hashes_alignment",
                "description": "ComputationWitness result_hashes match ResultArtifact",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ComputationWitness.v0.result_hashes_match_result_artifacts",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "computation_code_commit_present",
                "description": "ComputationWitness and run receipt carry non-zero code commits",
                "status": "passed",
                "details": {},
                "registry_check_refs": ["ComputationWitness.v0.code_commit_present"],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "computation_witness_status_checked",
                "description": "ComputationWitness status is CertificateChecked",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ComputationWitness.v0.computation_status_checked_for_release",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "computation_certifyedge_commit",
                "description": "ComputationWitness source_commit matches release manifest",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ComputationWitness.v0.source_commit_matches_release_manifest",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "computation_witness_signature_valid",
                "description": "ComputationWitness signature_or_digest is canonical",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ComputationWitness.v0.signature_or_digest_valid",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "release_manifest_integrity",
                "description": "Release manifest hashes and commit policy",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ReleaseManifest.v0.artifact_hashes_match_files",
                    "ReleaseManifest.v0.release_mode_commit_policy",
                ],
                "responsible_component": "pcs-core",
            },
            {
                "check_id": "verification_and_signed_bundle_hashes",
                "description": "Verification and signed bundle hash alignment",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "VerificationResult.v0.verified_input_bundle_hash_matches_certified",
                    "SignedScienceClaimBundle.v0.signed_input_bundle_hash_matches_certified",
                ],
                "responsible_component": "Provability Fabric",
            },
        ],
        "artifacts_checked": 0,
        "failure_codes": [],
        "source_repo": PCS_CORE_REPO,
        "source_commit": PCS_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }

    from pcs_core.registry_semantics import (
        build_deferred_registry_checks,
        collect_chain_registry_refs,
        deferral_reason,
        enforcement_layer,
        lookup_registry_check,
    )
    from pcs_core.workflow_profiles import required_release_blocking_refs_for_profile

    validation["deferred_registry_checks"] = build_deferred_registry_checks(validation["checks"])
    cited = collect_chain_registry_refs(validation["checks"])
    deferred_refs = {item["registry_ref"] for item in validation["deferred_registry_checks"]}
    for ref in sorted(
        required_release_blocking_refs_for_profile(COMPUTATION_WORKFLOW_ID) - cited - deferred_refs,
    ):
        found = lookup_registry_check(ref)
        if found is None:
            continue
        _artifact_type, check = found
        if enforcement_layer(check) == "release_chain":
            continue
        validation["deferred_registry_checks"].append(
            {
                "registry_ref": ref,
                "status": "deferred",
                "enforcement_location": enforcement_layer(check),
                "responsible_component": str(check.get("responsible_component", "pcs-core")),
                "reason": deferral_reason(str(check.get("check_id", ""))),
            },
        )
    validation["artifacts_checked"] = len(COMPUTATION_MANIFEST_ARTIFACTS)
    validation["signature_or_digest"] = canonical_hash(validation)
    _write_json(release / "release_chain_validation_result.v0.json", validation)

    artifact_specs = {
        "dataset_receipt.json": ("DatasetReceipt.v0", dataset),
        "environment_receipt.json": ("EnvironmentReceipt.v0", environment),
        "computation_run_receipt.json": ("ComputationRunReceipt.v0", run_receipt),
        "result_artifact.json": ("ResultArtifact.v0", result),
        "computation_witness.json": ("ComputationWitness.v0", witness),
        "science_claim_bundle.certified.json": ("ScienceClaimBundle.v0", certified),
        "workflow_profile.v0.json": ("WorkflowProfile.v0", profile),
    }
    for filename, (artifact_type, doc) in artifact_specs.items():
        path = release / filename
        _write_json(path, doc)
        manifest_body["artifacts"][filename] = {
            "artifact_type": artifact_type,
            "schema": f"schemas/{artifact_type}.schema.json",
            "producer": "pcs-core",
            "source_repo": PCS_CORE_REPO,
            "source_commit": PCS_COMMIT,
            "sha256": file_digest(path.read_bytes()),
        }
    for filename, artifact_type in (
        ("verification_result.json", "VerificationResult.v0"),
        ("signed_science_claim_bundle.json", "SignedScienceClaimBundle.v0"),
    ):
        path = release / filename
        if path.is_file():
            manifest_body["artifacts"][filename] = {
                "artifact_type": artifact_type,
                "schema": f"schemas/{artifact_type}.schema.json",
                "producer": "Provability Fabric",
                "source_repo": PF_REPO,
                "source_commit": PF_COMMIT,
                "sha256": file_digest(path.read_bytes()),
            }

    manifest_body["release_chain_validation_result"]["sha256"] = file_digest(
        (release / "release_chain_validation_result.v0.json").read_bytes(),
    )
    _write_json(release / "release_manifest.v0.json", _with_digest(manifest_body))

    def _write_invalid_case(
        case_name: str,
        builder: Callable[[], tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]],
    ) -> None:
        ds, env, run_doc, res, wit = builder()
        case_dir = invalid_root / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        for stale in case_dir.glob("*.json"):
            stale.unlink()
        _write_json(case_dir / "dataset_receipt.json", ds)
        _write_json(case_dir / "environment_receipt.json", env)
        _write_json(case_dir / "computation_run_receipt.json", run_doc)
        _write_json(case_dir / "result_artifact.json", res)
        _write_json(case_dir / "computation_witness.json", wit)

    def _invalid_dataset_hash_mismatch() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            dataset_hash="sha256:" + "f" * 64,
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_result_hash_mismatch() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            result_hashes=["sha256:" + "e" * 64],
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_missing_code_commit() -> tuple[dict[str, Any], ...]:
        ds, env, _, res, _ = _valid_train()
        zero = "0" * 40
        run_doc = _with_digest(_run_body(code_commit=zero))
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            code_commit=zero,
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_nonzero_exit_code() -> tuple[dict[str, Any], ...]:
        ds, env, _, res, _ = _valid_train()
        run_doc = _with_digest(_run_body(exit_code=1))
        wit = _witness_body(dataset=ds, environment=env, run_receipt=run_doc, result=res)
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_environment_digest_mismatch() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            environment_hash="sha256:" + "c" * 64,
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_rejected_witness() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            status="Rejected",
            violations=[
                _violation(
                    violation_id="viol-001",
                    violation_type="unreproducible_command",
                    explanation="Command hash does not match declared reproducibility profile.",
                ),
            ],
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_witness_undeclared_extra_result() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            result_hashes=[
                str(res["sha256"]),
                "sha256:" + "b" * 64,
            ],
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_manifest_result_absent_from_witness() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            result_hashes=["sha256:" + "c" * 64],
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_result_file_hash_ne_manifest() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        # Tamper payload sha256 but keep the prior signature_or_digest so digests diverge.
        tampered = dict(res)
        prior_digest = tampered["signature_or_digest"]
        tampered["sha256"] = "sha256:" + "d" * 64
        tampered["signature_or_digest"] = prior_digest
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=tampered,
            result_hashes=[str(tampered["sha256"])],
        )
        return ds, env, run_doc, tampered, _with_digest(wit)

    def _invalid_duplicate_result_hash() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        # Duplicate declared digests are encoded by repeating the result sha in a
        # companion artifact list on the witness side; extraction sees one ResultArtifact
        # but obligation evaluation rejects duplicate declared lists when injected.
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            result_hashes=[str(res["sha256"]), str(res["sha256"])],
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_empty_declared_nonempty_witness() -> tuple[dict[str, Any], ...]:
        # Represented as a witness with results but a result artifact whose sha256 is
        # stripped so declared extraction fails / empty declared is forced at validation.
        ds, env, run_doc, res, _ = _valid_train()
        empty_result = dict(res)
        empty_result["sha256"] = "sha256:" + "0" * 64
        empty_result = _with_digest(empty_result)
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            result_hashes=[str(res["sha256"])],
        )
        return ds, env, run_doc, empty_result, _with_digest(wit)

    def _invalid_missing_dataset_hash() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            dataset_hash="",
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_missing_environment_hash() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            environment_hash="",
        )
        return ds, env, run_doc, res, _with_digest(wit)

    def _invalid_missing_run_receipt_hash() -> tuple[dict[str, Any], ...]:
        ds, env, run_doc, res, _ = _valid_train()
        wit = _witness_body(
            dataset=ds,
            environment=env,
            run_receipt=run_doc,
            result=res,
            run_receipt_hash="",
        )
        return ds, env, run_doc, res, _with_digest(wit)

    for case_name, builder in {
        "dataset_hash_mismatch": _invalid_dataset_hash_mismatch,
        "result_hash_mismatch": _invalid_result_hash_mismatch,
        "missing_code_commit": _invalid_missing_code_commit,
        "nonzero_exit_code": _invalid_nonzero_exit_code,
        "environment_digest_mismatch": _invalid_environment_digest_mismatch,
        "rejected_computation_witness": _invalid_rejected_witness,
        "witness_undeclared_extra_result": _invalid_witness_undeclared_extra_result,
        "manifest_result_absent_from_witness": _invalid_manifest_result_absent_from_witness,
        "result_file_hash_ne_payload": _invalid_result_file_hash_ne_manifest,
        "duplicate_result_hash": _invalid_duplicate_result_hash,
        "empty_declared_nonempty_witness": _invalid_empty_declared_nonempty_witness,
        "missing_dataset_hash": _invalid_missing_dataset_hash,
        "missing_environment_hash": _invalid_missing_environment_hash,
        "missing_run_receipt_hash": _invalid_missing_run_receipt_hash,
    }.items():
        _write_invalid_case(case_name, builder)

    sm_report = {
        "allow_legacy": False,
        "bundle_shape": "pcs_core",
        "claim_id": manifest_body["canonical_claim_id"],
        "imported_at": manifest_body["generated_at"],
        "render_path": f"/pcs/workflows/{COMPUTATION_WORKFLOW_ID}/claims/{manifest_body['canonical_claim_id']}",
        "workflow_profile_id": COMPUTATION_WORKFLOW_ID,
        "workflow_profile_render_path": f"/pcs/workflows/{COMPUTATION_WORKFLOW_ID}/profile",
        "scientific_memory_commit": PCS_COMMIT,
        "source_bundle_path": "signed_science_claim_bundle.json",
        "stale_artifacts": [],
        "strict": True,
        "verification_status": "passed",
        "warnings": [],
        "source_commit": PCS_COMMIT,
        "source_repo": SM_REPO,
        "release_id": manifest_body["release_id"],
        "release_candidate": manifest_body["release_candidate"],
        "release_manifest_path": "release_manifest.v0.json",
        "validation_profile": COMPUTATION_WORKFLOW_ID,
        "release_chain_validation_id": validation["validation_id"],
        "release_chain_validation_status": validation["status"],
        "release_chain_validator": "pcs-core",
        "release_chain_checked_at": validation["checked_at"],
        "release_manifest_hash": canonical_hash(manifest_body),
    }
    _write_json(release / "scientific_memory_import_report.json", sm_report)
    manifest_body["artifacts"]["scientific_memory_import_report.json"] = {
        "artifact_type": "ScientificMemory.ImportReport.v0",
        "sha256": file_digest((release / "scientific_memory_import_report.json").read_bytes()),
    }

    dataset_digest = file_digest((release / "dataset_receipt.json").read_bytes())
    env_digest = file_digest((release / "environment_receipt.json").read_bytes())
    run_digest = file_digest((release / "computation_run_receipt.json").read_bytes())
    result_digest = file_digest((release / "result_artifact.json").read_bytes())
    witness_digest = file_digest((release / "computation_witness.json").read_bytes())
    certified_digest = file_digest((release / "science_claim_bundle.certified.json").read_bytes())

    handoff_to_certifyedge = _with_digest(
        {
            "schema_version": "v0",
            "handoff_id": "handoff-computation-runtime-to-certifyedge",
            "handoff_kind": "runtime_to_certificate",
            "from_component": "scientific-computation demo producer",
            "to_component": "CertifyEdge",
            "created_at": manifest_body["generated_at"],
            "source_repo": RUNNER_REPO,
            "source_commit": RUNNER_COMMIT,
            "input_artifacts": {
                "dataset_receipt.json": {"artifact_type": "DatasetReceipt.v0", "sha256": dataset_digest},
                "environment_receipt.json": {
                    "artifact_type": "EnvironmentReceipt.v0",
                    "sha256": env_digest,
                },
                "computation_run_receipt.json": {
                    "artifact_type": "ComputationRunReceipt.v0",
                    "sha256": run_digest,
                },
                "result_artifact.json": {"artifact_type": "ResultArtifact.v0", "sha256": result_digest},
            },
            "expected_outputs": {
                "computation_witness.json": {"artifact_type": "ComputationWitness.v0"},
            },
            "invariants": {
                "run_receipt_hash": witness["run_receipt_hash"],
                "dataset_hash": witness["dataset_hash"],
            },
            "status": "Validated",
            "signature_or_digest": PLACEHOLDER_DIGEST,
        },
    )
    _write_json(release / "handoff_to_certifyedge.json", handoff_to_certifyedge)
    _write_json(release / "handoff_manifest.runtime_to_certificate.v0.json", handoff_to_certifyedge)

    handoff_to_pf = _with_digest(
        {
            "schema_version": "v0",
            "handoff_id": "handoff-computation-to-pf",
            "handoff_kind": "bundle_to_verifier",
            "from_component": "CertifyEdge",
            "to_component": "Provability Fabric",
            "created_at": manifest_body["generated_at"],
            "source_repo": CERTIFYEDGE_REPO,
            "source_commit": CERTIFYEDGE_COMMIT,
            "input_artifacts": {
                "science_claim_bundle.certified.json": {
                    "artifact_type": "ScienceClaimBundle.v0",
                    "sha256": certified_digest,
                },
            },
            "expected_outputs": {
                "verification_result.json": {"artifact_type": "VerificationResult.v0"},
                "signed_science_claim_bundle.json": {
                    "artifact_type": "SignedScienceClaimBundle.v0",
                },
            },
            "invariants": {
                "witness_id": WITNESS_ID,
                "run_receipt_hash": witness["run_receipt_hash"],
                "certified_bundle_hash": certified_digest,
            },
            "status": "Validated",
            "signature_or_digest": PLACEHOLDER_DIGEST,
        },
    )
    _write_json(release / "handoff_to_pf.json", handoff_to_pf)
    _write_json(release / "handoff_manifest.bundle_to_verifier.v0.json", handoff_to_pf)

    handoff_cert_to_bundle = _with_digest(
        {
            "schema_version": "v0",
            "handoff_id": "handoff-computation-witness-to-bundle",
            "handoff_kind": "certificate_to_bundle",
            "from_component": "CertifyEdge",
            "to_component": "scientific-computation demo producer",
            "created_at": manifest_body["generated_at"],
            "source_repo": CERTIFYEDGE_REPO,
            "source_commit": CERTIFYEDGE_COMMIT,
            "input_artifacts": {
                "computation_witness.json": {
                    "artifact_type": "ComputationWitness.v0",
                    "sha256": witness_digest,
                },
            },
            "expected_outputs": {
                "science_claim_bundle.certified.json": {
                    "artifact_type": "ScienceClaimBundle.v0",
                },
            },
            "invariants": {
                "witness_id": WITNESS_ID,
                "run_receipt_hash": witness["run_receipt_hash"],
            },
            "status": "Validated",
            "signature_or_digest": PLACEHOLDER_DIGEST,
        },
    )
    _write_json(release / "handoff_manifest.certificate_to_bundle.v0.json", handoff_cert_to_bundle)

    signed_digest = file_digest((release / "signed_science_claim_bundle.json").read_bytes())
    handoff_signed_to_memory = _with_digest(
        {
            "schema_version": "v0",
            "handoff_id": "handoff-computation-signed-bundle-to-memory",
            "handoff_kind": "signed_bundle_to_memory",
            "from_component": "Provability Fabric",
            "to_component": "Scientific Memory",
            "created_at": manifest_body["generated_at"],
            "source_repo": PF_REPO,
            "source_commit": PF_COMMIT,
            "input_artifacts": {
                "signed_science_claim_bundle.json": {
                    "artifact_type": "SignedScienceClaimBundle.v0",
                    "sha256": signed_digest,
                },
            },
            "expected_outputs": {
                "scientific_memory_import_report.json": {
                    "artifact_type": "ScientificMemory.ImportReport.v0",
                },
            },
            "invariants": {
                "workflow_profile_id": COMPUTATION_WORKFLOW_ID,
                "claim_id": manifest_body["canonical_claim_id"],
            },
            "status": "Validated",
            "signature_or_digest": PLACEHOLDER_DIGEST,
        },
    )
    _write_json(
        release / "handoff_manifest.signed_bundle_to_memory.v0.json",
        handoff_signed_to_memory,
    )

    legacy_manifest = {
        "schema_version": "v0",
        "release_candidate": manifest_body["release_candidate"],
        "generated_at": manifest_body["generated_at"],
        "workflow_profile_id": COMPUTATION_WORKFLOW_ID,
        "pcs_core_commit": PCS_COMMIT,
        "scientific_computation_commit": RUNNER_COMMIT,
        "certifyedge_commit": CERTIFYEDGE_COMMIT,
        "provability_fabric_commit": PF_COMMIT,
        "scientific_memory_commit": PCS_COMMIT,
        "artifacts": {
            name: file_digest((release / name).read_bytes())
            for name in COMPUTATION_MANIFEST_ARTIFACTS
            if (release / name).is_file()
        },
    }
    _write_json(release / "RELEASE_FIXTURE_MANIFEST.json", legacy_manifest)

    from pcs_core.lean_materialize import patch_release_manifest_lean_refs

    patch_release_manifest_lean_refs(release, source_commit=PCS_COMMIT)

    _write_json(examples_dir() / "artifact_registry.valid.json", build_artifact_registry())

    root_examples = examples_dir()
    _write_json(root_examples / "dataset_receipt.valid.json", dataset)
    _write_json(root_examples / "environment_receipt.valid.json", environment)
    _write_json(root_examples / "computation_run_receipt.valid.json", run_receipt)
    _write_json(root_examples / "result_artifact.valid.json", result)
    _write_json(root_examples / "computation_witness.valid.json", witness)

    from pcs_core.shared_hash_vectors import write_shared_vectors

    write_shared_vectors(force=True)

    for rel in (
        "workflow_profile.v0.json",
        "dataset_receipt.json",
        "computation_witness.json",
        "release_manifest.v0.json",
        "release_chain_validation_result.v0.json",
        "handoff_to_certifyedge.json",
        "handoff_to_pf.json",
        "proof_obligation.v0.json",
        "lean_check_result.v0.json",
    ):
        validate_file(release / rel)
    validate_file(profiles / "scientific_computation_reproducibility.valid.json")
    validate_file(examples_dir() / "artifact_registry.valid.json")
    print(f"Wrote computation fixtures under {release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
