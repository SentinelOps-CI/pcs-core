use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceSpanV0 {
    pub source_span_id: String,
    pub schema_version: String,
    pub source_type: String,
    pub source_uri: String,
    pub start: SpanPosition,
    pub end: SpanPosition,
    pub hash: String,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpanPosition {
    pub line: u32,
    pub column: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssumptionV0 {
    pub assumption_id: String,
    pub text: String,
    pub kind: String,
    pub status: String,
    pub source_span_refs: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssumptionSetV0 {
    pub assumption_set_id: String,
    pub schema_version: String,
    pub created_at: String,
    pub producer: String,
    pub producer_version: String,
    pub source_repo: String,
    pub source_commit: String,
    pub assumptions: Vec<AssumptionV0>,
    pub human_review_status: String,
    pub status: String,
    pub signature_or_digest: String,
}
