"""PCS command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pcs_core.hash import canonical_hash
from pcs_core.hash_vectors import verify_vectors, write_vectors
from pcs_core.migrate import migrate_file
from pcs_core.paths import examples_dir, resolve_release_chain_directory
from pcs_core.registry import (
    check_artifact_against_registry,
    explain_artifact_type,
    list_artifact_types,
    validate_registry_file,
)
from pcs_core.registry_semantics import (
    enforcement_layer,
    iter_registry_checks,
)
from pcs_core.release_chain_report import (
    build_release_chain_report,
    build_release_chain_validation_result,
    write_release_chain_validation_result,
)
from pcs_core.release_fixtures import release_dir, validate_release_manifest
from pcs_core.conformance import build_conformance_report_data, list_suites, run_conformance
from pcs_core.shared_hash_vectors import verify_shared_vectors, write_shared_vectors
from pcs_core.status_policy import check_status_transition, explain_status
from pcs_core.validate import (
    ValidationError,
    check_all_schemas,
    check_invalid_examples,
    check_valid_examples,
    detect_artifact_type,
    validate_artifact,
    validate_file,
)


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: root must be a JSON object")
    return data


def cmd_validate(path: Path) -> int:
    try:
        artifact_type = validate_file(path)
        print(f"OK {artifact_type} {path}")
        return 0
    except ValidationError as exc:
        print(f"FAIL {path}: {exc}", file=sys.stderr)
        for err in exc.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1


def cmd_hash(path: Path) -> int:
    data = _load_json(path)
    print(canonical_hash(data))
    return 0


def _collect_statuses(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if "status" in data and isinstance(data["status"], str) and "check_id" not in data:
        key = f"{prefix}status" if prefix else "status"
        found.append((key, data["status"]))
    for key, value in data.items():
        if key == "status":
            continue
        child_prefix = f"{prefix}{key}." if prefix else f"{key}."
        if isinstance(value, dict):
            found.extend(_collect_statuses(value, child_prefix))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    found.extend(_collect_statuses(item, f"{child_prefix}{i}."))
    return found


def cmd_status_fields(path: Path) -> int:
    data = _load_json(path)
    artifact_type = detect_artifact_type(data) or "unknown"
    statuses = _collect_statuses(data)
    print(f"artifact_type: {artifact_type}")
    for key, value in statuses:
        print(f"{key}: {value}")
    return 0


def cmd_explain_status(status: str) -> int:
    print(explain_status(status))
    return 0


def cmd_check_status_transition(old_path: Path, new_path: Path) -> int:
    old_status = _load_json(old_path).get("status")
    new_status = _load_json(new_path).get("status")
    if not isinstance(old_status, str) or not isinstance(new_status, str):
        print("FAIL both artifacts must include top-level status", file=sys.stderr)
        return 1
    verdict = check_status_transition(old_status, new_status)
    if verdict.allowed:
        print(f"OK {verdict.message}")
        return 0
    print(f"FAIL {verdict.message}", file=sys.stderr)
    return 1


def cmd_migrate(path: Path, from_version: str, to_version: str) -> int:
    report = migrate_file(path, from_version=from_version, to_version=to_version)
    print(json.dumps(report, indent=2))
    return 0


def cmd_registry_list() -> int:
    for name in list_artifact_types():
        print(name)
    return 0


def cmd_registry_explain(artifact_type: str) -> int:
    entry = explain_artifact_type(artifact_type)
    print(json.dumps(entry, indent=2))
    return 0


def cmd_registry_validate(path: Path) -> int:
    errors, warnings = validate_registry_file(path)
    for warn in warnings:
        print(f"WARN {warn}", file=sys.stderr)
    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print(f"OK artifact registry {path}")
    return 0


def cmd_registry_check_artifact(path: Path) -> int:
    drift = check_artifact_against_registry(path)
    if drift:
        for err in drift:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print(f"OK registry check {path}")
    return 0


def cmd_registry_audit() -> int:
    from pcs_core.registry_semantics import audit_registry_enforcement

    errors = audit_registry_enforcement()
    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("OK registry semantic-check catalog")
    print(f"{'ARTIFACT':<32} {'CHECK':<42} {'SEVERITY':<20} ENFORCEMENT")
    for artifact_type, check in iter_registry_checks():
        check_id = str(check.get("check_id", ""))
        severity = str(check.get("severity", ""))
        layer = enforcement_layer(check)
        print(f"{artifact_type:<32} {check_id:<42} {severity:<20} {layer}")
    return 0


def cmd_shared_hash_vectors_verify() -> int:
    drift = verify_shared_vectors()
    if drift:
        for err in drift:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("OK shared hash vectors")
    return 0


def cmd_conformance_run(suite: str, *, json_output: bool = False, out_path: Path | None = None) -> int:
    report = build_conformance_report_data(suite)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if json_output:
        print(json.dumps(report, indent=2))
    code, errors = run_conformance(suite)
    if code == 0:
        if not json_output:
            print(f"OK conformance suite {suite}")
        return 0
    if not json_output:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
    return code


def cmd_schema_check() -> int:
    try:
        check_all_schemas()
        print("OK all schemas")
        return 0
    except Exception as exc:
        print(f"FAIL schema check: {exc}", file=sys.stderr)
        return 1


def cmd_examples_check() -> int:
    try:
        check_valid_examples(examples_dir())
        check_invalid_examples(examples_dir())
        print("OK all examples")
        return 0
    except ValidationError as exc:
        print(f"FAIL examples: {exc}", file=sys.stderr)
        for err in exc.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1


def cmd_validate_release_manifest(path: Path) -> int:
    drift = validate_release_manifest(path)
    if drift:
        for err in drift:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print(f"OK release manifest {path}")
    return 0


def cmd_validate_release_chain(
    path: Path | None,
    *,
    json_output: bool = False,
    out_path: Path | None = None,
) -> int:
    directory = resolve_release_chain_directory(path or release_dir())
    result = build_release_chain_validation_result(directory)
    validate_artifact(result, "ReleaseChainValidationResult.v0")
    if out_path is not None:
        write_release_chain_validation_result(directory, out_path)
    if json_output:
        print(json.dumps(result, indent=2))
    elif result["status"] == "ProofChecked":
        print(f"OK release chain {directory}")
    else:
        summary = build_release_chain_report(directory)
        print(
            f"FAIL {summary.get('failure_code')}: {summary.get('message')}",
            file=sys.stderr,
        )
    return 0 if result["status"] == "ProofChecked" else 1


def cmd_hash_vectors_verify() -> int:
    drift = verify_vectors()
    if drift:
        for err in drift:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("OK hash vectors")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pcs", description="Proof-Carrying Science CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate a PCS artifact file")
    p_validate.add_argument("path", type=Path)

    p_hash = sub.add_parser("hash", help="Compute canonical hash")
    p_hash.add_argument("path", type=Path)

    p_status = sub.add_parser("status", help="Status inspection and policy")
    status_sub = p_status.add_subparsers(dest="status_cmd", required=True)
    p_status_fields = status_sub.add_parser("fields", help="Print status fields from an artifact")
    p_status_fields.add_argument("path", type=Path)
    p_explain_status = status_sub.add_parser("explain", help="Explain a PCS status value")
    p_explain_status.add_argument("status_name")
    p_check_transition = status_sub.add_parser(
        "check-transition",
        help="Check whether transition between two artifacts is allowed",
    )
    p_check_transition.add_argument("old_path", type=Path)
    p_check_transition.add_argument("new_path", type=Path)

    p_explain_status_top = sub.add_parser("explain-status", help="Explain a PCS status value")
    p_explain_status_top.add_argument("status_name")

    p_check_transition_top = sub.add_parser(
        "check-status-transition",
        help="Check status transition between two artifact files",
    )
    p_check_transition_top.add_argument("old_path", type=Path)
    p_check_transition_top.add_argument("new_path", type=Path)

    p_migrate = sub.add_parser("migrate", help="Migrate a PCS artifact between schema versions")
    p_migrate.add_argument("path", type=Path)
    p_migrate.add_argument("--from", dest="from_version", default="v0")
    p_migrate.add_argument("--to", dest="to_version", default="v0")

    registry_parser = sub.add_parser("registry", help="Artifact registry commands")
    registry_sub = registry_parser.add_subparsers(dest="registry_cmd", required=True)
    registry_sub.add_parser("list", help="List registered artifact types")
    p_registry_explain = registry_sub.add_parser("explain", help="Explain a registry entry")
    p_registry_explain.add_argument("artifact_type")
    p_registry_validate = registry_sub.add_parser("validate", help="Validate registry file")
    p_registry_validate.add_argument("path", type=Path)
    p_registry_check = registry_sub.add_parser(
        "check-artifact", help="Check artifact against registry"
    )
    p_registry_check.add_argument("path", type=Path)
    registry_sub.add_parser(
        "audit",
        help="Audit registry semantic checks and release-chain ref catalog",
    )

    p_release = sub.add_parser(
        "validate-release-manifest",
        help="Validate LabTrust release fixture manifest and artifacts",
    )
    p_release.add_argument("path", type=Path)

    p_chain = sub.add_parser(
        "validate-release-chain",
        help="Validate atomic LabTrust release fixture chain consistency",
    )
    p_chain.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=None,
        help="Release fixture directory (default: examples/labtrust-release under repo root)",
    )
    p_chain.add_argument(
        "--json",
        action="store_true",
        help="Emit ReleaseChainValidationResult.v0 JSON",
    )
    p_chain.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write ReleaseChainValidationResult.v0 to this path",
    )

    schema_parser = sub.add_parser("schema", help="Schema commands")
    schema_sub = schema_parser.add_subparsers(dest="schema_cmd", required=True)
    schema_sub.add_parser("check", help="Validate JSON schemas")

    examples_parser = sub.add_parser("examples", help="Example fixture commands")
    examples_sub = examples_parser.add_subparsers(dest="examples_cmd", required=True)
    examples_sub.add_parser("check", help="Validate example fixtures")

    hash_parser = sub.add_parser("hash-vectors", help="Canonical hash test vectors")
    hash_sub = hash_parser.add_subparsers(dest="hash_cmd", required=True)
    hash_sub.add_parser("verify", help="Verify frozen hash vectors")
    hash_write = hash_sub.add_parser("write", help="Regenerate frozen hash vectors")
    hash_write.add_argument("--force", action="store_true")

    shared_hash_parser = sub.add_parser("shared-hash-vectors", help="Cross-language hash vectors")
    shared_hash_sub = shared_hash_parser.add_subparsers(dest="shared_hash_cmd", required=True)
    shared_hash_sub.add_parser("verify", help="Verify test_vectors/hash parity")
    shared_hash_write = shared_hash_sub.add_parser("write", help="Regenerate test_vectors/hash")
    shared_hash_write.add_argument("--force", action="store_true")

    conformance_parser = sub.add_parser("conformance", help="Protocol conformance suites")
    conformance_sub = conformance_parser.add_subparsers(dest="conformance_cmd", required=True)
    p_conformance_run = conformance_sub.add_parser("run", help="Run a conformance suite")
    p_conformance_run.add_argument(
        "--suite",
        default="all",
        help=f"Suite name or all (available: {', '.join(list_suites())}, all)",
    )
    p_conformance_run.add_argument("--json", action="store_true", help="Emit machine-readable report")
    p_conformance_run.add_argument("--out", type=Path, default=None, help="Write report JSON to path")

    p_extract_obligations = sub.add_parser(
        "extract-proof-obligations",
        help="Extract ProofObligation.v0 from a release fixture directory",
    )
    p_extract_obligations.add_argument(
        "--release",
        type=Path,
        required=True,
        help="Path to release_manifest.v0.json or release directory",
    )
    p_extract_obligations.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output ProofObligation.v0 JSON path",
    )

    p_lean_check = sub.add_parser(
        "lean-check",
        help="Check ProofObligation.v0 against the PCS Lean trust kernel catalog",
    )
    p_lean_check.add_argument(
        "--obligations",
        type=Path,
        required=True,
        help="ProofObligation.v0 JSON path",
    )
    p_lean_check.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output LeanCheckResult.v0 JSON path",
    )
    p_lean_check.add_argument(
        "--skip-lean-build",
        action="store_true",
        help="Skip lake build (for tests only)",
    )

    benchmark_parser = sub.add_parser("benchmark", help="PCS benchmark evaluation protocol")
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_cmd", required=True)
    benchmark_sub.add_parser("list", help="List registered benchmark suite ids")
    benchmark_sub.add_parser("validate", help="Validate benchmark fixture tree")
    benchmark_sub.add_parser(
        "materialize-ingest",
        help="Regenerate examples/benchmark_ingest from producer dialect fixtures",
    )
    p_benchmark_validate_ingest = benchmark_sub.add_parser(
        "validate-ingest",
        help="Validate examples/benchmark_ingest golden producer bundles",
    )
    p_benchmark_validate_ingest.add_argument(
        "--release-grade",
        action="store_true",
        help="Require release-grade adequacy (not only schema-valid / developer-grade)",
    )
    p_benchmark_validate_ingest.add_argument("--json", action="store_true", help="JSON report")
    p_benchmark_normalize = benchmark_sub.add_parser(
        "normalize",
        help="Normalize a repo dialect JSON file to a pcs-core benchmark schema",
    )
    p_benchmark_normalize.add_argument(
        "--dialect",
        type=Path,
        required=True,
        help="Path to dialect JSON (e.g. examples/benchmarks/compatibility/pf_admission_explain_quality.dialect.json)",
    )
    p_benchmark_normalize.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output normalized JSON path",
    )
    p_benchmark_run = benchmark_sub.add_parser("run", help="Run a benchmark suite")
    p_benchmark_run.add_argument(
        "--suite",
        required=True,
        help="Benchmark suite id (e.g. labtrust-qc-release-v0)",
    )
    p_benchmark_run.add_argument("--json", action="store_true", help="Emit BenchmarkReport.v0 JSON")
    p_benchmark_run.add_argument("--out", type=Path, default=None, help="Write report JSON to path")

    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args.path)
    if args.command == "hash":
        return cmd_hash(args.path)
    if args.command == "status" and args.status_cmd == "fields":
        return cmd_status_fields(args.path)
    if args.command == "status" and args.status_cmd == "explain":
        return cmd_explain_status(args.status_name)
    if args.command == "status" and args.status_cmd == "check-transition":
        return cmd_check_status_transition(args.old_path, args.new_path)
    if args.command == "explain-status":
        return cmd_explain_status(args.status_name)
    if args.command == "check-status-transition":
        return cmd_check_status_transition(args.old_path, args.new_path)
    if args.command == "migrate":
        return cmd_migrate(args.path, args.from_version, args.to_version)
    if args.command == "registry" and args.registry_cmd == "list":
        return cmd_registry_list()
    if args.command == "registry" and args.registry_cmd == "explain":
        return cmd_registry_explain(args.artifact_type)
    if args.command == "registry" and args.registry_cmd == "validate":
        return cmd_registry_validate(args.path)
    if args.command == "registry" and args.registry_cmd == "check-artifact":
        return cmd_registry_check_artifact(args.path)
    if args.command == "registry" and args.registry_cmd == "audit":
        return cmd_registry_audit()
    if args.command == "validate-release-manifest":
        return cmd_validate_release_manifest(args.path)
    if args.command == "validate-release-chain":
        return cmd_validate_release_chain(
            args.path,
            json_output=args.json,
            out_path=args.out,
        )
    if args.command == "schema" and args.schema_cmd == "check":
        return cmd_schema_check()
    if args.command == "examples" and args.examples_cmd == "check":
        return cmd_examples_check()
    if args.command == "hash-vectors" and args.hash_cmd == "verify":
        return cmd_hash_vectors_verify()
    if args.command == "hash-vectors" and args.hash_cmd == "write":
        write_vectors(force=args.force)
        print("Wrote hash vectors")
        return 0
    if args.command == "shared-hash-vectors" and args.shared_hash_cmd == "verify":
        return cmd_shared_hash_vectors_verify()
    if args.command == "shared-hash-vectors" and args.shared_hash_cmd == "write":
        write_shared_vectors(force=args.force)
        print("Wrote shared hash vectors")
        return 0
    if args.command == "conformance" and args.conformance_cmd == "run":
        return cmd_conformance_run(args.suite, json_output=args.json, out_path=args.out)
    if args.command == "extract-proof-obligations":
        return cmd_extract_proof_obligations(args.release, args.out)
    if args.command == "lean-check":
        return cmd_lean_check(args.obligations, args.out, skip_lean_build=args.skip_lean_build)
    if args.command == "benchmark" and args.benchmark_cmd == "list":
        return cmd_benchmark_list()
    if args.command == "benchmark" and args.benchmark_cmd == "validate":
        return cmd_benchmark_validate()
    if args.command == "benchmark" and args.benchmark_cmd == "materialize-ingest":
        return cmd_benchmark_materialize_ingest()
    if args.command == "benchmark" and args.benchmark_cmd == "validate-ingest":
        return cmd_benchmark_validate_ingest(
            release_grade=args.release_grade,
            json_output=args.json,
        )
    if args.command == "benchmark" and args.benchmark_cmd == "normalize":
        return cmd_benchmark_normalize(args.dialect, args.out)
    if args.command == "benchmark" and args.benchmark_cmd == "run":
        return cmd_benchmark_run(args.suite, json_output=args.json, out_path=args.out)

    parser.print_help()
    return 2


def cmd_benchmark_list() -> int:
    from pcs_core.benchmark_runner import list_benchmark_suite_ids

    for suite_id in list_benchmark_suite_ids():
        print(suite_id)
    return 0


def cmd_benchmark_materialize_ingest() -> int:
    import subprocess
    import sys

    from pcs_core.paths import repo_root

    script = repo_root() / "python" / "scripts" / "materialize_benchmark_producer_examples.py"
    proc = subprocess.run([sys.executable, str(script)], cwd=repo_root() / "python", check=False)
    return int(proc.returncode)


def cmd_benchmark_validate_ingest(*, release_grade: bool = False, json_output: bool = False) -> int:
    import json

    from pcs_core.benchmark_ingest import (
        summarize_ingest_adequacy,
        validate_all_benchmark_ingest_examples,
        validate_benchmark_ingest_supporting_artifacts,
    )

    errors = validate_benchmark_ingest_supporting_artifacts()
    errors.extend(validate_all_benchmark_ingest_examples(check_release_grade=release_grade))
    if json_output:
        print(
            json.dumps(
                {
                    "status": "failed" if errors else "passed",
                    "errors": errors,
                    "adequacy": summarize_ingest_adequacy(),
                },
                indent=2,
            ),
        )
        return 1 if errors else 0
    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("OK benchmark ingest examples")
    for row in summarize_ingest_adequacy():
        print(f"  {row['file']}: {row['tier']}")
    return 0


def cmd_benchmark_validate() -> int:
    from pcs_core.benchmark_compat import validate_compatibility_corpus
    from pcs_core.benchmark_runner import validate_benchmark_fixtures
    from pcs_core.paths import examples_dir, repo_root

    errors = validate_benchmark_fixtures()
    errors.extend(validate_compatibility_corpus())
    from pcs_core.benchmark_ingest import validate_all_benchmark_ingest_examples

    errors.extend(validate_all_benchmark_ingest_examples())
    for rel in (
        "benchmark_registry.valid.json",
        "benchmark_metric_registry.valid.json",
    ):
        path = examples_dir() / rel
        if not path.is_file():
            errors.append(f"missing examples/{rel}")
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"examples/{rel}: {exc}")
    manifest_path = repo_root() / "benchmarks/labtrust-qc-release/benchmark_manifest.v0.json"
    if manifest_path.is_file():
        try:
            validate_file(manifest_path)
        except ValidationError as exc:
            errors.append(f"{manifest_path.relative_to(repo_root())}: {exc}")
    if not errors:
        print("OK benchmark fixtures")
        return 0
    for err in errors:
        print(f"FAIL {err}", file=sys.stderr)
    return 1


def cmd_benchmark_normalize(dialect_path: Path, out_path: Path) -> int:
    import json

    from pcs_core.benchmark_compat import ALL_NORMALIZERS

    name = dialect_path.name
    if name not in ALL_NORMALIZERS:
        print(
            f"FAIL unknown dialect {name!r}; expected one of: {', '.join(sorted(ALL_NORMALIZERS))}",
            file=sys.stderr,
        )
        return 1
    artifact_type, normalizer = ALL_NORMALIZERS[name]
    try:
        raw = _load_json(dialect_path)
        normalized = normalizer(raw)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
        validate_file(out_path)
        print(f"OK {artifact_type} {out_path}")
        return 0
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL benchmark normalize: {exc}", file=sys.stderr)
        return 1


def cmd_benchmark_run(suite: str, *, json_output: bool = False, out_path: Path | None = None) -> int:
    from pcs_core.benchmark_runner import run_benchmark_suite

    try:
        report = run_benchmark_suite(suite)
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            validate_file(out_path)
        if json_output:
            print(json.dumps(report, indent=2))
        summary = report.get("summary", {})
        passed = summary.get("passed_cases", 0)
        total = summary.get("total_cases", 0)
        if passed == total:
            if not json_output:
                print(f"OK benchmark suite {suite} ({passed}/{total} cases)")
            return 0
        if not json_output:
            for failure in report.get("failures", []):
                print(f"FAIL {failure.get('case_id')}: {failure.get('message')}", file=sys.stderr)
        return 1
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        print(f"FAIL benchmark run: {exc}", file=sys.stderr)
        return 1


def cmd_extract_proof_obligations(release: Path, out_path: Path) -> int:
    from pcs_core.lean_trust import extract_proof_obligations_from_release

    release_path = release.resolve()
    if release_path.is_file():
        release_dir = release_path.parent
    else:
        release_dir = release_path
    try:
        doc = extract_proof_obligations_from_release(release_dir)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        validate_file(out_path)
        print(f"OK ProofObligation.v0 {out_path}")
        return 0
    except (ValidationError, ValueError) as exc:
        print(f"FAIL extract-proof-obligations: {exc}", file=sys.stderr)
        return 1


def cmd_lean_check(obligations_path: Path, out_path: Path, *, skip_lean_build: bool = False) -> int:
    from pcs_core.lean_trust import run_lean_check

    try:
        obligations_doc = _load_json(obligations_path)
        validate_artifact(obligations_doc, "ProofObligation.v0")
        result = run_lean_check(
            obligations_doc,
            require_lean_build=not skip_lean_build,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        validate_file(out_path)
        print(f"OK LeanCheckResult.v0 {out_path} status={result.get('status')}")
        return 0 if result.get("status") == "ProofChecked" else 1
    except (ValidationError, ValueError) as exc:
        print(f"FAIL lean-check: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
