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
    obligation_id = str(obligations_doc.get("obligation_id") or canonical_hash(dict(obligations_doc)))
    digest = obligation_id.removeprefix("proof-obligation-")
    slug = lean_ident("Obligation", digest)
    return slug


def generate_release_chain_lean(obligations_doc: Mapping[str, Any]) -> str:
    values = release_chain_values_from_obligations(obligations_doc)
    return "\n\n".join(
        [
            certificate_to_lean(
                name="concreteCertificate",
                certificate_id=values["certificate_id"],
                trace_hash=values["certificate_trace_hash"],
                status=values["certificate_status"],
            ),
            runtime_receipt_to_lean(
                name="concreteRuntimeReceipt",
                trace_hash=values["runtime_trace_hash"],
                status=values["runtime_status"],
            ),
            verification_result_to_lean(
                name="concreteVerification",
                status=values["verification_status"],
                verified_input_bundle_hash=values["verified_input_bundle_hash"],
                release_blocking_checks_passed=values["release_blocking_checks_passed"],
            ),
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


def generate_proof_obligation_file(
    obligations_doc: Mapping[str, Any],
    out_dir: Path,
    *,
    release_dir: Path | None = None,
) -> Path:
    """Write a `.lean` file proving concrete release-chain admissibility."""
    module = generated_module_name(obligations_doc)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{module}.lean"
    release_id = str(obligations_doc.get("release_id") or "release-unknown")
    values_body = generate_release_chain_lean(obligations_doc)

    source = f"""import PCS.ReleaseChainCheck

/-!
# Generated PCS release-chain proof for `{release_id}`

Auto-generated by pcs-core pcs-envelope check --lean-proof. Do not edit by hand.
This discharges ProofObligation.v0 against `PCS.ReleaseChainAdmissible` deciders only.
It does **not** imply PF-Core trace safety or `LeanKernelChecked` assurance.
-/

namespace PCS.Generated.{module}

{values_body}

theorem concrete_certificate_matches_runtime :
    certificateMatchesRuntimeD concreteCertificate concreteRuntimeReceipt = true := by
  decide

theorem concrete_verification_admits_bundle :
    verificationAdmitsBundleD concreteVerification concreteCertifiedBundleHash = true := by
  decide

theorem concrete_signed_bundle_admissible :
    signedBundleAdmissibleD concreteSignedInputHash
      concreteVerification.verifiedInputBundleHash = true := by
  decide

theorem concrete_release_chain_admissible :
    releaseChainAdmissibleD concreteCertificate concreteRuntimeReceipt concreteVerification
      concreteCertifiedBundleHash concreteSignedInputHash = true := by
  decide

theorem concrete_release_chain_admissible_prop :
    ReleaseChainAdmissible concreteCertificate concreteRuntimeReceipt concreteVerification
      concreteCertifiedBundleHash concreteSignedInputHash :=
  (releaseChainAdmissibleD_sound _ _ _ _ _).mp concrete_release_chain_admissible

#eval releaseChainAdmissibleD concreteCertificate concreteRuntimeReceipt concreteVerification
  concreteCertifiedBundleHash concreteSignedInputHash

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
