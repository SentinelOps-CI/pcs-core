"""Benchmark protocol extension tests."""

from __future__ import annotations

import json

import pytest

from pcs_core.benchmark_registry import build_benchmark_registry, load_benchmark_registry
from pcs_core.benchmark_runner import (
    discover_cases_for_suite,
    execute_benchmark_case,
    load_benchmark_case,
    run_benchmark_suite,
)
from pcs_core.conformance_run import build_conformance_run
from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate import validate_artifact, validate_file

BENCHMARKS = repo_root() / "benchmarks"
REGISTRY_PATH = examples_dir() / "benchmark_registry.valid.json"


@pytest.fixture(scope="module")
def benchmark_registry() -> dict:
    if not REGISTRY_PATH.is_file():
        pytest.skip("run python/scripts/materialize_benchmark_fixtures.py first")
    return load_benchmark_registry()


def test_benchmark_registry_matches_catalog(benchmark_registry: dict) -> None:
    built = build_benchmark_registry()
    assert set(benchmark_registry["suites"]) == set(built["suites"])
    validate_artifact(benchmark_registry, "BenchmarkRegistry.v0")


def test_benchmark_schemas_validate_examples() -> None:
    if not REGISTRY_PATH.is_file():
        pytest.skip("missing benchmark registry fixture")
    validate_file(REGISTRY_PATH)
    case_path = (
        BENCHMARKS
        / "labtrust-qc-release"
        / "valid"
        / "valid-release-chain"
        / "benchmark_case.v0.json"
    )
    if not case_path.is_file():
        pytest.skip("missing labtrust benchmark case")
    validate_file(case_path)


def test_discover_labtrust_cases(benchmark_registry: dict) -> None:
    cases = discover_cases_for_suite("labtrust-qc-release-v0")
    assert len(cases) >= 6
    kinds = {case["case_kind"] for _, case in cases}
    assert "valid_release" in kinds
    assert "invalid_hash_mismatch" in kinds


def test_execute_labtrust_valid_case() -> None:
    case_path = (
        BENCHMARKS
        / "labtrust-qc-release"
        / "valid"
        / "valid-release-chain"
        / "benchmark_case.v0.json"
    )
    if not case_path.is_file():
        pytest.skip("missing labtrust valid case")
    case = load_benchmark_case(case_path)
    run = execute_benchmark_case(case)
    validate_artifact(run, "BenchmarkRun.v0")
    assert run["observed_status"] == "passed"


def test_run_labtrust_suite_report() -> None:
    expected = BENCHMARKS / "labtrust-qc-release" / "expected_reports" / "benchmark_report.v0.json"
    if not expected.is_file():
        pytest.skip("missing expected benchmark report; materialize fixtures")
    report = run_benchmark_suite("labtrust-qc-release-v0")
    validate_artifact(report, "BenchmarkReport.v0")
    assert report["summary"]["passed_cases"] == report["summary"]["total_cases"]
    golden = json.loads(expected.read_text(encoding="utf-8"))
    assert report["benchmark_suite_id"] == golden["benchmark_suite_id"]
    assert report["summary"]["total_cases"] == golden["summary"]["total_cases"]


@pytest.mark.parametrize(
    ("suite_id", "fixture_root", "golden_name"),
    [
        (
            "labtrust-qc-release-v0",
            "labtrust-qc-release",
            "benchmark_report.labtrust-qc-release-v0.v0.json",
        ),
        (
            "tool-use-safety-v0",
            "tool-use-safety",
            "benchmark_report.tool-use-safety-v0.v0.json",
        ),
        (
            "computation-reproducibility-v0",
            "computation-reproducibility",
            "benchmark_report.computation-reproducibility-v0.v0.json",
        ),
        (
            "cross-domain-release-chain-v0",
            "cross-domain",
            "benchmark_report.cross-domain-release-chain-v0.v0.json",
        ),
        (
            "formal-trust-kernel-v0",
            "cross-domain",
            "benchmark_report.formal-trust-kernel-v0.v0.json",
        ),
        (
            "scientific-memory-rendering-v0",
            "labtrust-qc-release",
            "benchmark_report.scientific-memory-rendering-v0.v0.json",
        ),
    ],
)
def test_golden_benchmark_report_matches_suite(
    suite_id: str,
    fixture_root: str,
    golden_name: str,
) -> None:
    golden_path = BENCHMARKS / fixture_root / "expected_reports" / golden_name
    if not golden_path.is_file():
        pytest.skip(f"missing golden report {golden_path}")
    report = run_benchmark_suite(suite_id)
    validate_artifact(report, "BenchmarkReport.v0")
    summary = report["summary"]
    assert summary["passed_cases"] == summary["total_cases"], report.get("failures", [])
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert report["benchmark_suite_id"] == golden["benchmark_suite_id"]
    assert summary["total_cases"] == golden["summary"]["total_cases"]


def test_conformance_run_bridge() -> None:
    run = build_conformance_run("release-chain")
    validate_artifact(run, "ConformanceRun.v0")
    assert run["suite"] == "release-chain"


@pytest.mark.parametrize(
    "suite_id",
    [
        "labtrust-qc-release-v0",
        "tool-use-safety-v0",
        "computation-reproducibility-v0",
        "formal-trust-kernel-v0",
        "scientific-memory-rendering-v0",
    ],
)
def test_benchmark_suite_all_cases_pass(suite_id: str) -> None:
    if not REGISTRY_PATH.is_file():
        pytest.skip("missing benchmark registry")
    report = run_benchmark_suite(suite_id)
    validate_artifact(report, "BenchmarkReport.v0")
    summary = report["summary"]
    assert summary["passed_cases"] == summary["total_cases"], report.get("failures", [])


def test_formal_suite_has_three_cases() -> None:
    cases = discover_cases_for_suite("formal-trust-kernel-v0")
    assert len(cases) == 3
    assert {case["case_id"] for _, case in cases} == {
        "formal-labtrust-lean-check",
        "formal-tool-use-lean-check",
        "formal-computation-lean-check",
    }


def test_scientific_memory_suite_cases() -> None:
    cases = discover_cases_for_suite("scientific-memory-rendering-v0")
    assert len(cases) == 2
    assert {case["case_id"] for _, case in cases} == {
        "labtrust-valid-release-v0",
        "labtrust-scientific-memory-import-failure-v0",
    }


def test_validate_benchmark_fixtures_clean() -> None:
    from pcs_core.benchmark_runner import validate_benchmark_fixtures

    if not REGISTRY_PATH.is_file():
        pytest.skip("missing benchmark registry")
    assert validate_benchmark_fixtures() == []


def test_labtrust_gallery_evaluator_paths() -> None:
    from pcs_core.benchmark_labtrust_gallery import detect_gallery_failure, is_labtrust_gallery_case
    from pcs_core.benchmark_runner import execute_benchmark_case, load_benchmark_case

    valid_path = (
        BENCHMARKS / "labtrust-qc-release/valid/labtrust-valid-release-v0/benchmark_case.v0.json"
    )
    tamper_path = (
        BENCHMARKS
        / "labtrust-qc-release/invalid/labtrust-trace-hash-tamper-v0/benchmark_case.v0.json"
    )
    if not valid_path.is_file() or not tamper_path.is_file():
        pytest.skip("missing labtrust gallery fixtures")
    valid_case = load_benchmark_case(valid_path)
    tamper_case = load_benchmark_case(tamper_path)
    assert is_labtrust_gallery_case(valid_case)
    valid_dir = repo_root() / valid_case["input_artifacts"]["release_directory"]
    tamper_dir = repo_root() / tamper_case["input_artifacts"]["release_directory"]
    assert detect_gallery_failure(valid_dir) == (None, None)
    assert detect_gallery_failure(tamper_dir)[0] == "trace_hash_mismatch"
    assert execute_benchmark_case(valid_case)["observed_status"] == "passed"
    assert execute_benchmark_case(tamper_case)["observed_status"] == "passed"


def test_valid_benchmark_run_has_null_failure_fields() -> None:
    from pcs_core.benchmark_runner import execute_benchmark_case, load_benchmark_case

    case_path = (
        repo_root()
        / "benchmarks/labtrust-qc-release/valid/labtrust-valid-release-v0/benchmark_case.v0.json"
    )
    if not case_path.is_file():
        pytest.skip("run materialize_benchmark_fixtures.py")
    case = load_benchmark_case(case_path)
    run = execute_benchmark_case(case)
    assert run["observed_status"] == "passed"
    assert run["observed_failure_code"] is None
    assert run["observed_responsible_component"] is None
    assert run["observed_repair_hint"] is None
    validate_artifact(run, "BenchmarkRun.v0")


def test_benchmark_report_accepts_conformance_refs() -> None:
    report = {
        "schema_version": "v0",
        "report_id": "benchmark-report-test",
        "benchmark_suite_id": "labtrust-qc-release-v0",
        "runs": [],
        "metrics": ["failure_localization_accuracy"],
        "metric_summaries": [
            {
                "schema_version": "v0",
                "metric_id": "failure_localization_accuracy",
                "score": 1.0,
                "applicability": "insufficient_cases",
                "numerator": 0,
                "denominator": 0,
                "reason": "no invalid cases",
                "details": {},
                "source_repo": "https://github.com/SentinelOps-CI/pcs-core",
                "source_commit": "d444444444444444444444444444444444444444",
                "signature_or_digest": "sha256:" + "0" * 64,
            },
        ],
        "summary": {
            "total_cases": 0,
            "passed_cases": 0,
            "failed_cases": 0,
            "expected_failures_detected": 0,
            "unexpected_passes": 0,
            "unexpected_failures": 0,
            "failure_localization_accuracy": 1.0,
            "repair_hint_accuracy": 1.0,
            "formal_check_coverage": 1.0,
            "registry_coverage": 1.0,
            "scientific_memory_render_coverage": 1.0,
        },
        "coverage": {},
        "failures": [],
        "conformance_refs": [{"suite": "release-chain", "run_id": "conf-run-release-chain-test"}],
        "source_repo": "https://github.com/SentinelOps-CI/pcs-core",
        "source_commit": "d444444444444444444444444444444444444444",
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    validate_artifact(report, "BenchmarkReport.v0")
