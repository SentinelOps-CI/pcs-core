"""PF-Core Lean trace checking and no-sorry audit."""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.lean_catalog import (
    PF_CORE_CONCRETE_PROOF_THEOREMS,
    PF_CORE_FORBIDDEN_LEAN_TOKENS,
    PF_CORE_LEAN_KERNEL_THEOREM_CATALOG,
    PF_CORE_THEOREM_CATALOG,
)
from pcs_core.paths import repo_root
from pcs_core.pf_core_contract_semantics import build_contract_semantics_checked
from pcs_core.pf_core_lean_codegen import (
    collect_contracts_for_trace,
    compute_lean_environment_hash,
    generate_proof_obligation_file,
    proof_term_ref_from_path,
    validate_contracts_before_codegen,
)
from pcs_core.pf_core_contract import (
    DEFAULT_TRACE_SAFE_CONTRACT_ID,
    default_trace_safe_contract_hash,
    trace_has_contract_binding,
)
from pcs_core.pf_core_runtime import (
    compute_trace_hash,
    expand_principal_capabilities,
    principal_capabilities_explicit,
    validate_pfcore_trace_hash_chain,
    validate_resource_scope,
)
from pcs_core.validate import validate_schema

PCS_LEAN_CHECK_DEPRECATION = (
    "Deprecation: `pcs lean-check` is deprecated for PCS release work; use "
    "`pcs pcs-envelope check` for PCS release-envelope consistency checks."
)

PCS_LEAN_CHECK_DISCLAIMER = (
    "PCS release-envelope consistency check validates ProofObligation.v0 against "
    "the PCS theorem catalog. A `ProofChecked` LeanCheckResult does not imply "
    "PF-Core trace safety (`RuntimeChecked` / concrete Lean proof). Use "
    "`pcs pf-core lean-check --trace <PFCoreTrace.v0.json>` for PF-Core kernel assurance."
)

LEAN_CHECK_DISCLAIMER = (
    "PF-Core lean-check validates trace events against Python deciders aligned with "
    "the PF-Core Lean kernel predicates. When the full pipeline runs (default), it "
    "generates a concrete Lean proof obligation file and requires `traceSafeD` to "
    "evaluate to true via the Lean kernel (`decide`). "
    "`LeanKernelChecked` is emitted only when that concrete proof succeeds. "
    "Use `--skip-build` or `--skip-lean-proof` for runtime-only assurance "
    "(`RuntimeChecked`)."
)

PF_CORE_ASSUMPTION_REFS = [
    "docs/pf-core/assumptions.md",
    "docs/pf-core/trusted-boundary.md",
]

_FORBIDDEN_TOKEN_RE = re.compile(
    r"\b(" + "|".join(re.escape(token) for token in PF_CORE_FORBIDDEN_LEAN_TOKENS) + r")\b"
)


@dataclass(frozen=True)
class PFCoreLeanCheckIssue:
    code: str
    message: str
    path: str | None = None


def print_lean_check_disclaimer(*, stream=None) -> None:
    stream = stream or sys.stderr
    print(LEAN_CHECK_DISCLAIMER, file=stream)


def lean_dir() -> Path:
    return repo_root() / "lean"


def pfcore_lean_dir() -> Path:
    return lean_dir() / "PFCore"


def pfcore_generated_dir() -> Path:
    return pfcore_lean_dir() / "Generated"


def pfcore_theorems_checked(*, lean_kernel: bool = False) -> list[str]:
    catalog = PF_CORE_LEAN_KERNEL_THEOREM_CATALOG if lean_kernel else PF_CORE_THEOREM_CATALOG
    return sorted(catalog)


def pfcore_concrete_proof_theorems() -> list[str]:
    return sorted(PF_CORE_CONCRETE_PROOF_THEOREMS)


def lean_build_status(*, ok: bool, detail: str, target: str = "PFCore") -> dict[str, Any]:
    return {"ok": ok, "target": target, "detail": detail}


def _windows_to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[-1]
    return f"/mnt/{drive}{tail}"


def _lake_invocation(args: list[str], *, cwd: Path) -> tuple[list[str], Path]:
    if shutil.which("lake"):
        return ["lake", *args], cwd
    if platform.system() == "Windows" and shutil.which("wsl"):
        wsl_cwd = _windows_to_wsl_path(cwd)
        cmd = " ".join(["lake", *args])
        return ["wsl", "bash", "-lc", f"cd {wsl_cwd} && {cmd}"], cwd
    return ["lake", *args], cwd


def _run_lake(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    directory = cwd or lean_dir()
    command, _ = _lake_invocation(args, cwd=directory)
    return subprocess.run(
        command,
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )


def run_lean_library_build(*, target: str = "PFCore", skip_build: bool = False) -> tuple[bool, str]:
    """Run `lake build <target>` in lean/ if present."""
    if skip_build:
        return True, "skipped"
    directory = lean_dir()
    if not (directory / "lakefile.lean").is_file():
        return False, f"Lean project not found at {directory}"
    if not shutil.which("lake") and not (
        platform.system() == "Windows" and shutil.which("wsl")
    ):
        return False, "lake executable not found (install Lean 4 toolchain or WSL)"
    proc = _run_lake(["build", target], cwd=directory)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return False, detail or f"lake build {target} failed"
    return True, "ok"


def run_lean_concrete_proof(
    proof_path: Path,
    *,
    skip_build: bool = False,
) -> tuple[bool, str]:
    """Compile a generated proof file with `lake env lean`."""
    if skip_build:
        return False, "skipped"
    directory = lean_dir()
    if not proof_path.is_file():
        return False, f"generated proof file missing: {proof_path}"
    build_ok, build_detail = run_lean_library_build(target="PFCore", skip_build=False)
    if not build_ok:
        return False, build_detail
    try:
        rel = proof_path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False, f"proof file must live under {directory}: {proof_path}"
    proc = _run_lake(["env", "lean", rel.as_posix()], cwd=directory)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return False, detail or "lake env lean failed on generated proof"
    return True, "ok"


def _allowed_capability_ids(principal: Mapping[str, Any]) -> set[str]:
    return {str(cap) for cap in principal.get("capabilities", [])}


def _same_tenant(principal: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    tenant = str(principal.get("tenant") or "")
    for key in ("reads", "writes"):
        resources = action.get(key)
        if not isinstance(resources, list):
            return False
        for resource in resources:
            if isinstance(resource, dict) and str(resource.get("tenant") or "") != tenant:
                return False
    return True


def has_capability_d(principal: Mapping[str, Any], capability: str) -> bool:
    return capability in _allowed_capability_ids(principal)


def action_within_tenant_d(principal: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    return _same_tenant(principal, action)


def action_allowed_d(principal: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    capability = action.get("capability")
    if not isinstance(capability, dict):
        return False
    cap_id = str(capability.get("capability_id") or "")
    if not (has_capability_d(principal, cap_id) and action_within_tenant_d(principal, action)):
        return False
    try:
        validate_resource_scope(action)
    except Exception:
        return False
    return True


def event_safe_d(event: Mapping[str, Any]) -> bool:
    decision = str(event.get("decision") or "")
    if decision == "deny":
        return True
    if decision != "allow":
        return False
    principal = event.get("principal")
    action = event.get("action")
    if not isinstance(principal, dict) or not isinstance(action, dict):
        return False
    return action_allowed_d(principal, action)


def trace_safe_d(events: list[Mapping[str, Any]]) -> bool:
    return all(event_safe_d(event) for event in events)


def build_decider_obligations(events: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    obligations: list[dict[str, Any]] = [
        {
            "kind": "TraceSafeDeciderSound",
            "theorem": "traceSafeD_sound",
            "passed": trace_safe_d(events),
        }
    ]
    for index, event in enumerate(events):
        obligations.append(
            {
                "kind": "EventSafeDeciderSound",
                "theorem": "eventSafeD_sound",
                "passed": event_safe_d(event),
                "proof_ref": f"events[{index}]",
            }
        )
    return obligations


def audit_pfcore_lean_no_sorry(*, allowlist_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    pfcore_dir = pfcore_lean_dir()
    if not pfcore_dir.is_dir():
        return ["PF-Core Lean directory missing: lean/PFCore/"]

    allowlist: set[tuple[str, str]] = set()
    if allowlist_path is None:
        allowlist_path = repo_root() / "docs" / "pf-core" / "trusted-boundary.md"
    if allowlist_path.is_file():
        for line in allowlist_path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| `lean/PFCore/"):
                continue
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) < 4:
                continue
            rel = cells[1].strip("`")
            exception = cells[2]
            if exception and exception != "—":
                allowlist.add((rel, exception))

    for path in sorted(pfcore_dir.rglob("*.lean")):
        rel = f"lean/PFCore/{path.relative_to(pfcore_dir).as_posix()}"
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{rel}: read failed: {exc}")
            continue
        for match in _FORBIDDEN_TOKEN_RE.finditer(content):
            token = match.group(1)
            if (rel, token) in allowlist:
                continue
            line_no = content.count("\n", 0, match.start()) + 1
            errors.append(f"{rel}:{line_no}: forbidden token {token!r}")
    return errors


def _trace_events(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = trace.get("events")
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, dict)]


def check_pfcore_trace_lean_semantics(trace: Mapping[str, Any]) -> list[PFCoreLeanCheckIssue]:
    issues: list[PFCoreLeanCheckIssue] = []
    schema_errors = validate_schema(dict(trace), "PFCoreTrace.v0")
    if schema_errors:
        for err in schema_errors:
            issues.append(PFCoreLeanCheckIssue("SchemaInvalid", err))
        return issues

    hash_errors = validate_pfcore_trace_hash_chain(dict(trace))
    for err in hash_errors:
        issues.append(PFCoreLeanCheckIssue("HashChainInvalid", err))

    events = _trace_events(trace)
    for index, event in enumerate(events):
        principal = event.get("principal")
        if isinstance(principal, dict) and not principal_capabilities_explicit(principal):
            expanded = expand_principal_capabilities(principal)
            issues.append(
                PFCoreLeanCheckIssue(
                    "PrincipalCapabilityMismatch",
                    "principal.capabilities must explicitly list all role-expanded "
                    f"capabilities for lean-check (expected {expanded!r})",
                    f"events[{index}].principal",
                )
            )
        if not event_safe_d(event):
            event_id = str(event.get("event_id") or index)
            issues.append(
                PFCoreLeanCheckIssue(
                    "EventUnsafe",
                    f"event {event_id!r} violates PF-Core EventSafe decider",
                    f"events[{index}]",
                )
            )

    if events and not trace_safe_d(events):
        issues.append(PFCoreLeanCheckIssue("TraceUnsafe", "trace fails TraceSafe decider"))

    claim_class = str(trace.get("claim_class") or "")
    if claim_class == "LeanKernelChecked" and not trace_has_contract_binding(trace):
        issues.append(
            PFCoreLeanCheckIssue(
                "ContractBindingMissing",
                "claim_class LeanKernelChecked requires contract_refs on events or "
                "default trace-safe contract binding",
                "root",
            )
        )

    return issues


def build_pfcore_certificate(
    trace: Mapping[str, Any],
    *,
    checker: str = "pcs-core",
    checker_version: str = "0.1.0",
    lean_build_ok: bool,
    lean_proof_ok: bool,
    skip_build: bool,
    skip_lean_proof: bool,
    build_detail: str,
    proof_detail: str,
    obligations: list[dict[str, Any]],
    proof_term_ref: str | None = None,
    lean_environment_hash: str | None = None,
) -> dict[str, Any]:
    events = _trace_events(trace)
    trace_hash = str(trace.get("trace_hash") or compute_trace_hash(dict(trace)))
    policy_hash = str(trace.get("policy_hash") or "sha256:" + "0" * 64)
    contract_hash = str(trace.get("contract_hash") or "sha256:" + "0" * 64)

    lean_proof_checked = lean_proof_ok and not skip_build and not skip_lean_proof
    if lean_proof_checked:
        claim_class = "LeanKernelChecked"
        proof_ref = proof_term_ref
    else:
        claim_class = "RuntimeChecked"
        proof_ref = None

    contracts = collect_contracts_for_trace(trace)
    contract_semantics = build_contract_semantics_checked(trace, contracts)

    default_contract_ref: str | None = None
    if lean_proof_checked:
        explicit_default = str(trace.get("default_contract_ref") or "")
        if explicit_default == DEFAULT_TRACE_SAFE_CONTRACT_ID:
            default_contract_ref = DEFAULT_TRACE_SAFE_CONTRACT_ID
        elif str(trace.get("contract_hash") or "") == default_trace_safe_contract_hash():
            default_contract_ref = DEFAULT_TRACE_SAFE_CONTRACT_ID
        elif trace_has_contract_binding(trace):
            for event in events:
                refs = event.get("contract_refs") if isinstance(event, dict) else None
                if isinstance(refs, list) and refs:
                    default_contract_ref = None
                    break

    cert: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": f"pfcore-cert-{trace.get('trace_id', 'unknown')}",
        "trace_hash": trace_hash,
        "contract_hash": contract_hash,
        "policy_hash": policy_hash,
        "claim_class": claim_class,
        "checker": checker,
        "checker_version": checker_version,
        "assumption_refs": list(PF_CORE_ASSUMPTION_REFS),
        "theorems_checked": pfcore_theorems_checked(lean_kernel=lean_proof_checked),
        "obligations": obligations,
        "lean_build_status": lean_build_status(
            ok=lean_build_ok and not skip_build,
            detail=build_detail,
        ),
        "lean_proof_checked": lean_proof_checked,
        "disclaimer": LEAN_CHECK_DISCLAIMER,
        "event_count": len(events),
        "contract_semantics_checked": contract_semantics,
        "source_repo": str(trace.get("source_repo") or "https://github.com/example/pcs-core"),
        "source_commit": str(trace.get("source_commit") or "0000000"),
        "signature_or_digest": trace_hash,
    }
    if lean_environment_hash:
        cert["lean_environment_hash"] = lean_environment_hash
    if default_contract_ref:
        cert["default_contract_ref"] = default_contract_ref
    if proof_ref:
        cert["proof_ref"] = proof_ref
        cert["proof_term_ref"] = proof_ref
    cert["signature_or_digest"] = canonical_hash(cert)
    return cert


def build_lean_check_result(
    *,
    trace_path: Path,
    issues: list[PFCoreLeanCheckIssue],
    no_sorry_errors: list[str],
    build_ok: bool,
    build_detail: str,
    proof_ok: bool,
    proof_detail: str,
    skip_build: bool,
    skip_lean_proof: bool,
    obligations: list[dict[str, Any]],
    lean_environment_hash: str | None = None,
    certificate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claim_class = "OutOfScope"
    status = "Rejected"
    if certificate is not None:
        claim_class = str(certificate["claim_class"])
        if certificate.get("lean_proof_checked"):
            status = "LeanProofChecked"
        else:
            status = "DecidersPassed"

    result: dict[str, Any] = {
        "artifact_type": "LeanCheckResult.v0",
        "schema_version": "v0",
        "status": status,
        "claim_class": claim_class,
        "trace_path": str(trace_path),
        "issues": [{"code": i.code, "message": i.message, "path": i.path} for i in issues],
        "obligations": obligations,
        "assumption_refs": list(PF_CORE_ASSUMPTION_REFS),
        "theorems_checked": pfcore_theorems_checked(
            lean_kernel=bool(certificate and certificate.get("lean_proof_checked"))
        ),
        "lean_build_status": lean_build_status(ok=build_ok and not skip_build, detail=build_detail),
        "lean_proof_checked": bool(certificate and certificate.get("lean_proof_checked")),
        "no_sorry_audit": {"ok": not no_sorry_errors, "errors": no_sorry_errors},
        "disclaimer": LEAN_CHECK_DISCLAIMER,
        "certificate": certificate,
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    if lean_environment_hash:
        result["lean_environment_hash"] = lean_environment_hash
    result["signature_or_digest"] = canonical_hash(result)
    return result


def run_pfcore_lean_check(
    trace_path: Path,
    *,
    out_path: Path | None = None,
    result_out_path: Path | None = None,
    skip_build: bool = False,
    skip_lean_proof: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Validate trace semantics, optionally prove concrete trace safety in Lean."""
    print_lean_check_disclaimer()
    data = json.loads(trace_path.read_text(encoding="utf-8"))
    events = _trace_events(data)
    obligations = build_decider_obligations(events)
    lean_environment_hash = compute_lean_environment_hash()

    issues = check_pfcore_trace_lean_semantics(data)
    contract_errors = validate_contracts_before_codegen(data, trace_path=trace_path)
    for err in contract_errors:
        issues.append(PFCoreLeanCheckIssue("ContractViolation", err))
    no_sorry_errors = audit_pfcore_lean_no_sorry()
    build_ok, build_detail = run_lean_library_build(target="PFCore", skip_build=skip_build)

    proof_ok = False
    proof_detail = "skipped" if skip_lean_proof or skip_build else "not-run"
    proof_term_ref: str | None = None

    if not issues and not no_sorry_errors and not skip_lean_proof:
        try:
            proof_path = generate_proof_obligation_file(
                data,
                pfcore_generated_dir(),
                trace_path=trace_path,
            )
            proof_term_ref = proof_term_ref_from_path(proof_path)
            obligations.append(
                {
                    "kind": "ConcreteTraceSafe",
                    "theorem": "concrete_trace_safe",
                    "passed": False,
                    "proof_ref": proof_term_ref,
                }
            )
            obligations.append(
                {
                    "kind": "ConcreteTraceSafeProp",
                    "theorem": "concrete_trace_safe_prop",
                    "passed": False,
                    "proof_ref": proof_term_ref,
                }
            )
            obligations.append(
                {
                    "kind": "ConcreteAllowedEventsAllowed",
                    "theorem": "concrete_allowed_events_allowed",
                    "passed": False,
                    "proof_ref": proof_term_ref,
                }
            )
            if not skip_build:
                proof_ok, proof_detail = run_lean_concrete_proof(proof_path, skip_build=False)
                for entry in obligations[-3:]:
                    entry["passed"] = proof_ok
        except OSError as exc:
            issues.append(PFCoreLeanCheckIssue("LeanCodegenFailed", str(exc)))
        except ValueError as exc:
            issues.append(PFCoreLeanCheckIssue("LeanCodegenFailed", str(exc)))

    def _emit(code: int, result: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if result_out_path:
            result_out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        elif out_path:
            sibling = out_path.with_name("LeanCheckResult.v0.json")
            sibling.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return code, result

    if issues or no_sorry_errors:
        result = build_lean_check_result(
            trace_path=trace_path,
            issues=issues,
            no_sorry_errors=no_sorry_errors,
            build_ok=build_ok,
            build_detail=build_detail,
            proof_ok=proof_ok,
            proof_detail=proof_detail,
            skip_build=skip_build,
            skip_lean_proof=skip_lean_proof,
            obligations=obligations,
            lean_environment_hash=lean_environment_hash,
        )
        return _emit(1, result)

    if not build_ok and not skip_build:
        issues.append(PFCoreLeanCheckIssue("LeanBuildFailed", build_detail))
        result = build_lean_check_result(
            trace_path=trace_path,
            issues=issues,
            no_sorry_errors=no_sorry_errors,
            build_ok=build_ok,
            build_detail=build_detail,
            proof_ok=proof_ok,
            proof_detail=proof_detail,
            skip_build=skip_build,
            skip_lean_proof=skip_lean_proof,
            obligations=obligations,
            lean_environment_hash=lean_environment_hash,
        )
        return _emit(1, result)

    if not skip_lean_proof and not skip_build and not proof_ok:
        issues.append(PFCoreLeanCheckIssue("LeanProofFailed", proof_detail))
        result = build_lean_check_result(
            trace_path=trace_path,
            issues=issues,
            no_sorry_errors=no_sorry_errors,
            build_ok=build_ok,
            build_detail=build_detail,
            proof_ok=proof_ok,
            proof_detail=proof_detail,
            skip_build=skip_build,
            skip_lean_proof=skip_lean_proof,
            obligations=obligations,
            lean_environment_hash=lean_environment_hash,
        )
        return _emit(1, result)

    cert = build_pfcore_certificate(
        data,
        lean_build_ok=build_ok,
        lean_proof_ok=proof_ok,
        skip_build=skip_build,
        skip_lean_proof=skip_lean_proof,
        build_detail=build_detail,
        proof_detail=proof_detail,
        obligations=obligations,
        proof_term_ref=proof_term_ref,
        lean_environment_hash=lean_environment_hash,
    )
    cert_errors = validate_schema(cert, "PFCoreCertificate.v0")
    if cert_errors:
        for err in cert_errors:
            issues.append(PFCoreLeanCheckIssue("CertificateInvalid", err))
        result = build_lean_check_result(
            trace_path=trace_path,
            issues=issues,
            no_sorry_errors=no_sorry_errors,
            build_ok=build_ok,
            build_detail=build_detail,
            proof_ok=proof_ok,
            proof_detail=proof_detail,
            skip_build=skip_build,
            skip_lean_proof=skip_lean_proof,
            obligations=obligations,
            lean_environment_hash=lean_environment_hash,
        )
        return _emit(1, result)

    result = build_lean_check_result(
        trace_path=trace_path,
        issues=[],
        no_sorry_errors=[],
        build_ok=build_ok,
        build_detail=build_detail,
        proof_ok=proof_ok,
        proof_detail=proof_detail,
        skip_build=skip_build,
        skip_lean_proof=skip_lean_proof,
        obligations=obligations,
        lean_environment_hash=lean_environment_hash,
        certificate=cert,
    )
    if out_path:
        out_path.write_text(json.dumps(cert, indent=2), encoding="utf-8")
    return _emit(0, result)


def cmd_lean_check_disclaimer_only() -> int:
    print(PCS_LEAN_CHECK_DISCLAIMER, file=sys.stderr)
    print_lean_check_disclaimer()
    print(
        "Note: use `pcs pf-core lean-check --trace <PFCoreTrace.v0.json>` "
        "for PF-Core trace checking.",
        file=sys.stderr,
    )
    return 2
