"""Verify PF-Core certificate proof binding (trace, proof file, Lean environment)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pcs_core.lean_check import compute_proof_term_hash
from pcs_core.paths import repo_root
from pcs_core.pf_core_lean_codegen import compute_lean_environment_hash
from pcs_core.pf_core_runtime import compute_trace_hash


@dataclass(frozen=True)
class ProofBindingIssue:
    code: str
    message: str


@dataclass
class ProofBindingResult:
    ok: bool
    certificate_path: Path
    trace_path: Path | None = None
    proof_path: Path | None = None
    issues: list[ProofBindingIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "certificate_path": str(self.certificate_path),
            "trace_path": str(self.trace_path) if self.trace_path else None,
            "proof_path": str(self.proof_path) if self.proof_path else None,
            "issues": [{"code": i.code, "message": i.message} for i in self.issues],
        }


def _resolve_repo_path(ref: str) -> Path:
    path = Path(ref)
    if path.is_file():
        return path.resolve()
    candidate = repo_root() / ref.replace("\\", "/")
    if candidate.is_file():
        return candidate.resolve()
    return path


def verify_proof_binding(
    certificate_path: Path,
    *,
    trace_path: Path | None = None,
) -> ProofBindingResult:
    """Verify certificate binds trace hash, proof term hash, and Lean environment."""
    result = ProofBindingResult(ok=False, certificate_path=certificate_path)
    try:
        cert = json.loads(certificate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.issues.append(ProofBindingIssue("CertificateUnreadable", str(exc)))
        return result

    if not isinstance(cert, Mapping):
        result.issues.append(ProofBindingIssue("InvalidCertificate", "certificate root must be object"))
        return result

    claim_class = str(cert.get("claim_class") or "")
    if claim_class != "LeanKernelChecked":
        result.issues.append(
            ProofBindingIssue(
                "ClaimClassMismatch",
                f"verify-proof-binding requires LeanKernelChecked, got {claim_class!r}",
            )
        )
        return result

    if cert.get("lean_proof_checked") is not True:
        result.issues.append(
            ProofBindingIssue("LeanProofNotChecked", "certificate lean_proof_checked must be true")
        )

    cert_trace_hash = str(cert.get("trace_hash") or "")
    cert_proof_hash = str(cert.get("proof_term_hash") or "")
    cert_env_hash = str(cert.get("lean_environment_hash") or "")
    proof_ref = str(cert.get("proof_term_ref") or cert.get("proof_ref") or "")

    if not cert_trace_hash.startswith("sha256:"):
        result.issues.append(ProofBindingIssue("MissingTraceHash", "certificate missing trace_hash"))
    if not cert_proof_hash.startswith("sha256:"):
        result.issues.append(
            ProofBindingIssue("MissingProofTermHash", "certificate missing proof_term_hash")
        )
    if not cert_env_hash.startswith("sha256:"):
        result.issues.append(
            ProofBindingIssue("MissingLeanEnvironmentHash", "certificate missing lean_environment_hash")
        )
    if not proof_ref:
        result.issues.append(ProofBindingIssue("MissingProofTermRef", "certificate missing proof_term_ref"))

    resolved_trace: Path | None = None
    if trace_path is not None:
        resolved_trace = trace_path.resolve()
        result.trace_path = resolved_trace
        if not resolved_trace.is_file():
            result.issues.append(
                ProofBindingIssue("TraceMissing", f"trace file not found: {resolved_trace}")
            )
        else:
            try:
                trace = json.loads(resolved_trace.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                result.issues.append(ProofBindingIssue("TraceUnreadable", str(exc)))
            else:
                if isinstance(trace, Mapping):
                    actual_trace_hash = str(trace.get("trace_hash") or compute_trace_hash(dict(trace)))
                    if cert_trace_hash and actual_trace_hash != cert_trace_hash:
                        result.issues.append(
                            ProofBindingIssue(
                                "TraceHashMismatch",
                                f"trace hash {actual_trace_hash!r} != certificate {cert_trace_hash!r}",
                            )
                        )
                else:
                    result.issues.append(ProofBindingIssue("InvalidTrace", "trace root must be object"))

    resolved_proof: Path | None = None
    if proof_ref:
        resolved_proof = _resolve_repo_path(proof_ref)
        result.proof_path = resolved_proof
        if not resolved_proof.is_file():
            result.issues.append(
                ProofBindingIssue("ProofFileMissing", f"generated proof not found: {resolved_proof}")
            )
        elif cert_proof_hash.startswith("sha256:"):
            actual_proof_hash = compute_proof_term_hash(resolved_proof)
            if actual_proof_hash != cert_proof_hash:
                result.issues.append(
                    ProofBindingIssue(
                        "ProofTermHashMismatch",
                        f"proof file hash {actual_proof_hash!r} != certificate {cert_proof_hash!r}",
                    )
                )

    if cert_env_hash.startswith("sha256:"):
        actual_env_hash = compute_lean_environment_hash()
        if actual_env_hash != cert_env_hash:
            result.issues.append(
                ProofBindingIssue(
                    "LeanEnvironmentHashMismatch",
                    f"current lean environment {actual_env_hash!r} != certificate {cert_env_hash!r}",
                )
            )

    result.ok = not result.issues
    return result
