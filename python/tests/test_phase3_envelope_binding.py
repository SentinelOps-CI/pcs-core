"""Phase 3 — PCS envelope binding: fail-closed extraction, projection, profile engine."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from pcs_core.lean_trust import extract_proof_obligations_from_release, run_lean_check
from pcs_core.obligation_extraction_errors import (
    MissingCertificateId,
    MissingReleaseId,
    MissingTraceHash,
    MissingVerificationChecks,
    ObligationExtractionError,
)
from pcs_core.paths import examples_dir, repo_root
from pcs_core.pcs_lean_codegen import (
    generate_proof_obligation_file,
    release_chain_values_from_obligations,
)
from pcs_core.pcs_projection import projection_manifest_hash
from pcs_core.release_chain import validate_release_chain
from pcs_core.release_profile_engine import (
    get_release_profile,
    list_release_profiles,
    run_release_profile_validation,
    validate_release_directory,
)
from pcs_core.release_profile_specs import (
    COMPUTATION_RELEASE_PROFILE,
    LABTRUST_RELEASE_PROFILE,
    TOOL_USE_RELEASE_PROFILE,
)
from pcs_core.validate import validate_artifact, validate_file

LABTRUST = examples_dir() / "labtrust-release"
TOOL_USE = examples_dir() / "tool-use-release"
COMPUTATION = examples_dir() / "computation-release"


def _copy_release(src: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def test_extract_fail_closed_missing_certificate_id(tmp_path: Path) -> None:
    release = _copy_release(LABTRUST, tmp_path / "release")
    cert_path = release / "trace_certificate.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    del cert["certificate_id"]
    cert_path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(MissingCertificateId):
        extract_proof_obligations_from_release(release)


def test_extract_fail_closed_missing_trace_hash(tmp_path: Path) -> None:
    release = _copy_release(LABTRUST, tmp_path / "release")
    cert_path = release / "trace_certificate.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    del cert["trace_hash"]
    cert_path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(MissingTraceHash):
        extract_proof_obligations_from_release(release)


def test_extract_fail_closed_missing_verification_checks(tmp_path: Path) -> None:
    release = _copy_release(LABTRUST, tmp_path / "release")
    vr_path = release / "verification_result.json"
    vr = json.loads(vr_path.read_text(encoding="utf-8"))
    vr["checks"] = []
    vr_path.write_text(json.dumps(vr, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(MissingVerificationChecks):
        extract_proof_obligations_from_release(release)


def test_extract_fail_closed_missing_release_id(tmp_path: Path) -> None:
    release = _copy_release(LABTRUST, tmp_path / "release")
    manifest_path = release / "release_manifest.v0.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["release_id"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(MissingReleaseId):
        extract_proof_obligations_from_release(release)


def test_codegen_rejects_unknown_placeholders() -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    broken = copy.deepcopy(doc)
    for entry in broken["obligations"]:
        if entry.get("obligation_id") == "trace_hash_alignment":
            entry["inputs"]["certificate_id"] = "cert-unknown"
    with pytest.raises(ObligationExtractionError):
        release_chain_values_from_obligations(broken)


def test_projection_manifest_bound_into_obligation_and_lean_check(tmp_path: Path) -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    assert "pcs_projection_manifest" in doc
    assert "pcs_projection_manifest_hash" in doc
    projection = doc["pcs_projection_manifest"]
    validate_artifact(projection, "PCSProjectionManifest.v0", release_grade=True)
    assert projection_manifest_hash(projection) == doc["pcs_projection_manifest_hash"]
    for entry in projection["entries"]:
        assert entry["normalized_value"]
        assert "unknown" not in entry["normalized_value"].lower()
        assert "unknown" not in entry["lean_identifier"].lower()

    lean_result = run_lean_check(doc, require_lean_build=False, lean_proof=False)
    assert lean_result["pcs_projection_manifest_hash"] == doc["pcs_projection_manifest_hash"]

    lean_path = generate_proof_obligation_file(doc, tmp_path)
    text = lean_path.read_text(encoding="utf-8")
    assert "pcsProjectionManifestHash" in text
    assert doc["pcs_projection_manifest_hash"] in text
    assert "cert-unknown" not in text
    assert 'Hash.ofString ""' not in text


@pytest.mark.parametrize("release_dir", [LABTRUST, TOOL_USE, COMPUTATION])
def test_extract_happy_paths_include_projection(release_dir: Path) -> None:
    doc = extract_proof_obligations_from_release(release_dir)
    validate_artifact(doc, "ProofObligation.v0", release_grade=False)
    assert doc["pcs_projection_manifest_hash"].startswith("sha256:")
    assert doc["pcs_projection_manifest"]["entries"]


def test_release_profile_registry_covers_three_domains() -> None:
    profiles = {spec.workflow_profile_id for spec in list_release_profiles()}
    assert LABTRUST_RELEASE_PROFILE.workflow_profile_id in profiles
    assert TOOL_USE_RELEASE_PROFILE.workflow_profile_id in profiles
    assert COMPUTATION_RELEASE_PROFILE.workflow_profile_id in profiles
    assert get_release_profile(LABTRUST_RELEASE_PROFILE.workflow_profile_id) is not None


def test_release_profile_engine_parity_with_wrappers() -> None:
    assert validate_release_chain(LABTRUST) == []
    assert validate_release_directory(LABTRUST) == []
    assert run_release_profile_validation(LABTRUST, LABTRUST_RELEASE_PROFILE) == []
    assert validate_release_chain(TOOL_USE) == []
    assert run_release_profile_validation(TOOL_USE, TOOL_USE_RELEASE_PROFILE) == []
    assert validate_release_chain(COMPUTATION) == []
    assert run_release_profile_validation(COMPUTATION, COMPUTATION_RELEASE_PROFILE) == []


def test_release_manifest_schema_accepts_projection_hash() -> None:
    path = LABTRUST / "release_manifest.v0.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    doc = extract_proof_obligations_from_release(LABTRUST)
    data["pcs_projection_manifest_hash"] = doc["pcs_projection_manifest_hash"]
    # Re-hash not required for schema acceptance of the optional field.
    validate_artifact(data, "ReleaseManifest.v0", release_grade=False)


def test_pcs_projection_schema_file_registered() -> None:
    schema = repo_root() / "schemas" / "PCSProjectionManifest.v0.schema.json"
    assert schema.is_file()
    example = extract_proof_obligations_from_release(LABTRUST)["pcs_projection_manifest"]
    out = repo_root() / "python" / "tests" / "_tmp_projection.json"
    try:
        out.write_text(json.dumps(example, indent=2) + "\n", encoding="utf-8")
        validate_file(out)
    finally:
        if out.exists():
            out.unlink()
