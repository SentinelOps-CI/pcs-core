"""Generate concrete Lean terms and proof obligations from PCS release-chain artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.lean_trust import extract_proof_obligations_from_release
from pcs_core.paths import repo_root

_LEAN_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")


def lean_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def lean_ident(prefix: str, raw: str) -> str:
    slug = _LEAN_IDENT_RE.sub("_", raw).strip("_")
    if not slug or slug[0].isdigit():
        slug = f"{prefix}_{slug or 'x'}"
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
        raise ValueError(f"unsupported artifact status for Lean codegen: {status!r}")
    return mapped


def hash_to_lean(value: str) -> str:
    digest = value.removeprefix("sha256:")
    return f"Hash.ofString {lean_string_literal(digest)}"


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
    """Extract concrete PCS artifact field values from ProofObligation.v0."""
    by_id = _obligation_inputs(obligations_doc)
    cert_inputs = by_id.get("trace_hash_alignment", {})
    verify_inputs = by_id.get("verification_admits_bundle", {})
    signed_inputs = by_id.get("signed_bundle_admissible", {})
    if not cert_inputs or not verify_inputs or not signed_inputs:
        raise ValueError("ProofObligation.v0 missing labtrust-style release-chain obligations")

    certified_bundle_hash = str(verify_inputs.get("certified_bundle_hash") or "")
    verified_bundle_hash = str(verify_inputs.get("verified_input_bundle_hash") or "")
    signed_bundle_hash = str(signed_inputs.get("signed_input_bundle_hash") or "")

    return {
        "certificate_id": str(cert_inputs.get("certificate_id") or "cert-unknown"),
        "certificate_trace_hash": str(cert_inputs.get("certificate_trace_hash") or ""),
        "certificate_status": str(cert_inputs.get("certificate_status") or "CertificateChecked"),
        "runtime_trace_hash": str(cert_inputs.get("runtime_trace_hash") or ""),
        "runtime_status": "RuntimeObserved",
        "verification_status": str(verify_inputs.get("verification_status") or "ProofChecked"),
        "verified_input_bundle_hash": verified_bundle_hash,
        "release_blocking_checks_passed": bool(
            verify_inputs.get("release_blocking_checks_passed"),
        ),
        "certified_bundle_hash": certified_bundle_hash,
        "signed_input_bundle_hash": signed_bundle_hash,
        "release_id": str(obligations_doc.get("release_id") or "release-unknown"),
        "obligation_id": str(obligations_doc.get("obligation_id") or "proof-obligation-unknown"),
    }


def generated_module_name(obligations_doc: Mapping[str, Any]) -> str:
    obligation_id = str(
        obligations_doc.get("obligation_id") or canonical_hash(dict(obligations_doc))
    )
    digest = obligation_id.removeprefix("proof-obligation-")
    slug = lean_ident("Obligation", digest)
    return slug


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
        "trace_id": str(tool_inputs.get("certificate_id") or chain["certificate_id"]),
        "trace_hash": str(tool_inputs.get("trace_hash") or ""),
        "policy_hash": str(tool_inputs.get("trace_policy_hash") or ""),
        "tool_certificate_trace_hash": str(tool_inputs.get("certificate_trace_hash") or ""),
        "tool_certificate_policy_hash": str(tool_inputs.get("certificate_policy_hash") or ""),
        "tool_certificate_status": str(
            chain.get("certificate_status") or "CertificateChecked",
        ),
    }


def declared_artifact_hashes_for_computation(values: Mapping[str, Any]) -> list[str]:
    """Return the full witness `result_hashes` listing as the declared artifact digest set."""
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values.get("witness_result_hashes") or []:
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
    by_id = _obligation_inputs(obligations_doc)
    witness_inputs = by_id.get("computation_witness_hash_alignment", {})
    verify_inputs = by_id.get("verification_admits_bundle", {})
    signed_inputs = by_id.get("signed_bundle_admissible", {})
    if not witness_inputs or not verify_inputs or not signed_inputs:
        raise ValueError(
            "ProofObligation.v0 missing computation witness or release-chain obligations",
        )
    witness_hashes = witness_inputs.get("witness_result_hashes")
    if not isinstance(witness_hashes, list):
        witness_hashes = []
    result_sha = str(witness_inputs.get("result_artifact_sha256") or "")
    dataset_hash = result_sha
    environment_hash = result_sha
    if release_dir is not None:
        witness_path = release_dir / "computation_witness.json"
        if witness_path.is_file():
            witness_doc = json.loads(witness_path.read_text(encoding="utf-8"))
            if isinstance(witness_doc, dict):
                dataset_hash = str(witness_doc.get("dataset_hash") or dataset_hash)
                environment_hash = str(witness_doc.get("environment_hash") or environment_hash)
    return {
        "witness_id": str(witness_inputs.get("witness_id") or "witness-unknown"),
        "witness_result_hashes": [str(value) for value in witness_hashes],
        "result_artifact_sha256": result_sha,
        "witness_status": str(witness_inputs.get("witness_status") or "CertificateChecked"),
        "run_receipt_hash": str(witness_inputs.get("run_receipt_hash") or ""),
        "dataset_hash": dataset_hash,
        "environment_hash": environment_hash,
        "verification_status": str(verify_inputs.get("verification_status") or "ProofChecked"),
        "verified_input_bundle_hash": str(verify_inputs.get("verified_input_bundle_hash") or ""),
        "release_blocking_checks_passed": bool(
            verify_inputs.get("release_blocking_checks_passed"),
        ),
        "certified_bundle_hash": str(verify_inputs.get("certified_bundle_hash") or ""),
        "signed_input_bundle_hash": str(signed_inputs.get("signed_input_bundle_hash") or ""),
        "release_id": str(obligations_doc.get("release_id") or "release-unknown"),
    }


def workflow_id_from_obligations(obligations_doc: Mapping[str, Any]) -> str:
    return str(obligations_doc.get("workflow_id") or "")


def aggregate_lean_theorem_for_workflow(workflow_id: str) -> str:
    if workflow_id == "agent_tool_use.safety_v0":
        return "concrete_tool_use_release_admissible_prop"
    if workflow_id == "scientific_computation.reproducibility_v0":
        return "concrete_computation_release_admissible_prop"
    return "concrete_release_chain_admissible_prop"


def _release_chain_definitions(values: Mapping[str, Any]) -> str:
    return "\n\n".join(
        [
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
        ],
    )


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
""".strip()


def generate_release_chain_lean(obligations_doc: Mapping[str, Any]) -> str:
    values = release_chain_values_from_obligations(obligations_doc)
    return _release_chain_definitions(values)


def generate_tool_use_lean(obligations_doc: Mapping[str, Any]) -> str:
    values = tool_use_values_from_obligations(obligations_doc)
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
            _release_chain_definitions(values),
        ],
    )
    return tool_defs


def generate_computation_lean(
    obligations_doc: Mapping[str, Any],
    *,
    release_dir: Path | None = None,
) -> str:
    values = computation_values_from_obligations(obligations_doc, release_dir=release_dir)
    witness_def = computation_witness_to_lean(
        name="concreteComputationWitness",
        witness_id=values["witness_id"],
        dataset_hash=values["dataset_hash"],
        environment_hash=values["environment_hash"],
        run_receipt_hash=values["run_receipt_hash"],
        result_hashes=values["witness_result_hashes"],
        status=values["witness_status"],
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
    return "\n\n".join([witness_def, result_hash_def, verification_def, bundle_defs])


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
      ReleaseChainAdmissible concreteCertificate concreteRuntimeReceipt concreteVerification
        concreteCertifiedBundleHash concreteSignedInputHash :=
  And.intro concrete_tool_trace_hash_matches_prop concrete_release_chain_admissible_prop
""".rstrip()
    )


def _computation_theorems_block() -> str:
    return """
def concreteArtifactHashes : List Hash := witnessDeclaredArtifactHashes concreteComputationWitness

theorem concrete_witness_result_hashes_admissible :
    witnessResultHashesAdmissibleD concreteComputationWitness.resultHashes
      concreteArtifactHashes = true := by
  decide

theorem concrete_witness_result_hashes_admissible_prop :
    witnessResultHashesAdmissible concreteComputationWitness concreteArtifactHashes :=
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

theorem concrete_computation_release_admissible_prop :
    witnessResultHashesAdmissible concreteComputationWitness concreteArtifactHashes ∧
      concreteResultArtifactHash ∈ concreteComputationWitness.resultHashes ∧
      VerificationAdmitsBundle concreteVerification concreteCertifiedBundleHash ∧
      SignedBundleAdmissible concreteSignedInputHash
        concreteVerification.verifiedInputBundleHash :=
  And.intro concrete_witness_result_hashes_admissible_prop
    (And.intro concrete_witness_result_hash_listed_prop
      (And.intro concrete_verification_admits_bundle_prop concrete_signed_bundle_admissible_prop))
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
    release_id = str(obligations_doc.get("release_id") or "release-unknown")
    workflow_id = workflow_id_from_obligations(obligations_doc)

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
            "This discharges computation witness result-hash admissibility over the full "
            "witness `result_hashes` listing plus verification/signed bundle obligations. "
            "It does **not** imply PF-Core trace safety or `LeanKernelChecked`."
        )
        values_body = generate_computation_lean(obligations_doc, release_dir=release_dir)
        theorems = _computation_theorems_block()
        eval_line = ""
    else:
        imports = "import PCS.ReleaseChainCheck"
        disclaimer = (
            "This discharges ProofObligation.v0 against `PCS.ReleaseChainAdmissible` "
            "deciders only. "
            "It does **not** imply PF-Core trace safety or `LeanKernelChecked` assurance."
        )
        values_body = generate_release_chain_lean(obligations_doc)
        theorems = _release_chain_theorems_block()
        eval_line = """
#eval releaseChainAdmissibleD concreteCertificate concreteRuntimeReceipt concreteVerification
  concreteCertifiedBundleHash concreteSignedInputHash
""".strip()

    source = f"""{imports}

/-!
# Generated PCS release-chain proof for `{release_id}`

Auto-generated by pcs-core pcs-envelope check --lean-proof. Do not edit by hand.
{disclaimer}
-/

namespace PCS.Generated.{module}

{values_body}

{theorems}
{eval_line}

end PCS.Generated.{module}
"""
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
    return repo_root() / "lean" / "PCS" / "Generated"


def compute_lean_environment_hash() -> str:
    """Hash pinned Lean toolchain + lake manifest for PCS proof metadata."""
    lean_root = repo_root() / "lean"
    parts: list[str] = []
    toolchain = repo_root() / "lean-toolchain"
    if toolchain.is_file():
        parts.append(toolchain.read_text(encoding="utf-8"))
    for rel in ("lakefile.lean", "lake-manifest.json"):
        path = lean_root / rel
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def proof_term_ref_from_path(path: Path) -> str:
    root = repo_root()
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
