export const ARTIFACT_STATUSES = new Set([
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
]);

export const TRACE_CERTIFICATE_STATUSES = new Set([
  "CertificatePending",
  "CertificateChecked",
  "Rejected",
  "Stale",
]);

export function isValidStatus(value: string): boolean {
  return ARTIFACT_STATUSES.has(value);
}
