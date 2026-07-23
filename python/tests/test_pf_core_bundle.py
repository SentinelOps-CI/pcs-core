"""Tests for PF-Core release bundle assembly, validation, and verify-bundle."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash
from pcs_core.pf_core_bundle import bundle_release, validate_bundle, verify_bundle
from pcs_core.pf_core_lean_codegen import compute_pfcore_kernel_hash

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"
LAKE_AVAILABLE = shutil.which("lake") is not None


def _runtime_cert(tmp_path: Path) -> Path:
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-bundle-test",
        "trace_hash": json.loads(VALID_TRACE.read_text(encoding="utf-8"))["trace_hash"],
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
    cert["signature_or_digest"] = canonical_hash(cert)
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(cert, indent=2), encoding="utf-8")
    return cert_path


def test_bundle_release_and_validate(tmp_path: Path) -> None:
    cert_path = _runtime_cert(tmp_path)
    out_dir = tmp_path / "bundle"
    manifest_path = bundle_release(VALID_TRACE, cert_path, out_dir)
    assert manifest_path.is_file()
    tool_versions = out_dir / "tool_versions.json"
    assert tool_versions.is_file()
    tools = json.loads(tool_versions.read_text(encoding="utf-8"))
    assert tools["artifact_type"] == "PcsToolVersions.v0"
    assert "pcs_core" in tools["tools"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["pfcore_kernel_hash"] == compute_pfcore_kernel_hash()
    assert (out_dir / "kernel_manifest.json").is_file()
    assert (out_dir / "kernel" / "lean" / "PFCore" / "Action.lean").is_file()
    assert (out_dir / "lean-toolchain").is_file()
    assert (out_dir / "lean" / "lakefile.lean").is_file()
    assert (out_dir / "lean" / "lake-manifest.json").is_file()
    assert (out_dir / "trace.json").is_file()
    assert (out_dir / "certificate.json").is_file()
    assert (out_dir / "evidence_manifest.json").is_file()
    assert manifest.get("evidence_manifest_path") == "evidence_manifest.json"
    assert str(manifest.get("evidence_manifest_hash") or "").startswith("sha256:")

    result = validate_bundle(out_dir)
    assert result.ok, result.issues


def test_bundle_release_tool_use_defaults_trace_safe_r_mode(tmp_path: Path) -> None:
    cert_path = _runtime_cert(tmp_path)
    out_dir = tmp_path / "bundle"
    bundle_release(VALID_TRACE, cert_path, out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["certificate_mode"] == "TraceSafeRCertificate"


def test_validate_bundle_from_kernel_manifest_without_checkout(tmp_path: Path) -> None:
    cert_path = _runtime_cert(tmp_path)
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


def test_validate_bundle_isolated_from_checkout(tmp_path: Path) -> None:
    """Bundle validation must succeed without matching repository checkout layout."""
    cert_path = _runtime_cert(tmp_path)
    bundle_dir = tmp_path / "bundle"
    bundle_release(VALID_TRACE, cert_path, bundle_dir)

    isolated_root = tmp_path / "isolated"
    isolated_root.mkdir()
    isolated_bundle = isolated_root / "bundle-copy"
    shutil.copytree(bundle_dir, isolated_bundle)

    result = validate_bundle(isolated_bundle)
    assert result.ok, result.issues


def test_verify_bundle_runtime_structural(tmp_path: Path) -> None:
    """verify-bundle on RuntimeChecked succeeds without Lean compile."""
    cert_path = _runtime_cert(tmp_path)
    bundle_dir = tmp_path / "bundle"
    bundle_release(VALID_TRACE, cert_path, bundle_dir)
    result = verify_bundle(bundle_dir, skip_lean_compile=True)
    assert result.ok, result.issues
    assert result.result_path is not None and result.result_path.is_file()
    payload = json.loads(result.result_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "PFCoreBundleVerificationResult.v0"
    assert payload["ok"] is True
    assert str(payload.get("signature_or_digest") or "").startswith("sha256:")
    check_ids = {c["check_id"] for c in payload["checks"]}
    assert "validate_closed_manifests" in check_ids
    assert "compare_certificate" in check_ids


def test_verify_bundle_detects_evidence_tamper(tmp_path: Path) -> None:
    cert_path = _runtime_cert(tmp_path)
    bundle_dir = tmp_path / "bundle"
    bundle_release(VALID_TRACE, cert_path, bundle_dir)
    evidence_manifest = json.loads(
        (bundle_dir / "evidence_manifest.json").read_text(encoding="utf-8")
    )
    evidence_manifest["evidence_manifest_digest"] = "sha256:" + "a" * 64
    (bundle_dir / "evidence_manifest.json").write_text(
        json.dumps(evidence_manifest, indent=2) + "\n", encoding="utf-8"
    )
    release = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    release["evidence_manifest_hash"] = evidence_manifest["evidence_manifest_digest"]
    release["signature_or_digest"] = canonical_hash(release)
    (bundle_dir / "manifest.json").write_text(
        json.dumps(release, indent=2) + "\n", encoding="utf-8"
    )
    result = validate_bundle(bundle_dir)
    assert not result.ok
    assert any(issue.code == "EvidenceManifestHashMismatch" for issue in result.issues)


def test_validate_event_sequence_order_fixture() -> None:
    from pcs_core.pf_core_runtime import validate_event_sequence_order

    case = REPO / "examples" / "pf-core-invalid" / "event_sequence_order_mismatch" / "trace.json"
    trace = json.loads(case.read_text(encoding="utf-8"))
    errors = validate_event_sequence_order(trace)
    assert any("EventSequenceOrderMismatch" in err for err in errors)


@pytest.mark.skipif(not LAKE_AVAILABLE, reason="lake not available")
def test_verify_bundle_lean_kernel_checked_e2e(tmp_path: Path) -> None:
    """Full closed-bundle verify: lean-check → bundle-release → verify-bundle."""
    work = tmp_path / "case"
    work.mkdir()
    trace_path = work / "trace.json"
    shutil.copy2(VALID_TRACE, trace_path)
    out_cert = work / "PFCoreCertificate.v0.json"
    result_out = work / "LeanCheckResult.v0.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pcs_core.cli",
            "pf-core",
            "lean-check",
            "--trace",
            str(trace_path),
            "--out",
            str(out_cert),
            "--result-out",
            str(result_out),
            "--release-grade",
        ],
        cwd=REPO / "python",
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    cert = json.loads(out_cert.read_text(encoding="utf-8"))
    assert cert["claim_class"] == "LeanKernelChecked"
    assert (work / "PFCoreSemanticProjection.v0.json").is_file()
    assert (work / "PFCoreTheoremManifest.v0.json").is_file()

    bundle_dir = tmp_path / "bundle"
    bundle_release(
        trace_path,
        out_cert,
        bundle_dir,
        lean_check_result_path=result_out,
    )
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    for key in (
        "semantic_projection_path",
        "semantic_projection_hash",
        "theorem_manifest_path",
        "theorem_manifest_hash",
        "evidence_manifest_path",
        "evidence_manifest_hash",
        "lean_check_result_path",
        "lean_check_result_hash",
    ):
        assert manifest.get(key), f"missing closed field {key}"
    assert (bundle_dir / "PFCoreSemanticProjection.v0.json").is_file()
    assert (bundle_dir / "PFCoreTheoremManifest.v0.json").is_file()
    assert (bundle_dir / "evidence_manifest.json").is_file()

    structural = validate_bundle(bundle_dir)
    assert structural.ok, structural.issues

    verified = verify_bundle(bundle_dir, skip_lean_compile=False)
    assert verified.ok, verified.issues
    check_map = {c.check_id: c.status for c in verified.checks}
    assert check_map.get("replay_semantic_projection") == "passed"
    assert check_map.get("reconstruct_theorem_metadata") == "passed"
    assert check_map.get("compile_bundled_proof") == "passed"

    isolated = tmp_path / "isolated" / "bundle"
    isolated.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle_dir, isolated)
    isolated_result = verify_bundle(isolated)
    assert isolated_result.ok, isolated_result.issues
    payload = json.loads(isolated_result.result_path.read_text(encoding="utf-8"))
    assert payload["signature_or_digest"] == canonical_hash(payload)
