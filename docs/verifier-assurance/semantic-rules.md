# Verifier Assurance semantic rules

Release-grade validation enforces these rules (see `python/pcs_core/verifier_assurance_validate.py`).
Rust and TypeScript mirror single-artifact codes; Python is authoritative for multi-file context
(`VaValidationContext`: profiles, results, campaign).

Fail-closed: `timeout` / `unavailable` / `malformed_input` / `unsupported_scope` / `error` must not
yield `accept` or `reject` (`FailClosedDecision`).

| # | Rule | Stable error code(s) | Fixture |
|---|------|----------------------|---------|
| 1 | Profile refs resolve; digests match when a profile body is supplied | `ProfileDigestMismatch`, `ProfileRefUnresolved` | `invalid/profile_digest_mismatch/` |
| 2 | Reward trajectory digests match supporting results when results are supplied | `RewardTrajectoryMismatch`, `RewardResultRefUnresolved` | `invalid/reward_trajectory_mismatch/` |
| 3 | `accept` cannot coexist with a mandatory failed check | `AcceptWithMandatoryFailure` | `invalid/accept_mandatory_failure/` |
| 4 | Release-grade reports need independent adjudication | `ReleaseGradeAdjudication` | `invalid/release_grade_no_adjudication/` |
| 5 | Optimization-gap needs ordinary + optimized cohorts | `OptimizationGapCohorts` | `invalid/optimization_gap_missing_cohort/` |
| 6 | Every cohort declares access + compute exposure | `CohortAccessClass`, `CohortComputeExposure`, `AccessClassRequired` | `invalid/cohort_missing_access/` |
| 7 | Aggregate counts reconcile exactly (`accept+reject+indeterminate == included`) | `CohortCountMismatch`, `AggregateCountReconcile` | `invalid/cohort_count_mismatch/` |
| 8 | Revoked/expired profiles cannot support new active rewards without migration | `RevokedProfileGate` | `invalid/revoked_profile_active_reward/` |
| 9 | Raw vs normalized digests distinct and both present when normalization occurs | `IdenticalNormalizationDigests`, `MissingNormalizationDigests` | `invalid/identical_normalization_digests/` |
| 10 | Env/policy/model/verifier/campaign versions consistent when cross-checked | `CrossArtifactVersionMismatch` | `invalid/cross_artifact_version_mismatch/` |
| 11 | Public protected-evidence retains commitments (no rationale content) | `RationaleCommitment` | `invalid/missing_rationale_commitment/` |
| 12 | Excluded/unadjudicated remain visible and count-matched | `ExcludedItemsVisible`, `UnadjudicatedItemsVisible` | `invalid/excluded_items_invisible/` |
| 13 | CI methods + parameters declared (no silent denominator invention) | `CIMethodsDeclared`, `CIParametersDeclared` | `invalid/missing_ci_method/` |
| 14 | Reward component totals reproduce under the declared composition rule | `RewardCompositionMismatch` | `invalid/reward_total_mismatch/` |
| 15 | Indeterminate never counted as accept/reject | `IndeterminateMisclassification` | `invalid/indeterminate_misclassification/` |

Additional producer / schema gates (not in the 15-rule matrix but release-blocking):

| Code | Meaning | Fixture |
|------|---------|---------|
| `FailClosedDecision` | Timeout / unavailable / error must not yield accept/reject | `invalid/timeout_accept/` |
| `InvalidSourceCommit` | `source_commit` must be 40-char lowercase hex | `invalid/short_source_commit/` |
| `ActiveRewardUnresolvedClaims` | Active envelopes cannot carry mandatory unresolved claims | `invalid/active_reward_unresolved/` |
| `additionalProperties` / type errors | Unknown fields and float rewards rejected | `invalid/unknown_field/`, `invalid/float_reward/` |

Multi-file context is loaded from sibling files in a fixture directory (`profile.json`,
`result.json`, `results/*.json`, `campaign.json`) or passed explicitly to validators.
`pcs assurance build-report` is the reference multi-file executor; Rust/TS `verify` accept golden
report outputs and reject digest tampering (`ReportDigestMismatch`).
