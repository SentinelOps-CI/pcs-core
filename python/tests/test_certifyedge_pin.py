"""CertifyEdge pin, provision env, and trust-grade tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pcs_core.certifyedge_pin import (
    ProvisionEnvironment,
    certifyedge_pin_record_for_bundle,
    classify_checker_trust,
    dev_fixture_digest,
    load_certifyedge_pin,
    parse_provision_env,
    pin_allows_dev_fixture,
    pin_is_production_ready,
    validate_attestation_against_pin,
    write_dev_fixture_binary,
)
from pcs_core.external_attestation import build_external_attestation
from pcs_core.pf_core_bundle import bundle_release

REPO = Path(__file__).resolve().parents[2]
MOCK_TRACE = REPO / "examples" / "pf-core-valid" / "certifyedge_mock" / "trace.json"
MOCK_CERT = REPO / "examples" / "pf-core-valid" / "certifyedge_mock" / "certificate.json"


def test_repo_pin_unpinned_fail_closed_for_production() -> None:
    pin = load_certifyedge_pin()
    assert pin.status == "unpinned"
    ready, errors = pin_is_production_ready(pin)
    assert ready is False
    assert any("status" in e for e in errors)


def test_dev_fixture_digest_stable(tmp_path: Path) -> None:
    dest = tmp_path / "certifyedge"
    digest = write_dev_fixture_binary(dest)
    assert digest == dev_fixture_digest()
    assert dest.read_bytes().startswith(b"PCS_CERTIFYEDGE_DEV_FIXTURE_V1")


def test_dev_fixture_pin_preview_ok(tmp_path: Path) -> None:
    pin_doc = {
        "status": "pinned",
        "version": "dev-fixture-0",
        "provision_strategy": "dev_fixture",
        "binary_sha256": dev_fixture_digest(),
        "image": "",
        "image_digest": "",
        "binary_url": "",
        "source_repo": "",
        "source_commit": "",
    }
    ok, errors = pin_allows_dev_fixture(pin_doc)
    assert ok, errors
    ready, prod_errors = pin_is_production_ready(pin_doc)
    assert ready is False
    assert any("dev_fixture" in e for e in prod_errors)

    pin_path = tmp_path / "pin.json"
    pin_path.write_text(json.dumps(pin_doc), encoding="utf-8")
    script = REPO / "scripts" / "verify-certifyedge-pin.py"
    preview = subprocess.run(
        [sys.executable, str(script), "--pin", str(pin_path), "--mode", "preview"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert preview.returncode == 0, preview.stderr
    release = subprocess.run(
        [sys.executable, str(script), "--pin", str(pin_path), "--mode", "release"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert release.returncode == 1
    assert "not production-ready" in release.stderr or "FAIL" in release.stderr


def test_provision_env_roundtrip(tmp_path: Path) -> None:
    env = ProvisionEnvironment(
        executable_path=str(tmp_path / "certifyedge"),
        binary_digest=dev_fixture_digest(),
        version="0.0.0-dev",
        pin_identity=f"dev_fixture:{dev_fixture_digest()}",
        provision_strategy="dev_fixture",
        trust_grade="untrusted_development",
    )
    path = env.write(tmp_path / "provision.env")
    loaded = parse_provision_env(path)
    assert loaded.executable_path == env.executable_path
    assert loaded.binary_digest == env.binary_digest
    assert loaded.trust_grade == "untrusted_development"
    assert "PF_CORE_CERTIFYEDGE_CLI=" in path.read_text(encoding="utf-8")


def test_arbitrary_executable_untrusted(tmp_path: Path) -> None:
    exe = tmp_path / "random-checker"
    exe.write_bytes(b"not-the-fixture")
    pin = load_certifyedge_pin()
    grade = classify_checker_trust(executable=exe, pin=pin)
    assert grade in {"unpinned", "untrusted_development"}


def test_bundle_carries_certifyedge_pin(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    bundle_release(MOCK_TRACE, MOCK_CERT, out)
    pin_path = out / "certifyedge_pin.json"
    assert pin_path.is_file()
    record = json.loads(pin_path.read_text(encoding="utf-8"))
    assert record["artifact_type"] == "CertifyEdgePinRecord.v0"
    assert record["status"] == "unpinned"
    assert record["production_ready"] is False
    # Same shape as helper.
    helper = certifyedge_pin_record_for_bundle()
    assert helper["pin_identity"] == record["pin_identity"]


def test_attestation_pin_validation_digest_fields() -> None:
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
    # Unpinned repo pin: require_pinned fails closed.
    errors = validate_attestation_against_pin(attestation, require_pinned=True)
    assert any("NotProductionReady" in e or "TrustGrade" in e for e in errors)
    # Preview path without require_pinned still validates digest field shapes.
    soft = validate_attestation_against_pin(attestation, require_pinned=False)
    assert soft == [] or all("NotProductionReady" not in e for e in soft)


def test_certifyedge_dev_fixture_script() -> None:
    script = REPO / "scripts" / "certifyedge-dev-fixture.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--print-digest-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == dev_fixture_digest()
