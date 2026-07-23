"""Generate concrete Lean terms and proof obligations from PFCoreTrace.v0.

Role expansion alignment: runtime ``ROLE_CAPABILITY_MAP`` (generated from
``catalog/pf_core.catalog.json``) must stay in sync with Lean
``Catalog.runtimeRoleMapEntries`` / ``runtimeRoleMap``. Codegen emits principals with
explicit ``capabilities`` (already expanded); it does not reference ``runtimeRoleMap``
directly. Parity is enforced by ``tests/test_pf_core_research.py`` and
``pcs pf-core audit-lean-catalog``.

Effect-kind → Lean constructors come from generated ``EFFECT_KIND_TO_LEAN`` in
``pf_core_catalog.py`` (single source in ``scripts/gen_pf_core_catalog.py``).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from pcs_core.asset_resolver import (
    lean_root as resolve_lean_root,
)
from pcs_core.asset_resolver import (
    pcs_kernel_root,
    pf_core_kernel_root,
    proof_ref_from_path,
    require_lean_root,
)
from pcs_core.hash import canonical_hash
from pcs_core.pf_core_contract import (
    field_semantics_layer,
    load_contracts_from_dir,
    validate_trace_contracts,
)
from pcs_core.pf_core_runtime import is_tool_use_trace


@dataclass(frozen=True)
class GeneratedLeanProof:
    """Inventory of a generated PF-Core Lean proof module."""

    path: Path
    theorem_names: frozenset[str]
    certificate_mode: str
    evidence_files: tuple[Path, ...]
    mode_witness_theorem: str = "concrete_certificate_mode_witness"
    mode_witness_proposition: str = ""
    semantic_projection_hash: str | None = None
    semantic_projection: Mapping[str, Any] | None = None
    theorem_specs: tuple[Any, ...] = ()
    theorem_manifest: Mapping[str, Any] | None = None
    theorem_manifest_hash: str | None = None
    theorem_manifest_path: Path | None = None


class CertificateModeEvidenceMissing(ValueError):
    """Raised when a certificate mode lacks required evidence or theorems."""


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
            "compositional_frame_valid_initial",
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

_LEAN_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")
_THEOREM_SIGNATURE_RE = re.compile(
    r"theorem\s+(\w+)(?:\s*\([^)]*\))*\s*:\s*(.+?)\s*:=",
    re.DOTALL,
)


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
                raise ValueError(f"unknown catalog required_certificate_mode {catalog_mode!r}")
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
    """Static + per-event obligations for a certificate mode."""
    base = MODE_OBLIGATION_THEOREMS.get(mode, frozenset())
    if mode == "TraceSafeRCertificate":
        resource_scope = frozenset(
            f"concrete_action_resource_scope_{lean_ident('ev', str(event.get('event_id') or index))}"
            for index, event in enumerate(events)
            if str(event.get("decision") or "") == "allow"
        )
        return base | resource_scope | {"concrete_certificate_mode_witness"}
    if mode == "FramePreservedCertificate":
        transition_names: set[str] = set()
        for index, event in enumerate(events):
            event_name = lean_ident("ev", str(event.get("event_id") or index))
            transition_names.add(f"step_state_applies_{event_name}")
            transition_names.add(f"frame_valid_after_{event_name}")
            decision = str(event.get("decision") or "")
            if decision == "deny":
                transition_names.add(f"deny_identity_{event_name}")
            else:
                transition_names.update(
                    {
                        f"resource_frame_update_{event_name}",
                        f"active_principal_update_{event_name}",
                        f"tenant_update_{event_name}",
                        f"capability_frame_update_{event_name}",
                    }
                )
        return base | transition_names | {"concrete_certificate_mode_witness"}
    return base | {"concrete_certificate_mode_witness"}


def theorem_inventory_hash(theorem_names: frozenset[str] | set[str]) -> str:
    """Stable hash of the generated theorem-name inventory."""
    payload = "\n".join(sorted(theorem_names)).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def register_theorem_name(inventory: set[str], name: str) -> str:
    """Register a theorem name constructed at emit time; return the name."""
    if not name or not name.isidentifier():
        raise ValueError(f"invalid theorem name for inventory: {name!r}")
    inventory.add(name)
    return name


def verify_certificate_mode_prerequisites(
    mode: str,
    *,
    events: list[Mapping[str, Any]],
    handoffs: list[Mapping[str, Any]],
    contracts: Mapping[str, Mapping[str, Any]],
    contract_theorems: list[str],
    effect_frame: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed when a certificate mode lacks required evidence."""
    if mode == "HandoffSafeCertificate":
        if not handoffs:
            raise CertificateModeEvidenceMissing(
                "HandoffSafeCertificate requires ≥1 validated handoff artifact"
            )
    elif mode == "ContractCheckedCertificate":
        if not contracts:
            raise CertificateModeEvidenceMissing(
                "ContractCheckedCertificate requires ≥1 resolved contract"
            )
        if not contract_theorems:
            raise CertificateModeEvidenceMissing(
                "ContractCheckedCertificate requires ≥1 generated contract theorem"
            )
    elif mode == "FramePreservedCertificate":
        if not events:
            raise CertificateModeEvidenceMissing(
                "FramePreservedCertificate requires ≥1 event and concrete initial state"
            )
        first = events[0]
        principal = first.get("principal") if isinstance(first, Mapping) else None
        if not isinstance(principal, dict):
            raise CertificateModeEvidenceMissing(
                "FramePreservedCertificate requires concrete initial state (event principal)"
            )
        from pcs_core.pf_core_resolved_evidence import (
            EvidenceResolutionError,
            simulate_frame_preserved_transitions,
        )

        try:
            simulate_frame_preserved_transitions(events)
        except EvidenceResolutionError as exc:
            raise CertificateModeEvidenceMissing(str(exc)) from exc
    elif mode == "EffectFrameCertificate":
        if not events:
            raise CertificateModeEvidenceMissing("EffectFrameCertificate requires ≥1 event")
        if effect_frame is None:
            raise CertificateModeEvidenceMissing(
                "EffectFrameCertificate requires an independently declared "
                "PFCoreEffectFrame.v0 (evidence_selection.effect_frame_id)"
            )
        from pcs_core.pf_core_resolved_evidence import (
            EvidenceResolutionError,
            assert_actions_in_declared_frame,
            effect_frame_allowed_kinds,
        )

        if not effect_frame_allowed_kinds(effect_frame):
            raise CertificateModeEvidenceMissing(
                "EffectFrameCertificate declared frame has empty allowed_effect_kinds"
            )
        try:
            assert_actions_in_declared_frame(frame=effect_frame, events=events)
        except EvidenceResolutionError as exc:
            raise CertificateModeEvidenceMissing(str(exc)) from exc
    elif mode == "CompositionalExtensionCertificate":
        if not events:
            raise CertificateModeEvidenceMissing(
                "CompositionalExtensionCertificate requires ≥1 event"
            )
        # A6: operational application + frame preservation (same transition evidence as
        # FramePreserved). Prefix-only TraceSafe chaining is TracePrefixSafeCertificate.
        from pcs_core.pf_core_resolved_evidence import (
            EvidenceResolutionError,
            simulate_frame_preserved_transitions,
        )

        try:
            simulate_frame_preserved_transitions(events)
        except EvidenceResolutionError as exc:
            raise CertificateModeEvidenceMissing(
                f"CompositionalExtensionCertificate operational application failed: {exc}"
            ) from exc
    elif mode == "TraceSafeCertificate":
        if not events:
            raise CertificateModeEvidenceMissing("TraceSafeCertificate requires ≥1 event")
    elif mode == "TraceSafeRCertificate":
        if not events:
            raise CertificateModeEvidenceMissing(
                "TraceSafeRCertificate requires ≥1 event with resource-pattern evidence"
            )
        for index, event in enumerate(events):
            if not isinstance(event, Mapping):
                continue
            if str(event.get("decision") or "") != "allow":
                continue
            action = event.get("action")
            if not isinstance(action, dict) or not action_resources_within_capability_pattern_d(
                action
            ):
                event_id = str(event.get("event_id") or index)
                raise CertificateModeEvidenceMissing(
                    "TraceSafeRCertificate missing resource-pattern evidence for allow event "
                    f"{event_id!r}"
                )


def mode_witness_proposition_and_proof(
    mode: str,
    *,
    trace_var: str,
    aggregate_prop: str | None = None,
    aggregate_proof: str | None = None,
) -> tuple[str, str]:
    """Return (proposition, proof term) for ``concrete_certificate_mode_witness``."""
    if aggregate_prop and aggregate_proof:
        return aggregate_prop, aggregate_proof
    if mode == "TraceSafeRCertificate":
        return f"TraceSafeR {trace_var}", "concrete_trace_safe_r_prop"
    return f"TraceSafe {trace_var}", "concrete_trace_safe_prop"


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
        # Parenthesize nested And.intro so Lean does not parse
        # ``And.intro a And.intro b c`` as a failed function application.
        proof = f"And.intro {ref} ({proof})"
    return f"theorem {name} : {typ} := {proof}"


def _parse_theorem_signature(lean_theorem: str) -> tuple[str, str] | None:
    from pcs_core.pf_core_theorem_manifest import parse_theorem_signature

    return parse_theorem_signature(lean_theorem)


def lean_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def lean_ident(prefix: str, raw: str) -> str:
    slug = _LEAN_IDENT_RE.sub("_", raw).strip("_")
    if not slug or slug[0].isdigit():
        slug = f"{prefix}_{slug or 'x'}"
    return slug


def effect_kind_to_lean(effect_kind: str) -> str:
    from pcs_core.pf_core_catalog import EFFECT_KIND_TO_LEAN

    mapped = EFFECT_KIND_TO_LEAN.get(effect_kind)
    if mapped is None:
        return f"Effect.custom {lean_string_literal(effect_kind)}"
    return mapped


def declared_effect_frame_to_lean(
    frame: Mapping[str, Any],
    *,
    name: str = "concreteDeclaredFrame",
) -> str:
    """Emit an independent Lean ``List Effect`` from a PFCoreEffectFrame.v0 artifact.

    The frame is never derived from ``action.effects``.
    """
    from pcs_core.pf_core_resolved_evidence import effect_frame_allowed_kinds

    kinds = effect_frame_allowed_kinds(frame)
    if not kinds:
        raise CertificateModeEvidenceMissing(
            "declared effect frame requires ≥1 allowed_effect_kinds"
        )
    effect_exprs = [effect_kind_to_lean(kind) for kind in kinds]
    return f"def {name} : List Effect :=\n  [{', '.join(effect_exprs)}]"


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
    *,
    inventory: set[str] | None = None,
    ctx: Any | None = None,
) -> tuple[list[str], list[str]]:
    """Return (contract Lean defs, contract proof theorems) for referenced contracts."""
    from pcs_core.pf_core_theorem_manifest import TheoremBuildContext

    defs: list[str] = []
    theorems: list[str] = []
    seen_contracts: set[str] = set()
    build_ctx = ctx if isinstance(ctx, TheoremBuildContext) else None
    names = (
        build_ctx.inventory
        if build_ctx is not None
        else (inventory if inventory is not None else set())
    )

    def _emit(lean: str, *, node: str, evidence: tuple[str, ...] = ()) -> None:
        if build_ctx is not None:
            theorems.append(
                build_ctx.emit(
                    lean,
                    category="contract",
                    generation_node=node,
                    evidence_artifact_ids=evidence,
                    certificate_mode_role="required",
                )
            )
        else:
            parsed = _parse_theorem_signature(lean)
            if parsed is not None:
                register_theorem_name(names, parsed[0])
            theorems.append(lean)

    trace_id = str(trace.get("trace_id") or "trace")
    trace_var = lean_ident("trace", trace_id)

    for index, event in enumerate(trace_events(trace)):
        refs = event.get("contract_refs")
        if not isinstance(refs, list):
            continue
        event_name = lean_ident("ev", str(event.get("event_id") or index))
        event_id = str(event.get("event_id") or index)
        for ref in refs:
            contract_id = str(ref)
            contract = contracts.get(contract_id)
            if contract is None:
                continue
            base_name = lean_ident("contract", contract_id)
            evidence = (contract_id, event_id)
            if contract_id not in seen_contracts:
                seen_contracts.add(contract_id)
                defs.append(contract_specs_to_lean(contract, base_name=base_name))
                theorem_name = f"concrete_trace_satisfies_{base_name}"
                _emit(
                    f"theorem {theorem_name} : "
                    f"traceSatisfiesContractSpecsD {base_name}Pre {base_name}Post "
                    f"{base_name}Inv {trace_var} = true := by\n"
                    "  decide",
                    node=f"codegen.contract.{contract_id}.trace_satisfies",
                    evidence=(contract_id,),
                )
            theorem_name = f"concrete_satisfies_{base_name}_{event_name}"
            _emit(
                f"theorem {theorem_name} : "
                f"satisfiesContractSpecD {base_name}Pre {base_name}Post {event_name} = true := by\n"
                "  decide",
                node=f"codegen.contract.{contract_id}.event.{event_id}.satisfies",
                evidence=evidence,
            )
            if _contract_has_lean_pre_fields(contract):
                pre_name = f"concrete_contract_pre_{base_name}_{event_name}"
                _emit(
                    f"theorem {pre_name} : "
                    f"contractPreD {base_name}Pre {event_name}Principal {event_name}Action = true := by\n"
                    "  decide",
                    node=f"codegen.contract.{contract_id}.event.{event_id}.pre",
                    evidence=evidence,
                )
            if _contract_has_lean_post_fields(contract):
                post_name = f"concrete_contract_post_{base_name}_{event_name}"
                _emit(
                    f"theorem {post_name} : "
                    f"contractPostD {base_name}Post {event_name} = true := by\n"
                    "  decide",
                    node=f"codegen.contract.{contract_id}.event.{event_id}.post",
                    evidence=evidence,
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
    # Exact projected ID sequence — do not sort or rediscover from source siblings.
    from pcs_core.pf_core_resolved_evidence import delegated_capability_ids

    cap_ids = delegated_capability_ids(handoff)
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
    inventory: set[str],
    trace_path: Path | None = None,
    effect_frame: Mapping[str, Any] | None = None,
) -> tuple[list[str], str | None, str | None]:
    """Return mode theorems plus optional aggregate (prop, proof) for the mode witness.

    Theorem names are registered into ``inventory`` at construction time.
    Prerequisites must already be verified; missing evidence raises.
    """
    del trace, trace_path  # reserved for future mode-specific evidence binding
    theorems: list[str] = []
    mode = certificate_mode if certificate_mode in CERTIFICATE_MODES else DEFAULT_CERTIFICATE_MODE
    aggregate_prop: str | None = None
    aggregate_proof: str | None = None

    if mode == "FramePreservedCertificate":
        if not events:
            raise CertificateModeEvidenceMissing(
                "FramePreservedCertificate requires ≥1 event and concrete initial state"
            )
        from pcs_core.pf_core_resolved_evidence import (
            EvidenceResolutionError,
            simulate_frame_preserved_transitions,
        )

        try:
            simulate_frame_preserved_transitions(events)
        except EvidenceResolutionError as exc:
            raise CertificateModeEvidenceMissing(str(exc)) from exc

        first = events[0]
        first_name = lean_ident("ev", str(first.get("event_id") or "0"))
        principal_name = f"{first_name}Principal"
        pre_state = "frameState_0"
        theorems.append(f"def {pre_state} : State := initialState {principal_name}")
        register_theorem_name(inventory, "frame_valid_initial")
        theorems.append(
            f"theorem frame_valid_initial : frameValidD {pre_state} = true := by\n  decide"
        )
        step_props: list[str] = [f"frameValidD {pre_state} = true"]
        step_refs: list[str] = ["frame_valid_initial"]
        for index, event in enumerate(events):
            event_name = lean_ident("ev", str(event.get("event_id") or index))
            principal_ref = f"{event_name}Principal"
            action_ref = f"{event_name}Action"
            post_state = f"frameState_{index + 1}"
            decision = str(event.get("decision") or "")
            if decision == "deny":
                theorems.append(f"def {post_state} : State := {pre_state}")
                applies_name = f"step_state_applies_{event_name}"
                register_theorem_name(inventory, applies_name)
                theorems.append(
                    f"theorem {applies_name} : "
                    f"stepState {pre_state} {event_name} = some {post_state} := by\n"
                    "  decide"
                )
                identity_name = f"deny_identity_{event_name}"
                register_theorem_name(inventory, identity_name)
                theorems.append(
                    f"theorem {identity_name} : {pre_state} = {post_state} := by\n  decide"
                )
                step_props.extend(
                    [
                        f"stepState {pre_state} {event_name} = some {post_state}",
                        f"{pre_state} = {post_state}",
                    ]
                )
                step_refs.extend([applies_name, identity_name])
            else:
                # Explicit post-state via expandResourceFrame (no applyEvent fallback).
                theorems.append(
                    f"def {post_state} : State :=\n"
                    "  {\n"
                    f"    tenant := {principal_ref}.tenant\n"
                    f"    activePrincipal := {principal_ref}\n"
                    f"    resourceFrame := expandResourceFrame {pre_state}.resourceFrame "
                    f"{action_ref}\n"
                    f"    capabilityFrame := {principal_ref}.capabilities\n"
                    "  }"
                )
                applies_name = f"step_state_applies_{event_name}"
                register_theorem_name(inventory, applies_name)
                theorems.append(
                    f"theorem {applies_name} : "
                    f"stepState {pre_state} {event_name} = some {post_state} := by\n"
                    "  decide"
                )
                resource_name = f"resource_frame_update_{event_name}"
                register_theorem_name(inventory, resource_name)
                theorems.append(
                    f"theorem {resource_name} : "
                    f"{post_state}.resourceFrame = "
                    f"expandResourceFrame {pre_state}.resourceFrame {action_ref} := by\n"
                    "  decide"
                )
                principal_upd = f"active_principal_update_{event_name}"
                register_theorem_name(inventory, principal_upd)
                theorems.append(
                    f"theorem {principal_upd} : "
                    f"{post_state}.activePrincipal = {principal_ref} := by\n"
                    "  decide"
                )
                tenant_upd = f"tenant_update_{event_name}"
                register_theorem_name(inventory, tenant_upd)
                theorems.append(
                    f"theorem {tenant_upd} : "
                    f"{post_state}.tenant = {principal_ref}.tenant := by\n"
                    "  decide"
                )
                caps_upd = f"capability_frame_update_{event_name}"
                register_theorem_name(inventory, caps_upd)
                theorems.append(
                    f"theorem {caps_upd} : "
                    f"{post_state}.capabilityFrame = {principal_ref}.capabilities := by\n"
                    "  decide"
                )
                step_props.extend(
                    [
                        f"stepState {pre_state} {event_name} = some {post_state}",
                        f"{post_state}.resourceFrame = "
                        f"expandResourceFrame {pre_state}.resourceFrame {action_ref}",
                        f"{post_state}.activePrincipal = {principal_ref}",
                        f"{post_state}.tenant = {principal_ref}.tenant",
                        f"{post_state}.capabilityFrame = {principal_ref}.capabilities",
                    ]
                )
                step_refs.extend(
                    [
                        applies_name,
                        resource_name,
                        principal_upd,
                        tenant_upd,
                        caps_upd,
                    ]
                )
            frame_after = f"frame_valid_after_{event_name}"
            register_theorem_name(inventory, frame_after)
            theorems.append(
                f"theorem {frame_after} : frameValidD {post_state} = true := by\n  decide"
            )
            step_props.append(f"frameValidD {post_state} = true")
            step_refs.append(frame_after)
            pre_state = post_state
        register_theorem_name(inventory, "frame_preserved_steps")
        theorems.append(lean_and_intro_theorem("frame_preserved_steps", step_props, step_refs))
        aggregate_prop = " ∧ ".join(step_props)
        aggregate_proof = "frame_preserved_steps"

    if mode == "EffectFrameCertificate":
        if not events:
            raise CertificateModeEvidenceMissing("EffectFrameCertificate requires ≥1 event")
        if effect_frame is None:
            raise CertificateModeEvidenceMissing(
                "EffectFrameCertificate requires an independently declared "
                "PFCoreEffectFrame.v0 bound via evidence_selection.effect_frame_id"
            )
        # One global declared frame for all events (v0 policy).
        frame_name = "concreteDeclaredFrame"
        theorems.append(declared_effect_frame_to_lean(effect_frame, name=frame_name))
        effect_props: list[str] = []
        effect_refs: list[str] = []
        for index, event in enumerate(events):
            event_name = lean_ident("ev", str(event.get("event_id") or index))
            action_name = f"{event_name}Action"
            step_theorem = f"concrete_action_effects_in_frame_{event_name}"
            register_theorem_name(inventory, step_theorem)
            # Non-tautological: frame is the independent declared artifact, never action.effects.
            theorems.append(
                f"theorem {step_theorem} : "
                f"actionEffectsInFrameD {action_name} {frame_name} = true := by\n"
                "  decide"
            )
            effect_props.append(f"actionEffectsInFrameD {action_name} {frame_name} = true")
            effect_refs.append(step_theorem)
        register_theorem_name(inventory, "concrete_action_effects_in_frame")
        theorems.append(
            lean_and_intro_theorem(
                "concrete_action_effects_in_frame",
                effect_props,
                effect_refs,
            )
        )
        aggregate_prop = " ∧ ".join(effect_props) if len(effect_props) > 1 else effect_props[0]
        aggregate_proof = "concrete_action_effects_in_frame"

    if mode == "HandoffSafeCertificate":
        if not handoff_theorems:
            raise CertificateModeEvidenceMissing(
                "HandoffSafeCertificate requires ≥1 validated handoff"
            )
        handoff_props: list[str] = []
        handoff_refs: list[str] = []
        for handoff_theorem in handoff_theorems:
            parsed = _parse_theorem_signature(handoff_theorem)
            if parsed is None:
                continue
            theorem_name, prop_type = parsed
            handoff_props.append(prop_type)
            handoff_refs.append(theorem_name)
        if not handoff_props:
            raise CertificateModeEvidenceMissing(
                "HandoffSafeCertificate requires ≥1 validated handoff theorem"
            )
        register_theorem_name(inventory, "concrete_handoff_safe")
        theorems.append(
            lean_and_intro_theorem("concrete_handoff_safe", handoff_props, handoff_refs)
        )
        aggregate_prop = " ∧ ".join(handoff_props) if len(handoff_props) > 1 else handoff_props[0]
        aggregate_proof = "concrete_handoff_safe"

    if mode == "CompositionalExtensionCertificate":
        # A6: safe prefix + EventSafe + Applies + FrameValid pre/post → TraceSafe extended.
        # Prefix-only TraceSafe chaining belongs under TracePrefixSafeCertificate (docs alias).
        if not events:
            raise CertificateModeEvidenceMissing(
                "CompositionalExtensionCertificate requires ≥1 event"
            )
        from pcs_core.pf_core_resolved_evidence import (
            EvidenceResolutionError,
            simulate_frame_preserved_transitions,
        )

        try:
            simulate_frame_preserved_transitions(events)
        except EvidenceResolutionError as exc:
            raise CertificateModeEvidenceMissing(
                f"CompositionalExtensionCertificate operational application failed: {exc}"
            ) from exc

        first = events[0]
        first_name = lean_ident("ev", str(first.get("event_id") or "0"))
        principal_name = f"{first_name}Principal"
        pre_state = "compositionalState_0"
        theorems.append(f"def {pre_state} : State := initialState {principal_name}")
        register_theorem_name(inventory, "compositional_frame_valid_initial")
        theorems.append(
            f"theorem compositional_frame_valid_initial : "
            f"frameValidD {pre_state} = true := by\n"
            "  decide"
        )
        trace_expr = "Trace.empty"
        compositional_props: list[str] = [f"frameValidD {pre_state} = true"]
        compositional_refs: list[str] = ["compositional_frame_valid_initial"]
        frame_valid_pre = "compositional_frame_valid_initial"
        for index, event in enumerate(events):
            event_name = lean_ident("ev", str(event.get("event_id") or index))
            principal_ref = f"{event_name}Principal"
            action_ref = f"{event_name}Action"
            post_state = f"compositionalState_{index + 1}"
            prev_trace = trace_expr
            # Fully parenthesize so `TraceSafe (Trace.cons ...)` parses correctly.
            trace_expr = f"(Trace.cons ({prev_trace}) {event_name})"
            decision = str(event.get("decision") or "")
            if decision == "deny":
                theorems.append(f"def {post_state} : State := {pre_state}")
            else:
                theorems.append(
                    f"def {post_state} : State :=\n"
                    "  {\n"
                    f"    tenant := {principal_ref}.tenant\n"
                    f"    activePrincipal := {principal_ref}\n"
                    f"    resourceFrame := expandResourceFrame {pre_state}.resourceFrame "
                    f"{action_ref}\n"
                    f"    capabilityFrame := {principal_ref}.capabilities\n"
                    "  }"
                )
            applies_name = f"compositional_step_applies_{event_name}"
            register_theorem_name(inventory, applies_name)
            theorems.append(
                f"theorem {applies_name} : "
                f"stepState {pre_state} {event_name} = some {post_state} := by\n"
                "  decide"
            )
            frame_after = f"compositional_frame_valid_after_{event_name}"
            register_theorem_name(inventory, frame_after)
            theorems.append(
                f"theorem {frame_after} : frameValidD {post_state} = true := by\n  decide"
            )
            step_theorem = f"concrete_compositional_extension_{event_name}"
            register_theorem_name(inventory, step_theorem)
            if index == 0:
                prefix_proof = "traceSafe_empty"
            else:
                prev_event = lean_ident("ev", str(events[index - 1].get("event_id") or index - 1))
                prefix_proof = f"concrete_compositional_extension_{prev_event}"
            # Package CompositionalSafeExtension via the A6 yield lemma.
            # eventSafeD → EventSafe via soundness; stepState equality is Applies.
            theorems.append(
                f"theorem {step_theorem} :\n"
                f"    TraceSafe {trace_expr} :=\n"
                f"  compositional_safe_extension_yields_safe_extended_trace "
                f"({prev_trace}) {event_name} {pre_state} {post_state} ⟨\n"
                f"    {prefix_proof},\n"
                f"    (eventSafeD_sound {event_name}).mp concrete_event_safe_{event_name},\n"
                f"    {applies_name},\n"
                f"    (frameValidD_sound {pre_state}).mp {frame_valid_pre},\n"
                f"    (frameValidD_sound {post_state}).mp {frame_after}⟩"
            )
            compositional_props.extend(
                [
                    f"stepState {pre_state} {event_name} = some {post_state}",
                    f"frameValidD {post_state} = true",
                    f"TraceSafe {trace_expr}",
                ]
            )
            compositional_refs.extend([applies_name, frame_after, step_theorem])
            pre_state = post_state
            frame_valid_pre = frame_after

        # Optional handoff / contract composition when PR2/PR3 resolved evidence exists.
        for handoff_theorem in handoff_theorems:
            parsed = _parse_theorem_signature(handoff_theorem)
            if parsed is None:
                continue
            theorem_name, prop_type = parsed
            compositional_props.append(prop_type)
            compositional_refs.append(theorem_name)
        for contract_theorem in contract_theorems:
            parsed = _parse_theorem_signature(contract_theorem)
            if parsed is None:
                continue
            theorem_name, prop_type = parsed
            compositional_props.append(prop_type)
            compositional_refs.append(theorem_name)

        register_theorem_name(inventory, "concrete_compositional_extension")
        theorems.append(
            lean_and_intro_theorem(
                "concrete_compositional_extension",
                compositional_props,
                compositional_refs,
            )
        )
        aggregate_prop = (
            " ∧ ".join(compositional_props)
            if len(compositional_props) > 1
            else compositional_props[0]
        )
        aggregate_proof = "concrete_compositional_extension"

    if mode == "ContractCheckedCertificate":
        if not contract_theorems:
            raise CertificateModeEvidenceMissing(
                "ContractCheckedCertificate requires ≥1 generated contract theorem"
            )
        contract_props: list[str] = []
        contract_refs: list[str] = []
        for contract_theorem in contract_theorems:
            parsed = _parse_theorem_signature(contract_theorem)
            if parsed is None:
                continue
            theorem_name, prop_type = parsed
            contract_props.append(prop_type)
            contract_refs.append(theorem_name)
        if not contract_props:
            raise CertificateModeEvidenceMissing(
                "ContractCheckedCertificate requires ≥1 generated contract theorem"
            )
        register_theorem_name(inventory, "concrete_contract_checked")
        theorems.append(
            lean_and_intro_theorem("concrete_contract_checked", contract_props, contract_refs)
        )
        aggregate_prop = (
            " ∧ ".join(contract_props) if len(contract_props) > 1 else contract_props[0]
        )
        aggregate_proof = "concrete_contract_checked"

    if mode == "TraceSafeRCertificate":
        if not events:
            raise CertificateModeEvidenceMissing(
                "TraceSafeRCertificate requires ≥1 event with resource-pattern evidence"
            )
        if not all(
            str(event.get("decision") or "") != "allow"
            or action_resources_within_capability_pattern_d(event.get("action") or {})
            for event in events
            if isinstance(event, dict)
        ):
            raise CertificateModeEvidenceMissing(
                "TraceSafeRCertificate requires all allow events to pass resource-pattern scope"
            )
        for name in (
            "concrete_trace_safe_r",
            "concrete_trace_safe_r_prop",
            "concrete_trace_safe_r_implies_trace_safe",
        ):
            register_theorem_name(inventory, name)
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
        aggregate_prop = f"TraceSafeR {trace_var}"
        aggregate_proof = "concrete_trace_safe_r_prop"

    return theorems, aggregate_prop, aggregate_proof


def generate_resource_scope_theorems(
    events: list[Mapping[str, Any]],
    *,
    inventory: set[str],
) -> list[str]:
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
        theorem_name = f"concrete_action_resource_scope_{event_name}"
        register_theorem_name(inventory, theorem_name)
        theorems.append(
            f"theorem {theorem_name} :\n"
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
    inventory: set[str],
) -> list[str]:
    """Conservative tenant isolation, cross-tenant safety, NI hooks (not TraceSafeR)."""
    del events
    names = (
        "concrete_tenant_isolation_prop",
        "concrete_trace_cross_tenant_safe_prop",
        "concrete_non_interference_prop",
    )
    for name in names:
        register_theorem_name(inventory, name)
    return [
        f"theorem concrete_tenant_isolation_prop : TenantIsolation {trace_var} :=\n"
        f"  traceSafe_implies_tenant_isolation {trace_var} concrete_trace_safe_prop",
        f"theorem concrete_trace_cross_tenant_safe_prop : TraceCrossTenantSafe {trace_var} :=\n"
        f"  traceSafe_implies_trace_cross_tenant_safe {trace_var} concrete_trace_safe_prop",
        f"theorem concrete_non_interference_prop (tenantLow tenantHigh : String) :\n"
        f"    TenantProjectionIsolation tenantLow tenantHigh {trace_var} :=\n"
        f"  traceSafe_implies_tenant_projection_isolation tenantLow tenantHigh {trace_var} "
        "concrete_trace_safe_prop",
    ]


def _adopt_theorem_ir(
    ctx: Any,
    lean_text: str,
    *,
    category: str,
    generation_node: str,
    evidence_artifact_ids: Sequence[str] | tuple[str, ...] = (),
    certificate_mode_role: str = "supporting",
) -> str:
    """Record a Lean theorem into shared IR. Non-theorem fragments (defs) pass through."""
    from pcs_core.pf_core_theorem_manifest import TheoremSpec, parse_theorem_signature

    parsed = parse_theorem_signature(lean_text)
    if parsed is None:
        return lean_text
    name, prop = parsed
    if name not in ctx.inventory:
        ctx.register_name(name)
    if any(spec.name == name for spec in ctx.specs):
        return lean_text
    ctx.specs.append(
        TheoremSpec(
            name=name,
            normalized_proposition=prop,
            category=category,
            generation_node=generation_node,
            evidence_artifact_ids=tuple(evidence_artifact_ids),
            certificate_mode_role=certificate_mode_role,
            lean_text=lean_text,
        )
    )
    return lean_text


def _classify_mode_theorem_name(name: str, mode: str) -> tuple[str, str]:
    """Return (category, certificate_mode_role) for a mode-generated theorem name."""
    if name == "concrete_certificate_mode_witness":
        return "mode_witness", "final_witness"
    aggregates = {
        "concrete_handoff_safe",
        "concrete_contract_checked",
        "concrete_action_effects_in_frame",
        "frame_preserved_steps",
        "concrete_compositional_extension",
    }
    if name in aggregates:
        return "mode_aggregate", "aggregate"
    if name.startswith("concrete_compositional_extension_"):
        return "compositional", "required"
    if name.startswith(
        (
            "compositional_step_applies_",
            "compositional_frame_valid_",
        )
    ):
        return "compositional", "required"
    if name == "compositional_frame_valid_initial":
        return "compositional", "required"
    if name.startswith("concrete_action_effects_in_frame_"):
        return "effect_frame", "required"
    if name.startswith(
        (
            "step_state_applies_",
            "frame_valid_",
            "deny_identity_",
            "resource_frame_update_",
            "active_principal_update_",
            "tenant_update_",
            "capability_frame_update_",
        )
    ):
        return "transition", "required"
    if name.startswith("concrete_trace_safe_r"):
        return "trace_safety", "required"
    mode_defaults = {
        "EffectFrameCertificate": ("effect_frame", "required"),
        "FramePreservedCertificate": ("transition", "required"),
        "HandoffSafeCertificate": ("handoff_safety", "required"),
        "ContractCheckedCertificate": ("contract", "required"),
        "CompositionalExtensionCertificate": ("compositional", "required"),
    }
    return mode_defaults.get(mode, ("mode_aggregate", "required"))


def generate_proof_obligation_file(
    trace: Mapping[str, Any],
    out_dir: Path,
    *,
    trace_path: Path | None = None,
    certificate_mode: str | None = None,
    release_grade: bool = False,
    resolved_evidence: Any | None = None,
) -> GeneratedLeanProof:
    """Write a `.lean` file proving concrete trace/event (and optional handoff) safety.

    Lean terms and ``PFCoreTheoremManifest.v0`` are produced from the same structured
    theorem IR collected during construction.
    """
    from pcs_core.pf_core_resolved_evidence import (
        EvidenceResolutionError,
        assert_handoff_capability_fidelity,
        resolve_pf_core_evidence,
    )
    from pcs_core.pf_core_semantic_projection import (
        build_semantic_projection,
        extract_lean_delegated_capability_sequences,
        projection_contract_ids,
        projection_contracts,
        projection_handoffs,
        projection_to_codegen_trace,
    )
    from pcs_core.pf_core_theorem_manifest import (
        TheoremBuildContext,
        build_theorem_manifest,
        write_theorem_manifest,
    )

    mode = resolve_certificate_mode(
        trace,
        trace_path=trace_path,
        certificate_mode=certificate_mode,
        release_grade=release_grade,
    )
    if release_grade and is_tool_use_trace(trace, trace_path=trace_path):
        mode = TOOL_USE_DEFAULT_CERTIFICATE_MODE

    if resolved_evidence is None:
        if trace_path is None:
            raise CertificateModeEvidenceMissing(
                "generate_proof_obligation_file requires trace_path or resolved_evidence"
            )
        try:
            resolved_evidence = resolve_pf_core_evidence(
                trace,
                trace_path=trace_path,
                certificate_mode=mode,
            )
        except EvidenceResolutionError as exc:
            raise CertificateModeEvidenceMissing(str(exc)) from exc

    handoffs = resolved_evidence.handoff_artifacts
    projection = build_semantic_projection(
        trace,
        certificate_mode=mode,
        trace_path=trace_path,
        resolved_evidence=resolved_evidence,
    )
    projection_hash = str(projection["projection_hash"])
    codegen_trace = projection_to_codegen_trace(projection)
    # Preserve workflow / tool-use hints used by mode policy helpers.
    for key in ("workflow_id", "policy_hash", "contract_hash", "trace_hash"):
        if key in trace:
            codegen_trace[key] = trace[key]

    module = generated_module_name(trace)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{module}.lean"

    events = trace_events(codegen_trace)
    ctx = TheoremBuildContext()
    inventory = ctx.inventory
    evidence_files: list[Path] = []
    if trace_path is not None:
        evidence_files.append(trace_path)
    evidence_files.extend(resolved_evidence.handoff_paths)
    evidence_files.extend(resolved_evidence.contract_paths)
    if resolved_evidence.effect_frame_path is not None:
        evidence_files.append(resolved_evidence.effect_frame_path)

    trace_body = trace_to_lean(codegen_trace)
    trace_id = str(codegen_trace.get("trace_id") or "trace")
    trace_var = lean_ident("trace", trace_id)

    event_theorem_parts: list[str] = []
    for index, event in enumerate(events):
        event_id = str(event.get("event_id") or index)
        event_name = lean_ident("ev", event_id)
        theorem_name = f"concrete_event_safe_{event_name}"
        lean = f"theorem {theorem_name} : eventSafeD {event_name} = true := by\n  decide"
        event_theorem_parts.append(
            _adopt_theorem_ir(
                ctx,
                lean,
                category="event_safety",
                generation_node=f"codegen.event.{event_id}.safe",
                evidence_artifact_ids=(event_id,),
                certificate_mode_role="supporting",
            )
        )
    event_theorem_block = ("\n".join(event_theorem_parts) + "\n\n") if event_theorem_parts else ""

    projected_handoffs = projection_handoffs(projection)
    handoff_defs: list[str] = []
    handoff_theorems: list[str] = []
    for index, handoff in enumerate(projected_handoffs):
        handoff_id = str(handoff.get("handoff_id") or f"handoff_{index}")
        handoff_name = lean_ident("handoff", handoff_id)
        handoff_defs.append(handoff_to_lean(handoff, name=handoff_name))
        theorem_name = f"concrete_handoff_safe_{handoff_name}"
        lean = f"theorem {theorem_name} : handoffSafeD {handoff_name} = true := by\n  decide"
        handoff_theorems.append(
            _adopt_theorem_ir(
                ctx,
                lean,
                category="handoff_safety",
                generation_node=f"codegen.handoff.{handoff_id}.safe",
                evidence_artifact_ids=(handoff_id,),
                certificate_mode_role="required",
            )
        )

    handoff_block = ""
    if handoff_defs:
        handoff_block = "\n\n".join(handoff_defs) + "\n\n"
        handoff_block += "\n\n".join(handoff_theorems) + "\n\n"

    projected_contracts = projection_contracts(projection)
    source_contracts = resolved_evidence.contracts_by_id
    if projected_contracts or source_contracts:
        from pcs_core.pf_core_resolved_evidence import assert_contract_projection_ids

        assert_contract_projection_ids(
            selected_contract_ids=resolved_evidence.selected_contract_ids,
            projected_contract_ids=projection_contract_ids(projection),
        )
    # Codegen binds Lean obligations from resolved source contracts (flat
    # semantics_layer map), not the projection's materialized field records.
    contract_defs, contract_theorems = generate_contract_proof_obligations(
        codegen_trace, source_contracts, inventory=inventory, ctx=ctx
    )
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
    elif trace_has_contract_refs(codegen_trace):
        contract_note = (
            "-- Contract refs present but contract JSON not found alongside trace; "
            "run `pcs pf-core validate-contracts` before lean-check.\n"
        )

    verify_certificate_mode_prerequisites(
        mode,
        events=events,
        handoffs=list(projected_handoffs),
        contracts=source_contracts,
        contract_theorems=contract_theorems,
        effect_frame=resolved_evidence.effect_frame,
    )

    base_trace_safe = f"theorem concrete_trace_safe : traceSafeD {trace_var} = true := by\n  decide"
    base_trace_safe_prop = (
        f"theorem concrete_trace_safe_prop : TraceSafe {trace_var} :=\n"
        f"  (traceSafeD_sound {trace_var}).mp concrete_trace_safe"
    )
    base_allowed = (
        f"theorem concrete_allowed_events_allowed :\n"
        f"    ∀ ev, EventIn ev {trace_var} → ev.decision = Decision.allow →\n"
        f"      ActionAllowed ev.principal ev.action :=\n"
        f"  fun ev hIn hAllow =>\n"
        f"    every_allowed_event_in_safe_trace_is_allowed {trace_var} ev "
        f"concrete_trace_safe_prop hIn hAllow"
    )
    for lean, node in (
        (base_trace_safe, "codegen.trace_safety.concrete_trace_safe"),
        (base_trace_safe_prop, "codegen.trace_safety.concrete_trace_safe_prop"),
        (base_allowed, "codegen.trace_safety.concrete_allowed_events_allowed"),
    ):
        _adopt_theorem_ir(
            ctx,
            lean,
            category="trace_safety",
            generation_node=node,
            certificate_mode_role="required",
        )

    mode_theorems, aggregate_prop, aggregate_proof = generate_mode_proof_theorems(
        codegen_trace,
        trace_var=trace_var,
        events=events,
        certificate_mode=mode,
        handoff_theorems=handoff_theorems,
        contract_theorems=contract_theorems,
        inventory=inventory,
        trace_path=trace_path,
        effect_frame=resolved_evidence.effect_frame,
    )
    adopted_mode: list[str] = []
    for fragment in mode_theorems:
        parsed = _parse_theorem_signature(fragment)
        if parsed is None:
            adopted_mode.append(fragment)
            continue
        name, _prop = parsed
        category, role = _classify_mode_theorem_name(name, mode)
        frame_id = ""
        if resolved_evidence.effect_frame is not None:
            frame_id = str(resolved_evidence.effect_frame.get("frame_id") or "")
        evidence_ids: tuple[str, ...] = ()
        if frame_id and category == "effect_frame":
            evidence_ids = (frame_id,)
        adopted_mode.append(
            _adopt_theorem_ir(
                ctx,
                fragment,
                category=category,
                generation_node=f"codegen.mode.{mode}.{name}",
                evidence_artifact_ids=evidence_ids,
                certificate_mode_role=role,
            )
        )
    mode_theorem_block = ""
    if adopted_mode:
        mode_theorem_block = "\n\n".join(adopted_mode) + "\n\n"

    trust_boundary_theorems = generate_trust_boundary_theorems(
        events, trace_var=trace_var, inventory=inventory
    )
    adopted_trust: list[str] = []
    for lean in trust_boundary_theorems:
        parsed = _parse_theorem_signature(lean)
        name = parsed[0] if parsed else "trust"
        adopted_trust.append(
            _adopt_theorem_ir(
                ctx,
                lean,
                category="trust_boundary",
                generation_node=f"codegen.trust_boundary.{name}",
                certificate_mode_role="supporting",
            )
        )
    trust_boundary_block = "\n\n".join(adopted_trust) + "\n\n"

    resource_scope_theorems = (
        generate_resource_scope_theorems(events, inventory=inventory)
        if mode == "TraceSafeRCertificate"
        else []
    )
    adopted_resource: list[str] = []
    for index, lean in enumerate(resource_scope_theorems):
        event = events[index] if index < len(events) else {}
        event_id = str(event.get("event_id") or index) if isinstance(event, dict) else str(index)
        # Resource theorems are only for allow events; match by parsed name.
        parsed = _parse_theorem_signature(lean)
        node_name = parsed[0] if parsed else f"resource_{index}"
        adopted_resource.append(
            _adopt_theorem_ir(
                ctx,
                lean,
                category="resource_scope",
                generation_node=f"codegen.resource_scope.{node_name}",
                evidence_artifact_ids=(event_id,),
                certificate_mode_role="required",
            )
        )
    resource_scope_block = ""
    if adopted_resource:
        resource_scope_block = "\n\n".join(adopted_resource) + "\n\n"

    witness_prop, witness_proof = mode_witness_proposition_and_proof(
        mode,
        trace_var=trace_var,
        aggregate_prop=aggregate_prop,
        aggregate_proof=aggregate_proof,
    )
    witness_lean = (
        f"theorem concrete_certificate_mode_witness :\n"
        f"    SelectedCertificateModePredicate :=\n"
        f"  {witness_proof}"
    )
    # Witness proposition is the SelectedCertificateModePredicate alias body.
    _adopt_theorem_ir(
        ctx,
        f"theorem concrete_certificate_mode_witness : {witness_prop} := {witness_proof}",
        category="mode_witness",
        generation_node="codegen.witness.concrete_certificate_mode_witness",
        certificate_mode_role="final_witness",
    )
    # Keep lean_text as the module form for emit consistency in the IR entry.
    if ctx.specs and ctx.specs[-1].name == "concrete_certificate_mode_witness":
        from pcs_core.pf_core_theorem_manifest import TheoremSpec

        last = ctx.specs[-1]
        ctx.specs[-1] = TheoremSpec(
            name=last.name,
            normalized_proposition=last.normalized_proposition,
            category=last.category,
            generation_node=last.generation_node,
            evidence_artifact_ids=last.evidence_artifact_ids,
            certificate_mode_role=last.certificate_mode_role,
            lean_text=witness_lean,
        )
    witness_block = (
        f"/-- Final certificate-mode witness for `{mode}`. -/\n"
        f"def SelectedCertificateModePredicate : Prop :=\n"
        f"  {witness_prop}\n\n"
        f"{witness_lean}\n\n"
    )

    required = certificate_mode_obligations(mode, events)
    missing = required - inventory
    if missing:
        raise CertificateModeEvidenceMissing(
            f"certificate mode {mode} missing required theorems in generated inventory: "
            f"{sorted(missing)}"
        )

    effect_frame_import = "import PFCore.EffectFrame\n" if mode == "EffectFrameCertificate" else ""
    transition_import = (
        "import PFCore.Transition\n"
        if mode in {"FramePreservedCertificate", "CompositionalExtensionCertificate"}
        else ""
    )
    compositional_import = (
        "import PFCore.Compositional\n"
        if mode == "CompositionalExtensionCertificate"
        else ""
    )
    effect_frame_doc = (
        "EffectFrameCertificate binds `actionEffectsInFrameD` against the independent "
        "`concreteDeclaredFrame` (v0: one global frame).\n"
        if mode == "EffectFrameCertificate"
        else ""
    )
    transition_doc = (
        "FramePreservedCertificate proves `stepState pre event = some post` for allows, "
        "deny identity transitions, frame validity at every post-state, and "
        "resource/active-principal/tenant/capability-frame update equalities "
        "(no `applyEvent` fallback).\n"
        if mode == "FramePreservedCertificate"
        else ""
    )
    compositional_doc = (
        "CompositionalExtensionCertificate (A6) proves `CompositionalSafeExtension`: "
        "safe prefix + EventSafe extension + successful `stepState` application + "
        "preserved FrameValid resource/capability frames => TraceSafe extended trace. "
        "Prefix-only TraceSafe chaining is the narrower `TracePrefixSafe` claim "
        "(experimental alias TracePrefixSafeCertificate); handoff/contract composition "
        "is included only when resolved evidence supplies those theorems.\n"
        if mode == "CompositionalExtensionCertificate"
        else ""
    )
    source = f"""import PFCore.Theorems
import PFCore.TraceCheck
import PFCore.State
import PFCore.NonInterference
import PFCore.Observational
import PFCore.ResourcePattern
{effect_frame_import}{transition_import}{compositional_import}
/-!
# Generated concrete trace proof for `{trace_id}`

Auto-generated by pcs-core pf-core lean-check. Do not edit by hand.
Certificate mode: `{mode}`.
Semantic projection hash: `{projection_hash}`.
{contract_note.strip()}
Trust-boundary hooks (tenant isolation, cross-tenant safety, TenantProjectionIsolation)
are discharged via proved links from `TraceSafe`. `TraceSafeRCertificate` additionally
discharges `concrete_trace_safe_r*` and per-event `concrete_action_resource_scope_*`.
Base `TraceSafe` / `ActionAdmissible` omit pattern discharge; `TraceSafeR` refines them.
{effect_frame_doc}{transition_doc}{compositional_doc}
Release-grade tool-use lean-check treats `TraceSafeRCertificate` as the sole supported
`LeanKernelChecked` path (refinement to base `TraceSafe` via `traceSafeR_implies_traceSafe`).
-/

namespace PFCore.Generated.{module}

{trace_body}

{contract_def_block}{handoff_block}{base_trace_safe}

{base_trace_safe_prop}

{base_allowed}

{event_theorem_block}{trust_boundary_block}{resource_scope_block}{contract_theorem_block}{mode_theorem_block}{witness_block}end PFCore.Generated.{module}
"""
    if projected_handoffs:
        lean_sequences = extract_lean_delegated_capability_sequences(source)
        assert_handoff_capability_fidelity(
            source_handoffs=handoffs,
            projected_handoffs=projected_handoffs,
            lean_capability_sequences=lean_sequences,
        )
    out_path.write_text(source, encoding="utf-8")
    proof_file_hash = f"sha256:{hashlib.sha256(out_path.read_bytes()).hexdigest()}"
    theorem_manifest = build_theorem_manifest(
        specs=ctx.specs,
        generated_module_name=module,
        proof_file_hash=proof_file_hash,
        semantic_projection_hash=projection_hash,
        certificate_mode=mode,
        final_witness_theorem="concrete_certificate_mode_witness",
        final_witness_proposition=witness_prop,
    )
    theorem_manifest_hash = str(theorem_manifest["theorem_manifest_digest"])
    manifest_path = out_dir / "PFCoreTheoremManifest.v0.json"
    write_theorem_manifest(theorem_manifest, manifest_path)
    # Also persist the projection next to the generated proof for replay/mutation tests.
    projection_path = out_dir / "PFCoreSemanticProjection.v0.json"
    projection_path.write_text(json.dumps(projection, indent=2), encoding="utf-8")
    # Deduplicate evidence paths while preserving order.
    seen_evidence: set[Path] = set()
    evidence_tuple: list[Path] = []
    for path in evidence_files:
        resolved = path if isinstance(path, Path) else Path(path)
        key = resolved.resolve() if resolved.exists() else resolved
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        evidence_tuple.append(resolved)
    return GeneratedLeanProof(
        path=out_path,
        theorem_names=frozenset(inventory),
        certificate_mode=mode,
        evidence_files=tuple(evidence_tuple),
        mode_witness_theorem="concrete_certificate_mode_witness",
        mode_witness_proposition=witness_prop,
        semantic_projection_hash=projection_hash,
        semantic_projection=projection,
        theorem_specs=tuple(ctx.specs),
        theorem_manifest=theorem_manifest,
        theorem_manifest_hash=theorem_manifest_hash,
        theorem_manifest_path=manifest_path,
    )


def validate_contracts_before_codegen(
    trace: Mapping[str, Any],
    *,
    trace_path: Path | None = None,
    contracts_dir: Path | None = None,
    resolved_evidence: Any | None = None,
) -> list[str]:
    """Return contract validation errors (empty when satisfied or no contract JSON)."""
    if not trace_has_contract_refs(trace):
        return []
    if resolved_evidence is not None:
        contracts = resolved_evidence.contracts_by_id
    else:
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
    try:
        pfcore_dir = pf_core_kernel_root()
    except FileNotFoundError:
        return []
    if not pfcore_dir.is_dir():
        return []
    paths = sorted(pfcore_dir.rglob("*.lean"))
    return [path for path in paths if "Generated" not in path.parts]


def pcs_kernel_lean_paths() -> list[Path]:
    """Sorted PCS Lean sources for PCS release-chain proof paths (excludes Generated/)."""
    try:
        pcs_dir = pcs_kernel_root()
    except FileNotFoundError:
        return []
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
    try:
        lean_project = require_lean_root()
    except FileNotFoundError:
        lean_project = resolve_lean_root() or Path()
    parts: list[bytes] = []
    toolchain = lean_project / "lean-toolchain"
    if toolchain.is_file():
        parts.append(toolchain.read_bytes())
    for rel in ("lakefile.lean", "lake-manifest.json"):
        path = lean_project / rel
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
    from pcs_core.safe_paths import UnsafePathError, resolve_contained_file

    parts: list[bytes] = []
    for rel in ("lean-toolchain", "lean/lean-toolchain"):
        try:
            path = resolve_contained_file(bundle_dir, rel)
        except UnsafePathError:
            continue
        parts.append(path.read_bytes())
        break
    for rel in ("lean/lakefile.lean", "lean/lake-manifest.json"):
        try:
            path = resolve_contained_file(bundle_dir, rel)
        except UnsafePathError:
            continue
        parts.append(path.read_bytes())
    entries = kernel_manifest.get("files")
    if isinstance(entries, list):
        kernel_root = bundle_dir / "kernel"
        for entry in sorted(entries, key=lambda item: str(item.get("path") or "")):
            if not isinstance(entry, dict):
                continue
            rel_path = str(entry.get("path") or "")
            if not rel_path:
                continue
            path = resolve_contained_file(
                kernel_root, rel_path, allowed_suffixes=frozenset({".lean"})
            )
            parts.append(path.read_bytes())
    if not parts:
        raise ValueError("bundle missing lean environment files for hash computation")
    return _hash_byte_parts(parts)


def proof_term_ref_from_path(path: Path) -> str:
    return proof_ref_from_path(path)
