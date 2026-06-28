"""Generate certificate mode valid/invalid example fixtures."""

from __future__ import annotations

import json
import shutil

from pcs_core.paths import repo_root

MODES = [
    "TraceSafeCertificate",
    "TraceSafeRCertificate",
    "FramePreservedCertificate",
    "EffectFrameCertificate",
    "HandoffSafeCertificate",
    "CompositionalExtensionCertificate",
    "ContractCheckedCertificate",
]


def main() -> None:
    repo = repo_root()
    trace_src = repo / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
    for mode in MODES:
        slug = mode.lower()
        valid_dir = repo / "examples" / "pf-core-valid" / f"certificate_mode_{slug}"
        valid_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(trace_src, valid_dir / "trace.json")
        (valid_dir / "manifest.json").write_text(
            json.dumps({"certificate_mode": mode, "valid": True}, indent=2) + "\n",
            encoding="utf-8",
        )

        invalid_dir = (
            repo / "examples" / "pf-core-invalid" / f"certificate_mode_{slug}_missing_obligations"
        )
        invalid_dir.mkdir(parents=True, exist_ok=True)
        (invalid_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "expected_error": "certificate_mode obligations",
                    "must_fail_at": "validate_semantics",
                    "artifact_file": "certificate.json",
                    "artifact_type": "PFCoreCertificate.v0",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        cert = {
            "schema_version": "v0",
            "artifact_type": "PFCoreCertificate.v0",
            "certificate_id": f"pfcore-cert-mode-{slug}",
            "trace_hash": "sha256:" + "0" * 64,
            "contract_hash": "sha256:" + "0" * 64,
            "policy_hash": "sha256:" + "0" * 64,
            "claim_class": "LeanKernelChecked",
            "checker": "pcs-core",
            "checker_version": "0.1.0",
            "assumption_refs": ["docs/pf-core/trusted-boundary.md"],
            "certificate_mode": mode,
            "lean_proof_checked": True,
            "proof_term_ref": "lean/PFCore/Generated/example.lean",
            "proof_term_hash": "sha256:" + "f" * 64,
            "lean_environment_hash": "sha256:" + "e" * 64,
            "pfcore_kernel_hash": "sha256:" + "d" * 64,
            "lean_build_status": {"ok": True, "target": "PFCore", "detail": "ok"},
            "obligations": [
                {"kind": "ConcreteTraceSafe", "theorem": "concrete_trace_safe", "passed": True}
            ],
            "event_count": 1,
            "default_contract_ref": "trace-safe",
            "contract_semantics_checked": {
                "lean": ["resource_within_capability_pattern"],
                "runtime": ["resource_pattern_scope"],
            },
            "source_repo": "https://github.com/example/pcs-core",
            "source_commit": "abc1234567890abc1234567890abc1234567890",
            "signature_or_digest": "sha256:" + "0" * 64,
        }
        (invalid_dir / "certificate.json").write_text(
            json.dumps(cert, indent=2) + "\n", encoding="utf-8"
        )
    print("Generated certificate mode fixtures")


if __name__ == "__main__":
    main()
