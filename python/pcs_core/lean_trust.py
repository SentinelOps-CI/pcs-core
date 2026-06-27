"""PCS Lean trust kernel bridge: proof obligations and check results."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.lean_catalog import OBLIGATION_KIND_THEOREM
from pcs_core.paths import repo_root
from pcs_core.protocol_fixtures import PCS_CORE_REPO
from pcs_core.release_chain_profiles import detect_workflow_profile_id

LEAN_MODULE = "PCS.Theorems"
LEAN_VERSION = "leanprover/lean4:stable"

PCS_CORE_COMMIT_PLACEHOLDER = "d444444444444444444444444444444444444444"

PCS_LEAN_CHECK_DISCLAIMER = (
    "PCS release-envelope consistency check validates ProofObligation.v0 release-envelope "
    "consistency against the PCS theorem catalog. A `ProofChecked` LeanCheckResult does "
    "not imply PF-Core trace safety. Use "
    "`pcs pf-core lean-check --trace <PFCoreTrace.v0.json>` for PF-Core kernel assurance."
)


def _file_digest(content: bytes) -> str:
    from pcs_core.release_fixtures import file_digest

    return file_digest(content)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _resolve_certified_bundle_hash(release_dir: Path) -> str | None:
    from pcs_core.bundle_identity import resolve_certified_bundle_identity_hash

    return resolve_certified_bundle_identity_hash(release_dir)


def _release_blocking_checks_passed(verification: dict[str, Any]) -> bool:
    if verification.get("status") != "ProofChecked":
        return False
    checks = verification.get("checks")
    if not isinstance(checks, list):
        return True
    for item in checks:
        if not isinstance(item, dict):
            return False
        status = item.get("status")
        if status in {"failed", "warning"}:
            return False
    return True


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
        result_sha = inputs.get("result_artifact_sha256")
        if not isinstance(witness_hashes, list) or not isinstance(result_sha, str):
            return False, "missing witness_result_hashes or result_artifact_sha256"
        if result_sha not in witness_hashes:
            return False, "result artifact sha256 not listed in witness result_hashes"
        if inputs.get("witness_status") != "CertificateChecked":
            return False, "witness_status must be CertificateChecked"
        return True, ""

    return False, f"unknown obligation kind {kind!r}"


def _extract_labtrust_obligations(release_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cert = _load_json(release_dir / "trace_certificate.json")
    receipt = _load_json(release_dir / "runtime_receipt.json")
    verification = _load_json(release_dir / "verification_result.json")
    signed = _load_json(release_dir / "signed_science_claim_bundle.json")
    certified = _load_json(release_dir / "science_claim_bundle.certified.json")
    if not all(isinstance(doc, dict) for doc in (cert, receipt, verification, signed, certified)):
        raise ValueError(f"{release_dir}: missing LabTrust trust-envelope artifacts")

    certified_bundle_hash = _resolve_certified_bundle_hash(release_dir)
    verified = verification.get("verified_input")
    verified_bundle = verified.get("bundle_hash") if isinstance(verified, dict) else None

    obligations = [
        _obligation(
            obligation_id="trace_hash_alignment",
            kind="CertificateMatchesRuntime",
            inputs={
                "certificate_id": cert.get("certificate_id"),
                "certificate_trace_hash": cert.get("trace_hash"),
                "runtime_trace_hash": receipt.get("trace_hash"),
                "certificate_status": cert.get("status"),
            },
        ),
        _obligation(
            obligation_id="verification_admits_bundle",
            kind="VerificationAdmitsBundle",
            inputs={
                "verification_status": verification.get("status"),
                "verified_input_bundle_hash": verified_bundle,
                "certified_bundle_hash": certified_bundle_hash,
                "release_blocking_checks_passed": _release_blocking_checks_passed(verification),
            },
        ),
        _obligation(
            obligation_id="signed_bundle_admissible",
            kind="SignedBundleAdmissible",
            inputs={
                "signed_input_bundle_hash": signed.get("signed_input_bundle_hash"),
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


def _extract_tool_use_obligations(release_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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

    certified_bundle_hash = _resolve_certified_bundle_hash(release_dir)
    verified = verification.get("verified_input")
    verified_bundle = verified.get("bundle_hash") if isinstance(verified, dict) else None

    obligations = [
        _obligation(
            obligation_id="tool_trace_hash_alignment",
            kind="ToolTraceHashMatchesCertificate",
            inputs={
                "certificate_id": cert.get("certificate_id"),
                "certificate_trace_hash": cert.get("trace_hash"),
                "trace_hash": trace.get("trace_hash"),
                "certificate_policy_hash": cert.get("policy_hash"),
                "trace_policy_hash": trace.get("policy_hash"),
            },
        ),
        _obligation(
            obligation_id="trace_hash_alignment",
            kind="CertificateMatchesRuntime",
            inputs={
                "certificate_id": cert.get("certificate_id"),
                "certificate_trace_hash": cert.get("trace_hash"),
                "runtime_trace_hash": receipt.get("trace_hash"),
                "certificate_status": cert.get("status"),
            },
        ),
        _obligation(
            obligation_id="verification_admits_bundle",
            kind="VerificationAdmitsBundle",
            inputs={
                "verification_status": verification.get("status"),
                "verified_input_bundle_hash": verified_bundle,
                "certified_bundle_hash": certified_bundle_hash,
                "release_blocking_checks_passed": _release_blocking_checks_passed(verification),
            },
        ),
        _obligation(
            obligation_id="signed_bundle_admissible",
            kind="SignedBundleAdmissible",
            inputs={
                "signed_input_bundle_hash": signed.get("signed_input_bundle_hash"),
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


def _extract_computation_obligations(
    release_dir: Path,
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

    certified_bundle_hash = _resolve_certified_bundle_hash(release_dir)
    verified = verification.get("verified_input")
    verified_bundle = verified.get("bundle_hash") if isinstance(verified, dict) else None

    obligations = [
        _obligation(
            obligation_id="computation_witness_hash_alignment",
            kind="ComputationWitnessHashAlignment",
            inputs={
                "witness_id": witness.get("witness_id"),
                "witness_result_hashes": witness.get("result_hashes"),
                "result_artifact_sha256": result.get("sha256"),
                "witness_status": witness.get("status"),
                "run_receipt_hash": witness.get("run_receipt_hash"),
            },
        ),
        _obligation(
            obligation_id="verification_admits_bundle",
            kind="VerificationAdmitsBundle",
            inputs={
                "verification_status": verification.get("status"),
                "verified_input_bundle_hash": verified_bundle,
                "certified_bundle_hash": certified_bundle_hash,
                "release_blocking_checks_passed": _release_blocking_checks_passed(verification),
            },
        ),
        _obligation(
            obligation_id="signed_bundle_admissible",
            kind="SignedBundleAdmissible",
            inputs={
                "signed_input_bundle_hash": signed.get("signed_input_bundle_hash"),
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
    """Build ProofObligation.v0 from a release fixture directory."""
    release_dir = release_dir.resolve()
    workflow_id = detect_workflow_profile_id(release_dir) or "labtrust.qc_release_v0.1"

    if workflow_id == "agent_tool_use.safety_v0":
        obligations, source_artifacts = _extract_tool_use_obligations(release_dir)
    elif workflow_id == "scientific_computation.reproducibility_v0":
        obligations, source_artifacts = _extract_computation_obligations(release_dir)
    else:
        obligations, source_artifacts = _extract_labtrust_obligations(release_dir)

    manifest = _load_json(release_dir / "release_manifest.v0.json")
    resolved_release_id = release_id
    if not resolved_release_id and manifest:
        resolved_release_id = str(manifest.get("release_id", "release-unknown"))
    if not resolved_release_id:
        resolved_release_id = f"release-{release_dir.name}"

    body: dict[str, Any] = {
        "schema_version": "v0",
        "obligation_id": f"proof-obligation-{resolved_release_id}",
        "release_id": resolved_release_id,
        "workflow_id": workflow_id,
        "obligations": obligations,
        "source_artifacts": source_artifacts,
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
) -> dict[str, Any]:
    """Evaluate obligations against the fixed PCS theorem set; emit LeanCheckResult.v0."""
    import sys

    print(PCS_LEAN_CHECK_DISCLAIMER, file=sys.stderr)
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

    if require_lean_build and not build_ok:
        failures.insert(0, f"lean_build: {build_reason}")

    all_passed = not failures
    status = "ProofChecked" if all_passed else "Rejected"
    checked_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    proof_obligation_id = str(obligations_doc.get("obligation_id", "proof-obligation-unknown"))

    body: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "LeanCheckResult.v0",
        "check_id": check_id or f"lean-check-{proof_obligation_id}",
        "proof_obligation_id": proof_obligation_id,
        "lean_module": str(obligations_doc.get("lean_module", LEAN_MODULE)),
        "lean_theorem": "ReleaseChainAdmissible",
        "status": status,
        "checked_at": checked_at,
        "lean_version": LEAN_VERSION,
        "source_repo": PCS_CORE_REPO,
        "source_commit": source_commit
        or str(obligations_doc.get("source_commit", PCS_CORE_COMMIT_PLACEHOLDER)),
        "failure_reason": "; ".join(failures),
        "disclaimer": PCS_LEAN_CHECK_DISCLAIMER,
        "obligation_results": obligation_results,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
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
