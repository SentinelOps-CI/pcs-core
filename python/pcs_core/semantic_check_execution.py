"""SemanticCheckExecution.v0 builder (executable registry contract)."""

from __future__ import annotations

from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.registry_data import registry_entries, registry_semantic_check_ref
from pcs_core.registry_semantics import (
    enrich_semantic_check,
    enforcement_layer,
    iter_registry_checks,
)

POLICY_ID = "pcs-semantic-check-execution-v0.1"
POLICY_VERSION = "0.1.0"

SEVERITY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "required": {
        "description": "Must run in release mode; failure is fatal.",
        "fatal_if_skipped_in_release_mode": True,
        "downstream_must_report_execution": True,
    },
    "optional": {
        "description": "May be skipped; failures are non-fatal.",
        "fatal_if_skipped_in_release_mode": False,
        "downstream_must_report_execution": False,
    },
    "warning_only": {
        "description": "Non-blocking advisory check.",
        "fatal_if_skipped_in_release_mode": False,
        "downstream_must_report_execution": False,
    },
    "release_blocking": {
        "description": "Must run in release mode; blocks Validated/ProofChecked status.",
        "fatal_if_skipped_in_release_mode": True,
        "downstream_must_report_execution": True,
    },
    "producer_responsible": {
        "description": "Runtime producer must execute and attest before handoff.",
        "fatal_if_skipped_in_release_mode": True,
        "downstream_must_report_execution": True,
    },
    "consumer_responsible": {
        "description": "Consumer must execute at import/admission time.",
        "fatal_if_skipped_in_release_mode": True,
        "downstream_must_report_execution": True,
    },
    "validator_responsible": {
        "description": "Release validator (pcs-core) must execute and cite in validation results.",
        "fatal_if_skipped_in_release_mode": True,
        "downstream_must_report_execution": True,
    },
}


def build_semantic_check_execution() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for artifact_type, check in iter_registry_checks():
        enriched = enrich_semantic_check(dict(check))
        checks.append(
            {
                "registry_ref": registry_semantic_check_ref(
                    artifact_type,
                    str(enriched["check_id"]),
                ),
                "artifact_type": artifact_type,
                "check_id": enriched["check_id"],
                "severity": enriched["severity"],
                "responsible_component": enriched["responsible_component"],
                "execution_required_in_release_mode": enriched[
                    "execution_required_in_release_mode"
                ],
                "allowed_to_skip": enriched["allowed_to_skip"],
                "enforcement_layer": enforcement_layer(enriched),
            },
        )
    checks.sort(key=lambda row: str(row["registry_ref"]))
    body: dict[str, Any] = {
        "schema_version": "v0",
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "severity_definitions": SEVERITY_DEFINITIONS,
        "checks": checks,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body

