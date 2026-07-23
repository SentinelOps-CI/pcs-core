"""Phase 6 external attestation binding tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.external_attestation import (
    ABSENCE_NOTICE_NAME,
    EXTERNAL_ATTESTATION_NAME,
    attest_release_bundle,
    build_external_attestation,
    validate_bundle_external_attestation,
    validate_external_attestation,
    write_preview_absence_notice,
)
from pcs_core.pf_core_bundle import bundle_release, validate_bundle

REPO = Path(__file__).resolve().parents[2]
LABTRUST_TRACE = REPO / "examples" / "pf-core-valid" / "certifyedge_mock" / "trace.json"
MOCK_CERT = REPO / "examples" / "pf-core-valid" / "certifyedge_mock" / "certificate.json"


@pytest.fixture()
def mock_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "mock")
    out = tmp_path / "bundle"
    bundle_release(LABTRUST_TRACE, MOCK_CERT, out)
    return out


def test_external_attestation_schema_and_digest_seal() -> None:
    attestation = build_external_attestation(
        release_bundle_digest="sha256:" + "a" * 64,
        trace_digest="sha256:" + "b" * 64,
        property_id="qc_release.temporal.safety",
        checker="certifyedge",
        checker_version="0.1.0",
        checker_binary_digest="sha256:" + "c" * 64,
        result="CertificateChecked",
        attestation_class="mock",
        issuer_identity="certifyedge-mock",
        attestation_ref="mock://certifyedge/qc_release.temporal.safety",
    )
    errors = validate_external_attestation(attestation)
    assert errors == []
    assert attestation["authentication_mode"] == "digest_bound"
    assert attestation["attestation_signature"]["algorithm"] == "sha256-digest-bound"


def test_live_class_rejects_mock_ref() -> None:
    with pytest.raises(ValueError, match="live attestation"):
        build_external_attestation(
            release_bundle_digest="sha256:" + "a" * 64,
            trace_digest="sha256:" + "b" * 64,
            property_id="qc_release.temporal.safety",
            checker="certifyedge",
            checker_version="0.1.0",
            checker_binary_digest="sha256:" + "c" * 64,
            result="CertificateChecked",
            attestation_class="live",
            issuer_identity="certifyedge",
            attestation_ref="mock://certifyedge/x",
        )


def test_attest_bundle_binds_exact_manifest_digest(
    mock_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "mock")
    attestation, check = attest_release_bundle(
        mock_bundle,
        property_id="qc_release.temporal.safety",
        require_live=False,
    )
    assert check.ok
    assert attestation["attestation_class"] == "mock"
    manifest = json.loads((mock_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert attestation["release_bundle_digest"] == manifest["signature_or_digest"]
    assert (mock_bundle / EXTERNAL_ATTESTATION_NAME).is_file()
    errors = validate_bundle_external_attestation(mock_bundle, require_live=False)
    assert errors == []


def test_require_live_rejects_mock_attestation(
    mock_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "mock")
    with pytest.raises(RuntimeError, match="live|mock|require"):
        attest_release_bundle(
            mock_bundle,
            property_id="qc_release.temporal.safety",
            require_live=True,
        )


def test_preview_absence_notice(mock_bundle: Path) -> None:
    notice_path = write_preview_absence_notice(mock_bundle, reason="CertifyEdge pin unpinned")
    assert notice_path.name == ABSENCE_NOTICE_NAME
    errors = validate_bundle_external_attestation(
        mock_bundle, require_live=False, allow_absence_notice=True
    )
    assert errors == []
    errors_live = validate_bundle_external_attestation(
        mock_bundle, require_live=True, allow_absence_notice=True
    )
    assert any("ExternalAttestationMissing" in e for e in errors_live)


def test_validate_bundle_checks_sidecar_when_present(
    mock_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "mock")
    monkeypatch.delenv("PCS_RELEASE_MODE", raising=False)
    attest_release_bundle(mock_bundle, property_id="qc_release.temporal.safety")
    result = validate_bundle(mock_bundle)
    assert result.ok, result.to_dict()


def test_ed25519_signed_external_attestation_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pcs_core.artifact_integrity import (
        build_trusted_key,
        build_trusted_key_registry,
        encode_key_bytes,
        generate_ed25519_keypair,
    )
    from pcs_core.external_attestation import seal_external_attestation

    seed, pub = generate_ed25519_keypair()
    key_id = "attest-key"
    registry_path = tmp_path / "keys.json"
    registry_path.write_text(
        json.dumps(
            build_trusted_key_registry(
                [
                    build_trusted_key(
                        key_id=key_id,
                        public_key=encode_key_bytes(pub),
                        valid_from="2020-01-01T00:00:00Z",
                        purposes=["external_attestation"],
                    )
                ]
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PCS_TRUSTED_KEY_REGISTRY", str(registry_path))

    base = {
        "schema_version": "v0",
        "artifact_type": "ExternalAttestation.v0",
        "attestation_id": "ext-1",
        "release_bundle_digest": "sha256:" + "a" * 64,
        "trace_digest": "sha256:" + "b" * 64,
        "property_id": "qc_release.temporal.safety",
        "property_version": "v0",
        "checker": "certifyedge",
        "checker_version": "0.1.0",
        "checker_binary_digest": "sha256:" + "c" * 64,
        "policy_digest": "sha256:" + "d" * 64,
        "executed_at": "2026-07-22T12:00:00Z",
        "result": "CertificateChecked",
        "attestation_class": "mock",
        "issuer_identity": "certifyedge-mock",
        "authentication_mode": "ed25519_signed",
        "attestation_ref": "mock://certifyedge/x",
    }
    # Fix policy digest to match helper.
    from pcs_core.external_attestation import policy_digest_from_property

    base["policy_digest"] = policy_digest_from_property("qc_release.temporal.safety", "v0")
    sealed = seal_external_attestation(base, private_seed=seed, key_id=key_id)
    assert sealed["authentication_mode"] == "ed25519_signed"
    assert sealed["attestation_signature"]["algorithm"] == "ed25519"
    errors = validate_external_attestation(sealed)
    assert errors == [], errors


def test_verify_certifyedge_pin_release_fail_closed() -> None:
    import subprocess
    import sys

    script = REPO / "scripts" / "verify-certifyedge-pin.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--mode", "release"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "not production-ready" in proc.stderr or "FAIL" in proc.stderr


def test_verify_certifyedge_pin_preview_ok() -> None:
    import subprocess
    import sys

    script = REPO / "scripts" / "verify-certifyedge-pin.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--mode", "preview"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
