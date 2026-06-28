import {
  validateBenchmarkArtifactRefSemantics,
  validatePcsBenchIngestSemantics,
} from "./benchmarkIngest.js";
import {
  validateDirectTraceActionSemantics,
  validatePfcoreCertificateSemantics,
  validatePfcoreTraceHashChain,
} from "./pfCore.js";
import { ARTIFACT_STATUSES, TRACE_CERTIFICATE_STATUSES } from "./status.js";
import { isZeroSourceCommit } from "./hash.js";
import { validateSchema } from "./schema.js";

export class ValidationError extends Error {
  readonly errors: string[];

  constructor(message: string, errors: string[] = []) {
    super(message);
    this.name = "ValidationError";
    this.errors = errors;
  }
}

const CERTIFIED_CLAIM_STATUSES = new Set([
  "CertificateChecked",
  "ProofChecked",
  "RuntimeChecked",
]);

const IMPORT_READY_VERIFICATION_STATUSES = new Set([
  "ProofChecked",
  "CertificateChecked",
  "RuntimeChecked",
]);

export type ArtifactType =
  | "AssumptionSet.v0"
  | "SourceSpan.v0"
  | "ClaimArtifact.v0"
  | "RuntimeReceipt.v0"
  | "TraceCertificate.v0"
  | "EvidenceBundle.v0"
  | "ScienceClaimBundle.v0"
  | "VerificationResult.v0"
  | "SignedScienceClaimBundle.v0"
  | "PFCorePrincipal.v0"
  | "PFCoreCapability.v0"
  | "PFCoreResource.v0"
  | "PFCoreAction.v0"
  | "PFCoreEffect.v0"
  | "PFCoreDecision.v0"
  | "PFCoreEvent.v0"
  | "PFCoreTrace.v0"
  | "PFCoreContract.v0"
  | "PFCoreHandoff.v0"
  | "PFCoreRuntimeObservation.v0"
  | "PFCoreCertificate.v0"
  | "PCSBridgeCertificate.v0"
  | "ReleaseManifest.v0"
  | "HandoffManifest.v0"
  | "ReleaseChainValidationResult.v0"
  | "ArtifactRegistry.v0"
  | "SemanticCheckExecution.v0"
  | "ComponentReleaseFragment.v0"
  | "MigrationReport.v0"
  | "WorkflowProfile.v0"
  | "ToolUseTrace.v0"
  | "ToolUseCertificate.v0"
  | "DatasetReceipt.v0"
  | "EnvironmentReceipt.v0"
  | "ComputationRunReceipt.v0"
  | "ResultArtifact.v0"
  | "ComputationWitness.v0"
  | "ProofObligation.v0"
  | "LeanCheckResult.v0"
  | "BenchmarkRegistry.v0"
  | "BenchmarkSuiteManifest.v0"
  | "BenchmarkTask.v0"
  | "BenchmarkCase.v0"
  | "BenchmarkRun.v0"
  | "BenchmarkReport.v0"
  | "MetricSummary.v0"
  | "PcsBenchIngest.v0"
  | "BenchmarkArtifactRef.v0"
  | "ConformanceRun.v0"
  | "FailureCaseManifest.v0"
  | "FailureLocalizationResult.v0"
  | "CoverageReport.v0"
  | "ExplainQualityReport.v0"
  | "ProfileCoverageReport.v0"
  | "BenchmarkMetricRegistry.v0"
  | "ConformanceReport.v0";

const PROTOCOL_ARTIFACT_TYPES = new Set<ArtifactType>([
  "ReleaseManifest.v0",
  "HandoffManifest.v0",
  "ReleaseChainValidationResult.v0",
  "ArtifactRegistry.v0",
  "SemanticCheckExecution.v0",
  "MigrationReport.v0",
] as ArtifactType[]);

const EXPLICIT_ARTIFACT_TYPES = new Set<ArtifactType>([
  "PFCorePrincipal.v0",
  "PFCoreCapability.v0",
  "PFCoreResource.v0",
  "PFCoreAction.v0",
  "PFCoreEffect.v0",
  "PFCoreDecision.v0",
  "PFCoreEvent.v0",
  "PFCoreTrace.v0",
  "PFCoreContract.v0",
  "PFCoreHandoff.v0",
  "PFCoreRuntimeObservation.v0",
  "PFCoreCertificate.v0",
  "LeanCheckResult.v0",
  "ToolUseTrace.v0",
  "PCSBridgeCertificate.v0",
  "ClaimArtifact.v0",
]);

export function detectArtifactType(data: Record<string, unknown>): ArtifactType | null {
  const explicit = data.artifact_type;
  if (typeof explicit === "string" && EXPLICIT_ARTIFACT_TYPES.has(explicit as ArtifactType)) {
    return explicit as ArtifactType;
  }
  if (
    data.schema_version === "v0" &&
    typeof data.registry_id === "string" &&
    typeof data.metrics === "object" &&
    data.metrics !== null &&
    "registry_version" in data &&
    !("suites" in data)
  ) {
    return "BenchmarkMetricRegistry.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.registry_id === "string" &&
    typeof data.suites === "object" &&
    data.suites !== null &&
    "registry_version" in data
  ) {
    return "BenchmarkRegistry.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.report_id === "string" &&
    Array.isArray(data.required_sections) &&
    "quality_score" in data
  ) {
    return "ExplainQualityReport.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.coverage_id === "string" &&
    typeof data.workflow_profile_id === "string" &&
    Array.isArray(data.artifact_types_required)
  ) {
    return "ProfileCoverageReport.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.artifact_type === "string" &&
    typeof data.path === "string" &&
    typeof data.sha256 === "string" &&
    typeof data.role === "string" &&
    !("producer_id" in data) &&
    !("benchmark_runs" in data)
  ) {
    return "BenchmarkArtifactRef.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.producer_id === "string" &&
    typeof data.suite_id === "string" &&
    Array.isArray(data.benchmark_runs) &&
    Array.isArray(data.logs) &&
    "workflow_id" in data
  ) {
    return "PcsBenchIngest.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.metric_id === "string" &&
    "applicability" in data &&
    "score" in data &&
    "numerator" in data &&
    !("benchmark_suite_id" in data)
  ) {
    return "MetricSummary.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.report_id === "string" &&
    typeof data.benchmark_suite_id === "string" &&
    typeof data.summary === "object" &&
    data.summary !== null
  ) {
    return "BenchmarkReport.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.run_id === "string" &&
    typeof data.case_id === "string" &&
    "duration_ms" in data &&
    "observed_status" in data
  ) {
    return "BenchmarkRun.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.case_id === "string" &&
    typeof data.case_kind === "string" &&
    "input_artifacts" in data
  ) {
    return "BenchmarkCase.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.suite_id === "string" &&
    Array.isArray(data.case_ids) &&
    Array.isArray(data.cases) &&
    "case_count" in data &&
    typeof data.task_id === "string"
  ) {
    return "BenchmarkSuiteManifest.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.task_id === "string" &&
    Array.isArray(data.metrics) &&
    "success_criteria" in data
  ) {
    return "BenchmarkTask.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.coverage_id === "string" &&
    "coverage_ratio" in data &&
    "numerator" in data &&
    ("metric" in data || "metric_id" in data)
  ) {
    return "CoverageReport.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.result_id === "string" &&
    "localized_correctly" in data
  ) {
    return "FailureLocalizationResult.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.manifest_id === "string" &&
    typeof data.failure_code === "string" &&
    "repair_hint_kind" in data
  ) {
    return "FailureCaseManifest.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.run_id === "string" &&
    typeof data.suite === "string" &&
    "started_at" in data &&
    "completed_at" in data
  ) {
    return "ConformanceRun.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.suite === "string" &&
    "checks_passed" in data &&
    "checks_failed" in data &&
    Array.isArray(data.failures)
  ) {
    return "ConformanceReport.v0";
  }
  if ("policy_id" in data && "severity_definitions" in data && Array.isArray(data.checks)) {
    return "SemanticCheckExecution.v0";
  }
  if ("from_version" in data && "to_version" in data && "changes" in data && "artifact_type" in data) {
    return "MigrationReport.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.check_id === "string" &&
    typeof data.proof_obligation_id === "string" &&
    "lean_theorem" in data &&
    "lean_version" in data
  ) {
    return "LeanCheckResult.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.obligation_id === "string" &&
    Array.isArray(data.obligations) &&
    "lean_module" in data
  ) {
    return "ProofObligation.v0";
  }
  if ("validation_id" in data && "artifacts_checked" in data) {
    return "ReleaseChainValidationResult.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.component === "string" &&
    data.artifacts &&
    typeof data.artifacts === "object" &&
    "signature_or_digest" in data &&
    "source_commit" in data
  ) {
    return "ComponentReleaseFragment.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.workflow_id === "string" &&
    typeof data.domain === "string" &&
    Array.isArray(data.handoff_sequence) &&
    Array.isArray(data.runtime_artifacts)
  ) {
    return "WorkflowProfile.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.witness_id === "string" &&
    typeof data.dataset_hash === "string" &&
    typeof data.run_receipt_hash === "string"
  ) {
    return "ComputationWitness.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.dataset_id === "string" &&
    typeof data.aggregate_hash === "string" &&
    Array.isArray(data.files)
  ) {
    return "DatasetReceipt.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.environment_id === "string" &&
    typeof data.environment_kind === "string"
  ) {
    return "EnvironmentReceipt.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.run_id === "string" &&
    typeof data.command === "string" &&
    "dataset_receipt_ref" in data
  ) {
    return "ComputationRunReceipt.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.result_id === "string" &&
    typeof data.result_kind === "string"
  ) {
    return "ResultArtifact.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.trace_id === "string" &&
    Array.isArray(data.tool_calls)
  ) {
    return "ToolUseTrace.v0";
  }
  if (
    data.schema_version === "v0" &&
    typeof data.certificate_id === "string" &&
    "policy_hash" in data &&
    Array.isArray(data.violations) &&
    !("spec_hash" in data)
  ) {
    return "ToolUseCertificate.v0";
  }
  if ("handoff_id" in data && "handoff_kind" in data) {
    return "HandoffManifest.v0";
  }
  if ("registry_id" in data && "entries" in data && "registry_version" in data) {
    return "ArtifactRegistry.v0";
  }
  if (
    "release_id" in data &&
    "producer_repos" in data &&
    "validation_profile" in data &&
    "workflow_profile_id" in data
  ) {
    return "ReleaseManifest.v0";
  }
  if ("signed_bundle_id" in data && "science_claim_bundle" in data) {
    return "SignedScienceClaimBundle.v0";
  }
  if ("claim_artifact" in data && "bundle_id" in data) return "ScienceClaimBundle.v0";
  if ("verification_id" in data) return "VerificationResult.v0";
  if ("receipt_id" in data) return "RuntimeReceipt.v0";
  if ("certificate_id" in data) return "TraceCertificate.v0";
  if ("assumption_set_id" in data) return "AssumptionSet.v0";
  if ("source_span_id" in data) return "SourceSpan.v0";
  if (data.artifact_type === "ClaimArtifact.v0") return "ClaimArtifact.v0";
  if ("claim_refs" in data && "bundle_id" in data) return "EvidenceBundle.v0";
  return null;
}

function checkSourceCommits(
  value: unknown,
  path: string,
  errors: string[],
  inheritedLocalDev: boolean,
): void {
  if (Array.isArray(value)) {
    value.forEach((item, index) =>
      checkSourceCommits(item, `${path}[${index}]`, errors, inheritedLocalDev),
    );
    return;
  }
  if (value === null || typeof value !== "object") return;
  const obj = value as Record<string, unknown>;
  const localDev = inheritedLocalDev || obj.local_dev === true;
  const commit = obj.source_commit;
  if (typeof commit === "string" && isZeroSourceCommit(commit) && !localDev) {
    errors.push(`${path || "root"}: zero source_commit not allowed without local_dev=true`);
  }
  for (const [key, child] of Object.entries(obj)) {
    const childPath = path ? `${path}.${key}` : key;
    checkSourceCommits(child, childPath, errors, localDev);
  }
}

function validateScienceClaimBundle(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  const assumptionSet = data.assumption_set;
  if (!assumptionSet || typeof assumptionSet !== "object") {
    errors.push("ScienceClaimBundle.v0 requires assumption_set");
  } else {
    const assumptions = (assumptionSet as Record<string, unknown>).assumptions;
    if (!Array.isArray(assumptions) || assumptions.length === 0) {
      errors.push("ScienceClaimBundle.v0 requires non-empty assumption_set.assumptions");
    }
  }
  const receipts = data.runtime_receipts;
  if (!Array.isArray(receipts) || receipts.length === 0) {
    errors.push("ScienceClaimBundle.v0 requires non-empty runtime_receipts");
  }
  const claim = data.claim_artifact;
  const claimStatus =
    claim && typeof claim === "object"
      ? String((claim as Record<string, unknown>).status ?? "")
      : "";
  const certificates = Array.isArray(data.certificates) ? data.certificates : [];
  if (CERTIFIED_CLAIM_STATUSES.has(claimStatus) && certificates.length === 0) {
    errors.push("certified ScienceClaimBundle requires at least one TraceCertificate");
  }
  if (Array.isArray(receipts)) {
    for (const receipt of receipts) {
      if (!receipt || typeof receipt !== "object") continue;
      const rHash = (receipt as Record<string, unknown>).trace_hash;
      for (const cert of certificates) {
        if (!cert || typeof cert !== "object") continue;
        const cHash = (cert as Record<string, unknown>).trace_hash;
        const cStatus = String((cert as Record<string, unknown>).status ?? "");
        if (cStatus && !TRACE_CERTIFICATE_STATUSES.has(cStatus)) {
          errors.push(`invalid TraceCertificate status ${cStatus}`);
        }
        if (rHash && cHash && rHash !== cHash) {
          errors.push("trace_hash mismatch between receipt and certificate");
        }
      }
    }
  }
  return errors;
}

function validateVerificationResult(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  const checks = data.checks;
  if (!Array.isArray(checks)) {
    return errors;
  }
  const hasFailed = checks.some(
    (check) =>
      check &&
      typeof check === "object" &&
      (check as Record<string, unknown>).status === "failed",
  );
  const topStatus = String(data.status ?? "");
  if (hasFailed && IMPORT_READY_VERIFICATION_STATUSES.has(topStatus)) {
    errors.push(
      `VerificationResult.v0 with failed checks cannot use import-ready status ${topStatus} (Scientific Memory import contract)`,
    );
  }
  return errors;
}

export function validateArtifact(
  data: Record<string, unknown>,
  artifactType?: ArtifactType,
): void {
  const type = artifactType ?? detectArtifactType(data);
  if (!type) {
    throw new ValidationError("Could not detect artifact type");
  }
  const errors: string[] = [...validateSchema(data, type)];
  if (PROTOCOL_ARTIFACT_TYPES.has(type)) {
    if (errors.length > 0) {
      throw new ValidationError(`Validation failed for ${type}`, errors);
    }
    return;
  }
  checkSourceCommits(data, "", errors, false);

  if (type === "RuntimeReceipt.v0") {
    const status = String(data.status ?? "");
    if (status && !ARTIFACT_STATUSES.has(status)) {
      errors.push(`unknown status ${status}`);
    }
  }
  if (type === "ScienceClaimBundle.v0") {
    errors.push(...validateScienceClaimBundle(data));
  }
  if (type === "VerificationResult.v0") {
    errors.push(...validateVerificationResult(data));
  }
  if (type === "SignedScienceClaimBundle.v0") {
    const scb = data.science_claim_bundle;
    if (scb && typeof scb === "object") {
      errors.push(...validateScienceClaimBundle(scb as Record<string, unknown>));
    }
    const vr = data.verification_result;
    if (vr && typeof vr === "object") {
      errors.push(...validateVerificationResult(vr as Record<string, unknown>));
    }
  }
  if (type === "TraceCertificate.v0") {
    const status = String(data.status ?? "");
    if (status && !TRACE_CERTIFICATE_STATUSES.has(status)) {
      errors.push(`TraceCertificate.v0 invalid status ${status}`);
    }
  }
  if (type === "PFCoreTrace.v0") {
    errors.push(...validateDirectTraceActionSemantics(data));
    errors.push(...validatePfcoreTraceHashChain(data));
  }
  if (type === "PFCoreCertificate.v0") {
    errors.push(...validatePfcoreCertificateSemantics(data));
  }
  if (type === "BenchmarkArtifactRef.v0") {
    errors.push(...validateBenchmarkArtifactRefSemantics(data));
  }
  if (type === "PcsBenchIngest.v0") {
    errors.push(...validatePcsBenchIngestSemantics(data));
  }
  if (errors.length > 0) {
    throw new ValidationError(`Validation failed for ${type}`, errors);
  }
}
