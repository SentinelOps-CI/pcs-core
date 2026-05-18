"""Registry semantic-check catalog, enforcement layer, and audit helpers."""

from __future__ import annotations

from typing import Any, Literal

from pcs_core.registry_data import registry_entries, registry_semantic_check_ref

EnforcementLayer = Literal["artifact_validate", "release_chain", "consumer", "registry_metadata"]

# check_id -> how pcs-core enforces the rule in v0.1
CHECK_ENFORCEMENT: dict[str, EnforcementLayer] = {
    "source_commit_not_placeholder": "release_chain",
    "trace_hash_present": "artifact_validate",
    "source_commit_matches_release_manifest": "release_chain",
    "trace_hash_matches_runtime_receipt": "artifact_validate",
    "status_is_certificate_checked_for_release": "release_chain",
    "assumption_set_ref_present": "artifact_validate",
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
    "component_artifacts_match_release_pins": "release_chain",
    "status_matches_check_outcomes": "release_chain",
    "entries_cover_required_artifact_types": "registry_metadata",
}


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
        severity = str(check.get("severity") or "")
        exec_required = bool(check.get("execution_required_in_release_mode"))
        allowed_skip = bool(check.get("allowed_to_skip"))
        fatal_default, _ = default_execution_flags(severity)
        if fatal_default and not exec_required:
            errors.append(f"{ref}: execution_required_in_release_mode must be true")
        if fatal_default and allowed_skip:
            errors.append(f"{ref}: allowed_to_skip must be false for severity {severity}")
    return errors


def collect_release_blocking_refs() -> set[str]:
    refs: set[str] = set()
    for artifact_type, check in iter_registry_checks():
        if str(check.get("severity")) == "release_blocking":
            check_id = str(check.get("check_id"))
            refs.add(registry_semantic_check_ref(artifact_type, check_id))
    return refs


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


def audit_release_chain_registry_coverage(checks: list[dict[str, Any]]) -> list[str]:
    """Warn when release_blocking registry checks are not referenced by any chain check."""
    errors: list[str] = []
    blocking = collect_release_blocking_refs()
    referenced = collect_chain_registry_refs(checks)
    known = {registry_semantic_check_ref(at, str(ch["check_id"])) for at, ch in iter_registry_checks()}
    for ref in referenced:
        if ref not in known:
            errors.append(f"unknown registry_check_ref in release chain result: {ref}")
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
