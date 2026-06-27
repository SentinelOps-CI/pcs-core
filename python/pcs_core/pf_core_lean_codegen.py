"""Generate concrete Lean terms and proof obligations from PFCoreTrace.v0."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.paths import repo_root
from pcs_core.pf_core_contract import load_contracts_from_dir, validate_trace_contracts

EFFECT_KIND_TO_LEAN: dict[str, str] = {
    "file.read": "Effect.read",
    "file.write": "Effect.write",
    "network.egress": "Effect.network",
    "email.send": "Effect.externalMessage",
    "handoff.delegate": "Effect.stateChange",
    "mcp.invoke": "Effect.codeExecution",
    "lab.release": 'Effect.custom "lab.release"',
}

_LEAN_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")


def lean_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def lean_ident(prefix: str, raw: str) -> str:
    slug = _LEAN_IDENT_RE.sub("_", raw).strip("_")
    if not slug or slug[0].isdigit():
        slug = f"{prefix}_{slug or 'x'}"
    return slug


def effect_kind_to_lean(effect_kind: str) -> str:
    mapped = EFFECT_KIND_TO_LEAN.get(effect_kind)
    if mapped is None:
        return f'Effect.custom {lean_string_literal(effect_kind)}'
    return mapped


def principal_to_lean(principal: Mapping[str, Any], *, name: str) -> str:
    roles = [lean_string_literal(str(role)) for role in principal.get("roles", [])]
    capabilities = [
        lean_string_literal(str(cap)) for cap in principal.get("capabilities", [])
    ]
    roles_expr = "[]" if not roles else f"[{', '.join(roles)}]"
    caps_expr = "[]" if not capabilities else f"[{', '.join(capabilities)}]"
    return (
        f"def {name} : Principal :=\n"
        "  {\n"
        f"    id := {lean_string_literal(str(principal.get('principal_id') or ''))},\n"
        f"    tenant := {lean_string_literal(str(principal.get('tenant') or ''))},\n"
        f"    roles := {roles_expr},\n"
        f"    capabilities := {caps_expr}\n"
        "  }"
    )


def resource_to_lean(resource: Mapping[str, Any]) -> str:
    return (
        "{\n"
        f"      uri := {lean_string_literal(str(resource.get('uri') or ''))},\n"
        f"      tenant := {lean_string_literal(str(resource.get('tenant') or ''))},\n"
        "      labels := []\n"
        "    }"
    )


def action_to_lean(action: Mapping[str, Any], *, name: str) -> str:
    capability = action.get("capability")
    cap_id = ""
    if isinstance(capability, dict):
        cap_id = str(capability.get("capability_id") or "")
    effects = action.get("effects")
    effect_exprs: list[str] = []
    if isinstance(effects, list):
        for effect in effects:
            if isinstance(effect, dict):
                effect_exprs.append(effect_kind_to_lean(str(effect.get("effect_kind") or "")))
    if not effect_exprs:
        effect_exprs = ["Effect.read"]
    reads = action.get("reads")
    writes = action.get("writes")
    read_exprs = [
        resource_to_lean(item)
        for item in reads
        if isinstance(item, dict)
    ] if isinstance(reads, list) else []
    write_exprs = [
        resource_to_lean(item)
        for item in writes
        if isinstance(item, dict)
    ] if isinstance(writes, list) else []
    reads_expr = "[]" if not read_exprs else f"[{', '.join(read_exprs)}]"
    writes_expr = "[]" if not write_exprs else f"[{', '.join(write_exprs)}]"
    return (
        f"def {name} : Action :=\n"
        "  {\n"
        f"    id := {lean_string_literal(str(action.get('action_id') or ''))},\n"
        f"    toolName := {lean_string_literal(str(action.get('tool_name') or ''))},\n"
        f"    capability := {lean_string_literal(cap_id)},\n"
        f"    effects := [{', '.join(effect_exprs)}],\n"
        f"    reads := {reads_expr},\n"
        f"    writes := {writes_expr}\n"
        "  }"
    )


def decision_to_lean(decision: str) -> str:
    if decision == "deny":
        return "Decision.deny"
    return "Decision.allow"


def event_to_lean(event: Mapping[str, Any], *, name: str) -> tuple[str, str, str]:
    principal = event.get("principal")
    action = event.get("action")
    if not isinstance(principal, dict) or not isinstance(action, dict):
        raise ValueError("event requires principal and action objects")
    principal_name = f"{name}Principal"
    action_name = f"{name}Action"
    principal_def = principal_to_lean(principal, name=principal_name)
    action_def = action_to_lean(action, name=action_name)
    event_def = (
        f"def {name} : Event :=\n"
        "  {\n"
        f"    id := {lean_string_literal(str(event.get('event_id') or ''))},\n"
        f"    principal := {principal_name},\n"
        f"    action := {action_name},\n"
        f"    decision := {decision_to_lean(str(event.get('decision') or ''))}\n"
        "  }"
    )
    return principal_def, action_def, event_def


def trace_events(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = trace.get("events")
    if not isinstance(events, list):
        return []
    typed = [event for event in events if isinstance(event, dict)]
    return sorted(typed, key=lambda item: int(item.get("sequence") or 0))


def collect_contracts_for_trace(
    trace: Mapping[str, Any],
    *,
    trace_path: Path | None = None,
    contracts_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load PFCoreContract.v0 objects referenced by trace events."""
    if contracts_dir is not None and contracts_dir.is_dir():
        return load_contracts_from_dir(contracts_dir)

    if trace_path is None:
        return {}

    case_dir = trace_path.parent
    contracts = load_contracts_from_dir(case_dir)
    nested = case_dir / "contracts"
    if nested.is_dir():
        contracts.update(load_contracts_from_dir(nested))
    return contracts


def contract_pre_to_lean(contract: Mapping[str, Any], *, name: str) -> str:
    pre = contract.get("pre")
    cap_expr = "none"
    effect_expr = "none"
    tenant_expr = "false"
    if isinstance(pre, dict):
        cap = pre.get("require_capability")
        if isinstance(cap, str) and cap:
            cap_expr = f"some {lean_string_literal(cap)}"
        effect = pre.get("require_effect")
        if isinstance(effect, str) and effect:
            effect_expr = f"some {effect_kind_to_lean(effect)}"
        if pre.get("require_tenant_match") is True:
            tenant_expr = "true"
    return (
        f"def {name} : ContractPreSpec :=\n"
        "  {\n"
        f"    requireCapability := {cap_expr},\n"
        f"    requireEffect := {effect_expr},\n"
        f"    requireTenantMatch := {tenant_expr}\n"
        "  }"
    )


def contract_post_to_lean(contract: Mapping[str, Any], *, name: str) -> str:
    post = contract.get("post")
    decision_expr = "none"
    safe_expr = "false"
    if isinstance(post, dict):
        decision = post.get("require_decision")
        if isinstance(decision, str) and decision:
            decision_expr = f"some {decision_to_lean(decision)}"
        if post.get("require_event_safe") is True:
            safe_expr = "true"
    return (
        f"def {name} : ContractPostSpec :=\n"
        "  {\n"
        f"    requireDecision := {decision_expr},\n"
        f"    requireEventSafe := {safe_expr}\n"
        "  }"
    )


def contract_invariant_to_lean(contract: Mapping[str, Any], *, name: str) -> str:
    invariant = contract.get("invariant")
    safe_expr = "false"
    if isinstance(invariant, dict) and invariant.get("require_trace_safe") is True:
        safe_expr = "true"
    return (
        f"def {name} : ContractInvariantSpec :=\n"
        "  {\n"
        f"    requireTraceSafe := {safe_expr}\n"
        "  }"
    )


def contract_specs_to_lean(contract: Mapping[str, Any], *, base_name: str) -> str:
    return "\n\n".join(
        [
            contract_pre_to_lean(contract, name=f"{base_name}Pre"),
            contract_post_to_lean(contract, name=f"{base_name}Post"),
            contract_invariant_to_lean(contract, name=f"{base_name}Inv"),
        ]
    )


def generate_contract_proof_obligations(
    trace: Mapping[str, Any],
    contracts: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    """Return (contract Lean defs, contract proof theorems) for referenced contracts."""
    defs: list[str] = []
    theorems: list[str] = []
    seen_contracts: set[str] = set()

    trace_id = str(trace.get("trace_id") or "trace")
    trace_var = lean_ident("trace", trace_id)

    for index, event in enumerate(trace_events(trace)):
        refs = event.get("contract_refs")
        if not isinstance(refs, list):
            continue
        event_name = lean_ident("ev", str(event.get("event_id") or index))
        for ref in refs:
            contract_id = str(ref)
            contract = contracts.get(contract_id)
            if contract is None:
                continue
            base_name = lean_ident("contract", contract_id)
            if contract_id not in seen_contracts:
                seen_contracts.add(contract_id)
                defs.append(contract_specs_to_lean(contract, base_name=base_name))
                theorems.append(
                    f"theorem concrete_trace_satisfies_{base_name} : "
                    f"traceSatisfiesContractSpecsD {base_name}Pre {base_name}Post "
                    f"{base_name}Inv {trace_var} = true := by\n"
                    "  decide"
                )
            theorems.append(
                f"theorem concrete_satisfies_{base_name}_{event_name} : "
                f"satisfiesContractSpecD {base_name}Pre {base_name}Post {event_name} = true := by\n"
                "  decide"
            )
            theorems.append(
                f"theorem concrete_contract_pre_{base_name}_{event_name} : "
                f"contractPreD {base_name}Pre {event_name}Principal {event_name}Action = true := by\n"
                "  decide"
            )
            theorems.append(
                f"theorem concrete_contract_post_{base_name}_{event_name} : "
                f"contractPostD {base_name}Post {event_name} = true := by\n"
                "  decide"
            )

    return defs, theorems


def trace_has_contract_refs(trace: Mapping[str, Any]) -> bool:
    for event in trace_events(trace):
        refs = event.get("contract_refs")
        if isinstance(refs, list) and refs:
            return True
    return False


def collect_handoffs_near_trace(
    trace: Mapping[str, Any],
    *,
    trace_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Collect PFCoreHandoff.v0 objects from sibling fixture files or ToolUseTrace handoffs."""
    handoffs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_handoff(item: Mapping[str, Any]) -> None:
        handoff_id = str(item.get("handoff_id") or "")
        key = handoff_id or canonical_hash(dict(item))
        if key in seen:
            return
        seen.add(key)
        handoffs.append(dict(item))

    if trace_path is not None:
        case_dir = trace_path.parent
        for path in sorted(case_dir.glob("*.json")):
            if path.name == trace_path.name:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and data.get("artifact_type") == "PFCoreHandoff.v0":
                add_handoff(data)
        tool_use_path = case_dir / "tool_use_trace.json"
        if tool_use_path.is_file():
            try:
                tool_use = json.loads(tool_use_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                tool_use = None
            if isinstance(tool_use, dict):
                raw = tool_use.get("handoffs")
                if isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, dict) and item.get("artifact_type") == "PFCoreHandoff.v0":
                            add_handoff(item)
    return handoffs


def handoff_to_lean(handoff: Mapping[str, Any], *, name: str) -> str:
    from_principal = handoff.get("from_principal")
    to_principal = handoff.get("to_principal")
    if not isinstance(from_principal, dict) or not isinstance(to_principal, dict):
        raise ValueError("handoff requires from_principal and to_principal objects")
    from_name = f"{name}From"
    to_name = f"{name}To"
    from_def = principal_to_lean(from_principal, name=from_name)
    to_def = principal_to_lean(to_principal, name=to_name)
    delegated = handoff.get("delegated_capabilities")
    cap_ids: list[str] = []
    if isinstance(delegated, list):
        for item in delegated:
            if isinstance(item, dict):
                cap_id = str(item.get("capability_id") or "")
                if cap_id:
                    cap_ids.append(cap_id)
    caps_expr = "[]" if not cap_ids else f"[{', '.join(lean_string_literal(c) for c in cap_ids)}]"
    handoff_def = (
        f"def {name} : Handoff :=\n"
        "  {\n"
        f"    fromPrincipal := {from_name},\n"
        f"    toPrincipal := {to_name},\n"
        f"    delegatedCapabilities := {caps_expr}\n"
        "  }"
    )
    return "\n\n".join([from_def, to_def, handoff_def])


def trace_to_lean(trace: Mapping[str, Any]) -> str:
    """Generate Lean source defining concrete Principal/Action/Event/Trace values."""
    events = trace_events(trace)
    defs: list[str] = []
    event_names: list[str] = []
    for index, event in enumerate(events):
        event_id = str(event.get("event_id") or f"event_{index}")
        base_name = lean_ident("ev", event_id)
        principal_def, action_def, event_def = event_to_lean(event, name=base_name)
        defs.extend([principal_def, action_def, event_def])
        event_names.append(base_name)

    trace_expr = "Trace.empty"
    for event_name in event_names:
        trace_expr = f"Trace.cons ({trace_expr}) {event_name}"

    trace_id = str(trace.get("trace_id") or "trace")
    trace_name = lean_ident("trace", trace_id)
    body = "\n\n".join(defs)
    if body:
        body += "\n\n"
    body += f"def {trace_name} : Trace := {trace_expr}"
    return body


def generated_module_name(trace: Mapping[str, Any]) -> str:
    trace_hash = str(trace.get("trace_hash") or canonical_hash(dict(trace)))
    digest = trace_hash.removeprefix("sha256:")
    return f"Trace_{digest[:16]}"


def build_contract_semantics_checked(
    trace: Mapping[str, Any],
    contracts: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Summarize which contract fields are checked in Lean vs runtime only."""
    lean_checks: list[str] = []
    runtime_checks: list[str] = []
    if not trace_has_contract_refs(trace):
        return {"lean": lean_checks, "runtime": runtime_checks}
    for event in trace_events(trace):
        refs = event.get("contract_refs")
        if not isinstance(refs, list):
            continue
        for ref in refs:
            contract_id = str(ref)
            contract = contracts.get(contract_id)
            if contract is None:
                runtime_checks.append(f"missing_contract:{contract_id}")
                continue
            pre = contract.get("pre")
            if isinstance(pre, dict):
                if pre.get("require_capability"):
                    lean_checks.append(f"{contract_id}.pre.require_capability")
                if pre.get("require_effect"):
                    lean_checks.append(f"{contract_id}.pre.require_effect")
                if pre.get("require_tenant_match"):
                    lean_checks.append(f"{contract_id}.pre.require_tenant_match")
                if pre.get("require_role"):
                    runtime_checks.append(f"{contract_id}.pre.require_role")
                if pre.get("require_policy_ref"):
                    runtime_checks.append(f"{contract_id}.pre.require_policy_ref")
                if pre.get("require_evidence_ref"):
                    runtime_checks.append(f"{contract_id}.pre.require_evidence_ref")
            post = contract.get("post")
            if isinstance(post, dict):
                if post.get("require_decision"):
                    lean_checks.append(f"{contract_id}.post.require_decision")
                if post.get("require_event_safe"):
                    lean_checks.append(f"{contract_id}.post.require_event_safe")
            invariant = contract.get("invariant")
            if isinstance(invariant, dict) and invariant.get("require_trace_safe"):
                lean_checks.append(f"{contract_id}.invariant.require_trace_safe")
    return {
        "lean": sorted(set(lean_checks)),
        "runtime": sorted(set(runtime_checks)),
    }


def generate_proof_obligation_file(
    trace: Mapping[str, Any],
    out_dir: Path,
    *,
    trace_path: Path | None = None,
) -> Path:
    """Write a `.lean` file proving concrete trace/event (and optional handoff) safety."""
    module = generated_module_name(trace)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{module}.lean"

    events = trace_events(trace)
    trace_body = trace_to_lean(trace)
    trace_id = str(trace.get("trace_id") or "trace")
    trace_var = lean_ident("trace", trace_id)

    event_theorems = "\n".join(
        f"theorem concrete_event_safe_{lean_ident('ev', str(event.get('event_id') or index))} : "
        f"eventSafeD {lean_ident('ev', str(event.get('event_id') or index))} = true := by\n"
        "  decide"
        for index, event in enumerate(events)
    )
    event_theorem_block = f"{event_theorems}\n\n" if event_theorems else ""

    handoff_defs: list[str] = []
    handoff_theorems: list[str] = []
    for index, handoff in enumerate(collect_handoffs_near_trace(trace, trace_path=trace_path)):
        handoff_id = str(handoff.get("handoff_id") or f"handoff_{index}")
        handoff_name = lean_ident("handoff", handoff_id)
        handoff_defs.append(handoff_to_lean(handoff, name=handoff_name))
        handoff_theorems.append(
            f"theorem concrete_handoff_safe_{handoff_name} : "
            f"handoffSafeD {handoff_name} = true := by\n"
            "  decide"
        )
    handoff_block = ""
    if handoff_defs:
        handoff_block = "\n\n".join(handoff_defs) + "\n\n"
        handoff_block += "\n\n".join(handoff_theorems) + "\n\n"

    contracts = collect_contracts_for_trace(trace, trace_path=trace_path)
    contract_defs, contract_theorems = generate_contract_proof_obligations(trace, contracts)
    contract_def_block = ""
    contract_theorem_block = ""
    contract_note = ""
    if contract_defs:
        contract_def_block = "\n\n".join(contract_defs) + "\n\n"
        contract_theorem_block = "\n\n".join(contract_theorems) + "\n\n"
        contract_note = (
            "-- Contract refs discharged via ContractPreSpec/PostSpec deciders "
            "(subset of PFCoreContract.v0; see docs/pf-core/contract-semantics.md).\n"
        )
    elif trace_has_contract_refs(trace):
        contract_note = (
            "-- Contract refs present but contract JSON not found alongside trace; "
            "run `pcs pf-core validate-contracts` before lean-check.\n"
        )

    source = f"""import PFCore.Theorems
import PFCore.TraceCheck

/-!
# Generated concrete trace proof for `{trace_id}`

Auto-generated by pcs-core pf-core lean-check. Do not edit by hand.
{contract_note.strip()}
-/

namespace PFCore.Generated.{module}

{trace_body}

{contract_def_block}{handoff_block}theorem concrete_trace_safe : traceSafeD {trace_var} = true := by
  decide

theorem concrete_trace_safe_prop : TraceSafe {trace_var} :=
  (traceSafeD_sound {trace_var}).mp concrete_trace_safe

theorem concrete_allowed_events_allowed :
    ∀ ev, EventIn ev {trace_var} → ev.decision = Decision.allow →
      ActionAllowed ev.principal ev.action :=
  fun ev hIn hAllow =>
    every_allowed_event_in_safe_trace_is_allowed {trace_var} ev concrete_trace_safe_prop hIn hAllow

{event_theorem_block}{contract_theorem_block}end PFCore.Generated.{module}
"""
    out_path.write_text(source, encoding="utf-8")
    return out_path


def validate_contracts_before_codegen(
    trace: Mapping[str, Any],
    *,
    trace_path: Path | None = None,
    contracts_dir: Path | None = None,
) -> list[str]:
    """Return contract validation errors (empty when satisfied or no contract JSON)."""
    if not trace_has_contract_refs(trace):
        return []
    contracts = collect_contracts_for_trace(
        trace, trace_path=trace_path, contracts_dir=contracts_dir
    )
    if not contracts:
        return []
    issues = validate_trace_contracts(trace, contracts)
    return [
        f"{issue.code}: {issue.message}" + (f" (at {issue.path})" if issue.path else "")
        for issue in issues
    ]


def compute_lean_environment_hash() -> str:
    """Hash pinned Lean toolchain + lake manifest for reproducibility metadata."""
    lean_root = repo_root() / "lean"
    parts: list[str] = []
    toolchain = repo_root() / "lean-toolchain"
    if toolchain.is_file():
        parts.append(toolchain.read_text(encoding="utf-8"))
    for rel in ("lakefile.lean", "lake-manifest.json"):
        path = lean_root / rel
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def proof_term_ref_from_path(path: Path) -> str:
    root = repo_root()
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
