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
  | "ReleaseManifest.v0"
  | "HandoffManifest.v0"
  | "ReleaseChainValidationResult.v0"
  | "ArtifactRegistry.v0"
  | "MigrationReport.v0";

const PROTOCOL_ARTIFACT_TYPES = new Set<ArtifactType>([
  "ReleaseManifest.v0",
  "HandoffManifest.v0",
  "ReleaseChainValidationResult.v0",
  "ArtifactRegistry.v0",
  "MigrationReport.v0",
] as ArtifactType[]);

export function detectArtifactType(data: Record<string, unknown>): ArtifactType | null {
  if ("from_version" in data && "to_version" in data && "changes" in data && "artifact_type" in data) {
    return "MigrationReport.v0";
  }
  if ("validation_id" in data && "artifacts_checked" in data) {
    return "ReleaseChainValidationResult.v0";
  }
  if ("handoff_id" in data && "handoff_kind" in data) {
    return "HandoffManifest.v0";
  }
  if ("registry_id" in data && "entries" in data && "registry_version" in data) {
    return "ArtifactRegistry.v0";
  }
  if ("release_id" in data && "producer_repos" in data && "validation_profile" in data) {
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
  if (errors.length > 0) {
    throw new ValidationError(`Validation failed for ${type}`, errors);
  }
}
