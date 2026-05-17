pub const ARTIFACT_STATUSES: &[&str] = &[
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
];

pub const TRACE_CERTIFICATE_STATUSES: &[&str] = &[
    "CertificatePending",
    "CertificateChecked",
    "Rejected",
    "Stale",
];

pub const CERTIFIED_CLAIM_STATUSES: &[&str] =
    &["CertificateChecked", "ProofChecked", "RuntimeChecked"];
