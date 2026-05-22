"""PCS protocol hardening conformance tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from pcs_core.legacy_manifest import legacy_manifest_equivalent_to_release_manifest
from pcs_core.migrate import migrate_file
from pcs_core.paths import examples_dir
from pcs_core.protocol_fixtures import release_manifest_valid
from pcs_core.conformance import build_conformance_report_data, list_suites, run_conformance
from pcs_core.registry import audit_registry_producer_fields, validate_registry_file
from pcs_core.semantic_check_execution import build_semantic_check_execution
from pcs_core.registry import (
    build_artifact_registry,
    check_artifact_against_registry,
    registry_entries,
)
from pcs_core.registry_data import all_registry_semantic_check_refs
from pcs_core.registry_semantics import (
    audit_registry_enforcement,
    audit_release_blocking_chain_catalog_coverage,
)
from pcs_core.release_chain_checks import RELEASE_CHAIN_CHECK_SPECS
from pcs_core.release_chain_registry_refs import RELEASE_CHAIN_REGISTRY_CHECK_REFS
from pcs_core.release_chain_report import build_release_chain_validation_result
from pcs_core.release_fixtures import release_dir
from pcs_core.shared_hash_vectors import VECTOR_FILENAMES, VECTOR_SPECS, verify_shared_vectors
from pcs_core.status_policy import check_status_transition
from pcs_core.validate import ValidationError, validate_artifact, validate_file

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "examples" / "labtrust-release"
LEGACY_MANIFEST = RELEASE / "RELEASE_FIXTURE_MANIFEST.json"
RELEASE_MANIFEST_V0 = RELEASE / "release_manifest.v0.json"


def test_release_manifest_v0_validates() -> None:
    assert validate_file(RELEASE_MANIFEST_V0) == "ReleaseManifest.v0"


def test_release_manifest_legacy_equivalence() -> None:
    legacy = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
    release = json.loads(RELEASE_MANIFEST_V0.read_text(encoding="utf-8"))
    drift = legacy_manifest_equivalent_to_release_manifest(legacy, release)
    assert drift == [], drift


def test_legacy_manifest_and_release_manifest_v0_are_semantically_equivalent() -> None:
    test_release_manifest_legacy_equivalence()


def test_release_manifest_validation_result_ref_matches_file() -> None:
    from pcs_core.release_fixtures import file_digest

    manifest = json.loads(RELEASE_MANIFEST_V0.read_text(encoding="utf-8"))
    ref = manifest["release_chain_validation_result"]
    path = RELEASE / str(ref["path"])
    assert file_digest(path.read_bytes()) == ref["sha256"]


def test_on_disk_release_chain_validation_has_full_checks() -> None:
    data = json.loads(
        (RELEASE / "release_chain_validation_result.v0.json").read_text(encoding="utf-8"),
    )
    assert data.get("workflow_profile_id") == "labtrust.qc_release_v0.1"
    assert len(data["checks"]) == 30


def test_validate_release_chain_emits_release_chain_validation_result() -> None:
    result = build_release_chain_validation_result(release_dir())
    assert result["status"] == "ProofChecked"
    assert len(result["checks"]) == 30
    validate_artifact(result, "ReleaseChainValidationResult.v0")


def test_artifact_registry_contains_all_v0_artifacts() -> None:
    expected = set(registry_entries().keys())
    on_disk = build_artifact_registry()["entries"]
    assert expected == set(on_disk.keys())


def test_registry_distinguishes_schema_owner_from_runtime_producer() -> None:
    entry = registry_entries()["HandoffManifest.v0"]
    assert entry["schema_owner"] == "pcs-core"
    assert entry["runtime_producer"] == "LabTrust-Gym"
    assert "pcs-core" not in entry["allowed_runtime_producers"]
    assert len(entry["allowed_runtime_producers"]) >= 4


def test_all_registry_semantic_checks_have_responsible_component() -> None:
    for artifact_type, entry in registry_entries().items():
        for check in entry["semantic_checks"]:
            assert check.get("responsible_component"), f"{artifact_type} missing responsible_component"
            assert check.get("severity"), f"{artifact_type} missing severity"
            assert check.get("check_id"), f"{artifact_type} missing check_id"


def test_registry_semantic_checks_have_execution_policy() -> None:
    built = build_artifact_registry()
    for artifact_type, entry in built["entries"].items():
        for check in entry["semantic_checks"]:
            assert "execution_required_in_release_mode" in check, artifact_type
            assert "allowed_to_skip" in check, artifact_type
    policy = build_semantic_check_execution()
    validate_artifact(policy, "SemanticCheckExecution.v0")
    assert len(policy["checks"]) >= len(list(all_registry_semantic_check_refs()))


def test_release_chain_result_references_registry_checks() -> None:
    result = build_release_chain_validation_result(release_dir())
    known = all_registry_semantic_check_refs()
    executed: set[str] = set()
    for check in result["checks"]:
        refs = check.get("registry_check_refs", [])
        assert isinstance(refs, list)
        for ref in refs:
            assert ref in known
            executed.add(ref)
    assert executed, "expected at least one registry check ref in validation result"


def test_registry_warns_when_legacy_producer_differs_from_runtime_producer(
    tmp_path: Path,
) -> None:
    registry = build_artifact_registry()
    entry = dict(registry["entries"]["HandoffManifest.v0"])
    entry["producer"] = "legacy-producer"
    entry["runtime_producer"] = "LabTrust-Gym"
    registry["entries"]["HandoffManifest.v0"] = entry
    warnings = audit_registry_producer_fields(registry)
    assert any("producer" in warn and "runtime_producer" in warn for warn in warnings)


def test_conformance_artifact_registry_suite_passes() -> None:
    code, errors = run_conformance("artifact-registry")
    assert code == 0, errors
    report = build_conformance_report_data("artifact-registry")
    assert report["status"] == "passed"
    assert report["results"][0]["suite"] == "artifact-registry"


def test_release_chain_checks_reference_registry_semantic_checks() -> None:
    known = all_registry_semantic_check_refs()
    for spec in RELEASE_CHAIN_CHECK_SPECS:
        refs = RELEASE_CHAIN_REGISTRY_CHECK_REFS.get(spec.check_id, ())
        for ref in refs:
            assert ref in known, f"{spec.check_id} unknown registry ref {ref}"
    result = build_release_chain_validation_result(release_dir())
    for check in result["checks"]:
        assert "registry_check_refs" in check
        for ref in check["registry_check_refs"]:
            assert ref in known


def test_registry_check_artifact_fails_wrong_producer(tmp_path: Path) -> None:
    path = release_dir() / "trace_certificate.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = copy.deepcopy(data)
    bad["producer"] = "LabTrust-Gym"
    bad_path = tmp_path / "bad_trace_certificate.json"
    bad_path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")
    errors = check_artifact_against_registry(bad_path)
    assert any("allowed_runtime_producers" in err for err in errors)


def test_registry_check_artifact_fails_disallowed_status(tmp_path: Path) -> None:
    path = release_dir() / "trace_certificate.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = copy.deepcopy(data)
    bad["status"] = "Draft"
    bad_path = tmp_path / "bad_status.json"
    bad_path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")
    errors = check_artifact_against_registry(bad_path)
    assert any("allowed_statuses" in err for err in errors)


def test_python_shared_hash_vectors_verify() -> None:
    assert verify_shared_vectors() == []


def test_hash_vectors_match_across_python_rust_typescript() -> None:
    test_python_shared_hash_vectors_verify()


def test_component_release_fragment_validates_labtrust_fragment() -> None:
    path = RELEASE / "labtrust_release_fragment.json"
    assert path.is_file(), "run just materialize-labtrust-protocol"
    assert validate_file(path) == "ComponentReleaseFragment.v0"


def test_conformance_suite_runs_handoff_manifest() -> None:
    test_conformance_handoff_manifest_suite_passes()


def test_conformance_handoff_manifest_suite_passes() -> None:
    code, errors = run_conformance("handoff-manifest")
    assert code == 0, errors
    report = build_conformance_report_data("handoff-manifest")
    assert report["status"] == "passed"


def test_conformance_suite_runs_release_chain() -> None:
    test_conformance_release_chain_suite_passes()


def test_conformance_release_chain_suite_passes() -> None:
    code, errors = run_conformance("release-chain")
    assert code == 0, errors
    report = build_conformance_report_data("release-chain")
    assert report["status"] == "passed"


def test_registry_semantic_check_catalog_audits_clean() -> None:
    assert audit_registry_enforcement() == []


def test_release_blocking_chain_layer_refs_in_chain_catalog() -> None:
    assert audit_release_blocking_chain_catalog_coverage() == []


def test_release_blocking_registry_checks_referenced_in_chain_catalog() -> None:
    """Every registry_check_ref emitted by the chain catalog must exist in the registry."""
    known = all_registry_semantic_check_refs()
    for refs in RELEASE_CHAIN_REGISTRY_CHECK_REFS.values():
        for ref in refs:
            assert ref in known


def test_release_chain_result_covers_release_blocking_registry_checks() -> None:
    from pcs_core.registry_semantics import (
        audit_release_chain_registry_coverage,
        collect_required_release_blocking_refs,
    )

    result = build_release_chain_validation_result(release_dir())
    checks = result["checks"]
    deferred = result["deferred_registry_checks"]
    assert audit_release_chain_registry_coverage(checks, deferred) == []
    cited = {
        ref
        for check in checks
        for ref in check.get("registry_check_refs", [])
    }
    deferred_refs = {item["registry_ref"] for item in deferred}
    required = collect_required_release_blocking_refs()
    assert required <= cited | deferred_refs
    for check in checks:
        assert "responsible_component" in check


def test_conformance_report_emits_checks_passed_failed() -> None:
    report = build_conformance_report_data("artifact-registry")
    assert "checks_passed" in report
    assert "checks_failed" in report
    assert "failures" in report
    assert report["checks_failed"] == 0
    validate_artifact(report, "ConformanceReport.v0")


@pytest.mark.parametrize("suite_name", list_suites())
def test_conformance_suite_passes_individually(suite_name: str) -> None:
    code, errors = run_conformance(suite_name)
    assert code == 0, errors
    report = build_conformance_report_data(suite_name)
    validate_artifact(report, "ConformanceReport.v0")
    assert report["status"] == "passed"
    assert report["suite"] == suite_name


def test_conformance_all_suite_passes() -> None:
    code, errors = run_conformance("all")
    assert code == 0, errors
    report = build_conformance_report_data("all")
    validate_artifact(report, "ConformanceReport.v0")
    assert report["status"] == "passed"
    assert report["suites_run"] == len(list_suites())


def test_shared_hash_vectors_cover_all_catalog_types() -> None:
    assert set(VECTOR_SPECS) == set(VECTOR_FILENAMES)
    assert verify_shared_vectors() == []


def test_conformance_suite_runs_component_release_fragment() -> None:
    code, errors = run_conformance("component-release-fragment")
    assert code == 0, errors


def test_hash_vector_files_use_canonical_names() -> None:
    for filename in VECTOR_FILENAMES.values():
        assert (ROOT / "test_vectors" / "hash" / filename).is_file()


def test_migration_report_validates() -> None:
    path = examples_dir() / "migration_report.valid.json"
    assert validate_file(path) == "MigrationReport.v0"


def test_migrate_emits_valid_report(tmp_path: Path) -> None:
    src = examples_dir() / "runtime_receipt.valid.json"
    dest = tmp_path / "runtime_receipt.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    report = migrate_file(dest, from_version="v0", to_version="v0")
    validate_artifact(report, "MigrationReport.v0")
    assert report["status"] == "noop"


@pytest.mark.parametrize(
    ("old_status", "new_status"),
    [
        ("Rejected", "ProofChecked"),
        ("Stale", "ProofChecked"),
        ("RuntimeObserved", "ProofChecked"),
    ],
)
def test_status_transition_forbidden_cases(old_status: str, new_status: str) -> None:
    verdict = check_status_transition(old_status, new_status)
    assert not verdict.allowed


def test_built_release_manifest_matches_fixture_builder() -> None:
    built = release_manifest_valid()
    on_disk = json.loads(RELEASE_MANIFEST_V0.read_text(encoding="utf-8"))
    assert on_disk["chain_root"] == built["chain_root"]


def test_benchmark_ingest_suite_registered() -> None:
    assert "benchmark-ingest" in list_suites()


def test_benchmark_ingest_conformance_passes() -> None:
    code, errors = run_conformance("benchmark-ingest")
    assert code == 0, errors


def test_invalid_pcs_bench_ingest_examples_rejected() -> None:
    for name in (
        "invalid_pcs_bench_ingest_missing_refs.json",
        "invalid_pcs_bench_ingest_bad_ref_digest.json",
        "invalid_pcs_bench_ingest_zero_commit.json",
        "invalid_pcs_bench_ingest_empty_runs.json",
        "invalid_pcs_bench_ingest_path_only.json",
    ):
        path = examples_dir() / name
        if not path.is_file():
            pytest.skip("run materialize_benchmark_producer_examples.py")
        with pytest.raises(ValidationError):
            validate_file(path)
