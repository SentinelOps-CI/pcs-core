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
from pcs_core.release_chain_report import (
    build_release_chain_report,
    build_release_chain_validation_result,
    write_release_chain_validation_result,
)
from pcs_core.release_fixtures import release_dir, validate_release_manifest
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
    drift = validate_registry_file(path)
    if drift:
        for err in drift:
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


def cmd_shared_hash_vectors_verify() -> int:
    drift = verify_shared_vectors()
    if drift:
        for err in drift:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("OK shared hash vectors")
    return 0


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

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
