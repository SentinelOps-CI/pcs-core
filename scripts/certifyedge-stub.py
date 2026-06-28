#!/usr/bin/env python3
"""CertifyEdge CLI format stub for CI (no live attestation).

Mimics ``certifyedge check-trace`` stdout/exit codes for release-gate format
validation without a real CertifyEdge install.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _print_version() -> None:
    print("certifyedge-stub 0.1.0 (PF-Core CI format validation only)")


def _validate_trace_file(trace_path: Path) -> str | None:
    """Return an error message when the trace file is unusable."""
    if not trace_path.is_file():
        return f"trace not found: {trace_path}"
    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"trace is not valid JSON: {exc}"
    if not isinstance(payload, dict):
        return "trace root must be a JSON object"
    artifact_type = payload.get("artifact_type")
    if artifact_type is not None and artifact_type != "PFCoreTrace.v0":
        return f"expected PFCoreTrace.v0, got {artifact_type!r}"
    return None


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv in (["--version"], ["-V"], ["version"]):
        _print_version()
        return 0
    if argv == ["--help"] or (len(argv) == 1 and argv[0] in {"-h", "help"}):
        parser = argparse.ArgumentParser(prog="certifyedge")
        sub = parser.add_subparsers(dest="command")
        sub.add_parser("version")
        check = sub.add_parser("check-trace")
        check.add_argument("--trace", type=Path, required=True)
        check.add_argument("--property", type=str, required=True)
        parser.print_help()
        return 0

    parser = argparse.ArgumentParser(prog="certifyedge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version")
    check = sub.add_parser("check-trace")
    check.add_argument("--trace", type=Path, required=True)
    check.add_argument("--property", type=str, required=True)
    args = parser.parse_args(argv)

    if args.command == "version":
        _print_version()
        return 0

    trace_error = _validate_trace_file(args.trace)
    if trace_error is not None:
        print(f"error: {trace_error}", file=sys.stderr)
        return 2

    property_id = args.property.strip()
    if not property_id:
        print("error: --property is required", file=sys.stderr)
        return 2

    attestation = f"stub://certifyedge/{property_id}/{args.trace.name}"
    print(f"attestation: {attestation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
