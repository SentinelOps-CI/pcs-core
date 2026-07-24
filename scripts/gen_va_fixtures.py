"""Generate Verifier Assurance example fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from pcs_core.hash import CANONICALIZATION_VERSION, canonical_hash
from pcs_core.paths import repo_root
from pcs_core.verifier_assurance_report import build_assurance_report

D = "sha256:" + ("a" * 64)
D2 = "sha256:" + ("b" * 64)
D3 = "sha256:" + ("c" * 64)
D4 = "sha256:" + ("d" * 64)
D5 = "sha256:" + ("e" * 64)
COMMIT = "e068794683959c52a19594a6d271dd5e69f3c999"
REPO = "https://github.com/SentinelOps-CI/pcs-core"


def integrity_for(body: dict) -> dict:
    payload = {k: v for k, v in body.items() if k != "integrity"}
    return {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "artifact_digest": canonical_hash(payload),
    }


def finalize(body: dict) -> dict:
    out = {k: v for k, v in body.items() if k != "integrity"}
    out["integrity"] = integrity_for(out)
    return out


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_manifest(path: Path, expected_error: str, artifact_type: str, artifact_file: str = "artifact.json") -> None:
    write(
        path,
        {
            "expected_error": expected_error,
            "artifact_type": artifact_type,
            "artifact_file": artifact_file,
        },
    )


def base_profile(**overrides) -> dict:
    body = {
        "schema_version": "v1",
        "artifact_type": "VerifierProfile.v1",
        "verifier_profile_id": "vp-ovk-static-001",
        "created_at": "2026-07-24T12:00:00Z",
        "producer": "OVK",
        "producer_version": "0.1.0",
        "source_repo": REPO,
        "source_commit": COMMIT,
        "implementation": {
            "name": "ovk-static-checker",
            "version": "1.0.0",
            "implementation_digest": D,
            "language": "rust",
        },
        "configuration": {
            "config_digest": D2,
            "policy_digest": None,
            "model_digest": None,
            "prompt_digest": None,
            "resource_limit_digest": D3,
        },
        "mechanism": {
            "mechanism_class": "static_analysis",
            "determinism": "deterministic",
            "allows_abstention": True,
            "description": "Static claim checker",
        },
        "claim_surface": {
            "supported_claim_ids": ["claim.safety.no_egress"],
            "guarantee_class": "certificate_checked",
            "out_of_scope_claim_ids": ["claim.formal.full_correctness"],
        },
        "applicability": {"status": "active", "valid_from": "2026-07-01T00:00:00Z"},
        "assumptions": ["host OS is Linux"],
        "known_blind_spots": ["does not observe runtime network"],
    }
    body.update(overrides)
    return finalize(body)


def base_result(profile: dict, **overrides) -> dict:
    body = {
        "schema_version": "v1",
        "artifact_type": "VerificationResult.v1",
        "verification_result_id": "vr-001",
        "created_at": "2026-07-24T12:05:00Z",
        "producer": "OVK",
        "producer_version": "0.1.0",
        "source_repo": REPO,
        "source_commit": COMMIT,
        "verifier_profile": {
            "verifier_profile_id": profile["verifier_profile_id"],
            "profile_digest": canonical_hash(profile),
        },
        "claim_ids": ["claim.safety.no_egress"],
        "trajectory_digest": D4,
        "initial_state_digest": D,
        "terminal_state_digest": D2,
        "input_bundle_digest": D3,
        "raw_backend_output_digest": D,
        "normalized_result_digest": D2,
        "normalization_applied": True,
        "check_groups": [
            {
                "kind": "process",
                "checks": [
                    {"check_id": "process.complete", "mandatory": True, "status": "passed"}
                ],
            },
            {
                "kind": "evidence",
                "checks": [
                    {"check_id": "evidence.present", "mandatory": True, "status": "passed"}
                ],
            },
        ],
        "resource_limits": {"wall_time_ms": 1000, "memory_bytes": 1048576},
        "execution_status": "completed",
        "decision": "accept",
    }
    body.update(overrides)
    return finalize(body)


def base_reward(**overrides) -> dict:
    body = {
        "schema_version": "v1",
        "artifact_type": "RewardEvidenceEnvelope.v1",
        "reward_envelope_id": "rew-001",
        "created_at": "2026-07-24T12:10:00Z",
        "producer": "LabTrust-Gym",
        "producer_version": "0.1.0",
        "source_repo": REPO,
        "source_commit": COMMIT,
        "episode_id": "ep-1",
        "step_index": 0,
        "env_profile_id": "env-lab",
        "env_profile_version": "1.0.0",
        "state_digest": D,
        "trajectory_digest": D4,
        "scalar_total": "1.5",
        "composition_function": "sum",
        "components": [
            {
                "component_id": "safety",
                "value": "1.0",
                "guarantee_class": "certificate_checked",
                "claim_id": "claim.safety.no_egress",
            },
            {
                "component_id": "quality",
                "value": "0.5",
                "guarantee_class": "empirically_measured",
            },
        ],
        "verifier_result_refs": [
            {
                "artifact_type": "VerificationResult.v1",
                "artifact_id": "vr-001",
                "artifact_digest": D5,
            }
        ],
        "claims_issued": ["claim.safety.no_egress"],
        "claims_rejected": [],
        "claims_unresolved": [],
        "mandatory_unresolved_claim_ids": [],
        "authority": {"authority_id": "labtrust-reward", "authority_class": "producer"},
        "lifecycle": {"status": "active"},
        "profile_refs": [
            {
                "verifier_profile_id": "vp-ovk-static-001",
                "profile_digest": D,
                "applicability_status": "active",
            }
        ],
    }
    body.update(overrides)
    return finalize(body)


def base_campaign(**overrides) -> dict:
    body = {
        "schema_version": "v1",
        "artifact_type": "OptimizationCampaignManifest.v1",
        "campaign_id": "camp-001",
        "created_at": "2026-07-24T11:00:00Z",
        "producer": "pcs-core",
        "producer_version": "0.1.0",
        "source_repo": REPO,
        "source_commit": COMMIT,
        "target_verifier_profile": {
            "verifier_profile_id": "vp-ovk-static-001",
            "profile_digest": D,
        },
        "env_profile_id": "env-lab",
        "env_profile_version": "1.0.0",
        "model_id": "model-a",
        "policy_id": "policy-a",
        "harness_id": "harness-a",
        "checkpoint_ids": ["ckpt-0"],
        "algorithm": "random-search",
        "optimizer_settings": {"learning_rate": "0.01", "batch_size": 8},
        "episode_count": 10,
        "trajectory_count": 10,
        "query_count": 100,
        "seeds": [1, 2, 3],
        "compute_budget": {
            "accounting_method": "wall_clock",
            "wall_time_seconds": 3600,
            "query_budget": 1000,
            "gpu_hours": "0",
        },
        "access_class": "black_box",
        "visibility": {"public_summary": True, "full_traces_retained": False},
        "splits": {"train": "train-v1", "validation": "val-v1", "holdout": "hold-v1"},
        "cohorts": [
            {
                "cohort_id": "cohort-ordinary",
                "cohort_kind": "ordinary",
                "access_class": "black_box",
                "compute_exposure": {
                    "accounting_method": "wall_clock",
                    "wall_time_seconds": 600,
                    "query_count": 50,
                },
            },
            {
                "cohort_id": "cohort-optimized",
                "cohort_kind": "optimized",
                "access_class": "adaptive",
                "compute_exposure": {
                    "accounting_method": "wall_clock",
                    "wall_time_seconds": 3000,
                    "query_count": 950,
                },
            },
        ],
        "containment_policy": "offline-only",
        "disclosure_policy": "public-summary",
    }
    body.update(overrides)
    return finalize(body)


def base_adjudication(**overrides) -> dict:
    body = {
        "schema_version": "v1",
        "artifact_type": "AdjudicationRecord.v1",
        "adjudication_id": "adj-001",
        "created_at": "2026-07-24T13:00:00Z",
        "producer": "pcs-core",
        "producer_version": "0.1.0",
        "source_repo": REPO,
        "source_commit": COMMIT,
        "subject": {
            "artifact_type": "VerificationResult.v1",
            "artifact_id": "vr-001",
            "artifact_digest": D5,
        },
        "protocol_id": "adj-protocol",
        "protocol_version": "1.0.0",
        "label": "valid",
        "votes": [{"voter_pseudonym_id": "voter-a", "role": "primary", "vote": "valid"}],
        "independence_declared": True,
        "conflict_of_interest_declared": False,
        "disagreement": False,
        "escalation": False,
        "blinded": True,
        "label_released_at": "2026-07-24T14:00:00Z",
        "evidence_refs": [],
        "protected_rationale": {
            "commitment_digest": D,
            "location_class": "access_controlled_store",
            "content_omitted": True,
        },
    }
    body.update(overrides)
    return finalize(body)


def main() -> None:
    root = repo_root() / "examples" / "verifier_assurance"
    profile = base_profile()
    write(root / "valid" / "profile_basic" / "profile.json", profile)
    write(root / "valid" / "result_accept" / "result.json", base_result(profile))
    write(root / "valid" / "reward_scalar" / "reward.json", base_reward())
    campaign = base_campaign()
    write(root / "valid" / "campaign_basic" / "campaign.json", campaign)
    write(root / "valid" / "adjudication_basic" / "adjudication.json", base_adjudication())

    r1 = base_result(profile, verification_result_id="vr-001", cohort_id="cohort-ordinary")
    r2 = base_result(
        profile,
        verification_result_id="vr-002",
        cohort_id="cohort-optimized",
        decision="reject",
        check_groups=[
            {
                "kind": "process",
                "checks": [
                    {"check_id": "process.complete", "mandatory": True, "status": "failed"}
                ],
            }
        ],
    )
    a1 = base_adjudication()
    a2 = base_adjudication(
        adjudication_id="adj-002",
        subject={
            "artifact_type": "VerificationResult.v1",
            "artifact_id": "vr-002",
            "artifact_digest": D5,
        },
        label="invalid",
        votes=[{"voter_pseudonym_id": "voter-a", "role": "primary", "vote": "invalid"}],
    )
    report = build_assurance_report(
        campaign=campaign,
        results=[r1, r2],
        adjudications=[a1, a2],
        report_id="rep-001",
        created_at="2026-07-24T15:00:00Z",
        source_commit=COMMIT,
        release_grade=True,
        excluded_items=[{"item_id": "ex-1", "reason_code": "out_of_scope"}],
        unadjudicated_items=[],
        applicability_limits=["synthetic fixture only"],
    )
    report_dir = root / "valid" / "report_rebuild"
    write(report_dir / "campaign.json", campaign)
    write(report_dir / "results" / "vr-001.json", r1)
    write(report_dir / "results" / "vr-002.json", r2)
    write(report_dir / "adjudications" / "adj-001.json", a1)
    write(report_dir / "adjudications" / "adj-002.json", a2)
    write(report_dir / "report.json", report)

    # Invalid fixtures
    inv = root / "invalid"

    bad_timeout = base_result(profile, execution_status="timeout", decision="accept")
    write(inv / "timeout_accept" / "artifact.json", bad_timeout)
    write_manifest(inv / "timeout_accept" / "manifest.json", "FailClosedDecision", "VerificationResult.v1")

    bad_accept = base_result(
        profile,
        decision="accept",
        check_groups=[
            {
                "kind": "process",
                "checks": [
                    {"check_id": "process.complete", "mandatory": True, "status": "failed"}
                ],
            }
        ],
    )
    write(inv / "accept_mandatory_failure" / "artifact.json", bad_accept)
    write_manifest(
        inv / "accept_mandatory_failure" / "manifest.json",
        "AcceptWithMandatoryFailure",
        "VerificationResult.v1",
    )

    bad_norm = base_result(
        profile,
        normalization_applied=True,
        raw_backend_output_digest=D,
        normalized_result_digest=D,
    )
    write(inv / "identical_normalization_digests" / "artifact.json", bad_norm)
    write_manifest(
        inv / "identical_normalization_digests" / "manifest.json",
        "IdenticalNormalizationDigests",
        "VerificationResult.v1",
    )

    bad_reward = base_reward(scalar_total="9.9")
    write(inv / "reward_total_mismatch" / "artifact.json", bad_reward)
    write_manifest(
        inv / "reward_total_mismatch" / "manifest.json",
        "RewardCompositionMismatch",
        "RewardEvidenceEnvelope.v1",
    )

    bad_revoked = base_reward(
        lifecycle={"status": "active"},
        profile_refs=[
            {
                "verifier_profile_id": "vp-ovk-static-001",
                "profile_digest": D,
                "applicability_status": "revoked",
            }
        ],
    )
    write(inv / "revoked_profile_active_reward" / "artifact.json", bad_revoked)
    write_manifest(
        inv / "revoked_profile_active_reward" / "manifest.json",
        "RevokedProfileGate",
        "RewardEvidenceEnvelope.v1",
    )

    bad_adj = base_adjudication(protected_rationale={"location_class": "partner_vault"})
    write(inv / "missing_rationale_commitment" / "artifact.json", bad_adj)
    write_manifest(
        inv / "missing_rationale_commitment" / "manifest.json",
        "RationaleCommitment",
        "AdjudicationRecord.v1",
    )

    short_commit = base_profile(source_commit="abc1234")
    write(inv / "short_source_commit" / "artifact.json", short_commit)
    write_manifest(
        inv / "short_source_commit" / "manifest.json",
        "InvalidSourceCommit",
        "VerifierProfile.v1",
    )

    unknown = base_profile()
    unknown["extra_field"] = "nope"
    unknown.pop("integrity", None)
    unknown = finalize(unknown)
    write(inv / "unknown_field" / "artifact.json", unknown)
    write_manifest(
        inv / "unknown_field" / "manifest.json",
        "Additional properties are not allowed ('extra_field' was unexpected)",
        "VerifierProfile.v1",
    )

    # Rule 1: profile digest mismatch (multi-file)
    digest_case = inv / "profile_digest_mismatch"
    write(digest_case / "profile.json", profile)
    bad_result = base_result(
        profile,
        verifier_profile={
            "verifier_profile_id": profile["verifier_profile_id"],
            "profile_digest": "sha256:" + ("f" * 64),
        },
    )
    write(digest_case / "artifact.json", bad_result)
    write_manifest(digest_case / "manifest.json", "ProfileDigestMismatch", "VerificationResult.v1")

    # Rule 2: reward trajectory mismatch (multi-file)
    traj_case = inv / "reward_trajectory_mismatch"
    good_result = base_result(profile)
    write(traj_case / "result.json", good_result)
    bad_traj_reward = base_reward(
        trajectory_digest="sha256:" + ("f" * 64),
        verifier_result_refs=[
            {
                "artifact_type": "VerificationResult.v1",
                "artifact_id": "vr-001",
                "artifact_digest": D5,
            }
        ],
    )
    write(traj_case / "artifact.json", bad_traj_reward)
    write_manifest(
        traj_case / "manifest.json", "RewardTrajectoryMismatch", "RewardEvidenceEnvelope.v1"
    )

    # Rule 4: release-grade without independent adjudication
    bad_rg = dict(report)
    bad_rg["release_grade"] = True
    bad_rg["independent_adjudication"] = False
    bad_rg.pop("integrity", None)
    bad_rg = finalize(bad_rg)
    write(inv / "release_grade_no_adjudication" / "artifact.json", bad_rg)
    write_manifest(
        inv / "release_grade_no_adjudication" / "manifest.json",
        "ReleaseGradeAdjudication",
        "VerifierAssuranceReport.v1",
    )

    # Rule 5: optimization gap without both cohorts
    bad_gap = dict(report)
    bad_gap["cohorts"] = [report["cohorts"][0]]
    bad_gap["metrics"] = dict(report["metrics"])
    bad_gap["metrics"]["optimization_gap"] = "0.500000"
    bad_gap.pop("integrity", None)
    bad_gap = finalize(bad_gap)
    write(inv / "optimization_gap_missing_cohort" / "artifact.json", bad_gap)
    write_manifest(
        inv / "optimization_gap_missing_cohort" / "manifest.json",
        "OptimizationGapCohorts",
        "VerifierAssuranceReport.v1",
    )

    # Rule 6: cohort missing access/compute
    bad_cohort = base_campaign(
        cohorts=[
            {
                "cohort_id": "cohort-ordinary",
                "cohort_kind": "ordinary",
                "compute_exposure": {
                    "accounting_method": "wall_clock",
                    "wall_time_seconds": 600,
                    "query_count": 50,
                },
            }
        ]
    )
    write(inv / "cohort_missing_access" / "artifact.json", bad_cohort)
    write_manifest(
        inv / "cohort_missing_access" / "manifest.json",
        "CohortAccessClass",
        "OptimizationCampaignManifest.v1",
    )

    # Rule 7: cohort count mismatch
    bad_counts = dict(report)
    bad_counts["cohorts"] = [
        {
            **report["cohorts"][0],
            "accept_count": 99,
            "reject_count": 0,
            "indeterminate_count": 0,
            "included_result_count": 1,
        },
        report["cohorts"][1],
    ]
    bad_counts.pop("integrity", None)
    bad_counts = finalize(bad_counts)
    write(inv / "cohort_count_mismatch" / "artifact.json", bad_counts)
    write_manifest(
        inv / "cohort_count_mismatch" / "manifest.json",
        "CohortCountMismatch",
        "VerifierAssuranceReport.v1",
    )

    # Rule 10: cross-artifact env version mismatch
    ver_case = inv / "cross_artifact_version_mismatch"
    write(ver_case / "campaign.json", campaign)
    write(ver_case / "result.json", good_result)
    bad_env_reward = base_reward(env_profile_id="env-other", env_profile_version="9.9.9")
    write(ver_case / "artifact.json", bad_env_reward)
    write_manifest(
        ver_case / "manifest.json",
        "CrossArtifactVersionMismatch",
        "RewardEvidenceEnvelope.v1",
    )

    # Rule 12: excluded items not visible
    bad_excl = dict(report)
    bad_excl["excluded_items"] = []
    bad_excl["metrics"] = dict(report["metrics"])
    bad_excl["metrics"]["excluded_count"] = 3
    bad_excl.pop("integrity", None)
    bad_excl = finalize(bad_excl)
    write(inv / "excluded_items_invisible" / "artifact.json", bad_excl)
    write_manifest(
        inv / "excluded_items_invisible" / "manifest.json",
        "ExcludedItemsVisible",
        "VerifierAssuranceReport.v1",
    )

    # Rule 13: missing CI method
    bad_ci = dict(report)
    bad_ci["metrics"] = dict(report["metrics"])
    far = dict(report["metrics"]["false_accept_rate"])
    far["confidence_interval"] = {
        "lower": "0",
        "upper": "0",
        "sample_size": 2,
        "parameters": {"alpha": "0.05"},
    }
    bad_ci["metrics"]["false_accept_rate"] = far
    bad_ci.pop("integrity", None)
    bad_ci = finalize(bad_ci)
    write(inv / "missing_ci_method" / "artifact.json", bad_ci)
    write_manifest(
        inv / "missing_ci_method" / "manifest.json",
        "CIMethodsDeclared",
        "VerifierAssuranceReport.v1",
    )

    # Rule 15: negative indeterminate bucket
    bad_indet = dict(report)
    bad_indet["cohorts"] = [
        {
            **report["cohorts"][0],
            "accept_count": 2,
            "reject_count": 0,
            "indeterminate_count": -1,
            "included_result_count": 1,
        },
        report["cohorts"][1],
    ]
    bad_indet.pop("integrity", None)
    bad_indet = finalize(bad_indet)
    write(inv / "indeterminate_misclassification" / "artifact.json", bad_indet)
    write_manifest(
        inv / "indeterminate_misclassification" / "manifest.json",
        "IndeterminateMisclassification",
        "VerifierAssuranceReport.v1",
    )

    # Active reward with mandatory unresolved claims
    bad_unresolved = base_reward(
        lifecycle={"status": "active"},
        mandatory_unresolved_claim_ids=["claim.safety.no_egress"],
    )
    write(inv / "active_reward_unresolved" / "artifact.json", bad_unresolved)
    write_manifest(
        inv / "active_reward_unresolved" / "manifest.json",
        "ActiveRewardUnresolvedClaims",
        "RewardEvidenceEnvelope.v1",
    )

    # Producer dialect: float reward (schema reject)
    float_reward = base_reward()
    float_reward["scalar_total"] = 1.5  # type: ignore[assignment]
    float_reward.pop("integrity", None)
    write(inv / "float_reward" / "artifact.json", float_reward)
    write_manifest(
        inv / "float_reward" / "manifest.json",
        "is not of type 'string'",
        "RewardEvidenceEnvelope.v1",
    )

    print("Wrote VA fixtures under", root)


if __name__ == "__main__":
    main()
