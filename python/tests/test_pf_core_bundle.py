"""Tests for PF-Core release bundle assembly and validation."""

from __future__ import annotations

import json
from pathlib import Path

from pcs_core.pf_core_bundle import bundle_release, validate_bundle
from pcs_core.pf_core_lean_codegen import compute_pfcore_kernel_hash

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"


def test_bundle_release_and_validate(tmp_path: Path) -> None:
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-bundle-test",
        "trace_hash": json.loads(VALID_TRACE.read_text())["trace_hash"],
        "contract_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "claim_class": "RuntimeChecked",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "assumption_refs": ["docs/pf-core/trusted-boundary.md"],
        "event_count": 1,
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(cert, indent=2), encoding="utf-8")

    out_dir = tmp_path / "bundle"
    manifest_path = bundle_release(VALID_TRACE, cert_path, out_dir)
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["pfcore_kernel_hash"] == compute_pfcore_kernel_hash()
    assert (out_dir / "kernel_manifest.json").is_file()
    assert (out_dir / "kernel" / "lean" / "PFCore" / "Action.lean").is_file()
    assert (out_dir / "trace.json").is_file()
    assert (out_dir / "certificate.json").is_file()

    result = validate_bundle(out_dir)
    assert result.ok, result.issues


def test_validate_bundle_from_kernel_manifest_without_checkout(tmp_path: Path) -> None:
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-bundle-offline",
        "trace_hash": json.loads(VALID_TRACE.read_text())["trace_hash"],
        "contract_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "claim_class": "RuntimeChecked",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "assumption_refs": ["docs/pf-core/trusted-boundary.md"],
        "event_count": 1,
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(cert, indent=2), encoding="utf-8")
    bundle_dir = tmp_path / "bundle"
    bundle_release(VALID_TRACE, cert_path, bundle_dir)

    kernel_file = bundle_dir / "kernel" / "lean" / "PFCore" / "Action.lean"
    assert kernel_file.is_file()
    original = kernel_file.read_bytes()
    kernel_file.write_bytes(b"tampered")

    result = validate_bundle(bundle_dir)
    assert not result.ok
    assert any(issue.code == "KernelManifestInvalid" for issue in result.issues)

    kernel_file.write_bytes(original)
    result = validate_bundle(bundle_dir)
    assert result.ok, result.issues


def test_validate_event_sequence_order_fixture() -> None:
    from pcs_core.pf_core_runtime import validate_event_sequence_order

    case = REPO / "examples" / "pf-core-invalid" / "event_sequence_order_mismatch" / "trace.json"
    trace = json.loads(case.read_text(encoding="utf-8"))
    errors = validate_event_sequence_order(trace)
    assert any("EventSequenceOrderMismatch" in err for err in errors)
