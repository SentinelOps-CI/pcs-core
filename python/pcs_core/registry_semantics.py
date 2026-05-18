"""Registry semantic-check catalog, enforcement layer, and audit helpers."""

from __future__ import annotations

from typing import Any, Literal

from pcs_core.registry_data import registry_entries, registry_semantic_check_ref

EnforcementLayer = Literal["artifact_validate", "release_chain", "consumer", "registry_metadata"]

# check_id -> how pcs-core enforces the rule in v0.1
CHECK_ENFORCEMENT: dict[str, EnforcementLayer] = {
    "source_commit_not_placeholder": "artifact_validate",
    "assumption_set_ref_present": "artifact_validate",
    "trace_hash_present": "artifact_validate",
    "source_commit_matches_release_manifest": "release_chain",
    "trace_hash_matches_runtime_receipt": "artifact_validate",
    "status_is_certificate_checked_for_release": "release_chain",
    "certificate_refs_resolve": "artifact_validate",
    "non_empty_runtime_receipts": "artifact_validate",
    "certified_bundle_has_certificate_when_checked": "artifact_validate",
    "verified_input_bundle_hash_matches_certified": "release_chain",
    "failed_checks_block_import_ready_status": "artifact_validate",
    "signed_input_bundle_hash_matches_certified": "release_chain",
    "embedded_bundle_passes_science_claim_semantics": "artifact_validate",
    "release_mode_commit_policy": "artifact_validate",
    "artifact_hashes_match_files": "release_chain",
    "handoff_input_hashes_when_validated": "artifact_validate",
    "component_artifacts_match_release_pins": "artifact_validate",
    "status_matches_check_outcomes": "release_chain",
    "entries_cover_required_artifact_types": "registry_metadata",
    "tool_trace_hash_matches_certificate": "artifact_validate",
    "certificate_status_checked_for_release": "release_chain",
    "policy_hash_matches_trace_policy": "artifact_validate",
    "policy_hash_matches_certificate": "artifact_validate",
    "signature_or_digest_valid": "artifact_validate",
    "no_unauthorized_tool_calls": "artifact_validate",
    "no_unknown_authorization_status": "artifact_validate",
    "required_registry_entries_registered": "registry_metadata",
}

DEFERRAL_REASONS: dict[str, str] = {
    "source_commit_not_placeholder": (
        "Verified during per-artifact validation of nested AssumptionSet and SourceSpan instances."
    ),
    "assumption_set_ref_present": (
        "Verified during per-artifact validation of ClaimArtifact instances in the release train."
    ),
    "handoff_input_hashes_when_validated": (
        "Executed via pcs conformance run --suite handoff-manifest during release qualification."
    ),
    "component_artifacts_match_release_pins": (
        "Executed via pcs conformance run --suite component-release-fragment during release qualification."
    ),
    "trace_hash_matches_runtime_receipt": (
        "Verified during per-artifact validation of TraceCertificate against RuntimeReceipt."
    ),
    "failed_checks_block_import_ready_status": (
        "Verified during per-artifact validation of VerificationResult instances."
    ),
    "certificate_refs_resolve": (
        "Producer-responsible check executed by LabTrust-Gym before EvidenceBundle handoff."
    ),
    "embedded_bundle_passes_science_claim_semantics": (
        "Producer-responsible check executed by Provability Fabric when signing bundles."
    ),
    "entries_cover_required_artifact_types": (
        "Executed via pcs registry audit and conformance run --suite artifact-registry."
    ),
    "status_matches_check_outcomes": (
        "Validator-responsible invariant enforced when constructing ReleaseChainValidationResult."
    ),
}

PCS_CORE_COMPONENT = "pcs-core"


def default_execution_flags(severity: str) -> tuple[bool, bool]:
    """Return (execution_required_in_release_mode, allowed_to_skip)."""
    if severity in {"optional", "warning_only"}:
        return False, True
    return True, False


def enrich_semantic_check(check: dict[str, Any]) -> dict[str, Any]:
    severity = str(check["severity"])
    required, skippable = default_execution_flags(severity)
    execution_required = bool(check.get("execution_required_in_release_mode", required))
    allowed_to_skip = bool(check.get("allowed_to_skip", skippable))
    if execution_required and allowed_to_skip:
        allowed_to_skip = False
    return {
        **check,
        "execution_required_in_release_mode": execution_required,
        "allowed_to_skip": allowed_to_skip,
    }


def enforcement_layer(check: dict[str, Any]) -> EnforcementLayer:
    severity = str(check.get("severity") or "")
    check_id = str(check.get("check_id") or "")
    if severity in {"consumer_responsible", "producer_responsible"}:
        return "consumer"
    if severity == "validator_responsible":
        return "release_chain"
    return CHECK_ENFORCEMENT.get(check_id, "release_chain")


def iter_registry_checks() -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for artifact_type, entry in registry_entries().items():
        for check in entry.get("semantic_checks", []):
            if isinstance(check, dict):
                rows.append((artifact_type, check))
    return rows


def audit_registry_catalog() -> list[str]:
    """Ensure every registry semantic check is classified and structurally valid."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for artifact_type, check in iter_registry_checks():
        check_id = check.get("check_id")
        if not isinstance(check_id, str) or not check_id:
            errors.append(f"{artifact_type}: semantic check missing check_id")
            continue
        ref = registry_semantic_check_ref(artifact_type, check_id)
        if ref in seen_ids:
            errors.append(f"duplicate semantic check ref {ref}")
        seen_ids.add(ref)
        layer = enforcement_layer(check)
        severity = str(check.get("severity") or "")
        if (
            check_id not in CHECK_ENFORCEMENT
            and layer not in {"consumer", "release_chain"}
            and severity != "validator_responsible"
        ):
            errors.append(
                f"{ref}: not listed in CHECK_ENFORCEMENT "
                "(add mapping or use consumer/producer_responsible severity)",
            )
        if not check.get("severity"):
            errors.append(f"{ref}: missing severity")
        if not check.get("responsible_component"):
            errors.append(f"{ref}: missing responsible_component")
        if "execution_required_in_release_mode" not in check:
            errors.append(f"{ref}: missing execution_required_in_release_mode")
        if "allowed_to_skip" not in check:
            errors.append(f"{ref}: missing allowed_to_skip")
        exec_required = bool(check.get("execution_required_in_release_mode"))
        allowed_skip = bool(check.get("allowed_to_skip"))
        fatal_default, _ = default_execution_flags(severity)
        if fatal_default and not exec_required:
            errors.append(f"{ref}: execution_required_in_release_mode must be true")
        if fatal_default and allowed_skip:
            errors.append(f"{ref}: allowed_to_skip must be false for severity {severity}")
    return errors


def collect_release_blocking_refs() -> set[str]:
    return collect_required_release_blocking_refs()


def collect_required_release_blocking_refs_for_artifact_types(
    artifact_types: set[str],
) -> set[str]:
    refs: set[str] = set()
    for artifact_type, entry in registry_entries().items():
        if artifact_type not in artifact_types:
            continue
        if not entry.get("release_mode_required", True):
            continue
        for check in entry.get("semantic_checks", []):
            if not isinstance(check, dict):
                continue
            if str(check.get("severity")) != "release_blocking":
                continue
            if not check.get("execution_required_in_release_mode", True):
                continue
            if check.get("allowed_to_skip", False):
                continue
            check_id = str(check.get("check_id"))
            refs.add(registry_semantic_check_ref(artifact_type, check_id))
    return refs


def collect_required_release_blocking_refs() -> set[str]:
    """Release-blocking checks for the default LabTrust QC workflow profile."""
    from pcs_core.workflow_profiles import required_release_blocking_refs_for_profile

    return required_release_blocking_refs_for_profile("labtrust.qc_release_v0.1")


def lookup_registry_check(registry_ref: str) -> tuple[str, dict[str, Any]] | None:
    marker = ".v0."
    if marker not in registry_ref:
        return None
    prefix, check_id = registry_ref.split(marker, 1)
    artifact_type = f"{prefix}.v0"
    entry = registry_entries().get(artifact_type)
    if not isinstance(entry, dict):
        return None
    for check in entry.get("semantic_checks", []):
        if isinstance(check, dict) and str(check.get("check_id")) == check_id:
            return artifact_type, check
    return None


def responsible_component_for_registry_refs(refs: frozenset[str] | tuple[str, ...]) -> str:
    if not refs:
        return PCS_CORE_COMPONENT
    first = sorted(refs)[0]
    found = lookup_registry_check(first)
    if found is not None:
        return str(found[1].get("responsible_component") or PCS_CORE_COMPONENT)
    return PCS_CORE_COMPONENT


def deferral_reason(check_id: str) -> str:
    return DEFERRAL_REASONS.get(
        check_id,
        "Executed outside the 30-check release-chain catalog at the cited enforcement location.",
    )


def build_deferred_registry_checks(chain_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Defer release-blocking checks not cited by release-chain checks."""
    cited = collect_chain_registry_refs(chain_checks)
    deferred: list[dict[str, Any]] = []
    for ref in sorted(collect_required_release_blocking_refs() - cited):
        found = lookup_registry_check(ref)
        if found is None:
            continue
        _artifact_type, check = found
        check_id = str(check.get("check_id"))
        layer = enforcement_layer(check)
        if layer == "release_chain":
            continue
        deferred.append(
            {
                "registry_ref": ref,
                "status": "deferred",
                "enforcement_location": layer,
                "responsible_component": str(
                    check.get("responsible_component") or PCS_CORE_COMPONENT,
                ),
                "reason": deferral_reason(check_id),
            },
        )
    return deferred


def collect_chain_registry_refs(checks: list[dict[str, Any]]) -> set[str]:
    refs: set[str] = set()
    for check in checks:
        if not isinstance(check, dict):
            continue
        raw = check.get("registry_check_refs")
        if isinstance(raw, list):
            for ref in raw:
                if isinstance(ref, str):
                    refs.add(ref)
    return refs


def audit_release_chain_registry_coverage(
    checks: list[dict[str, Any]],
    deferred_registry_checks: list[dict[str, Any]] | None = None,
    *,
    required_refs: set[str] | None = None,
) -> list[str]:
    """Ensure every release-blocking registry check is cited or properly deferred."""
    errors: list[str] = []
    required = (
        required_refs
        if required_refs is not None
        else collect_required_release_blocking_refs()
    )
    cited = collect_chain_registry_refs(checks)
    known = {registry_semantic_check_ref(at, str(ch["check_id"])) for at, ch in iter_registry_checks()}
    for ref in cited:
        if ref not in known:
            errors.append(f"unknown registry_check_ref in release chain result: {ref}")
    deferred_refs: set[str] = set()
    for index, item in enumerate(deferred_registry_checks or []):
        if not isinstance(item, dict):
            errors.append(f"deferred_registry_checks[{index}]: must be an object")
            continue
        ref = item.get("registry_ref")
        if not isinstance(ref, str) or not ref:
            errors.append(f"deferred_registry_checks[{index}]: registry_ref required")
            continue
        if ref not in known:
            errors.append(f"deferred_registry_checks[{index}]: unknown registry_ref {ref!r}")
        deferred_refs.add(ref)
        status = item.get("status")
        if status not in {"deferred", "skipped"}:
            errors.append(
                f"deferred_registry_checks[{index}]: status must be deferred or skipped",
            )
        if not item.get("enforcement_location"):
            errors.append(f"deferred_registry_checks[{index}]: enforcement_location required")
        if not item.get("responsible_component"):
            errors.append(f"deferred_registry_checks[{index}]: responsible_component required")
        if status == "deferred" and not item.get("reason"):
            errors.append(f"deferred_registry_checks[{index}]: reason required for deferred checks")
        found = lookup_registry_check(ref)
        if found is not None:
            _artifact_type, check = found
            layer = enforcement_layer(check)
            if layer == "release_chain" and status == "deferred":
                errors.append(
                    f"deferred_registry_checks[{index}]: release-chain enforcement "
                    f"cannot be deferred for {ref}",
                )
    covered = cited | deferred_refs
    for ref in sorted(required - covered):
        errors.append(
            f"release-blocking registry semantic check not cited or deferred: {ref}",
        )
    for ref in sorted(deferred_refs - required):
        if ref in cited:
            errors.append(
                f"deferred_registry_checks: {ref} is already cited by release-chain checks",
            )
    return errors


def audit_release_chain_ref_catalog() -> list[str]:
    """Every non-empty registry_check_refs entry in the chain catalog must be a registry ref."""
    from pcs_core.release_chain_registry_refs import RELEASE_CHAIN_REGISTRY_CHECK_REFS

    errors: list[str] = []
    known = {registry_semantic_check_ref(at, str(ch["check_id"])) for at, ch in iter_registry_checks()}
    for check_id, refs in RELEASE_CHAIN_REGISTRY_CHECK_REFS.items():
        for ref in refs:
            if ref not in known:
                errors.append(f"{check_id}: unknown registry_check_ref {ref}")
    return errors


def audit_release_blocking_chain_catalog_coverage() -> list[str]:
    """Release-blocking checks enforced at release_chain must be cited in the LabTrust chain catalog."""
    from pcs_core.release_chain_registry_refs import RELEASE_CHAIN_REGISTRY_CHECK_REFS
    from pcs_core.workflow_profiles import load_workflow_profile

    catalog_refs: set[str] = set()
    for refs in RELEASE_CHAIN_REGISTRY_CHECK_REFS.values():
        catalog_refs.update(refs)
    labtrust = load_workflow_profile("labtrust.qc_release_v0.1")
    scope_types: set[str] | None = None
    if labtrust is not None:
        entries = labtrust.get("required_registry_entries")
        if isinstance(entries, list):
            scope_types = {str(item) for item in entries}
    errors: list[str] = []
    for artifact_type, entry in registry_entries().items():
        if scope_types is not None and artifact_type not in scope_types:
            continue
        if not entry.get("release_mode_required", True):
            continue
        for check in entry.get("semantic_checks", []):
            if not isinstance(check, dict):
                continue
            if str(check.get("severity")) != "release_blocking":
                continue
            if not check.get("execution_required_in_release_mode", True):
                continue
            if check.get("allowed_to_skip", False):
                continue
            enriched = enrich_semantic_check(dict(check))
            if enforcement_layer(enriched) != "release_chain":
                continue
            ref = registry_semantic_check_ref(artifact_type, str(check["check_id"]))
            if ref not in catalog_refs:
                errors.append(
                    f"{ref}: release_blocking release_chain check missing from "
                    "RELEASE_CHAIN_REGISTRY_CHECK_REFS",
                )
    return errors


def audit_registry_enforcement() -> list[str]:
    """Full registry semantic catalog and release-chain mapping audits."""
    return [
        *audit_registry_catalog(),
        *audit_release_chain_ref_catalog(),
        *audit_release_blocking_chain_catalog_coverage(),
    ]
