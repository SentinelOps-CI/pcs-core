"""Benchmark ingest golden validation and release-grade adequacy policy."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate import ValidationError, validate_artifact, validate_file

INGEST_EXAMPLES_DIR = examples_dir() / "benchmark_ingest"
_COMPAT = "examples/benchmarks/compatibility/"

GOLDEN_INGEST_FILES: tuple[str, ...] = (
    "labtrust.pcs_bench_ingest.valid.json",
    "certifyedge.pcs_bench_ingest.valid.json",
    "provability_fabric.pcs_bench_ingest.valid.json",
    "scientific_memory.pcs_bench_ingest.valid.json",
)

PRODUCER_INGEST_SOURCES: dict[str, dict[str, str]] = {
    "labtrust.pcs_bench_ingest.valid.json": {
        "producer_id": "labtrust-gym",
        "producer_repo": "LabTrust-Gym",
        "producer_command": "python benchmark_reproducibility.py",
        "dialect_fixture": f"{_COMPAT}labtrust_case_manifest.dialect.json",
        "pcs_core_generator": "build_labtrust_pcs_bench_ingest",
    },
    "certifyedge.pcs_bench_ingest.valid.json": {
        "producer_id": "certifyedge",
        "producer_repo": "CertifyEdge",
        "producer_command": "certifyedge benchmark certificates",
        "dialect_fixture": f"{_COMPAT}certifyedge_certificate_benchmark.dialect.json",
        "pcs_core_generator": "build_certifyedge_pcs_bench_ingest",
    },
    "provability_fabric.pcs_bench_ingest.valid.json": {
        "producer_id": "provability-fabric",
        "producer_repo": "provability-fabric",
        "producer_command": "pf benchmark admission",
        "dialect_fixture": f"{_COMPAT}pf_admission_explain_quality.dialect.json",
        "pcs_core_generator": "build_pf_pcs_bench_ingest",
    },
    "scientific_memory.pcs_bench_ingest.valid.json": {
        "producer_id": "scientific-memory",
        "producer_repo": "scientific-memory",
        "producer_command": "pcs-benchmark-rendering",
        "dialect_fixture": f"{_COMPAT}scientific_memory_render_benchmark.dialect.json",
        "pcs_core_generator": "build_scientific_memory_pcs_bench_ingest",
    },
}

EMBEDDED_ARRAY_ARTIFACT_TYPES: dict[str, str] = {
    "benchmark_runs": "BenchmarkRun.v0",
    "coverage_reports": "CoverageReport.v0",
    "failure_localization_reports": "FailureLocalizationResult.v0",
    "explain_quality_reports": "ExplainQualityReport.v0",
    "profile_coverage_reports": "ProfileCoverageReport.v0",
}

_ZERO_COMMIT_RE = re.compile(r"^[0f]{40}$", re.IGNORECASE)

PRODUCER_RELEASE_GRADE_EXPECTATIONS: dict[str, dict[str, bool]] = {
    "labtrust-gym": {
        "benchmark_runs": True,
        "coverage_reports": True,
        "commands": True,
    },
    "certifyedge": {
        "coverage_reports": True,
        "profile_coverage_reports": True,
        "commands": True,
    },
    "provability-fabric": {
        "failure_localization_reports": True,
        "explain_quality_reports": True,
        "profile_coverage_reports": True,
        "commands": True,
    },
    "scientific-memory": {
        "explain_quality_reports": True,
        "coverage_reports": True,
        "commands": True,
    },
}


def is_placeholder_commit(commit: Any) -> bool:
    if not isinstance(commit, str) or len(commit) != 40:
        return True
    return bool(_ZERO_COMMIT_RE.match(commit))


def validate_embedded_artifacts_in_ingest(ingest: dict[str, Any], *, prefix: str = "") -> list[str]:
    errors: list[str] = []
    for field, artifact_type in EMBEDDED_ARRAY_ARTIFACT_TYPES.items():
        rows = ingest.get(field)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{prefix}{field}[{index}] must be an object")
                continue
            try:
                validate_artifact(row, artifact_type)
            except ValidationError as exc:
                errors.append(f"{prefix}{field}[{index}] ({artifact_type}): {exc}")
                errors.extend(f"{prefix}{field}[{index}]: {err}" for err in exc.errors)
    refs = ingest.get("artifact_refs")
    if isinstance(refs, list):
        for index, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(f"{prefix}artifact_refs[{index}] must be an object")
                continue
            try:
                validate_artifact(ref, "BenchmarkArtifactRef.v0")
            except ValidationError as exc:
                errors.append(f"{prefix}artifact_refs[{index}]: {exc}")
    return errors


def assess_ingest_adequacy_tier(ingest: dict[str, Any]) -> tuple[str, list[str]]:
    """Return adequacy tier and findings (schema-valid through external-review)."""
    findings: list[str] = []
    producer_id = str(ingest.get("producer_id", ""))
    if is_placeholder_commit(ingest.get("source_commit")):
        findings.append("ingest source_commit is placeholder (developer-grade at best)")
    commands = ingest.get("commands")
    if not isinstance(commands, list) or not commands:
        findings.append("commands is empty (not release-grade for live producer runs)")
    expectations = PRODUCER_RELEASE_GRADE_EXPECTATIONS.get(producer_id, {})
    for field, required in expectations.items():
        rows = ingest.get(field)
        if required and (not isinstance(rows, list) or not rows):
            findings.append(f"producer {producer_id!r} expects non-empty {field} for release-grade")
    refs = ingest.get("artifact_refs")
    if producer_id in PRODUCER_RELEASE_GRADE_EXPECTATIONS and (
        not isinstance(refs, list) or not refs
    ):
        findings.append("producer export requires artifact_refs for release-grade provenance")
    missing_required = [item for item in findings if "expects non-empty" in item]
    soft_findings = [item for item in findings if item not in missing_required]
    if missing_required:
        tier = "schema-valid"
    elif not soft_findings:
        tier = "release-grade"
    else:
        tier = "developer-grade"
    if (
        tier == "release-grade"
        and not is_placeholder_commit(ingest.get("source_commit"))
        and isinstance(refs, list)
        and refs
        and commands
    ):
        tier = "external-review-grade"
    return tier, findings


def validate_benchmark_ingest_file(path: Path, *, check_release_grade: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        validate_file(path)
    except ValidationError as exc:
        errors.append(f"{path.name}: {exc}")
        errors.extend(exc.errors)
        return errors
    import json

    ingest = json.loads(path.read_text(encoding="utf-8"))
    errors.extend(validate_embedded_artifacts_in_ingest(ingest, prefix=f"{path.name}: "))
    if check_release_grade:
        tier, findings = assess_ingest_adequacy_tier(ingest)
        if tier not in ("release-grade", "external-review-grade"):
            errors.append(
                f"{path.name}: adequacy tier {tier} (release-grade required); "
                + "; ".join(findings),
            )
    return errors


def validate_all_benchmark_ingest_examples(
    *,
    ingest_dir: Path | None = None,
    check_release_grade: bool = False,
) -> list[str]:
    root = ingest_dir or INGEST_EXAMPLES_DIR
    errors: list[str] = []
    for name in GOLDEN_INGEST_FILES:
        path = root / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(repo_root()).as_posix()}")
            continue
        errors.extend(validate_benchmark_ingest_file(path, check_release_grade=check_release_grade))
    return errors


def build_provenance_manifest() -> dict[str, Any]:
    import json

    entries: list[dict[str, Any]] = []
    for name, meta in PRODUCER_INGEST_SOURCES.items():
        path = INGEST_EXAMPLES_DIR / name
        entry: dict[str, Any] = {
            "golden_file": f"examples/benchmark_ingest/{name}",
            "dialect_fixture": meta["dialect_fixture"],
            "producer_id": meta["producer_id"],
            "producer_repo": meta["producer_repo"],
            "producer_command": meta["producer_command"],
            "pcs_core_generator": meta["pcs_core_generator"],
        }
        if path.is_file():
            ingest = json.loads(path.read_text(encoding="utf-8"))
            tier, findings = assess_ingest_adequacy_tier(ingest)
            entry["adequacy_tier"] = tier
            if findings:
                entry["adequacy_findings"] = findings
        entries.append(entry)
    return {
        "schema_version": "v0",
        "contract": "PcsBenchIngest.v0",
        "policy_doc": "docs/benchmark-ingest-contract.md",
        "release_grade_doc": "docs/release-grade-benchmark-evidence.md",
        "entries": entries,
    }


def summarize_ingest_adequacy(*, ingest_dir: Path | None = None) -> list[dict[str, Any]]:
    import json

    root = ingest_dir or INGEST_EXAMPLES_DIR
    rows: list[dict[str, Any]] = []
    for name in GOLDEN_INGEST_FILES:
        path = root / name
        if not path.is_file():
            rows.append({"file": name, "tier": "missing", "findings": ["file not found"]})
            continue
        ingest = json.loads(path.read_text(encoding="utf-8"))
        tier, findings = assess_ingest_adequacy_tier(ingest)
        rows.append({"file": name, "tier": tier, "findings": findings})
    return rows


def validate_benchmark_ingest_supporting_artifacts() -> list[str]:
    """Validate canonical benchmark artifact types used by the ingest contract."""
    errors: list[str] = []
    benchmarks_root = examples_dir() / "benchmarks"
    for name, artifact_type in (
        ("benchmark_run.valid.json", "BenchmarkRun.v0"),
        ("coverage_report.valid.json", "CoverageReport.v0"),
        ("failure_localization_result.valid.json", "FailureLocalizationResult.v0"),
        ("explain_quality_report.valid.json", "ExplainQualityReport.v0"),
        ("profile_coverage_report.valid.json", "ProfileCoverageReport.v0"),
        ("metric_summary.valid.json", "MetricSummary.v0"),
        ("benchmark_report.valid.json", "BenchmarkReport.v0"),
        ("benchmark_artifact_ref.valid.json", "BenchmarkArtifactRef.v0"),
    ):
        path = benchmarks_root / name
        if not path.is_file():
            errors.append(f"missing examples/benchmarks/{name}")
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"benchmarks/{name}: {exc}")
    return errors
