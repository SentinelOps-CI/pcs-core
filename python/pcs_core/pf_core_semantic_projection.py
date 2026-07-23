"""PF-Core semantic projection: Lean-relevant fields extracted from a trace.

The projection is hashed independently of the full PFCoreTrace.v0 envelope and is
the preferred input for concrete Lean term emission. A restricted Lean JSON
decoder is deferred; Python/codegen remains the trusted bridge for v0.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.obligation_extraction_errors import ObligationExtractionError


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
        from pcs_core.pf_core_catalog import CAPABILITY_CATALOG

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
    }


def _project_contract(contract_id: str, contract: Mapping[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {"contract_id": contract_id}
    for key in ("pre", "post", "invariant", "field_semantics"):
        value = contract.get(key)
        if isinstance(value, Mapping):
            projected[key] = dict(value)
    return projected


def build_semantic_projection(
    trace: Mapping[str, Any],
    *,
    certificate_mode: str,
    trace_path: Path | None = None,
    handoffs: list[Mapping[str, Any]] | None = None,
    contracts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract Lean-relevant fields and bind an independent projection hash."""
    events_raw = trace.get("events")
    if not isinstance(events_raw, list):
        events_raw = []
    typed_events = [event for event in events_raw if isinstance(event, Mapping)]
    typed_events = sorted(typed_events, key=lambda item: int(item.get("sequence") or 0))
    projected_events = [
        _project_event(event, index=index) for index, event in enumerate(typed_events)
    ]

    if handoffs is None:
        from pcs_core.pf_core_lean_codegen import collect_handoffs_near_trace

        handoffs = collect_handoffs_near_trace(trace, trace_path=trace_path)
    projected_handoffs = [
        _project_handoff(item, index=index)
        for index, item in enumerate(handoffs)
        if isinstance(item, Mapping)
    ]

    if contracts is None:
        from pcs_core.pf_core_lean_codegen import collect_contracts_for_trace

        contracts = collect_contracts_for_trace(trace, trace_path=trace_path)
    projected_contracts = [
        _project_contract(contract_id, contract)
        for contract_id, contract in sorted(contracts.items())
        if isinstance(contract, Mapping)
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
