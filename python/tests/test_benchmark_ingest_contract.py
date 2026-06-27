"""PcsBenchIngest.v0 and BenchmarkArtifactRef.v0 contract tests."""

from __future__ import annotations

import copy
import json

import pytest

from pcs_core.benchmark_compat import build_pcs_bench_ingest
from pcs_core.benchmark_ingest import (
    GOLDEN_INGEST_FILES,
    assess_ingest_adequacy_tier,
    run_benchmark_ingest_contract_checks,
    validate_all_benchmark_ingest_examples,
)
from pcs_core.hash import canonical_hash
from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate import ValidationError, validate_artifact, validate_file

INGEST_DIR = examples_dir() / "benchmark_ingest"


def _load_ingest(name: str) -> dict:
    path = INGEST_DIR / name
    if not path.is_file():
        pytest.skip("run python/scripts/materialize_benchmark_producer_examples.py")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name",
    [
        "labtrust.pcs_bench_ingest.valid.json",
        "certifyedge.pcs_bench_ingest.valid.json",
        "provability_fabric.pcs_bench_ingest.valid.json",
        "scientific_memory.pcs_bench_ingest.valid.json",
    ],
)
def test_producer_ingest_has_bidirectional_refs(name: str) -> None:
    doc = _load_ingest(name)
    validate_artifact(doc, "PcsBenchIngest.v0")
    refs = doc.get("artifact_refs")
    assert isinstance(refs, list) and refs, f"{name} must include artifact_refs"
    for ref in refs:
        validate_artifact(ref, "BenchmarkArtifactRef.v0")


def test_ingest_rejects_mismatched_ref_digest() -> None:
    doc = _load_ingest("scientific_memory.pcs_bench_ingest.valid.json")
    bad = copy.deepcopy(doc)
    bad["artifact_refs"][0]["sha256"] = "sha256:" + "f" * 64
    with pytest.raises(ValidationError) as exc:
        validate_artifact(bad, "PcsBenchIngest.v0")
    assert any("sha256 does not match" in err for err in exc.value.errors)


def test_ingest_rejects_producer_without_refs() -> None:
    doc = _load_ingest("certifyedge.pcs_bench_ingest.valid.json")
    bad = copy.deepcopy(doc)
    del bad["artifact_refs"]
    with pytest.raises(ValidationError) as exc:
        validate_artifact(bad, "PcsBenchIngest.v0")
    assert any("requires artifact_refs" in err for err in exc.value.errors)


def test_ingest_rejects_orphan_ref() -> None:
    doc = _load_ingest("certifyedge.pcs_bench_ingest.valid.json")
    bad = copy.deepcopy(doc)
    bad["artifact_refs"].append(
        {
            "schema_version": "v0",
            "artifact_type": "FailureLocalizationResult.v0",
            "path": "reports/nonexistent.failure_localization.v0.json",
            "sha256": "sha256:" + "a" * 64,
            "role": "producer_export",
            "source_repo": doc["source_repo"],
            "source_commit": doc["source_commit"],
            "signature_or_digest": "sha256:" + "b" * 64,
        },
    )
    with pytest.raises(ValidationError) as exc:
        validate_artifact(bad, "PcsBenchIngest.v0")
    assert any("no embedded objects" in err or "does not match" in err for err in exc.value.errors)


def test_ingest_rejects_duplicate_ref_paths() -> None:
    doc = _load_ingest("provability_fabric.pcs_bench_ingest.valid.json")
    bad = copy.deepcopy(doc)
    bad["artifact_refs"].append(copy.deepcopy(bad["artifact_refs"][0]))
    with pytest.raises(ValidationError) as exc:
        validate_artifact(bad, "PcsBenchIngest.v0")
    assert any("duplicate path" in err for err in exc.value.errors)


def test_benchmark_artifact_ref_example_validates() -> None:
    path = examples_dir() / "benchmarks" / "benchmark_artifact_ref.valid.json"
    if not path.is_file():
        pytest.skip("run python/scripts/materialize_benchmark_examples.py")
    validate_file(path)


def test_pcs_core_ingest_without_refs_allowed() -> None:
    body = build_pcs_bench_ingest(
        producer_id="pcs-core",
        suite_id="test-suite",
        workflow_id="test.workflow",
        source_repo="https://github.com/SentinelOps-CI/pcs-core",
    )
    validate_artifact(body, "PcsBenchIngest.v0")


def test_validate_benchmark_ingest_examples_script_surface() -> None:
    assert run_benchmark_ingest_contract_checks() == []
    assert len(GOLDEN_INGEST_FILES) == 4


def test_contract_gate_release_grade() -> None:
    assert run_benchmark_ingest_contract_checks(check_release_grade=True) == []


def test_golden_ingest_meets_developer_grade() -> None:
    for name in GOLDEN_INGEST_FILES:
        doc = _load_ingest(name)
        tier, _findings = assess_ingest_adequacy_tier(doc)
        assert tier in ("developer-grade", "release-grade", "external-review-grade"), (
            f"{name}: expected developer-grade+, got {tier}"
        )


def test_golden_ingest_meets_release_grade_gate() -> None:
    assert validate_all_benchmark_ingest_examples(check_release_grade=True) == []


def test_artifact_ref_record_digest() -> None:
    doc = _load_ingest("scientific_memory.pcs_bench_ingest.valid.json")
    ref = doc["artifact_refs"][0]
    expected = canonical_hash({k: v for k, v in ref.items() if k != "signature_or_digest"})
    assert ref["signature_or_digest"] == expected


def test_benchmark_validate_ingest_cli() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "pcs_core.cli", "benchmark", "validate-ingest"],
        cwd=repo_root() / "python",
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK benchmark ingest" in proc.stdout


def test_conformance_benchmark_ingest_suite() -> None:
    from pcs_core.conformance import run_conformance

    code, errors = run_conformance("benchmark-ingest")
    assert code == 0, errors


@pytest.mark.parametrize(
    ("producer_id", "strip_field"),
    [
        ("provability-fabric", "failure_localization_reports"),
        ("provability-fabric", "explain_quality_reports"),
        ("certifyedge", "profile_coverage_reports"),
        ("scientific-memory", "explain_quality_reports"),
        ("labtrust-gym", "coverage_reports"),
    ],
)
def test_release_grade_requires_producer_specific_arrays(
    producer_id: str,
    strip_field: str,
) -> None:
    name_by_producer = {
        "labtrust-gym": "labtrust.pcs_bench_ingest.valid.json",
        "certifyedge": "certifyedge.pcs_bench_ingest.valid.json",
        "provability-fabric": "provability_fabric.pcs_bench_ingest.valid.json",
        "scientific-memory": "scientific_memory.pcs_bench_ingest.valid.json",
    }
    doc = copy.deepcopy(_load_ingest(name_by_producer[producer_id]))
    assert doc.get("producer_id") == producer_id
    doc[strip_field] = []
    tier, findings = assess_ingest_adequacy_tier(doc)
    assert tier == "schema-valid"
    assert any(strip_field in item for item in findings)


def test_provenance_manifest_lists_all_goldens() -> None:
    path = INGEST_DIR / "provenance.manifest.json"
    if not path.is_file():
        pytest.skip("run materialize_benchmark_producer_examples.py")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest.get("contract_version") == "1.0"
    listed = {entry["golden_file"].split("/")[-1] for entry in manifest.get("entries", [])}
    assert listed == set(GOLDEN_INGEST_FILES)
    for entry in manifest.get("entries", []):
        assert entry.get("adequacy_tier") == "external-review-grade", entry["golden_file"]
        materialized = entry.get("materialized_from", "")
        assert materialized
        assert "\\" not in materialized, "use posix-relative materialized_from paths"
