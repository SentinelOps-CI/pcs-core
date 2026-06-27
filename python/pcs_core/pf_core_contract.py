"""PF-Core contract satisfaction runtime checker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from pcs_core.pf_core_runtime import expand_principal_capabilities
from pcs_core.validate import validate_schema


@dataclass(frozen=True)
class ContractIssue:
    code: str
    message: str
    path: str | None = None


def load_contract(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: contract root must be a JSON object")
    errors = validate_schema(data, "PFCoreContract.v0")
    if errors:
        raise ValueError(f"{path}: invalid PFCoreContract.v0: {'; '.join(errors)}")
    return data


def load_contracts(paths: list[Path]) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for path in paths:
        contract = load_contract(path)
        contract_id = str(contract["contract_id"])
        contracts[contract_id] = contract
    return contracts


def load_contracts_from_dir(directory: Path) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        if data.get("artifact_type") != "PFCoreContract.v0":
            continue
        errors = validate_schema(data, "PFCoreContract.v0")
        if errors:
            raise ValueError(f"{path}: invalid PFCoreContract.v0: {'; '.join(errors)}")
        contract_id = str(data["contract_id"])
        contracts[contract_id] = data
    return contracts


def _principal_has_capability(principal: Mapping[str, Any], capability_id: str) -> bool:
    return capability_id in expand_principal_capabilities(dict(principal))


def _action_has_effect(action: Mapping[str, Any], effect_kind: str) -> bool:
    effects = action.get("effects")
    if not isinstance(effects, list):
        return False
    return any(
        isinstance(effect, dict) and str(effect.get("effect_kind") or "") == effect_kind
        for effect in effects
    )


def _tenant_matches(principal: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    tenant = str(principal.get("tenant") or "")
    for key in ("reads", "writes"):
        resources = action.get(key)
        if not isinstance(resources, list):
            continue
        for resource in resources:
            if isinstance(resource, dict) and str(resource.get("tenant") or "") != tenant:
                return False
    return True


def validate_event_against_contract(
    event: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    path: str,
) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    pre = contract.get("pre")
    post = contract.get("post")
    principal = event.get("principal")
    action = event.get("action")
    if not isinstance(principal, dict) or not isinstance(action, dict):
        issues.append(ContractIssue("ContractEventInvalid", "event missing principal or action", path))
        return issues

    if isinstance(pre, dict):
        if pre.get("require_tenant_match") and not _tenant_matches(principal, action):
            issues.append(
                ContractIssue(
                    "ContractTenantMismatch",
                    f"contract {contract.get('contract_id')!r} requires tenant match",
                    path,
                )
            )
        required_cap = pre.get("require_capability")
        if isinstance(required_cap, str) and required_cap:
            if not _principal_has_capability(principal, required_cap):
                issues.append(
                    ContractIssue(
                        "ContractCapabilityRequired",
                        f"contract {contract.get('contract_id')!r} requires capability {required_cap!r}",
                        f"{path}.principal",
                    )
                )
        required_effect = pre.get("require_effect")
        if isinstance(required_effect, str) and required_effect:
            if not _action_has_effect(action, required_effect):
                issues.append(
                    ContractIssue(
                        "ContractEffectRequired",
                        f"contract {contract.get('contract_id')!r} requires effect {required_effect!r}",
                        f"{path}.action.effects",
                    )
                )
        required_role = pre.get("require_role")
        if isinstance(required_role, str) and required_role:
            roles = principal.get("roles")
            if not isinstance(roles, list) or required_role not in [str(role) for role in roles]:
                issues.append(
                    ContractIssue(
                        "ContractRoleRequired",
                        f"contract {contract.get('contract_id')!r} requires role {required_role!r}",
                        f"{path}.principal.roles",
                    )
                )
        required_policy = pre.get("require_policy_ref")
        if isinstance(required_policy, str) and required_policy:
            refs = event.get("contract_refs")
            if not isinstance(refs, list) or required_policy not in [str(ref) for ref in refs]:
                issues.append(
                    ContractIssue(
                        "ContractPolicyRefRequired",
                        f"contract {contract.get('contract_id')!r} requires policy ref {required_policy!r}",
                        f"{path}.contract_refs",
                    )
                )
        required_evidence = pre.get("require_evidence_ref")
        if isinstance(required_evidence, str) and required_evidence:
            evidence = event.get("evidence_refs")
            if not isinstance(evidence, list) or required_evidence not in [
                str(ref) for ref in evidence
            ]:
                issues.append(
                    ContractIssue(
                        "ContractEvidenceRefRequired",
                        f"contract {contract.get('contract_id')!r} requires evidence ref {required_evidence!r}",
                        f"{path}.evidence_refs",
                    )
                )

    if isinstance(post, dict):
        required_decision = post.get("require_decision")
        if isinstance(required_decision, str) and required_decision:
            decision = str(event.get("decision") or "")
            if decision != required_decision:
                issues.append(
                    ContractIssue(
                        "ContractDecisionMismatch",
                        f"contract {contract.get('contract_id')!r} requires decision {required_decision!r}, "
                        f"got {decision!r}",
                        f"{path}.decision",
                    )
                )
        if post.get("require_event_safe") is True:
            decision = str(event.get("decision") or "")
            if decision == "allow":
                cap = action.get("capability")
                cap_id = str(cap.get("capability_id") or "") if isinstance(cap, dict) else ""
                if not cap_id or not _principal_has_capability(principal, cap_id):
                    issues.append(
                        ContractIssue(
                            "ContractEventUnsafe",
                            f"allowed event violates contract {contract.get('contract_id')!r} event safety",
                            path,
                        )
                    )
                elif not _tenant_matches(principal, action):
                    issues.append(
                        ContractIssue(
                            "ContractEventUnsafe",
                            f"allowed event violates contract {contract.get('contract_id')!r} tenant safety",
                            path,
                        )
                    )

    return issues


def validate_trace_contracts(
    trace: Mapping[str, Any],
    contracts: Mapping[str, Mapping[str, Any]],
) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    events = trace.get("events")
    if not isinstance(events, list):
        return [ContractIssue("TraceInvalid", "events must be an array", "events")]

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        base = f"events[{index}]"
        refs = event.get("contract_refs")
        if not isinstance(refs, list) or not refs:
            continue
        for ref_index, ref in enumerate(refs):
            contract_id = str(ref)
            contract = contracts.get(contract_id)
            if contract is None:
                issues.append(
                    ContractIssue(
                        "ContractRefMissing",
                        f"unknown contract reference {contract_id!r}",
                        f"{base}.contract_refs[{ref_index}]",
                    )
                )
                continue
            issues.extend(
                validate_event_against_contract(event, contract, path=base)
            )
    return issues
