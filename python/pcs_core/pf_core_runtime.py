"""Deterministic PF-Core runtime observation compiler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from pcs_core.hash import SIGNATURE_FIELD, canonical_hash
from pcs_core.pf_core_catalog import (
    CAPABILITY_CATALOG,
    EFFECT_KINDS,
    ROLE_CAPABILITY_MAP,
    TOOL_NAME_MAP,
)
from pcs_core.validate import ValidationError, validate_schema

GENESIS_HASH = "sha256:" + "0" * 64

TOOL_USE_DEFAULT_CERTIFICATE_MODE = "TraceSafeRCertificate"


def is_tool_use_trace(
    trace: Mapping[str, Any],
    *,
    trace_path: Any | None = None,
) -> bool:
    """Return True when trace policy targets tool-use certificate mode."""
    required = trace.get("required_certificate_mode")
    if required == TOOL_USE_DEFAULT_CERTIFICATE_MODE:
        return True
    workflow_id = str(trace.get("workflow_id") or "")
    if workflow_id.startswith("agent_tool_use"):
        return True
    if trace_path is not None:
        from pathlib import Path

        path = trace_path if isinstance(trace_path, Path) else Path(str(trace_path))
        if (path.parent / "tool_use_trace.json").is_file():
            return True
    return False

AUTHORIZATION_TO_DECISION = {
    "authorized": "allow",
    "rejected": "deny",
    "unknown": "deny",
    "policy_missing": "deny",
}

RUNTIME_CHECKED_CLAIM_CLASSES = frozenset({"SchemaValidated", "RuntimeChecked", "OutOfScope"})
TRACE_CLAIM_CLASSES = frozenset(
    {
        "SchemaValidated",
        "RuntimeChecked",
        "ReplayValidated",
        "AssumptionDeclared",
        "OutOfScope",
    }
)
CERTIFICATE_CLAIM_CLASSES = frozenset(
    {
        "SchemaValidated",
        "RuntimeChecked",
        "CertificateChecked",
        "LeanKernelChecked",
        "ReplayValidated",
        "AssumptionDeclared",
        "OutOfScope",
    }
)
LEAN_CLAIM_CLASSES = frozenset({"LeanKernelChecked"})


@dataclass(frozen=True)
class PFCoreRuntimeError(Exception):
    code: str
    message: str
    path: str | None = None

    def __str__(self) -> str:
        if self.path:
            return f"{self.code}: {self.message} (at {self.path})"
        return f"{self.code}: {self.message}"


class UnknownCapability(PFCoreRuntimeError):
    def __init__(self, capability: str, path: str | None = None):
        super().__init__("UnknownCapability", f"unknown capability: {capability}", path)


class UnknownEffect(PFCoreRuntimeError):
    def __init__(self, effect: str, path: str | None = None):
        super().__init__("UnknownEffect", f"unknown effect: {effect}", path)


class MissingPrincipal(PFCoreRuntimeError):
    def __init__(self, message: str = "principal required", path: str | None = None):
        super().__init__("MissingPrincipal", message, path)


class AmbiguousMapping(PFCoreRuntimeError):
    def __init__(self, message: str, path: str | None = None):
        super().__init__("AmbiguousMapping", message, path)


class HandoffAuthorityExpansion(PFCoreRuntimeError):
    def __init__(self, capability: str, path: str | None = None):
        super().__init__(
            "HandoffAuthorityExpansion",
            f"delegated capability exceeds source authority: {capability}",
            path,
        )


class ClaimClassOverclaim(PFCoreRuntimeError):
    def __init__(self, claim_class: str, path: str | None = None):
        super().__init__(
            "ClaimClassOverclaim",
            f"claim_class {claim_class!r} exceeds available assurance",
            path,
        )


class CapabilityEffectMismatch(PFCoreRuntimeError):
    def __init__(self, capability: str, effect: str, path: str | None = None):
        super().__init__(
            "CapabilityEffectMismatch",
            f"capability {capability!r} effect_kind {effect!r} not listed in action effects",
            path,
        )


class DroppedDeniedEvent(PFCoreRuntimeError):
    def __init__(self, event_id: str, path: str | None = None):
        super().__init__(
            "DroppedDeniedEvent",
            f"denied event {event_id!r} missing from compiled trace",
            path,
        )


class ResourceScopeViolation(PFCoreRuntimeError):
    def __init__(self, uri: str, pattern: str, path: str | None = None):
        super().__init__(
            "ResourceScopeViolation",
            f"resource {uri!r} outside declared pattern {pattern!r}",
            path,
        )


def validate_denied_events_preserved(
    tool_use_trace: Mapping[str, Any],
    pfcore_trace: Mapping[str, Any],
) -> None:
    tool_calls = tool_use_trace.get("tool_calls")
    if not isinstance(tool_calls, list):
        return
    events = pfcore_trace.get("events")
    if not isinstance(events, list):
        raise DroppedDeniedEvent("<missing-events>", "events")
    compiled_ids = {str(event.get("event_id")) for event in events if isinstance(event, dict)}
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        auth = str(tool_call.get("authorization_status") or "")
        if AUTHORIZATION_TO_DECISION.get(auth, "deny") != "deny":
            continue
        event_id = str(tool_call.get("event_id") or "")
        if event_id and event_id not in compiled_ids:
            raise DroppedDeniedEvent(event_id, "events")


def _require_schema_valid(data: Mapping[str, Any], artifact_type: str) -> None:
    errors = validate_schema(dict(data), artifact_type)
    if errors:
        raise ValidationError(f"Schema validation failed for {artifact_type}", errors=errors)


def normalize_hash(value: str) -> str:
    if value.startswith("sha256:") and len(value) == 71:
        return value
    if len(value) == 64 and all(c in "0123456789abcdef" for c in value):
        return f"sha256:{value}"
    raise PFCoreRuntimeError("InvalidHash", f"invalid hash value: {value!r}")


def compute_event_hash(event: Mapping[str, Any]) -> str:
    payload = {
        key: value for key, value in event.items() if key not in ("event_hash", SIGNATURE_FIELD)
    }
    return canonical_hash(payload)


def compute_trace_hash(trace: Mapping[str, Any]) -> str:
    payload = {
        key: value for key, value in trace.items() if key not in ("trace_hash", SIGNATURE_FIELD)
    }
    return canonical_hash(payload)


def expand_principal_capabilities(principal: Mapping[str, Any]) -> list[str]:
    """Expand roles and direct capabilities into an explicit capability id list."""
    ids: list[str] = []
    for role in principal.get("roles", []):
        role = str(role)
        if role in ROLE_CAPABILITY_MAP:
            for cap_id in ROLE_CAPABILITY_MAP[role]:
                if cap_id not in ids:
                    ids.append(cap_id)
        elif role.startswith("cap:") and role not in ids:
            ids.append(role)
    for cap_id in principal.get("capabilities", []):
        cap_id = str(cap_id)
        if cap_id not in ids:
            ids.append(cap_id)
    return ids


def principal_capabilities_explicit(principal: Mapping[str, Any]) -> bool:
    """True when principal.capabilities matches role expansion (Lean HasCapability alignment)."""
    explicit = {str(cap) for cap in principal.get("capabilities", [])}
    return explicit == set(expand_principal_capabilities(principal))


_allowed_capability_ids = expand_principal_capabilities


def _validate_capability(capability: Mapping[str, Any], *, path: str) -> dict[str, str]:
    cap_id = str(capability.get("capability_id") or "")
    if cap_id not in CAPABILITY_CATALOG:
        raise UnknownCapability(cap_id or "<missing>", path)
    catalog = CAPABILITY_CATALOG[cap_id]
    effect_kind = str(capability.get("effect_kind") or "")
    if effect_kind not in EFFECT_KINDS:
        raise UnknownEffect(effect_kind or "<missing>", f"{path}.effect_kind")
    if catalog["effect_kind"] != effect_kind:
        raise AmbiguousMapping(
            f"capability {cap_id} maps to {catalog['effect_kind']}, not {effect_kind}",
            f"{path}.effect_kind",
        )
    return dict(catalog)


def _validate_effects(effects: list[Any], *, path: str) -> list[dict[str, str]]:
    if not effects:
        raise UnknownEffect("<missing>", path)
    validated: list[dict[str, str]] = []
    for index, effect in enumerate(effects):
        if not isinstance(effect, dict):
            raise UnknownEffect("<invalid>", f"{path}[{index}]")
        kind = str(effect.get("effect_kind") or "")
        if kind not in EFFECT_KINDS:
            raise UnknownEffect(kind or "<missing>", f"{path}[{index}].effect_kind")
        validated.append({"effect_kind": kind})
    return validated


def _validate_action(action: Mapping[str, Any], *, path: str = "action") -> dict[str, Any]:
    capability = action.get("capability")
    if not isinstance(capability, dict):
        raise UnknownCapability("<missing>", f"{path}.capability")
    cap = _validate_capability(capability, path=f"{path}.capability")
    effects = action.get("effects")
    if not isinstance(effects, list):
        raise UnknownEffect("<missing>", f"{path}.effects")
    validated_effects = _validate_effects(effects, path=f"{path}.effects")
    reads = action.get("reads")
    writes = action.get("writes")
    if not isinstance(reads, list) or not isinstance(writes, list):
        raise PFCoreRuntimeError("InvalidAction", "reads and writes must be arrays", path)
    normalized = {
        "action_id": str(action.get("action_id") or ""),
        "tool_name": str(action.get("tool_name") or ""),
        "capability": {
            "capability_id": cap["capability_id"],
            "effect_kind": cap["effect_kind"],
            "resource_pattern": cap["resource_pattern"],
        },
        "effects": validated_effects,
        "reads": [dict(item) for item in reads if isinstance(item, dict)],
        "writes": [dict(item) for item in writes if isinstance(item, dict)],
        "input_hash": str(action.get("input_hash") or GENESIS_HASH),
        "output_hash": str(action.get("output_hash") or GENESIS_HASH),
    }
    validate_resource_scope(normalized, path=path)
    return normalized


def _validate_principal(principal: Any, *, path: str = "principal") -> dict[str, Any]:
    if not isinstance(principal, dict):
        raise MissingPrincipal(path=path)
    principal_id = principal.get("principal_id")
    if not isinstance(principal_id, str) or not principal_id.strip():
        raise MissingPrincipal("principal_id required", path)
    normalized = {
        "principal_id": principal_id,
        "principal_kind": str(principal.get("principal_kind") or "agent"),
        "tenant": str(principal.get("tenant") or ""),
        "roles": [str(role) for role in principal.get("roles", [])],
        "capabilities": [str(cap) for cap in principal.get("capabilities", [])],
    }
    normalized["capabilities"] = expand_principal_capabilities(normalized)
    return normalized


def _assert_claim_class_allowed(claim_class: str, *, proof_ref: str | None = None) -> None:
    if claim_class not in TRACE_CLAIM_CLASSES:
        raise ClaimClassOverclaim(claim_class, "claim_class")
    proof_term_ref = proof_ref
    if claim_class in LEAN_CLAIM_CLASSES and not proof_term_ref:
        raise ClaimClassOverclaim(claim_class, "claim_class")
    if claim_class == "CertificateChecked":
        raise ClaimClassOverclaim(claim_class, "claim_class")


def validate_action_effects_known(action: Mapping[str, Any], *, path: str = "action") -> None:
    effects = action.get("effects")
    if not isinstance(effects, list):
        raise UnknownEffect("<missing>", f"{path}.effects")
    _validate_effects(effects, path=f"{path}.effects")


def validate_action_capabilities_known(action: Mapping[str, Any], *, path: str = "action") -> None:
    capability = action.get("capability")
    if not isinstance(capability, dict):
        raise UnknownCapability("<missing>", f"{path}.capability")
    _validate_capability(capability, path=f"{path}.capability")


def validate_action_capability_effects(action: Mapping[str, Any], *, path: str = "action") -> None:
    capability = action.get("capability")
    if not isinstance(capability, dict):
        raise UnknownCapability("<missing>", f"{path}.capability")
    cap = _validate_capability(capability, path=f"{path}.capability")
    effects = action.get("effects")
    if not isinstance(effects, list):
        raise UnknownEffect("<missing>", f"{path}.effects")
    validated_effects = _validate_effects(effects, path=f"{path}.effects")
    cap_effect = cap["effect_kind"]
    if not any(effect["effect_kind"] == cap_effect for effect in validated_effects):
        raise CapabilityEffectMismatch(cap["capability_id"], cap_effect, f"{path}.effects")


def _finalize_event(
    *,
    trace_id: str,
    event_id: str,
    sequence: int,
    timestamp: str,
    principal: dict[str, Any],
    action: dict[str, Any],
    decision: str,
    decision_reason: str,
    contract_refs: list[str],
    evidence_refs: list[str],
    previous_event_hash: str,
    source_repo: str,
    source_commit: str,
) -> dict[str, Any]:
    if decision not in {"allow", "deny"}:
        raise PFCoreRuntimeError("InvalidDecision", f"unknown decision {decision!r}", "decision")
    event: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreEvent.v0",
        "event_id": event_id,
        "trace_id": trace_id,
        "sequence": sequence,
        "timestamp": timestamp,
        "principal": principal,
        "action": action,
        "decision": decision,
        "decision_reason": decision_reason,
        "contract_refs": list(contract_refs),
        "evidence_refs": list(evidence_refs),
        "previous_event_hash": normalize_hash(previous_event_hash),
        "event_hash": GENESIS_HASH,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "signature_or_digest": GENESIS_HASH,
    }
    event["event_hash"] = compute_event_hash(event)
    event["signature_or_digest"] = event["event_hash"]
    return event


def _glob_match_chars_fuel(
    fuel: int,
    pattern: list[str],
    uri: list[str],
) -> bool:
    """Lean ``globMatchCharsFuel`` subset: ``*`` wildcards only (no ``?`` / ``[]``)."""
    if fuel == 0:
        return False
    if not pattern:
        return not uri
    if pattern[0] == "*":
        return _glob_match_chars_fuel(fuel - 1, pattern[1:], uri) or (
            bool(uri) and _glob_match_chars_fuel(fuel - 1, pattern, uri[1:])
        )
    if not uri or pattern[0] != uri[0]:
        return False
    return _glob_match_chars_fuel(fuel - 1, pattern[1:], uri[1:])


def _glob_match(pattern: str, uri: str) -> bool:
    """Match URI against catalog glob patterns (aligned with Lean ``globMatch``)."""
    pat = list(pattern)
    text = list(uri)
    fuel = len(pat) + len(text) + 1
    return _glob_match_chars_fuel(fuel, pat, text)


def resource_matches_pattern(uri: str, pattern: str) -> bool:
    """Return True when ``uri`` matches capability ``resource_pattern``."""
    if pattern == "*":
        return True
    return _glob_match(pattern, uri)


def validate_resource_scope(action: Mapping[str, Any], *, path: str = "action") -> None:
    capability = action.get("capability")
    if not isinstance(capability, dict):
        return
    pattern = str(capability.get("resource_pattern") or "")
    if not pattern:
        return
    for key in ("reads", "writes"):
        resources = action.get(key)
        if not isinstance(resources, list):
            continue
        for index, resource in enumerate(resources):
            if not isinstance(resource, dict):
                continue
            uri = str(resource.get("uri") or "")
            if uri and not resource_matches_pattern(uri, pattern):
                raise ResourceScopeViolation(uri, pattern, f"{path}.{key}[{index}].uri")


def _same_tenant(principal: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    tenant = str(principal.get("tenant") or "")
    for key in ("reads", "writes"):
        resources = action.get(key)
        if not isinstance(resources, list):
            continue
        for resource in resources:
            if isinstance(resource, dict) and str(resource.get("tenant") or "") != tenant:
                return False
    return True


def _event_cross_tenant_safe(
    principal: Mapping[str, Any],
    action: Mapping[str, Any],
    decision: str,
) -> bool:
    """Mirror ``EventCrossTenantSafe``: in-tenant footprint or explicit deny."""
    if decision == "deny":
        return True
    return _same_tenant(principal, action)


def validate_cross_tenant_safety(trace: Mapping[str, Any]) -> list[str]:
    """Return cross-tenant safety violations (``TraceCrossTenantSafe`` mirror).

    Every event must be in-tenant or explicitly denied. Unlike
    ``validate_tenant_isolation``, denied cross-tenant attempts satisfy this check.
    Does not claim full global non-interference or covert-channel freedom.
    """
    errors: list[str] = []
    events = trace.get("events")
    if not isinstance(events, list):
        return ["TraceInvalid: events must be an array"]

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        base = f"events[{index}]"
        principal = event.get("principal")
        action = event.get("action")
        decision = str(event.get("decision") or "")
        if not isinstance(principal, dict) or not isinstance(action, dict):
            errors.append(f"CrossTenantSafe: {base} missing principal or action")
            continue
        if not _event_cross_tenant_safe(principal, action, decision):
            errors.append(
                f"CrossTenantSafe: cross-tenant allow at {base} "
                f"(principal tenant {principal.get('tenant')!r})"
            )
    return errors


def _low_event_for_tenant(tenant: str, event: Mapping[str, Any]) -> bool:
    """Mirror ``LowEvent``: allowed and principal tenant equals observer tenant."""
    if str(event.get("decision") or "") != "allow":
        return False
    principal = event.get("principal")
    if not isinstance(principal, dict):
        return False
    return str(principal.get("tenant") or "") == tenant


def trace_projection_for_tenant(trace: Mapping[str, Any], tenant: str) -> list[Mapping[str, Any]]:
    """Oldest-first low-visible events for ``tenant`` (``TraceProjection`` mirror)."""
    projection: list[Mapping[str, Any]] = []
    events = trace.get("events")
    if not isinstance(events, list):
        return projection
    for event in events:
        if isinstance(event, dict) and _low_event_for_tenant(tenant, event):
            projection.append(event)
    return projection


def validate_observational_non_interference(
    trace: Mapping[str, Any],
    tenant_low: str,
    tenant_high: str,
) -> list[str]:
    """Return observational NI violations (``NonInterference`` / ``nonInterferenceD`` mirror).

    Conservative projection-based check only. Does not claim covert-channel freedom,
    timing indistinguishability, or scheduler-level global non-interference.
    """
    if tenant_low == tenant_high:
        return []

    errors: list[str] = []
    events = trace.get("events")
    if not isinstance(events, list):
        return ["TraceInvalid: events must be an array"]

    projection = trace_projection_for_tenant(trace, tenant_low)
    for index, event in enumerate(projection):
        if not _low_event_for_tenant(tenant_low, event):
            errors.append(
                f"NonInterference: projected event at projection[{index}] is not "
                f"LowEvent for tenant {tenant_low!r}"
            )

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        principal = event.get("principal")
        if not isinstance(principal, dict):
            continue
        if str(principal.get("tenant") or "") != tenant_high:
            continue
        if _low_event_for_tenant(tenant_low, event):
            errors.append(
                f"NonInterference: high-tenant event at events[{index}] is low-visible "
                f"to tenant {tenant_low!r}"
            )
    return errors


def validate_observational_non_interference_all_pairs(trace: Mapping[str, Any]) -> list[str]:
    """Check observational NI for every distinct tenant pair present in the trace."""
    tenants: list[str] = []
    events = trace.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            principal = event.get("principal")
            if isinstance(principal, dict):
                tenant = str(principal.get("tenant") or "")
                if tenant and tenant not in tenants:
                    tenants.append(tenant)
    errors: list[str] = []
    for tenant_low in tenants:
        for tenant_high in tenants:
            if tenant_low == tenant_high:
                continue
            errors.extend(validate_observational_non_interference(trace, tenant_low, tenant_high))
    return errors


def validate_tenant_isolation(trace: Mapping[str, Any]) -> list[str]:
    """Return tenant isolation violations for a PFCoreTrace.v0 (empty if scoped).

    Checks that every event's principal tenant matches all read/write resource
    tenants. This is a conservative runtime mirror of ``TraceTenantScoped`` /
    ``EventTenantScoped`` in Lean; it does not claim full cross-tenant
    non-interference.
    """
    errors: list[str] = []
    events = trace.get("events")
    if not isinstance(events, list):
        return ["TraceInvalid: events must be an array"]

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        base = f"events[{index}]"
        principal = event.get("principal")
        action = event.get("action")
        if not isinstance(principal, dict) or not isinstance(action, dict):
            errors.append(f"TenantIsolation: {base} missing principal or action")
            continue
        tenant = str(principal.get("tenant") or "")
        if not tenant:
            errors.append(f"TenantIsolation: {base}.principal.tenant is empty")
            continue
        if not _same_tenant(principal, action):
            errors.append(
                f"TenantIsolation: cross-tenant resource access at {base} "
                f"(principal tenant {tenant!r})"
            )
    return errors


def validate_denied_observations_preserved(
    observations: list[Any] | list[Mapping[str, Any]],
    events: list[Mapping[str, Any]],
) -> None:
    """Ensure denied runtime observations appear as deny events in a compiled trace."""
    compiled: dict[str, Mapping[str, Any]] = {}
    for event in events:
        if isinstance(event, dict):
            compiled[str(event.get("event_id") or "")] = event
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            continue
        if str(observation.get("decision") or "") != "deny":
            continue
        event_id = str(observation.get("event_id") or "")
        if not event_id:
            raise DroppedDeniedEvent("<missing-event-id>", f"observations[{index}].event_id")
        event = compiled.get(event_id)
        if event is None:
            raise DroppedDeniedEvent(event_id, "events")
        if str(event.get("decision") or "") != "deny":
            raise DroppedDeniedEvent(event_id, f"events[{event_id}].decision")


def _observation_sequence(observation: Mapping[str, Any]) -> int:
    sequence = observation.get("sequence")
    if isinstance(sequence, int) and sequence >= 0:
        return sequence
    raise PFCoreRuntimeError(
        "InvalidObservation",
        "sequence must be a non-negative integer",
        "sequence",
    )


def _sort_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return observations ordered by ``sequence`` with stable index tie-breaking."""
    indexed = list(enumerate(observations))
    indexed.sort(key=lambda item: (_observation_sequence(item[1]), item[0]))
    return [observation for _, observation in indexed]


def compile_runtime_observation_to_event(observation: dict) -> dict:
    """Compile a schema-valid runtime observation into a PFCoreEvent.v0."""
    _require_schema_valid(observation, "PFCoreRuntimeObservation.v0")

    principal = _validate_principal(observation.get("principal"), path="principal")
    action = _validate_action(observation.get("action", {}), path="action")

    decision = str(observation.get("decision") or "")
    if decision == "allow":
        cap_id = action["capability"]["capability_id"]
        if cap_id not in _allowed_capability_ids(principal):
            decision = "deny"
        elif not _same_tenant(principal, action):
            decision = "deny"

    policy_ref = str(observation.get("policy_ref") or "").strip()
    contract_refs = [policy_ref] if policy_ref else []

    event = _finalize_event(
        trace_id=str(observation["trace_id"]),
        event_id=str(observation["event_id"]),
        sequence=_observation_sequence(observation),
        timestamp=str(observation["observed_at"]),
        principal=principal,
        action=action,
        decision=decision,
        decision_reason=str(observation.get("decision_reason") or ""),
        contract_refs=contract_refs,
        evidence_refs=[str(ref) for ref in observation.get("evidence_refs", []) if ref],
        previous_event_hash=str(observation.get("previous_event_hash") or GENESIS_HASH),
        source_repo=str(observation["source_repo"]),
        source_commit=str(observation["source_commit"]),
    )
    return event


def compile_runtime_observations_to_pfcore_trace(
    observations: list[dict[str, Any]],
    *,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    """Compile ordered runtime observations into a PFCoreTrace.v0 with chained hashes."""
    if not observations:
        raise PFCoreRuntimeError("InvalidTrace", "observations must be non-empty", "observations")

    for index, observation in enumerate(observations):
        _require_schema_valid(observation, "PFCoreRuntimeObservation.v0")

    ordered = _sort_observations(observations)
    trace_id = str(ordered[0]["trace_id"])
    for observation in ordered[1:]:
        if str(observation["trace_id"]) != trace_id:
            raise PFCoreRuntimeError(
                "InvalidTrace",
                "all observations must share trace_id",
                "trace_id",
            )

    events: list[dict[str, Any]] = []
    previous_hash = GENESIS_HASH
    for observation in ordered:
        event = compile_runtime_observation_to_event(observation)
        event = dict(event)
        event["previous_event_hash"] = previous_hash
        event["event_hash"] = compute_event_hash(event)
        event["signature_or_digest"] = event["event_hash"]
        events.append(event)
        previous_hash = event["event_hash"]

    validate_denied_observations_preserved(ordered, events)

    claim_class = "RuntimeChecked"
    _assert_claim_class_allowed(claim_class)

    trace: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreTrace.v0",
        "trace_id": trace_id,
        "workflow_id": workflow_id or str(ordered[0].get("runtime_ref") or "observation.batch"),
        "events": events,
        "trace_hash": GENESIS_HASH,
        "policy_hash": GENESIS_HASH,
        "contract_hash": GENESIS_HASH,
        "claim_class": claim_class,
        "source_repo": str(ordered[0]["source_repo"]),
        "source_commit": str(ordered[0]["source_commit"]),
        "signature_or_digest": GENESIS_HASH,
    }
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    return trace


def _resolve_tool_mapping(tool_name: str, tool_category: str) -> tuple[str, str, str]:
    key = (tool_name, tool_category)
    if key not in TOOL_NAME_MAP:
        raise UnknownCapability(f"{tool_name}/{tool_category}", "tool_calls.tool_name")
    return TOOL_NAME_MAP[key]


def _tool_call_to_action(
    tool_call: Mapping[str, Any],
    *,
    agent_id: str,
    tenant: str,
    capabilities: list[str],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    cap_id, effect_kind, resource_pattern = _resolve_tool_mapping(
        str(tool_call["tool_name"]),
        str(tool_call["tool_category"]),
    )
    _validate_capability(
        {
            "capability_id": cap_id,
            "effect_kind": effect_kind,
            "resource_pattern": resource_pattern,
        },
        path="tool_calls.capability",
    )
    resource_uri = str(tool_call.get("resource_uri") or resource_pattern.replace("*", "default"))
    principal = {
        "principal_id": agent_id,
        "principal_kind": "agent",
        "tenant": tenant,
        "roles": ["agent"],
        "capabilities": list(capabilities),
    }
    action = {
        "action_id": f"act-{tool_call['event_id']}",
        "tool_name": str(tool_call["tool_name"]),
        "capability": {
            "capability_id": cap_id,
            "effect_kind": effect_kind,
            "resource_pattern": resource_pattern,
        },
        "effects": [{"effect_kind": effect_kind}],
        "reads": [
            {
                "resource_id": f"res-{tool_call['event_id']}",
                "uri": resource_uri,
                "tenant": tenant,
            }
        ],
        "writes": [],
        "input_hash": str(tool_call["input_hash"]),
        "output_hash": str(tool_call["output_hash"]),
    }
    auth = str(tool_call.get("authorization_status") or "")
    if auth not in AUTHORIZATION_TO_DECISION:
        raise PFCoreRuntimeError(
            "InvalidDecision",
            f"unknown authorization_status {auth!r}",
            "tool_calls.authorization_status",
        )
    decision = AUTHORIZATION_TO_DECISION[auth]
    if decision == "allow" and cap_id not in _allowed_capability_ids(principal):
        decision = "deny"
    elif decision == "allow" and not _same_tenant(principal, action):
        decision = "deny"
    return principal, _validate_action(action), decision


def _handoff_to_event(
    handoff: Mapping[str, Any],
    *,
    trace_id: str,
    sequence: int,
    timestamp: str,
    previous_event_hash: str,
    source_repo: str,
    source_commit: str,
    contract_refs: list[str],
) -> dict[str, Any]:
    _require_schema_valid(dict(handoff), "PFCoreHandoff.v0")
    validate_handoff_authority(handoff)
    from_principal = _validate_principal(handoff.get("from_principal"), path="from_principal")
    delegated = handoff.get("delegated_capabilities")
    if not isinstance(delegated, list) or not delegated:
        raise HandoffAuthorityExpansion("<missing>", "delegated_capabilities")
    first = delegated[0] if isinstance(delegated[0], dict) else {}
    cap_id = str(first.get("capability_id") or "cap:handoff")
    effect_kind = str(first.get("effect_kind") or "handoff.delegate")
    resource_pattern = str(first.get("resource_pattern") or "agent:*")
    to_principal = handoff.get("to_principal")
    target_id = (
        str(to_principal.get("principal_id") or "agent-unknown")
        if isinstance(to_principal, dict)
        else "agent-unknown"
    )
    action = _validate_action(
        {
            "action_id": f"act-{handoff.get('handoff_id', sequence)}",
            "tool_name": "handoff.delegate",
            "capability": {
                "capability_id": cap_id,
                "effect_kind": effect_kind,
                "resource_pattern": resource_pattern,
            },
            "effects": [{"effect_kind": effect_kind}],
            "reads": [
                {
                    "resource_id": f"res-handoff-{sequence}",
                    "uri": f"agent:{target_id}",
                    "tenant": from_principal["tenant"],
                }
            ],
            "writes": [],
            "input_hash": GENESIS_HASH,
            "output_hash": GENESIS_HASH,
        },
        path="handoffs.action",
    )
    return _finalize_event(
        trace_id=trace_id,
        event_id=str(handoff.get("handoff_id") or f"handoff-{sequence}"),
        sequence=sequence,
        timestamp=timestamp,
        principal=from_principal,
        action=action,
        decision="allow",
        decision_reason=str(handoff.get("reason") or "handoff"),
        contract_refs=list(contract_refs),
        evidence_refs=[str(ref) for ref in handoff.get("evidence_refs", []) if ref],
        previous_event_hash=previous_event_hash,
        source_repo=source_repo,
        source_commit=source_commit,
    )


def compile_tool_use_trace_to_pfcore_trace(tool_use_trace: dict) -> dict:
    """Compile a schema-valid ToolUseTrace.v0 into PFCoreTrace.v0."""
    _require_schema_valid(tool_use_trace, "ToolUseTrace.v0")

    claim_class = "RuntimeChecked"
    _assert_claim_class_allowed(claim_class)

    tool_calls = tool_use_trace.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        raise PFCoreRuntimeError("InvalidTrace", "tool_calls must be non-empty", "tool_calls")

    handoffs = tool_use_trace.get("handoffs")
    if handoffs is not None and not isinstance(handoffs, list):
        raise PFCoreRuntimeError("InvalidTrace", "handoffs must be an array", "handoffs")

    events: list[dict[str, Any]] = []
    previous_hash = GENESIS_HASH
    tenant = str(tool_calls[0].get("tenant") or "default")
    agent_id = str(tool_use_trace["agent_id"])
    policy_id = str(tool_use_trace["policy_id"])
    contract_refs = [policy_id]

    for index, tool_call in enumerate(tool_calls):
        if not isinstance(tool_call, dict):
            continue
        principal, action, decision = _tool_call_to_action(
            tool_call,
            agent_id=agent_id,
            tenant=tenant,
            capabilities=list(_allowed_capability_ids({"roles": ["agent"], "capabilities": []})),
        )
        event = _finalize_event(
            trace_id=str(tool_use_trace["trace_id"]),
            event_id=str(tool_call["event_id"]),
            sequence=index,
            timestamp=str(tool_call["timestamp"]),
            principal=principal,
            action=action,
            decision=decision,
            decision_reason=str(tool_call.get("authorization_status") or ""),
            contract_refs=list(contract_refs),
            evidence_refs=[str(ref) for ref in tool_call.get("policy_refs", []) if ref],
            previous_event_hash=previous_hash,
            source_repo=str(tool_use_trace["source_repo"]),
            source_commit=str(tool_use_trace["source_commit"]),
        )
        events.append(event)
        previous_hash = event["event_hash"]

    if isinstance(handoffs, list):
        for offset, handoff in enumerate(handoffs):
            if not isinstance(handoff, dict):
                continue
            sequence = len(events) + offset
            timestamp = str(handoff.get("timestamp") or tool_use_trace.get("completed_at") or "")
            event = _handoff_to_event(
                handoff,
                trace_id=str(tool_use_trace["trace_id"]),
                sequence=sequence,
                timestamp=timestamp,
                previous_event_hash=previous_hash,
                source_repo=str(tool_use_trace["source_repo"]),
                source_commit=str(tool_use_trace["source_commit"]),
                contract_refs=contract_refs,
            )
            events.append(event)
            previous_hash = event["event_hash"]

    denied_source = [
        str(item.get("event_id"))
        for item in tool_calls
        if isinstance(item, dict)
        and AUTHORIZATION_TO_DECISION.get(str(item.get("authorization_status")), "deny") == "deny"
    ]
    denied_compiled = [event["event_id"] for event in events if event["decision"] == "deny"]
    for event_id in denied_source:
        if event_id not in denied_compiled:
            raise DroppedDeniedEvent(event_id, "events")

    trace: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreTrace.v0",
        "trace_id": str(tool_use_trace["trace_id"]),
        "workflow_id": str(tool_use_trace["workflow_id"]),
        "events": events,
        "trace_hash": GENESIS_HASH,
        "policy_hash": str(tool_use_trace["policy_hash"]),
        "contract_hash": GENESIS_HASH,
        "claim_class": claim_class,
        "required_certificate_mode": TOOL_USE_DEFAULT_CERTIFICATE_MODE,
        "source_repo": str(tool_use_trace["source_repo"]),
        "source_commit": str(tool_use_trace["source_commit"]),
        "signature_or_digest": GENESIS_HASH,
    }
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    return trace


def validate_handoff_authority(handoff: Mapping[str, Any]) -> None:
    src = handoff.get("from_principal")
    if not isinstance(src, dict):
        raise MissingPrincipal(path="from_principal")
    allowed = set(_allowed_capability_ids(src))
    delegated = handoff.get("delegated_capabilities")
    if not isinstance(delegated, list):
        raise HandoffAuthorityExpansion("<missing>", "delegated_capabilities")
    for index, cap in enumerate(delegated):
        if not isinstance(cap, dict):
            continue
        cap_id = str(cap.get("capability_id") or "")
        if cap_id and cap_id not in allowed:
            raise HandoffAuthorityExpansion(cap_id, f"delegated_capabilities[{index}]")


def validate_event_sequence_order(
    trace: Mapping[str, Any], *, strict_gaps: bool = True
) -> list[str]:
    """Reject duplicate sequences, unsorted event arrays, and optional sequence gaps."""
    errors: list[str] = []
    events = trace.get("events")
    if not isinstance(events, list):
        return errors

    seen: set[int] = set()
    prev_seq: int | None = None
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        base = f"events[{index}]"
        sequence = event.get("sequence")
        if not isinstance(sequence, int):
            errors.append(f"EventSequenceInvalid: missing or invalid sequence at {base}")
            continue
        if sequence in seen:
            errors.append(f"EventSequenceDuplicate: duplicate sequence {sequence} at {base}")
        seen.add(sequence)
        if prev_seq is not None and sequence < prev_seq:
            errors.append(
                "EventSequenceOrderMismatch: "
                f"events not sorted by sequence at {base} "
                f"(sequence {sequence} < previous {prev_seq})"
            )
        if strict_gaps and prev_seq is not None and sequence != prev_seq + 1:
            errors.append(
                f"EventSequenceGap: gap between sequence {prev_seq} and {sequence} at {base}"
            )
        prev_seq = sequence
    return errors


def validate_pfcore_trace_hash_chain(trace: dict) -> list[str]:
    """Return semantic hash-chain errors for a PFCoreTrace.v0 (empty if valid)."""
    errors: list[str] = []
    events = trace.get("events")
    if not isinstance(events, list):
        return ["TraceInvalid: events must be an array"]

    previous = normalize_hash(GENESIS_HASH)
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"EventInvalid: events[{index}] must be an object")
            continue
        base = f"events[{index}]"
        try:
            prev_field = normalize_hash(str(event.get("previous_event_hash") or ""))
        except PFCoreRuntimeError:
            errors.append(f"EventHashMismatch: invalid previous_event_hash at {base}")
            continue
        if prev_field != previous:
            errors.append(
                "EventHashMismatch: "
                f"previous_event_hash mismatch at {base} "
                f"(expected {previous}, got {prev_field})"
            )
        try:
            actual_hash = normalize_hash(str(event.get("event_hash") or ""))
        except PFCoreRuntimeError:
            errors.append(f"EventHashMismatch: invalid event_hash at {base}")
            continue
        expected_hash = compute_event_hash(event)
        if actual_hash != expected_hash:
            errors.append(
                "EventHashMismatch: "
                f"event_hash mismatch at {base} (expected {expected_hash}, got {actual_hash})"
            )
        previous = actual_hash

    trace_hash = trace.get("trace_hash")
    if trace_hash is None:
        return errors
    if not isinstance(trace_hash, str):
        errors.append("TraceHashMismatch: missing trace_hash")
    else:
        try:
            actual_trace_hash = normalize_hash(trace_hash)
        except PFCoreRuntimeError:
            errors.append("TraceHashMismatch: invalid trace_hash")
        else:
            expected_trace_hash = compute_trace_hash(trace)
            if actual_trace_hash != expected_trace_hash:
                errors.append(
                    "TraceHashMismatch: "
                    f"trace_hash mismatch (expected {expected_trace_hash}, got {actual_trace_hash})"
                )

    claim_class = trace.get("claim_class")
    if isinstance(claim_class, str):
        try:
            _assert_claim_class_allowed(
                claim_class,
                proof_ref=trace.get("proof_ref") or trace.get("proof_term_ref"),
            )
        except ClaimClassOverclaim as exc:
            errors.append(f"{exc.code}: {exc.message}")

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        action = event.get("action")
        if not isinstance(action, dict):
            continue
        try:
            validate_resource_scope(action, path=f"events[{index}].action")
        except ResourceScopeViolation as exc:
            errors.append(f"{exc.code}: {exc.message} (at {exc.path})")

    return errors
