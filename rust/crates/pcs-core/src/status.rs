use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum ArtifactStatus {
    Draft,
    Extracted,
    HumanReviewed,
    Formalized,
    ProofPending,
    ProofChecked,
    CertificatePending,
    CertificateChecked,
    RuntimeObserved,
    RuntimeChecked,
    Rejected,
    EmpiricalOnly,
    Deprecated,
    Stale,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum TraceCertificateStatus {
    CertificatePending,
    CertificateChecked,
    Rejected,
    Stale,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum CheckStatus {
    Passed,
    Failed,
    Skipped,
    Warning,
}
