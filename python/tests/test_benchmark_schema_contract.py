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
        ("labtrust_case.valid.json", "BenchmarkCase.v0"),
        ("certifyedge_certificate_benchmark.valid.json", "CoverageReport.v0"),
        ("pf_admission_benchmark.valid.json", "ExplainQualityReport.v0"),
        ("scientific_memory_rendering_benchmark.valid.json", "ExplainQualityReport.v0"),
        ("pcs_core_benchmark_report.valid.json", "BenchmarkReport.v0"),
    ],
)
def test_producer_benchmark_examples(name: str, artifact_type: str) -> None:
    path = PRODUCER_EXAMPLES / name
    if not path.is_file():
        pytest.skip("run python/scripts/materialize_benchmark_producer_examples.py")
    doc = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(doc, artifact_type)


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
