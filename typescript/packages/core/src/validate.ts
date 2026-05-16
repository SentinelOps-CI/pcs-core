import type {
  ArtifactType,
  ClaimArtifactV0,
  RuntimeReceiptV0,
  ScienceClaimBundleV0,
} from "./artifact.js";
import { detectArtifactType } from "./artifact.js";
import { isValidStatus } from "./status.js";

export class ValidationError extends Error {
  readonly errors: string[];

  constructor(message: string, errors: string[] = []) {
    super(message);
    this.name = "ValidationError";
    this.errors = errors;
  }
}

const SHA256 = /^sha256:[a-f0-9]{64}$/;

function requireString(obj: Record<string, unknown>, key: string, errors: string[]): string {
  const value = obj[key];
  if (typeof value !== "string" || value.length === 0) {
    errors.push(`missing or invalid string field: ${key}`);
    return "";
  }
  return value;
}

function validateBaseMetadata(obj: Record<string, unknown>, errors: string[]): void {
  requireString(obj, "schema_version", errors);
  if (obj.schema_version !== "v0") {
    errors.push("schema_version must be v0");
  }
}

function validateClaimArtifact(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateBaseMetadata(data, errors);
  requireString(data, "artifact_id", errors);
  if (data.artifact_type !== "ClaimArtifact.v0") {
    errors.push("artifact_type must be ClaimArtifact.v0");
  }
  const ref = requireString(data, "assumption_set_ref", errors);
  if (!ref.trim()) {
    errors.push("ClaimArtifact.v0 requires non-empty assumption_set_ref");
  }
  const status = requireString(data, "status", errors);
  if (!isValidStatus(status)) {
    errors.push(`invalid status: ${status}`);
  }
  requireString(data, "signature_or_digest", errors);
  if (typeof data.signature_or_digest === "string" && !SHA256.test(data.signature_or_digest)) {
    errors.push("invalid signature_or_digest");
  }
  return errors;
}

function validateRuntimeReceipt(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateBaseMetadata(data, errors);
  requireString(data, "receipt_id", errors);
  const status = requireString(data, "status", errors);
  if (!isValidStatus(status)) {
    errors.push(`invalid status: ${status}`);
  }
  for (const field of ["events_hash", "policy_hash", "trace_hash", "signature_or_digest"]) {
    const v = requireString(data, field, errors);
    if (v && !SHA256.test(v)) {
      errors.push(`invalid ${field}`);
    }
  }
  return errors;
}

function validateScienceClaimBundle(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateBaseMetadata(data, errors);
  requireString(data, "bundle_id", errors);

  const claim = data.claim_artifact;
  if (!claim || typeof claim !== "object") {
    errors.push("missing claim_artifact");
    return errors;
  }
  errors.push(...validateClaimArtifact(claim as Record<string, unknown>));

  const assumption = data.assumption_set;
  if (!assumption || typeof assumption !== "object") {
    errors.push("missing assumption_set");
    return errors;
  }

  const claimRef = (claim as ClaimArtifactV0).assumption_set_ref;
  const assumptionId = (assumption as { assumption_set_id?: string }).assumption_set_id;
  if (claimRef && assumptionId && claimRef !== assumptionId) {
    errors.push("assumption_set_ref mismatch");
  }

  const receipts = data.runtime_receipts;
  const certificates = data.certificates;
  if (Array.isArray(receipts) && Array.isArray(certificates)) {
    for (const receipt of receipts) {
      if (!receipt || typeof receipt !== "object") continue;
      const rHash = (receipt as RuntimeReceiptV0).trace_hash;
      for (const cert of certificates) {
        if (!cert || typeof cert !== "object") continue;
        const cHash = (cert as { trace_hash?: string }).trace_hash;
        if (rHash && cHash && rHash !== cHash) {
          errors.push("trace_hash mismatch between receipt and certificate");
        }
      }
    }
  }

  return errors;
}

const validators: Partial<Record<ArtifactType, (d: Record<string, unknown>) => string[]>> = {
  "ClaimArtifact.v0": validateClaimArtifact,
  "RuntimeReceipt.v0": validateRuntimeReceipt,
  "ScienceClaimBundle.v0": validateScienceClaimBundle,
};

export function validateArtifact(data: Record<string, unknown>, artifactType?: ArtifactType): void {
  const type = artifactType ?? detectArtifactType(data);
  if (!type) {
    throw new ValidationError("Could not detect artifact type");
  }
  const validator = validators[type];
  const errors: string[] = [];
  if (validator) {
    errors.push(...validator(data));
  } else {
    validateBaseMetadata(data, errors);
  }
  if (errors.length > 0) {
    throw new ValidationError(`Validation failed for ${type}`, errors);
  }
}

export function parseScienceClaimBundle(data: Record<string, unknown>): ScienceClaimBundleV0 {
  validateArtifact(data, "ScienceClaimBundle.v0");
  return data as unknown as ScienceClaimBundleV0;
}
