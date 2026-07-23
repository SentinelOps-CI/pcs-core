"""Semantic validation for ProofObligation.v0 and LeanCheckResult.v0."""

from __future__ import annotations

from typing import Any

from pcs_core.lean_catalog import (
    KNOWN_OBLIGATION_KINDS,
    LEAN_THEOREM_CATALOG,
    OBLIGATION_KIND_THEOREM,
)


def validate_proof_obligation_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    from pcs_core.pcs_projection import validate_proof_obligation_projection

    errors.extend(validate_proof_obligation_projection(data))
    obligations = data.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        errors.append("ProofObligation.v0 requires non-empty obligations")
        return errors
    for index, entry in enumerate(obligations):
        if not isinstance(entry, dict):
            errors.append(f"obligations[{index}]: must be an object")
            continue
        kind = entry.get("kind")
        if not isinstance(kind, str) or kind not in KNOWN_OBLIGATION_KINDS:
            errors.append(
                f"obligations[{index}]: unknown kind {kind!r} (obligations_reference_known_kinds)",
            )
    return errors


def validate_lean_check_result_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = data.get("status")
    if status not in {"ProofChecked", "Rejected", "Stale"}:
        errors.append(f"LeanCheckResult.v0 invalid status {status!r}")
    claim_class = data.get("claim_class")
    if claim_class is not None and claim_class not in {
        "ProofChecked",
        "EnvelopeLeanChecked",
        "Rejected",
    }:
        errors.append(f"LeanCheckResult.v0 invalid claim_class {claim_class!r}")
    if claim_class == "LeanKernelChecked":
        errors.append(
            "LeanCheckResult.v0 PCS variant must not use claim_class LeanKernelChecked",
        )
    if claim_class == "EnvelopeLeanChecked":
        if data.get("lean_proof_checked") is not True:
            errors.append(
                "LeanCheckResult.v0 EnvelopeLeanChecked requires lean_proof_checked=true",
            )
        if not data.get("proof_term_ref"):
            errors.append(
                "LeanCheckResult.v0 EnvelopeLeanChecked requires proof_term_ref",
            )
        proj_hash = data.get("pcs_projection_manifest_hash")
        if not isinstance(proj_hash, str) or not proj_hash.startswith("sha256:"):
            errors.append(
                "LeanCheckResult.v0 EnvelopeLeanChecked requires pcs_projection_manifest_hash",
            )
    results = data.get("obligation_results")
    if not isinstance(results, list):
        errors.append("LeanCheckResult.v0 obligation_results must be an array")
        return errors
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            errors.append(f"obligation_results[{index}]: must be an object")
            continue
        theorem = item.get("lean_theorem")
        kind = item.get("kind")
        if isinstance(kind, str) and isinstance(theorem, str):
            expected = OBLIGATION_KIND_THEOREM.get(kind)
            if expected and theorem != expected:
                errors.append(
                    f"obligation_results[{index}]: lean_theorem {theorem!r} "
                    f"!= catalog {expected!r}",
                )
        if isinstance(theorem, str) and theorem not in LEAN_THEOREM_CATALOG:
            errors.append(
                f"obligation_results[{index}]: lean_theorem {theorem!r} not in catalog "
                "(lean_theorem_in_catalog)",
            )
    if status == "ProofChecked":
        for index, item in enumerate(results):
            if isinstance(item, dict) and item.get("status") != "passed":
                errors.append(
                    f"obligation_results[{index}]: status must be passed when "
                    "LeanCheckResult is ProofChecked",
                )
    return errors
