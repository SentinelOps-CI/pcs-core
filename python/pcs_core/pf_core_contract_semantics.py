"""Machine-readable PFCoreContract.v0 field semantics layers (lean | runtime | out_of_scope)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

SEMANTICS_LAYERS = frozenset({"lean", "runtime", "out_of_scope"})

# Canonical mapping from docs/pf-core/contract-semantics.md (bare field names).
DEFAULT_FIELD_LAYERS: dict[str, str] = {
    "require_capability": "lean",
    "require_effect": "lean",
    "require_tenant_match": "lean",
    "require_role": "runtime",
    "require_policy_ref": "runtime",
    "require_evidence_ref": "runtime",
    "require_decision": "lean",
    "require_event_safe": "lean",
    "require_trace_safe": "lean",
}

CONTRACT_SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "pre": (
        "require_capability",
        "require_effect",
        "require_tenant_match",
        "require_role",
        "require_policy_ref",
        "require_evidence_ref",
    ),
    "post": ("require_decision", "require_event_safe"),
    "invariant": ("require_trace_safe",),
}


@dataclass(frozen=True)
class SemanticsLayerIssue:
    code: str
    message: str
    path: str | None = None


def _field_active(block: Mapping[str, Any] | None, field: str) -> bool:
    if not isinstance(block, dict):
        return False
    value = block.get(field)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return bool(value.strip())
    return True


def contract_fields_in_use(contract: Mapping[str, Any]) -> dict[str, str]:
    """Return bare field names present with non-empty values, mapped to their section."""
    active: dict[str, str] = {}
    for section, fields in CONTRACT_SECTION_FIELDS.items():
        block = contract.get(section)
        for field in fields:
            if _field_active(block if isinstance(block, dict) else None, field):
                active[field] = section
    return active


def default_semantics_layer_for_contract(contract: Mapping[str, Any]) -> dict[str, str]:
    """Derive semantics_layer entries for fields referenced by pre/post/invariant."""
    return {
        field: DEFAULT_FIELD_LAYERS.get(field, "runtime")
        for field in contract_fields_in_use(contract)
    }


def resolve_semantics_layer(contract: Mapping[str, Any]) -> dict[str, str]:
    """Effective semantics_layer map (explicit entries merged with defaults for active fields)."""
    explicit = contract.get("semantics_layer")
    resolved = default_semantics_layer_for_contract(contract)
    if isinstance(explicit, dict):
        for key, value in explicit.items():
            if isinstance(key, str) and isinstance(value, str):
                resolved[key] = value
    return resolved


def validate_semantics_layer(contract: Mapping[str, Any]) -> list[SemanticsLayerIssue]:
    """Validate semantics_layer consistency with contract body and canonical defaults."""
    issues: list[SemanticsLayerIssue] = []
    explicit = contract.get("semantics_layer")
    active = contract_fields_in_use(contract)

    if explicit is not None and not isinstance(explicit, dict):
        issues.append(
            SemanticsLayerIssue(
                "SemanticsLayerInvalid",
                "semantics_layer must be an object when present",
                "semantics_layer",
            )
        )
        return issues

    if isinstance(explicit, dict):
        for key, value in explicit.items():
            if not isinstance(key, str) or not isinstance(value, str):
                issues.append(
                    SemanticsLayerIssue(
                        "SemanticsLayerInvalid",
                        "semantics_layer entries must be string keys and string values",
                        f"semantics_layer.{key}",
                    )
                )
                continue
            if value not in SEMANTICS_LAYERS:
                issues.append(
                    SemanticsLayerIssue(
                        "SemanticsLayerInvalid",
                        f"semantics_layer[{key!r}] must be one of lean, runtime, out_of_scope",
                        f"semantics_layer.{key}",
                    )
                )
            if key not in DEFAULT_FIELD_LAYERS:
                issues.append(
                    SemanticsLayerIssue(
                        "SemanticsLayerUnknownField",
                        f"unknown semantics_layer field {key!r}",
                        f"semantics_layer.{key}",
                    )
                )
            elif key in active and value != DEFAULT_FIELD_LAYERS[key]:
                issues.append(
                    SemanticsLayerIssue(
                        "SemanticsLayerMismatch",
                        f"semantics_layer[{key!r}]={value!r} conflicts with canonical layer "
                        f"{DEFAULT_FIELD_LAYERS[key]!r}",
                        f"semantics_layer.{key}",
                    )
                )
            elif key not in active:
                issues.append(
                    SemanticsLayerIssue(
                        "SemanticsLayerOrphanField",
                        f"semantics_layer[{key!r}] set but {key} is absent from pre/post/invariant",
                        f"semantics_layer.{key}",
                    )
                )

    for field in active:
        layer = resolve_semantics_layer(contract).get(field, "runtime")
        if layer == "out_of_scope":
            issues.append(
                SemanticsLayerIssue(
                    "SemanticsLayerOutOfScopeFieldSet",
                    f"contract sets {field} but semantics_layer marks it out_of_scope",
                    field,
                )
            )

    return issues


def field_semantics_layer(contract: Mapping[str, Any], *, section: str, field: str) -> str:
    """Return discharge layer for a contract field (section is used for documentation only)."""
    _ = section
    return resolve_semantics_layer(contract).get(field, DEFAULT_FIELD_LAYERS.get(field, "runtime"))


_LEAN_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")

OUT_OF_SCOPE_RATIONALES: dict[str, str] = {
    "require_capability": "Marked out_of_scope; not discharged by Lean or runtime checkers",
    "require_effect": "Marked out_of_scope; not discharged by Lean or runtime checkers",
    "require_tenant_match": "Marked out_of_scope; not discharged by Lean or runtime checkers",
    "require_role": "Not mapped to Lean ContractDecide; runtime role membership only",
    "require_policy_ref": "Not mapped to Lean ContractDecide; runtime contract_refs membership only",
    "require_evidence_ref": "Not mapped to Lean ContractDecide; runtime evidence_refs membership only",
    "require_decision": "Marked out_of_scope; not discharged by Lean or runtime checkers",
    "require_event_safe": "Marked out_of_scope; not discharged by Lean or runtime checkers",
    "require_trace_safe": "Marked out_of_scope; not discharged by Lean or runtime checkers",
}


def _lean_ident(prefix: str, raw: str) -> str:
    slug = _LEAN_IDENT_RE.sub("_", raw).strip("_")
    if not slug or slug[0].isdigit():
        slug = f"{prefix}_{slug or 'x'}"
    return slug


def runtime_check_id(contract_id: str, *, section: str, field: str) -> str:
    """Stable runtime check identifier recorded on certificates and projections."""
    return f"{contract_id}.{section}.{field}"


def lean_theorem_for_contract_field(
    contract_id: str,
    *,
    section: str,
    field: str,
    event_id: str | None,
) -> str | None:
    """Deterministic Lean theorem name that discharges a lean-layer contract field."""
    _ = field
    base = _lean_ident("contract", contract_id)
    if section == "invariant":
        return f"concrete_trace_satisfies_{base}"
    if event_id is None:
        return None
    event_name = _lean_ident("ev", event_id)
    if section == "pre":
        return f"concrete_contract_pre_{base}_{event_name}"
    if section == "post":
        return f"concrete_contract_post_{base}_{event_name}"
    return None


def normalize_contract_field_value(value: Any) -> str | bool | None:
    """Normalize an active contract field value for projection records."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def materialize_contract_semantics_layer(
    contract: Mapping[str, Any],
    *,
    contract_id: str,
    referencing_event_ids: list[str] | tuple[str, ...] | None = None,
    effective_layers: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Materialize effective semantics_layer records after defaults are applied.

    Each active contract field records section, field name, normalized value,
    effective layer, and the applicable Lean theorem / runtime check id /
    out-of-scope rationale.
    """
    layers = dict(effective_layers) if effective_layers is not None else resolve_semantics_layer(contract)
    event_ids = [str(item) for item in (referencing_event_ids or []) if str(item)]
    primary_event = event_ids[0] if event_ids else None
    records: list[dict[str, Any]] = []
    for field, section in sorted(
        contract_fields_in_use(contract).items(),
        key=lambda item: (item[1], item[0]),
    ):
        block = contract.get(section)
        raw_value = block.get(field) if isinstance(block, Mapping) else None
        layer = layers.get(field, DEFAULT_FIELD_LAYERS.get(field, "runtime"))
        record: dict[str, Any] = {
            "section": section,
            "field": field,
            "normalized_value": normalize_contract_field_value(raw_value),
            "effective_layer": layer,
        }
        if layer == "lean":
            theorem = lean_theorem_for_contract_field(
                contract_id,
                section=section,
                field=field,
                event_id=primary_event,
            )
            if theorem:
                record["lean_theorem"] = theorem
        elif layer == "runtime":
            record["runtime_check_id"] = runtime_check_id(
                contract_id, section=section, field=field
            )
        elif layer == "out_of_scope":
            record["out_of_scope_rationale"] = OUT_OF_SCOPE_RATIONALES.get(
                field,
                "Field marked out_of_scope for this contract",
            )
        records.append(record)
    return records


def _trace_events(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = trace.get("events")
    if not isinstance(events, list):
        return []
    typed = [event for event in events if isinstance(event, dict)]
    return sorted(typed, key=lambda item: int(item.get("sequence") or 0))


def _trace_has_contract_refs(trace: Mapping[str, Any]) -> bool:
    for event in _trace_events(trace):
        refs = event.get("contract_refs")
        if isinstance(refs, list) and refs:
            return True
    return False


def build_contract_semantics_checked(
    trace: Mapping[str, Any],
    contracts: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Summarize contract fields checked in Lean vs runtime from semantics_layer."""
    lean_checks: list[str] = []
    runtime_checks: list[str] = []
    if not _trace_has_contract_refs(trace):
        return {"lean": lean_checks, "runtime": runtime_checks}

    seen: set[str] = set()
    for event in _trace_events(trace):
        refs = event.get("contract_refs")
        if not isinstance(refs, list):
            continue
        for ref in refs:
            contract_id = str(ref)
            contract = contracts.get(contract_id)
            if contract is None:
                runtime_checks.append(f"missing_contract:{contract_id}")
                continue
            for field, section in contract_fields_in_use(contract).items():
                cert_key = f"{contract_id}.{section}.{field}"
                if cert_key in seen:
                    continue
                seen.add(cert_key)
                layer = field_semantics_layer(contract, section=section, field=field)
                if layer == "lean":
                    lean_checks.append(cert_key)
                elif layer == "runtime":
                    runtime_checks.append(cert_key)

    return {
        "lean": sorted(set(lean_checks)),
        "runtime": sorted(set(runtime_checks)),
    }
