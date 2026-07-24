"""Semantic validation for Verifier Assurance (VA) *.v1 artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pcs_core.hash import SIGNATURE_FIELD, canonical_hash
from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate_detect import ValidationError, validate_schema

VA_ARTIFACT_TYPES = frozenset(
    {
        "VerifierProfile.v1",
        "VerificationResult.v1",
        "VerifierInvocationRecord.v1",
        "VerifierReplayReport.v1",
        "VerifierMutationManifest.v1",
        "RewardEvidenceEnvelope.v1",
        "OptimizationCampaignManifest.v1",
        "AdjudicationRecord.v1",
        "VerifierAssuranceReport.v1",
    }
)

# OVK pin surface: profile, result, invocation, replay, mutation.
OVK_VA_ARTIFACT_TYPES = frozenset(
    {
        "VerifierProfile.v1",
        "VerificationResult.v1",
        "VerifierInvocationRecord.v1",
        "VerifierReplayReport.v1",
        "VerifierMutationManifest.v1",
    }
)

_INDETERMINATE = frozenset(
    {
        "indeterminate",
        "indeterminate_insufficient_evidence",
        "indeterminate_execution_error",
        "indeterminate_out_of_scope",
        "indeterminate_configuration_drift",
        # Legacy / producer dialects collapsed to indeterminate buckets
        "indeterminate_missing_checker",
        "indeterminate_timeout",
        "indeterminate_parser_failure",
        "indeterminate_unsupported_input",
        "indeterminate_external_service_error",
        "indeterminate_missing_evidence",
        "indeterminate_domain_disagreement",
    }
)


@dataclass(frozen=True)
class VaValidationContext:
    """Optional multi-artifact context for cross-file semantic rules."""

    profiles: tuple[dict[str, Any], ...] = ()
    results: tuple[dict[str, Any], ...] = ()
    campaign: dict[str, Any] | None = None
    rewards: tuple[dict[str, Any], ...] = ()


def _profile_body_digest(profile: dict[str, Any]) -> str:
    body = {k: v for k, v in profile.items() if k != "integrity"}
    return canonical_hash(body)


def _index_profiles(
    profiles: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        pid = profile.get("verifier_profile_id")
        if isinstance(pid, str):
            out[pid] = profile
    return out


def _index_results(
    results: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for result in results:
        rid = result.get("verification_result_id") or result.get("result_id")
        if isinstance(rid, str):
            out[rid] = result
    return out

_GUARANTEE_RANK: dict[str, int] = {
    "unchecked_advisory": 0,
    "observational": 1,
    "runtime_observed": 1,
    "empirically_measured": 2,
    "human_reviewed": 3,
    "certificate_checked": 4,
    "formally_checked": 5,
}

_SECRET_KEY_HINTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "private_key",
    "access_key",
)


@dataclass(frozen=True)
class SemanticIssue:
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


def _as_strings(issues: list[SemanticIssue] | list[str], *, as_issues: bool) -> list[Any]:
    if as_issues:
        return issues
    return [str(i) for i in issues]


def _forbid_legacy_signature_field(
    data: dict[str, Any], artifact_type: str
) -> list[SemanticIssue]:
    if SIGNATURE_FIELD in data:
        return [
            SemanticIssue(
                "LegacySignatureOrDigest",
                SIGNATURE_FIELD,
                f"{artifact_type}: {SIGNATURE_FIELD} is forbidden on VA *.v1 roots",
            )
        ]
    return []


def _require_integrity(data: dict[str, Any], artifact_type: str) -> list[SemanticIssue]:
    integrity = data.get("integrity")
    if not isinstance(integrity, dict):
        return [
            SemanticIssue(
                "MissingIntegrity",
                "integrity",
                f"{artifact_type}: nested integrity envelope is required",
            )
        ]
    issues: list[SemanticIssue] = []
    if integrity.get("canonicalization_version") != "v1":
        issues.append(
            SemanticIssue(
                "BadCanonicalizationVersion",
                "integrity.canonicalization_version",
                "must be v1",
            )
        )
    digest = integrity.get("artifact_digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        issues.append(
            SemanticIssue(
                "BadArtifactDigest",
                "integrity.artifact_digest",
                "must be sha256:<64 hex>",
            )
        )
    return issues


def _check_zero_commit(commit: Any, path: str) -> list[SemanticIssue]:
    if isinstance(commit, str) and commit == "0" * 40:
        return [
            SemanticIssue("PlaceholderCommit", path, "placeholder zero git commit rejected")
        ]
    return []


def _check_secret_leaks(env_entries: Any, path: str) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    if not isinstance(env_entries, dict):
        return issues
    for key, value in env_entries.items():
        key_l = str(key).lower()
        if any(hint in key_l for hint in _SECRET_KEY_HINTS):
            issues.append(
                SemanticIssue(
                    "SecretKeyName",
                    f"{path}.{key}",
                    f"redacted_environment key {key!r} looks like a secret name",
                )
            )
        if isinstance(value, str):
            value_l = value.lower()
            if value.startswith("sk-") or "begin private key" in value_l:
                issues.append(
                    SemanticIssue(
                        "SecretValue",
                        f"{path}.{key}",
                        "value appears to contain a secret",
                    )
                )
    return issues


def _parse_decimal(value: Any, path: str) -> tuple[Decimal | None, list[SemanticIssue]]:
    if not isinstance(value, str):
        return None, [SemanticIssue("DecimalType", path, "decimal values must be strings")]
    try:
        return Decimal(value), []
    except (InvalidOperation, ValueError):
        return None, [SemanticIssue("DecimalParse", path, f"invalid decimal string {value!r}")]


def validate_verifier_profile_semantics(
    data: dict[str, Any], *, as_issues: bool = False
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "VerifierProfile.v1")
    issues.extend(_require_integrity(data, "VerifierProfile.v1"))
    commit = data.get("source_commit")
    if not isinstance(commit, str) or len(commit) != 40 or any(
        c not in "0123456789abcdef" for c in commit
    ):
        issues.append(
            SemanticIssue(
                "InvalidSourceCommit",
                "source_commit",
                "source_commit must be a full 40-char lowercase hex SHA",
            )
        )
    issues.extend(_check_zero_commit(commit, "source_commit"))
    configuration = data.get("configuration")
    if isinstance(configuration, dict):
        for key in (
            "policy_digest",
            "model_digest",
            "prompt_digest",
            "resource_limit_digest",
        ):
            if key not in configuration:
                issues.append(
                    SemanticIssue(
                        "MissingNullDigestSlot",
                        f"configuration.{key}",
                        "inapplicable config digests must be present as explicit null",
                    )
                )
    impl = data.get("implementation")
    if isinstance(impl, dict) and not impl.get("implementation_digest"):
        issues.append(
            SemanticIssue(
                "MissingImplementationDigest",
                "implementation.implementation_digest",
                "implementation_digest is required",
            )
        )
    applicability = data.get("applicability")
    if isinstance(applicability, dict):
        status = applicability.get("status")
        if status == "revoked" and not applicability.get("revocation_reason"):
            issues.append(
                SemanticIssue(
                    "MissingRevocationReason",
                    "applicability.revocation_reason",
                    "revoked profiles require revocation_reason",
                )
            )
        if status == "superseded" and not applicability.get("superseded_by_profile_id"):
            issues.append(
                SemanticIssue(
                    "MissingSupersededBy",
                    "applicability.superseded_by_profile_id",
                    "superseded profiles require superseded_by_profile_id",
                )
            )
    redacted = data.get("redacted_environment")
    if isinstance(redacted, dict):
        issues.extend(_check_secret_leaks(redacted.get("entries"), "redacted_environment.entries"))
    schema_doc = data.get("configuration_schema")
    schema_digest = data.get("configuration_schema_digest")
    if isinstance(schema_doc, dict) and isinstance(schema_digest, str):
        try:
            recomputed = canonical_hash(schema_doc)
        except Exception as exc:  # noqa: BLE001
            issues.append(
                SemanticIssue("ConfigSchemaUnhashable", "configuration_schema", str(exc))
            )
        else:
            if recomputed != schema_digest:
                issues.append(
                    SemanticIssue(
                        "ConfigSchemaDigestMismatch",
                        "configuration_schema_digest",
                        f"recorded {schema_digest!r} != recomputed {recomputed!r}",
                    )
                )
    return _as_strings(issues, as_issues=as_issues)


def validate_verification_result_semantics(
    data: dict[str, Any],
    *,
    as_issues: bool = False,
    context: VaValidationContext | None = None,
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "VerificationResult.v1")
    issues.extend(_require_integrity(data, "VerificationResult.v1"))
    commit = data.get("source_commit")
    if not isinstance(commit, str) or len(commit) != 40 or any(
        c not in "0123456789abcdef" for c in commit
    ):
        issues.append(
            SemanticIssue(
                "InvalidSourceCommit",
                "source_commit",
                "source_commit must be a full 40-char lowercase hex SHA",
            )
        )
    decision = data.get("decision")
    execution_status = data.get("execution_status")
    fail_closed = {
        "timeout",
        "unavailable",
        "malformed_input",
        "unsupported_scope",
        "error",
        "cancelled",
        "resource_exhausted",
    }
    if execution_status in fail_closed and decision in {"accept", "reject"}:
        issues.append(
            SemanticIssue(
                "FailClosedDecision",
                "decision",
                f"execution_status {execution_status!r} cannot yield accept/reject",
            )
        )
    if data.get("normalization_applied") is True:
        raw = data.get("raw_backend_output_digest")
        normalized = data.get("normalized_result_digest")
        if not isinstance(raw, str) or not isinstance(normalized, str):
            issues.append(
                SemanticIssue(
                    "MissingNormalizationDigests",
                    "normalized_result_digest",
                    "normalization_applied requires raw and normalized digests",
                )
            )
        elif raw == normalized:
            issues.append(
                SemanticIssue(
                    "IdenticalNormalizationDigests",
                    "normalized_result_digest",
                    "raw and normalized digests must be distinct when normalization occurs",
                )
            )
    mandatory_failed = False
    for g_index, group in enumerate(data.get("check_groups") or []):
        if not isinstance(group, dict):
            continue
        for c_index, check in enumerate(group.get("checks") or []):
            if not isinstance(check, dict):
                continue
            if check.get("mandatory") is True and check.get("status") == "failed":
                mandatory_failed = True
            if check.get("status") == "skipped" and not (
                check.get("reason_code") or check.get("skip_reason_code")
            ):
                issues.append(
                    SemanticIssue(
                        "MissingSkipReason",
                        f"check_groups[{g_index}].checks[{c_index}].reason_code",
                        "skipped checks require reason_code",
                    )
                )
    if decision == "accept" and mandatory_failed:
        issues.append(
            SemanticIssue(
                "AcceptWithMandatoryFailure",
                "decision",
                "accept cannot coexist with a mandatory failed check",
            )
        )
    declared = data.get("declared_input_guarantee_class")
    result_class = data.get("guarantee_class")
    if isinstance(declared, str) and isinstance(result_class, str):
        if declared in _GUARANTEE_RANK and result_class in _GUARANTEE_RANK:
            if _GUARANTEE_RANK[result_class] > _GUARANTEE_RANK[declared]:
                issues.append(
                    SemanticIssue(
                        "GuaranteeUpgrade",
                        "guarantee_class",
                        f"must not upgrade declared_input_guarantee_class ({declared!r} -> {result_class!r})",
                    )
                )
    # Rule 1: profile refs resolve; digests match when profile bodies supplied.
    if context is not None and context.profiles:
        pref = data.get("verifier_profile")
        if isinstance(pref, dict):
            profile_id = pref.get("verifier_profile_id")
            recorded = pref.get("profile_digest")
            by_id = _index_profiles(context.profiles)
            if not isinstance(profile_id, str) or profile_id not in by_id:
                issues.append(
                    SemanticIssue(
                        "ProfileRefUnresolved",
                        "verifier_profile.verifier_profile_id",
                        f"profile {profile_id!r} not found in supplied profiles",
                    )
                )
            else:
                recomputed = _profile_body_digest(by_id[profile_id])
                if isinstance(recorded, str) and recorded != recomputed:
                    issues.append(
                        SemanticIssue(
                            "ProfileDigestMismatch",
                            "verifier_profile.profile_digest",
                            f"recorded {recorded!r} != recomputed {recomputed!r}",
                        )
                    )
    return _as_strings(issues, as_issues=as_issues)


def validate_verification_result_v1_semantics(
    data: dict[str, Any],
    *,
    as_issues: bool = False,
    context: VaValidationContext | None = None,
) -> list[Any]:
    return validate_verification_result_semantics(
        data, as_issues=as_issues, context=context
    )


def validate_reward_envelope_semantics(
    data: dict[str, Any],
    *,
    as_issues: bool = False,
    context: VaValidationContext | None = None,
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "RewardEvidenceEnvelope.v1")
    issues.extend(_require_integrity(data, "RewardEvidenceEnvelope.v1"))
    issues.extend(_check_zero_commit(data.get("source_commit"), "source_commit"))
    total, total_issues = _parse_decimal(data.get("scalar_total"), "scalar_total")
    issues.extend(total_issues)
    components = data.get("components")
    if isinstance(components, list) and total is not None:
        composition = data.get("composition_function")
        if composition == "sum":
            acc = Decimal("0")
            for index, component in enumerate(components):
                if not isinstance(component, dict):
                    continue
                value, value_issues = _parse_decimal(
                    component.get("value"), f"components[{index}].value"
                )
                issues.extend(value_issues)
                if value is not None:
                    acc += value
            if acc != total:
                issues.append(
                    SemanticIssue(
                        "RewardCompositionMismatch",
                        "scalar_total",
                        f"sum of components {acc} != scalar_total {total}",
                    )
                )
    claims_issued = data.get("claims_issued") or []
    if isinstance(claims_issued, list) and claims_issued:
        refs = data.get("verifier_result_refs") or []
        if not isinstance(refs, list) or not refs:
            issues.append(
                SemanticIssue(
                    "ClaimsNeedVerifierRefs",
                    "verifier_result_refs",
                    "claims_issued requires at least one verifier_result_ref",
                )
            )
    lifecycle = data.get("lifecycle") if isinstance(data.get("lifecycle"), dict) else {}
    lifecycle_status = lifecycle.get("status")
    migration = lifecycle.get("migration_record_id")
    for index, pref in enumerate(data.get("profile_refs") or []):
        if not isinstance(pref, dict):
            continue
        status = pref.get("applicability_status")
        if status in {"revoked", "expired"} and lifecycle_status == "active" and not migration:
            issues.append(
                SemanticIssue(
                    "RevokedProfileGate",
                    f"profile_refs[{index}]",
                    f"{status} profiles cannot support new active rewards without migration_record_id",
                )
            )
        elif status == "revoked" and lifecycle_status != "active":
            # Still gate revoked refs on non-active envelopes that claim issued positive rewards.
            if claims_issued:
                issues.append(
                    SemanticIssue(
                        "RevokedProfileGate",
                        f"profile_refs[{index}]",
                        "revoked profiles cannot authorize reward claims",
                    )
                )
    mandatory_unresolved = data.get("mandatory_unresolved_claim_ids") or []
    if (
        lifecycle_status == "active"
        and isinstance(mandatory_unresolved, list)
        and mandatory_unresolved
    ):
        issues.append(
            SemanticIssue(
                "ActiveRewardUnresolvedClaims",
                "mandatory_unresolved_claim_ids",
                "unresolved mandatory claims block active release-grade envelopes",
            )
        )
    # Rule 2: reward trajectory digests match supporting results when results supplied.
    if context is not None and context.results:
        by_id = _index_results(context.results)
        reward_traj = data.get("trajectory_digest")
        for index, ref in enumerate(data.get("verifier_result_refs") or []):
            if not isinstance(ref, dict):
                continue
            rid = ref.get("artifact_id")
            if not isinstance(rid, str) or rid not in by_id:
                issues.append(
                    SemanticIssue(
                        "RewardResultRefUnresolved",
                        f"verifier_result_refs[{index}]",
                        f"result {rid!r} not found in supplied results",
                    )
                )
                continue
            result = by_id[rid]
            result_traj = result.get("trajectory_digest")
            if (
                isinstance(reward_traj, str)
                and isinstance(result_traj, str)
                and reward_traj != result_traj
            ):
                issues.append(
                    SemanticIssue(
                        "RewardTrajectoryMismatch",
                        f"verifier_result_refs[{index}]",
                        "reward trajectory_digest must match supporting VerificationResult",
                    )
                )
    # Rule 10: env/policy/model/verifier/campaign versions consistent when cross-checked.
    if context is not None and context.campaign is not None:
        camp_env = context.campaign.get("env_profile_id")
        camp_ver = context.campaign.get("env_profile_version")
        if (
            isinstance(camp_env, str)
            and isinstance(data.get("env_profile_id"), str)
            and camp_env != data.get("env_profile_id")
        ):
            issues.append(
                SemanticIssue(
                    "CrossArtifactVersionMismatch",
                    "env_profile_id",
                    "reward env_profile_id must match campaign env_profile_id",
                )
            )
        if (
            isinstance(camp_ver, str)
            and isinstance(data.get("env_profile_version"), str)
            and camp_ver != data.get("env_profile_version")
        ):
            issues.append(
                SemanticIssue(
                    "CrossArtifactVersionMismatch",
                    "env_profile_version",
                    "reward env_profile_version must match campaign env_profile_version",
                )
            )
    if context is not None and context.profiles:
        by_profile = _index_profiles(context.profiles)
        for p_index, pref in enumerate(data.get("profile_refs") or []):
            if not isinstance(pref, dict):
                continue
            pid = pref.get("verifier_profile_id")
            recorded = pref.get("profile_digest")
            if not isinstance(pid, str) or pid not in by_profile:
                issues.append(
                    SemanticIssue(
                        "ProfileRefUnresolved",
                        f"profile_refs[{p_index}]",
                        f"profile {pid!r} not found in supplied profiles",
                    )
                )
            elif isinstance(recorded, str):
                recomputed = _profile_body_digest(by_profile[pid])
                if recorded != recomputed:
                    issues.append(
                        SemanticIssue(
                            "ProfileDigestMismatch",
                            f"profile_refs[{p_index}].profile_digest",
                            f"recorded {recorded!r} != recomputed {recomputed!r}",
                        )
                    )
                status = by_profile[pid].get("applicability", {})
                if isinstance(status, dict):
                    app_status = status.get("status")
                    if (
                        app_status in {"revoked", "expired"}
                        and lifecycle_status == "active"
                        and not migration
                    ):
                        issues.append(
                            SemanticIssue(
                                "RevokedProfileGate",
                                f"profile_refs[{p_index}]",
                                f"profile body status {app_status!r} blocks active rewards",
                            )
                        )
    return _as_strings(issues, as_issues=as_issues)


def validate_campaign_manifest_semantics(
    data: dict[str, Any], *, as_issues: bool = False
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "OptimizationCampaignManifest.v1")
    issues.extend(_require_integrity(data, "OptimizationCampaignManifest.v1"))
    issues.extend(_check_zero_commit(data.get("source_commit"), "source_commit"))
    if not data.get("access_class"):
        issues.append(
            SemanticIssue("AccessClassRequired", "access_class", "access_class is required")
        )
    cohorts = data.get("cohorts")
    if isinstance(cohorts, list):
        for index, cohort in enumerate(cohorts):
            if not isinstance(cohort, dict):
                continue
            exposure = cohort.get("compute_exposure")
            if not isinstance(exposure, dict):
                issues.append(
                    SemanticIssue(
                        "CohortComputeExposure",
                        f"cohorts[{index}].compute_exposure",
                        "compute_exposure is required",
                    )
                )
            if not cohort.get("access_class"):
                issues.append(
                    SemanticIssue(
                        "CohortAccessClass",
                        f"cohorts[{index}].access_class",
                        "every cohort must declare access_class",
                    )
                )
    return _as_strings(issues, as_issues=as_issues)


def validate_adjudication_record_semantics(
    data: dict[str, Any],
    *,
    release_grade: bool = False,
    as_issues: bool = False,
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "AdjudicationRecord.v1")
    issues.extend(_require_integrity(data, "AdjudicationRecord.v1"))
    issues.extend(_check_zero_commit(data.get("source_commit"), "source_commit"))
    protected = data.get("protected_rationale")
    if isinstance(protected, dict):
        if not protected.get("commitment_digest"):
            issues.append(
                SemanticIssue(
                    "RationaleCommitment",
                    "protected_rationale.commitment_digest",
                    "commitment_digest is required",
                )
            )
    if release_grade and data.get("independence_declared") is not True:
        issues.append(
            SemanticIssue(
                "IndependenceForReleaseGrade",
                "independence_declared",
                "release-grade adjudication requires independence_declared=true",
            )
        )
    return _as_strings(issues, as_issues=as_issues)


def validate_assurance_report_semantics(
    data: dict[str, Any], *, as_issues: bool = False
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "VerifierAssuranceReport.v1")
    issues.extend(_require_integrity(data, "VerifierAssuranceReport.v1"))
    issues.extend(_check_zero_commit(data.get("source_commit"), "source_commit"))
    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        sample = metrics.get("sample_size")
        excluded = metrics.get("excluded_count")
        unadj = metrics.get("unadjudicated_count")
        if (
            isinstance(sample, int)
            and isinstance(excluded, int)
            and isinstance(unadj, int)
            and excluded + unadj > sample
            and sample > 0
        ):
            issues.append(
                SemanticIssue(
                    "AggregateCountReconcile",
                    "metrics",
                    "excluded_count + unadjudicated_count exceeds sample_size",
                )
            )
        for key in (
            "false_accept_rate",
            "false_reject_rate",
            "abstention_rate",
            "adjudication_coverage",
        ):
            rate = metrics.get(key)
            if isinstance(rate, dict):
                ci = rate.get("confidence_interval")
                if not isinstance(ci, dict) or not ci.get("method"):
                    issues.append(
                        SemanticIssue(
                            "CIMethodsDeclared",
                            f"metrics.{key}.confidence_interval.method",
                            "CI method must be declared",
                        )
                    )
                elif not isinstance(ci.get("parameters"), dict):
                    issues.append(
                        SemanticIssue(
                            "CIParametersDeclared",
                            f"metrics.{key}.confidence_interval.parameters",
                            "CI parameters must be declared (no silent denominator invention)",
                        )
                    )
        gap = metrics.get("optimization_gap")
        gap_nonzero = isinstance(gap, str) and gap not in {"0", "0.0", "0.000000"}
        ordinary = metrics.get("ordinary_accept_rate")
        optimized = metrics.get("optimized_accept_rate")
        both_cohort_rates = (
            isinstance(ordinary, dict)
            and isinstance(optimized, dict)
            and (ordinary.get("denominator") or 0) > 0
            and (optimized.get("denominator") or 0) > 0
        )
        claims_gap = gap_nonzero or both_cohort_rates
    else:
        claims_gap = False

    # Rule 12: excluded/unadjudicated remain visible and count-matched.
    excluded_items = data.get("excluded_items")
    unadj_items = data.get("unadjudicated_items")
    if isinstance(metrics, dict):
        if isinstance(excluded_items, list) and isinstance(metrics.get("excluded_count"), int):
            if len(excluded_items) != metrics["excluded_count"]:
                issues.append(
                    SemanticIssue(
                        "ExcludedItemsVisible",
                        "excluded_items",
                        "excluded_count must equal len(excluded_items)",
                    )
                )
        elif metrics.get("excluded_count"):
            issues.append(
                SemanticIssue(
                    "ExcludedItemsVisible",
                    "excluded_items",
                    "excluded_count > 0 requires visible excluded_items",
                )
            )
        if isinstance(unadj_items, list) and isinstance(metrics.get("unadjudicated_count"), int):
            if len(unadj_items) != metrics["unadjudicated_count"]:
                issues.append(
                    SemanticIssue(
                        "UnadjudicatedItemsVisible",
                        "unadjudicated_items",
                        "unadjudicated_count must equal len(unadjudicated_items)",
                    )
                )
        elif metrics.get("unadjudicated_count"):
            issues.append(
                SemanticIssue(
                    "UnadjudicatedItemsVisible",
                    "unadjudicated_items",
                    "unadjudicated_count > 0 requires visible unadjudicated_items",
                )
            )

    if data.get("release_grade") is True and data.get("independent_adjudication") is not True:
        issues.append(
            SemanticIssue(
                "ReleaseGradeAdjudication",
                "independent_adjudication",
                "release-grade reports require independent_adjudication=true",
            )
        )

    cohorts = data.get("cohorts") or []
    has_ordinary = False
    has_optimized = False
    for index, cohort in enumerate(cohorts):
        if not isinstance(cohort, dict):
            continue
        kind = cohort.get("cohort_kind")
        if kind == "ordinary":
            has_ordinary = True
        if kind == "optimized":
            has_optimized = True
        if not cohort.get("access_class"):
            issues.append(
                SemanticIssue(
                    "CohortAccessClass",
                    f"cohorts[{index}].access_class",
                    "every cohort must declare access_class",
                )
            )
        exposure = cohort.get("compute_exposure")
        if not isinstance(exposure, dict):
            issues.append(
                SemanticIssue(
                    "CohortComputeExposure",
                    f"cohorts[{index}].compute_exposure",
                    "every cohort must declare compute_exposure",
                )
            )
        accept = cohort.get("accept_count")
        reject = cohort.get("reject_count")
        indeterminate = cohort.get("indeterminate_count")
        included = cohort.get("included_result_count")
        if all(isinstance(v, int) for v in (accept, reject, indeterminate, included)):
            if accept + reject + indeterminate != included:  # type: ignore[operator]
                issues.append(
                    SemanticIssue(
                        "CohortCountMismatch",
                        f"cohorts[{index}]",
                        "aggregate counts must reconcile exactly with included records",
                    )
                )
            if accept < 0 or reject < 0 or indeterminate < 0:  # type: ignore[operator]
                issues.append(
                    SemanticIssue(
                        "IndeterminateMisclassification",
                        f"cohorts[{index}]",
                        "cohort decision counts must be non-negative distinct buckets",
                    )
                )
            # Rule 15: indeterminate never folded into accept/reject (detect over-claim).
            if included > 0 and indeterminate == 0 and accept + reject > included:  # type: ignore[operator]
                issues.append(
                    SemanticIssue(
                        "IndeterminateMisclassification",
                        f"cohorts[{index}]",
                        "indeterminate decisions must not be counted as accept/reject",
                    )
                )
    # Rule 5: optimization-gap needs ordinary + optimized cohorts.
    if claims_gap and not (has_ordinary and has_optimized):
        issues.append(
            SemanticIssue(
                "OptimizationGapCohorts",
                "cohorts",
                "optimization-gap metrics require ordinary and optimized cohorts",
            )
        )
    return _as_strings(issues, as_issues=as_issues)


def validate_va_semantics(
    data: dict[str, Any],
    artifact_type: str,
    *,
    as_issues: bool = False,
    context: VaValidationContext | None = None,
) -> list[str] | list[SemanticIssue]:
    """Dispatch used by validate_semantics for all VA *.v1 types."""
    return validate_verifier_assurance_semantics(
        data, artifact_type, as_issues=as_issues, context=context
    )



def validate_invocation_record_semantics(
    data: dict[str, Any], *, as_issues: bool = False
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "VerifierInvocationRecord.v1")
    issues.extend(_require_integrity(data, "VerifierInvocationRecord.v1"))
    raw = data.get("raw_backend_result_digest")
    normalized = data.get("normalized_result_digest")
    if (
        isinstance(raw, str)
        and isinstance(normalized, str)
        and raw == normalized
        and data.get("normalizer_version")
    ):
        issues.append(
            SemanticIssue(
                "IdenticalNormalizationDigests",
                "normalized_result_digest",
                "when normalization is applied, raw and normalized digests must differ",
            )
        )
    return _as_strings(issues, as_issues=as_issues)


def validate_replay_report_semantics(
    data: dict[str, Any], *, as_issues: bool = False
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "VerifierReplayReport.v1")
    issues.extend(_require_integrity(data, "VerifierReplayReport.v1"))
    drift = data.get("drift") if isinstance(data.get("drift"), dict) else {}
    status = data.get("replay_status")
    if status == "matched" and (
        drift.get("raw_digest_match") is False
        or drift.get("normalized_digest_match") is False
        or data.get("original_raw_digest") != data.get("replay_raw_digest")
        or data.get("original_normalized_digest") != data.get("replay_normalized_digest")
    ):
        issues.append(
            SemanticIssue(
                "ReplayMatchedWithDrift",
                "replay_status",
                "matched status requires matching digests and drift flags true",
            )
        )
    return _as_strings(issues, as_issues=as_issues)


def validate_mutation_manifest_semantics(
    data: dict[str, Any], *, as_issues: bool = False
) -> list[Any]:
    issues = _forbid_legacy_signature_field(data, "VerifierMutationManifest.v1")
    issues.extend(_require_integrity(data, "VerifierMutationManifest.v1"))
    if data.get("production_prohibition") is not True:
        issues.append(
            SemanticIssue(
                "ProductionProhibitionRequired",
                "production_prohibition",
                "production_prohibition must be true",
            )
        )
    return _as_strings(issues, as_issues=as_issues)


def validate_verifier_assurance_semantics(
    data: dict[str, Any],
    artifact_type: str,
    *,
    as_issues: bool = False,
    context: VaValidationContext | None = None,
) -> list[str] | list[SemanticIssue]:
    if artifact_type == "VerifierProfile.v1":
        return validate_verifier_profile_semantics(data, as_issues=as_issues)
    if artifact_type == "VerificationResult.v1":
        return validate_verification_result_semantics(
            data, as_issues=as_issues, context=context
        )
    if artifact_type == "VerifierInvocationRecord.v1":
        return validate_invocation_record_semantics(data, as_issues=as_issues)
    if artifact_type == "VerifierReplayReport.v1":
        return validate_replay_report_semantics(data, as_issues=as_issues)
    if artifact_type == "VerifierMutationManifest.v1":
        return validate_mutation_manifest_semantics(data, as_issues=as_issues)
    if artifact_type == "RewardEvidenceEnvelope.v1":
        return validate_reward_envelope_semantics(
            data, as_issues=as_issues, context=context
        )
    if artifact_type == "OptimizationCampaignManifest.v1":
        return validate_campaign_manifest_semantics(data, as_issues=as_issues)
    if artifact_type == "AdjudicationRecord.v1":
        return validate_adjudication_record_semantics(data, as_issues=as_issues)
    if artifact_type == "VerifierAssuranceReport.v1":
        return validate_assurance_report_semantics(data, as_issues=as_issues)
    msg = f"unknown verifier-assurance artifact type: {artifact_type}"
    if as_issues:
        return [SemanticIssue("UnknownArtifactType", "artifact_type", msg)]
    return [msg]





def load_va_context_from_dir(case_dir: Path) -> VaValidationContext:
    """Load optional profile/results/campaign siblings for multi-file fixtures."""
    profiles: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    rewards: list[dict[str, Any]] = []
    campaign: dict[str, Any] | None = None
    profile_path = case_dir / "profile.json"
    if profile_path.is_file():
        profiles.append(json.loads(profile_path.read_text(encoding="utf-8")))
    campaign_path = case_dir / "campaign.json"
    if campaign_path.is_file():
        campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    results_dir = case_dir / "results"
    if results_dir.is_dir():
        for path in sorted(results_dir.glob("*.json")):
            item = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(item, dict):
                results.append(item)
    result_path = case_dir / "result.json"
    if result_path.is_file():
        item = json.loads(result_path.read_text(encoding="utf-8"))
        if isinstance(item, dict):
            results.append(item)
    reward_path = case_dir / "reward.json"
    if reward_path.is_file():
        item = json.loads(reward_path.read_text(encoding="utf-8"))
        if isinstance(item, dict):
            rewards.append(item)
    return VaValidationContext(
        profiles=tuple(profiles),
        results=tuple(results),
        campaign=campaign,
        rewards=tuple(rewards),
    )


def verifier_assurance_examples_root() -> Path:
    return examples_dir() / "verifier_assurance"


def list_verifier_assurance_valid_fixtures() -> list[Path]:
    root = verifier_assurance_examples_root()
    paths: list[Path] = []
    if root.is_dir():
        paths.extend(sorted(p for p in root.glob("*.valid.json") if p.is_file()))
    for case_dir in iter_va_example_dirs("valid"):
        paths.extend(
            p for p in sorted(case_dir.rglob("*.json")) if p.name != "manifest.json"
        )
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            out.append(path)
    return out


def list_verifier_assurance_invalid_fixtures() -> list[Path]:
    """Flat invalid JSON files only (manifest-based dirs handled separately)."""
    # Invalid VA cases live under examples/verifier_assurance/invalid/<case>/
    # with manifest.json; there is no flat invalid_* directory for the six-artifact family.
    return []


def iter_va_example_dirs(kind: str) -> list[Path]:
    candidate = examples_dir() / "verifier_assurance" / kind
    if candidate.is_dir():
        return sorted(path for path in candidate.iterdir() if path.is_dir())
    return []


def load_va_fixture_manifest(case_dir: Path) -> dict[str, Any]:
    manifest_path = case_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValidationError(f"Missing manifest.json in {case_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValidationError(f"manifest.json root must be an object in {case_dir}")
    return manifest


def _expected_artifact_type_from_name(path: Path) -> str | None:
    name = path.name
    for artifact_type in sorted(VA_ARTIFACT_TYPES, key=len, reverse=True):
        if name.startswith(artifact_type):
            return artifact_type
    return None


def check_va_valid_fixtures() -> None:
    from pcs_core.validate_semantics import validate_artifact

    flat = list_verifier_assurance_valid_fixtures()
    if not flat and not iter_va_example_dirs("valid"):
        raise ValidationError("missing verifier-assurance valid fixtures")
    for path in flat:
        if path.is_dir():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValidationError(f"{path}: root must be object")
        artifact_type = data.get("artifact_type") or _expected_artifact_type_from_name(path)
        if not isinstance(artifact_type, str):
            raise ValidationError(f"{path}: missing artifact_type")
        validate_artifact(data, artifact_type, release_grade=True)


def check_va_invalid_fixtures() -> None:
    flat_files = list_verifier_assurance_invalid_fixtures()
    if flat_files:
        for path in flat_files:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValidationError(f"{path}: root must be object")
            artifact_type = data.get("artifact_type") or _expected_artifact_type_from_name(
                path
            )
            if not isinstance(artifact_type, str) or artifact_type not in VA_ARTIFACT_TYPES:
                raise ValidationError(f"{path}: could not resolve VA artifact_type")
            schema_errors = validate_schema(data, artifact_type)
            semantic_errors = validate_verifier_assurance_semantics(data, artifact_type)
            if not schema_errors and not semantic_errors:
                raise ValidationError(f"{path}: expected validation failure")

    for case_dir in iter_va_example_dirs("invalid"):
        # Skip flat-file directories (no manifest).
        if not (case_dir / "manifest.json").is_file():
            continue
        from pcs_core.validate_detect import detect_artifact_type

        manifest = load_va_fixture_manifest(case_dir)
        expected_error = str(manifest["expected_error"])
        artifact_file = str(manifest.get("artifact_file") or "artifact.json")
        artifact_type = str(manifest.get("artifact_type") or "")
        path = case_dir / artifact_file
        data = json.loads(path.read_text(encoding="utf-8"))
        use_type = artifact_type or detect_artifact_type(data)
        if not use_type:
            raise ValidationError(f"{case_dir.name}: could not detect artifact type")
        context = load_va_context_from_dir(case_dir)
        schema_errors = validate_schema(data, use_type)
        semantic_issues = validate_va_semantics(
            data, use_type, as_issues=True, context=context
        )
        assert isinstance(semantic_issues, list)
        codes = {
            (i.code if isinstance(i, SemanticIssue) else str(i)) for i in semantic_issues
        }
        joined = " ".join(schema_errors) + " " + " ".join(str(i) for i in semantic_issues)
        if expected_error not in codes and expected_error not in joined:
            raise ValidationError(
                f"{case_dir.name}: expected error {expected_error!r}, "
                f"got codes={sorted(c for c in codes if c)} schema={schema_errors}"
            )


def check_verifier_assurance_valid_fixtures() -> list[str]:
    try:
        check_va_valid_fixtures()
        return []
    except ValidationError as exc:
        return [str(exc), *list(exc.errors)]


def check_verifier_assurance_invalid_fixtures() -> list[str]:
    try:
        check_va_invalid_fixtures()
        return []
    except ValidationError as exc:
        return [str(exc), *list(exc.errors)]

def profile_digest(profile: dict[str, Any]) -> str:
    return canonical_hash(profile)
