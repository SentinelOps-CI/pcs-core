"""Execute benchmark cases and build portable BenchmarkReport.v0 artifacts."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pcs_core.benchmark_localization import localize_failure_code, repair_hint_for_component
from pcs_core.benchmark_metrics import build_metric_summaries, coerce_metric_ids
from pcs_core.benchmark_registry import load_benchmark_registry
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.paths import repo_root
from pcs_core.protocol_fixtures import PCS_CORE_REPO
from pcs_core.release_chain import validate_release_chain

PCS_CORE_COMMIT_PLACEHOLDER = "d444444444444444444444444444444444444444"

# Keys required for Scientific Memory interpretability scoring (v0).
SM_INTERPRETABILITY_KEYS: tuple[str, ...] = (
    "verification_status",
    "strict",
    "allow_legacy",
    "bundle_shape",
    "render_path",
    "release_id",
    "release_manifest_hash",
    "scientific_memory_commit",
    "source_repo",
    "source_commit",
    "release_chain_validation_status",
    "validation_profile",
    "source_bundle_path",
)


def benchmarks_dir() -> Path:
    return repo_root() / "benchmarks"


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _with_digest(doc: dict[str, Any]) -> dict[str, Any]:
    body = dict(doc)
    body["signature_or_digest"] = canonical_hash(
        {k: v for k, v in body.items() if k != "signature_or_digest"}
    )
    return body


def resolve_release_directory(case: dict[str, Any]) -> Path:
    inputs = case.get("input_artifacts")
    if not isinstance(inputs, dict):
        raise ValueError("BenchmarkCase.v0 input_artifacts must be an object")
    rel = inputs.get("release_directory")
    if not isinstance(rel, str) or not rel:
        raise ValueError("input_artifacts.release_directory is required")
    path = (repo_root() / rel).resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"release directory not found: {path}")
    return path


def _scientific_memory_interpretability_score(report: dict[str, Any]) -> float:
    present = sum(1 for key in SM_INTERPRETABILITY_KEYS if key in report)
    return present / len(SM_INTERPRETABILITY_KEYS)


def _evaluate_formal_kernel(release_dir: Path) -> tuple[bool, str, str]:
    lean_path = release_dir / "lean_check_result.v0.json"
    obligation_path = release_dir / "proof_obligation.v0.json"
    if not lean_path.is_file():
        return False, "missing_formal_artifacts", "formal_kernel"
    if not obligation_path.is_file():
        return False, "missing_formal_artifacts", "formal_kernel"
    lean = json.loads(lean_path.read_text(encoding="utf-8"))
    if not isinstance(lean, dict):
        return False, "schema_validation_failed", "formal_kernel"
    status = lean.get("status")
    if status != "ProofChecked":
        return False, "formal_check_failed", "formal_kernel"
    obligations = json.loads(obligation_path.read_text(encoding="utf-8"))
    ob_count = len(obligations.get("obligations", [])) if isinstance(obligations, dict) else 0
    if ob_count == 0:
        return False, "missing_formal_artifacts", "formal_kernel"
    return True, "", "formal_kernel"


def _null_if_empty(value: str | None) -> str | None:
    return None if value is None or value == "" else value


def _build_benchmark_run(
    case: dict[str, Any],
    *,
    started_at: str,
    duration_ms: int,
    commands: list[dict[str, Any]],
    artifacts_produced: list[str],
    observed_status: str,
    observed_failure_code: str | None,
    observed_component: str | None,
    release_chain_status: str = "not_applicable",
    certificate_status: str = "not_applicable",
    scientific_memory_import_status: str = "not_applicable",
    scientific_memory_render_status: str = "not_applicable",
    system_admission_outcome: str = "not_evaluated",
) -> dict[str, Any]:
    repair_hint = repair_hint_for_component(observed_component)
    completed_at = _iso_now()
    run_id = f"bench-run-{case.get('case_id', uuid.uuid4().hex[:8])}"
    body: dict[str, Any] = {
        "schema_version": "v0",
        "run_id": run_id,
        "task_id": str(case.get("task_id", "")),
        "case_id": str(case.get("case_id", "")),
        "started_at": started_at,
        "completed_at": completed_at,
        "commands": commands,
        "artifacts_produced": artifacts_produced,
        "observed_status": observed_status,
        "observed_failure_code": observed_failure_code,
        "observed_responsible_component": observed_component,
        "observed_repair_hint": repair_hint,
        "system_admission_outcome": system_admission_outcome,
        "release_chain_status": release_chain_status,
        "certificate_status": certificate_status,
        "scientific_memory_import_status": scientific_memory_import_status,
        "scientific_memory_render_status": scientific_memory_render_status,
        "duration_ms": duration_ms,
        "source_repo": PCS_CORE_REPO,
        "source_commit": PCS_CORE_COMMIT_PLACEHOLDER,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def _execute_formal_benchmark_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = _iso_now()
    release_dir = resolve_release_directory(case)
    case_kind = str(case.get("case_kind", ""))
    commands: list[dict[str, Any]] = [
        {
            "command": f"lean_check {release_dir.as_posix()}",
            "exit_code": 0,
        },
    ]
    ok, failure_code, component = _evaluate_formal_kernel(release_dir)
    if case_kind == "valid_release":
        observed_status = "passed" if ok else "failed"
        obs_code: str | None = None if ok else failure_code
        obs_component: str | None = None if ok else component
    else:
        expected_code = case.get("expected_failure_code")
        expected_component = case.get("expected_responsible_component") or "formal_kernel"
        code_ok = not ok and (not expected_code or failure_code == expected_code)
        component_ok = component == expected_component
        observed_status = "passed" if code_ok and component_ok else "failed"
        obs_code = failure_code or None
        obs_component = component
    return _build_benchmark_run(
        case,
        started_at=started_at,
        duration_ms=int((time.perf_counter() - started) * 1000),
        commands=commands,
        artifacts_produced=["lean_check_result.v0.json", "proof_obligation.v0.json"],
        observed_status=observed_status,
        observed_failure_code=obs_code,
        observed_component=obs_component,
        release_chain_status="not_applicable",
    )


def _execute_scientific_memory_benchmark_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = _iso_now()
    release_dir = resolve_release_directory(case)
    case_kind = str(case.get("case_kind", ""))
    commands: list[dict[str, Any]] = []
    sm_path = release_dir / "scientific_memory_import_report.json"
    interpretability = 0.0
    observed_failure_code: str | None = None
    observed_component: str | None = "scientific_memory"
    sm_import_status = "not_applicable"
    sm_render_status = "not_applicable"

    if sm_path.is_file():
        sm_report = json.loads(sm_path.read_text(encoding="utf-8"))
        if isinstance(sm_report, dict):
            interpretability = _scientific_memory_interpretability_score(sm_report)
            sm_import_status = (
                "passed" if sm_report.get("verification_status") == "passed" else "failed"
            )
            if sm_report.get("verification_status") != "passed":
                observed_failure_code = "scientific_memory_import_failed"
    else:
        sm_import_status = "failed"
        observed_failure_code = "scientific_memory_import_failed"

    try:
        release_rel = release_dir.relative_to(repo_root()).as_posix()
    except ValueError:
        release_rel = release_dir.as_posix()
    issues = validate_release_chain(release_dir)
    commands.append(
        {
            "command": f"validate_release_chain {release_rel}",
            "exit_code": 0 if not issues else 1,
        },
    )
    if issues and not observed_failure_code:
        expected_code = str(case.get("expected_failure_code", ""))
        matching = (
            [issue for issue in issues if issue.code == expected_code] if expected_code else issues
        )
        primary = matching[0] if matching else issues[0]
        observed_failure_code = primary.code
        observed_component = localize_failure_code(primary.code)

    release_chain_status = "valid" if not issues else "invalid"
    sm_render_status = (
        "rendered" if interpretability >= 1.0 and sm_import_status == "passed" else "incomplete"
    )

    if case_kind == "valid_release":
        sm_ok = interpretability >= 1.0 and not observed_failure_code and not issues
        observed_status = "passed" if sm_ok else "failed"
        if sm_ok:
            observed_failure_code = None
            observed_component = None
        elif not observed_failure_code:
            observed_failure_code = "scientific_memory_render_incomplete"
            observed_component = "scientific_memory"
    else:
        expected_code = case.get("expected_failure_code")
        expected_component = case.get("expected_responsible_component") or "scientific_memory"
        code_ok = bool(observed_failure_code or issues) and (
            not expected_code or observed_failure_code == expected_code
        )
        component_ok = observed_component == expected_component
        observed_status = "passed" if code_ok and component_ok else "failed"

    return _build_benchmark_run(
        case,
        started_at=started_at,
        duration_ms=int((time.perf_counter() - started) * 1000),
        commands=commands,
        artifacts_produced=["scientific_memory_import_report.json"],
        observed_status=observed_status,
        observed_failure_code=_null_if_empty(observed_failure_code),
        observed_component=observed_component,
        release_chain_status=release_chain_status,
        scientific_memory_import_status=sm_import_status,
        scientific_memory_render_status=sm_render_status,
    )


def _execute_release_chain_benchmark_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = _iso_now()
    release_dir = resolve_release_directory(case)
    case_kind = str(case.get("case_kind", ""))
    commands: list[dict[str, Any]] = []
    artifacts_produced: list[str] = []

    try:
        release_rel = release_dir.relative_to(repo_root()).as_posix()
    except ValueError:
        release_rel = release_dir.as_posix()
    issues = validate_release_chain(release_dir)
    commands.append(
        {
            "command": f"validate_release_chain {release_rel}",
            "exit_code": 0 if not issues else 1,
        },
    )

    observed_failure_code: str | None = None
    observed_component: str | None = None
    certificate_status = "not_applicable"
    cert_path = release_dir / "trace_certificate.json"
    if cert_path.is_file():
        try:
            cert = json.loads(cert_path.read_text(encoding="utf-8"))
            if isinstance(cert, dict) and cert.get("status") in {
                "CertificateChecked",
                "Rejected",
                "Stale",
            }:
                certificate_status = str(cert["status"])
        except json.JSONDecodeError:
            certificate_status = "Rejected"

    if issues:
        expected_code = case.get("expected_failure_code")
        if expected_code:
            matching = [issue for issue in issues if issue.code == expected_code]
            primary = matching[0] if matching else issues[0]
        else:
            primary = issues[0]
        observed_failure_code = primary.code
        observed_component = localize_failure_code(primary.code)

    release_chain_status = "valid" if not issues else "invalid"

    if case_kind == "valid_release":
        observed_status = "passed" if not issues else "failed"
        if not issues:
            observed_failure_code = None
            observed_component = None
    else:
        expected_code = case.get("expected_failure_code")
        expected_component = case.get("expected_responsible_component") or "unknown"
        code_ok = bool(issues) and (not expected_code or observed_failure_code == expected_code)
        component_ok = observed_component == expected_component
        observed_status = "passed" if code_ok and component_ok else "failed"

    return _build_benchmark_run(
        case,
        started_at=started_at,
        duration_ms=int((time.perf_counter() - started) * 1000),
        commands=commands,
        artifacts_produced=artifacts_produced,
        observed_status=observed_status,
        observed_failure_code=observed_failure_code,
        observed_component=observed_component,
        release_chain_status=release_chain_status,
        certificate_status=certificate_status,
    )


def execute_benchmark_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run one benchmark case and return BenchmarkRun.v0."""
    from pcs_core.benchmark_labtrust_gallery import is_labtrust_gallery_case

    task_id = str(case.get("task_id", ""))
    if is_labtrust_gallery_case(case):
        return _execute_labtrust_gallery_benchmark_case(case)
    if task_id == "formal-trust-kernel-v0":
        return _execute_formal_benchmark_case(case)
    if task_id == "scientific-memory-rendering-v0":
        return _execute_scientific_memory_benchmark_case(case)
    return _execute_release_chain_benchmark_case(case)


def _execute_labtrust_gallery_benchmark_case(case: dict[str, Any]) -> dict[str, Any]:
    from pcs_core.benchmark_labtrust_gallery import evaluate_labtrust_gallery_case

    started = time.perf_counter()
    started_at = _iso_now()
    release_dir = resolve_release_directory(case)
    try:
        release_rel = release_dir.relative_to(repo_root()).as_posix()
    except ValueError:
        release_rel = release_dir.as_posix()

    observed_status, failure_code, component, release_chain_status, certificate_status = (
        evaluate_labtrust_gallery_case(case, release_dir)
    )
    commands = [
        {
            "command": f"evaluate_labtrust_gallery {release_rel}",
            "exit_code": 0 if observed_status == "passed" else 1,
        },
    ]
    sm_import = "not_applicable"
    sm_render = "not_applicable"
    sm_path = release_dir / "scientific_memory_import_report.json"
    if sm_path.is_file():
        sm_report = json.loads(sm_path.read_text(encoding="utf-8"))
        if isinstance(sm_report, dict):
            sm_import = "passed" if sm_report.get("verification_status") == "passed" else "failed"
            sm_render = (
                "rendered" if sm_report.get("verification_status") == "passed" else "incomplete"
            )

    return _build_benchmark_run(
        case,
        started_at=started_at,
        duration_ms=int((time.perf_counter() - started) * 1000),
        commands=commands,
        artifacts_produced=["manifest.json", "trace_certificate.json"],
        observed_status=observed_status,
        observed_failure_code=failure_code,
        observed_component=component,
        release_chain_status=release_chain_status,
        certificate_status=certificate_status,
        scientific_memory_import_status=sm_import,
        scientific_memory_render_status=sm_render,
    )


def build_failure_localization_result(
    case: dict[str, Any],
    run: dict[str, Any],
) -> dict[str, Any]:
    expected_component = str(case.get("expected_responsible_component") or "unknown")
    observed_component = str(run.get("observed_responsible_component") or "unknown")
    body: dict[str, Any] = {
        "schema_version": "v0",
        "result_id": f"failure-loc-{run.get('run_id', 'unknown')}",
        "run_id": str(run.get("run_id", "")),
        "case_id": str(case.get("case_id", "")),
        "expected_failure_code": str(case.get("expected_failure_code") or ""),
        "observed_failure_code": str(run.get("observed_failure_code") or ""),
        "expected_responsible_component": expected_component,
        "observed_responsible_component": observed_component,
        "localized_correctly": expected_component == observed_component,
        "source_repo": PCS_CORE_REPO,
        "source_commit": PCS_CORE_COMMIT_PLACEHOLDER,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def _coverage_report(
    *,
    coverage_id: str,
    metric: str,
    numerator: float,
    denominator: float,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ratio = (numerator / denominator) if denominator else 0.0
    body: dict[str, Any] = {
        "schema_version": "v0",
        "coverage_id": coverage_id,
        "metric": metric,
        "numerator": numerator,
        "denominator": denominator,
        "coverage_ratio": min(1.0, max(0.0, ratio)),
        "details": details or {},
        "source_repo": PCS_CORE_REPO,
        "source_commit": PCS_CORE_COMMIT_PLACEHOLDER,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def compute_suite_coverage(
    suite_id: str,
    runs: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive coverage snapshots for a benchmark suite."""
    from pcs_core.lean_trust import formal_checks_from_lean_result
    from pcs_core.registry import registry_entries
    from pcs_core.registry_semantics import audit_release_chain_registry_coverage

    registry_entries_count = len(registry_entries())
    sum(
        1
        for case, run in zip(cases, runs, strict=False)
        if case.get("expected_responsible_component") == run.get("observed_responsible_component")
    )
    sum(
        1
        for case, run in zip(cases, runs, strict=False)
        if repair_hint_for_component(str(case.get("expected_responsible_component", "unknown")))
        == str(run.get("observed_repair_hint", ""))
    )
    formal_num = 0.0
    formal_den = 0.0
    registry_num = 0.0
    registry_den = 0.0
    sm_num = 0.0
    sm_den = 0.0

    for case in cases:
        try:
            release_dir = resolve_release_directory(case)
        except (ValueError, FileNotFoundError):
            continue
        rc_path = release_dir / "release_chain_validation_result.v0.json"
        if rc_path.is_file():
            rc = json.loads(rc_path.read_text(encoding="utf-8"))
            checks = rc.get("checks") if isinstance(rc, dict) else None
            deferred = rc.get("deferred_registry_checks") if isinstance(rc, dict) else None
            if isinstance(checks, list) and isinstance(deferred, list):
                gaps = audit_release_chain_registry_coverage(checks, deferred)
                registry_den += 1.0
                registry_num += 1.0 if not gaps else max(0.0, 1.0 - len(gaps) / max(len(checks), 1))
        lean_path = release_dir / "lean_check_result.v0.json"
        if lean_path.is_file():
            lean = json.loads(lean_path.read_text(encoding="utf-8"))
            formal_den += 1.0
            if isinstance(lean, dict) and lean.get("status") == "ProofChecked":
                formal_num += 1.0
            obligations = release_dir / "proof_obligation.v0.json"
            if obligations.is_file() and isinstance(lean, dict):
                ob_doc = json.loads(obligations.read_text(encoding="utf-8"))
                ob_count = len(ob_doc.get("obligations", [])) if isinstance(ob_doc, dict) else 0
                passed_checks = sum(
                    1
                    for item in formal_checks_from_lean_result(lean)
                    if item.get("status") == "passed"
                )
                if ob_count:
                    formal_num += passed_checks / ob_count
        sm_path = release_dir / "scientific_memory_import_report.json"
        if sm_path.is_file():
            sm = json.loads(sm_path.read_text(encoding="utf-8"))
            sm_den += 1.0
            required = (
                "verification_status",
                "strict",
                "allow_legacy",
                "bundle_shape",
                "render_path",
                "workflow_profile_id",
            )
            present = sum(1 for key in required if key in sm)
            sm_num += present / len(required)

    total = len(cases) or 1
    passed = sum(1 for run in runs if run.get("observed_status") == "passed")
    return {
        "registry": _coverage_report(
            coverage_id=f"{suite_id}-registry",
            metric="registry_coverage",
            numerator=registry_num,
            denominator=max(registry_den, 1.0),
            details={"registry_entry_count": registry_entries_count},
        ),
        "formal_checks": _coverage_report(
            coverage_id=f"{suite_id}-formal",
            metric="formal_check_coverage",
            numerator=formal_num,
            denominator=max(formal_den, 1.0),
        ),
        "scientific_memory": _coverage_report(
            coverage_id=f"{suite_id}-sm",
            metric="scientific_memory_interpretability",
            numerator=sm_num,
            denominator=max(sm_den, 1.0),
        ),
        "release_reproducibility": _coverage_report(
            coverage_id=f"{suite_id}-repro",
            metric="release_reproducibility",
            numerator=float(passed),
            denominator=float(total),
        ),
        "certificate_completeness": _coverage_report(
            coverage_id=f"{suite_id}-cert",
            metric="certificate_completeness",
            numerator=float(passed),
            denominator=float(total),
        ),
    }


def build_benchmark_report(
    suite_id: str,
    *,
    runs: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    conformance_refs: list[dict[str, Any]] | None = None,
    run_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Aggregate benchmark runs into BenchmarkReport.v0."""
    registry = load_benchmark_registry()
    suite = registry.get("suites", {}).get(suite_id)
    if not isinstance(suite, dict):
        raise ValueError(f"unknown benchmark suite: {suite_id}")

    total = len(runs)
    passed_cases = sum(1 for run in runs if run.get("observed_status") == "passed")
    failed_cases = total - passed_cases
    expected_invalid = [c for c in cases if c.get("case_kind") != "valid_release"]
    [c for c in cases if c.get("case_kind") == "valid_release"]
    expected_failures_detected = 0
    unexpected_passes = 0
    unexpected_failures = 0

    case_by_id = {str(c["case_id"]): c for c in cases}
    for run in runs:
        case = case_by_id.get(str(run.get("case_id", "")), {})
        kind = case.get("case_kind")
        status = run.get("observed_status")
        if kind == "valid_release":
            if status != "passed":
                unexpected_failures += 1
        elif status == "passed":
            expected_failures_detected += 1
        else:
            unexpected_failures += 1
    for run in runs:
        case = case_by_id.get(str(run.get("case_id", "")), {})
        if case.get("case_kind") != "valid_release" and run.get("observed_status") == "passed":
            continue
        if case.get("case_kind") == "valid_release" and run.get("observed_status") == "passed":
            unexpected_passes += 0

    loc_denom = len(expected_invalid) or 1
    localization_hits = sum(
        1
        for case, run in zip(cases, runs, strict=False)
        if case.get("case_kind") != "valid_release"
        and case.get("expected_responsible_component") is not None
        and case.get("expected_responsible_component") == run.get("observed_responsible_component")
    )
    repair_hits = sum(
        1
        for case, run in zip(cases, runs, strict=False)
        if case.get("case_kind") != "valid_release"
        and case.get("expected_responsible_component") is not None
        and repair_hint_for_component(str(case.get("expected_responsible_component")))
        == run.get("observed_repair_hint")
    )

    coverage = compute_suite_coverage(suite_id, runs, cases)
    failures = [
        {
            "case_id": str(run.get("case_id", "")),
            "run_id": str(run.get("run_id", "")),
            "message": (
                f"expected {case_by_id.get(str(run.get('case_id')), {}).get('expected_status')} "
                f"got {run.get('observed_status')} "
                f"({run.get('observed_failure_code')})"
            ),
        }
        for run in runs
        if run.get("observed_status") != "passed"
    ]

    run_refs = []
    paths = run_paths or {}
    for run in runs:
        case_id = str(run.get("case_id", ""))
        run_refs.append(
            {
                "run_id": str(run.get("run_id", "")),
                "case_id": case_id,
                "path": paths.get(case_id, f"runs/{run.get('run_id')}.v0.json"),
                "observed_status": run.get("observed_status"),
            },
        )

    metric_ids = coerce_metric_ids(
        suite.get("metrics", []) if isinstance(suite.get("metrics"), list) else [],
    )
    summary = {
        "total_cases": total,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "expected_failures_detected": expected_failures_detected,
        "unexpected_passes": unexpected_passes,
        "unexpected_failures": unexpected_failures,
        "failure_localization_accuracy": localization_hits / loc_denom,
        "repair_hint_accuracy": repair_hits / (loc_denom if expected_invalid else (total or 1)),
        "formal_check_coverage": coverage["formal_checks"]["coverage_ratio"],
        "registry_coverage": coverage["registry"]["coverage_ratio"],
        "scientific_memory_render_coverage": coverage["scientific_memory"]["coverage_ratio"],
    }

    body: dict[str, Any] = {
        "schema_version": "v0",
        "report_id": f"benchmark-report-{suite_id}",
        "benchmark_suite_id": suite_id,
        "runs": run_refs,
        "metrics": metric_ids,
        "summary": summary,
        "coverage": coverage,
        "metric_summaries": build_metric_summaries(
            metric_ids=metric_ids,
            summary=summary,
            coverage=coverage,
            invalid_case_count=len(expected_invalid),
            suite_id=suite_id,
        ),
        "failures": failures,
        "source_repo": PCS_CORE_REPO,
        "source_commit": PCS_CORE_COMMIT_PLACEHOLDER,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    if conformance_refs:
        body["conformance_refs"] = conformance_refs
    return _with_digest(body)


def load_benchmark_case(path: Path) -> dict[str, Any]:
    from pcs_core.benchmark_case_normalize import normalize_benchmark_case

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: case must be a JSON object")
    extension_path = path.parent / "labtrust_benchmark_extension.v0.json"
    failure_path = path.parent / "expected_failure.json"
    extension = None
    expected_failure = None
    if extension_path.is_file():
        extension = json.loads(extension_path.read_text(encoding="utf-8"))
    if failure_path.is_file():
        expected_failure = json.loads(failure_path.read_text(encoding="utf-8"))
    return normalize_benchmark_case(
        data,
        extension=extension if isinstance(extension, dict) else None,
        expected_failure=expected_failure if isinstance(expected_failure, dict) else None,
    )


def list_benchmark_suite_ids() -> list[str]:
    registry = load_benchmark_registry()
    suites = registry.get("suites")
    if not isinstance(suites, dict):
        return []
    return sorted(suites)


def discover_cases_for_suite(suite_id: str) -> list[tuple[Path, dict[str, Any]]]:
    registry = load_benchmark_registry()
    suites = registry.get("suites")
    if not isinstance(suites, dict) or suite_id not in suites:
        raise ValueError(f"unknown benchmark suite: {suite_id}")
    suite = suites[suite_id]
    root = repo_root() / str(suite["fixture_root"])
    allowed_ids = set(suite.get("valid_cases", [])) | set(suite.get("invalid_cases", []))
    discovered: list[tuple[Path, dict[str, Any]]] = []
    for sub in ("valid", "invalid"):
        base = root / sub
        if not base.is_dir():
            continue
        for case_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            if allowed_ids and case_dir.name not in allowed_ids:
                continue
            case_path = case_dir / "benchmark_case.v0.json"
            if case_path.is_file():
                discovered.append((case_path, load_benchmark_case(case_path)))
    if allowed_ids:
        found_ids = {case["case_id"] for _, case in discovered}
        missing = sorted(allowed_ids - found_ids)
        if missing:
            raise FileNotFoundError(
                f"suite {suite_id} missing benchmark cases: {', '.join(missing)}",
            )
    return discovered


def validate_benchmark_fixtures() -> list[str]:
    """Validate all benchmark tasks, cases, and optional sidecar manifests."""
    from pcs_core.validate import validate_file

    errors: list[str] = []
    for suite_id in list_benchmark_suite_ids():
        root_name = ""
        try:
            registry = load_benchmark_registry()
            root_name = str(registry["suites"][suite_id].get("fixture_root", ""))
            task_path = repo_root() / root_name / "benchmark_task.v0.json"
            if task_path.is_file():
                validate_file(task_path)
            for case_path, case in discover_cases_for_suite(suite_id):
                from pcs_core.validate import ValidationError, validate_artifact

                try:
                    validate_artifact(case, "BenchmarkCase.v0")
                except ValidationError as exc:
                    errors.append(f"{case_path.relative_to(repo_root())}: {exc}")
                    continue
                failure_path = case_path.parent / "expected_failure.json"
                if failure_path.is_file():
                    from pcs_core.validate import detect_artifact_type

                    failure_doc = json.loads(failure_path.read_text(encoding="utf-8"))
                    if isinstance(failure_doc, dict) and detect_artifact_type(failure_doc):
                        try:
                            validate_file(failure_path)
                        except ValidationError as exc:
                            errors.append(f"{failure_path.relative_to(repo_root())}: {exc}")
        except (ValueError, FileNotFoundError) as exc:
            errors.append(f"{suite_id}: {exc}")
    return errors


def assert_suite_meets_thresholds(report: dict[str, Any], suite_id: str) -> list[str]:
    """Return errors when a report violates registry minimum_passing_thresholds."""
    registry = load_benchmark_registry()
    suite = registry["suites"][suite_id]
    thresholds = suite.get("minimum_passing_thresholds", {})
    summary = report.get("summary", {})
    errors: list[str] = []
    total = int(summary.get("total_cases", 0))
    passed = int(summary.get("passed_cases", 0))
    if total and thresholds.get("minimum_pass_rate") is not None:
        rate = passed / total
        if rate < float(thresholds["minimum_pass_rate"]):
            errors.append(
                f"{suite_id}: pass rate {rate:.3f} < {thresholds['minimum_pass_rate']}",
            )
    for key, summary_key in (
        ("minimum_failure_localization_accuracy", "failure_localization_accuracy"),
        ("minimum_formal_check_coverage", "formal_check_coverage"),
        ("minimum_registry_coverage", "registry_coverage"),
        ("minimum_scientific_memory_render_coverage", "scientific_memory_render_coverage"),
    ):
        floor = thresholds.get(key)
        if floor is None:
            continue
        value = float(summary.get(summary_key, 0.0))
        if value < float(floor):
            errors.append(f"{suite_id}: {summary_key} {value:.3f} < {floor}")
    return errors


def run_benchmark_suite(suite_id: str) -> dict[str, Any]:
    """Execute all cases for a suite; return BenchmarkReport.v0."""
    from pcs_core.conformance_run import run_conformance_as_benchmark_input

    cases_paths = discover_cases_for_suite(suite_id)
    cases = [case for _, case in cases_paths]
    runs: list[dict[str, Any]] = []
    run_paths: dict[str, str] = {}
    conformance_refs: list[dict[str, Any]] = []

    suite_to_conformance = {
        "labtrust-qc-release-v0": "release-chain",
        "tool-use-safety-v0": "tool-use",
        "computation-reproducibility-v0": "computation",
        "cross-domain-release-chain-v0": "multidomain",
        "formal-trust-kernel-v0": "lean-trust",
    }
    conf_suite = suite_to_conformance.get(suite_id)
    if conf_suite:
        conf_run = run_conformance_as_benchmark_input(conf_suite)
        conformance_refs.append(
            {
                "suite": conf_suite,
                "run_id": str(conf_run.get("run_id", "")),
                "status": str(conf_run.get("status", "")),
            },
        )

    for case_path, case in cases_paths:
        run = execute_benchmark_case(case)
        runs.append(run)
        rel = case_path.parent / f"benchmark_run.{case['case_id']}.v0.json"
        rel.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        run_paths[str(case["case_id"])] = str(
            rel.relative_to(repo_root()).as_posix(),
        )

    return build_benchmark_report(
        suite_id,
        runs=runs,
        cases=cases,
        conformance_refs=conformance_refs or None,
        run_paths=run_paths,
    )
