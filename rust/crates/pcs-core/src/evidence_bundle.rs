use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::artifact::AssumptionSetV0;
use crate::claim::ClaimArtifactV0;
use crate::runtime_receipt::RuntimeReceiptV0;
use crate::trace_certificate::TraceCertificateV0;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvidenceBundleV0 {
    pub bundle_id: String,
    pub schema_version: String,
    pub claim_refs: Vec<String>,
    pub assumption_set_refs: Vec<String>,
    pub runtime_receipt_refs: Vec<String>,
    pub certificate_refs: Vec<String>,
    pub artifact_hashes: BTreeMap<String, String>,
    pub created_at: String,
    pub producer: String,
    pub producer_version: String,
    pub source_repo: String,
    pub source_commit: String,
    pub signature_or_digest: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationPolicy {
    pub policy_id: String,
    pub required_checks: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScienceClaimBundleV0 {
    pub bundle_id: String,
    pub schema_version: String,
    pub claim_artifact: ClaimArtifactV0,
    pub assumption_set: AssumptionSetV0,
    pub runtime_receipts: Vec<RuntimeReceiptV0>,
    pub certificates: Vec<TraceCertificateV0>,
    pub evidence_bundle: EvidenceBundleV0,
    pub verification_policy: VerificationPolicy,
    pub created_at: String,
    pub producer: String,
    pub producer_version: String,
    pub source_repo: String,
    pub source_commit: String,
    pub signature_or_digest: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationCheck {
    pub check_id: String,
    pub description: String,
    pub status: String,
    pub details: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationResultV0 {
    pub verification_id: String,
    pub schema_version: String,
    pub bundle_id: String,
    pub verifier: String,
    pub verifier_version: String,
    pub status: String,
    pub checks: Vec<VerificationCheck>,
    pub created_at: String,
    pub source_repo: String,
    pub source_commit: String,
    pub signature_or_digest: String,
}
