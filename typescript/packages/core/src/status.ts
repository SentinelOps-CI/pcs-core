export const ARTIFACT_STATUSES = [
  "Draft",
  "Extracted",
  "HumanReviewed",
  "Formalized",
  "ProofPending",
  "ProofChecked",
  "CertificatePending",
  "CertificateChecked",
  "RuntimeObserved",
  "RuntimeChecked",
  "Rejected",
  "EmpiricalOnly",
  "Deprecated",
  "Stale",
] as const;

export type ArtifactStatus = (typeof ARTIFACT_STATUSES)[number];

export function isValidStatus(value: string): value is ArtifactStatus {
  return (ARTIFACT_STATUSES as readonly string[]).includes(value);
}
