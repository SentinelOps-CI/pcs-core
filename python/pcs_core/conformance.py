"""LabTrust fixture paths and PCS protocol conformance suite runner."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from pcs_core.paths import examples_dir, repo_root
from pcs_core.release_chain import validate_release_chain
from pcs_core.release_chain_checks import RELEASE_CHAIN_CHECK_COUNT
from pcs_core.release_fixtures import release_dir
from pcs_core.shared_hash_vectors import VECTOR_SPECS, shared_vectors_dir, verify_shared_vectors
from pcs_core.validate import ValidationError, validate_artifact, validate_file

LABTRUST_VALID_FIXTURES: tuple[str, ...] = (
    "science_claim_bundle.pending.valid.json",
    "trace_certificate.valid.json",
    "science_claim_bundle.certified.valid.json",
    "verification_result.valid.json",
    "signed_science_claim_bundle.valid.json",
)

LABTRUST_INVALID_FIXTURES: tuple[str, ...] = (
    "invalid_signed_schema_version_artifact_name.json",
    "invalid_singular_runtime_receipt_bundle.json",
    "invalid_failed_verification_result.json",
    "invalid_missing_trace_certificate.json",
)

SuiteFn = Callable[[], tuple[list[str], list[str], int]]


def labtrust_examples_dir() -> Path:
    return examples_dir() / "labtrust"


def labtrust_fixture_path(name: str) -> Path:
    path = labtrust_examples_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"LabTrust conformance fixture not found: {path}")
    return path


SUITES: dict[str, SuiteFn] = {}

_conformance_release_grade = False


def conformance_release_grade() -> bool:
    return _conformance_release_grade


def set_conformance_release_grade(value: bool) -> None:
    global _conformance_release_grade
    _conformance_release_grade = value


def _record(name: str) -> Callable[[SuiteFn], SuiteFn]:
    def decorator(fn: SuiteFn) -> SuiteFn:
        SUITES[name] = fn
        return fn

    return decorator


def _validate_release_chain_result_artifact(path: Path) -> tuple[list[str], int]:
    """Validate on-disk ReleaseChainValidationResult and registry coverage."""
    from pcs_core.registry_semantics import audit_release_chain_registry_coverage
    from pcs_core.release_fixtures import file_digest

    errors: list[str] = []
    checks_run = 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON: {exc}"], checks_run
    try:
        validate_artifact(data, "ReleaseChainValidationResult.v0")
    except ValidationError as exc:
        errors.append(str(exc))
        errors.extend(exc.errors)
    checks = data.get("checks")
    if not isinstance(checks, list):
        errors.append(f"{path.name}: checks must be an array")
    elif len(checks) != RELEASE_CHAIN_CHECK_COUNT:
        errors.append(
            f"{path.name}: expected {RELEASE_CHAIN_CHECK_COUNT} checks, got {len(checks)}",
        )
    deferred = data.get("deferred_registry_checks")
    if not isinstance(deferred, list):
        errors.append(f"{path.name}: deferred_registry_checks required")
        deferred = []
    if isinstance(checks, list):
        checks_run += len(checks) + len(deferred)
        errors.extend(audit_release_chain_registry_coverage(checks, deferred))
    manifest_path = release_dir() / "release_manifest.v0.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            ref = manifest.get("release_chain_validation_result")
            if isinstance(ref, dict):
                expected = ref.get("sha256")
                if isinstance(expected, str) and file_digest(path.read_bytes()) != expected:
                    errors.append(
                        f"{path.name}: digest does not match release_manifest."
                        "release_chain_validation_result.sha256",
                    )
                checks_run += 1
        except json.JSONDecodeError:
            errors.append("release_manifest.v0.json: invalid JSON")
    return errors, checks_run


@_record("release-manifest")
def _suite_release_manifest() -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    path = release_dir() / "release_manifest.v0.json"
    try:
        validate_file(path)
    except ValidationError as exc:
        errors.append(str(exc))
        errors.extend(exc.errors)
    return errors, [], 1


@_record("handoff-manifest")
def _suite_handoff_manifest() -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    paths = sorted(release_dir().glob("handoff_manifest.*.v0.json"))
    checks_run = 0
    for path in paths:
        checks_run += 1
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{path.name}: {exc}")
            errors.extend(f"{path.name}: {err}" for err in exc.errors)
    example = examples_dir() / "handoff_manifest.valid.json"
    checks_run += 1
    try:
        validate_file(example)
    except ValidationError as exc:
        errors.append(f"{example.name}: {exc}")
    if not paths:
        errors.append("no handoff_manifest.*.v0.json files under labtrust-release/")
    return errors, [], max(checks_run, 1)


@_record("artifact-registry")
def _suite_artifact_registry() -> tuple[list[str], list[str], int]:
    from pcs_core.registry import validate_registry_file
    from pcs_core.registry_semantics import audit_registry_enforcement
    from pcs_core.semantic_check_execution import build_semantic_check_execution

    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(audit_registry_enforcement())
    registry_errors, registry_warnings = validate_registry_file(
        examples_dir() / "artifact_registry.valid.json",
    )
    errors.extend(registry_errors)
    warnings.extend(registry_warnings)
    policy_path = examples_dir() / "semantic_check_execution.valid.json"
    checks_run = 3
    try:
        validate_file(policy_path)
    except ValidationError as exc:
        errors.append(f"semantic_check_execution.valid.json: {exc}")
        errors.extend(exc.errors)
    built = build_semantic_check_execution()
    on_disk = json.loads(policy_path.read_text(encoding="utf-8"))
    if built != on_disk:
        errors.append(
            "semantic_check_execution.valid.json drift "
            "(run materialize_labtrust_protocol_artifacts.py)",
        )
    return errors, warnings, checks_run


@_record("semantic-check-execution")
def _suite_semantic_check_execution() -> tuple[list[str], list[str], int]:
    from pcs_core.semantic_check_execution import build_semantic_check_execution

    errors: list[str] = []
    path = examples_dir() / "semantic_check_execution.valid.json"
    try:
        validate_file(path)
    except ValidationError as exc:
        errors.append(str(exc))
        errors.extend(exc.errors)
    built = build_semantic_check_execution()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    if built != on_disk:
        errors.append("semantic_check_execution.valid.json drift from registry catalog")
    return errors, [], len(built.get("checks", [])) or 1


@_record("release-chain-validation")
def _suite_release_chain_validation() -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    issues = validate_release_chain(release_dir())
    checks_run = len(issues) or 1
    if issues:
        errors.extend(f"{issue.code}: {issue.message}" for issue in issues)
    result_path = release_dir() / "release_chain_validation_result.v0.json"
    result_errors, result_checks = _validate_release_chain_result_artifact(result_path)
    errors.extend(result_errors)
    checks_run += result_checks
    return errors, [], checks_run


@_record("release-chain")
def _suite_release_chain() -> tuple[list[str], list[str], int]:
    return _suite_release_chain_validation()


@_record("hash")
def _suite_hash() -> tuple[list[str], list[str], int]:
    errors = verify_shared_vectors()
    expected = len(VECTOR_SPECS)
    on_disk = len(list(shared_vectors_dir().glob("*.vector.json")))
    if on_disk != expected:
        errors.append(
            f"test_vectors/hash: expected {expected} vector files, found {on_disk}",
        )
    return errors, [], expected


@_record("migration")
def _suite_migration() -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    path = examples_dir() / "migration_report.valid.json"
    try:
        validate_file(path)
    except ValidationError as exc:
        errors.append(str(exc))
    return errors, [], 1


@_record("component-release-fragment")
def _suite_component_release_fragment() -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    paths = (
        examples_dir() / "component_release_fragment.valid.json",
        release_dir() / "labtrust_release_fragment.json",
    )
    checks_run = 0
    for path in paths:
        if not path.is_file():
            errors.append(f"missing {path}")
            continue
        checks_run += 1
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{path.name}: {exc}")
            errors.extend(f"{path.name}: {err}" for err in exc.errors)
    return errors, [], max(checks_run, 1)


@_record("workflow-profile")
def _suite_workflow_profile() -> tuple[list[str], list[str], int]:
    from pcs_core.workflow_profiles import audit_workflow_profile_files

    errors: list[str] = []
    errors.extend(audit_workflow_profile_files())
    profiles = examples_dir() / "workflow_profiles"
    checks_run = 0
    for path in sorted(profiles.glob("*.json")):
        checks_run += 1
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{path.name}: {exc}")
            errors.extend(f"{path.name}: {err}" for err in exc.errors)
    release_profile = examples_dir() / "tool-use-release" / "workflow_profile.v0.json"
    if release_profile.is_file():
        checks_run += 1
        try:
            validate_file(release_profile)
        except ValidationError as exc:
            errors.append(f"{release_profile.name}: {exc}")
    return errors, [], max(checks_run, 1)


@_record("tool-use")
def _suite_tool_use() -> tuple[list[str], list[str], int]:
    from pcs_core.tool_use_validate import (
        validate_tool_use_invalid_case,
        validate_tool_use_release_directory,
    )

    errors: list[str] = []
    release = examples_dir() / "tool-use-release"
    errors.extend(validate_tool_use_release_directory(release))
    checks_run = 8
    invalid_root = examples_dir() / "tool-use-release-invalid"
    if invalid_root.is_dir():
        for case_dir in sorted(p for p in invalid_root.iterdir() if p.is_dir()):
            checks_run += 1
            case_errors = validate_tool_use_invalid_case(case_dir)
            errors.extend(case_errors)
    return errors, [], checks_run


@_record("computation")
def _suite_computation() -> tuple[list[str], list[str], int]:
    from pcs_core.computation_validate import (
        validate_computation_invalid_case,
        validate_computation_release_directory,
    )

    errors: list[str] = []
    release = examples_dir() / "computation-release"
    errors.extend(validate_computation_release_directory(release))
    checks_run = 10
    invalid_root = examples_dir() / "computation-release-invalid"
    if invalid_root.is_dir():
        for case_dir in sorted(p for p in invalid_root.iterdir() if p.is_dir()):
            checks_run += 1
            case_errors = validate_computation_invalid_case(case_dir)
            errors.extend(case_errors)
    return errors, [], checks_run


@_record("benchmark-ingest")
def _suite_benchmark_ingest() -> tuple[list[str], list[str], int]:
    from pcs_core.benchmark_compat import validate_compatibility_corpus
    from pcs_core.benchmark_ingest import run_benchmark_ingest_contract_checks

    errors = validate_compatibility_corpus()
    errors.extend(run_benchmark_ingest_contract_checks(check_release_grade=True))
    warnings: list[str] = []
    checks = 24
    ingest_root = examples_dir() / "benchmark_ingest"
    for name in (
        "labtrust.pcs_bench_ingest.valid.json",
        "certifyedge.pcs_bench_ingest.valid.json",
        "provability_fabric.pcs_bench_ingest.valid.json",
        "scientific_memory.pcs_bench_ingest.valid.json",
    ):
        path = ingest_root / name
        checks += 1
        if not path.is_file():
            errors.append(f"missing {path.relative_to(repo_root()).as_posix()}")
    return errors, warnings, checks


@_record("benchmark-report")
def _suite_benchmark_report() -> tuple[list[str], list[str], int]:
    from pcs_core.benchmark_compat import validate_compatibility_corpus

    errors = validate_compatibility_corpus()
    checks = 12
    examples_root = examples_dir() / "benchmarks"
    for name in (
        "benchmark_case.valid.json",
        "benchmark_run.valid.json",
        "benchmark_report.valid.json",
        "failure_localization_result.valid.json",
        "coverage_report.valid.json",
        "explain_quality_report.valid.json",
        "profile_coverage_report.valid.json",
        "metric_summary.valid.json",
    ):
        path = examples_root / name
        if path.is_file():
            checks += 1
            try:
                validate_file(path)
            except ValidationError as exc:
                errors.append(f"{name}: {exc}")
    compat = examples_root / "compatibility"
    if compat.is_dir():
        for path in sorted(compat.glob("*.normalized.json")) + sorted(
            compat.glob("*.pcs_bench_ingest.normalized.json"),
        ):
            checks += 1
            try:
                validate_file(path)
                if path.name.endswith(".pcs_bench_ingest.normalized.json"):
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    refs = doc.get("artifact_refs")
                    if not isinstance(refs, list) or not refs:
                        errors.append(f"{path.name}: producer ingest must include artifact_refs")
            except ValidationError as exc:
                errors.append(f"{path.name}: {exc}")
    producer_root = examples_dir() / "benchmark"
    if producer_root.is_dir():
        for path in sorted(producer_root.glob("*.valid.json")):
            checks += 1
            try:
                validate_file(path)
            except ValidationError as exc:
                errors.append(f"benchmark/{path.name}: {exc}")
    ingest_root = examples_dir() / "benchmark_ingest"
    if ingest_root.is_dir():
        for path in sorted(ingest_root.glob("*.pcs_bench_ingest.valid.json")):
            checks += 1
            try:
                validate_file(path)
            except ValidationError as exc:
                errors.append(f"benchmark_ingest/{path.name}: {exc}")
    metric_registry = examples_dir() / "benchmark_metric_registry.valid.json"
    if metric_registry.is_file():
        checks += 1
        try:
            validate_file(metric_registry)
        except ValidationError as exc:
            errors.append(f"benchmark_metric_registry.valid.json: {exc}")
    manifest = repo_root() / "benchmarks" / "labtrust-qc-release" / "benchmark_manifest.v0.json"
    if manifest.is_file():
        checks += 1
        try:
            validate_file(manifest)
        except ValidationError as exc:
            errors.append(f"benchmark_manifest.v0.json: {exc}")
    return errors, [], checks


@_record("benchmark")
def _suite_benchmark() -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    checks = 0
    registry_path = examples_dir() / "benchmark_registry.valid.json"
    if not registry_path.is_file():
        errors.append("missing examples/benchmark_registry.valid.json")
    else:
        try:
            validate_file(registry_path)
            checks += 1
        except ValidationError as exc:
            errors.append(f"benchmark_registry.valid.json: {exc}")
    from pcs_core.benchmark_runner import (
        list_benchmark_suite_ids,
        run_benchmark_suite,
        validate_benchmark_fixtures,
    )

    errors.extend(validate_benchmark_fixtures())
    checks += len(list_benchmark_suite_ids())
    for suite_id in list_benchmark_suite_ids():
        checks += 1
        try:
            report = run_benchmark_suite(suite_id)
            from pcs_core.validate import validate_artifact

            validate_artifact(report, "BenchmarkReport.v0")
            summary = report.get("summary", {})
            if summary.get("passed_cases") != summary.get("total_cases"):
                errors.append(
                    f"{suite_id}: {summary.get('passed_cases')}/"
                    f"{summary.get('total_cases')} cases passed",
                )
                for failure in report.get("failures", []):
                    if isinstance(failure, dict):
                        errors.append(
                            f"{suite_id}/{failure.get('case_id')}: {failure.get('message')}",
                        )
        except (ValidationError, ValueError, FileNotFoundError) as exc:
            errors.append(f"{suite_id}: {exc}")
    return errors, [], checks


@_record("lean-trust")
def _suite_lean_trust() -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    checks = 0
    for name in ("proof_obligation.valid.json", "lean_check_result.valid.json"):
        path = examples_dir() / name
        if not path.is_file():
            errors.append(f"missing examples/{name}")
            continue
        try:
            validate_file(path)
            checks += 1
        except ValidationError as exc:
            errors.append(f"{name}: {exc}")
    for release_name in ("labtrust-release", "tool-use-release", "computation-release"):
        release_dir = examples_dir() / release_name
        if not release_dir.is_dir():
            continue
        for artifact in ("proof_obligation.v0.json", "lean_check_result.v0.json"):
            path = release_dir / artifact
            if not path.is_file():
                errors.append(f"{release_name}/{artifact} missing (run materialize-protocol.ps1)")
                continue
            try:
                validate_file(path)
                checks += 1
            except ValidationError as exc:
                errors.append(f"{release_name}/{artifact}: {exc}")
        lean_result_path = release_dir / "lean_check_result.v0.json"
        if lean_result_path.is_file():
            lean_result = json.loads(lean_result_path.read_text(encoding="utf-8"))
            if lean_result.get("status") != "ProofChecked":
                errors.append(
                    f"{release_name}/lean_check_result.v0.json: status must be ProofChecked",
                )
    lean_dir = repo_root() / "lean"
    if not (lean_dir / "lakefile.lean").is_file():
        errors.append("lean/lakefile.lean missing")
    else:
        checks += 1
    return errors, [], checks


@_record("multidomain")
def _suite_multidomain() -> tuple[list[str], list[str], int]:
    profile_errors, _, profile_checks = _suite_workflow_profile()
    tool_errors, _, tool_checks = _suite_tool_use()
    computation_errors, _, computation_checks = _suite_computation()
    chain_errors, _, chain_checks = _suite_release_chain_validation()
    tool_use_release = examples_dir() / "tool-use-release"
    if tool_use_release.is_dir():
        tool_chain_issues = validate_release_chain(tool_use_release)
        chain_checks += len(tool_chain_issues) or 1
        if tool_chain_issues:
            chain_errors.extend(
                f"[tool-use-release] {issue.code}: {issue.message}" for issue in tool_chain_issues
            )
    computation_release = examples_dir() / "computation-release"
    if computation_release.is_dir():
        computation_chain_issues = validate_release_chain(computation_release)
        chain_checks += len(computation_chain_issues) or 1
        if computation_chain_issues:
            chain_errors.extend(
                f"[computation-release] {issue.code}: {issue.message}"
                for issue in computation_chain_issues
            )
    errors = [*profile_errors, *tool_errors, *computation_errors, *chain_errors]
    return errors, [], profile_checks + tool_checks + computation_checks + chain_checks


@_record("status-transition")
def _suite_status_transition() -> tuple[list[str], list[str], int]:
    from pcs_core.status_policy import check_status_transition

    errors: list[str] = []
    cases = (
        ("Rejected", "ProofChecked"),
        ("Stale", "ProofChecked"),
        ("RuntimeObserved", "ProofChecked"),
    )
    for old_status, new_status in cases:
        verdict = check_status_transition(old_status, new_status)
        if verdict.allowed:
            errors.append(f"forbidden transition allowed: {old_status} -> {new_status}")
    return errors, [], len(cases)


@_record("pf-core")
def _suite_pf_core() -> tuple[list[str], list[str], int]:
    from pcs_core.lean_check import audit_pfcore_lean_no_sorry, check_pfcore_trace_lean_semantics
    from pcs_core.pf_core_contract import load_contracts_from_dir, validate_trace_contracts
    from pcs_core.validate import (
        check_pf_core_invalid_fixtures,
        check_pf_core_valid_fixtures,
        iter_pf_core_example_dirs,
        load_pf_core_fixture_manifest,
        validate_file,
    )

    errors: list[str] = []
    checks = 0
    try:
        check_pf_core_valid_fixtures()
        checks += 1
    except ValidationError as exc:
        errors.append(f"pf-core valid fixtures: {exc}")
    try:
        check_pf_core_invalid_fixtures()
        checks += 1
    except ValidationError as exc:
        errors.append(f"pf-core invalid fixtures: {exc}")
    for case_dir in iter_pf_core_example_dirs("valid"):
        manifest = load_pf_core_fixture_manifest(case_dir)
        trace_name = str(manifest.get("trace_file") or "trace.json")
        trace_path = case_dir / trace_name
        if not trace_path.is_file():
            errors.append(f"{case_dir.name}: missing trace file {trace_name}")
            continue
        checks += 1
        try:
            validate_file(trace_path)
            data = json.loads(trace_path.read_text(encoding="utf-8"))
            for issue in check_pfcore_trace_lean_semantics(data):
                errors.append(f"{trace_path.name}: {issue.code}: {issue.message}")
            contracts_dir = case_dir / "contracts"
            contracts = (
                load_contracts_from_dir(contracts_dir)
                if contracts_dir.is_dir()
                else load_contracts_from_dir(case_dir)
            )
            if contracts:
                for issue in validate_trace_contracts(data, contracts):
                    errors.append(f"{trace_path.name}: {issue.code}: {issue.message}")
        except ValidationError as exc:
            errors.append(f"{trace_path}: {exc}")
    checks += 1
    errors.extend(audit_pfcore_lean_no_sorry())
    checks = _check_pf_core_generated_lean_proof(errors, checks)
    return errors, [], checks


def _check_pf_core_generated_lean_proof(errors: list[str], checks: int) -> int:
    import platform
    import shutil
    import tempfile

    from pcs_core.lean_check import run_pfcore_lean_check
    from pcs_core.pf_core_proof_binding import verify_proof_binding

    trace_path = repo_root() / "examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json"
    if not trace_path.is_file():
        errors.append("pf-core.generated-lean-proof: missing canonical trace fixture")
        return checks + 1

    lake_available = shutil.which("lake") is not None
    wsl_available = platform.system() == "Windows" and shutil.which("wsl") is not None
    if not lake_available and not wsl_available:
        if conformance_release_grade():
            errors.append(
                "pf-core.generated-lean-proof: release-grade requires lake or WSL "
                "for Lean proof check"
            )
            return checks + 1
        return checks

    checks += 1
    with tempfile.TemporaryDirectory(prefix="pfcore-lean-cert-") as tmp_dir:
        cert_path = Path(tmp_dir) / "pfcore-lean-cert.json"
        code, result = run_pfcore_lean_check(
            trace_path,
            out_path=cert_path,
            skip_build=False,
            skip_lean_proof=False,
        )
        certificate = result.get("certificate")
        if code != 0:
            errors.append(
                "pf-core.generated-lean-proof: lean-check failed "
                f"({[issue.get('code') for issue in result.get('issues', [])]})"
            )
            return checks
        if (
            not isinstance(certificate, dict)
            or certificate.get("claim_class") != "LeanKernelChecked"
        ):
            errors.append("pf-core.generated-lean-proof: expected claim_class LeanKernelChecked")
            return checks
        try:
            validate_artifact(certificate, "PFCoreCertificate.v0")
        except ValidationError as exc:
            errors.append(f"pf-core.generated-lean-proof: certificate validation failed: {exc}")
            return checks
        if conformance_release_grade():
            binding = verify_proof_binding(cert_path, trace_path=trace_path)
            if not binding.ok:
                for issue in binding.issues:
                    errors.append(f"pf-core.verify-proof-binding: {issue.code}: {issue.message}")
    return checks


@_record("pf-core-cross-language")
def _suite_pf_core_cross_language() -> tuple[list[str], list[str], int]:
    import subprocess

    from pcs_core.pf_core_contract import validate_trace_contracts
    from pcs_core.pf_core_runtime import (
        validate_denied_events_preserved,
        validate_pfcore_trace_hash_chain,
    )

    errors: list[str] = []
    checks = 0
    vector_root = repo_root() / "python" / "tests" / "hash_vectors" / "pf_core"
    cases: tuple[tuple[str, str], ...] = (
        ("invalid/trace_hash_chain_break.json", "EventHashMismatch"),
        ("invalid/claim_class_overclaim_trace.json", "ClaimClassOverclaim"),
        ("invalid/trace_hash_mismatch.json", "TraceHashMismatch"),
        ("invalid/previous_event_hash_mismatch.json", "EventHashMismatch"),
    )
    for relative, needle in cases:
        checks += 1
        trace = json.loads((vector_root / relative).read_text(encoding="utf-8"))
        py_errors = validate_pfcore_trace_hash_chain(trace)
        if not any(needle in err for err in py_errors):
            errors.append(f"python vector {relative}: expected {needle!r}, got {py_errors!r}")

    contract_dir = vector_root / "invalid" / "contract_capability_missing"
    if contract_dir.is_dir():
        checks += 1
        trace = json.loads((contract_dir / "trace.json").read_text(encoding="utf-8"))
        contract = json.loads((contract_dir / "contract.json").read_text(encoding="utf-8"))
        issues = validate_trace_contracts(trace, {contract["contract_id"]: contract})
        if not any(issue.code == "ContractCapabilityRequired" for issue in issues):
            errors.append("python contract_capability_missing vector failed")

    denied_dir = vector_root / "invalid" / "denied_event_dropped"
    if denied_dir.is_dir():
        checks += 1
        tool_use = json.loads((denied_dir / "tool_use_trace.json").read_text(encoding="utf-8"))
        pfcore = json.loads((denied_dir / "pfcore_trace.json").read_text(encoding="utf-8"))
        try:
            validate_denied_events_preserved(tool_use, pfcore)
            errors.append("python denied_event_dropped vector should fail")
        except Exception:
            pass

    cross_tenant_path = vector_root / "invalid" / "cross_tenant_leak.json"
    if cross_tenant_path.is_file():
        checks += 1
        from pcs_core.pf_core_runtime import validate_tenant_isolation

        trace = json.loads(cross_tenant_path.read_text(encoding="utf-8"))
        tenant_errors = validate_tenant_isolation(trace)
        if not any("TenantIsolation" in err for err in tenant_errors):
            errors.append("python cross_tenant_leak vector failed")

    rust = repo_root() / "rust"
    proc = subprocess.run(
        ["cargo", "test", "pf_core_", "--", "--nocapture"],
        cwd=rust,
        capture_output=True,
        text=True,
    )
    checks += 1
    if proc.returncode != 0:
        errors.append(f"rust pf_core tests failed: {proc.stderr or proc.stdout}")

    ts_root = repo_root() / "typescript"
    if (ts_root / "package.json").is_file():
        install = subprocess.run(
            ["npm", "install", "--silent"],
            cwd=ts_root,
            capture_output=True,
            text=True,
        )
        checks += 1
        if install.returncode != 0:
            errors.append(f"typescript npm install failed: {install.stderr or install.stdout}")
        proc = subprocess.run(
            ["npm", "test", "--silent"],
            cwd=ts_root,
            capture_output=True,
            text=True,
        )
        checks += 1
        if proc.returncode != 0:
            errors.append(f"typescript pf_core tests failed: {proc.stderr or proc.stdout}")

    return errors, [], checks


def list_suites() -> list[str]:
    return sorted(SUITES.keys())


def run_conformance(suite: str, *, release_grade: bool = False) -> tuple[int, list[str]]:
    """Run one suite or `all`. Returns (exit_code, human-readable error lines)."""
    global _conformance_release_grade
    _conformance_release_grade = release_grade
    report = build_conformance_report_data(suite)
    lines: list[str] = []
    if report["status"] == "failed":
        for failure in report.get("failures", []):
            suite_name = failure.get("suite", suite)
            lines.append(f"[{suite_name}] {failure.get('message', '')}")
        if not lines:
            for result in report.get("results", []):
                if result.get("status") == "failed":
                    lines.append(f"[{result['suite']}]")
                    lines.extend(str(err) for err in result.get("errors", []))
    return (0 if report["status"] == "passed" else 1, lines)


def build_conformance_report_data(suite: str) -> dict:
    from pcs_core.conformance_report import build_conformance_report, suite_result

    names = list_suites() if suite == "all" else [suite]
    if suite != "all" and suite not in SUITES:
        report = build_conformance_report(
            suite=suite,
            suite_results=[
                suite_result(
                    suite,
                    [f"unknown suite: {suite}", f"available: {', '.join(list_suites())}"],
                    checks_run=1,
                ),
            ],
        )
        validate_artifact(report, "ConformanceReport.v0")
        return report

    results: list[dict] = []
    for name in names:
        errors, warnings, checks_run = SUITES[name]()
        results.append(suite_result(name, errors, warnings, checks_run=checks_run))
    report = build_conformance_report(suite=suite, suite_results=results)
    validate_artifact(report, "ConformanceReport.v0")
    return report


def conformance_repo_root() -> Path:
    """Repository root for downstream repos vendoring pcs-core."""
    return repo_root()
