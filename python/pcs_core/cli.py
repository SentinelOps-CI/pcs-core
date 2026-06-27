"""PCS command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pcs_core.hash import canonical_hash
from pcs_core.hash_vectors import verify_vectors, write_vectors
from pcs_core.paths import examples_dir
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


def cmd_pf_core_audit_claims() -> int:
    from pcs_core.pf_core_claims import audit_claims

    violations = audit_claims()
    if violations:
        for item in violations:
            print(
                f"FAIL {item.path}:{item.line}: forbidden phrase {item.phrase!r}; "
                f"use {item.replacement!r}",
                file=sys.stderr,
            )
        return 1
    print("OK pf-core claim boundary (no forbidden phrases)")
    return 0


def cmd_pf_core_audit_boundary() -> int:
    from pcs_core.pf_core_claims import audit_boundary

    issues = audit_boundary()
    if issues:
        for item in issues:
            print(f"FAIL {item.code}: {item.message}", file=sys.stderr)
        return 1
    print("OK pf-core trusted boundary docs and registry")
    return 0


def cmd_pf_core_validate_trace(
    path: Path,
    contracts_dir: Path | None = None,
    *,
    tenant_isolation: bool = False,
) -> int:
    from pcs_core.pf_core_contract import load_contracts_from_dir, validate_trace_contracts
    from pcs_core.pf_core_runtime import validate_pfcore_trace_hash_chain, validate_tenant_isolation

    data = _load_json(path)
    errors = validate_pfcore_trace_hash_chain(data)
    if tenant_isolation:
        errors.extend(validate_tenant_isolation(data))
    if contracts_dir is not None:
        contracts = load_contracts_from_dir(contracts_dir)
        for issue in validate_trace_contracts(data, contracts):
            errors.append(f"{issue.code}: {issue.message}" + (f" (at {issue.path})" if issue.path else ""))
    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print(f"OK PFCoreTrace hash chain {path}")
    return 0


def cmd_pf_core_validate_contracts(trace: Path, contracts_dir: Path) -> int:
    from pcs_core.pf_core_contract import load_contracts_from_dir, validate_trace_contracts

    data = _load_json(trace)
    contracts = load_contracts_from_dir(contracts_dir)
    issues = validate_trace_contracts(data, contracts)
    if issues:
        for issue in issues:
            location = f" (at {issue.path})" if issue.path else ""
            print(f"FAIL {issue.code}: {issue.message}{location}", file=sys.stderr)
        return 1
    print(f"OK PF-Core contract satisfaction {trace}")
    return 0


def cmd_pf_core_compile_trace(path: Path) -> int:
    from pcs_core.pf_core_runtime import compile_tool_use_trace_to_pfcore_trace

    data = _load_json(path)
    try:
        compiled = compile_tool_use_trace_to_pfcore_trace(data)
    except Exception as exc:
        print(f"FAIL {path}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(compiled, indent=2))
    return 0


def cmd_pf_core_audit_lean_catalog() -> int:
    from pcs_core.pf_core_claims import audit_lean_catalog

    errors = audit_lean_catalog()
    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("OK pf-core lean catalog matches Lean sources")
    return 0


def cmd_pf_core_replay_trace(
    trace: Path,
    source: Path | None,
    out: Path | None,
    result_out: Path | None,
) -> int:
    from pcs_core.pf_core_replay import print_replay_disclaimer, run_replay_trace

    print_replay_disclaimer()
    code, result = run_replay_trace(
        trace,
        source_path=source,
        out_path=out,
        result_out_path=result_out,
    )
    if code == 0:
        dest = out or trace.with_name("PFCoreCertificate.v0.json")
        print(f"OK PF-Core replay-trace {trace} -> {dest}")
    else:
        print(f"FAIL PF-Core replay-trace {trace}", file=sys.stderr)
        for issue in result.get("issues", []):
            print(f"  - {issue.get('code')}: {issue.get('message')}", file=sys.stderr)
    return code


def cmd_pf_core_attach_certificate_check(
    trace: Path,
    checker: str,
    checker_version: str,
    attestation_ref: str | None,
    out: Path,
) -> int:
    from pcs_core.pf_core_certificate import attach_external_certificate_check
    from pcs_core.validate import validate_file

    data = _load_json(trace)
    cert = attach_external_certificate_check(
        data,
        checker=checker,
        checker_version=checker_version,
        attestation_ref=attestation_ref,
    )
    out.write_text(json.dumps(cert, indent=2), encoding="utf-8")
    validate_file(out)
    print(f"OK PF-Core attach-certificate-check {trace} -> {out}")
    return 0


def cmd_pf_core_certifyedge_check(
    trace: Path,
    property_id: str,
    out: Path,
    *,
    checker_version: str = "0.1.0",
    attestation_ref: str | None = None,
) -> int:
    from pcs_core.pf_core_certifyedge import run_certifyedge_check, write_certifyedge_certificate

    try:
        if out:
            write_certifyedge_certificate(
                trace,
                property_id,
                out,
                checker_version=checker_version,
                attestation_ref=attestation_ref,
            )
        else:
            result = run_certifyedge_check(
                trace,
                property_id,
                checker_version=checker_version,
                attestation_ref=attestation_ref,
            )
            if not result.ok:
                print(f"FAIL {result.message}", file=sys.stderr)
                return 1
            print(json.dumps(result.certificate, indent=2))
    except RuntimeError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if out:
        print(f"OK PF-Core certifyedge-check {trace} -> {out}")
    return 0


def cmd_pf_core_lean_check(
    trace: Path,
    out: Path | None,
    result_out: Path | None,
    skip_build: bool,
    skip_lean_proof: bool,
) -> int:
    from pcs_core.lean_check import run_pfcore_lean_check

    code, _result = run_pfcore_lean_check(
        trace,
        out_path=out,
        result_out_path=result_out,
        skip_build=skip_build,
        skip_lean_proof=skip_lean_proof,
    )
    if code == 0:
        dest = out or trace.with_name("PFCoreCertificate.v0.json")
        print(f"OK PF-Core lean-check {trace} -> {dest}")
    return code


def cmd_pf_core_audit_lean_no_sorry() -> int:
    from pcs_core.lean_check import audit_pfcore_lean_no_sorry

    errors = audit_pfcore_lean_no_sorry()
    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("OK pf-core lean no-sorry audit (lean/PFCore/)")
    return 0


def cmd_lean_check() -> int:
    from pcs_core.lean_check import cmd_lean_check_disclaimer_only

    return cmd_lean_check_disclaimer_only()


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

    pf_core_parser = sub.add_parser("pf-core", help="PF-Core trust boundary commands")
    pf_core_sub = pf_core_parser.add_subparsers(dest="pf_core_cmd", required=True)
    pf_core_sub.add_parser("audit-claims", help="Scan docs/examples for forbidden claim phrases")
    pf_core_sub.add_parser("audit-boundary", help="Verify PF-Core docs and registry entries")
    pf_core_sub.add_parser(
        "audit-lean-catalog",
        help="Verify trusted Lean catalog symbols exist in lean/**/*.lean",
    )
    pf_core_validate = pf_core_sub.add_parser(
        "validate-trace",
        help="Validate PFCoreTrace.v0 hash chain",
    )
    pf_core_validate.add_argument("path", type=Path)
    pf_core_validate.add_argument(
        "--contracts-dir",
        type=Path,
        default=None,
        help="Optional directory of PFCoreContract.v0 JSON files",
    )
    pf_core_validate.add_argument(
        "--tenant-isolation",
        action="store_true",
        help="Also require conservative tenant isolation on all events",
    )
    pf_core_contracts = pf_core_sub.add_parser(
        "validate-contracts",
        help="Validate PFCoreTrace events against PFCoreContract.v0 predicates",
    )
    pf_core_contracts.add_argument("trace", type=Path)
    pf_core_contracts.add_argument(
        "--contracts-dir",
        type=Path,
        required=True,
        help="Directory containing PFCoreContract.v0 JSON files",
    )
    pf_core_compile = pf_core_sub.add_parser(
        "compile-trace",
        help="Compile ToolUseTrace.v0 to PFCoreTrace.v0",
    )
    pf_core_compile.add_argument("path", type=Path)
    pf_core_lean = pf_core_sub.add_parser(
        "lean-check",
        help="Check PFCoreTrace against deciders and PFCore Lean build",
    )
    pf_core_lean.add_argument("--trace", type=Path, required=True)
    pf_core_lean.add_argument("--out", type=Path, default=None)
    pf_core_lean.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip lake build and concrete Lean proof (claim_class will be RuntimeChecked)",
    )
    pf_core_lean.add_argument(
        "--skip-lean-proof",
        action="store_true",
        help="Skip Lean codegen/proof; deciders only (claim_class will be RuntimeChecked)",
    )
    pf_core_lean.add_argument(
        "--result-out",
        type=Path,
        default=None,
        help="Write LeanCheckResult.v0 JSON (default: alongside --out certificate)",
    )
    pf_core_sub.add_parser(
        "audit-lean-no-sorry",
        help="Scan lean/PFCore/ for sorry/admit/axiom/unsafe",
    )
    pf_core_replay = pf_core_sub.add_parser(
        "replay-trace",
        help="Replay PFCoreTrace.v0 hash chain (ReplayValidated)",
    )
    pf_core_replay.add_argument("path", type=Path, help="PFCoreTrace.v0 JSON")
    pf_core_replay.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Optional ToolUseTrace.v0 or PFCoreRuntimeObservation.v0 source",
    )
    pf_core_replay.add_argument("--out", type=Path, default=None)
    pf_core_replay.add_argument(
        "--result-out",
        type=Path,
        default=None,
        help="Write LeanCheckResult.v0 JSON",
    )
    pf_core_attach = pf_core_sub.add_parser(
        "attach-certificate-check",
        help="Wrap external checker attestation as CertificateChecked",
    )
    pf_core_attach.add_argument("--trace", type=Path, required=True)
    pf_core_attach.add_argument("--checker", type=str, required=True)
    pf_core_attach.add_argument("--checker-version", type=str, required=True)
    pf_core_attach.add_argument("--attestation-ref", type=str, default=None)
    pf_core_attach.add_argument("--out", type=Path, required=True)
    pf_core_certifyedge = pf_core_sub.add_parser(
        "certifyedge-check",
        help="Run CertifyEdge (or mock) and emit CertificateChecked PFCoreCertificate",
    )
    pf_core_certifyedge.add_argument("--trace", type=Path, required=True)
    pf_core_certifyedge.add_argument(
        "--property",
        type=str,
        required=True,
        help="CertifyEdge property id (e.g. qc_release.temporal.safety)",
    )
    pf_core_certifyedge.add_argument("--out", type=Path, required=True)
    pf_core_certifyedge.add_argument("--checker-version", type=str, default="0.1.0")
    pf_core_certifyedge.add_argument("--attestation-ref", type=str, default=None)

    sub.add_parser(
        "lean-check",
        help="Lean trust kernel check (interim: disclaimer + catalog guidance)",
    )

    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args.path)
    if args.command == "hash":
        return cmd_hash(args.path)
    if args.command == "status":
        return cmd_status(args.path)
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
    if args.command == "pf-core" and args.pf_core_cmd == "audit-claims":
        return cmd_pf_core_audit_claims()
    if args.command == "pf-core" and args.pf_core_cmd == "audit-boundary":
        return cmd_pf_core_audit_boundary()
    if args.command == "pf-core" and args.pf_core_cmd == "audit-lean-catalog":
        return cmd_pf_core_audit_lean_catalog()
    if args.command == "pf-core" and args.pf_core_cmd == "validate-trace":
        return cmd_pf_core_validate_trace(
            args.path,
            args.contracts_dir,
            tenant_isolation=args.tenant_isolation,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "validate-contracts":
        return cmd_pf_core_validate_contracts(args.trace, args.contracts_dir)
    if args.command == "pf-core" and args.pf_core_cmd == "compile-trace":
        return cmd_pf_core_compile_trace(args.path)
    if args.command == "pf-core" and args.pf_core_cmd == "lean-check":
        return cmd_pf_core_lean_check(
            args.trace,
            args.out,
            args.result_out,
            args.skip_build,
            args.skip_lean_proof,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "audit-lean-no-sorry":
        return cmd_pf_core_audit_lean_no_sorry()
    if args.command == "pf-core" and args.pf_core_cmd == "replay-trace":
        return cmd_pf_core_replay_trace(args.path, args.source, args.out, args.result_out)
    if args.command == "pf-core" and args.pf_core_cmd == "attach-certificate-check":
        return cmd_pf_core_attach_certificate_check(
            args.trace,
            args.checker,
            args.checker_version,
            args.attestation_ref,
            args.out,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "certifyedge-check":
        return cmd_pf_core_certifyedge_check(
            args.trace,
            args.property,
            args.out,
            checker_version=args.checker_version,
            attestation_ref=args.attestation_ref,
        )
    if args.command == "lean-check":
        return cmd_lean_check()

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
