"""Single-resolution PF-Core evidence for lean-check and certificate construction.

``PFCoreResolvedEvidence`` is resolved once at the start of ``run_pfcore_lean_check``
and threaded into every downstream stage. Downstream stages must not rediscover
handoffs, contracts, or policy frames via directory scans.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from pcs_core.pf_core_contract_semantics import resolve_semantics_layer

EVIDENCE_SELECTION_POLICY = "explicit_ids"
EVIDENCE_SELECTION_POLICY_VERSION = "v0"
EVIDENCE_SELECTION_FILENAME = "evidence_selection.json"


class EvidenceResolutionError(ValueError):
    """Raised when evidence selection or artifact binding cannot be resolved."""


@dataclass(frozen=True)
class ResolvedHandoff:
    handoff_id: str
    path: Path | None
    artifact: Mapping[str, Any]


@dataclass(frozen=True)
class ResolvedContract:
    contract_id: str
    path: Path | None
    artifact: Mapping[str, Any]


@dataclass(frozen=True)
class PFCoreResolvedEvidence:
    """Immutable snapshot of all evidence selected for a lean-check run."""

    source_trace_path: Path
    canonical_trace: Mapping[str, Any]
    certificate_mode: str
    selected_events: tuple[Mapping[str, Any], ...]
    handoffs: tuple[ResolvedHandoff, ...]
    contracts: tuple[ResolvedContract, ...]
    effective_contract_semantic_layers: Mapping[str, Mapping[str, str]]
    effect_frame: Mapping[str, Any] | None
    effect_frame_path: Path | None
    initial_state: Mapping[str, Any] | None
    transition_states: tuple[Mapping[str, Any], ...]
    source_file_digests: Mapping[str, str]
    evidence_selection_policy: str
    evidence_selection_policy_version: str
    selected_handoff_ids: tuple[str, ...]
    selected_contract_ids: tuple[str, ...]

    @property
    def handoff_artifacts(self) -> list[dict[str, Any]]:
        return [dict(item.artifact) for item in self.handoffs]

    @property
    def handoff_paths(self) -> list[Path]:
        return [item.path for item in self.handoffs if item.path is not None]

    @property
    def contracts_by_id(self) -> dict[str, dict[str, Any]]:
        return {item.contract_id: dict(item.artifact) for item in self.contracts}

    @property
    def contract_paths(self) -> list[Path]:
        return [item.path for item in self.contracts if item.path is not None]


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def load_evidence_selection(
    trace: Mapping[str, Any],
    *,
    trace_path: Path | None = None,
) -> dict[str, Any]:
    """Load evidence-selection policy from the trace or a sibling JSON file."""
    embedded = trace.get("evidence_selection")
    if isinstance(embedded, Mapping):
        return dict(embedded)
    if trace_path is not None:
        sibling = trace_path.parent / EVIDENCE_SELECTION_FILENAME
        if sibling.is_file():
            try:
                data = json.loads(sibling.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise EvidenceResolutionError(
                    f"unreadable evidence selection file {sibling}: {exc}"
                ) from exc
            if isinstance(data, dict):
                return data
    return {}


def _selected_ids(selection: Mapping[str, Any], key: str) -> tuple[str, ...] | None:
    raw = selection.get(key)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise EvidenceResolutionError(f"evidence_selection.{key} must be an array")
    ids: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        value = str(item or "").strip()
        if not value:
            raise EvidenceResolutionError(
                f"evidence_selection.{key}[{index}] must be a non-empty string"
            )
        if value in seen:
            raise EvidenceResolutionError(
                f"evidence_selection.{key} contains duplicate id {value!r}"
            )
        seen.add(value)
        ids.append(value)
    return tuple(ids)


def _selected_effect_frame_id(selection: Mapping[str, Any]) -> str | None:
    """v0: one global frame id (``effect_frame_id``). Reject multi-id arrays."""
    if "effect_frame_ids" in selection:
        raise EvidenceResolutionError(
            "evidence_selection.effect_frame_ids is not supported in v0; "
            "use effect_frame_id for the single global frame"
        )
    raw = selection.get("effect_frame_id")
    if raw is None:
        return None
    value = str(raw or "").strip()
    if not value:
        raise EvidenceResolutionError(
            "evidence_selection.effect_frame_id must be a non-empty string"
        )
    return value


def _index_effect_frame_candidates(
    *,
    trace_path: Path | None,
) -> dict[str, tuple[dict[str, Any], Path]]:
    """Map frame_id -> (artifact, path) from sibling PFCoreEffectFrame.v0 files."""
    indexed: dict[str, tuple[dict[str, Any], Path]] = {}
    if trace_path is None:
        return indexed
    case_dir = trace_path.parent
    for path in sorted(case_dir.glob("*.json")):
        if path.name == trace_path.name:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("artifact_type") != "PFCoreEffectFrame.v0":
            continue
        frame_id = str(data.get("frame_id") or "").strip()
        if not frame_id:
            raise EvidenceResolutionError(
                f"effect frame artifact {path} missing frame_id"
            )
        if frame_id in indexed:
            raise EvidenceResolutionError(
                f"ambiguous effect frame id {frame_id!r}: multiple candidate artifacts"
            )
        indexed[frame_id] = (dict(data), path.resolve())
    return indexed


def effect_frame_allowed_kinds(frame: Mapping[str, Any]) -> list[str]:
    """Normalized allowed effect-kind sequence from a declared frame artifact."""
    raw = frame.get("allowed_effect_kinds")
    if not isinstance(raw, list):
        return []
    kinds: list[str] = []
    for item in raw:
        value = str(item or "").strip()
        if value:
            kinds.append(value)
    return kinds


def action_effect_kinds(action: Mapping[str, Any]) -> list[str]:
    """Declared effect kinds on an action (order-preserving)."""
    raw = action.get("effects")
    if not isinstance(raw, list):
        return []
    kinds: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            kind = str(item.get("effect_kind") or "").strip()
            if kind:
                kinds.append(kind)
        elif isinstance(item, str) and item.strip():
            kinds.append(item.strip())
    return kinds


def action_effects_in_declared_frame(
    action: Mapping[str, Any],
    frame: Mapping[str, Any],
) -> bool:
    """True iff every action effect kind is permitted by the independent frame."""
    allowed = set(effect_frame_allowed_kinds(frame))
    if not allowed:
        return False
    for kind in action_effect_kinds(action):
        if kind not in allowed:
            return False
    return True


def assert_actions_in_declared_frame(
    *,
    frame: Mapping[str, Any],
    events: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> None:
    """Fail closed when any event action declares an effect omitted from the frame."""
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            continue
        action = event.get("action")
        if not isinstance(action, Mapping):
            continue
        if action_effects_in_declared_frame(action, frame):
            continue
        event_id = str(event.get("event_id") or index)
        missing = sorted(
            set(action_effect_kinds(action)) - set(effect_frame_allowed_kinds(frame))
        )
        raise EvidenceResolutionError(
            f"action effects not in declared frame for event {event_id!r}: "
            f"undeclared effect kinds {missing!r}"
        )


def _resource_structural_key(resource: Mapping[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    """Lean ``Resource`` DecidableEq key: uri, tenant, labels."""
    labels_raw = resource.get("labels")
    labels: tuple[str, ...]
    if isinstance(labels_raw, list):
        labels = tuple(str(item) for item in labels_raw)
    else:
        labels = ()
    return (
        str(resource.get("uri") or ""),
        str(resource.get("tenant") or ""),
        labels,
    )


def insert_resource(
    frame: list[Mapping[str, Any]],
    resource: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Mirror Lean ``insertResource`` (prepend when absent)."""
    key = _resource_structural_key(resource)
    for existing in frame:
        if _resource_structural_key(existing) == key:
            return [dict(item) for item in frame]
    return [dict(resource), *[dict(item) for item in frame]]


def expand_resource_frame(
    frame: list[Mapping[str, Any]],
    action: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Mirror Lean ``expandResourceFrame`` over ``reads ++ writes``."""
    reads = action.get("reads")
    writes = action.get("writes")
    footprint: list[Mapping[str, Any]] = []
    if isinstance(reads, list):
        footprint.extend(item for item in reads if isinstance(item, Mapping))
    if isinstance(writes, list):
        footprint.extend(item for item in writes if isinstance(item, Mapping))
    result: list[dict[str, Any]] = [dict(item) for item in frame]
    for resource in footprint:
        result = insert_resource(result, resource)
    return result


def initial_state_from_principal(principal: Mapping[str, Any]) -> dict[str, Any]:
    """Mirror Lean ``initialState`` (empty resource frame)."""
    caps = principal.get("capabilities")
    capability_frame = (
        [str(cap) for cap in caps] if isinstance(caps, list) else []
    )
    return {
        "tenant": str(principal.get("tenant") or ""),
        "active_principal": dict(principal),
        "resource_frame": [],
        "capability_frame": capability_frame,
    }


def step_state(
    state: Mapping[str, Any],
    event: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Mirror Lean ``stepState``: deny is identity; allow succeeds or returns ``None``.

    Returning ``None`` is the operational failure that ``applyEvent`` would silently
    collapse to a no-op. FramePreservedCertificate must reject that path.
    """
    decision = str(event.get("decision") or "")
    if decision == "deny":
        return {
            "tenant": str(state.get("tenant") or ""),
            "active_principal": dict(state.get("active_principal") or {}),
            "resource_frame": [dict(item) for item in (state.get("resource_frame") or [])],
            "capability_frame": [str(cap) for cap in (state.get("capability_frame") or [])],
        }
    if decision != "allow":
        return None
    principal = event.get("principal")
    action = event.get("action")
    if not isinstance(principal, Mapping) or not isinstance(action, Mapping):
        return None
    from pcs_core.lean_check import action_allowed_d

    if not action_allowed_d(principal, action):
        return None
    if str(state.get("tenant") or "") != str(principal.get("tenant") or ""):
        return None
    caps = principal.get("capabilities")
    capability_frame = (
        [str(cap) for cap in caps] if isinstance(caps, list) else []
    )
    prior_frame = state.get("resource_frame")
    frame_list: list[Mapping[str, Any]] = (
        [item for item in prior_frame if isinstance(item, Mapping)]
        if isinstance(prior_frame, list)
        else []
    )
    return {
        "tenant": str(principal.get("tenant") or ""),
        "active_principal": dict(principal),
        "resource_frame": expand_resource_frame(frame_list, action),
        "capability_frame": capability_frame,
    }


def simulate_frame_preserved_transitions(
    events: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Compute initial + post-states; reject allow events that would become applyEvent no-ops."""
    if not events:
        raise EvidenceResolutionError(
            "FramePreservedCertificate requires ≥1 event and concrete initial state"
        )
    first = events[0]
    if not isinstance(first, Mapping):
        raise EvidenceResolutionError(
            "FramePreservedCertificate requires concrete initial state (event principal)"
        )
    principal = first.get("principal")
    if not isinstance(principal, Mapping):
        raise EvidenceResolutionError(
            "FramePreservedCertificate requires concrete initial state (event principal)"
        )
    state = initial_state_from_principal(principal)
    initial = dict(state)
    posts: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise EvidenceResolutionError(
                f"FramePreservedCertificate event at index {index} is not an object"
            )
        event_id = str(event.get("event_id") or index)
        decision = str(event.get("decision") or "")
        next_state = step_state(state, event)
        if next_state is None:
            raise EvidenceResolutionError(
                f"stepState failed for allow event {event_id!r}: "
                "operational transition is none (applyEvent no-op rejected; "
                "cross-tenant or actionAllowed gate)"
            )
        if decision == "deny":
            # Identity must hold exactly for deny semantics.
            if (
                next_state.get("tenant") != state.get("tenant")
                or next_state.get("active_principal") != state.get("active_principal")
                or next_state.get("resource_frame") != state.get("resource_frame")
                or next_state.get("capability_frame") != state.get("capability_frame")
            ):
                raise EvidenceResolutionError(
                    f"deny identity violated for event {event_id!r}"
                )
        posts.append(next_state)
        state = next_state
    return initial, tuple(posts)


def compute_transition_chain_digest(
    *,
    initial_state: Mapping[str, Any],
    transition_states: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    event_ids: list[str] | tuple[str, ...],
) -> str:
    """Digest binding initial state, event order, and proved post-states."""
    from pcs_core.hash import canonical_hash

    payload = {
        "initial_state": dict(initial_state),
        "event_ids": list(event_ids),
        "transition_states": [dict(state) for state in transition_states],
    }
    return canonical_hash(payload)


def _index_handoff_candidates(
    candidates: list[dict[str, Any]],
    *,
    trace_path: Path | None,
) -> dict[str, tuple[dict[str, Any], Path | None]]:
    """Map handoff_id -> (artifact, path). Path is best-effort from sibling files."""
    indexed: dict[str, tuple[dict[str, Any], Path | None]] = {}
    path_by_id: dict[str, Path] = {}
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
                handoff_id = str(data.get("handoff_id") or "")
                if handoff_id:
                    path_by_id[handoff_id] = path.resolve()

    for item in candidates:
        handoff_id = str(item.get("handoff_id") or "")
        if not handoff_id:
            raise EvidenceResolutionError("handoff candidate missing handoff_id")
        if handoff_id in indexed:
            raise EvidenceResolutionError(
                f"ambiguous handoff id {handoff_id!r}: multiple candidate artifacts"
            )
        indexed[handoff_id] = (dict(item), path_by_id.get(handoff_id))
    return indexed


def _index_contract_paths(
    contracts: Mapping[str, Mapping[str, Any]],
    *,
    trace_path: Path | None,
) -> dict[str, Path]:
    path_by_id: dict[str, Path] = {}
    if trace_path is None:
        return path_by_id
    search_dirs = [trace_path.parent]
    nested = trace_path.parent / "contracts"
    if nested.is_dir():
        search_dirs.append(nested)
    for directory in search_dirs:
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            if data.get("artifact_type") != "PFCoreContract.v0":
                continue
            contract_id = str(data.get("contract_id") or "")
            if contract_id and contract_id in contracts:
                path_by_id[contract_id] = path.resolve()
    return path_by_id


def _referenced_contract_ids(trace: Mapping[str, Any]) -> set[str]:
    from pcs_core.pf_core_lean_codegen import trace_events

    refs: set[str] = set()
    for event in trace_events(trace):
        raw = event.get("contract_refs")
        if isinstance(raw, list):
            for item in raw:
                value = str(item or "").strip()
                if value:
                    refs.add(value)
    return refs


def resolve_pf_core_evidence(
    trace: Mapping[str, Any],
    *,
    trace_path: Path,
    certificate_mode: str,
    selection: Mapping[str, Any] | None = None,
) -> PFCoreResolvedEvidence:
    """Resolve handoffs/contracts/events once for the given mode and selection policy."""
    from pcs_core.pf_core_lean_codegen import (
        collect_contracts_for_trace,
        collect_handoffs_near_trace,
        trace_events,
    )

    resolved_path = trace_path.resolve()
    if not resolved_path.is_file():
        raise EvidenceResolutionError(f"trace file not found: {resolved_path}")

    selection_obj = (
        dict(selection)
        if selection is not None
        else load_evidence_selection(trace, trace_path=resolved_path)
    )
    policy = str(selection_obj.get("policy") or EVIDENCE_SELECTION_POLICY)
    policy_version = str(
        selection_obj.get("policy_version") or EVIDENCE_SELECTION_POLICY_VERSION
    )
    selected_handoff_ids = _selected_ids(selection_obj, "handoff_ids")
    selected_contract_ids = _selected_ids(selection_obj, "contract_ids")
    selected_effect_frame_id = _selected_effect_frame_id(selection_obj)

    # Handoffs: never auto-accept every sibling. Explicit IDs only.
    candidates = collect_handoffs_near_trace(trace, trace_path=resolved_path)
    candidate_index = _index_handoff_candidates(candidates, trace_path=resolved_path)
    if selected_handoff_ids is None:
        if certificate_mode == "HandoffSafeCertificate":
            raise EvidenceResolutionError(
                "HandoffSafeCertificate requires evidence_selection.handoff_ids "
                "(explicit handoff binding; sibling auto-scan is not accepted)"
            )
        handoff_id_order: tuple[str, ...] = ()
    else:
        handoff_id_order = selected_handoff_ids

    resolved_handoffs: list[ResolvedHandoff] = []
    for handoff_id in handoff_id_order:
        found = candidate_index.get(handoff_id)
        if found is None:
            raise EvidenceResolutionError(
                f"selected handoff id {handoff_id!r} not found near trace {resolved_path}"
            )
        artifact, path = found
        resolved_handoffs.append(
            ResolvedHandoff(
                handoff_id=handoff_id,
                path=path,
                artifact=_freeze_mapping(artifact),
            )
        )

    # Contracts: never auto-accept every sibling for ContractChecked.
    # Explicit IDs required for ContractCheckedCertificate; other modes may
    # bind referenced artifacts or an explicit selection.
    loaded_contracts = collect_contracts_for_trace(trace, trace_path=resolved_path)
    contract_paths = _index_contract_paths(loaded_contracts, trace_path=resolved_path)
    if selected_contract_ids is None:
        if certificate_mode == "ContractCheckedCertificate":
            raise EvidenceResolutionError(
                "ContractCheckedCertificate requires evidence_selection.contract_ids "
                "(explicit contract binding; sibling auto-scan is not accepted)"
            )
        referenced = _referenced_contract_ids(trace)
        if referenced:
            # contract_refs may include non-contract policy IDs on tool-use traces.
            # Bind only refs that resolve to PFCoreContract.v0 artifacts.
            contract_id_order = tuple(
                contract_id
                for contract_id in sorted(loaded_contracts)
                if contract_id in referenced
            )
        else:
            contract_id_order = ()
    else:
        contract_id_order = selected_contract_ids
        for contract_id in contract_id_order:
            if contract_id not in loaded_contracts:
                raise EvidenceResolutionError(
                    f"selected contract id {contract_id!r} not found near trace {resolved_path}"
                )

    if certificate_mode == "ContractCheckedCertificate":
        if not contract_id_order:
            raise EvidenceResolutionError(
                "ContractCheckedCertificate requires ≥1 explicitly selected contract"
            )
        referenced = _referenced_contract_ids(trace)
        missing_refs = sorted(referenced - set(contract_id_order))
        if missing_refs:
            raise EvidenceResolutionError(
                f"trace contract_refs unresolved against selected contracts: {missing_refs}"
            )
        unresolved_selected = sorted(set(contract_id_order) - set(loaded_contracts))
        if unresolved_selected:
            raise EvidenceResolutionError(
                f"selected contracts missing artifacts: {unresolved_selected}"
            )

    resolved_contracts: list[ResolvedContract] = []
    layers: dict[str, Mapping[str, str]] = {}
    for contract_id in contract_id_order:
        artifact = dict(loaded_contracts[contract_id])
        resolved_contracts.append(
            ResolvedContract(
                contract_id=contract_id,
                path=contract_paths.get(contract_id),
                artifact=_freeze_mapping(artifact),
            )
        )
        layers[contract_id] = MappingProxyType(dict(resolve_semantics_layer(artifact)))

    events = tuple(_freeze_mapping(event) for event in trace_events(trace))

    # Effect frame: one global declared frame when required / explicitly selected.
    frame_candidates = _index_effect_frame_candidates(trace_path=resolved_path)
    effect_frame_obj: Mapping[str, Any] | None = None
    effect_frame_path: Path | None = None
    if selected_effect_frame_id is None:
        if certificate_mode == "EffectFrameCertificate":
            raise EvidenceResolutionError(
                "EffectFrameCertificate requires evidence_selection.effect_frame_id "
                "(explicit independent frame binding; action.effects is not a frame)"
            )
    else:
        found_frame = frame_candidates.get(selected_effect_frame_id)
        if found_frame is None:
            raise EvidenceResolutionError(
                f"selected effect_frame_id {selected_effect_frame_id!r} not found "
                f"near trace {resolved_path}"
            )
        frame_body, frame_path = found_frame
        if str(frame_body.get("frame_scope_policy") or "") != "global":
            raise EvidenceResolutionError(
                "v0 effect frames must declare frame_scope_policy='global' "
                "(one global frame per trace)"
            )
        if certificate_mode == "EffectFrameCertificate":
            assert_actions_in_declared_frame(frame=frame_body, events=events)
        effect_frame_obj = _freeze_mapping(frame_body)
        effect_frame_path = frame_path

    digests: dict[str, str] = {str(resolved_path): _sha256_file(resolved_path)}
    for handoff in resolved_handoffs:
        if handoff.path is not None:
            digests[str(handoff.path)] = _sha256_file(handoff.path)
        else:
            payload = json.dumps(dict(handoff.artifact), sort_keys=True, separators=(",", ":"))
            digests[f"embedded:handoff:{handoff.handoff_id}"] = _sha256_bytes(
                payload.encode("utf-8")
            )
    for contract in resolved_contracts:
        if contract.path is not None:
            digests[str(contract.path)] = _sha256_file(contract.path)
        else:
            payload = json.dumps(dict(contract.artifact), sort_keys=True, separators=(",", ":"))
            digests[f"embedded:contract:{contract.contract_id}"] = _sha256_bytes(
                payload.encode("utf-8")
            )
    if effect_frame_path is not None:
        digests[str(effect_frame_path)] = _sha256_file(effect_frame_path)
    elif effect_frame_obj is not None:
        payload = json.dumps(dict(effect_frame_obj), sort_keys=True, separators=(",", ":"))
        digests[f"embedded:effect_frame:{effect_frame_obj.get('frame_id')}"] = _sha256_bytes(
            payload.encode("utf-8")
        )

    selection_path = resolved_path.parent / EVIDENCE_SELECTION_FILENAME
    if selection_path.is_file() and not isinstance(trace.get("evidence_selection"), Mapping):
        digests[str(selection_path.resolve())] = _sha256_file(selection_path)

    initial_state_obj: Mapping[str, Any] | None = None
    transition_states_tuple: tuple[Mapping[str, Any], ...] = ()
    if certificate_mode == "FramePreservedCertificate":
        initial_raw, posts_raw = simulate_frame_preserved_transitions(events)
        initial_state_obj = _freeze_mapping(initial_raw)
        transition_states_tuple = tuple(_freeze_mapping(post) for post in posts_raw)
        chain_digest = compute_transition_chain_digest(
            initial_state=initial_raw,
            transition_states=posts_raw,
            event_ids=[
                str(event.get("event_id") or index) for index, event in enumerate(events)
            ],
        )
        digests["embedded:transition_chain"] = chain_digest

    return PFCoreResolvedEvidence(
        source_trace_path=resolved_path,
        canonical_trace=_freeze_mapping(dict(trace)),
        certificate_mode=certificate_mode,
        selected_events=events,
        handoffs=tuple(resolved_handoffs),
        contracts=tuple(resolved_contracts),
        effective_contract_semantic_layers=MappingProxyType(layers),
        effect_frame=effect_frame_obj,
        effect_frame_path=effect_frame_path,
        initial_state=initial_state_obj,
        transition_states=transition_states_tuple,
        source_file_digests=MappingProxyType(digests),
        evidence_selection_policy=policy,
        evidence_selection_policy_version=policy_version,
        selected_handoff_ids=handoff_id_order,
        selected_contract_ids=contract_id_order,
    )


def transition_chain_digest(evidence: PFCoreResolvedEvidence) -> str:
    """Digest for the resolved FramePreserved transition chain."""
    digest = evidence.source_file_digests.get("embedded:transition_chain")
    if digest is None:
        raise EvidenceResolutionError("missing transition chain digest in resolved evidence")
    return digest


def effect_frame_source_digest(evidence: PFCoreResolvedEvidence) -> str:
    """Digest for the selected independent effect-frame artifact."""
    if evidence.effect_frame is None:
        raise EvidenceResolutionError("no declared effect frame in resolved evidence")
    if evidence.effect_frame_path is not None:
        key = str(evidence.effect_frame_path)
    else:
        frame_id = str(evidence.effect_frame.get("frame_id") or "")
        key = f"embedded:effect_frame:{frame_id}"
    digest = evidence.source_file_digests.get(key)
    if digest is None:
        raise EvidenceResolutionError(f"missing source digest for effect frame {key!r}")
    return digest


def delegated_capability_ids(handoff: Mapping[str, Any]) -> list[str]:
    """Exact delegated capability ID sequence from a source or projected handoff."""
    raw = handoff.get("delegated_capabilities")
    if not isinstance(raw, list):
        return []
    ids: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            cap_id = str(item.get("capability_id") or "").strip()
            if cap_id:
                ids.append(cap_id)
        elif isinstance(item, str) and item.strip():
            ids.append(item.strip())
    return ids


def assert_handoff_capability_fidelity(
    *,
    source_handoffs: list[Mapping[str, Any]],
    projected_handoffs: list[Mapping[str, Any]],
    lean_capability_sequences: list[list[str]],
) -> None:
    """Enforce source IDs = projected IDs = Lean delegatedCapabilities sequences."""
    if len(source_handoffs) != len(projected_handoffs):
        raise EvidenceResolutionError(
            "handoff fidelity: source/projected handoff counts differ "
            f"({len(source_handoffs)} != {len(projected_handoffs)})"
        )
    if len(projected_handoffs) != len(lean_capability_sequences):
        raise EvidenceResolutionError(
            "handoff fidelity: projected/Lean handoff counts differ "
            f"({len(projected_handoffs)} != {len(lean_capability_sequences)})"
        )
    for index, (source, projected, lean_ids) in enumerate(
        zip(source_handoffs, projected_handoffs, lean_capability_sequences)
    ):
        source_ids = delegated_capability_ids(source)
        projected_ids = delegated_capability_ids(projected)
        if source_ids != projected_ids:
            raise EvidenceResolutionError(
                f"handoff fidelity mismatch at index {index}: "
                f"source={source_ids!r} projected={projected_ids!r}"
            )
        if projected_ids != list(lean_ids):
            raise EvidenceResolutionError(
                f"handoff fidelity mismatch at index {index}: "
                f"projected={projected_ids!r} lean={list(lean_ids)!r}"
            )


def contract_source_file_digests(evidence: PFCoreResolvedEvidence) -> dict[str, str]:
    """Digests for selected contract source files (or embedded payloads)."""
    out: dict[str, str] = {}
    for contract in evidence.contracts:
        if contract.path is not None:
            key = str(contract.path)
        else:
            key = f"embedded:contract:{contract.contract_id}"
        digest = evidence.source_file_digests.get(key)
        if digest is None:
            raise EvidenceResolutionError(
                f"missing source digest for selected contract {contract.contract_id!r}"
            )
        out[key] = digest
    return out


def collect_contract_theorem_names(
    theorem_inventory: frozenset[str] | set[str] | list[str] | None,
) -> list[str]:
    """Concrete contract theorem names from a generated inventory."""
    if theorem_inventory is None:
        return []
    names = sorted(str(name) for name in theorem_inventory)
    prefixes = (
        "concrete_trace_satisfies_contract",
        "concrete_satisfies_contract",
        "concrete_contract_pre_",
        "concrete_contract_post_",
        "concrete_contract_checked",
    )
    return [name for name in names if name.startswith(prefixes)]


def handoff_source_file_digests(evidence: PFCoreResolvedEvidence) -> dict[str, str]:
    """Digests for selected handoff source files (or embedded payloads)."""
    out: dict[str, str] = {}
    for handoff in evidence.handoffs:
        if handoff.path is not None:
            key = str(handoff.path)
        else:
            key = f"embedded:handoff:{handoff.handoff_id}"
        digest = evidence.source_file_digests.get(key)
        if digest is None:
            raise EvidenceResolutionError(
                f"missing source digest for selected handoff {handoff.handoff_id!r}"
            )
        out[key] = digest
    return out


def collect_handoff_theorem_names(
    theorem_inventory: frozenset[str] | set[str] | list[str] | None,
) -> list[str]:
    """Concrete handoff theorem names from a generated inventory."""
    if theorem_inventory is None:
        return []
    names = sorted(str(name) for name in theorem_inventory)
    return [
        name
        for name in names
        if name == "concrete_handoff_safe" or name.startswith("concrete_handoff_safe_")
    ]


def compute_handoff_evidence_digest(
    *,
    selected_handoff_ids: tuple[str, ...] | list[str],
    handoff_source_file_digests: Mapping[str, str],
    handoff_theorem_names: list[str] | tuple[str, ...],
) -> str:
    """Digest binding selected handoffs, source digests, and theorems."""
    from pcs_core.hash import canonical_hash

    payload = {
        "selected_handoff_ids": list(selected_handoff_ids),
        "handoff_source_file_digests": dict(sorted(handoff_source_file_digests.items())),
        "handoff_theorem_names": list(handoff_theorem_names),
    }
    return canonical_hash(payload)


def compute_contract_evidence_digest(
    *,
    selected_contract_ids: tuple[str, ...] | list[str],
    contract_source_file_digests: Mapping[str, str],
    effective_layers: Mapping[str, Mapping[str, str]],
    contract_theorem_names: list[str] | tuple[str, ...],
) -> str:
    """Digest binding selected contracts, source digests, layers, and theorems."""
    from pcs_core.hash import canonical_hash

    payload = {
        "selected_contract_ids": list(selected_contract_ids),
        "contract_source_file_digests": dict(sorted(contract_source_file_digests.items())),
        "effective_contract_semantic_layers": {
            contract_id: dict(sorted(dict(layers).items()))
            for contract_id, layers in sorted(effective_layers.items())
        },
        "contract_theorem_names": list(contract_theorem_names),
    }
    return canonical_hash(payload)


def assert_contract_projection_ids(
    *,
    selected_contract_ids: tuple[str, ...] | list[str],
    projected_contract_ids: list[str] | tuple[str, ...],
) -> None:
    """Require projection contract IDs to match the explicitly selected set."""
    selected = list(selected_contract_ids)
    projected = list(projected_contract_ids)
    if selected != projected:
        raise EvidenceResolutionError(
            "contract fidelity: selected/projected contract ids differ "
            f"(selected={selected!r} projected={projected!r})"
        )
