export type ArtifactType =
  | "AssumptionSet.v0"
  | "SourceSpan.v0"
  | "ClaimArtifact.v0"
  | "RuntimeReceipt.v0"
  | "TraceCertificate.v0"
  | "EvidenceBundle.v0"
  | "ScienceClaimBundle.v0"
  | "VerificationResult.v0";

export interface ClaimArtifactV0 {
  artifact_id: string;
  artifact_type: "ClaimArtifact.v0";
  schema_version: string;
  claim_text: string;
  claim_kind: string;
  status: string;
  assumption_set_ref: string;
  source_span_refs: string[];
  formal_statement: string;
  certificate_refs: string[];
  runtime_receipt_refs: string[];
  created_at: string;
  producer: string;
  producer_version: string;
  source_repo: string;
  source_commit: string;
  signature_or_digest: string;
}

export interface RuntimeReceiptV0 {
  receipt_id: string;
  schema_version: string;
  run_id: string;
  environment: Record<string, string>;
  started_at: string;
  ended_at: string;
  status: string;
  events_hash: string;
  policy_hash: string;
  trace_hash: string;
  producer: string;
  producer_version: string;
  source_repo: string;
  source_commit: string;
  input_hashes: Record<string, string>;
  output_hashes: Record<string, string>;
  signature_or_digest: string;
}

export interface TraceCertificateV0 {
  certificate_id: string;
  schema_version: string;
  trace_hash: string;
  spec_hash: string;
  property_id: string;
  checker: string;
  checker_version: string;
  status: string;
  counterexample_ref: string | null;
  created_at: string;
  producer: string;
  producer_version: string;
  source_repo: string;
  source_commit: string;
  signature_or_digest: string;
}

export interface ScienceClaimBundleV0 {
  bundle_id: string;
  schema_version: string;
  claim_artifact: ClaimArtifactV0;
  assumption_set: { assumption_set_id: string };
  runtime_receipts: RuntimeReceiptV0[];
  certificates: TraceCertificateV0[];
  evidence_bundle: Record<string, unknown>;
  verification_policy: { policy_id: string; required_checks: string[] };
  created_at: string;
  producer: string;
  producer_version: string;
  source_repo: string;
  source_commit: string;
  signature_or_digest: string;
}

export function detectArtifactType(data: Record<string, unknown>): ArtifactType | null {
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
