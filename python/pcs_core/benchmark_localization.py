"""Failure-code to responsible-component mapping for benchmarks."""

from __future__ import annotations

FAILURE_CODE_TO_COMPONENT: dict[str, str] = {
    "manifest_missing": "release_manifest",
    "manifest_hash_mismatch": "hashing",
    "artifact_missing": "release_manifest",
    "trace_hash_mismatch": "hashing",
    "certificate_id_mismatch": "certificate_producer",
    "verified_input_hash_mismatch": "verifier",
    "signed_input_hash_mismatch": "hashing",
    "labtrust_commit_mismatch": "runtime_producer",
    "certifyedge_commit_mismatch": "certificate_producer",
    "provability_fabric_commit_mismatch": "verifier",
    "scientific_memory_commit_mismatch": "scientific_memory",
    "scientific_memory_import_failed": "scientific_memory",
    "legacy_import_detected": "scientific_memory",
    "placeholder_commit_detected": "runtime_producer",
    "schema_validation_failed": "registry",
    "registry_check_coverage_gap": "registry",
    "tool_trace_hash_mismatch": "certificate_producer",
    "unauthorized_tool_call": "runtime_producer",
    "rejected_certificate": "certificate_producer",
    "rejected_computation_witness": "certificate_producer",
    "witness_hash_mismatch": "hashing",
    "rejected_computation_witness": "certificate_producer",
    "unauthorized_tool_call": "runtime_producer",
    "tool_trace_hash_mismatch": "certificate_producer",
    "manifest_hash_mismatch": "hashing",
    "local_dev_detected": "runtime_producer",
    "missing_formal_artifacts": "formal_kernel",
    "formal_check_failed": "formal_kernel",
    "scientific_memory_render_incomplete": "scientific_memory",
    "unauthorized_release": "runtime_producer",
    "stale_trace_after_certificate": "runtime_producer",
    "scientific_memory_claim_id_mismatch": "scientific_memory",
    "placeholder_source_commit": "runtime_producer",
    "legacy_handoff_file": "handoff",
    "missing_qc": "runtime_producer",
    "lean_certificate_trace_hash_mismatch": "formal_kernel",
    "lean_certificate_stale": "formal_kernel",
    "lean_verified_input_hash_mismatch": "verifier",
    "lean_certificate_rejected": "formal_kernel",
}


REPAIR_HINT_BY_COMPONENT: dict[str, str] = {
    "runtime_producer": "align_provenance",
    "certificate_producer": "align_certificate_id",
    "verifier": "rerun_verification",
    "registry": "fix_registry_entry",
    "formal_kernel": "rerun_formal_check",
    "scientific_memory": "fix_import_report",
    "release_manifest": "align_provenance",
    "handoff": "align_handoff",
    "hashing": "align_hash",
    "unknown": "unknown",
}


def localize_failure_code(code: str) -> str:
    return FAILURE_CODE_TO_COMPONENT.get(code, "unknown")


def repair_hint_for_component(component: str | None) -> str | None:
    if not component:
        return None
    return REPAIR_HINT_BY_COMPONENT.get(component, "unknown")
