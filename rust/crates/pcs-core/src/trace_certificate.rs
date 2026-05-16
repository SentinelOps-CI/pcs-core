use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceCertificateV0 {
    pub certificate_id: String,
    pub schema_version: String,
    pub trace_hash: String,
    pub spec_hash: String,
    pub property_id: String,
    pub checker: String,
    pub checker_version: String,
    pub status: String,
    pub counterexample_ref: Option<String>,
    pub created_at: String,
    pub producer: String,
    pub producer_version: String,
    pub source_repo: String,
    pub source_commit: String,
    pub signature_or_digest: String,
}
