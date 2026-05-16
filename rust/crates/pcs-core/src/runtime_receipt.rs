use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuntimeReceiptV0 {
    pub receipt_id: String,
    pub schema_version: String,
    pub run_id: String,
    pub environment: BTreeMap<String, String>,
    pub started_at: String,
    pub ended_at: String,
    pub status: String,
    pub events_hash: String,
    pub policy_hash: String,
    pub trace_hash: String,
    pub producer: String,
    pub producer_version: String,
    pub source_repo: String,
    pub source_commit: String,
    pub input_hashes: BTreeMap<String, String>,
    pub output_hashes: BTreeMap<String, String>,
    pub signature_or_digest: String,
}
