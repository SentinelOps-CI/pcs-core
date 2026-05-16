use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimArtifactV0 {
    pub artifact_id: String,
    pub artifact_type: String,
    pub schema_version: String,
    pub claim_text: String,
    pub claim_kind: String,
    pub status: String,
    pub assumption_set_ref: String,
    pub source_span_refs: Vec<String>,
    pub formal_statement: String,
    pub certificate_refs: Vec<String>,
    pub runtime_receipt_refs: Vec<String>,
    pub created_at: String,
    pub producer: String,
    pub producer_version: String,
    pub source_repo: String,
    pub source_commit: String,
    pub signature_or_digest: String,
}
