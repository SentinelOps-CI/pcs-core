"""PR9 — mandatory PCS projection + Lean envelope binding."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from pcs_core.lean_trust import extract_proof_obligations_from_release, run_lean_check
from pcs_core.obligation_extraction_errors import ObligationExtractionError
from pcs_core.paths import examples_dir
from pcs_core.pcs_lean_codegen import (
    aggregate_lean_theorem_for_workflow,
    generate_proof_obligation_file,
)
from pcs_core.pcs_projection import (
    CERTIFIED_BUNDLE_RESOLVER_ID,
    PROJECTION_RESOLVER_REGISTRY_VERSION,
    ProjectionManifestBuilder,
    synthetic_resolver_digest,
    validate_projection_against_release,
    validate_proof_obligation_projection,
)
from pcs_core.validate import validate_artifact

LABTRUST = examples_dir() / "labtrust-release"
TOOL_USE = examples_dir() / "tool-use-release"
COMPUTATION = examples_dir() / "computation-release"


def _copy_release(src: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def test_proof_obligation_schema_requires_projection() -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    validate_artifact(doc, "ProofObligation.v0", release_grade=False)
    broken = copy.deepcopy(doc)
    del broken["pcs_projection_manifest"]
    del broken["pcs_projection_manifest_hash"]
    # Recompute root digest after mutation is unnecessary; schema must reject missing fields.
    from pcs_core.validate_detect import ValidationError

    with pytest.raises(ValidationError):
        validate_artifact(broken, "ProofObligation.v0", release_grade=False)


def test_projection_replay_against_release() -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    errors = validate_projection_against_release(
        doc["pcs_projection_manifest"],
        LABTRUST,
        expected_hash=doc["pcs_projection_manifest_hash"],
    )
    assert errors == []
    assert validate_proof_obligation_projection(doc, release_dir=LABTRUST) == []


def test_certified_bundle_resolver_binds_value_not_namespace_alone() -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    entries = doc["pcs_projection_manifest"]["entries"]
    synthetic = [
        entry
        for entry in entries
        if entry["artifact_path"] == CERTIFIED_BUNDLE_RESOLVER_ID
    ]
    assert len(synthetic) == 1
    entry = synthetic[0]
    expected = synthetic_resolver_digest(
        resolver_id=CERTIFIED_BUNDLE_RESOLVER_ID,
        resolver_version=PROJECTION_RESOLVER_REGISTRY_VERSION,
        normalized_value=entry["normalized_value"],
    )
    assert entry["artifact_digest"] == expected
    # Legacy release-id+namespace digest must not match.
    from hashlib import sha256

    legacy_payload = f"synthetic:{doc['release_id']}:{CERTIFIED_BUNDLE_RESOLVER_ID}"
    legacy = f"sha256:{sha256(legacy_payload.encode()).hexdigest()}"
    assert entry["artifact_digest"] != legacy


def test_reject_unrecognized_synthetic_resolver(tmp_path: Path) -> None:
    release = _copy_release(LABTRUST, tmp_path / "release")
    builder = ProjectionManifestBuilder(
        release_dir=release,
        release_id="release-pcs-v0.1-labtrust-qc",
        workflow_id="labtrust.qc_release_v0.1",
    )
    with pytest.raises(ObligationExtractionError, match="unrecognized synthetic"):
        builder.add(
            artifact_path="#resolved/not_a_real_resolver",
            json_pointer="/#resolved/not_a_real_resolver",
            normalized_value="sha256:" + ("ab" * 32),
            lean_identifier="bogusResolver",
            require_digest=True,
        )


def test_reject_duplicate_and_conflicting_lean_identifiers(tmp_path: Path) -> None:
    release = _copy_release(LABTRUST, tmp_path / "release")
    builder = ProjectionManifestBuilder(
        release_dir=release,
        release_id="release-pcs-v0.1-labtrust-qc",
        workflow_id="labtrust.qc_release_v0.1",
    )
    builder.add(
        artifact_path="trace_certificate.json",
        json_pointer="/certificate_id",
        normalized_value="cert-a",
        lean_identifier="concreteCertificate.certificateId",
    )
    with pytest.raises(ObligationExtractionError, match="conflicting Lean identifier"):
        builder.add(
            artifact_path="trace_certificate.json",
            json_pointer="/status",
            normalized_value="CertificateChecked",
            lean_identifier="concreteCertificate.certificateId",
        )


def test_reject_path_traversal_in_projection(tmp_path: Path) -> None:
    release = _copy_release(LABTRUST, tmp_path / "release")
    builder = ProjectionManifestBuilder(
        release_dir=release,
        release_id="release-pcs-v0.1-labtrust-qc",
        workflow_id="labtrust.qc_release_v0.1",
    )
    with pytest.raises(ObligationExtractionError, match="escapes"):
        builder.add(
            artifact_path="../secrets.json",
            json_pointer="/x",
            normalized_value="nope",
            lean_identifier="evil",
        )


def test_mutation_of_normalized_value_fails_replay(tmp_path: Path) -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    mutated = copy.deepcopy(doc["pcs_projection_manifest"])
    mutated["entries"][0]["normalized_value"] = "tampered-value-not-unknown"
    errors = validate_projection_against_release(mutated, LABTRUST)
    assert any("normalized_value mismatch" in err for err in errors)


def test_codegen_binds_projection_into_release_envelope(tmp_path: Path) -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    path = generate_proof_obligation_file(doc, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "concreteReleaseEnvelope" in text
    assert "EnvelopeReleaseAdmissible" in text
    assert "concrete_envelope_release_admissible_prop" in text
    assert "projectionDigest" in text
    assert doc["pcs_projection_manifest_hash"].removeprefix("sha256:") in text
    assert aggregate_lean_theorem_for_workflow(doc["workflow_id"]) == (
        "concrete_envelope_release_admissible_prop"
    )


def test_tool_use_and_computation_bind_projection(tmp_path: Path) -> None:
    tool_doc = extract_proof_obligations_from_release(TOOL_USE)
    tool_path = generate_proof_obligation_file(tool_doc, tmp_path / "tool", release_dir=TOOL_USE)
    tool_text = tool_path.read_text(encoding="utf-8")
    assert "concreteReleaseEnvelope" in tool_text
    assert "EnvelopeReleaseAdmissible concreteReleaseEnvelope" in tool_text

    comp_doc = extract_proof_obligations_from_release(COMPUTATION)
    comp_path = generate_proof_obligation_file(
        comp_doc,
        tmp_path / "comp",
        release_dir=COMPUTATION,
    )
    comp_text = comp_path.read_text(encoding="utf-8")
    assert "concreteEnvelopeProjection" in comp_text
    assert "EnvelopeProjectionBound" in comp_text


def test_envelope_lean_checked_requires_projection_hash() -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    result = run_lean_check(doc, require_lean_build=False, lean_proof=False)
    assert result["pcs_projection_manifest_hash"] == doc["pcs_projection_manifest_hash"]
    from pcs_core.lean_validate import validate_lean_check_result_semantics

    forged = copy.deepcopy(result)
    forged["claim_class"] = "EnvelopeLeanChecked"
    forged["lean_proof_checked"] = True
    forged["proof_term_ref"] = "lean/PCS/Generated/x.lean"
    del forged["pcs_projection_manifest_hash"]
    errors = validate_lean_check_result_semantics(forged)
    assert any("pcs_projection_manifest_hash" in err for err in errors)


def test_run_lean_check_rejects_missing_projection() -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    broken = copy.deepcopy(doc)
    del broken["pcs_projection_manifest"]
    del broken["pcs_projection_manifest_hash"]
    with pytest.raises(ObligationExtractionError):
        run_lean_check(broken, require_lean_build=False, lean_proof=False)
