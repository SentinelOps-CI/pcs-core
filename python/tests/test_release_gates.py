"""Fail-closed release gate checker tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pcs_core.artifact_integrity import (
    build_trusted_key,
    build_trusted_key_registry,
    generate_ed25519_keypair,
)
from pcs_core.certifyedge_pin import ProvisionEnvironment, pin_is_production_ready
from pcs_core.release_gates import (
    evaluate_release_gates,
    run_release_gate_check,
)

REPO = Path(__file__).resolve().parents[2]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _write_registry(path: Path) -> tuple[bytes, str]:
    seed, pub = generate_ed25519_keypair()
    key_id = "ops-release-1"
    doc = build_trusted_key_registry(
        [
            build_trusted_key(
                key_id=key_id,
                public_key=pub,
                valid_from=_utcnow() - timedelta(days=1),
                purposes=["release_signing"],
            )
        ],
        registry_id="test-ops-registry",
    )
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return seed, key_id


def _write_pinned_certifyedge(path: Path) -> None:
    digest = "sha256:" + ("ab" * 32)
    path.write_text(
        json.dumps(
            {
                "tool": "certifyedge",
                "status": "pinned",
                "version": "1.2.3",
                "provision_strategy": "signed_binary",
                "image": "",
                "image_digest": "",
                "binary_url": "https://example.invalid/certifyedge-1.2.3",
                "binary_sha256": digest,
                "source_repo": "",
                "source_commit": "",
                "notes": ["test pin only"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_gated_provenance(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    binding = {
        "schema_version": "v0",
        "artifact_type": "ReleaseProvenanceBinding.v0",
        "attestation": {
            "status": "gated",
            "gate_reason": "test gated status",
        },
        "signature_or_digest": "sha256:" + ("cd" * 32),
    }
    (path / "ReleaseProvenanceBinding.v0.json").write_text(
        json.dumps(binding, indent=2) + "\n", encoding="utf-8"
    )
    (path / "attestation-status.json").write_text(
        json.dumps({"status": "gated", "require_signed": False}, indent=2) + "\n",
        encoding="utf-8",
    )
    (path / "PROVENANCE_ATTESTATION_GATED.json").write_text(
        json.dumps({"status": "gated", "reason": "test"}, indent=2) + "\n",
        encoding="utf-8",
    )


def test_repo_unpinned_fails_release_passes_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PCS_TRUSTED_KEY_REGISTRY", raising=False)
    monkeypatch.delenv("PCS_PROVENANCE_ALLOW_GATED", raising=False)
    monkeypatch.delenv("PCS_CERTIFYEDGE_PROVISION_ENV", raising=False)

    preview = evaluate_release_gates(mode="preview")
    assert preview.ok
    assert any(r.gate_id == "certifyedge_pin" and r.ok for r in preview.results)

    release = evaluate_release_gates(mode="release")
    assert not release.ok
    fail_ids = {r.gate_id for r in release.hard_failures}
    assert "certifyedge_pin" in fail_ids
    assert "artifact_integrity_registry" in fail_ids


def test_release_passes_with_pin_registry_and_provision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PCS_PROVENANCE_ALLOW_GATED", raising=False)
    pin_path = tmp_path / "certifyedge.json"
    _write_pinned_certifyedge(pin_path)
    ready, errors = pin_is_production_ready(json.loads(pin_path.read_text(encoding="utf-8")))
    assert ready, errors

    registry_path = tmp_path / "TrustedKeyRegistry.v0.json"
    _write_registry(registry_path)

    digest = "sha256:" + ("ab" * 32)
    exe = tmp_path / "certifyedge"
    exe.write_bytes(b"x" * 16)
    # Digest won't match pin; force provision.env trust_grade=pinned for gate unit test.
    env = ProvisionEnvironment(
        executable_path=str(exe),
        binary_digest=digest,
        version="1.2.3",
        pin_identity=f"binary:{digest}",
        provision_strategy="signed_binary",
        trust_grade="pinned",
    )
    provision_path = env.write(tmp_path / "provision.env")
    monkeypatch.setenv("PCS_CERTIFYEDGE_PROVISION_ENV", str(provision_path))
    monkeypatch.setenv("PCS_TRUSTED_KEY_REGISTRY", str(registry_path))

    report = evaluate_release_gates(mode="release", pin_path=pin_path, registry_path=registry_path)
    assert report.ok, [r.to_dict() for r in report.hard_failures]


def test_gated_provenance_fail_closed_unless_allow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pin_path = tmp_path / "certifyedge.json"
    _write_pinned_certifyedge(pin_path)
    registry_path = tmp_path / "TrustedKeyRegistry.v0.json"
    _write_registry(registry_path)
    digest = "sha256:" + ("ab" * 32)
    env = ProvisionEnvironment(
        executable_path=str(tmp_path / "ce"),
        binary_digest=digest,
        version="1.2.3",
        pin_identity=f"binary:{digest}",
        provision_strategy="signed_binary",
        trust_grade="pinned",
    )
    provision_path = env.write(tmp_path / "provision.env")
    monkeypatch.setenv("PCS_CERTIFYEDGE_PROVISION_ENV", str(provision_path))
    monkeypatch.setenv("PCS_TRUSTED_KEY_REGISTRY", str(registry_path))
    monkeypatch.delenv("PCS_PROVENANCE_ALLOW_GATED", raising=False)

    prov = tmp_path / "provenance"
    _write_gated_provenance(prov)

    blocked = evaluate_release_gates(
        mode="release",
        pin_path=pin_path,
        registry_path=registry_path,
        provenance_dir=prov,
        allow_gated_provenance=False,
    )
    assert not blocked.ok
    assert any(r.gate_id == "provenance_attestation" for r in blocked.hard_failures)

    allowed = evaluate_release_gates(
        mode="release",
        pin_path=pin_path,
        registry_path=registry_path,
        provenance_dir=prov,
        allow_gated_provenance=True,
    )
    assert allowed.ok
    assert allowed.allow_gated_provenance is True

    preview = evaluate_release_gates(
        mode="preview",
        pin_path=pin_path,
        registry_path=registry_path,
        provenance_dir=prov,
        allow_gated_provenance=False,
    )
    assert preview.ok


def test_untrusted_trust_grade_fails_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pin_path = tmp_path / "certifyedge.json"
    _write_pinned_certifyedge(pin_path)
    registry_path = tmp_path / "TrustedKeyRegistry.v0.json"
    _write_registry(registry_path)
    env = ProvisionEnvironment(
        executable_path=str(tmp_path / "ce"),
        binary_digest="sha256:" + ("11" * 32),
        version="dev",
        pin_identity="dev_fixture:x",
        provision_strategy="dev_fixture",
        trust_grade="untrusted_development",
    )
    provision_path = env.write(tmp_path / "provision.env")
    monkeypatch.setenv("PCS_CERTIFYEDGE_PROVISION_ENV", str(provision_path))
    monkeypatch.setenv("PCS_TRUSTED_KEY_REGISTRY", str(registry_path))

    report = evaluate_release_gates(mode="release", pin_path=pin_path, registry_path=registry_path)
    assert not report.ok
    assert any(r.gate_id == "certifyedge_trust_grade" for r in report.hard_failures)


def test_certificate_mode_policy_trace_safer_rc() -> None:
    report = evaluate_release_gates(mode="preview")
    mode_gate = next(r for r in report.results if r.gate_id == "certificate_mode_policy")
    assert mode_gate.ok
    assert "TraceSafeRCertificate" in mode_gate.message


def test_cli_and_script_preview_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PCS_TRUSTED_KEY_REGISTRY", raising=False)
    monkeypatch.delenv("PCS_PROVENANCE_ALLOW_GATED", raising=False)
    code, text = run_release_gate_check(mode="preview", as_json=True)
    assert code == 0
    payload = json.loads(text)
    assert payload["ok"] is True
    assert payload["artifact_type"] == "ReleaseGateCheckReport.v0"

    script = REPO / "scripts" / "check-release-gates.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--mode", "preview", "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO),
        env={**os.environ, "PCS_RELEASE_MODE": "preview"},
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True

    cli = subprocess.run(
        [sys.executable, "-m", "pcs_core.cli", "release", "check-gates", "--mode", "preview"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO / "python"),
        env={**os.environ, "PYTHONPATH": str(REPO / "python")},
    )
    assert cli.returncode == 0, cli.stderr + cli.stdout


def test_script_release_fails_on_current_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PCS_TRUSTED_KEY_REGISTRY", raising=False)
    monkeypatch.delenv("PCS_PROVENANCE_ALLOW_GATED", raising=False)
    script = REPO / "scripts" / "check-release-gates.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--mode", "release"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO),
        env={
            k: v
            for k, v in os.environ.items()
            if k
            not in {
                "PCS_TRUSTED_KEY_REGISTRY",
                "PCS_PROVENANCE_ALLOW_GATED",
                "PCS_CERTIFYEDGE_PROVISION_ENV",
            }
        },
    )
    assert proc.returncode == 1
    assert "FAIL" in proc.stderr or "FAIL" in proc.stdout


def test_require_oci_publish_optional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin_path = tmp_path / "certifyedge.json"
    _write_pinned_certifyedge(pin_path)
    registry_path = tmp_path / "TrustedKeyRegistry.v0.json"
    _write_registry(registry_path)
    digest = "sha256:" + ("ab" * 32)
    env = ProvisionEnvironment(
        executable_path=str(tmp_path / "ce"),
        binary_digest=digest,
        version="1.2.3",
        pin_identity=f"binary:{digest}",
        provision_strategy="signed_binary",
        trust_grade="pinned",
    )
    monkeypatch.setenv("PCS_CERTIFYEDGE_PROVISION_ENV", str(env.write(tmp_path / "provision.env")))
    monkeypatch.setenv("PCS_TRUSTED_KEY_REGISTRY", str(registry_path))
    monkeypatch.delenv("PCS_VERIFIER_OCI_DIGEST", raising=False)

    soft = evaluate_release_gates(
        mode="release",
        pin_path=pin_path,
        registry_path=registry_path,
        require_oci_publish=False,
    )
    assert soft.ok

    hard = evaluate_release_gates(
        mode="release",
        pin_path=pin_path,
        registry_path=registry_path,
        require_oci_publish=True,
    )
    assert not hard.ok
    assert any(r.gate_id == "oci_cosign_publish" for r in hard.hard_failures)
