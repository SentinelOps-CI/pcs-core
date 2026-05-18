"""Builders for PCS Phase 2 protocol example artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.release_canonical import (
    LABTRUST_RC_CERTIFICATE_ID,
    LABTRUST_RC_CERTIFIED_BUNDLE_HASH,
    LABTRUST_RC_PCS_CORE_COMMIT,
    LABTRUST_RC_TRACE_HASH,
)

PCS_CORE_REPO = "https://github.com/SentinelOps-CI/pcs-core"
LABTRUST_REPO = "https://github.com/fraware/LabTrust-Gym"
CERTIFYEDGE_REPO = "https://github.com/fraware/CertifyEdge"
PF_REPO = "https://github.com/SentinelOps-CI/provability-fabric"
SM_REPO = "https://github.com/fraware/scientific-memory"

RELEASE_ID = "release-pcs-v0.1-labtrust-qc"
PCS_CORE_COMMIT = LABTRUST_RC_PCS_CORE_COMMIT

_ARTIFACT_MANIFEST_META: dict[str, dict[str, str]] = {
    "trace.json": {
        "artifact_type": "LabTrust.Trace.v0",
        "schema": "trace.json",
        "producer": "LabTrust-Gym",
        "source_repo": LABTRUST_REPO,
        "commit_key": "labtrust_gym_commit",
    },
    "runtime_receipt.json": {
        "artifact_type": "RuntimeReceipt.v0",
        "schema": "RuntimeReceipt.v0.schema.json",
        "producer": "LabTrust-Gym",
        "source_repo": LABTRUST_REPO,
        "commit_key": "labtrust_gym_commit",
    },
    "trace_certificate.json": {
        "artifact_type": "TraceCertificate.v0",
        "schema": "TraceCertificate.v0.schema.json",
        "producer": "CertifyEdge",
        "source_repo": CERTIFYEDGE_REPO,
        "commit_key": "certifyedge_commit",
    },
    "science_claim_bundle.pending.json": {
        "artifact_type": "ScienceClaimBundle.v0",
        "schema": "ScienceClaimBundle.v0.schema.json",
        "producer": "LabTrust-Gym",
        "source_repo": LABTRUST_REPO,
        "commit_key": "labtrust_gym_commit",
    },
    "science_claim_bundle.certified.json": {
        "artifact_type": "ScienceClaimBundle.v0",
        "schema": "ScienceClaimBundle.v0.schema.json",
        "producer": "LabTrust-Gym",
        "source_repo": LABTRUST_REPO,
        "commit_key": "labtrust_gym_commit",
    },
    "verification_result.json": {
        "artifact_type": "VerificationResult.v0",
        "schema": "VerificationResult.v0.schema.json",
        "producer": "Provability Fabric",
        "source_repo": PF_REPO,
        "commit_key": "provability_fabric_commit",
    },
    "signed_science_claim_bundle.json": {
        "artifact_type": "SignedScienceClaimBundle.v0",
        "schema": "SignedScienceClaimBundle.v0.schema.json",
        "producer": "Provability Fabric",
        "source_repo": PF_REPO,
        "commit_key": "provability_fabric_commit",
    },
    "scientific_memory_import_report.json": {
        "artifact_type": "ScientificMemory.ImportReport.v0",
        "schema": "scientific_memory_import_report.json",
        "producer": "Scientific Memory",
        "source_repo": SM_REPO,
        "commit_key": "scientific_memory_commit",
    },
}


def _legacy_artifact_hash(name: str) -> str:
    legacy = _load_legacy_release_manifest()
    artifacts = legacy.get("artifacts")
    if not isinstance(artifacts, dict) or name not in artifacts:
        raise ValueError(f"RELEASE_FIXTURE_MANIFEST.json missing artifact hash for {name}")
    return str(artifacts[name])


def _load_legacy_release_manifest() -> dict[str, Any]:
    from pcs_core.paths import examples_dir

    path = examples_dir() / "labtrust-release" / "RELEASE_FIXTURE_MANIFEST.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: manifest root must be an object")
    return data


def _with_digest(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["signature_or_digest"] = canonical_hash(out)
    return out


def labtrust_release_manifest_body(
    *,
    validation_artifact_path: str = "release_chain_validation_result.v0.json",
) -> dict[str, Any]:
    """ReleaseManifest.v0 derived from RELEASE_FIXTURE_MANIFEST.json on disk."""
    legacy = _load_legacy_release_manifest()
    legacy_artifacts = legacy.get("artifacts")
    if not isinstance(legacy_artifacts, dict):
        raise ValueError("RELEASE_FIXTURE_MANIFEST.json missing artifacts object")
    artifacts: dict[str, Any] = {}
    for name, digest in legacy_artifacts.items():
        meta = _ARTIFACT_MANIFEST_META[str(name)]
        commit_key = meta["commit_key"]
        source_commit = str(legacy[commit_key])
        artifacts[str(name)] = {
            "artifact_type": meta["artifact_type"],
            "schema": meta["schema"],
            "producer": meta["producer"],
            "source_repo": meta["source_repo"],
            "source_commit": source_commit,
            "sha256": str(digest),
        }
    pcs_commit = str(legacy.get("pcs_core_commit", PCS_CORE_COMMIT))
    certified_hash = str(legacy_artifacts["science_claim_bundle.certified.json"])
    signed_hash = str(legacy_artifacts["signed_science_claim_bundle.json"])
    validation_path = "release_chain_validation_result.v0.json"
    from pcs_core.paths import examples_dir
    from pcs_core.release_fixtures import file_digest

    validation_file = examples_dir() / "labtrust-release" / validation_path
    if validation_file.is_file():
        validation_digest = file_digest(validation_file.read_bytes())
    else:
        validation_digest = PLACEHOLDER_DIGEST
    return {
        "schema_version": "v0",
        "release_id": RELEASE_ID,
        "release_candidate": str(legacy.get("release_candidate", "pcs-v0.1.0-rc1")),
        "generated_at": str(legacy.get("generated_at", "2026-05-17T17:01:22Z")),
        "validation_profile": "labtrust-v0.1-release-chain",
        "workflow_profile_id": "labtrust.qc_release_v0.1",
        "chain_root": {
            "trace_hash": LABTRUST_RC_TRACE_HASH,
            "certificate_id": LABTRUST_RC_CERTIFICATE_ID,
            "certified_bundle_hash": certified_hash,
            "signed_bundle_hash": signed_hash,
        },
        "release_chain_validation_result": {
            "path": validation_artifact_path,
            "sha256": validation_digest,
        },
        "canonical_signed_bundle": {
            "path": "signed_science_claim_bundle.json",
            "sha256": signed_hash,
        },
        "canonical_claim_id": "claim-pcs-qc-release-v0.1",
        "limitations_notice": (
            "PCS v0.1 demonstrates a proof-carrying simulated lab workflow; "
            "it does not claim clinical validity or production certification."
        ),
        "producer_repos": {
            "pcs_core": {"repo": PCS_CORE_REPO, "commit": pcs_commit},
            "labtrust_gym": {
                "repo": LABTRUST_REPO,
                "commit": str(legacy["labtrust_gym_commit"]),
            },
            "certifyedge": {
                "repo": CERTIFYEDGE_REPO,
                "commit": str(legacy["certifyedge_commit"]),
            },
            "provability_fabric": {
                "repo": PF_REPO,
                "commit": str(legacy["provability_fabric_commit"]),
            },
            "scientific_memory": {
                "repo": SM_REPO,
                "commit": str(legacy["scientific_memory_commit"]),
            },
        },
        "artifacts": artifacts,
        "release_status": "Validated",
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }


def release_manifest_valid(*, for_examples_tree: bool = False) -> dict[str, Any]:
    validation_path = (
        "release_chain_validation_result.valid.json"
        if for_examples_tree
        else "release_chain_validation_result.v0.json"
    )
    return _with_digest(
        labtrust_release_manifest_body(validation_artifact_path=validation_path),
    )


def _handoff_base(
    *,
    handoff_id: str,
    handoff_kind: str,
    from_component: str,
    to_component: str,
    source_repo: str,
    source_commit: str,
    input_artifacts: dict[str, Any],
    expected_outputs: dict[str, Any],
    invariants: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "v0",
        "handoff_id": handoff_id,
        "handoff_kind": handoff_kind,
        "from_component": from_component,
        "to_component": to_component,
        "created_at": "2026-05-17T17:01:22Z",
        "source_repo": source_repo,
        "source_commit": source_commit,
        "input_artifacts": input_artifacts,
        "expected_outputs": expected_outputs,
        "invariants": invariants,
        "status": "Validated",
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }


def handoff_runtime_to_certificate() -> dict[str, Any]:
    legacy = _load_legacy_release_manifest()
    return _with_digest(
        _handoff_base(
            handoff_id="handoff-labtrust-runtime-to-certifyedge-rc",
            handoff_kind="runtime_to_certificate",
            from_component="LabTrust-Gym",
            to_component="CertifyEdge",
            source_repo=LABTRUST_REPO,
            source_commit=str(legacy["labtrust_gym_commit"]),
            input_artifacts={
                "trace.json": {
                    "artifact_type": "LabTrust.Trace.v0",
                    "sha256": _legacy_artifact_hash("trace.json"),
                },
                "runtime_receipt.json": {
                    "artifact_type": "RuntimeReceipt.v0",
                    "sha256": _legacy_artifact_hash("runtime_receipt.json"),
                },
            },
            expected_outputs={
                "trace_certificate.json": {"artifact_type": "TraceCertificate.v0"},
            },
            invariants={"trace_hash": LABTRUST_RC_TRACE_HASH},
        ),
    )


def handoff_certificate_to_bundle() -> dict[str, Any]:
    legacy = _load_legacy_release_manifest()
    return _with_digest(
        _handoff_base(
            handoff_id="handoff-certifyedge-to-labtrust-bundle-rc",
            handoff_kind="certificate_to_bundle",
            from_component="CertifyEdge",
            to_component="LabTrust-Gym",
            source_repo=CERTIFYEDGE_REPO,
            source_commit=str(legacy["certifyedge_commit"]),
            input_artifacts={
                "trace_certificate.json": {
                    "artifact_type": "TraceCertificate.v0",
                    "sha256": _legacy_artifact_hash("trace_certificate.json"),
                },
            },
            expected_outputs={
                "science_claim_bundle.certified.json": {
                    "artifact_type": "ScienceClaimBundle.v0",
                },
            },
            invariants={
                "certificate_id": LABTRUST_RC_CERTIFICATE_ID,
                "trace_hash": LABTRUST_RC_TRACE_HASH,
            },
        ),
    )


def handoff_manifest_valid() -> dict[str, Any]:
    return handoff_bundle_to_verifier()


def handoff_bundle_to_verifier() -> dict[str, Any]:
    legacy = _load_legacy_release_manifest()
    return _with_digest(
        _handoff_base(
            handoff_id="handoff-labtrust-to-pf-qc-release-v0.1",
            handoff_kind="bundle_to_verifier",
            from_component="LabTrust-Gym",
            to_component="Provability Fabric",
            source_repo=LABTRUST_REPO,
            source_commit=str(legacy["labtrust_gym_commit"]),
            input_artifacts={
                "science_claim_bundle.certified.json": {
                    "artifact_type": "ScienceClaimBundle.v0",
                    "sha256": LABTRUST_RC_CERTIFIED_BUNDLE_HASH,
                },
            },
            expected_outputs={
                "verification_result.json": {"artifact_type": "VerificationResult.v0"},
                "signed_science_claim_bundle.json": {
                    "artifact_type": "SignedScienceClaimBundle.v0",
                },
            },
            invariants={
                "certificate_id": LABTRUST_RC_CERTIFICATE_ID,
                "trace_hash": LABTRUST_RC_TRACE_HASH,
                "certified_bundle_hash": LABTRUST_RC_CERTIFIED_BUNDLE_HASH,
            },
        ),
    )


def handoff_signed_bundle_to_memory() -> dict[str, Any]:
    legacy = _load_legacy_release_manifest()
    return _with_digest(
        _handoff_base(
            handoff_id="handoff-pf-to-scientific-memory-rc",
            handoff_kind="signed_bundle_to_memory",
            from_component="Provability Fabric",
            to_component="Scientific Memory",
            source_repo=PF_REPO,
            source_commit=str(legacy["provability_fabric_commit"]),
            input_artifacts={
                "signed_science_claim_bundle.json": {
                    "artifact_type": "SignedScienceClaimBundle.v0",
                    "sha256": _legacy_artifact_hash("signed_science_claim_bundle.json"),
                },
            },
            expected_outputs={
                "scientific_memory_import_report.json": {
                    "artifact_type": "ScientificMemory.ImportReport.v0",
                },
            },
            invariants={
                "certificate_id": LABTRUST_RC_CERTIFICATE_ID,
                "trace_hash": LABTRUST_RC_TRACE_HASH,
            },
        ),
    )


_LABTRUST_FRAGMENT_ARTIFACTS = (
    "trace.json",
    "runtime_receipt.json",
    "science_claim_bundle.pending.json",
    "science_claim_bundle.certified.json",
)


def labtrust_release_fragment_valid(directory: Path | None = None) -> dict[str, Any]:
    """ComponentReleaseFragment.v0 for LabTrust-owned release evidence."""
    from pcs_core.paths import examples_dir
    from pcs_core.release_fixtures import file_digest

    legacy = _load_legacy_release_manifest()
    release_dir = directory or (examples_dir() / "labtrust-release")
    legacy_artifacts = legacy.get("artifacts")
    if not isinstance(legacy_artifacts, dict):
        raise ValueError("RELEASE_FIXTURE_MANIFEST.json missing artifacts object")
    artifacts: dict[str, Any] = {}
    for name in _LABTRUST_FRAGMENT_ARTIFACTS:
        digest = legacy_artifacts.get(name)
        if not isinstance(digest, str):
            continue
        meta = _ARTIFACT_MANIFEST_META[str(name)]
        artifacts[str(name)] = {
            "artifact_type": meta["artifact_type"],
            "sha256": digest,
        }
    manifest_path = release_dir / "release_manifest.v0.json"
    manifest_ref = {"path": "release_manifest.v0.json", "sha256": PLACEHOLDER_DIGEST}
    if manifest_path.is_file():
        manifest_ref["sha256"] = file_digest(manifest_path.read_bytes())
    body: dict[str, Any] = {
        "schema_version": "v0",
        "component": "LabTrust-Gym",
        "source_repo": LABTRUST_REPO,
        "source_commit": str(legacy["labtrust_gym_commit"]),
        "component_version": str(legacy.get("release_candidate", "pcs-v0.1.0-rc1")),
        "generated_at": str(legacy.get("generated_at", "2026-05-17T17:01:22Z")),
        "upstream_release_manifest": manifest_ref,
        "handoff_artifacts": ["handoff_manifest.runtime_to_certificate.v0.json"],
        "validation_summary": {
            "status": "ProofChecked",
            "checks_passed": 30,
            "checks_failed": 0,
        },
        "artifacts": artifacts,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def component_release_fragment_valid() -> dict[str, Any]:
    return labtrust_release_fragment_valid()


def release_chain_validation_result_valid() -> dict[str, Any]:
    """Full 30-check result for examples/, pinned to legacy manifest generated_at."""
    from pcs_core.paths import examples_dir
    from pcs_core.release_chain_report import build_release_chain_validation_result

    release_dir = examples_dir() / "labtrust-release"
    legacy = _load_legacy_release_manifest()
    checked_at = str(legacy.get("generated_at", "2026-05-17T17:01:22Z"))
    pcs_commit = str(legacy.get("pcs_core_commit", PCS_CORE_COMMIT))
    return build_release_chain_validation_result(
        release_dir,
        checked_at=checked_at,
        source_commit=pcs_commit,
    )


LABTRUST_HANDOFF_ARTIFACTS = {
    "handoff_manifest.runtime_to_certificate.v0.json": handoff_runtime_to_certificate,
    "handoff_manifest.certificate_to_bundle.v0.json": handoff_certificate_to_bundle,
    "handoff_manifest.bundle_to_verifier.v0.json": handoff_bundle_to_verifier,
    "handoff_manifest.signed_bundle_to_memory.v0.json": handoff_signed_bundle_to_memory,
}

LABTRUST_PROTOCOL_ARTIFACTS = {
    "release_manifest.v0.json": release_manifest_valid,
    "release_chain_validation_result.v0.json": release_chain_validation_result_valid,
    **LABTRUST_HANDOFF_ARTIFACTS,
}


def write_labtrust_protocol_artifacts(directory: Path) -> None:
    """Write Phase 2 protocol artifacts into a release fixture directory."""
    from pcs_core.release_chain_report import build_release_chain_validation_result

    directory.mkdir(parents=True, exist_ok=True)
    legacy = json.loads((directory / "RELEASE_FIXTURE_MANIFEST.json").read_text(encoding="utf-8"))
    checked_at = str(legacy.get("generated_at", "2026-05-17T17:01:22Z"))
    pcs_commit = str(legacy.get("pcs_core_commit", PCS_CORE_COMMIT))
    validation = build_release_chain_validation_result(
        directory,
        checked_at=checked_at,
        source_commit=pcs_commit,
    )
    (directory / "release_chain_validation_result.v0.json").write_text(
        json.dumps(validation, indent=2) + "\n",
        encoding="utf-8",
    )
    (directory / "release_manifest.v0.json").write_text(
        json.dumps(release_manifest_valid(), indent=2) + "\n",
        encoding="utf-8",
    )
    for filename, builder in LABTRUST_HANDOFF_ARTIFACTS.items():
        path = directory / filename
        path.write_text(json.dumps(builder(), indent=2) + "\n", encoding="utf-8")
    # PF CLI alias (HandoffManifest.v0); same payload as bundle_to_verifier stage handoff.
    (directory / "handoff_to_pf.json").write_text(
        json.dumps(handoff_bundle_to_verifier(), indent=2) + "\n",
        encoding="utf-8",
    )
    (directory / "labtrust_release_fragment.json").write_text(
        json.dumps(labtrust_release_fragment_valid(directory), indent=2) + "\n",
        encoding="utf-8",
    )
