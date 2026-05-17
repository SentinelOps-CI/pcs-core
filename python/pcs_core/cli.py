"""PCS command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pcs_core.hash import canonical_hash
from pcs_core.hash_vectors import verify_vectors, write_vectors
from pcs_core.paths import examples_dir, resolve_release_chain_directory
from pcs_core.release_fixtures import release_dir
from pcs_core.release_chain import validate_release_chain_messages, validate_release_chain_report
from pcs_core.release_fixtures import validate_release_manifest
from pcs_core.validate import (
    ValidationError,
    check_all_schemas,
    check_invalid_examples,
    check_valid_examples,
    detect_artifact_type,
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


def cmd_status(path: Path) -> int:
    data = _load_json(path)
    artifact_type = detect_artifact_type(data) or "unknown"
    statuses = _collect_statuses(data)
    print(f"artifact_type: {artifact_type}")
    for key, value in statuses:
        print(f"{key}: {value}")
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


def cmd_validate_release_chain(path: Path | None, *, json_output: bool = False) -> int:
    directory = resolve_release_chain_directory(path or release_dir())
    report = validate_release_chain_report(directory)
    if json_output:
        print(json.dumps(report, indent=2))
    elif report["status"] == "passed":
        print(f"OK release chain {directory}")
    else:
        print(f"FAIL {report.get('failure_code')}: {report.get('message')}", file=sys.stderr)
    return 0 if report["status"] == "passed" else 1


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

    p_status = sub.add_parser("status", help="Print status fields")
    p_status.add_argument("path", type=Path)

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
        help="Emit machine-readable validation report JSON",
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

    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args.path)
    if args.command == "hash":
        return cmd_hash(args.path)
    if args.command == "status":
        return cmd_status(args.path)
    if args.command == "validate-release-manifest":
        return cmd_validate_release_manifest(args.path)
    if args.command == "validate-release-chain":
        return cmd_validate_release_chain(args.path, json_output=args.json)
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

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
