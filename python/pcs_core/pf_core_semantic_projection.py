"""PF-Core semantic projection: Lean-relevant fields extracted from a trace.

The projection is hashed independently of the full PFCoreTrace.v0 envelope and is
the preferred input for concrete Lean term emission. A restricted Lean JSON
decoder is deferred; Python/codegen remains the trusted bridge for v0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.obligation_extraction_errors import ObligationExtractionError
from pcs_core.pf_core_catalog import CAPABILITY_CATALOG, EFFECT_KINDS

if TYPE_CHECKING:
    from pcs_core.pf_core_resolved_evidence import PFCoreResolvedEvidence


def _require_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObligationExtractionError(
            code="InvalidSemanticProjection",
            message=f"{field} must be an object",
            field_path=field,
        )
    return value


def _project_principal(principal: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    _require_mapping(principal, field=field)
    roles = principal.get("roles")
    capabilities = principal.get("capabilities")
    return {
        "principal_id": str(principal.get("principal_id") or ""),
        "tenant": str(principal.get("tenant") or ""),
        "roles": [str(role) for role in roles] if isinstance(roles, list) else [],
        "capabilities": (
            [str(cap) for cap in capabilities] if isinstance(capabilities, list) else []
        ),
    }


def _project_resource(resource: Mapping[str, Any]) -> dict[str, str]:
    return {
        "uri": str(resource.get("uri") or ""),
        "tenant": str(resource.get("tenant") or ""),
    }


def _project_action(action: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    _require_mapping(action, field=field)
    capability = action.get("capability")
    cap_id = ""
    cap_effect = "file.read"
    resource_pattern = ""
    if isinstance(capability, Mapping):
        cap_id = str(capability.get("capability_id") or "")
        cap_effect = str(capability.get("effect_kind") or "file.read")
        resource_pattern = str(capability.get("resource_pattern") or "")
    if not resource_pattern and cap_id:
        catalog_entry = CAPABILITY_CATALOG.get(cap_id)
        if isinstance(catalog_entry, Mapping):
            resource_pattern = str(catalog_entry.get("resource_pattern") or "")
    effects_raw = action.get("effects")
    effects: list[str] = []
    if isinstance(effects_raw, list):
        for item in effects_raw:
            if isinstance(item, Mapping):
                kind = str(item.get("effect_kind") or "")
                if kind:
                    effects.append(kind)
            elif isinstance(item, str) and item:
                effects.append(item)
    if not effects:
        effects = [cap_effect]
    reads_raw = action.get("reads")
    writes_raw = action.get("writes")
    reads = (
        [_project_resource(item) for item in reads_raw if isinstance(item, Mapping)]
        if isinstance(reads_raw, list)
        else []
    )
    writes = (
        [_project_resource(item) for item in writes_raw if isinstance(item, Mapping)]
        if isinstance(writes_raw, list)
        else []
    )
    return {
        "action_id": str(action.get("action_id") or ""),
        "tool_name": str(action.get("tool_name") or ""),
        "capability_id": cap_id,
        "capability_effect_kind": cap_effect,
        "resource_pattern": resource_pattern,
        "effects": effects,
        "reads": reads,
        "writes": writes,
    }


def _project_event(event: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    principal = event.get("principal")
    action = event.get("action")
    if not isinstance(principal, Mapping) or not isinstance(action, Mapping):
        raise ObligationExtractionError(
            code="InvalidSemanticProjection",
            message="event requires principal and action objects",
            field_path=f"events[{index}]",
        )
    projected: dict[str, Any] = {
        "sequence": int(event.get("sequence") or index),
        "event_id": str(event.get("event_id") or index),
        "decision": str(event.get("decision") or "allow"),
        "principal": _project_principal(principal, field=f"events[{index}].principal"),
        "action": _project_action(action, field=f"events[{index}].action"),
    }
    refs = event.get("contract_refs")
    if isinstance(refs, list) and refs:
        projected["contract_refs"] = [str(ref) for ref in refs if str(ref)]
    return projected


def _project_delegated_capabilities(
    raw: Any,
    *,
    field: str,
) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise ObligationExtractionError(
            code="EmptyProjectedDelegation",
            message="handoff delegated_capabilities must be a non-empty array",
            field_path=field,
        )
    projected: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        item_field = f"{field}[{index}]"
        if not isinstance(item, Mapping):
            raise ObligationExtractionError(
                code="InvalidSemanticProjection",
                message="delegated capability must be an object",
                field_path=item_field,
            )
        cap_id = str(item.get("capability_id") or "").strip()
        effect_kind = str(item.get("effect_kind") or "").strip()
        resource_pattern = str(item.get("resource_pattern") or "").strip()
        if not cap_id or not effect_kind or not resource_pattern:
            raise ObligationExtractionError(
                code="InvalidSemanticProjection",
                message=(
                    "delegated capability requires capability_id, effect_kind, "
                    "and resource_pattern"
                ),
                field_path=item_field,
            )
        catalog_entry = CAPABILITY_CATALOG.get(cap_id)
        if catalog_entry is None:
            raise ObligationExtractionError(
                code="UnknownDelegatedCapability",
                message=f"capability_id {cap_id!r} is not in the PF-Core catalog",
                field_path=item_field,
            )
        if effect_kind not in EFFECT_KINDS:
            raise ObligationExtractionError(
                code="UnknownDelegatedEffectKind",
                message=f"effect_kind {effect_kind!r} is not in the PF-Core catalog",
                field_path=item_field,
            )
        expected_effect = str(catalog_entry.get("effect_kind") or "")
        expected_pattern = str(catalog_entry.get("resource_pattern") or "")
        if effect_kind != expected_effect:
            raise ObligationExtractionError(
                code="DelegatedCapabilityCatalogMismatch",
                message=(
                    f"capability {cap_id!r} effect_kind {effect_kind!r} does not match "
                    f"catalog {expected_effect!r}"
                ),
                field_path=item_field,
            )
        if resource_pattern != expected_pattern:
            raise ObligationExtractionError(
                code="DelegatedCapabilityCatalogMismatch",
                message=(
                    f"capability {cap_id!r} resource_pattern {resource_pattern!r} does not "
                    f"match catalog {expected_pattern!r}"
                ),
                field_path=item_field,
            )
        projected.append(
            {
                "capability_id": cap_id,
                "effect_kind": effect_kind,
                "resource_pattern": resource_pattern,
            }
        )
    return projected


def _project_handoff(handoff: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    from_p = handoff.get("from_principal")
    to_p = handoff.get("to_principal")
    if not isinstance(from_p, Mapping) or not isinstance(to_p, Mapping):
        raise ObligationExtractionError(
            code="InvalidSemanticProjection",
            message="handoff requires from_principal and to_principal",
            field_path=f"handoffs[{index}]",
        )
    return {
        "handoff_id": str(handoff.get("handoff_id") or f"handoff_{index}"),
        "from_principal": _project_principal(from_p, field=f"handoffs[{index}].from_principal"),
        "to_principal": _project_principal(to_p, field=f"handoffs[{index}].to_principal"),
        "delegated_capabilities": _project_delegated_capabilities(
            handoff.get("delegated_capabilities"),
            field=f"handoffs[{index}].delegated_capabilities",
        ),
    }


def _project_contract(
    contract_id: str,
    contract: Mapping[str, Any],
    *,
    referencing_event_ids: list[str] | None = None,
    effective_layers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    from pcs_core.pf_core_contract_semantics import materialize_contract_semantics_layer

    projected: dict[str, Any] = {"contract_id": contract_id}
    for key in ("pre", "post", "invariant"):
        value = contract.get(key)
        if isinstance(value, Mapping):
            projected[key] = dict(value)
    projected["semantics_layer"] = materialize_contract_semantics_layer(
        contract,
        contract_id=contract_id,
        referencing_event_ids=referencing_event_ids,
        effective_layers=effective_layers,
    )
    return projected


def _project_effect_frame(frame: Mapping[str, Any]) -> dict[str, Any]:
    """Project Lean-relevant fields from an independently declared effect frame."""
    from pcs_core.pf_core_resolved_evidence import effect_frame_allowed_kinds

    kinds = effect_frame_allowed_kinds(frame)
    for kind in kinds:
        if kind not in EFFECT_KINDS:
            raise ObligationExtractionError(
                code="UnknownEffectKind",
                message=f"effect frame lists unknown effect kind {kind!r}",
                field_path="effect_frame.allowed_effect_kinds",
            )
    projected: dict[str, Any] = {
        "frame_id": str(frame.get("frame_id") or ""),
        "allowed_effect_kinds": kinds,
        "frame_scope_policy": "global",
    }
    workflow_id = str(frame.get("workflow_id") or "").strip()
    if workflow_id:
        projected["workflow_id"] = workflow_id
    contract_id = str(frame.get("contract_id") or "").strip()
    if contract_id:
        projected["contract_id"] = contract_id
    policy_ref = str(frame.get("source_policy_ref") or "").strip()
    if policy_ref:
        projected["source_policy_ref"] = policy_ref
    constraints_raw = frame.get("resource_constraints")
    if isinstance(constraints_raw, list) and constraints_raw:
        constraints: list[dict[str, str]] = []
        for item in constraints_raw:
            if not isinstance(item, Mapping):
                continue
            effect_kind = str(item.get("effect_kind") or "").strip()
            pattern = str(item.get("resource_pattern") or "").strip()
            if effect_kind and pattern:
                constraints.append(
                    {"effect_kind": effect_kind, "resource_pattern": pattern}
                )
        if constraints:
            projected["resource_constraints"] = constraints
    return projected


def _project_operational_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Project a rich operational State for FramePreservedCertificate binding."""
    principal = state.get("active_principal")
    if not isinstance(principal, Mapping):
        principal = {}
    resource_frame_raw = state.get("resource_frame")
    resources: list[dict[str, str]] = []
    if isinstance(resource_frame_raw, list):
        for item in resource_frame_raw:
            if not isinstance(item, Mapping):
                continue
            resources.append(
                {
                    "uri": str(item.get("uri") or ""),
                    "tenant": str(item.get("tenant") or ""),
                }
            )
    caps_raw = state.get("capability_frame")
    capabilities = (
        [str(cap) for cap in caps_raw] if isinstance(caps_raw, list) else []
    )
    return {
        "tenant": str(state.get("tenant") or ""),
        "active_principal": {
            "principal_id": str(principal.get("principal_id") or ""),
            "tenant": str(principal.get("tenant") or ""),
            "roles": (
                [str(role) for role in principal.get("roles") or []]
                if isinstance(principal.get("roles"), list)
                else []
            ),
            "capabilities": (
                [str(cap) for cap in principal.get("capabilities") or []]
                if isinstance(principal.get("capabilities"), list)
                else []
            ),
        },
        "resource_frame": resources,
        "capability_frame": capabilities,
    }


def _contract_referencing_event_ids(
    events: list[Mapping[str, Any]],
    contract_id: str,
) -> list[str]:
    ids: list[str] = []
    for index, event in enumerate(events):
        refs = event.get("contract_refs")
        if not isinstance(refs, list):
            continue
        if contract_id not in {str(ref) for ref in refs}:
            continue
        event_id = str(event.get("event_id") or index)
        if event_id:
            ids.append(event_id)
    return ids


def build_semantic_projection(
    trace: Mapping[str, Any],
    *,
    certificate_mode: str,
    trace_path: Path | None = None,
    handoffs: list[Mapping[str, Any]] | None = None,
    contracts: Mapping[str, Mapping[str, Any]] | None = None,
    resolved_evidence: PFCoreResolvedEvidence | None = None,
) -> dict[str, Any]:
    """Extract Lean-relevant fields and bind an independent projection hash.

    When ``resolved_evidence`` is provided, handoffs/contracts come from that
    snapshot only — no secondary directory rediscovery.
    """
    del trace_path  # retained for call-site compatibility; discovery is via resolved evidence
    events_raw = trace.get("events")
    if not isinstance(events_raw, list):
        events_raw = []
    typed_events = [event for event in events_raw if isinstance(event, Mapping)]
    typed_events = sorted(typed_events, key=lambda item: int(item.get("sequence") or 0))
    projected_events = [
        _project_event(event, index=index) for index, event in enumerate(typed_events)
    ]

    effective_layers_by_id: Mapping[str, Mapping[str, str]] = {}
    contract_items: list[tuple[str, Mapping[str, Any]]]
    if resolved_evidence is not None:
        handoffs = resolved_evidence.handoff_artifacts
        # Preserve explicit selection order (do not silently reorder/pick siblings).
        contract_items = [
            (item.contract_id, item.artifact) for item in resolved_evidence.contracts
        ]
        effective_layers_by_id = resolved_evidence.effective_contract_semantic_layers
    else:
        # Without resolved evidence, do not scan siblings. Callers must pass
        # explicit handoffs/contracts or resolve evidence first.
        if handoffs is None:
            handoffs = []
        if contracts is None:
            contracts = {}
        contract_items = [
            (contract_id, contract)
            for contract_id, contract in sorted(contracts.items())
            if isinstance(contract, Mapping)
        ]

    projected_handoffs = [
        _project_handoff(item, index=index)
        for index, item in enumerate(handoffs)
        if isinstance(item, Mapping)
    ]

    projected_contracts = [
        _project_contract(
            contract_id,
            contract,
            referencing_event_ids=_contract_referencing_event_ids(typed_events, contract_id),
            effective_layers=(
                dict(effective_layers_by_id[contract_id])
                if contract_id in effective_layers_by_id
                else None
            ),
        )
        for contract_id, contract in contract_items
        if isinstance(contract, Mapping)
    ]

    projected_effect_frame: dict[str, Any] | None = None
    if resolved_evidence is not None and resolved_evidence.effect_frame is not None:
        projected_effect_frame = _project_effect_frame(resolved_evidence.effect_frame)

    projected_initial_state: dict[str, Any] | None = None
    projected_transition_states: list[dict[str, Any]] | None = None
    if (
        resolved_evidence is not None
        and resolved_evidence.initial_state is not None
        and certificate_mode == "FramePreservedCertificate"
    ):
        projected_initial_state = _project_operational_state(resolved_evidence.initial_state)
        projected_transition_states = [
            _project_operational_state(state) for state in resolved_evidence.transition_states
        ]

    body: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreSemanticProjection.v0",
        "trace_id": str(trace.get("trace_id") or "trace"),
        "certificate_mode": certificate_mode,
        "events": projected_events,
    }
    if projected_handoffs:
        body["handoffs"] = projected_handoffs
    if projected_contracts:
        body["contracts"] = projected_contracts
    if projected_effect_frame is not None:
        body["effect_frame"] = projected_effect_frame
    if projected_initial_state is not None:
        body["initial_state"] = projected_initial_state
    if projected_transition_states is not None:
        body["transition_states"] = projected_transition_states

    # Hash without projection_hash, then bind.
    projection_hash = canonical_hash(body)
    body["projection_hash"] = projection_hash
    return body


def projection_to_codegen_trace(projection: Mapping[str, Any]) -> dict[str, Any]:
    """Rehydrate a minimal trace-shaped object for existing Lean term emitters."""
    events: list[dict[str, Any]] = []
    for projected in projection.get("events") or []:
        if not isinstance(projected, Mapping):
            continue
        action = projected.get("action")
        principal = projected.get("principal")
        if not isinstance(action, Mapping) or not isinstance(principal, Mapping):
            continue
        effects = [
            {"effect_kind": kind} for kind in (action.get("effects") or []) if isinstance(kind, str)
        ]
        event: dict[str, Any] = {
            "sequence": projected.get("sequence"),
            "event_id": projected.get("event_id"),
            "decision": projected.get("decision"),
            "principal": dict(principal),
            "action": {
                "action_id": action.get("action_id"),
                "tool_name": action.get("tool_name"),
                "capability": {
                    "capability_id": action.get("capability_id"),
                    "effect_kind": action.get("capability_effect_kind"),
                    "resource_pattern": action.get("resource_pattern") or "",
                },
                "effects": effects,
                "reads": list(action.get("reads") or []),
                "writes": list(action.get("writes") or []),
            },
        }
        refs = projected.get("contract_refs")
        if isinstance(refs, list) and refs:
            event["contract_refs"] = list(refs)
        events.append(event)

    result: dict[str, Any] = {
        "trace_id": projection.get("trace_id"),
        "events": events,
        "required_certificate_mode": projection.get("certificate_mode"),
    }
    return result


def projection_handoffs(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = projection.get("handoffs")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def projection_contracts(projection: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = projection.get("contracts")
    if not isinstance(raw, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        contract_id = str(item.get("contract_id") or "")
        if not contract_id:
            continue
        out[contract_id] = dict(item)
    return out


def projection_contract_ids(projection: Mapping[str, Any]) -> list[str]:
    """Contract IDs in projection order (selection order when resolved evidence was used)."""
    raw = projection.get("contracts")
    if not isinstance(raw, list):
        return []
    ids: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        contract_id = str(item.get("contract_id") or "")
        if contract_id:
            ids.append(contract_id)
    return ids


def extract_lean_delegated_capability_sequences(lean_source: str) -> list[list[str]]:
    """Parse ``delegatedCapabilities := [...]`` sequences from generated Lean source."""
    import re

    sequences: list[list[str]] = []
    pattern = re.compile(
        r"delegatedCapabilities\s*:=\s*(\[[^\]]*\])",
        re.MULTILINE,
    )
    string_lit = re.compile(r'"((?:\\.|[^"\\])*)"')
    for match in pattern.finditer(lean_source):
        expr = match.group(1).strip()
        if expr == "[]":
            sequences.append([])
            continue
        ids: list[str] = []
        for raw in string_lit.findall(expr):
            ids.append(json.loads(f'"{raw}"'))
        sequences.append(ids)
    return sequences
