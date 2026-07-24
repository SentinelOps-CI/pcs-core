"""PCS command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pcs_core.conformance import (
    build_conformance_report_data,
    list_suites,
    run_conformance,
    set_conformance_release_grade,
)
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


def _cmd_va_validate(path: Path, *, expected_type: str, as_json: bool = False) -> int:
    try:
        data = _load_json(path)
        from pcs_core.verifier_assurance_validate import (
            SemanticIssue,
            validate_va_semantics,
        )

        validate_artifact(data, expected_type, release_grade=True)
        issues = validate_va_semantics(data, expected_type, as_issues=True)
        assert isinstance(issues, list)
        if issues:
            structured = []
            for item in issues:
                if isinstance(item, SemanticIssue):
                    structured.append(
                        {"code": item.code, "path": item.path, "message": item.message}
                    )
                else:
                    structured.append(
                        {"code": "ValidationError", "path": "$", "message": str(item)}
                    )
            if as_json:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "artifact_type": expected_type,
                            "path": str(path),
                            "errors": structured,
                        }
                    )
                )
            else:
                print(f"FAIL {path}: semantic validation failed for {expected_type}", file=sys.stderr)
                for item in structured:
                    print(
                        f"  - {item['code']} at {item['path']}: {item['message']}",
                        file=sys.stderr,
                    )
            return 1
        if as_json:
            print(json.dumps({"ok": True, "artifact_type": expected_type, "path": str(path)}))
        else:
            print(f"OK {expected_type} {path}")
        return 0
    except ValidationError as exc:
        errors: list[dict[str, str]] = []
        for err in exc.errors:
            if " at " in err and ": " in err:
                code, rest = err.split(" at ", 1)
                path_part, message = rest.split(": ", 1)
                errors.append({"code": code, "path": path_part, "message": message})
            else:
                errors.append({"code": "ValidationError", "path": "$", "message": err})
        if not errors:
            errors = [{"code": "ValidationError", "path": "$", "message": str(exc)}]
        payload = {
            "ok": False,
            "artifact_type": expected_type,
            "path": str(path),
            "errors": errors,
        }
        if as_json:
            print(json.dumps(payload))
        else:
            print(f"FAIL {path}: {exc}", file=sys.stderr)
            for err in exc.errors:
                print(f"  - {err}", file=sys.stderr)
        return 1


def cmd_assurance_build_report(
    *,
    campaign: Path,
    results: Path,
    adjudications: Path,
    out: Path,
    report_id: str,
    created_at: str,
    source_commit: str,
    release_grade: bool,
    as_json: bool,
) -> int:
    from pcs_core.verifier_assurance_report import (
        ReportBuildError,
        build_assurance_report_from_paths,
    )
    from pcs_core.verifier_assurance_validate import SemanticIssue

    try:
        report = build_assurance_report_from_paths(
            campaign_path=campaign,
            results_dir=results,
            adjudications_dir=adjudications,
            report_id=report_id,
            created_at=created_at,
            source_commit=source_commit,
            release_grade=release_grade,
            out_path=out,
        )
        if as_json:
            print(json.dumps({"ok": True, "out": str(out), "report_id": report["report_id"]}))
        else:
            print(f"OK wrote {out}")
        return 0
    except ReportBuildError as exc:
        structured = []
        for item in exc.issues:
            if isinstance(item, SemanticIssue):
                structured.append(
                    {"code": item.code, "path": item.path, "message": item.message}
                )
            else:
                structured.append(
                    {"code": "BuildFailure", "path": "$", "message": str(item)}
                )
        if as_json:
            print(json.dumps({"ok": False, "errors": structured}))
        else:
            print(f"FAIL build-report: {exc}", file=sys.stderr)
            for item in structured:
                print(
                    f"  - {item['code']} at {item['path']}: {item['message']}",
                    file=sys.stderr,
                )
        return 1
    except (ValidationError, OSError, ValueError) as exc:
        if as_json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "errors": [
                            {"code": "BuildFailure", "path": "$", "message": str(exc)}
                        ],
                    }
                )
            )
        else:
            print(f"FAIL build-report: {exc}", file=sys.stderr)
        return 1


def cmd_assurance_verify_report(path: Path, *, as_json: bool = False) -> int:
    try:
        from pcs_core.verifier_assurance_report import verify_assurance_report
        from pcs_core.verifier_assurance_validate import SemanticIssue

        data = _load_json(path)
        validate_artifact(data, "VerifierAssuranceReport.v1", release_grade=True)
        issues = verify_assurance_report(data)
        if issues:
            structured = []
            for item in issues:
                if isinstance(item, SemanticIssue):
                    structured.append(
                        {"code": item.code, "path": item.path, "message": item.message}
                    )
                else:
                    structured.append(
                        {"code": "ValidationError", "path": "$", "message": str(item)}
                    )
            if as_json:
                print(json.dumps({"ok": False, "path": str(path), "errors": structured}))
            else:
                print(
                    f"FAIL {path}: assurance report verification failed",
                    file=sys.stderr,
                )
                for item in structured:
                    print(
                        f"  - {item['code']} at {item['path']}: {item['message']}",
                        file=sys.stderr,
                    )
            return 1
        if as_json:
            print(json.dumps({"ok": True, "path": str(path)}))
        else:
            print(f"OK VerifierAssuranceReport.v1 {path}")
        return 0
    except ValidationError as exc:
        errors = [{"code": "ValidationError", "path": "$", "message": str(exc)}]
        for err in exc.errors:
            errors.append({"code": "ValidationError", "path": "$", "message": err})
        if as_json:
            print(json.dumps({"ok": False, "path": str(path), "errors": errors}))
        else:
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


def cmd_conformance_run(
    suite: str,
    *,
    json_output: bool = False,
    out_path: Path | None = None,
    release_grade: bool = False,
) -> int:
    set_conformance_release_grade(release_grade)
    report = build_conformance_report_data(suite)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if json_output:
        print(json.dumps(report, indent=2))
    code, errors = run_conformance(suite, release_grade=release_grade)
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
    cross_tenant_safety: bool = False,
    non_interference: bool = False,
    ni_tenant_low: str | None = None,
    ni_tenant_high: str | None = None,
) -> int:
    from pcs_core.pf_core_contract import load_contracts_from_dir, validate_trace_contracts
    from pcs_core.pf_core_runtime import (
        validate_cross_tenant_safety,
        validate_event_sequence_order,
        validate_observational_non_interference,
        validate_observational_non_interference_all_pairs,
        validate_pfcore_trace_hash_chain,
        validate_tenant_isolation,
    )

    data = _load_json(path)
    errors = validate_pfcore_trace_hash_chain(data)
    errors.extend(validate_event_sequence_order(data))
    if tenant_isolation:
        errors.extend(validate_tenant_isolation(data))
    if cross_tenant_safety:
        errors.extend(validate_cross_tenant_safety(data))
    if non_interference:
        if ni_tenant_low and ni_tenant_high:
            errors.extend(
                validate_observational_non_interference(data, ni_tenant_low, ni_tenant_high)
            )
        else:
            errors.extend(validate_observational_non_interference_all_pairs(data))
    if contracts_dir is not None:
        contracts = load_contracts_from_dir(contracts_dir)
        for issue in validate_trace_contracts(data, contracts):
            errors.append(
                f"{issue.code}: {issue.message}" + (f" (at {issue.path})" if issue.path else "")
            )
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
    require_live: bool = False,
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
                require_live=require_live,
            )
        else:
            result = run_certifyedge_check(
                trace,
                property_id,
                checker_version=checker_version,
                attestation_ref=attestation_ref,
                require_live=require_live,
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


def cmd_pf_core_attest_bundle(
    bundle: Path,
    property_id: str,
    *,
    require_live: bool = False,
    checker_version: str = "0.1.0",
    allow_absence: bool = False,
) -> int:
    """Bind live/stub/mock CertifyEdge evaluation to an exact release bundle."""
    from pcs_core.external_attestation import (
        attest_release_bundle,
        write_preview_absence_notice,
    )

    try:
        attestation, check = attest_release_bundle(
            bundle,
            property_id=property_id,
            require_live=require_live,
            checker_version=checker_version,
            write=True,
        )
    except (RuntimeError, ValueError) as exc:
        if allow_absence and not require_live:
            notice = write_preview_absence_notice(bundle, reason=str(exc))
            print(
                f"WARN external attestation unavailable; wrote preview absence notice {notice}",
                file=sys.stderr,
            )
            return 0
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print(
        f"OK PF-Core attest-bundle {bundle} "
        f"class={attestation.get('attestation_class')} "
        f"digest={attestation.get('release_bundle_digest')} "
        f"({check.message})"
    )
    return 0


def cmd_pf_core_validate_external_attestation(
    bundle: Path,
    *,
    require_live: bool = False,
    allow_absence: bool = False,
) -> int:
    from pcs_core.external_attestation import validate_bundle_external_attestation

    errors = validate_bundle_external_attestation(
        bundle,
        require_live=require_live,
        allow_absence_notice=allow_absence,
    )
    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print(f"OK PF-Core validate-external-attestation {bundle}")
    return 0


def cmd_pf_core_verify_proof_binding(certificate: Path, trace: Path | None) -> int:
    from pcs_core.pf_core_proof_binding import verify_proof_binding

    result = verify_proof_binding(certificate, trace_path=trace)
    if result.ok:
        print(f"OK PF-Core verify-proof-binding {certificate}")
        if result.proof_path:
            print(f"  proof: {result.proof_path}")
        if result.trace_path:
            print(f"  trace: {result.trace_path}")
        return 0
    print(f"FAIL PF-Core verify-proof-binding {certificate}", file=sys.stderr)
    for issue in result.issues:
        print(f"  - {issue.code}: {issue.message}", file=sys.stderr)
    return 1


def cmd_pf_core_lean_check(
    trace: Path,
    out: Path | None,
    result_out: Path | None,
    skip_build: bool,
    skip_lean_proof: bool,
    certificate_mode: str | None,
    release_grade: bool = False,
    allow_non_public_modes: bool = False,
) -> int:
    from pcs_core.lean_check import run_pfcore_lean_check

    code, result = run_pfcore_lean_check(
        trace,
        out_path=out,
        result_out_path=result_out,
        skip_build=skip_build,
        skip_lean_proof=skip_lean_proof,
        certificate_mode=certificate_mode,
        release_grade=release_grade,
        allow_non_public_modes=allow_non_public_modes,
    )
    paths = result.get("artifact_paths") if isinstance(result, dict) else None
    if isinstance(paths, dict) and paths:
        print("PF-Core lean-check artifact paths:")
        for key in (
            "certificate",
            "lean_check_result",
            "generated_proof",
            "semantic_projection",
            "theorem_manifest",
        ):
            if key in paths:
                print(f"  {key}: {paths[key]}")
    if code == 0:
        dest = out or trace.with_name("PFCoreCertificate.v0.json")
        print(f"OK PF-Core lean-check {trace} -> {dest}")
    return code


def cmd_release_check_gates(
    *,
    mode: str | None,
    pin: Path | None,
    registry: Path | None,
    release_root: Path | None,
    provenance_dir: Path | None,
    require_oci_publish: bool,
    as_json: bool,
) -> int:
    from pcs_core.release_gates import run_release_gate_check

    code, text = run_release_gate_check(
        mode=mode,
        pin_path=pin,
        registry_path=registry,
        release_root=release_root,
        provenance_dir=provenance_dir,
        require_oci_publish=require_oci_publish,
        as_json=as_json,
    )
    stream = sys.stdout if code == 0 or as_json else sys.stderr
    stream.write(text)
    return code


def cmd_pf_core_bundle_release(
    trace: Path,
    cert: Path,
    out: Path,
    lean_check_result: Path | None,
) -> int:
    from pcs_core.pf_core_bundle import bundle_release

    manifest = bundle_release(
        trace,
        cert,
        out,
        lean_check_result_path=lean_check_result,
    )
    print(f"OK PF-Core release bundle {out} -> {manifest}")
    return 0


def cmd_pf_core_validate_bundle(path: Path) -> int:
    from pcs_core.pf_core_bundle import validate_bundle

    result = validate_bundle(path)
    if not result.ok:
        for issue in result.issues:
            print(f"FAIL {issue.code}: {issue.message}", file=sys.stderr)
        return 1
    print(f"OK PF-Core release bundle {path}")
    return 0


def cmd_pf_core_verify_bundle(
    path: Path,
    *,
    skip_lean_compile: bool = False,
    result_out: Path | None = None,
) -> int:
    from pcs_core.pf_core_bundle import verify_bundle

    result = verify_bundle(
        path,
        skip_lean_compile=skip_lean_compile,
        result_out=result_out,
    )
    if result.result_path:
        print(f"verification result: {result.result_path}")
    if not result.ok:
        print(f"FAIL PF-Core verify-bundle {path}", file=sys.stderr)
        for issue in result.issues:
            print(f"  - {issue.code}: {issue.message}", file=sys.stderr)
        return 1
    print(f"OK PF-Core verify-bundle {path}")
    for check in result.checks:
        detail = f" ({check.detail})" if check.detail else ""
        print(f"  {check.check_id}: {check.status}{detail}")
    return 0


def cmd_pf_core_audit_lean_no_sorry() -> int:
    from pcs_core.lean_check import audit_pfcore_lean_no_sorry

    errors = audit_pfcore_lean_no_sorry()
    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("OK pf-core lean no-sorry audit (lean/PFCore/)")
    return 0


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

    p_capabilities = sub.add_parser(
        "capabilities",
        help="Report which validator/verifier backends are actually available",
    )
    p_capabilities.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

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
    pf_core_validate.add_argument(
        "--cross-tenant-safety",
        action="store_true",
        help="Also require TraceCrossTenantSafe mirror (in-tenant or deny per event)",
    )
    pf_core_validate.add_argument(
        "--non-interference",
        action="store_true",
        help=(
            "Also require TenantProjectionIsolation mirror "
            "(single-trace observational isolation; not paired-execution NI)"
        ),
    )
    pf_core_validate.add_argument(
        "--ni-tenant-low",
        default=None,
        help="Low observer tenant for --non-interference (default: all distinct pairs)",
    )
    pf_core_validate.add_argument(
        "--ni-tenant-high",
        default=None,
        help="High tenant for --non-interference (requires --ni-tenant-low)",
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
    pf_core_lean.add_argument(
        "--certificate-mode",
        type=str,
        default=None,
        help=(
            "Certificate mode for generated Lean obligations. Public claim surface is "
            "schemas/pf_core.certificate_mode_status.json: TraceSafeRCertificate=release_candidate "
            "(sole tool-use RC); TraceSafeCertificate=legacy; CompositionalExtensionCertificate="
            "experimental; HandoffSafe/ContractChecked/EffectFrame/FramePreserved=disabled "
            "(handoff/contract/effect-frame/transition evidence repaired; public enablement deferred; "
            "fail closed). External CertificateChecked is preview."
        ),
    )
    pf_core_lean.add_argument(
        "--release-grade",
        action="store_true",
        help=(
            "Enforce release-grade policy: tool-use requires TraceSafeRCertificate; "
            "disabled/experimental modes fail closed"
        ),
    )
    pf_core_lean.add_argument(
        "--allow-non-public-modes",
        action="store_true",
        help=(
            "Allow issuance of disabled/preview modes for fixture and codegen tests. "
            "Not for public release-candidate issuance."
        ),
    )
    pf_core_bundle = pf_core_sub.add_parser(
        "bundle-release",
        help="Assemble PF-Core release bundle (trace, certificate, proof, manifest)",
    )
    pf_core_bundle.add_argument("--trace", type=Path, required=True)
    pf_core_bundle.add_argument("--cert", type=Path, required=True)
    pf_core_bundle.add_argument("--out", type=Path, required=True)
    pf_core_bundle.add_argument(
        "--lean-check-result",
        type=Path,
        default=None,
        help="Optional LeanCheckResult.v0.json to include in bundle",
    )
    pf_core_sub.add_parser(
        "validate-bundle",
        help=(
            "Structural PF-Core release bundle check (manifests + digests). "
            "Stable releases must also run verify-bundle."
        ),
    ).add_argument("path", type=Path)
    pf_core_verify_bundle = pf_core_sub.add_parser(
        "verify-bundle",
        help=(
            "Independently verify a closed PF-Core release bundle: digest checks, "
            "projection replay, theorem reconstruction, Lean compile against bundled "
            "kernel, and attestation when required. Required for stable releases."
        ),
    )
    pf_core_verify_bundle.add_argument("path", type=Path)
    pf_core_verify_bundle.add_argument(
        "--skip-lean-compile",
        action="store_true",
        help="Skip bundled-kernel Lean compile (not valid for stable release verification)",
    )
    pf_core_verify_bundle.add_argument(
        "--result-out",
        type=Path,
        default=None,
        help="Write PFCoreBundleVerificationResult.v0 JSON (default: inside bundle dir)",
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
    pf_core_verify_binding = pf_core_sub.add_parser(
        "verify-proof-binding",
        help=(
            "Verify certificate trace_hash, proof_term_hash, lean_environment_hash, and proof file"
        ),
    )
    pf_core_verify_binding.add_argument(
        "--certificate",
        type=Path,
        required=True,
        help="PFCoreCertificate.v0 JSON with LeanKernelChecked",
    )
    pf_core_verify_binding.add_argument(
        "--trace",
        type=Path,
        default=None,
        help="Optional PFCoreTrace.v0 JSON to verify trace_hash binding",
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
    pf_core_certifyedge.add_argument(
        "--require-live",
        action="store_true",
        help="Fail when CertifyEdge live CLI is absent (also PF_CORE_CERTIFYEDGE_REQUIRE_LIVE=1)",
    )
    pf_core_attest = pf_core_sub.add_parser(
        "attest-bundle",
        help="Run CertifyEdge on a release bundle's trace and write ExternalAttestation.v0",
    )
    pf_core_attest.add_argument("--bundle", type=Path, required=True)
    pf_core_attest.add_argument(
        "--property",
        type=str,
        required=True,
        help="CertifyEdge property id (e.g. qc_release.temporal.safety)",
    )
    pf_core_attest.add_argument("--checker-version", type=str, default="0.1.0")
    pf_core_attest.add_argument(
        "--require-live",
        action="store_true",
        help="Fail closed unless live CertifyEdge attestation is produced",
    )
    pf_core_attest.add_argument(
        "--allow-absence",
        action="store_true",
        help="On failure without --require-live, write ABSENCE_OF_EXTERNAL_ATTESTATION.json",
    )
    pf_core_validate_attest = pf_core_sub.add_parser(
        "validate-external-attestation",
        help="Validate ExternalAttestation.v0 (or preview absence notice) in a bundle",
    )
    pf_core_validate_attest.add_argument("--bundle", type=Path, required=True)
    pf_core_validate_attest.add_argument("--require-live", action="store_true")
    pf_core_validate_attest.add_argument(
        "--allow-absence",
        action="store_true",
        help="Accept ABSENCE_OF_EXTERNAL_ATTESTATION.json for technical preview",
    )

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
    p_conformance_run.add_argument(
        "--json", action="store_true", help="Emit machine-readable report"
    )
    p_conformance_run.add_argument(
        "--out", type=Path, default=None, help="Write report JSON to path"
    )
    p_conformance_run.add_argument(
        "--release-grade",
        action="store_true",
        help="Require release-grade adequacy (fail closed when Lean proof path unavailable)",
    )

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
        help="Deprecated alias for `pcs pcs-envelope check` (release-envelope consistency)",
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

    envelope_parser = sub.add_parser(
        "pcs-envelope",
        help="PCS release-envelope consistency checks (ProofObligation.v0)",
    )
    envelope_sub = envelope_parser.add_subparsers(dest="envelope_cmd", required=True)
    p_envelope_check = envelope_sub.add_parser(
        "check",
        help="Validate ProofObligation.v0 release-envelope consistency",
    )
    p_envelope_check.add_argument(
        "--obligations",
        type=Path,
        required=True,
        help="ProofObligation.v0 JSON path",
    )
    p_envelope_check.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output LeanCheckResult.v0 JSON path",
    )
    p_envelope_check.add_argument(
        "--skip-lean-build",
        action="store_true",
        help="Skip lake build (for tests only)",
    )
    p_envelope_check.add_argument(
        "--lean-proof",
        action="store_true",
        help="Generate PCS obligation Lean module and run lake env lean (EnvelopeLeanChecked)",
    )

    benchmark_parser = sub.add_parser("benchmark", help="PCS benchmark evaluation protocol")
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_cmd", required=True)
    benchmark_sub.add_parser("list", help="List registered benchmark suite ids")
    benchmark_sub.add_parser("validate", help="Validate benchmark fixture tree")
    benchmark_sub.add_parser(
        "materialize-ingest",
        help="Regenerate examples/benchmark_ingest (producer export or dialect fallback)",
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
        help="Path to dialect JSON under examples/benchmarks/compatibility/",
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

    release_parser = sub.add_parser(
        "release",
        help="Stable/preview release infrastructure gates",
    )
    release_sub = release_parser.add_subparsers(dest="release_cmd", required=True)
    p_release_gates = release_sub.add_parser(
        "check-gates",
        help=(
            "Fail-closed org/infra gates (CertifyEdge pin, TrustedKeyRegistry, "
            "provenance gated policy, certificate-mode policy)"
        ),
    )
    p_release_gates.add_argument(
        "--mode",
        choices=("release", "preview", "dev"),
        default=None,
        help="Override PCS_RELEASE_MODE (default: env or preview)",
    )
    p_release_gates.add_argument(
        "--pin",
        type=Path,
        default=None,
        help="Path to pins/certifyedge.json",
    )
    p_release_gates.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="TrustedKeyRegistry.v0 JSON (else PCS_TRUSTED_KEY_REGISTRY)",
    )
    p_release_gates.add_argument(
        "--release-root",
        type=Path,
        default=None,
        help="Optional release/bundle root for ArtifactIntegrity signature verify",
    )
    p_release_gates.add_argument(
        "--provenance-dir",
        type=Path,
        default=None,
        help="Optional provenance package dir",
    )
    p_release_gates.add_argument(
        "--require-oci-publish",
        action="store_true",
        help="Fail release mode when PCS_VERIFIER_OCI_DIGEST is unset",
    )
    p_release_gates.add_argument(
        "--json",
        action="store_true",
        help="Emit ReleaseGateCheckReport.v0 JSON",
    )

    verifier_parser = sub.add_parser("verifier", help="Verifier Assurance profile/result commands")
    verifier_sub = verifier_parser.add_subparsers(dest="verifier_cmd", required=True)
    verifier_profile = verifier_sub.add_parser("profile", help="VerifierProfile.v1 commands")
    verifier_profile_sub = verifier_profile.add_subparsers(dest="verifier_profile_cmd", required=True)
    p_vp_validate = verifier_profile_sub.add_parser("validate", help="Validate VerifierProfile.v1")
    p_vp_validate.add_argument("path", type=Path)
    p_vp_validate.add_argument("--json", action="store_true")
    verifier_result = verifier_sub.add_parser("result", help="VerificationResult.v1 commands")
    verifier_result_sub = verifier_result.add_subparsers(dest="verifier_result_cmd", required=True)
    p_vr_validate = verifier_result_sub.add_parser("validate", help="Validate VerificationResult.v1")
    p_vr_validate.add_argument("path", type=Path)
    p_vr_validate.add_argument("--json", action="store_true")

    reward_parser = sub.add_parser("reward", help="RewardEvidenceEnvelope.v1 commands")
    reward_sub = reward_parser.add_subparsers(dest="reward_cmd", required=True)
    p_reward_validate = reward_sub.add_parser("validate", help="Validate RewardEvidenceEnvelope.v1")
    p_reward_validate.add_argument("path", type=Path)
    p_reward_validate.add_argument("--json", action="store_true")

    campaign_parser = sub.add_parser("campaign", help="OptimizationCampaignManifest.v1 commands")
    campaign_sub = campaign_parser.add_subparsers(dest="campaign_cmd", required=True)
    p_campaign_validate = campaign_sub.add_parser(
        "validate", help="Validate OptimizationCampaignManifest.v1"
    )
    p_campaign_validate.add_argument("path", type=Path)
    p_campaign_validate.add_argument("--json", action="store_true")

    adjudication_parser = sub.add_parser("adjudication", help="AdjudicationRecord.v1 commands")
    adjudication_sub = adjudication_parser.add_subparsers(dest="adjudication_cmd", required=True)
    p_adj_validate = adjudication_sub.add_parser("validate", help="Validate AdjudicationRecord.v1")
    p_adj_validate.add_argument("path", type=Path)
    p_adj_validate.add_argument("--json", action="store_true")

    assurance_parser = sub.add_parser("assurance", help="VerifierAssuranceReport.v1 commands")
    assurance_sub = assurance_parser.add_subparsers(dest="assurance_cmd", required=True)
    p_assurance_build = assurance_sub.add_parser(
        "build-report", help="Build VerifierAssuranceReport.v1 offline"
    )
    p_assurance_build.add_argument("--campaign", type=Path, required=True)
    p_assurance_build.add_argument("--results", type=Path, required=True)
    p_assurance_build.add_argument("--adjudications", type=Path, required=True)
    p_assurance_build.add_argument("--out", type=Path, required=True)
    p_assurance_build.add_argument("--report-id", default="report-local")
    p_assurance_build.add_argument("--created-at", default="2026-07-24T15:00:00Z")
    p_assurance_build.add_argument(
        "--source-commit",
        default="e068794683959c52a19594a6d271dd5e69f3c999",
    )
    p_assurance_build.add_argument("--release-grade", action="store_true")
    p_assurance_build.add_argument("--json", action="store_true")
    p_assurance_verify = assurance_sub.add_parser(
        "verify-report", help="Verify VerifierAssuranceReport.v1"
    )
    p_assurance_verify.add_argument("path", type=Path)
    p_assurance_verify.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "capabilities":
        from pcs_core.capabilities import cmd_capabilities

        return cmd_capabilities(as_json=args.json)
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
            cross_tenant_safety=args.cross_tenant_safety,
            non_interference=args.non_interference,
            ni_tenant_low=args.ni_tenant_low,
            ni_tenant_high=args.ni_tenant_high,
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
            args.certificate_mode,
            args.release_grade,
            args.allow_non_public_modes,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "bundle-release":
        return cmd_pf_core_bundle_release(
            args.trace,
            args.cert,
            args.out,
            args.lean_check_result,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "validate-bundle":
        return cmd_pf_core_validate_bundle(args.path)
    if args.command == "pf-core" and args.pf_core_cmd == "verify-bundle":
        return cmd_pf_core_verify_bundle(
            args.path,
            skip_lean_compile=args.skip_lean_compile,
            result_out=args.result_out,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "audit-lean-no-sorry":
        return cmd_pf_core_audit_lean_no_sorry()
    if args.command == "pf-core" and args.pf_core_cmd == "replay-trace":
        return cmd_pf_core_replay_trace(args.path, args.source, args.out, args.result_out)
    if args.command == "pf-core" and args.pf_core_cmd == "verify-proof-binding":
        return cmd_pf_core_verify_proof_binding(args.certificate, args.trace)
    if args.command == "pf-core" and args.pf_core_cmd == "attach-certificate-check":
        return cmd_pf_core_attach_certificate_check(
            args.trace,
            args.checker,
            args.checker_version,
            args.attestation_ref,
            args.out,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "attest-bundle":
        return cmd_pf_core_attest_bundle(
            args.bundle,
            args.property,
            require_live=args.require_live,
            checker_version=args.checker_version,
            allow_absence=args.allow_absence,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "validate-external-attestation":
        return cmd_pf_core_validate_external_attestation(
            args.bundle,
            require_live=args.require_live,
            allow_absence=args.allow_absence,
        )
    if args.command == "pf-core" and args.pf_core_cmd == "certifyedge-check":
        return cmd_pf_core_certifyedge_check(
            args.trace,
            args.property,
            args.out,
            checker_version=args.checker_version,
            attestation_ref=args.attestation_ref,
            require_live=args.require_live,
        )
    if args.command == "shared-hash-vectors" and args.shared_hash_cmd == "verify":
        return cmd_shared_hash_vectors_verify()
    if args.command == "shared-hash-vectors" and args.shared_hash_cmd == "write":
        write_shared_vectors(force=args.force)
        print("Wrote shared hash vectors")
        return 0
    if args.command == "conformance" and args.conformance_cmd == "run":
        return cmd_conformance_run(
            args.suite,
            json_output=args.json,
            out_path=args.out,
            release_grade=args.release_grade,
        )
    if args.command == "extract-proof-obligations":
        return cmd_extract_proof_obligations(args.release, args.out)
    if args.command == "lean-check":
        return cmd_pcs_envelope_check(
            args.obligations,
            args.out,
            skip_lean_build=args.skip_lean_build,
            deprecated=True,
        )
    if args.command == "pcs-envelope" and args.envelope_cmd == "check":
        return cmd_pcs_envelope_check(
            args.obligations,
            args.out,
            skip_lean_build=args.skip_lean_build,
            lean_proof=args.lean_proof,
            deprecated=False,
        )
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
    if args.command == "release" and args.release_cmd == "check-gates":
        return cmd_release_check_gates(
            mode=args.mode,
            pin=args.pin,
            registry=args.registry,
            release_root=args.release_root,
            provenance_dir=args.provenance_dir,
            require_oci_publish=args.require_oci_publish,
            as_json=args.json,
        )
    if args.command == "verifier" and args.verifier_cmd == "profile":
        return _cmd_va_validate(
            args.path, expected_type="VerifierProfile.v1", as_json=args.json
        )
    if args.command == "verifier" and args.verifier_cmd == "result":
        return _cmd_va_validate(
            args.path, expected_type="VerificationResult.v1", as_json=args.json
        )
    if args.command == "reward" and args.reward_cmd == "validate":
        return _cmd_va_validate(
            args.path, expected_type="RewardEvidenceEnvelope.v1", as_json=args.json
        )
    if args.command == "campaign" and args.campaign_cmd == "validate":
        return _cmd_va_validate(
            args.path, expected_type="OptimizationCampaignManifest.v1", as_json=args.json
        )
    if args.command == "adjudication" and args.adjudication_cmd == "validate":
        return _cmd_va_validate(
            args.path, expected_type="AdjudicationRecord.v1", as_json=args.json
        )
    if args.command == "assurance" and args.assurance_cmd == "build-report":
        return cmd_assurance_build_report(
            campaign=args.campaign,
            results=args.results,
            adjudications=args.adjudications,
            out=args.out,
            report_id=args.report_id,
            created_at=args.created_at,
            source_commit=args.source_commit,
            release_grade=args.release_grade,
            as_json=args.json,
        )
    if args.command == "assurance" and args.assurance_cmd == "verify-report":
        return cmd_assurance_verify_report(args.path, as_json=args.json)

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
        run_benchmark_ingest_contract_checks,
        summarize_ingest_adequacy,
    )

    errors = run_benchmark_ingest_contract_checks(check_release_grade=release_grade)
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
    from pcs_core.benchmark_ingest import run_benchmark_ingest_contract_checks

    errors.extend(run_benchmark_ingest_contract_checks())
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


def cmd_benchmark_run(
    suite: str, *, json_output: bool = False, out_path: Path | None = None
) -> int:
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


def cmd_pcs_envelope_check(
    obligations_path: Path,
    out_path: Path,
    *,
    skip_lean_build: bool = False,
    lean_proof: bool = False,
    deprecated: bool = False,
) -> int:
    from pcs_core.lean_check import PCS_LEAN_CHECK_DEPRECATION
    from pcs_core.lean_trust import PCS_LEAN_CHECK_DISCLAIMER, run_lean_check

    if deprecated:
        print(PCS_LEAN_CHECK_DEPRECATION, file=sys.stderr)
    print(PCS_LEAN_CHECK_DISCLAIMER, file=sys.stderr)

    try:
        obligations_doc = _load_json(obligations_path)
        validate_artifact(obligations_doc, "ProofObligation.v0")
        result = run_lean_check(
            obligations_doc,
            require_lean_build=not skip_lean_build,
            lean_proof=lean_proof,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        validate_file(out_path)
        print(
            f"OK PCS release-envelope check {out_path} "
            f"status={result.get('status')} claim_class={result.get('claim_class')}",
        )
        return 0 if result.get("status") == "ProofChecked" else 1
    except (ValidationError, ValueError) as exc:
        print(f"FAIL pcs-envelope check: {exc}", file=sys.stderr)
        return 1


def cmd_lean_check(obligations_path: Path, out_path: Path, *, skip_lean_build: bool = False) -> int:
    return cmd_pcs_envelope_check(
        obligations_path,
        out_path,
        skip_lean_build=skip_lean_build,
        deprecated=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
