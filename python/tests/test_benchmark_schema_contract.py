"""Benchmark schema contract and cross-repo compatibility tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.benchmark_compat import validate_compatibility_corpus
from pcs_core.benchmark_metric_registry import (
    build_benchmark_metric_registry,
    load_benchmark_metric_registry,
)
from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate import validate_artifact, validate_file

EXAMPLES = examples_dir() / "benchmarks"
PRODUCER_EXAMPLES = examples_dir() / "benchmark"
INGEST_EXAMPLES = examples_dir() / "benchmark_ingest"


def test_benchmark_metric_registry_has_required_metrics() -> None:
    registry = load_benchmark_metric_registry()
    metrics = registry["metrics"]
    required = {
        "release_reproducibility_score",
        "failure_localization_accuracy",
        "certificate_completeness_score",
        "registry_coverage_score",
        "formal_check_coverage_score",
        "scientific_memory_interpretability_score",
        "repair_hint_quality_score",
        "cross_domain_portability_score",
    }
    assert required <= set(metrics)
    for metric_id, entry in metrics.items():
        assert entry["metric_id"] == metric_id
        assert "numerator" in entry and "denominator" in entry
        assert "minimum_recommended_threshold" in entry


def test_benchmark_metric_registry_matches_builder() -> None:
    built = build_benchmark_metric_registry()
    on_disk = load_benchmark_metric_registry()
    assert set(built["metrics"]) == set(on_disk["metrics"])


@pytest.mark.parametrize(
    "name,artifact_type",
    [
        ("benchmark_case.valid.json", "BenchmarkCase.v0"),
        ("benchmark_run.valid.json", "BenchmarkRun.v0"),
        ("benchmark_report.valid.json", "BenchmarkReport.v0"),
        ("failure_localization_result.valid.json", "FailureLocalizationResult.v0"),
        ("coverage_report.valid.json", "CoverageReport.v0"),
        ("explain_quality_report.valid.json", "ExplainQualityReport.v0"),
        ("profile_coverage_report.valid.json", "ProfileCoverageReport.v0"),
        ("metric_summary.valid.json", "MetricSummary.v0"),
        ("benchmark_artifact_ref.valid.json", "BenchmarkArtifactRef.v0"),
    ],
)
def test_benchmark_valid_examples(name: str, artifact_type: str) -> None:
    path = EXAMPLES / name
    if not path.is_file():
        pytest.skip(f"run python/scripts/materialize_benchmark_examples.py ({name})")
    doc = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(doc, artifact_type)


@pytest.mark.parametrize(
    "name,artifact_type",
    [
        ("pcs_bench_report.valid.json", "BenchmarkReport.v0"),
        ("labtrust_benchmark_case.valid.json", "BenchmarkCase.v0"),
    ],
)
def test_producer_benchmark_examples(name: str, artifact_type: str) -> None:
    path = PRODUCER_EXAMPLES / name
    if not path.is_file():
        pytest.skip("run python/scripts/materialize_benchmark_producer_examples.py")
    doc = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(doc, artifact_type)


@pytest.mark.parametrize(
    "name",
    [
        "labtrust.pcs_bench_ingest.valid.json",
        "certifyedge.pcs_bench_ingest.valid.json",
        "provability_fabric.pcs_bench_ingest.valid.json",
        "scientific_memory.pcs_bench_ingest.valid.json",
    ],
)
def test_benchmark_ingest_examples(name: str) -> None:
    path = INGEST_EXAMPLES / name
    if not path.is_file():
        pytest.skip("run python/scripts/materialize_benchmark_producer_examples.py")
    doc = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(doc, "PcsBenchIngest.v0")
    refs = doc.get("artifact_refs")
    if isinstance(refs, list) and refs:
        for ref in refs:
            validate_artifact(ref, "BenchmarkArtifactRef.v0")


def test_conformance_benchmark_ingest_suite() -> None:
    from pcs_core.conformance import run_conformance

    code, errors = run_conformance("benchmark-ingest")
    assert code == 0, errors


def test_labtrust_benchmark_manifest_validates() -> None:
    path = repo_root() / "benchmarks/labtrust-qc-release/benchmark_manifest.v0.json"
    if not path.is_file():
        pytest.skip("missing LabTrust benchmark manifest")
    doc = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(doc, "BenchmarkSuiteManifest.v0")
    assert doc["case_count"] == len(doc["case_ids"])
    assert doc["suite_id"] == "labtrust-qc-release-v0"


def test_labtrust_registry_matches_manifest() -> None:
    from pcs_core.benchmark_registry_data import benchmark_suite_entries
    from pcs_core.benchmark_suite_manifest import load_benchmark_manifest, registry_matches_manifest
    from pcs_core.paths import repo_root

    entry = benchmark_suite_entries()["labtrust-qc-release-v0"]
    manifest = load_benchmark_manifest(repo_root() / "benchmarks/labtrust-qc-release")
    assert manifest is not None
    assert registry_matches_manifest(entry, manifest) == []


def test_labtrust_valid_case_normalizes_to_null_failure_fields() -> None:
    from pcs_core.benchmark_runner import load_benchmark_case
    from pcs_core.paths import repo_root
    from pcs_core.validate import validate_artifact

    case_path = (
        repo_root()
        / "benchmarks/labtrust-qc-release/valid/labtrust-valid-release-v0/benchmark_case.v0.json"
    )
    if not case_path.is_file():
        pytest.skip("missing LabTrust benchmark gallery case")
    case = load_benchmark_case(case_path)
    assert case["expected_failure_code"] is None
    assert case["expected_system_outcome"] == "admitted"
    validate_artifact(case, "BenchmarkCase.v0")


def test_compatibility_corpus_clean() -> None:
    if not (EXAMPLES / "compatibility").is_dir():
        pytest.skip("run materialize_benchmark_examples.py")
    errors = validate_compatibility_corpus()
    assert errors == [], errors


def test_benchmark_normalize_cli_labtrust_case() -> None:
    import subprocess
    import sys
    import tempfile

    dialect = EXAMPLES / "compatibility" / "labtrust_case_manifest.dialect.json"
    if not dialect.is_file():
        pytest.skip("missing compatibility dialect")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out = Path(tmp.name)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pcs_core.cli",
            "benchmark",
            "normalize",
            "--dialect",
            str(dialect.resolve()),
            "--out",
            str(out),
        ],
        cwd=repo_root() / "python",
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    validate_file(out)


def test_conformance_benchmark_report_suite() -> None:
    from pcs_core.conformance import run_conformance

    code, errors = run_conformance("benchmark-report")
    assert code == 0, errors
