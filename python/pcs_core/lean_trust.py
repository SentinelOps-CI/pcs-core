"""PCS Lean trust kernel bridge: proof obligations and check results."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.lean_catalog import OBLIGATION_KIND_THEOREM
from pcs_core.obligation_extraction_errors import (
    MissingArtifactStatus,
    MissingCertificateId,
    MissingCertifiedBundleHash,
    MissingPolicyHash,
    MissingReleaseId,
    MissingSignedBundleHash,
    MissingTraceHash,
    MissingVerificationChecks,
    MissingVerifiedBundleHash,
    MissingWitnessId,
)
from pcs_core.paths import repo_root
from pcs_core.pcs_projection import (
    ProjectionManifestBuilder,
    assert_no_unknown_or_empty,
    projection_manifest_hash,
    require_sha256_digest,
)
from pcs_core.protocol_fixtures import PCS_CORE_REPO
from pcs_core.release_chain_profiles import detect_workflow_profile_id

LEAN_MODULE = "PCS.Theorems"
LEAN_VERSION = "leanprover/lean4:stable"

PCS_CORE_COMMIT_PLACEHOLDER = "d444444444444444444444444444444444444444"

PCS_LEAN_CHECK_DISCLAIMER = (
    "PCS release-envelope consistency check validates ProofObligation.v0 release-envelope "
    "consistency against the PCS theorem catalog. A `ProofChecked` or `EnvelopeLeanChecked` "
    "LeanCheckResult does not imply PF-Core trace safety. Use "
    "`pcs pf-core lean-check --trace <PFCoreTrace.v0.json>` for PF-Core kernel assurance."
)

PCS_ENVELOPE_LEAN_PROOF_DISCLAIMER = (
    "EnvelopeLeanChecked means a generated PCS release-chain module compiled with `lake env lean` "
    "and discharged `ReleaseChainAdmissible` deciders for the concrete obligation bundle. "
    "This is not LeanKernelChecked PF-Core trace safety."
)


def _file_digest(content: bytes) -> str:
    from pcs_core.release_fixtures import file_digest

    return file_digest(content)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _resolve_certified_bundle_hash(release_dir: Path) -> str:
    from pcs_core.bundle_identity import resolve_certified_bundle_identity_hash

    value = resolve_certified_bundle_identity_hash(release_dir)
    if not isinstance(value, str) or not value:
        raise MissingCertifiedBundleHash(
            f"{release_dir}: certified_bundle_hash could not be resolved",
            artifact="science_claim_bundle.certified.json",
        )
    return require_sha256_digest(
        value,
        field="/#resolved/certified_bundle_hash",
        artifact="science_claim_bundle.certified.json",
    )


def _require_verification_checks(verification: dict[str, Any]) -> list[dict[str, Any]]:
    checks = verification.get("checks")
    if not isinstance(checks, list) or not checks:
        raise MissingVerificationChecks()
    for index, item in enumerate(checks):
        if not isinstance(item, dict):
            raise MissingVerificationChecks(
                f"verification_result.checks[{index}] must be an object",
                field_path=f"/checks/{index}",
            )
        if not isinstance(item.get("check_id"), str) or not item.get("check_id"):
            raise MissingVerificationChecks(
                f"verification_result.checks[{index}].check_id is required",
                field_path=f"/checks/{index}/check_id",
            )
        if not isinstance(item.get("status"), str) or not item.get("status"):
            raise MissingVerificationChecks(
                f"verification_result.checks[{index}].status is required",
                field_path=f"/checks/{index}/status",
            )
    return checks


def _release_blocking_checks_passed(verification: dict[str, Any]) -> bool:
    if verification.get("status") != "ProofChecked":
        return False
    checks = _require_verification_checks(verification)
    for item in checks:
        status = item.get("status")
        if status in {"failed", "warning"}:
            return False
    return True


def _require_certificate_id(doc: dict[str, Any], *, artifact: str) -> str:
    value = doc.get("certificate_id")
    if not isinstance(value, str) or not value.strip():
        raise MissingCertificateId(artifact=artifact)
    return assert_no_unknown_or_empty(value.strip(), field="/certificate_id")


def _require_trace_hash(doc: dict[str, Any], *, artifact: str, field: str = "/trace_hash") -> str:
    value = doc.get("trace_hash")
    if not isinstance(value, str) or not value:
        raise MissingTraceHash(artifact=artifact, field_path=field)
    return require_sha256_digest(value, field=field, artifact=artifact)


def _require_status(doc: dict[str, Any], *, artifact: str) -> str:
    value = doc.get("status")
    if not isinstance(value, str) or not value.strip():
        raise MissingArtifactStatus(artifact=artifact)
    return assert_no_unknown_or_empty(value.strip(), field="/status")


def _require_verified_bundle_hash(verification: dict[str, Any]) -> str:
    verified = verification.get("verified_input")
    if not isinstance(verified, dict):
        raise MissingVerifiedBundleHash("verified_input object is required")
    value = verified.get("bundle_hash")
    if not isinstance(value, str) or not value:
        raise MissingVerifiedBundleHash()
    return require_sha256_digest(
        value,
        field="/verified_input/bundle_hash",
        artifact="verification_result.json",
    )


def _require_signed_bundle_hash(signed: dict[str, Any]) -> str:
    value = signed.get("signed_input_bundle_hash")
    if not isinstance(value, str) or not value:
        raise MissingSignedBundleHash()
    return require_sha256_digest(
        value,
        field="/signed_input_bundle_hash",
        artifact="signed_science_claim_bundle.json",
    )


def _obligation(
    *,
    obligation_id: str,
    kind: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "obligation_id": obligation_id,
        "kind": kind,
        "inputs": inputs,
    }


def _evaluate_obligation(kind: str, inputs: dict[str, Any]) -> tuple[bool, str]:
    if kind == "CertificateMatchesRuntime":
        cert_hash = inputs.get("certificate_trace_hash")
        runtime_hash = inputs.get("runtime_trace_hash")
        cert_status = inputs.get("certificate_status")
        if cert_hash != runtime_hash:
            return False, "certificate_trace_hash != runtime_trace_hash"
        if cert_status != "CertificateChecked":
            return False, f"certificate_status must be CertificateChecked, got {cert_status!r}"
        return True, ""

    if kind == "VerificationAdmitsBundle":
        if inputs.get("verification_status") != "ProofChecked":
            return False, "verification_status must be ProofChecked"
        if inputs.get("verified_input_bundle_hash") != inputs.get("certified_bundle_hash"):
            return False, "verified_input.bundle_hash != certified_bundle_hash"
        if not inputs.get("release_blocking_checks_passed"):
            return False, "release_blocking_checks_passed must be true"
        return True, ""

    if kind == "SignedBundleAdmissible":
        if inputs.get("signed_input_bundle_hash") != inputs.get("verified_input_bundle_hash"):
            return False, "signed_input_bundle_hash != verified_input_bundle_hash"
        return True, ""

    if kind == "ToolTraceHashMatchesCertificate":
        if inputs.get("certificate_trace_hash") != inputs.get("trace_hash"):
            return False, "certificate trace_hash != tool_use trace_hash"
        if inputs.get("certificate_policy_hash") != inputs.get("trace_policy_hash"):
            return False, "certificate policy_hash != trace policy_hash"
        return True, ""

    if kind == "ComputationWitnessHashAlignment":
        witness_hashes = inputs.get("witness_result_hashes")
        declared_hashes = inputs.get("declared_result_artifact_hashes")
        result_sha = inputs.get("result_artifact_sha256")
        if not isinstance(witness_hashes, list) or not isinstance(result_sha, str):
            return False, "missing witness_result_hashes or result_artifact_sha256"
        if not isinstance(declared_hashes, list):
            return False, "missing declared_result_artifact_hashes"
        if len(declared_hashes) != len(set(str(h) for h in declared_hashes)):
            return False, "declared_result_artifact_hashes contains duplicates"
        if not declared_hashes and witness_hashes:
            return (
                False,
                "empty declared_result_artifact_hashes with non-empty witness_result_hashes",
            )
        declared_set = {str(h) for h in declared_hashes}
        for witness_hash in witness_hashes:
            if str(witness_hash) not in declared_set:
                return False, "witness result hash not justified by declared_result_artifact_hashes"
        if result_sha not in witness_hashes:
            return False, "result artifact sha256 not listed in witness result_hashes"
        if result_sha not in declared_set:
            return False, "result artifact sha256 not listed in declared_result_artifact_hashes"
        if inputs.get("witness_status") != "CertificateChecked":
            return False, "witness_status must be CertificateChecked"
        return True, ""

    return False, f"unknown obligation kind {kind!r}"


def _extract_labtrust_obligations(
    release_dir: Path,
    *,
    projection: ProjectionManifestBuilder,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cert = _load_json(release_dir / "trace_certificate.json")
    receipt = _load_json(release_dir / "runtime_receipt.json")
    verification = _load_json(release_dir / "verification_result.json")
    signed = _load_json(release_dir / "signed_science_claim_bundle.json")
    certified = _load_json(release_dir / "science_claim_bundle.certified.json")
    if not all(isinstance(doc, dict) for doc in (cert, receipt, verification, signed, certified)):
        raise ValueError(f"{release_dir}: missing LabTrust trust-envelope artifacts")

    certificate_id = _require_certificate_id(cert, artifact="trace_certificate.json")
    certificate_trace_hash = _require_trace_hash(cert, artifact="trace_certificate.json")
    runtime_trace_hash = _require_trace_hash(receipt, artifact="runtime_receipt.json")
    certificate_status = _require_status(cert, artifact="trace_certificate.json")
    certified_bundle_hash = _resolve_certified_bundle_hash(release_dir)
    verified_bundle = _require_verified_bundle_hash(verification)
    signed_bundle_hash = _require_signed_bundle_hash(signed)
    verification_status = _require_status(verification, artifact="verification_result.json")
    release_blocking = _release_blocking_checks_passed(verification)

    projection.add(
        artifact_path="trace_certificate.json",
        json_pointer="/certificate_id",
        normalized_value=certificate_id,
        lean_identifier="concreteCertificate.certificateId",
    )
    projection.add(
        artifact_path="trace_certificate.json",
        json_pointer="/trace_hash",
        normalized_value=certificate_trace_hash,
        lean_identifier="concreteCertificate.traceHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="runtime_receipt.json",
        json_pointer="/trace_hash",
        normalized_value=runtime_trace_hash,
        lean_identifier="concreteRuntimeReceipt.traceHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="verification_result.json",
        json_pointer="/verified_input/bundle_hash",
        normalized_value=verified_bundle,
        lean_identifier="concreteVerification.verifiedInputBundleHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="#resolved/certified_bundle_hash",
        json_pointer="/#resolved/certified_bundle_hash",
        normalized_value=certified_bundle_hash,
        lean_identifier="concreteCertifiedBundleHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="signed_science_claim_bundle.json",
        json_pointer="/signed_input_bundle_hash",
        normalized_value=signed_bundle_hash,
        lean_identifier="concreteSignedInputHash",
        require_digest=True,
    )

    obligations = [
        _obligation(
            obligation_id="trace_hash_alignment",
            kind="CertificateMatchesRuntime",
            inputs={
                "certificate_id": certificate_id,
                "certificate_trace_hash": certificate_trace_hash,
                "runtime_trace_hash": runtime_trace_hash,
                "certificate_status": certificate_status,
            },
        ),
        _obligation(
            obligation_id="verification_admits_bundle",
            kind="VerificationAdmitsBundle",
            inputs={
                "verification_status": verification_status,
                "verified_input_bundle_hash": verified_bundle,
                "certified_bundle_hash": certified_bundle_hash,
                "release_blocking_checks_passed": release_blocking,
            },
        ),
        _obligation(
            obligation_id="signed_bundle_admissible",
            kind="SignedBundleAdmissible",
            inputs={
                "signed_input_bundle_hash": signed_bundle_hash,
                "verified_input_bundle_hash": verified_bundle,
            },
        ),
    ]
    source_artifacts = {
        "trace_certificate.json": {
            "path": "trace_certificate.json",
            "artifact_type": "TraceCertificate.v0",
        },
        "runtime_receipt.json": {
            "path": "runtime_receipt.json",
            "artifact_type": "RuntimeReceipt.v0",
        },
        "verification_result.json": {
            "path": "verification_result.json",
            "artifact_type": "VerificationResult.v0",
        },
        "signed_science_claim_bundle.json": {
            "path": "signed_science_claim_bundle.json",
            "artifact_type": "SignedScienceClaimBundle.v0",
        },
        "science_claim_bundle.certified.json": {
            "path": "science_claim_bundle.certified.json",
            "artifact_type": "ScienceClaimBundle.v0",
        },
    }
    return obligations, source_artifacts


def _extract_tool_use_obligations(
    release_dir: Path,
    *,
    projection: ProjectionManifestBuilder,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from pcs_core.release_chain_profiles import resolve_tool_use_artifact

    trace_path = resolve_tool_use_artifact(
        release_dir, ("tool_use_trace.valid.json", "tool_use_trace.json")
    )
    cert_path = resolve_tool_use_artifact(
        release_dir,
        ("tool_use_certificate.valid.json", "tool_use_certificate.json"),
    )
    if not trace_path or not cert_path:
        raise ValueError(f"{release_dir}: missing tool-use trace or certificate")
    trace = _load_json(trace_path)
    cert = _load_json(cert_path)
    receipt = _load_json(release_dir / "runtime_receipt.json")
    verification = _load_json(release_dir / "verification_result.json")
    signed = _load_json(release_dir / "signed_science_claim_bundle.json")
    if not all(isinstance(doc, dict) for doc in (trace, cert, receipt, verification, signed)):
        raise ValueError(f"{release_dir}: missing tool-use trust-envelope artifacts")

    certificate_id = _require_certificate_id(cert, artifact=cert_path.name)
    certificate_trace_hash = _require_trace_hash(cert, artifact=cert_path.name)
    runtime_trace_hash = _require_trace_hash(receipt, artifact="runtime_receipt.json")
    trace_hash = _require_trace_hash(trace, artifact=trace_path.name)
    certificate_status = _require_status(cert, artifact=cert_path.name)
    cert_policy = cert.get("policy_hash")
    trace_policy = trace.get("policy_hash")
    if not isinstance(cert_policy, str) or not cert_policy:
        raise MissingPolicyHash(artifact=cert_path.name)
    if not isinstance(trace_policy, str) or not trace_policy:
        raise MissingPolicyHash(artifact=trace_path.name, field_path="/policy_hash")
    certificate_policy_hash = require_sha256_digest(
        cert_policy,
        field="/policy_hash",
        artifact=cert_path.name,
    )
    trace_policy_hash = require_sha256_digest(
        trace_policy,
        field="/policy_hash",
        artifact=trace_path.name,
    )
    certified_bundle_hash = _resolve_certified_bundle_hash(release_dir)
    verified_bundle = _require_verified_bundle_hash(verification)
    signed_bundle_hash = _require_signed_bundle_hash(signed)
    verification_status = _require_status(verification, artifact="verification_result.json")
    release_blocking = _release_blocking_checks_passed(verification)

    projection.add(
        artifact_path=cert_path.name,
        json_pointer="/certificate_id",
        normalized_value=certificate_id,
        lean_identifier="concreteCertificate.certificateId",
    )
    projection.add(
        artifact_path=trace_path.name,
        json_pointer="/trace_hash",
        normalized_value=trace_hash,
        lean_identifier="concreteToolUseTrace.traceHash",
        require_digest=True,
    )
    projection.add(
        artifact_path=cert_path.name,
        json_pointer="/trace_hash",
        normalized_value=certificate_trace_hash,
        lean_identifier="concreteToolUseCertificate.traceHash",
        require_digest=True,
    )
    projection.add(
        artifact_path=trace_path.name,
        json_pointer="/policy_hash",
        normalized_value=trace_policy_hash,
        lean_identifier="concreteToolUseTrace.policyHash",
        require_digest=True,
    )
    projection.add(
        artifact_path=cert_path.name,
        json_pointer="/policy_hash",
        normalized_value=certificate_policy_hash,
        lean_identifier="concreteToolUseCertificate.policyHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="runtime_receipt.json",
        json_pointer="/trace_hash",
        normalized_value=runtime_trace_hash,
        lean_identifier="concreteRuntimeReceipt.traceHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="verification_result.json",
        json_pointer="/verified_input/bundle_hash",
        normalized_value=verified_bundle,
        lean_identifier="concreteVerification.verifiedInputBundleHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="#resolved/certified_bundle_hash",
        json_pointer="/#resolved/certified_bundle_hash",
        normalized_value=certified_bundle_hash,
        lean_identifier="concreteCertifiedBundleHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="signed_science_claim_bundle.json",
        json_pointer="/signed_input_bundle_hash",
        normalized_value=signed_bundle_hash,
        lean_identifier="concreteSignedInputHash",
        require_digest=True,
    )

    obligations = [
        _obligation(
            obligation_id="tool_trace_hash_alignment",
            kind="ToolTraceHashMatchesCertificate",
            inputs={
                "certificate_id": certificate_id,
                "certificate_trace_hash": certificate_trace_hash,
                "trace_hash": trace_hash,
                "certificate_policy_hash": certificate_policy_hash,
                "trace_policy_hash": trace_policy_hash,
            },
        ),
        _obligation(
            obligation_id="trace_hash_alignment",
            kind="CertificateMatchesRuntime",
            inputs={
                "certificate_id": certificate_id,
                "certificate_trace_hash": certificate_trace_hash,
                "runtime_trace_hash": runtime_trace_hash,
                "certificate_status": certificate_status,
            },
        ),
        _obligation(
            obligation_id="verification_admits_bundle",
            kind="VerificationAdmitsBundle",
            inputs={
                "verification_status": verification_status,
                "verified_input_bundle_hash": verified_bundle,
                "certified_bundle_hash": certified_bundle_hash,
                "release_blocking_checks_passed": release_blocking,
            },
        ),
        _obligation(
            obligation_id="signed_bundle_admissible",
            kind="SignedBundleAdmissible",
            inputs={
                "signed_input_bundle_hash": signed_bundle_hash,
                "verified_input_bundle_hash": verified_bundle,
            },
        ),
    ]
    source_artifacts = {
        trace_path.name: {"path": trace_path.name, "artifact_type": "ToolUseTrace.v0"},
        cert_path.name: {"path": cert_path.name, "artifact_type": "ToolUseCertificate.v0"},
        "runtime_receipt.json": {
            "path": "runtime_receipt.json",
            "artifact_type": "RuntimeReceipt.v0",
        },
        "verification_result.json": {
            "path": "verification_result.json",
            "artifact_type": "VerificationResult.v0",
        },
        "signed_science_claim_bundle.json": {
            "path": "signed_science_claim_bundle.json",
            "artifact_type": "SignedScienceClaimBundle.v0",
        },
    }
    return obligations, source_artifacts


def _extract_declared_result_artifact_hashes(release_dir: Path) -> list[str]:
    """Collect result artifact digests from ResultArtifact.v0 files and release manifest.

    Digests are taken from independently verified result artifacts / manifest entries —
    never from the computation witness itself.
    """
    declared: list[str] = []
    seen: set[str] = set()

    def _add(digest: str) -> None:
        if digest and digest not in seen:
            seen.add(digest)
            declared.append(digest)

    # Primary ResultArtifact.v0 beside the release.
    result_path = release_dir / "result_artifact.json"
    if result_path.is_file():
        result = _load_json(result_path)
        if isinstance(result, dict):
            sha = str(result.get("sha256") or "")
            if sha.startswith("sha256:"):
                _add(sha)

    # Additional ResultArtifact.v0 files if present.
    for path in sorted(release_dir.glob("result_artifact*.json")):
        if path.name == "result_artifact.json":
            continue
        doc = _load_json(path)
        if isinstance(doc, dict) and str(doc.get("artifact_type") or "") in {
            "ResultArtifact.v0",
            "",
        }:
            # Accept schema-typed or legacy untyped result artifacts with sha256.
            sha = str(doc.get("sha256") or "")
            if sha.startswith("sha256:"):
                _add(sha)

    manifest = _load_json(release_dir / "release_manifest.v0.json")
    if isinstance(manifest, dict):
        artifacts = manifest.get("artifacts")
        if isinstance(artifacts, dict):
            for name, meta in artifacts.items():
                if not isinstance(meta, dict):
                    continue
                artifact_type = str(meta.get("artifact_type") or "")
                if artifact_type != "ResultArtifact.v0" and not str(name).startswith(
                    "result_artifact"
                ):
                    continue
                # Prefer content hash of the result file when present; else manifest sha.
                rel = str(name)
                candidate = release_dir / rel
                if candidate.is_file():
                    doc = _load_json(candidate)
                    if isinstance(doc, dict):
                        sha = str(doc.get("sha256") or "")
                        if sha.startswith("sha256:"):
                            _add(sha)
                            continue
                sha = str(meta.get("sha256") or "")
                # Manifest file digests are content hashes of JSON files, not result
                # payload digests — only accept payload digests from ResultArtifact bodies.
                del sha

    if not declared:
        raise ValueError(
            f"{release_dir}: no independent ResultArtifact.v0 digests for "
            "declared_result_artifact_hashes"
        )
    return declared


def _extract_computation_obligations(
    release_dir: Path,
    *,
    projection: ProjectionManifestBuilder,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    witness = _load_json(release_dir / "computation_witness.json")
    result = _load_json(release_dir / "result_artifact.json")
    run_receipt = _load_json(release_dir / "computation_run_receipt.json")
    verification = _load_json(release_dir / "verification_result.json")
    signed = _load_json(release_dir / "signed_science_claim_bundle.json")
    if not all(
        isinstance(doc, dict) for doc in (witness, result, run_receipt, verification, signed)
    ):
        raise ValueError(f"{release_dir}: missing computation trust-envelope artifacts")

    witness_id_raw = witness.get("witness_id")
    if not isinstance(witness_id_raw, str) or not witness_id_raw.strip():
        raise MissingWitnessId()
    witness_id = assert_no_unknown_or_empty(witness_id_raw.strip(), field="/witness_id")

    dataset_hash = require_sha256_digest(
        witness.get("dataset_hash"),
        field="/dataset_hash",
        artifact="computation_witness.json",
    )
    environment_hash = require_sha256_digest(
        witness.get("environment_hash"),
        field="/environment_hash",
        artifact="computation_witness.json",
    )
    run_receipt_hash = require_sha256_digest(
        witness.get("run_receipt_hash"),
        field="/run_receipt_hash",
        artifact="computation_witness.json",
    )
    result_sha = require_sha256_digest(
        result.get("sha256"),
        field="/sha256",
        artifact="result_artifact.json",
    )
    witness_status = _require_status(witness, artifact="computation_witness.json")
    witness_hashes = witness.get("result_hashes")
    if not isinstance(witness_hashes, list) or not witness_hashes:
        from pcs_core.obligation_extraction_errors import InvalidProofInputDigest

        raise InvalidProofInputDigest(
            "computation_witness.result_hashes is required and must be non-empty",
            field_path="/result_hashes",
            artifact="computation_witness.json",
        )
    normalized_witness_hashes = [
        require_sha256_digest(
            item,
            field=f"/result_hashes/{index}",
            artifact="computation_witness.json",
        )
        for index, item in enumerate(witness_hashes)
    ]

    declared_hashes = _extract_declared_result_artifact_hashes(release_dir)
    certified_bundle_hash = _resolve_certified_bundle_hash(release_dir)
    verified_bundle = _require_verified_bundle_hash(verification)
    signed_bundle_hash = _require_signed_bundle_hash(signed)
    verification_status = _require_status(verification, artifact="verification_result.json")
    release_blocking = _release_blocking_checks_passed(verification)

    projection.add(
        artifact_path="computation_witness.json",
        json_pointer="/witness_id",
        normalized_value=witness_id,
        lean_identifier="concreteComputationWitness.witnessId",
    )
    projection.add(
        artifact_path="computation_witness.json",
        json_pointer="/dataset_hash",
        normalized_value=dataset_hash,
        lean_identifier="concreteComputationWitness.datasetHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="computation_witness.json",
        json_pointer="/environment_hash",
        normalized_value=environment_hash,
        lean_identifier="concreteComputationWitness.environmentHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="computation_witness.json",
        json_pointer="/run_receipt_hash",
        normalized_value=run_receipt_hash,
        lean_identifier="concreteComputationWitness.runReceiptHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="result_artifact.json",
        json_pointer="/sha256",
        normalized_value=result_sha,
        lean_identifier="concreteResultArtifactHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="verification_result.json",
        json_pointer="/verified_input/bundle_hash",
        normalized_value=verified_bundle,
        lean_identifier="concreteVerification.verifiedInputBundleHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="#resolved/certified_bundle_hash",
        json_pointer="/#resolved/certified_bundle_hash",
        normalized_value=certified_bundle_hash,
        lean_identifier="concreteCertifiedBundleHash",
        require_digest=True,
    )
    projection.add(
        artifact_path="signed_science_claim_bundle.json",
        json_pointer="/signed_input_bundle_hash",
        normalized_value=signed_bundle_hash,
        lean_identifier="concreteSignedInputHash",
        require_digest=True,
    )

    obligations = [
        _obligation(
            obligation_id="computation_witness_hash_alignment",
            kind="ComputationWitnessHashAlignment",
            inputs={
                "witness_id": witness_id,
                "witness_result_hashes": normalized_witness_hashes,
                "declared_result_artifact_hashes": declared_hashes,
                "result_artifact_sha256": result_sha,
                "witness_status": witness_status,
                "run_receipt_hash": run_receipt_hash,
                "dataset_hash": dataset_hash,
                "environment_hash": environment_hash,
            },
        ),
        _obligation(
            obligation_id="verification_admits_bundle",
            kind="VerificationAdmitsBundle",
            inputs={
                "verification_status": verification_status,
                "verified_input_bundle_hash": verified_bundle,
                "certified_bundle_hash": certified_bundle_hash,
                "release_blocking_checks_passed": release_blocking,
            },
        ),
        _obligation(
            obligation_id="signed_bundle_admissible",
            kind="SignedBundleAdmissible",
            inputs={
                "signed_input_bundle_hash": signed_bundle_hash,
                "verified_input_bundle_hash": verified_bundle,
            },
        ),
    ]
    source_artifacts = {
        "computation_witness.json": {
            "path": "computation_witness.json",
            "artifact_type": "ComputationWitness.v0",
        },
        "result_artifact.json": {
            "path": "result_artifact.json",
            "artifact_type": "ResultArtifact.v0",
        },
        "computation_run_receipt.json": {
            "path": "computation_run_receipt.json",
            "artifact_type": "ComputationRunReceipt.v0",
        },
        "verification_result.json": {
            "path": "verification_result.json",
            "artifact_type": "VerificationResult.v0",
        },
        "signed_science_claim_bundle.json": {
            "path": "signed_science_claim_bundle.json",
            "artifact_type": "SignedScienceClaimBundle.v0",
        },
    }
    return obligations, source_artifacts


def extract_proof_obligations_from_release(
    release_dir: Path,
    *,
    release_id: str | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Build ProofObligation.v0 from a release fixture directory.

    Fail-closed: never invent certificate IDs, statuses, or proof-relevant hashes.
    """
    release_dir = release_dir.resolve()
    workflow_id = detect_workflow_profile_id(release_dir) or "labtrust.qc_release_v0.1"

    manifest = _load_json(release_dir / "release_manifest.v0.json")
    resolved_release_id = release_id
    if not resolved_release_id and isinstance(manifest, dict):
        candidate = manifest.get("release_id")
        if isinstance(candidate, str) and candidate.strip():
            resolved_release_id = candidate.strip()
    if not resolved_release_id:
        raise MissingReleaseId(
            f"{release_dir}: release_id must be declared on release_manifest.v0.json "
            "or passed explicitly",
        )
    resolved_release_id = assert_no_unknown_or_empty(resolved_release_id, field="release_id")

    projection = ProjectionManifestBuilder(
        release_dir=release_dir,
        release_id=resolved_release_id,
        workflow_id=workflow_id,
    )

    if workflow_id == "agent_tool_use.safety_v0":
        obligations, source_artifacts = _extract_tool_use_obligations(
            release_dir,
            projection=projection,
        )
    elif workflow_id == "scientific_computation.reproducibility_v0":
        obligations, source_artifacts = _extract_computation_obligations(
            release_dir,
            projection=projection,
        )
    else:
        obligations, source_artifacts = _extract_labtrust_obligations(
            release_dir,
            projection=projection,
        )

    projection_doc = projection.build()
    proj_hash = projection_manifest_hash(projection_doc)

    body: dict[str, Any] = {
        "schema_version": "v0",
        "obligation_id": f"proof-obligation-{resolved_release_id}",
        "release_id": resolved_release_id,
        "workflow_id": workflow_id,
        "obligations": obligations,
        "source_artifacts": source_artifacts,
        "pcs_projection_manifest": projection_doc,
        "pcs_projection_manifest_hash": proj_hash,
        "lean_module": LEAN_MODULE,
        "source_repo": PCS_CORE_REPO,
        "source_commit": source_commit or PCS_CORE_COMMIT_PLACEHOLDER,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body


def run_lean_build() -> tuple[bool, str]:
    lean_dir = repo_root() / "lean"
    try:
        proc = subprocess.run(
            ["lake", "build"],
            cwd=lean_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "lake executable not found (install Lean/elan)"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "lake build failed").strip()
    return True, ""


def run_lean_check(
    obligations_doc: dict[str, Any],
    *,
    check_id: str | None = None,
    source_commit: str | None = None,
    require_lean_build: bool = True,
    lean_proof: bool = False,
) -> dict[str, Any]:
    """Evaluate obligations against the fixed PCS theorem set; emit LeanCheckResult.v0."""
    import sys

    from pcs_core.pcs_lean_codegen import (
        aggregate_lean_theorem_for_workflow,
        compute_lean_environment_hash,
        generate_proof_obligation_file,
        generated_module_name,
        proof_term_ref_from_path,
        workflow_id_from_obligations,
    )

    print(PCS_LEAN_CHECK_DISCLAIMER, file=sys.stderr)
    if lean_proof:
        print(PCS_ENVELOPE_LEAN_PROOF_DISCLAIMER, file=sys.stderr)

    build_ok, build_reason = run_lean_build() if require_lean_build else (True, "")
    obligation_results: list[dict[str, Any]] = []
    failures: list[str] = []

    for entry in obligations_doc.get("obligations", []):
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind", ""))
        obligation_id = str(entry.get("obligation_id", ""))
        inputs = entry.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}
        passed, reason = _evaluate_obligation(kind, inputs)
        theorem = OBLIGATION_KIND_THEOREM.get(kind, "unknown")
        obligation_results.append(
            {
                "obligation_id": obligation_id,
                "kind": kind,
                "status": "passed" if passed else "failed",
                "lean_theorem": theorem,
                "failure_reason": reason,
            },
        )
        if not passed:
            failures.append(f"{obligation_id}: {reason}")

    lean_proof_checked = False
    proof_term_ref: str | None = None
    proof_term_hash: str | None = None
    lean_environment_hash: str | None = None
    claim_class = "ProofChecked"

    if lean_proof and not failures:
        from pcs_core.lean_check import run_pcs_lean_concrete_proof

        lean_environment_hash = compute_lean_environment_hash()
        generated_dir = repo_root() / "lean" / "PCS" / "Generated"
        module = generated_module_name(obligations_doc)
        proof_path = generate_proof_obligation_file(obligations_doc, generated_dir)
        proof_term_ref = proof_term_ref_from_path(proof_path)
        proof_ok, proof_detail = run_pcs_lean_concrete_proof(
            proof_path,
            skip_build=not require_lean_build,
        )
        if proof_ok:
            lean_proof_checked = True
            claim_class = "EnvelopeLeanChecked"
            from pcs_core.lean_check import compute_proof_term_hash

            proof_term_hash = compute_proof_term_hash(proof_path)
            workflow_id = workflow_id_from_obligations(obligations_doc)
            aggregate_theorem = aggregate_lean_theorem_for_workflow(workflow_id)
            obligation_results.append(
                {
                    "obligation_id": f"generated_{module}",
                    "kind": "ReleaseChainAdmissible",
                    "status": "passed",
                    "lean_theorem": aggregate_theorem,
                    "failure_reason": "",
                },
            )
        else:
            failures.append(f"lean_proof: {proof_detail}")

    if require_lean_build and not build_ok:
        failures.insert(0, f"lean_build: {build_reason}")

    all_passed = not failures
    status = "ProofChecked" if all_passed else "Rejected"
    checked_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    raw_obligation_id = obligations_doc.get("obligation_id")
    if not isinstance(raw_obligation_id, str) or not raw_obligation_id.strip():
        from pcs_core.obligation_extraction_errors import MissingObligationId

        raise MissingObligationId(
            "ProofObligation.v0.obligation_id is required for LeanCheckResult"
        )
    proof_obligation_id = assert_no_unknown_or_empty(
        raw_obligation_id.strip(),
        field="obligation_id",
    )

    disclaimer = PCS_LEAN_CHECK_DISCLAIMER
    if lean_proof:
        disclaimer = f"{PCS_LEAN_CHECK_DISCLAIMER} {PCS_ENVELOPE_LEAN_PROOF_DISCLAIMER}"

    projection_hash = obligations_doc.get("pcs_projection_manifest_hash")
    if projection_hash is not None:
        projection_hash = require_sha256_digest(
            projection_hash,
            field="/pcs_projection_manifest_hash",
            artifact="ProofObligation.v0",
        )

    body: dict[str, Any] = {
        "schema_version": "v0",
        "check_id": check_id or f"lean-check-{proof_obligation_id}",
        "proof_obligation_id": proof_obligation_id,
        "lean_module": str(obligations_doc.get("lean_module", LEAN_MODULE)),
        "lean_theorem": "ReleaseChainAdmissible",
        "status": status,
        "claim_class": claim_class if all_passed else "Rejected",
        "checked_at": checked_at,
        "lean_version": LEAN_VERSION,
        "source_repo": PCS_CORE_REPO,
        "source_commit": source_commit
        or str(obligations_doc.get("source_commit", PCS_CORE_COMMIT_PLACEHOLDER)),
        "failure_reason": "; ".join(failures),
        "obligation_results": obligation_results,
        "lean_proof_checked": lean_proof_checked,
        "disclaimer": disclaimer,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    if projection_hash:
        body["pcs_projection_manifest_hash"] = projection_hash
    if proof_term_ref:
        body["proof_term_ref"] = proof_term_ref
    if proof_term_hash:
        body["proof_term_hash"] = proof_term_hash
    if lean_environment_hash:
        body["lean_environment_hash"] = lean_environment_hash
    body["signature_or_digest"] = canonical_hash(body)
    return body


def formal_checks_from_lean_result(lean_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Map LeanCheckResult.v0 obligation_results to ReleaseChainValidationResult formal_checks."""
    checks: list[dict[str, Any]] = []
    for item in lean_result.get("obligation_results", []):
        if not isinstance(item, dict):
            continue
        theorem = str(item.get("lean_theorem", "unknown"))
        checks.append(
            {
                "check_id": f"lean.{theorem}",
                "status": "passed" if item.get("status") == "passed" else "failed",
                "artifact": "lean_check_result.v0.json",
                "lean_theorem": theorem,
            },
        )
    if checks:
        checks.append(
            {
                "check_id": "lean.kernel_build",
                "status": "passed" if lean_result.get("status") == "ProofChecked" else "failed",
                "artifact": "lean_check_result.v0.json",
                "lean_theorem": "ReleaseChainAdmissible",
            },
        )
    return checks


def write_proof_obligations_for_release(
    release_dir: Path,
    out_path: Path | None = None,
) -> Path:
    release_dir = release_dir.resolve()
    out = out_path or (release_dir / "proof_obligation.v0.json")
    manifest = _load_json(release_dir / "release_manifest.v0.json")
    commit = None
    if manifest:
        pcs = manifest.get("producer_repos")
        if isinstance(pcs, dict):
            core = pcs.get("pcs_core")
            if isinstance(core, dict) and isinstance(core.get("commit"), str):
                commit = core["commit"]
    doc = extract_proof_obligations_from_release(release_dir, source_commit=commit)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return out
