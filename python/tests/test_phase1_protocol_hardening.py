"""Phase 1 protocol hardening tests (1.1–1.5)."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from pcs_core.hash import (
    CANONICALIZATION_VERSION,
    SAFE_INTEGER_MAX,
    CanonicalizationError,
    assert_canonical_number_policy,
    attach_artifact_digest,
    canonical_hash,
    canonical_json_bytes,
    domain_separated_signing_message,
)
from pcs_core.pf_core_bundle import build_kernel_manifest, bundle_release, validate_bundle
from pcs_core.validate import (
    ARTIFACT_SCHEMAS,
    DetectionMode,
    ValidationError,
    detect_artifact_type,
    validate_artifact,
    validate_file,
    validate_schema,
)

REPO = Path(__file__).resolve().parents[2]
INVALID_FORMAT = REPO / "examples" / "invalid-format"
CANON_V1 = REPO / "test_vectors" / "hash" / "canonical_json_v1"
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"


def _minimal_cert(trace_hash: str) -> dict:
    return {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-phase1",
        "trace_hash": trace_hash,
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


def test_bundle_schemas_registered() -> None:
    assert "PFCoreKernelManifest.v0" in ARTIFACT_SCHEMAS
    assert "PFCoreReleaseBundleManifest.v0" in ARTIFACT_SCHEMAS
    assert "ArtifactIntegrity.v1" in ARTIFACT_SCHEMAS


def test_kernel_manifest_schema_and_unique_paths() -> None:
    manifest = build_kernel_manifest()
    assert manifest["canonicalization_version"] == CANONICALIZATION_VERSION
    validate_artifact(manifest, "PFCoreKernelManifest.v0", release_grade=True)
    paths = [entry["path"] for entry in manifest["files"]]
    assert len(paths) == len(set(paths))
    assert len(paths) <= 512


def test_validate_bundle_schema_before_paths(tmp_path: Path) -> None:
    trace_hash = json.loads(VALID_TRACE.read_text(encoding="utf-8"))["trace_hash"]
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(_minimal_cert(trace_hash), indent=2), encoding="utf-8")
    bundle_dir = tmp_path / "bundle"
    bundle_release(VALID_TRACE, cert_path, bundle_dir)

    # Corrupt a path field to an absolute path — schema must fail before resolve.
    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["trace_path"] = "/etc/passwd"
    manifest["signature_or_digest"] = canonical_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    result = validate_bundle(bundle_dir)
    assert not result.ok
    assert any(i.code == "ManifestSchemaInvalid" for i in result.issues)


def test_lean_kernel_checked_requires_proof_path() -> None:
    body = {
        "schema_version": "v0",
        "artifact_type": "PFCoreReleaseBundleManifest.v0",
        "claim_class": "LeanKernelChecked",
        "trace_path": "trace.json",
        "certificate_path": "certificate.json",
        "trace_hash": "sha256:" + "a" * 64,
        "kernel_manifest_path": "kernel_manifest.json",
        "pfcore_kernel_hash": "sha256:" + "b" * 64,
        "lean_environment_hash": "sha256:" + "c" * 64,
        "certificate_mode": "TraceSafeCertificate",
        "signature_or_digest": "sha256:" + "d" * 64,
    }
    errors = validate_schema(body, "PFCoreReleaseBundleManifest.v0")
    assert errors, "LeanKernelChecked without proof_path must fail schema"


def test_format_checker_rejects_malformed_uri_and_datetime() -> None:
    uri = json.loads((INVALID_FORMAT / "malformed_uri.json").read_text(encoding="utf-8"))
    dt = json.loads((INVALID_FORMAT / "malformed_date_time.json").read_text(encoding="utf-8"))
    assert validate_schema(uri, "AssumptionSet.v0")
    assert validate_schema(dt, "AssumptionSet.v0")


@pytest.mark.parametrize(
    ("filename", "artifact_type"),
    [
        ("invalid_uuid.json", "FormatAssertionProbe.v0"),
        ("invalid_duration.json", "FormatAssertionProbe.v0"),
        ("invalid_hostname.json", "FormatAssertionProbe.v0"),
        ("invalid_email.json", "FormatAssertionProbe.v0"),
    ],
)
def test_format_checker_rejects_vocabulary_fixtures(filename: str, artifact_type: str) -> None:
    data = json.loads((INVALID_FORMAT / filename).read_text(encoding="utf-8"))
    errors = validate_schema(data, artifact_type)
    assert errors, f"expected format failure for {filename}"


def test_canonical_json_v1_shared_vectors() -> None:
    vectors = json.loads((CANON_V1 / "vectors.json").read_text(encoding="utf-8"))
    assert vectors["canonicalization_version"] == CANONICALIZATION_VERSION
    for case in vectors["cases"]:
        case_id = case["case_id"]
        payload = json.loads((CANON_V1 / case_id / "input.json").read_text(encoding="utf-8"))
        assert canonical_json_bytes(payload).decode("utf-8") == case["canonical_json"]
        assert canonical_hash(payload) == case["expected_digest"]
        assert (CANON_V1 / case_id / "digest.txt").read_text(encoding="utf-8").strip() == case[
            "expected_digest"
        ]


def test_number_policy_rejects_floats_and_unsafe_ints() -> None:
    with pytest.raises(CanonicalizationError):
        assert_canonical_number_policy({"x": 1.5})
    with pytest.raises(CanonicalizationError):
        assert_canonical_number_policy({"x": SAFE_INTEGER_MAX + 1})
    assert_canonical_number_policy({"x": SAFE_INTEGER_MAX, "y": 0})


def test_artifact_integrity_v1_envelope_and_domain_separation() -> None:
    body = {
        "schema_version": "v1",
        "artifact_type": "ArtifactIntegrity.v1",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "payload": {"ok": True},
    }
    sealed = attach_artifact_digest(body)
    sealed["signature"] = {
        "algorithm": "ed25519",
        "key_id": "test-key-1",
        "signed_at": "2026-07-22T12:00:00Z",
        "value": "dGVzdA",
    }
    validate_artifact(sealed, "ArtifactIntegrity.v1", release_grade=True)
    msg = domain_separated_signing_message(
        artifact_type="ArtifactIntegrity.v1",
        schema_version="v1",
        artifact_digest=sealed["artifact_digest"],
    )
    assert msg.startswith("PCS:ArtifactIntegrity.v1:v1:sha256:")

    with_legacy = dict(sealed)
    with_legacy["signature_or_digest"] = sealed["artifact_digest"]
    assert validate_schema(with_legacy, "ArtifactIntegrity.v1")


def test_release_grade_requires_explicit_artifact_type() -> None:
    receipt = {
        "schema_version": "v0",
        "receipt_id": "r1",
        "created_at": "2026-01-15T12:00:00Z",
        "producer": "pcs-core",
        "producer_version": "0.1.0",
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "status": "RuntimeObserved",
        "events_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "trace_hash": "sha256:" + "0" * 64,
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    with pytest.raises(ValidationError) as exc:
        validate_artifact(receipt, release_grade=True)
    assert "MissingArtifactType" in (exc.value.errors or [str(exc.value)])
    # Caller-supplied type is allowed on the release path without heuristics.
    with pytest.raises(ValidationError):
        # Still fails schema/semantics, but not MissingArtifactType
        validate_artifact(receipt, "RuntimeReceipt.v0", release_grade=True)


def test_heuristic_detection_warns_outside_release_mode() -> None:
    from pcs_core import validate_detect as vd

    vd._HEURISTIC_WARNED.clear()
    receipt = {
        "schema_version": "v0",
        "receipt_id": "r1",
        "created_at": "2026-01-15T12:00:00Z",
        "producer": "pcs-core",
        "producer_version": "0.1.0",
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "status": "RuntimeObserved",
        "events_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "trace_hash": "sha256:" + "0" * 64,
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        detected = detect_artifact_type(receipt, mode=DetectionMode.DIAGNOSTIC)
    assert detected == "RuntimeReceipt.v0"
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert detect_artifact_type(receipt, mode=DetectionMode.RELEASE) is None


def test_bundle_release_still_validates(tmp_path: Path) -> None:
    trace_hash = json.loads(VALID_TRACE.read_text(encoding="utf-8"))["trace_hash"]
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(_minimal_cert(trace_hash), indent=2), encoding="utf-8")
    out_dir = tmp_path / "bundle"
    bundle_release(VALID_TRACE, cert_path, out_dir)
    result = validate_bundle(out_dir)
    assert result.ok, result.issues
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifact_type"] == "PFCoreReleaseBundleManifest.v0"
    assert manifest["canonicalization_version"] == CANONICALIZATION_VERSION
    validate_file(out_dir / "manifest.json", release_grade=True)
    validate_file(out_dir / "kernel_manifest.json", release_grade=True)
