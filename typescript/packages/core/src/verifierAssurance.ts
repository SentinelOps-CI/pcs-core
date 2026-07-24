/**
 * Verifier Assurance (VA) *.v1 semantic validation and report verify.
 * Error codes mirror python/pcs_core/verifier_assurance_validate.py.
 */

import { canonicalHash, SIGNATURE_FIELD } from "./hash.js";

export interface SemanticIssue {
  code: string;
  path: string;
  message: string;
}

export function formatSemanticIssue(issue: SemanticIssue): string {
  return `${issue.code} at ${issue.path}: ${issue.message}`;
}

const FAIL_CLOSED = new Set([
  "timeout",
  "unavailable",
  "malformed_input",
  "unsupported_scope",
  "error",
  "cancelled",
  "resource_exhausted",
]);

const SECRET_KEY_HINTS = [
  "password",
  "passwd",
  "secret",
  "token",
  "api_key",
  "apikey",
  "authorization",
  "private_key",
  "access_key",
];

const GUARANTEE_RANK: Record<string, number> = {
  unchecked_advisory: 0,
  observational: 1,
  runtime_observed: 1,
  empirically_measured: 2,
  human_reviewed: 3,
  certificate_checked: 4,
  formally_checked: 5,
};

const VA_ARTIFACT_TYPES = new Set([
  "VerifierProfile.v1",
  "VerificationResult.v1",
  "RewardEvidenceEnvelope.v1",
  "OptimizationCampaignManifest.v1",
  "AdjudicationRecord.v1",
  "VerifierAssuranceReport.v1",
]);

export function isVaArtifactType(artifactType: string): boolean {
  return VA_ARTIFACT_TYPES.has(artifactType);
}

function issue(code: string, path: string, message: string): SemanticIssue {
  return { code, path, message };
}

function forbidLegacySignature(
  data: Record<string, unknown>,
  artifactType: string,
): SemanticIssue[] {
  if (SIGNATURE_FIELD in data) {
    return [
      issue(
        "LegacySignatureOrDigest",
        SIGNATURE_FIELD,
        `${artifactType}: ${SIGNATURE_FIELD} is forbidden on VA *.v1 roots`,
      ),
    ];
  }
  return [];
}

function requireIntegrity(
  data: Record<string, unknown>,
  artifactType: string,
): SemanticIssue[] {
  const integrity = data.integrity;
  if (!integrity || typeof integrity !== "object" || Array.isArray(integrity)) {
    return [
      issue(
        "MissingIntegrity",
        "integrity",
        `${artifactType}: nested integrity envelope is required`,
      ),
    ];
  }
  const obj = integrity as Record<string, unknown>;
  const issues: SemanticIssue[] = [];
  if (obj.canonicalization_version !== "v1") {
    issues.push(
      issue("BadCanonicalizationVersion", "integrity.canonicalization_version", "must be v1"),
    );
  }
  const digest = obj.artifact_digest;
  if (typeof digest !== "string" || !digest.startsWith("sha256:")) {
    issues.push(
      issue("BadArtifactDigest", "integrity.artifact_digest", "must be sha256:<64 hex>"),
    );
  }
  return issues;
}

function checkZeroCommit(commit: unknown, path: string): SemanticIssue[] {
  if (
    typeof commit === "string" &&
    commit.length === 40 &&
    /^0+$/.test(commit)
  ) {
    return [issue("PlaceholderCommit", path, "placeholder zero git commit rejected")];
  }
  return [];
}

function isFullHexCommit(commit: string): boolean {
  return commit.length === 40 && /^[0-9a-f]{40}$/.test(commit);
}

function checkSecretLeaks(envEntries: unknown, path: string): SemanticIssue[] {
  if (!envEntries || typeof envEntries !== "object" || Array.isArray(envEntries)) {
    return [];
  }
  const issues: SemanticIssue[] = [];
  for (const [key, value] of Object.entries(envEntries as Record<string, unknown>)) {
    const keyL = key.toLowerCase();
    if (SECRET_KEY_HINTS.some((hint) => keyL.includes(hint))) {
      issues.push(
        issue(
          "SecretKeyName",
          `${path}.${key}`,
          `redacted_environment key ${JSON.stringify(key)} looks like a secret name`,
        ),
      );
    }
    if (typeof value === "string") {
      const valueL = value.toLowerCase();
      if (value.startsWith("sk-") || valueL.includes("begin private key")) {
        issues.push(issue("SecretValue", `${path}.${key}`, "value appears to contain a secret"));
      }
    }
  }
  return issues;
}

type Decimal = { mantissa: bigint; scale: number };

function parseDecimalStr(s: string): Decimal | null {
  const trimmed = s.trim();
  if (!trimmed) return null;
  const negative = trimmed.startsWith("-");
  const body =
    negative || trimmed.startsWith("+") ? trimmed.slice(1) : trimmed;
  if (!body || !/^\d*\.?\d*$/.test(body) || (body.match(/\./g) ?? []).length > 1) {
    return null;
  }
  const [intPart, fracPart = ""] = body.split(".");
  if (!intPart && !fracPart) return null;
  const combined = `${intPart || "0"}${fracPart}`;
  try {
    let mantissa = BigInt(combined);
    if (negative) mantissa = -mantissa;
    return { mantissa, scale: fracPart.length };
  } catch {
    return null;
  }
}

function parseDecimal(
  value: unknown,
  path: string,
): { ok: Decimal } | { err: SemanticIssue } {
  if (typeof value !== "string") {
    return { err: issue("DecimalType", path, "decimal values must be strings") };
  }
  const parsed = parseDecimalStr(value);
  if (!parsed) {
    return {
      err: issue("DecimalParse", path, `invalid decimal string ${JSON.stringify(value)}`),
    };
  }
  return { ok: parsed };
}

function rescale(d: Decimal, toScale: number): bigint {
  if (toScale >= d.scale) {
    return d.mantissa * 10n ** BigInt(toScale - d.scale);
  }
  return d.mantissa / 10n ** BigInt(d.scale - toScale);
}

function decimalsEqual(a: Decimal, b: Decimal): boolean {
  const scale = Math.max(a.scale, b.scale);
  return rescale(a, scale) === rescale(b, scale);
}

function addDecimals(a: Decimal, b: Decimal): Decimal {
  const scale = Math.max(a.scale, b.scale);
  return { mantissa: rescale(a, scale) + rescale(b, scale), scale };
}

export function validateVerifierProfileSemantics(
  data: Record<string, unknown>,
): SemanticIssue[] {
  const issues = [
    ...forbidLegacySignature(data, "VerifierProfile.v1"),
    ...requireIntegrity(data, "VerifierProfile.v1"),
  ];
  const commit = data.source_commit;
  if (typeof commit !== "string" || !isFullHexCommit(commit)) {
    issues.push(
      issue(
        "InvalidSourceCommit",
        "source_commit",
        "source_commit must be a full 40-char lowercase hex SHA",
      ),
    );
  }
  issues.push(...checkZeroCommit(commit, "source_commit"));
  const configuration = data.configuration;
  if (configuration && typeof configuration === "object" && !Array.isArray(configuration)) {
    const cfg = configuration as Record<string, unknown>;
    for (const key of [
      "policy_digest",
      "model_digest",
      "prompt_digest",
      "resource_limit_digest",
    ]) {
      if (!(key in cfg)) {
        issues.push(
          issue(
            "MissingNullDigestSlot",
            `configuration.${key}`,
            "inapplicable config digests must be present as explicit null",
          ),
        );
      }
    }
  }
  const impl = data.implementation;
  if (impl && typeof impl === "object" && !Array.isArray(impl)) {
    const digest = (impl as Record<string, unknown>).implementation_digest;
    if (digest === undefined || digest === null || digest === "") {
      issues.push(
        issue(
          "MissingImplementationDigest",
          "implementation.implementation_digest",
          "implementation_digest is required",
        ),
      );
    }
  }
  const applicability = data.applicability;
  if (applicability && typeof applicability === "object" && !Array.isArray(applicability)) {
    const app = applicability as Record<string, unknown>;
    if (app.status === "revoked" && !app.revocation_reason) {
      issues.push(
        issue(
          "MissingRevocationReason",
          "applicability.revocation_reason",
          "revoked profiles require revocation_reason",
        ),
      );
    }
    if (app.status === "superseded" && !app.superseded_by_profile_id) {
      issues.push(
        issue(
          "MissingSupersededBy",
          "applicability.superseded_by_profile_id",
          "superseded profiles require superseded_by_profile_id",
        ),
      );
    }
  }
  const redacted = data.redacted_environment;
  if (redacted && typeof redacted === "object" && !Array.isArray(redacted)) {
    issues.push(
      ...checkSecretLeaks(
        (redacted as Record<string, unknown>).entries,
        "redacted_environment.entries",
      ),
    );
  }
  const schemaDoc = data.configuration_schema;
  const schemaDigest = data.configuration_schema_digest;
  if (
    schemaDoc &&
    typeof schemaDoc === "object" &&
    !Array.isArray(schemaDoc) &&
    typeof schemaDigest === "string"
  ) {
    try {
      const recomputed = canonicalHash(schemaDoc as Record<string, unknown>);
      if (recomputed !== schemaDigest) {
        issues.push(
          issue(
            "ConfigSchemaDigestMismatch",
            "configuration_schema_digest",
            `recorded ${JSON.stringify(schemaDigest)} != recomputed ${JSON.stringify(recomputed)}`,
          ),
        );
      }
    } catch (err) {
      issues.push(
        issue("ConfigSchemaUnhashable", "configuration_schema", String(err)),
      );
    }
  }
  return issues;
}

export function validateVerificationResultSemantics(
  data: Record<string, unknown>,
): SemanticIssue[] {
  const issues = [
    ...forbidLegacySignature(data, "VerificationResult.v1"),
    ...requireIntegrity(data, "VerificationResult.v1"),
  ];
  const commit = data.source_commit;
  if (typeof commit !== "string" || !isFullHexCommit(commit)) {
    issues.push(
      issue(
        "InvalidSourceCommit",
        "source_commit",
        "source_commit must be a full 40-char lowercase hex SHA",
      ),
    );
  }
  const decision = data.decision;
  const executionStatus = data.execution_status;
  if (
    typeof executionStatus === "string" &&
    FAIL_CLOSED.has(executionStatus) &&
    (decision === "accept" || decision === "reject")
  ) {
    issues.push(
      issue(
        "FailClosedDecision",
        "decision",
        `execution_status ${JSON.stringify(executionStatus)} cannot yield accept/reject`,
      ),
    );
  }
  if (data.normalization_applied === true) {
    const raw = data.raw_backend_output_digest;
    const normalized = data.normalized_result_digest;
    if (typeof raw !== "string" || typeof normalized !== "string") {
      issues.push(
        issue(
          "MissingNormalizationDigests",
          "normalized_result_digest",
          "normalization_applied requires raw and normalized digests",
        ),
      );
    } else if (raw === normalized) {
      issues.push(
        issue(
          "IdenticalNormalizationDigests",
          "normalized_result_digest",
          "raw and normalized digests must be distinct when normalization occurs",
        ),
      );
    }
  }
  let mandatoryFailed = false;
  const groups = Array.isArray(data.check_groups) ? data.check_groups : [];
  groups.forEach((group, gIndex) => {
    if (!group || typeof group !== "object" || Array.isArray(group)) return;
    const checks = Array.isArray((group as Record<string, unknown>).checks)
      ? ((group as Record<string, unknown>).checks as unknown[])
      : [];
    checks.forEach((check, cIndex) => {
      if (!check || typeof check !== "object" || Array.isArray(check)) return;
      const c = check as Record<string, unknown>;
      if (c.mandatory === true && c.status === "failed") mandatoryFailed = true;
      if (c.status === "skipped" && !(c.reason_code || c.skip_reason_code)) {
        issues.push(
          issue(
            "MissingSkipReason",
            `check_groups[${gIndex}].checks[${cIndex}].reason_code`,
            "skipped checks require reason_code",
          ),
        );
      }
    });
  });
  if (decision === "accept" && mandatoryFailed) {
    issues.push(
      issue(
        "AcceptWithMandatoryFailure",
        "decision",
        "accept cannot coexist with a mandatory failed check",
      ),
    );
  }
  const declared = data.declared_input_guarantee_class;
  const resultClass = data.guarantee_class;
  if (typeof declared === "string" && typeof resultClass === "string") {
    const dRank = GUARANTEE_RANK[declared];
    const rRank = GUARANTEE_RANK[resultClass];
    if (dRank !== undefined && rRank !== undefined && rRank > dRank) {
      issues.push(
        issue(
          "GuaranteeUpgrade",
          "guarantee_class",
          `must not upgrade declared_input_guarantee_class (${JSON.stringify(declared)} -> ${JSON.stringify(resultClass)})`,
        ),
      );
    }
  }
  return issues;
}

export function validateRewardEnvelopeSemantics(
  data: Record<string, unknown>,
): SemanticIssue[] {
  const issues = [
    ...forbidLegacySignature(data, "RewardEvidenceEnvelope.v1"),
    ...requireIntegrity(data, "RewardEvidenceEnvelope.v1"),
    ...checkZeroCommit(data.source_commit, "source_commit"),
  ];
  const totalResult = parseDecimal(data.scalar_total, "scalar_total");
  let total: Decimal | null = null;
  if ("err" in totalResult) {
    issues.push(totalResult.err);
  } else {
    total = totalResult.ok;
  }
  const components = data.components;
  if (Array.isArray(components) && total && data.composition_function === "sum") {
    let acc: Decimal = { mantissa: 0n, scale: 0 };
    let ok = true;
    components.forEach((component, index) => {
      if (!component || typeof component !== "object" || Array.isArray(component)) return;
      const value = (component as Record<string, unknown>).value;
      if (value === undefined) return;
      const parsed = parseDecimal(value, `components[${index}].value`);
      if ("err" in parsed) {
        issues.push(parsed.err);
        ok = false;
        return;
      }
      acc = addDecimals(acc, parsed.ok);
    });
    if (ok && !decimalsEqual(acc, total)) {
      issues.push(
        issue(
          "RewardCompositionMismatch",
          "scalar_total",
          "sum of components != scalar_total",
        ),
      );
    }
  }
  const claims = Array.isArray(data.claims_issued) ? data.claims_issued : [];
  if (claims.length > 0) {
    const refs = data.verifier_result_refs;
    if (!Array.isArray(refs) || refs.length === 0) {
      issues.push(
        issue(
          "ClaimsNeedVerifierRefs",
          "verifier_result_refs",
          "claims_issued requires at least one verifier_result_ref",
        ),
      );
    }
  }
  const prefs = Array.isArray(data.profile_refs) ? data.profile_refs : [];
  const lifecycle =
    data.lifecycle && typeof data.lifecycle === "object" && !Array.isArray(data.lifecycle)
      ? (data.lifecycle as Record<string, unknown>)
      : {};
  const lifecycleStatus = lifecycle.status;
  const migration =
    typeof lifecycle.migration_record_id === "string" &&
    lifecycle.migration_record_id.length > 0;
  prefs.forEach((pref, index) => {
    if (!pref || typeof pref !== "object" || Array.isArray(pref)) return;
    const status = (pref as Record<string, unknown>).applicability_status;
    if (
      (status === "revoked" || status === "expired") &&
      lifecycleStatus === "active" &&
      !migration
    ) {
      issues.push(
        issue(
          "RevokedProfileGate",
          `profile_refs[${index}]`,
          `${status} profiles cannot support new active rewards without migration_record_id`,
        ),
      );
    } else if (status === "revoked" && lifecycleStatus !== "active" && claims.length > 0) {
      issues.push(
        issue(
          "RevokedProfileGate",
          `profile_refs[${index}]`,
          "revoked profiles cannot authorize reward claims",
        ),
      );
    }
  });
  const mandatory = Array.isArray(data.mandatory_unresolved_claim_ids)
    ? data.mandatory_unresolved_claim_ids
    : [];
  if (lifecycleStatus === "active" && mandatory.length > 0) {
    issues.push(
      issue(
        "ActiveRewardUnresolvedClaims",
        "mandatory_unresolved_claim_ids",
        "unresolved mandatory claims block active release-grade envelopes",
      ),
    );
  }
  return issues;
}

export function validateCampaignManifestSemantics(
  data: Record<string, unknown>,
): SemanticIssue[] {
  const issues = [
    ...forbidLegacySignature(data, "OptimizationCampaignManifest.v1"),
    ...requireIntegrity(data, "OptimizationCampaignManifest.v1"),
    ...checkZeroCommit(data.source_commit, "source_commit"),
  ];
  if (!data.access_class) {
    issues.push(issue("AccessClassRequired", "access_class", "access_class is required"));
  }
  const cohorts = Array.isArray(data.cohorts) ? data.cohorts : [];
  cohorts.forEach((cohort, index) => {
    if (!cohort || typeof cohort !== "object" || Array.isArray(cohort)) return;
    const exposure = (cohort as Record<string, unknown>).compute_exposure;
    if (!exposure || typeof exposure !== "object" || Array.isArray(exposure)) {
      issues.push(
        issue(
          "CohortComputeExposure",
          `cohorts[${index}].compute_exposure`,
          "compute_exposure is required",
        ),
      );
    }
    if (!(cohort as Record<string, unknown>).access_class) {
      issues.push(
        issue(
          "CohortAccessClass",
          `cohorts[${index}].access_class`,
          "every cohort must declare access_class",
        ),
      );
    }
  });
  return issues;
}

export function validateAdjudicationRecordSemantics(
  data: Record<string, unknown>,
  releaseGrade = false,
): SemanticIssue[] {
  const issues = [
    ...forbidLegacySignature(data, "AdjudicationRecord.v1"),
    ...requireIntegrity(data, "AdjudicationRecord.v1"),
    ...checkZeroCommit(data.source_commit, "source_commit"),
  ];
  const protectedRationale = data.protected_rationale;
  if (
    protectedRationale &&
    typeof protectedRationale === "object" &&
    !Array.isArray(protectedRationale)
  ) {
    if (!(protectedRationale as Record<string, unknown>).commitment_digest) {
      issues.push(
        issue(
          "RationaleCommitment",
          "protected_rationale.commitment_digest",
          "commitment_digest is required",
        ),
      );
    }
  }
  if (releaseGrade && data.independence_declared !== true) {
    issues.push(
      issue(
        "IndependenceForReleaseGrade",
        "independence_declared",
        "release-grade adjudication requires independence_declared=true",
      ),
    );
  }
  return issues;
}

export function validateAssuranceReportSemantics(
  data: Record<string, unknown>,
): SemanticIssue[] {
  const issues = [
    ...forbidLegacySignature(data, "VerifierAssuranceReport.v1"),
    ...requireIntegrity(data, "VerifierAssuranceReport.v1"),
    ...checkZeroCommit(data.source_commit, "source_commit"),
  ];
  let claimsGap = false;
  const metrics = data.metrics;
  if (metrics && typeof metrics === "object" && !Array.isArray(metrics)) {
    const m = metrics as Record<string, unknown>;
    const sample = m.sample_size;
    const excluded = m.excluded_count;
    const unadj = m.unadjudicated_count;
    if (
      typeof sample === "number" &&
      typeof excluded === "number" &&
      typeof unadj === "number" &&
      excluded + unadj > sample &&
      sample > 0
    ) {
      issues.push(
        issue(
          "AggregateCountReconcile",
          "metrics",
          "excluded_count + unadjudicated_count exceeds sample_size",
        ),
      );
    }
    for (const key of [
      "false_accept_rate",
      "false_reject_rate",
      "abstention_rate",
      "adjudication_coverage",
    ]) {
      const rate = m[key];
      if (rate && typeof rate === "object" && !Array.isArray(rate)) {
        const ci = (rate as Record<string, unknown>).confidence_interval;
        const ciObj =
          ci && typeof ci === "object" && !Array.isArray(ci)
            ? (ci as Record<string, unknown>)
            : undefined;
        const method = ciObj?.method;
        if (typeof method !== "string" || !method) {
          issues.push(
            issue(
              "CIMethodsDeclared",
              `metrics.${key}.confidence_interval.method`,
              "CI method must be declared",
            ),
          );
        } else if (
          !ciObj?.parameters ||
          typeof ciObj.parameters !== "object" ||
          Array.isArray(ciObj.parameters)
        ) {
          issues.push(
            issue(
              "CIParametersDeclared",
              `metrics.${key}.confidence_interval.parameters`,
              "CI parameters must be declared (no silent denominator invention)",
            ),
          );
        }
      }
    }
    const gap = m.optimization_gap;
    const gapNonzero =
      typeof gap === "string" && gap !== "0" && gap !== "0.0" && gap !== "0.000000";
    const ordinary = m.ordinary_accept_rate;
    const optimized = m.optimized_accept_rate;
    const ordinaryDen =
      ordinary && typeof ordinary === "object" && !Array.isArray(ordinary)
        ? Number((ordinary as Record<string, unknown>).denominator ?? 0)
        : 0;
    const optimizedDen =
      optimized && typeof optimized === "object" && !Array.isArray(optimized)
        ? Number((optimized as Record<string, unknown>).denominator ?? 0)
        : 0;
    claimsGap = gapNonzero || (ordinaryDen > 0 && optimizedDen > 0);

    const excludedItems = data.excluded_items;
    const unadjItems = data.unadjudicated_items;
    if (typeof excluded === "number") {
      if (Array.isArray(excludedItems)) {
        if (excludedItems.length !== excluded) {
          issues.push(
            issue(
              "ExcludedItemsVisible",
              "excluded_items",
              "excluded_count must equal len(excluded_items)",
            ),
          );
        }
      } else if (excluded > 0) {
        issues.push(
          issue(
            "ExcludedItemsVisible",
            "excluded_items",
            "excluded_count > 0 requires visible excluded_items",
          ),
        );
      }
    }
    if (typeof unadj === "number") {
      if (Array.isArray(unadjItems)) {
        if (unadjItems.length !== unadj) {
          issues.push(
            issue(
              "UnadjudicatedItemsVisible",
              "unadjudicated_items",
              "unadjudicated_count must equal len(unadjudicated_items)",
            ),
          );
        }
      } else if (unadj > 0) {
        issues.push(
          issue(
            "UnadjudicatedItemsVisible",
            "unadjudicated_items",
            "unadjudicated_count > 0 requires visible unadjudicated_items",
          ),
        );
      }
    }
  }
  const cohorts = Array.isArray(data.cohorts) ? data.cohorts : [];
  let hasOrdinary = false;
  let hasOptimized = false;
  cohorts.forEach((cohort, index) => {
    if (!cohort || typeof cohort !== "object" || Array.isArray(cohort)) return;
    const c = cohort as Record<string, unknown>;
    if (c.cohort_kind === "ordinary") hasOrdinary = true;
    if (c.cohort_kind === "optimized") hasOptimized = true;
    if (!c.access_class) {
      issues.push(
        issue(
          "CohortAccessClass",
          `cohorts[${index}].access_class`,
          "every cohort must declare access_class",
        ),
      );
    }
    const exposure = c.compute_exposure;
    if (!exposure || typeof exposure !== "object" || Array.isArray(exposure)) {
      issues.push(
        issue(
          "CohortComputeExposure",
          `cohorts[${index}].compute_exposure`,
          "every cohort must declare compute_exposure",
        ),
      );
    }
    const accept = c.accept_count;
    const reject = c.reject_count;
    const indeterminate = c.indeterminate_count;
    const included = c.included_result_count;
    if (
      typeof accept === "number" &&
      typeof reject === "number" &&
      typeof indeterminate === "number" &&
      typeof included === "number"
    ) {
      if (accept + reject + indeterminate !== included) {
        issues.push(
          issue(
            "CohortCountMismatch",
            `cohorts[${index}]`,
            "aggregate counts must reconcile exactly with included records",
          ),
        );
      }
      if (accept < 0 || reject < 0 || indeterminate < 0) {
        issues.push(
          issue(
            "IndeterminateMisclassification",
            `cohorts[${index}]`,
            "cohort decision counts must be non-negative distinct buckets",
          ),
        );
      }
    }
  });
  if (claimsGap && !(hasOrdinary && hasOptimized)) {
    issues.push(
      issue(
        "OptimizationGapCohorts",
        "cohorts",
        "optimization-gap metrics require ordinary and optimized cohorts",
      ),
    );
  }
  if (data.release_grade === true && data.independent_adjudication !== true) {
    issues.push(
      issue(
        "ReleaseGradeAdjudication",
        "independent_adjudication",
        "release-grade reports require independent_adjudication=true",
      ),
    );
  }
  return issues;
}

export function validateVaSemantics(
  data: Record<string, unknown>,
  artifactType: string,
): SemanticIssue[] {
  switch (artifactType) {
    case "VerifierProfile.v1":
      return validateVerifierProfileSemantics(data);
    case "VerificationResult.v1":
      return validateVerificationResultSemantics(data);
    case "RewardEvidenceEnvelope.v1":
      return validateRewardEnvelopeSemantics(data);
    case "OptimizationCampaignManifest.v1":
      return validateCampaignManifestSemantics(data);
    case "AdjudicationRecord.v1":
      return validateAdjudicationRecordSemantics(data, false);
    case "VerifierAssuranceReport.v1":
      return validateAssuranceReportSemantics(data);
    default:
      return [
        issue(
          "UnknownArtifactType",
          "artifact_type",
          `unknown verifier-assurance artifact type: ${artifactType}`,
        ),
      ];
  }
}

export function validateVaSemanticsStrings(
  data: Record<string, unknown>,
  artifactType: string,
): string[] {
  return validateVaSemantics(data, artifactType).map(formatSemanticIssue);
}

/** Verify report: semantics + integrity digest match (Python verify_assurance_report). */
export function verifyAssuranceReport(report: Record<string, unknown>): SemanticIssue[] {
  const issues = validateAssuranceReportSemantics(report);
  const integrity = report.integrity;
  if (integrity && typeof integrity === "object" && !Array.isArray(integrity)) {
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(report)) {
      if (k !== "integrity") body[k] = v;
    }
    const expected = canonicalHash(body);
    const got = (integrity as Record<string, unknown>).artifact_digest;
    if (got !== expected) {
      issues.push(
        issue(
          "ReportDigestMismatch",
          "integrity.artifact_digest",
          "artifact_digest does not match report body",
        ),
      );
    }
  }
  return issues;
}

const REQUIRED_FIELDS: Record<string, string[]> = {
  "VerifierProfile.v1": [
    "schema_version",
    "artifact_type",
    "verifier_profile_id",
    "created_at",
    "producer",
    "producer_version",
    "source_repo",
    "source_commit",
    "implementation",
    "configuration",
    "mechanism",
    "claim_surface",
    "applicability",
    "assumptions",
    "known_blind_spots",
    "integrity",
  ],
  "VerificationResult.v1": [
    "schema_version",
    "artifact_type",
    "verification_result_id",
    "created_at",
    "producer",
    "producer_version",
    "source_repo",
    "source_commit",
    "verifier_profile",
    "claim_ids",
    "raw_backend_output_digest",
    "normalized_result_digest",
    "normalization_applied",
    "check_groups",
    "resource_limits",
    "execution_status",
    "decision",
    "integrity",
  ],
  "RewardEvidenceEnvelope.v1": [
    "schema_version",
    "artifact_type",
    "reward_envelope_id",
    "created_at",
    "producer",
    "producer_version",
    "source_repo",
    "source_commit",
    "scalar_total",
    "components",
    "composition_function",
    "integrity",
  ],
  "OptimizationCampaignManifest.v1": [
    "schema_version",
    "artifact_type",
    "campaign_id",
    "created_at",
    "producer",
    "producer_version",
    "source_repo",
    "source_commit",
    "access_class",
    "cohorts",
    "integrity",
  ],
  "AdjudicationRecord.v1": [
    "schema_version",
    "artifact_type",
    "adjudication_id",
    "created_at",
    "producer",
    "producer_version",
    "source_repo",
    "source_commit",
    "subject",
    "label",
    "independence_declared",
    "integrity",
  ],
  "VerifierAssuranceReport.v1": [
    "schema_version",
    "artifact_type",
    "report_id",
    "created_at",
    "producer",
    "producer_version",
    "source_repo",
    "source_commit",
    "campaign_ref",
    "release_grade",
    "independent_adjudication",
    "metrics",
    "cohorts",
    "integrity",
  ],
};

/**
 * Constructor requiring mandatory fields. Unknown fields are retained (no silent drop)
 * so schema validation can reject additionalProperties.
 */
export function constructVaArtifact(
  artifactType: string,
  fields: Record<string, unknown>,
): Record<string, unknown> {
  const required = REQUIRED_FIELDS[artifactType];
  if (!required) {
    throw new Error(`unsupported VA constructor type: ${artifactType}`);
  }
  for (const key of required) {
    if (!(key in fields)) {
      throw new Error(`${artifactType}: missing mandatory field ${key}`);
    }
  }
  if (fields.artifact_type !== artifactType) {
    throw new Error(`${artifactType}: artifact_type must be ${JSON.stringify(artifactType)}`);
  }
  return { ...fields };
}

export function attachNestedIntegrity(
  data: Record<string, unknown>,
): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    if (k !== "integrity") body[k] = v;
  }
  const digest = canonicalHash(body);
  return {
    ...body,
    integrity: {
      canonicalization_version: "v1",
      artifact_digest: digest,
    },
  };
}
