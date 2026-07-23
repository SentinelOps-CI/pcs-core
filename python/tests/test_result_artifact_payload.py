"""ResultArtifact.v0 payload byte verification (PR10 / B3)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from pcs_core.computation_validate import (
    DUPLICATE_RESULT_DECLARATION,
    PAYLOAD_DIGEST_MISMATCH,
    PAYLOAD_MISSING,
    PAYLOAD_PATH_UNSAFE,
    PAYLOAD_SIZE_MISMATCH,
    validate_computation_invalid_case,
    validate_result_payloads_in_release,
    verify_all_result_artifact_payloads,
    verify_result_artifact_payload,
)
from pcs_core.lean_trust import extract_proof_obligations_from_release
from pcs_core.paths import examples_dir
from pcs_core.pcs_projection import PAYLOAD_SHA256_POINTER
from pcs_core.release_chain import validate_release_chain
from pcs_core.release_fixtures import file_digest

COMPUTATION_RELEASE = examples_dir() / "computation-release"
INVALID_ROOT = examples_dir() / "computation-release-invalid"


def _load_result(release: Path) -> dict:
    path = release / "result_artifact.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_valid_release_verifies_payload_bytes() -> None:
    if not (COMPUTATION_RELEASE / "result_artifact.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    verified = verify_all_result_artifact_payloads(COMPUTATION_RELEASE)
    assert len(verified) == 1
    item = verified[0]
    result = _load_result(COMPUTATION_RELEASE)
    assert item.digest == result["sha256"]
    assert item.size_bytes == result["size_bytes"]
    assert item.payload_relpath == result["path"]
    assert validate_result_payloads_in_release(COMPUTATION_RELEASE) == []
    assert validate_release_chain(COMPUTATION_RELEASE) == []


def test_computation_obligations_record_verified_payload_digest() -> None:
    if not (COMPUTATION_RELEASE / "proof_obligation.v0.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    doc = extract_proof_obligations_from_release(COMPUTATION_RELEASE)
    result = _load_result(COMPUTATION_RELEASE)
    payload_path = Path(result["path"])
    entries = doc["pcs_projection_manifest"]["entries"]
    payload_entries = [
        entry
        for entry in entries
        if entry.get("json_pointer") == PAYLOAD_SHA256_POINTER
    ]
    assert payload_entries, "expected verified payload projection entry"
    assert payload_entries[0]["artifact_path"] == payload_path.as_posix()
    assert payload_entries[0]["normalized_value"] == result["sha256"]
    lean_id = payload_entries[0]["lean_identifier"]
    assert lean_id == "concreteVerifiedResultPayloadHash"

    alignment = next(
        obligation
        for obligation in doc["obligations"]
        if obligation["obligation_id"] == "computation_witness_hash_alignment"
    )
    assert alignment["inputs"]["result_artifact_sha256"] == result["sha256"]
    declared = alignment["inputs"]["declared_result_artifact_hashes"]
    assert declared == [result["sha256"]]


@pytest.mark.parametrize(
    ("case_name", "expected_token"),
    [
        ("payload_modified", PAYLOAD_DIGEST_MISMATCH),
        ("payload_wrong_size", PAYLOAD_SIZE_MISMATCH),
        ("payload_missing", PAYLOAD_MISSING),
        ("payload_traversal", PAYLOAD_PATH_UNSAFE),
        ("payload_digest_mismatch_envelope", PAYLOAD_DIGEST_MISMATCH),
        ("duplicate_result_declaration", DUPLICATE_RESULT_DECLARATION),
    ],
)
def test_invalid_payload_fixtures(case_name: str, expected_token: str) -> None:
    case_dir = INVALID_ROOT / case_name
    if not case_dir.is_dir():
        pytest.skip(f"missing invalid fixture {case_name}")
    harness_errors = validate_computation_invalid_case(case_dir)
    assert harness_errors == [], harness_errors
    errors = validate_result_payloads_in_release(case_dir)
    assert errors, f"{case_name} must fail payload verification"
    joined = " ".join(errors)
    assert expected_token in joined, joined


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_payload_symlink_escape_rejected(tmp_path: Path) -> None:
    src = INVALID_ROOT / "payload_symlink"
    if not src.is_dir():
        pytest.skip("missing payload_symlink fixture")
    case_dir = tmp_path / "payload_symlink"
    shutil.copytree(src, case_dir)
    payload = case_dir / "outputs" / "metrics.json"
    outside = tmp_path / "outside_metrics.json"
    outside.write_bytes(b'{"metric":"escaped"}\n')
    if payload.is_file():
        payload.unlink()
    try:
        payload.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation failed: {exc}")
    if not payload.is_symlink():
        pytest.skip("platform did not create a detectable symlink")
    errors = validate_result_payloads_in_release(case_dir)
    assert errors
    assert PAYLOAD_PATH_UNSAFE in " ".join(errors)


def test_absolute_payload_path_rejected(tmp_path: Path) -> None:
    if not (COMPUTATION_RELEASE / "result_artifact.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    case_dir = tmp_path / "abs"
    shutil.copytree(
        COMPUTATION_RELEASE,
        case_dir,
        ignore=shutil.ignore_patterns(
            "handoff_*",
            "science_*",
            "signed_*",
            "verification_*",
            "release_*",
            "RELEASE_*",
            "lean_*",
            "proof_*",
            "Artifact*",
            "scientific_*",
            "workflow_*",
        ),
    )
    # Minimal copy: ensure payload + result exist.
    result_src = COMPUTATION_RELEASE / "result_artifact.json"
    if not (case_dir / "result_artifact.json").is_file():
        shutil.copy2(result_src, case_dir / "result_artifact.json")
        (case_dir / "outputs").mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            COMPUTATION_RELEASE / "outputs" / "metrics.json",
            case_dir / "outputs" / "metrics.json",
        )
    result = _load_result(case_dir)
    metrics = (case_dir / "outputs" / "metrics.json").resolve()
    result["path"] = str(metrics)
    from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash

    result["signature_or_digest"] = PLACEHOLDER_DIGEST
    result["signature_or_digest"] = canonical_hash(result)
    (case_dir / "result_artifact.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=PAYLOAD_PATH_UNSAFE):
        verify_result_artifact_payload(case_dir, result)


def test_tmp_mutation_digest_and_size(tmp_path: Path) -> None:
    if not (COMPUTATION_RELEASE / "outputs" / "metrics.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    case_dir = tmp_path / "mut"
    case_dir.mkdir()
    (case_dir / "outputs").mkdir()
    payload = b'{"ok":true}\n'
    (case_dir / "outputs" / "metrics.json").write_bytes(payload)
    result = {
        "result_id": "r1",
        "path": "outputs/metrics.json",
        "sha256": file_digest(payload),
        "size_bytes": len(payload),
    }
    verified = verify_result_artifact_payload(case_dir, result)
    assert verified.digest == file_digest(payload)

    (case_dir / "outputs" / "metrics.json").write_bytes(payload + b"x")
    with pytest.raises(ValueError, match=PAYLOAD_DIGEST_MISMATCH):
        verify_result_artifact_payload(case_dir, result)

    (case_dir / "outputs" / "metrics.json").write_bytes(payload)
    result_bad_size = dict(result)
    result_bad_size["size_bytes"] = len(payload) + 1
    with pytest.raises(ValueError, match=PAYLOAD_SIZE_MISMATCH):
        verify_result_artifact_payload(case_dir, result_bad_size)
