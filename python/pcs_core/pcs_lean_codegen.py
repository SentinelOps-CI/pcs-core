"""Generate concrete Lean terms and proof obligations from PCS release-chain artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from pcs_core.asset_resolver import pcs_generated_root, proof_ref_from_path, require_lean_root
from pcs_core.lean_trust import extract_proof_obligations_from_release
from pcs_core.obligation_extraction_errors import (
    InvalidProofInputDigest,
    MissingArtifactStatus,
    MissingCertificateId,
    MissingObligationId,
    MissingReleaseId,
    MissingWitnessId,
    ObligationExtractionError,
)
from pcs_core.pcs_projection import (
    assert_no_unknown_or_empty,
    require_sha256_digest,
)

_LEAN_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")


def lean_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def lean_ident(prefix: str, raw: str) -> str:
    slug = _LEAN_IDENT_RE.sub("_", raw).strip("_")
    if not slug or slug[0].isdigit():
        slug = f"{prefix}_{slug or 'x'}"
    if "unknown" in slug.lower():
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"Lean identifier must not contain 'unknown' (got {slug!r})",
        )
    return slug


def artifact_status_to_lean(status: str) -> str:
    mapping = {
        "RuntimeObserved": "ArtifactStatus.RuntimeObserved",
        "CertificateChecked": "ArtifactStatus.CertificateChecked",
        "ProofChecked": "ArtifactStatus.ProofChecked",
        "Rejected": "ArtifactStatus.Rejected",
        "Stale": "ArtifactStatus.Stale",
        "Deprecated": "ArtifactStatus.Deprecated",
    }
    mapped = mapping.get(status)
    if mapped is None:
        raise MissingArtifactStatus(
            f"unsupported artifact status for Lean codegen: {status!r}",
        )
    return mapped


def hash_to_lean(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidProofInputDigest("empty proof-relevant hash cannot be emitted to Lean")
    require_sha256_digest(value, field="lean_hash")
    digest = value.removeprefix("sha256:")
    return f"Hash.ofString {lean_string_literal(digest)}"


def _require_obligation_digest(value: Any, *, field: str) -> str:
    return require_sha256_digest(value, field=field)


def _require_obligation_id_field(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        if "certificate" in field:
            raise MissingCertificateId(f"{field} is required")
        if "witness" in field:
            raise MissingWitnessId(f"{field} is required")
        raise MissingObligationId(f"{field} is required")
    return assert_no_unknown_or_empty(value.strip(), field=field)


def _require_status_field(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MissingArtifactStatus(f"{field} is required")
    return assert_no_unknown_or_empty(value.strip(), field=field)


def certificate_to_lean(
    *,
    name: str,
    certificate_id: str,
    trace_hash: str,
    status: str,
) -> str:
    return (
        f"def {name} : Certificate :=\n"
        "  {\n"
        f"    certificateId := {lean_string_literal(certificate_id)},\n"
        f"    traceHash := {hash_to_lean(trace_hash)},\n"
        f"    status := {artifact_status_to_lean(status)}\n"
        "  }"
    )


def runtime_receipt_to_lean(*, name: str, trace_hash: str, status: str) -> str:
    return (
        f"def {name} : RuntimeReceipt :=\n"
        "  {\n"
        f"    traceHash := {hash_to_lean(trace_hash)},\n"
        f"    status := {artifact_status_to_lean(status)}\n"
        "  }"
    )


def verification_result_to_lean(
    *,
    name: str,
    status: str,
    verified_input_bundle_hash: str,
    release_blocking_checks_passed: bool,
) -> str:
    return (
        f"def {name} : VerificationResult :=\n"
        "  {\n"
        f"    status := {artifact_status_to_lean(status)},\n"
        f"    verifiedInputBundleHash := {hash_to_lean(verified_input_bundle_hash)},\n"
        f"    releaseBlockingChecksPassed := {str(release_blocking_checks_passed).lower()}\n"
        "  }"
    )


def bundle_hash_to_lean(*, name: str, bundle_hash: str) -> str:
    return f"def {name} : Hash := {hash_to_lean(bundle_hash)}"


def _obligation_inputs(obligations_doc: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for entry in obligations_doc.get("obligations", []):
        if not isinstance(entry, dict):
            continue
        obligation_id = str(entry.get("obligation_id") or "")
        inputs = entry.get("inputs")
        if obligation_id and isinstance(inputs, dict):
            indexed[obligation_id] = dict(inputs)
    return indexed


def release_chain_values_from_obligations(
    obligations_doc: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract concrete PCS artifact field values from ProofObligation.v0.

    Fail-closed: never invent certificate IDs, statuses, or empty digests.
    """
    by_id = _obligation_inputs(obligations_doc)
    cert_inputs = by_id.get("trace_hash_alignment", {})
    verify_inputs = by_id.get("verification_admits_bundle", {})
    signed_inputs = by_id.get("signed_bundle_admissible", {})
    if not cert_inputs or not verify_inputs or not signed_inputs:
        raise ValueError("ProofObligation.v0 missing labtrust-style release-chain obligations")

    release_id = obligations_doc.get("release_id")
    if not isinstance(release_id, str) or not release_id.strip():
        raise MissingReleaseId("ProofObligation.v0.release_id is required")
    obligation_id = obligations_doc.get("obligation_id")
    if not isinstance(obligation_id, str) or not obligation_id.strip():
        raise MissingObligationId("ProofObligation.v0.obligation_id is required")

    return {
        "certificate_id": _require_obligation_id_field(
            cert_inputs.get("certificate_id"),
            field="certificate_id",
        ),
        "certificate_trace_hash": _require_obligation_digest(
            cert_inputs.get("certificate_trace_hash"),
            field="certificate_trace_hash",
        ),
        "certificate_status": _require_status_field(
            cert_inputs.get("certificate_status"),
            field="certificate_status",
        ),
        "runtime_trace_hash": _require_obligation_digest(
            cert_inputs.get("runtime_trace_hash"),
            field="runtime_trace_hash",
        ),
        "runtime_status": "RuntimeObserved",
        "verification_status": _require_status_field(
            verify_inputs.get("verification_status"),
            field="verification_status",
        ),
        "verified_input_bundle_hash": _require_obligation_digest(
            verify_inputs.get("verified_input_bundle_hash"),
            field="verified_input_bundle_hash",
        ),
        "release_blocking_checks_passed": bool(
            verify_inputs.get("release_blocking_checks_passed"),
        ),
        "certified_bundle_hash": _require_obligation_digest(
            verify_inputs.get("certified_bundle_hash"),
            field="certified_bundle_hash",
        ),
        "signed_input_bundle_hash": _require_obligation_digest(
            signed_inputs.get("signed_input_bundle_hash"),
            field="signed_input_bundle_hash",
        ),
        "release_id": assert_no_unknown_or_empty(release_id.strip(), field="release_id"),
        "obligation_id": assert_no_unknown_or_empty(
            obligation_id.strip(),
            field="obligation_id",
        ),
        "pcs_projection_manifest_hash": obligations_doc.get("pcs_projection_manifest_hash"),
    }


def generated_module_name(obligations_doc: Mapping[str, Any]) -> str:
    obligation_id = obligations_doc.get("obligation_id")
    if not isinstance(obligation_id, str) or not obligation_id.strip():
        raise MissingObligationId("ProofObligation.v0.obligation_id is required for module name")
    assert_no_unknown_or_empty(obligation_id.strip(), field="obligation_id")
    digest = obligation_id.removeprefix("proof-obligation-")
    return lean_ident("Obligation", digest)


def hash_list_to_lean(hashes: list[str]) -> str:
    if not hashes:
        return "[]"
    items = ", ".join(hash_to_lean(value) for value in hashes)
    return f"[{items}]"


def tool_use_trace_to_lean(
    *,
    name: str,
    trace_id: str,
    trace_hash: str,
    policy_hash: str,
) -> str:
    return (
        f"def {name} : ToolUseTrace :=\n"
        "  {\n"
        f"    traceId := {lean_string_literal(trace_id)},\n"
        f"    traceHash := {hash_to_lean(trace_hash)},\n"
        f"    policyHash := {hash_to_lean(policy_hash)}\n"
        "  }"
    )


def tool_use_certificate_to_lean(
    *,
    name: str,
    certificate_id: str,
    trace_hash: str,
    policy_hash: str,
    status: str,
) -> str:
    return (
        f"def {name} : ToolUseCertificate :=\n"
        "  {\n"
        f"    certificateId := {lean_string_literal(certificate_id)},\n"
        f"    traceHash := {hash_to_lean(trace_hash)},\n"
        f"    policyHash := {hash_to_lean(policy_hash)},\n"
        f"    status := {lean_string_literal(status)}\n"
        "  }"
    )


def computation_witness_to_lean(
    *,
    name: str,
    witness_id: str,
    dataset_hash: str,
    environment_hash: str,
    run_receipt_hash: str,
    result_hashes: list[str],
    status: str,
) -> str:
    return (
        f"def {name} : ComputationWitness :=\n"
        "  {\n"
        f"    witnessId := {lean_string_literal(witness_id)},\n"
        f"    datasetHash := {hash_to_lean(dataset_hash)},\n"
        f"    environmentHash := {hash_to_lean(environment_hash)},\n"
        f"    runReceiptHash := {hash_to_lean(run_receipt_hash)},\n"
        f"    resultHashes := {hash_list_to_lean(result_hashes)},\n"
        f"    status := {lean_string_literal(status)}\n"
        "  }"
    )


def tool_use_values_from_obligations(
    obligations_doc: Mapping[str, Any],
) -> dict[str, Any]:
    by_id = _obligation_inputs(obligations_doc)
    tool_inputs = by_id.get("tool_trace_hash_alignment", {})
    if not tool_inputs:
        raise ValueError("ProofObligation.v0 missing tool_trace_hash_alignment obligation")
    chain = release_chain_values_from_obligations(obligations_doc)
    return {
        **chain,
        "trace_id": _require_obligation_id_field(
            tool_inputs.get("certificate_id") or chain["certificate_id"],
            field="trace_id",
        ),
        "trace_hash": _require_obligation_digest(
            tool_inputs.get("trace_hash"),
            field="trace_hash",
        ),
        "policy_hash": _require_obligation_digest(
            tool_inputs.get("trace_policy_hash"),
            field="trace_policy_hash",
        ),
        "tool_certificate_trace_hash": _require_obligation_digest(
            tool_inputs.get("certificate_trace_hash"),
            field="certificate_trace_hash",
        ),
        "tool_certificate_policy_hash": _require_obligation_digest(
            tool_inputs.get("certificate_policy_hash"),
            field="certificate_policy_hash",
        ),
        "tool_certificate_status": _require_status_field(
            chain.get("certificate_status"),
            field="certificate_status",
        ),
    }


def declared_artifact_hashes_for_computation(values: Mapping[str, Any]) -> list[str]:
    """Return independently declared result-artifact digests (never from the witness alone)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values.get("declared_result_artifact_hashes") or []:
        digest = str(raw)
        if digest not in seen:
            seen.add(digest)
            ordered.append(digest)
    return ordered


def computation_values_from_obligations(
    obligations_doc: Mapping[str, Any],
    *,
    release_dir: Path | None = None,
) -> dict[str, Any]:
    del release_dir  # proof inputs must come from obligations; no filesystem fallbacks
    by_id = _obligation_inputs(obligations_doc)
    witness_inputs = by_id.get("computation_witness_hash_alignment", {})
    verify_inputs = by_id.get("verification_admits_bundle", {})
    signed_inputs = by_id.get("signed_bundle_admissible", {})
    if not witness_inputs or not verify_inputs or not signed_inputs:
        raise ValueError(
            "ProofObligation.v0 missing computation witness or release-chain obligations",
        )
    witness_hashes = witness_inputs.get("witness_result_hashes")
    if not isinstance(witness_hashes, list) or not witness_hashes:
        raise InvalidProofInputDigest("computation obligation missing witness_result_hashes")
    declared_hashes = witness_inputs.get("declared_result_artifact_hashes")
    if not isinstance(declared_hashes, list) or not declared_hashes:
        raise InvalidProofInputDigest(
            "computation obligation missing declared_result_artifact_hashes",
        )
    release_id = obligations_doc.get("release_id")
    if not isinstance(release_id, str) or not release_id.strip():
        raise MissingReleaseId("ProofObligation.v0.release_id is required")
    return {
        "witness_id": _require_obligation_id_field(
            witness_inputs.get("witness_id"),
            field="witness_id",
        ),
        "witness_result_hashes": [
            _require_obligation_digest(value, field=f"witness_result_hashes[{index}]")
            for index, value in enumerate(witness_hashes)
        ],
        "declared_result_artifact_hashes": [
            _require_obligation_digest(value, field=f"declared_result_artifact_hashes[{index}]")
            for index, value in enumerate(declared_hashes)
        ],
        "result_artifact_sha256": _require_obligation_digest(
            witness_inputs.get("result_artifact_sha256"),
            field="result_artifact_sha256",
        ),
        "witness_status": _require_status_field(
            witness_inputs.get("witness_status"),
            field="witness_status",
        ),
        "run_receipt_hash": _require_obligation_digest(
            witness_inputs.get("run_receipt_hash"),
            field="run_receipt_hash",
        ),
        "dataset_hash": _require_obligation_digest(
            witness_inputs.get("dataset_hash"),
            field="dataset_hash",
        ),
        "environment_hash": _require_obligation_digest(
            witness_inputs.get("environment_hash"),
            field="environment_hash",
        ),
        "verification_status": _require_status_field(
            verify_inputs.get("verification_status"),
            field="verification_status",
        ),
        "verified_input_bundle_hash": _require_obligation_digest(
            verify_inputs.get("verified_input_bundle_hash"),
            field="verified_input_bundle_hash",
        ),
        "release_blocking_checks_passed": bool(
            verify_inputs.get("release_blocking_checks_passed"),
        ),
        "certified_bundle_hash": _require_obligation_digest(
            verify_inputs.get("certified_bundle_hash"),
            field="certified_bundle_hash",
        ),
        "signed_input_bundle_hash": _require_obligation_digest(
            signed_inputs.get("signed_input_bundle_hash"),
            field="signed_input_bundle_hash",
        ),
        "release_id": assert_no_unknown_or_empty(release_id.strip(), field="release_id"),
        "pcs_projection_manifest_hash": obligations_doc.get("pcs_projection_manifest_hash"),
    }


def workflow_id_from_obligations(obligations_doc: Mapping[str, Any]) -> str:
    return str(obligations_doc.get("workflow_id") or "")


def aggregate_lean_theorem_for_workflow(workflow_id: str) -> str:
    if workflow_id == "agent_tool_use.safety_v0":
        return "concrete_tool_use_release_admissible_prop"
    if workflow_id == "scientific_computation.reproducibility_v0":
        return "concrete_computation_release_admissible_prop"
    return "concrete_envelope_release_admissible_prop"


def _require_projection_hash(values: Mapping[str, Any]) -> str:
    raw = values.get("pcs_projection_manifest_hash")
    return require_sha256_digest(raw, field="pcs_projection_manifest_hash")


def _envelope_projection_meta_definition(
    values: Mapping[str, Any],
    *,
    workflow_id: str,
    name: str = "concreteEnvelopeProjection",
) -> str:
    projection_hash = _require_projection_hash(values)
    release_id = assert_no_unknown_or_empty(
        str(values.get("release_id") or ""),
        field="release_id",
    )
    workflow = assert_no_unknown_or_empty(workflow_id, field="workflow_id")
    return (
        f"def {name} : EnvelopeProjectionMeta :=\n"
        "  {\n"
        f"    workflowId := {lean_string_literal(workflow)},\n"
        f"    releaseId := {lean_string_literal(release_id)},\n"
        f"    projectionDigest := {hash_to_lean(projection_hash)}\n"
        "  }"
    )


def _release_envelope_definition(
    values: Mapping[str, Any],
    *,
    workflow_id: str,
) -> str:
    projection_hash = _require_projection_hash(values)
    release_id = assert_no_unknown_or_empty(
        str(values.get("release_id") or ""),
        field="release_id",
    )
    workflow = assert_no_unknown_or_empty(workflow_id, field="workflow_id")
    return (
        "def concreteReleaseEnvelope : ReleaseEnvelope :=\n"
        "  {\n"
        f"    workflowId := {lean_string_literal(workflow)},\n"
        f"    releaseId := {lean_string_literal(release_id)},\n"
        f"    projectionDigest := {hash_to_lean(projection_hash)},\n"
        "    certificate := concreteCertificate,\n"
        "    runtimeReceipt := concreteRuntimeReceipt,\n"
        "    verification := concreteVerification,\n"
        "    certifiedBundleHash := concreteCertifiedBundleHash,\n"
        "    signedInputHash := concreteSignedInputHash\n"
        "  }"
    )


def _release_chain_definitions(
    values: Mapping[str, Any],
    *,
    workflow_id: str | None = None,
) -> str:
    parts = [
        certificate_to_lean(
            name="concreteCertificate",
            certificate_id=str(values["certificate_id"]),
            trace_hash=str(values["certificate_trace_hash"]),
            status=str(values["certificate_status"]),
        ),
        runtime_receipt_to_lean(
            name="concreteRuntimeReceipt",
            trace_hash=str(values["runtime_trace_hash"]),
            status=str(values.get("runtime_status") or "RuntimeObserved"),
        ),
        verification_result_to_lean(
            name="concreteVerification",
            status=str(values["verification_status"]),
            verified_input_bundle_hash=str(values["verified_input_bundle_hash"]),
            release_blocking_checks_passed=bool(values["release_blocking_checks_passed"]),
        ),
        bundle_hash_to_lean(
            name="concreteCertifiedBundleHash",
            bundle_hash=str(values["certified_bundle_hash"]),
        ),
        bundle_hash_to_lean(
            name="concreteSignedInputHash",
            bundle_hash=str(values["signed_input_bundle_hash"]),
        ),
    ]
    if workflow_id is not None:
        parts.append(_release_envelope_definition(values, workflow_id=workflow_id))
    return "\n\n".join(parts)


def _release_chain_theorems_block() -> str:
    return """
theorem concrete_certificate_matches_runtime :
    certificateMatchesRuntimeD concreteCertificate concreteRuntimeReceipt = true := by
  decide

theorem concrete_certificate_matches_runtime_prop :
    CertificateMatchesRuntime concreteCertificate concreteRuntimeReceipt :=
  (certificateMatchesRuntimeD_sound _ _).mp concrete_certificate_matches_runtime

theorem concrete_verification_admits_bundle :
    verificationAdmitsBundleD concreteVerification concreteCertifiedBundleHash = true := by
  decide

theorem concrete_verification_admits_bundle_prop :
    VerificationAdmitsBundle concreteVerification concreteCertifiedBundleHash :=
  (verificationAdmitsBundleD_sound _ _).mp concrete_verification_admits_bundle

theorem concrete_signed_bundle_admissible :
    signedBundleAdmissibleD concreteSignedInputHash
      concreteVerification.verifiedInputBundleHash = true := by
  decide

theorem concrete_signed_bundle_admissible_prop :
    SignedBundleAdmissible concreteSignedInputHash
      concreteVerification.verifiedInputBundleHash :=
  (signedBundleAdmissibleD_sound _ _).mp concrete_signed_bundle_admissible

theorem concrete_release_chain_admissible :
    releaseChainAdmissibleD concreteCertificate concreteRuntimeReceipt concreteVerification
      concreteCertifiedBundleHash concreteSignedInputHash = true := by
  decide

theorem concrete_release_chain_admissible_prop :
    ReleaseChainAdmissible concreteCertificate concreteRuntimeReceipt concreteVerification
      concreteCertifiedBundleHash concreteSignedInputHash :=
  (releaseChainAdmissibleD_sound _ _ _ _ _).mp concrete_release_chain_admissible

theorem concrete_envelope_release_admissible :
    envelopeReleaseAdmissibleD concreteReleaseEnvelope = true := by
  decide

theorem concrete_envelope_release_admissible_prop :
    EnvelopeReleaseAdmissible concreteReleaseEnvelope :=
  (envelopeReleaseAdmissibleD_sound _).mp concrete_envelope_release_admissible
""".strip()


def generate_release_chain_lean(obligations_doc: Mapping[str, Any]) -> str:
    values = release_chain_values_from_obligations(obligations_doc)
    workflow_id = workflow_id_from_obligations(obligations_doc)
    return _release_chain_definitions(values, workflow_id=workflow_id)


def generate_tool_use_lean(obligations_doc: Mapping[str, Any]) -> str:
    values = tool_use_values_from_obligations(obligations_doc)
    workflow_id = workflow_id_from_obligations(obligations_doc)
    tool_defs = "\n\n".join(
        [
            tool_use_trace_to_lean(
                name="concreteToolUseTrace",
                trace_id=values["trace_id"],
                trace_hash=values["trace_hash"],
                policy_hash=values["policy_hash"],
            ),
            tool_use_certificate_to_lean(
                name="concreteToolUseCertificate",
                certificate_id=values["certificate_id"],
                trace_hash=values["tool_certificate_trace_hash"],
                policy_hash=values["tool_certificate_policy_hash"],
                status=values["tool_certificate_status"],
            ),
            _release_chain_definitions(values, workflow_id=workflow_id),
        ],
    )
    return tool_defs


def generate_computation_lean(
    obligations_doc: Mapping[str, Any],
    *,
    release_dir: Path | None = None,
) -> str:
    values = computation_values_from_obligations(obligations_doc, release_dir=release_dir)
    workflow_id = workflow_id_from_obligations(obligations_doc)
    declared = declared_artifact_hashes_for_computation(values)
    witness_def = computation_witness_to_lean(
        name="concreteComputationWitness",
        witness_id=values["witness_id"],
        dataset_hash=values["dataset_hash"],
        environment_hash=values["environment_hash"],
        run_receipt_hash=values["run_receipt_hash"],
        result_hashes=values["witness_result_hashes"],
        status=values["witness_status"],
    )
    declared_def = (
        f"def concreteDeclaredResultArtifactHashes : List Hash :=\n  {hash_list_to_lean(declared)}"
    )
    result_hash_def = bundle_hash_to_lean(
        name="concreteResultArtifactHash",
        bundle_hash=values["result_artifact_sha256"],
    )
    verification_def = verification_result_to_lean(
        name="concreteVerification",
        status=values["verification_status"],
        verified_input_bundle_hash=values["verified_input_bundle_hash"],
        release_blocking_checks_passed=values["release_blocking_checks_passed"],
    )
    bundle_defs = "\n\n".join(
        [
            bundle_hash_to_lean(
                name="concreteCertifiedBundleHash",
                bundle_hash=values["certified_bundle_hash"],
            ),
            bundle_hash_to_lean(
                name="concreteSignedInputHash",
                bundle_hash=values["signed_input_bundle_hash"],
            ),
        ],
    )
    projection_meta = _envelope_projection_meta_definition(values, workflow_id=workflow_id)
    return "\n\n".join(
        [witness_def, declared_def, result_hash_def, verification_def, bundle_defs, projection_meta],
    )


def _tool_use_theorems_block() -> str:
    return (
        """
theorem concrete_tool_trace_hash_matches :
    toolTraceHashMatchesCertificateD concreteToolUseTrace concreteToolUseCertificate = true := by
  decide

theorem concrete_tool_trace_hash_matches_prop :
    toolTraceHashMatchesCertificate concreteToolUseTrace concreteToolUseCertificate :=
  (tool_trace_hash_matches_certificate _ _).mp concrete_tool_trace_hash_matches
""".strip()
        + "\n\n"
        + _release_chain_theorems_block()
        + """

theorem concrete_tool_use_release_admissible_prop :
    toolTraceHashMatchesCertificate concreteToolUseTrace concreteToolUseCertificate ∧
      EnvelopeReleaseAdmissible concreteReleaseEnvelope :=
  And.intro concrete_tool_trace_hash_matches_prop concrete_envelope_release_admissible_prop
""".rstrip()
    )


def _computation_theorems_block() -> str:
    return """
theorem concrete_witness_result_hashes_admissible :
    witnessResultHashesAdmissibleD concreteComputationWitness.resultHashes
      concreteDeclaredResultArtifactHashes = true := by
  decide

theorem concrete_witness_result_hashes_admissible_prop :
    witnessResultHashesAdmissible concreteComputationWitness
      concreteDeclaredResultArtifactHashes :=
  (witnessResultHashesAdmissibleD_sound _ _).mp concrete_witness_result_hashes_admissible

theorem concrete_witness_result_hash_listed :
    witnessResultHashListedD concreteComputationWitness.resultHashes
      concreteResultArtifactHash = true := by
  decide

theorem concrete_witness_result_hash_listed_prop :
    concreteResultArtifactHash ∈ concreteComputationWitness.resultHashes :=
  (witness_result_hash_listedD_sound _ _).mp concrete_witness_result_hash_listed

theorem concrete_verification_admits_bundle :
    verificationAdmitsBundleD concreteVerification concreteCertifiedBundleHash = true := by
  decide

theorem concrete_verification_admits_bundle_prop :
    VerificationAdmitsBundle concreteVerification concreteCertifiedBundleHash :=
  (verificationAdmitsBundleD_sound _ _).mp concrete_verification_admits_bundle

theorem concrete_signed_bundle_admissible :
    signedBundleAdmissibleD concreteSignedInputHash
      concreteVerification.verifiedInputBundleHash = true := by
  decide

theorem concrete_signed_bundle_admissible_prop :
    SignedBundleAdmissible concreteSignedInputHash
      concreteVerification.verifiedInputBundleHash :=
  (signedBundleAdmissibleD_sound _ _).mp concrete_signed_bundle_admissible

theorem concrete_envelope_projection_bound :
    envelopeProjectionBoundD concreteEnvelopeProjection = true := by
  decide

theorem concrete_envelope_projection_bound_prop :
    EnvelopeProjectionBound concreteEnvelopeProjection :=
  (envelopeProjectionBoundD_sound _).mp concrete_envelope_projection_bound

theorem concrete_computation_release_admissible_prop :
    EnvelopeProjectionBound concreteEnvelopeProjection ∧
      witnessResultHashesAdmissible concreteComputationWitness
        concreteDeclaredResultArtifactHashes ∧
      concreteResultArtifactHash ∈ concreteComputationWitness.resultHashes ∧
      VerificationAdmitsBundle concreteVerification concreteCertifiedBundleHash ∧
      SignedBundleAdmissible concreteSignedInputHash
        concreteVerification.verifiedInputBundleHash :=
  And.intro concrete_envelope_projection_bound_prop
    (And.intro concrete_witness_result_hashes_admissible_prop
      (And.intro concrete_witness_result_hash_listed_prop
        (And.intro concrete_verification_admits_bundle_prop concrete_signed_bundle_admissible_prop)))
""".strip()


def generate_proof_obligation_file(
    obligations_doc: Mapping[str, Any],
    out_dir: Path,
    *,
    release_dir: Path | None = None,
) -> Path:
    """Write a `.lean` file proving concrete PCS obligation discharge for a release fixture."""
    module = generated_module_name(obligations_doc)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{module}.lean"
    release_id_raw = obligations_doc.get("release_id")
    if not isinstance(release_id_raw, str) or not release_id_raw.strip():
        raise MissingReleaseId("ProofObligation.v0.release_id is required for Lean codegen")
    release_id = assert_no_unknown_or_empty(release_id_raw.strip(), field="release_id")
    workflow_id = workflow_id_from_obligations(obligations_doc)
    projection_hash = obligations_doc.get("pcs_projection_manifest_hash")
    proj = require_sha256_digest(
        projection_hash,
        field="pcs_projection_manifest_hash",
    )
    projection_meta = (
        f"\n-- pcs_projection_manifest_hash: {proj}\n"
        f"def pcsProjectionManifestHash : String := {lean_string_literal(proj)}\n"
    )

    if workflow_id == "agent_tool_use.safety_v0":
        imports = "import PCS.ToolUse\nimport PCS.ReleaseChainCheck"
        disclaimer = (
            "This discharges tool-use hash alignment plus release-chain obligations. "
            "It does **not** imply PF-Core trace safety or `LeanKernelChecked` assurance."
        )
        values_body = generate_tool_use_lean(obligations_doc)
        theorems = _tool_use_theorems_block()
        eval_line = ""
    elif workflow_id == "scientific_computation.reproducibility_v0":
        imports = "import PCS.ComputationWitness\nimport PCS.ReleaseChainCheck"
        disclaimer = (
            "This discharges computation witness result-hash admissibility against "
            "independently declared ResultArtifact digests "
            "(`concreteDeclaredResultArtifactHashes`) plus verification/signed bundle "
            "obligations. "
            "It does **not** imply PF-Core trace safety or `LeanKernelChecked`."
        )
        values_body = generate_computation_lean(obligations_doc, release_dir=release_dir)
        theorems = _computation_theorems_block()
        eval_line = ""
    else:
        imports = "import PCS.ReleaseChainCheck"
        disclaimer = (
            "This discharges ProofObligation.v0 against `PCS.EnvelopeReleaseAdmissible` "
            "(projection-bound release envelope). "
            "It does **not** imply PF-Core trace safety or `LeanKernelChecked` assurance."
        )
        values_body = generate_release_chain_lean(obligations_doc)
        theorems = _release_chain_theorems_block()
        eval_line = """
#eval envelopeReleaseAdmissibleD concreteReleaseEnvelope
""".strip()

    source = f"""{imports}

/-!
# Generated PCS release-chain proof for `{release_id}`

Auto-generated by pcs-core pcs-envelope check --lean-proof. Do not edit by hand.
{disclaimer}
-/

namespace PCS.Generated.{module}
{projection_meta}
{values_body}

{theorems}
{eval_line}

end PCS.Generated.{module}
"""
    # Fail closed: never emit unknown placeholders or empty Hash.ofString "".
    lowered = source.lower()
    for bad in ("cert-unknown", "release-unknown", "witness-unknown", "proof-obligation-unknown"):
        if bad in lowered:
            raise ObligationExtractionError(
                code="InvalidProofInputDigest",
                message=f"generated Lean contains forbidden placeholder {bad!r}",
            )
    if 'Hash.ofString ""' in source:
        raise InvalidProofInputDigest("generated Lean contains empty proof-relevant hash")

    out_path.write_text(source, encoding="utf-8")
    return out_path


def generate_from_release_dir(release_dir: Path, out_dir: Path) -> Path:
    obligations_doc = extract_proof_obligations_from_release(release_dir.resolve())
    return generate_proof_obligation_file(
        obligations_doc,
        out_dir,
        release_dir=release_dir.resolve(),
    )


def pcs_generated_dir() -> Path:
    try:
        return pcs_generated_root()
    except FileNotFoundError:
        from pcs_core.paths import repo_root

        return repo_root() / "lean" / "PCS" / "Generated"


def compute_lean_environment_hash() -> str:
    """Hash pinned Lean toolchain + lake manifest for PCS proof metadata."""
    try:
        lean_project = require_lean_root()
    except FileNotFoundError:
        from pcs_core.paths import repo_root

        lean_project = repo_root() / "lean"
    parts: list[str] = []
    toolchain = lean_project / "lean-toolchain"
    if not toolchain.is_file():
        # Historical mis-pin: lean-toolchain lived at repo root in some trees.
        from pcs_core.paths import repo_root

        alt = repo_root() / "lean-toolchain"
        if alt.is_file():
            toolchain = alt
    if toolchain.is_file():
        parts.append(toolchain.read_text(encoding="utf-8"))
    for rel in ("lakefile.lean", "lake-manifest.json"):
        path = lean_project / rel
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def proof_term_ref_from_path(path: Path) -> str:
    return proof_ref_from_path(path)
