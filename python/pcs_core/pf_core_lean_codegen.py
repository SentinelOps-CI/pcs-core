"""Generate concrete Lean terms and proof obligations from PFCoreTrace.v0.

Role expansion alignment: runtime ``ROLE_CAPABILITY_MAP`` in ``pf_core_runtime.py``
must stay in sync with Lean ``runtimeRoleMap`` in ``lean/PFCore/RoleMap.lean``.
Codegen emits principals with explicit ``capabilities`` (already expanded); it does
not reference ``runtimeRoleMap`` directly. Parity is enforced by
``tests/test_pf_core_research.py`` and ``pcs pf-core audit-lean-catalog``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.paths import repo_root
from pcs_core.pf_core_contract import (
    field_semantics_layer,
    load_contracts_from_dir,
    validate_trace_contracts,
)
from pcs_core.pf_core_runtime import is_tool_use_trace

DEFAULT_CERTIFICATE_MODE = "TraceSafeCertificate"
TOOL_USE_DEFAULT_CERTIFICATE_MODE = "TraceSafeRCertificate"

CERTIFICATE_MODES = frozenset(
    {
        "TraceSafeCertificate",
        "TraceSafeRCertificate",
        "FramePreservedCertificate",
        "EffectFrameCertificate",
        "HandoffSafeCertificate",
        "CompositionalExtensionCertificate",
        "ContractCheckedCertificate",
    }
)

MODE_OBLIGATION_THEOREMS: dict[str, frozenset[str]] = {
    "TraceSafeCertificate": frozenset(
        {
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
        }
    ),
    "TraceSafeRCertificate": frozenset(
        {
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_trace_safe_r",
            "concrete_trace_safe_r_prop",
            "concrete_trace_safe_r_implies_trace_safe",
        }
    ),
    "FramePreservedCertificate": frozenset(
        {
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "frame_valid_initial",
            "frame_preserved_steps",
        }
    ),
    "EffectFrameCertificate": frozenset(
        {
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_action_effects_in_frame",
        }
    ),
    "HandoffSafeCertificate": frozenset(
        {
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_handoff_safe",
        }
    ),
    "CompositionalExtensionCertificate": frozenset(
        {
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_compositional_extension",
        }
    ),
    "ContractCheckedCertificate": frozenset(
        {
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_contract_checked",
        }
    ),
}

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
_THEOREM_SIGNATURE_RE = re.compile(r"theorem (\w+) : (.+) :=", re.DOTALL)


def _workflow_certificate_mode_from_catalog(workflow_id: str) -> str | None:
    from pcs_core.pf_core_catalog import WORKFLOW_CERTIFICATE_MODES

    for entry in WORKFLOW_CERTIFICATE_MODES:
        if entry.get("workflow_id") == workflow_id:
            mode = entry.get("required_certificate_mode")
            if isinstance(mode, str) and mode.strip():
                return mode.strip()
    return None


def resolve_certificate_mode(
    trace: Mapping[str, Any],
    *,
    trace_path: Path | None = None,
    certificate_mode: str | None = None,
    release_grade: bool = False,
) -> str:
    """Pick certificate mode: CLI override, trace policy, workflow map, or legacy default."""
    if certificate_mode:
        if certificate_mode not in CERTIFICATE_MODES:
            raise ValueError(f"unknown certificate_mode {certificate_mode!r}")
        return certificate_mode
    required = trace.get("required_certificate_mode")
    if isinstance(required, str) and required:
        if required not in CERTIFICATE_MODES:
            raise ValueError(f"unknown required_certificate_mode {required!r}")
        return required
    workflow_id = str(trace.get("workflow_id") or "")
    if workflow_id:
        from pcs_core.workflow_profiles import required_certificate_mode_for_workflow

        profile_mode = required_certificate_mode_for_workflow(workflow_id)
        if profile_mode:
            if profile_mode not in CERTIFICATE_MODES:
                raise ValueError(
                    f"unknown workflow profile required_certificate_mode {profile_mode!r}"
                )
            return profile_mode
        catalog_mode = _workflow_certificate_mode_from_catalog(workflow_id)
        if catalog_mode:
            if catalog_mode not in CERTIFICATE_MODES:
                raise ValueError(
                    f"unknown catalog required_certificate_mode {catalog_mode!r}"
                )
            return catalog_mode
    if (
        not release_grade
        and trace_path is not None
        and (trace_path.parent / "tool_use_trace.json").is_file()
    ):
        return TOOL_USE_DEFAULT_CERTIFICATE_MODE
    return DEFAULT_CERTIFICATE_MODE


def enforce_tool_use_certificate_mode_policy(
    trace: Mapping[str, Any],
    mode: str,
    *,
    trace_path: Path | None = None,
    release_grade: bool = False,
) -> str | None:
    """Release-grade policy: tool-use traces must not resolve to base TraceSafeCertificate."""
    if not release_grade:
        return None
    if is_tool_use_trace(trace, trace_path=trace_path) and mode == DEFAULT_CERTIFICATE_MODE:
        return (
            "tool-use trace must resolve to TraceSafeRCertificate under release-grade policy "
            "(set required_certificate_mode on trace or remove TraceSafeCertificate override)"
        )
    return None


def certificate_mode_obligations(
    mode: str,
    events: list[Mapping[str, Any]],
) -> frozenset[str]:
    """Static + per-allow-event obligations for a certificate mode."""
    base = MODE_OBLIGATION_THEOREMS.get(mode, frozenset())
    if mode != "TraceSafeRCertificate":
        return base
    resource_scope = frozenset(
        f"concrete_action_resource_scope_{lean_ident('ev', str(event.get('event_id') or index))}"
        for index, event in enumerate(events)
        if str(event.get("decision") or "") == "allow"
    )
    return base | resource_scope


def lean_and_intro_theorem(name: str, props: list[str], proof_refs: list[str]) -> str:
    """Emit a conjunction theorem chaining concrete proof references via ``And.intro``."""
    if not props:
        raise ValueError(f"{name}: no propositions to conjoin")
    if len(props) != len(proof_refs):
        raise ValueError(f"{name}: props/proof_refs length mismatch")
    if len(props) == 1:
        return f"theorem {name} : {props[0]} := {proof_refs[0]}"
    typ = " ∧ ".join(props)
    proof = proof_refs[-1]
    for ref in reversed(proof_refs[:-1]):
        proof = f"And.intro {ref} {proof}"
    return f"theorem {name} : {typ} := {proof}"


def _parse_theorem_signature(lean_theorem: str) -> tuple[str, str] | None:
    match = _THEOREM_SIGNATURE_RE.search(lean_theorem)
    if match is None:
        return None
    return match.group(1), " ".join(match.group(2).split())


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
        return f"Effect.custom {lean_string_literal(effect_kind)}"
    return mapped


def principal_to_lean(principal: Mapping[str, Any], *, name: str) -> str:
    roles = [lean_string_literal(str(role)) for role in principal.get("roles", [])]
    capabilities = [lean_string_literal(str(cap)) for cap in principal.get("capabilities", [])]
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
    cap_effect_expr = "Effect.read"
    if isinstance(capability, dict):
        cap_id = str(capability.get("capability_id") or "")
        cap_effect_expr = effect_kind_to_lean(str(capability.get("effect_kind") or "file.read"))
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
    read_exprs = (
        [resource_to_lean(item) for item in reads if isinstance(item, dict)]
        if isinstance(reads, list)
        else []
    )
    write_exprs = (
        [resource_to_lean(item) for item in writes if isinstance(item, dict)]
        if isinstance(writes, list)
        else []
    )
    reads_expr = "[]" if not read_exprs else f"[{', '.join(read_exprs)}]"
    writes_expr = "[]" if not write_exprs else f"[{', '.join(write_exprs)}]"
    return (
        f"def {name} : Action :=\n"
        "  {\n"
        f"    id := {lean_string_literal(str(action.get('action_id') or ''))},\n"
        f"    toolName := {lean_string_literal(str(action.get('tool_name') or ''))},\n"
        f"    capability := {lean_string_literal(cap_id)},\n"
        f"    capabilityEffect := {cap_effect_expr},\n"
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
    role_expr = "none"
    if isinstance(pre, dict):
        cap = pre.get("require_capability")
        if (
            isinstance(cap, str)
            and cap
            and field_semantics_layer(contract, section="pre", field="require_capability") == "lean"
        ):
            cap_expr = f"some {lean_string_literal(cap)}"
        effect = pre.get("require_effect")
        if (
            isinstance(effect, str)
            and effect
            and field_semantics_layer(contract, section="pre", field="require_effect") == "lean"
        ):
            effect_expr = f"some {effect_kind_to_lean(effect)}"
        if (
            pre.get("require_tenant_match") is True
            and field_semantics_layer(contract, section="pre", field="require_tenant_match")
            == "lean"
        ):
            tenant_expr = "true"
        role = pre.get("require_role")
        if (
            isinstance(role, str)
            and role
            and field_semantics_layer(contract, section="pre", field="require_role") == "lean"
        ):
            role_expr = f"some {lean_string_literal(role)}"
    return (
        f"def {name} : ContractPreSpec :=\n"
        "  {\n"
        f"    requireCapability := {cap_expr},\n"
        f"    requireEffect := {effect_expr},\n"
        f"    requireTenantMatch := {tenant_expr},\n"
        f"    requireRole := {role_expr}\n"
        "  }"
    )


def contract_post_to_lean(contract: Mapping[str, Any], *, name: str) -> str:
    post = contract.get("post")
    decision_expr = "none"
    safe_expr = "false"
    if isinstance(post, dict):
        decision = post.get("require_decision")
        if (
            isinstance(decision, str)
            and decision
            and field_semantics_layer(contract, section="post", field="require_decision") == "lean"
        ):
            decision_expr = f"some {decision_to_lean(decision)}"
        if (
            post.get("require_event_safe") is True
            and field_semantics_layer(contract, section="post", field="require_event_safe")
            == "lean"
        ):
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
    if (
        isinstance(invariant, dict)
        and invariant.get("require_trace_safe") is True
        and field_semantics_layer(contract, section="invariant", field="require_trace_safe")
        == "lean"
    ):
        safe_expr = "true"
    return f"def {name} : ContractInvariantSpec :=\n  {{\n    requireTraceSafe := {safe_expr}\n  }}"


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
            if _contract_has_lean_pre_fields(contract):
                theorems.append(
                    f"theorem concrete_contract_pre_{base_name}_{event_name} : "
                    f"contractPreD {base_name}Pre {event_name}Principal {event_name}Action = true := by\n"
                    "  decide"
                )
            if _contract_has_lean_post_fields(contract):
                theorems.append(
                    f"theorem concrete_contract_post_{base_name}_{event_name} : "
                    f"contractPostD {base_name}Post {event_name} = true := by\n"
                    "  decide"
                )

    return defs, theorems


def _contract_has_lean_pre_fields(contract: Mapping[str, Any]) -> bool:
    pre = contract.get("pre")
    if not isinstance(pre, dict):
        return False
    if (
        isinstance(pre.get("require_capability"), str)
        and pre.get("require_capability")
        and field_semantics_layer(contract, section="pre", field="require_capability") == "lean"
    ):
        return True
    if (
        isinstance(pre.get("require_effect"), str)
        and pre.get("require_effect")
        and field_semantics_layer(contract, section="pre", field="require_effect") == "lean"
    ):
        return True
    if (
        pre.get("require_tenant_match") is True
        and field_semantics_layer(contract, section="pre", field="require_tenant_match") == "lean"
    ):
        return True
    if (
        isinstance(pre.get("require_role"), str)
        and pre.get("require_role")
        and field_semantics_layer(contract, section="pre", field="require_role") == "lean"
    ):
        return True
    return False


def _contract_has_lean_post_fields(contract: Mapping[str, Any]) -> bool:
    post = contract.get("post")
    if not isinstance(post, dict):
        return False
    if (
        post.get("require_decision")
        and field_semantics_layer(contract, section="post", field="require_decision") == "lean"
    ):
        return True
    if (
        post.get("require_event_safe") is True
        and field_semantics_layer(contract, section="post", field="require_event_safe") == "lean"
    ):
        return True
    return False


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
                        if (
                            isinstance(item, dict)
                            and item.get("artifact_type") == "PFCoreHandoff.v0"
                        ):
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


def generate_mode_proof_theorems(
    trace: Mapping[str, Any],
    *,
    trace_var: str,
    events: list[dict[str, Any]],
    certificate_mode: str,
    handoff_theorems: list[str],
    contract_theorems: list[str],
    trace_path: Path | None = None,
) -> list[str]:
    """Return additional Lean theorems for the selected certificate mode."""
    theorems: list[str] = []
    mode = certificate_mode if certificate_mode in CERTIFICATE_MODES else DEFAULT_CERTIFICATE_MODE

    if mode == "FramePreservedCertificate" and events:
        first = events[0]
        first_name = lean_ident("ev", str(first.get("event_id") or "0"))
        principal_name = f"{first_name}Principal"
        theorems.append(
            f"theorem frame_valid_initial : frameValidD (initialState {principal_name}) = true := by\n"
            "  decide"
        )
        state_expr = f"initialState {principal_name}"
        step_props: list[str] = [f"frameValidD (initialState {principal_name}) = true"]
        step_refs: list[str] = ["frame_valid_initial"]
        for index, event in enumerate(events):
            event_name = lean_ident("ev", str(event.get("event_id") or index))
            next_state = f"applyEvent {state_expr} {event_name}"
            step_theorem = f"frame_preserved_step_{event_name}"
            theorems.append(
                f"theorem {step_theorem} : frameValidD {next_state} = true := by\n  decide"
            )
            step_props.append(f"frameValidD {next_state} = true")
            step_refs.append(step_theorem)
            state_expr = next_state
        theorems.append(lean_and_intro_theorem("frame_preserved_steps", step_props, step_refs))

    if mode == "EffectFrameCertificate":
        effect_props: list[str] = []
        effect_refs: list[str] = []
        for index, event in enumerate(events):
            event_name = lean_ident("ev", str(event.get("event_id") or index))
            action_name = f"{event_name}Action"
            step_theorem = f"concrete_action_effects_in_frame_{event_name}"
            theorems.append(
                f"theorem {step_theorem} : "
                f"actionEffectsInFrameD {action_name} {action_name}.effects = true := by\n"
                "  decide"
            )
            effect_props.append(f"actionEffectsInFrameD {action_name} {action_name}.effects = true")
            effect_refs.append(step_theorem)
        if effect_props:
            theorems.append(
                lean_and_intro_theorem(
                    "concrete_action_effects_in_frame",
                    effect_props,
                    effect_refs,
                )
            )

    if mode == "HandoffSafeCertificate" and handoff_theorems:
        handoff_props: list[str] = []
        handoff_refs: list[str] = []
        for handoff_theorem in handoff_theorems:
            parsed = _parse_theorem_signature(handoff_theorem)
            if parsed is None:
                continue
            theorem_name, prop_type = parsed
            handoff_props.append(prop_type)
            handoff_refs.append(theorem_name)
        if handoff_props:
            theorems.append(
                lean_and_intro_theorem("concrete_handoff_safe", handoff_props, handoff_refs)
            )

    if mode == "CompositionalExtensionCertificate" and events:
        trace_expr = "Trace.empty"
        compositional_props: list[str] = []
        compositional_refs: list[str] = []
        for index, event in enumerate(events):
            event_name = lean_ident("ev", str(event.get("event_id") or index))
            prev_trace = trace_expr
            trace_expr = f"Trace.cons ({prev_trace}) {event_name}"
            step_theorem = f"concrete_compositional_extension_{event_name}"
            if index == 0:
                theorems.append(
                    f"theorem {step_theorem} : "
                    f"TraceSafe {trace_expr} :=\n"
                    f"  safe_extension_preserves_trace_safe {prev_trace} {event_name} "
                    "traceSafe_empty "
                    f"concrete_event_safe_{event_name}"
                )
            else:
                prev_event = lean_ident("ev", str(events[index - 1].get("event_id") or index - 1))
                theorems.append(
                    f"theorem {step_theorem} : "
                    f"TraceSafe {trace_expr} :=\n"
                    f"  safe_extension_preserves_trace_safe {prev_trace} {event_name} "
                    f"concrete_compositional_extension_{prev_event} "
                    f"concrete_event_safe_{event_name}"
                )
            compositional_props.append(f"TraceSafe {trace_expr}")
            compositional_refs.append(step_theorem)
        if compositional_props:
            theorems.append(
                lean_and_intro_theorem(
                    "concrete_compositional_extension",
                    compositional_props,
                    compositional_refs,
                )
            )

    if mode == "ContractCheckedCertificate" and contract_theorems:
        contract_props: list[str] = []
        contract_refs: list[str] = []
        for contract_theorem in contract_theorems:
            parsed = _parse_theorem_signature(contract_theorem)
            if parsed is None:
                continue
            theorem_name, prop_type = parsed
            contract_props.append(prop_type)
            contract_refs.append(theorem_name)
        if contract_props:
            theorems.append(
                lean_and_intro_theorem("concrete_contract_checked", contract_props, contract_refs)
            )

    if mode == "TraceSafeRCertificate" and events:
        if not all(
            str(event.get("decision") or "") != "allow"
            or action_resources_within_capability_pattern_d(event.get("action") or {})
            for event in events
            if isinstance(event, dict)
        ):
            raise ValueError(
                "TraceSafeRCertificate requires all allow events to pass resource-pattern scope"
            )
        theorems.extend(
            [
                f"theorem concrete_trace_safe_r : traceSafeRD {trace_var} = true := by\n  decide",
                f"theorem concrete_trace_safe_r_prop : TraceSafeR {trace_var} :=\n"
                f"  (traceSafeRD_sound {trace_var}).mp concrete_trace_safe_r",
                f"theorem concrete_trace_safe_r_implies_trace_safe :\n"
                f"    TraceSafe {trace_var} :=\n"
                f"  traceSafeR_implies_traceSafe {trace_var} concrete_trace_safe_r_prop",
            ]
        )

    return theorems


def generate_resource_scope_theorems(events: list[Mapping[str, Any]]) -> list[str]:
    """Per-allow-event resource-pattern bridge obligations (runtime trust boundary)."""
    theorems: list[str] = []
    for index, event in enumerate(events):
        if str(event.get("decision") or "") != "allow":
            continue
        action = event.get("action")
        if not isinstance(action, dict):
            continue
        event_name = lean_ident("ev", str(event.get("event_id") or index))
        action_name = f"{event_name}Action"
        theorems.append(
            f"theorem concrete_action_resource_scope_{event_name} :\n"
            f"    actionResourcesWithinCapabilityPatternD {action_name}.reads "
            f"{action_name}.writes {action_name}.capability = true := by\n"
            "  decide"
        )
    return theorems


def action_resources_within_capability_pattern_d(action: Mapping[str, Any]) -> bool:
    from pcs_core.pf_core_runtime import validate_resource_scope

    if not isinstance(action, dict):
        return False
    try:
        validate_resource_scope(action)
    except Exception:
        return False
    return True


def generate_trust_boundary_theorems(
    events: list[Mapping[str, Any]],
    *,
    trace_var: str,
) -> list[str]:
    """Conservative tenant isolation, cross-tenant safety, NI hooks (not TraceSafeR)."""
    return [
        f"theorem concrete_tenant_isolation_prop : TenantIsolation {trace_var} :=\n"
        f"  traceSafe_implies_tenant_isolation {trace_var} concrete_trace_safe_prop",
        f"theorem concrete_trace_cross_tenant_safe_prop : TraceCrossTenantSafe {trace_var} :=\n"
        f"  traceSafe_implies_trace_cross_tenant_safe {trace_var} concrete_trace_safe_prop",
        f"theorem concrete_non_interference_prop (tenantLow tenantHigh : String) :\n"
        f"    NonInterference tenantLow tenantHigh {trace_var} :=\n"
        f"  traceSafe_implies_non_interference tenantLow tenantHigh {trace_var} "
        "concrete_trace_safe_prop",
    ]


def generate_proof_obligation_file(
    trace: Mapping[str, Any],
    out_dir: Path,
    *,
    trace_path: Path | None = None,
    certificate_mode: str | None = None,
    release_grade: bool = False,
) -> Path:
    """Write a `.lean` file proving concrete trace/event (and optional handoff) safety."""
    mode = resolve_certificate_mode(
        trace,
        trace_path=trace_path,
        certificate_mode=certificate_mode,
        release_grade=release_grade,
    )
    if release_grade and is_tool_use_trace(trace, trace_path=trace_path):
        mode = TOOL_USE_DEFAULT_CERTIFICATE_MODE

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

    mode_theorems = generate_mode_proof_theorems(
        trace,
        trace_var=trace_var,
        events=events,
        certificate_mode=mode,
        handoff_theorems=handoff_theorems,
        contract_theorems=contract_theorems,
        trace_path=trace_path,
    )
    mode_theorem_block = ""
    if mode_theorems:
        mode_theorem_block = "\n\n".join(mode_theorems) + "\n\n"

    trust_boundary_theorems = generate_trust_boundary_theorems(events, trace_var=trace_var)
    trust_boundary_block = "\n\n".join(trust_boundary_theorems) + "\n\n"

    resource_scope_theorems = (
        generate_resource_scope_theorems(events) if mode == "TraceSafeRCertificate" else []
    )
    resource_scope_block = ""
    if resource_scope_theorems:
        resource_scope_block = "\n\n".join(resource_scope_theorems) + "\n\n"

    source = f"""import PFCore.Theorems
import PFCore.TraceCheck
import PFCore.State
import PFCore.NonInterference
import PFCore.Observational
import PFCore.ResourcePattern

/-!
# Generated concrete trace proof for `{trace_id}`

Auto-generated by pcs-core pf-core lean-check. Do not edit by hand.
Certificate mode: `{mode}`.
{contract_note.strip()}
Trust-boundary hooks (tenant isolation, cross-tenant safety, observational NI) are
discharged via proved links from `TraceSafe`. `TraceSafeRCertificate` additionally
discharges `concrete_trace_safe_r*` and per-event `concrete_action_resource_scope_*`.
Base `TraceSafe` / `ActionAdmissible` omit pattern discharge; `TraceSafeR` refines them.

Release-grade tool-use lean-check treats `TraceSafeRCertificate` as the sole supported
`LeanKernelChecked` path (refinement to base `TraceSafe` via `traceSafeR_implies_traceSafe`).
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

{event_theorem_block}{trust_boundary_block}{resource_scope_block}{contract_theorem_block}{mode_theorem_block}end PFCore.Generated.{module}
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


def pfcore_kernel_lean_paths() -> list[Path]:
    """Sorted PF-Core kernel Lean sources (excludes Generated/)."""
    pfcore_dir = repo_root() / "lean" / "PFCore"
    if not pfcore_dir.is_dir():
        return []
    paths = sorted(pfcore_dir.rglob("*.lean"))
    return [path for path in paths if "Generated" not in path.parts]


def pcs_kernel_lean_paths() -> list[Path]:
    """Sorted PCS Lean sources for PCS release-chain proof paths (excludes Generated/)."""
    pcs_dir = repo_root() / "lean" / "PCS"
    if not pcs_dir.is_dir():
        return []
    paths = sorted(pcs_dir.rglob("*.lean"))
    return [path for path in paths if "Generated" not in path.parts]


def _hash_byte_parts(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"\n---\n".join(parts)).hexdigest()
    return f"sha256:{digest}"


def compute_pfcore_kernel_hash() -> str:
    """Hash canonical bytes of lean/PFCore/*.lean kernel sources (excludes Generated/)."""
    parts = [path.read_bytes() for path in pfcore_kernel_lean_paths()]
    return _hash_byte_parts(parts)


def compute_lean_environment_hash(*, include_pcs: bool = False) -> str:
    """Hash Lean toolchain, lake project files, and PF-Core kernel Lean sources."""
    lean_root = repo_root() / "lean"
    parts: list[bytes] = []
    toolchain = lean_root / "lean-toolchain"
    if toolchain.is_file():
        parts.append(toolchain.read_bytes())
    for rel in ("lakefile.lean", "lake-manifest.json"):
        path = lean_root / rel
        if path.is_file():
            parts.append(path.read_bytes())
    for path in pfcore_kernel_lean_paths():
        parts.append(path.read_bytes())
    if include_pcs:
        for path in pcs_kernel_lean_paths():
            parts.append(path.read_bytes())
    return _hash_byte_parts(parts)


def compute_lean_environment_hash_from_bundle(
    bundle_dir: Path,
    kernel_manifest: Mapping[str, Any],
) -> str:
    """Hash Lean environment using only files copied into a release bundle."""
    parts: list[bytes] = []
    for rel in ("lean-toolchain", "lean/lean-toolchain"):
        path = bundle_dir / rel
        if path.is_file():
            parts.append(path.read_bytes())
            break
    for rel in ("lean/lakefile.lean", "lean/lake-manifest.json"):
        path = bundle_dir / rel
        if path.is_file():
            parts.append(path.read_bytes())
    entries = kernel_manifest.get("files")
    if isinstance(entries, list):
        for entry in sorted(entries, key=lambda item: str(item.get("path") or "")):
            if not isinstance(entry, dict):
                continue
            rel_path = str(entry.get("path") or "")
            path = bundle_dir / "kernel" / rel_path
            if path.is_file():
                parts.append(path.read_bytes())
    if not parts:
        raise ValueError("bundle missing lean environment files for hash computation")
    return _hash_byte_parts(parts)


def proof_term_ref_from_path(path: Path) -> str:
    root = repo_root()
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
