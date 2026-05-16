use serde::de::DeserializeOwned;
use serde_json::Value;

use crate::claim::ClaimArtifactV0;
use crate::evidence_bundle::{ScienceClaimBundleV0, VerificationResultV0};
use crate::runtime_receipt::RuntimeReceiptV0;
use crate::trace_certificate::TraceCertificateV0;
use crate::artifact::{AssumptionSetV0, SourceSpanV0};
use crate::evidence_bundle::EvidenceBundleV0;

#[derive(Debug)]
pub struct ValidationError {
    pub message: String,
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl std::error::Error for ValidationError {}

pub fn detect_artifact_type(value: &Value) -> Option<&'static str> {
    let obj = value.as_object()?;
    if obj.contains_key("claim_artifact") && obj.contains_key("bundle_id") {
        return Some("ScienceClaimBundle.v0");
    }
    if obj.contains_key("verification_id") {
        return Some("VerificationResult.v0");
    }
    if obj.contains_key("receipt_id") {
        return Some("RuntimeReceipt.v0");
    }
    if obj.contains_key("certificate_id") {
        return Some("TraceCertificate.v0");
    }
    if obj.contains_key("assumption_set_id") {
        return Some("AssumptionSet.v0");
    }
    if obj.contains_key("source_span_id") {
        return Some("SourceSpan.v0");
    }
    if obj.get("artifact_type").and_then(|v| v.as_str()) == Some("ClaimArtifact.v0") {
        return Some("ClaimArtifact.v0");
    }
    if obj.contains_key("claim_refs") {
        return Some("EvidenceBundle.v0");
    }
    None
}

pub fn parse_artifact<T: DeserializeOwned>(value: &Value) -> Result<T, ValidationError> {
    serde_json::from_value(value.clone()).map_err(|e| ValidationError {
        message: e.to_string(),
    })
}

pub fn validate_semantics(value: &Value, artifact_type: &str) -> Result<(), ValidationError> {
    match artifact_type {
        "ClaimArtifact.v0" => {
            let claim: ClaimArtifactV0 = parse_artifact(value)?;
            if claim.assumption_set_ref.trim().is_empty() {
                return Err(ValidationError {
                    message: "ClaimArtifact.v0 requires non-empty assumption_set_ref".into(),
                });
            }
        }
        "ScienceClaimBundle.v0" => {
            let bundle: ScienceClaimBundleV0 = parse_artifact(value)?;
            if bundle.claim_artifact.assumption_set_ref.trim().is_empty() {
                return Err(ValidationError {
                    message: "claim_artifact missing assumption_set_ref".into(),
                });
            }
            if bundle.claim_artifact.assumption_set_ref != bundle.assumption_set.assumption_set_id
            {
                return Err(ValidationError {
                    message: "assumption_set_ref mismatch".into(),
                });
            }
            for receipt in &bundle.runtime_receipts {
                for cert in &bundle.certificates {
                    if receipt.trace_hash != cert.trace_hash {
                        return Err(ValidationError {
                            message: format!(
                                "trace_hash mismatch: {} vs {}",
                                receipt.receipt_id, cert.certificate_id
                            ),
                        });
                    }
                }
            }
        }
        _ => {}
    }
    Ok(())
}

pub fn deserialize_typed(value: &Value, artifact_type: &str) -> Result<(), ValidationError> {
    match artifact_type {
        "AssumptionSet.v0" => {
            let _: AssumptionSetV0 = parse_artifact(value)?;
        }
        "SourceSpan.v0" => {
            let _: SourceSpanV0 = parse_artifact(value)?;
        }
        "ClaimArtifact.v0" => {
            let _: ClaimArtifactV0 = parse_artifact(value)?;
        }
        "RuntimeReceipt.v0" => {
            let _: RuntimeReceiptV0 = parse_artifact(value)?;
        }
        "TraceCertificate.v0" => {
            let _: TraceCertificateV0 = parse_artifact(value)?;
        }
        "EvidenceBundle.v0" => {
            let _: EvidenceBundleV0 = parse_artifact(value)?;
        }
        "ScienceClaimBundle.v0" => {
            let _: ScienceClaimBundleV0 = parse_artifact(value)?;
        }
        "VerificationResult.v0" => {
            let _: VerificationResultV0 = parse_artifact(value)?;
        }
        other => {
            return Err(ValidationError {
                message: format!("unknown artifact type: {other}"),
            });
        }
    }
    validate_semantics(value, artifact_type)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;

    use serde_json::Value;
    use walkdir::WalkDir;

    use super::{deserialize_typed, detect_artifact_type};

    fn examples_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../..")
            .join("examples")
    }

    fn load(name: &str) -> Value {
        let text = fs::read_to_string(examples_dir().join(name)).unwrap();
        serde_json::from_str(&text).unwrap()
    }

    #[test]
    fn valid_examples_deserialize() {
        for entry in WalkDir::new(examples_dir())
            .min_depth(1)
            .max_depth(1)
        {
            let entry = entry.unwrap();
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("json") {
                continue;
            }
            let name = path.file_name().unwrap().to_string_lossy();
            if !name.ends_with(".valid.json") {
                continue;
            }
            let value: Value = serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
            let artifact_type = detect_artifact_type(&value).unwrap();
            deserialize_typed(&value, artifact_type).unwrap();
        }
    }

    #[test]
    fn mismatched_trace_hash_fails() {
        let value = load("invalid_mismatched_trace_hash.json");
        let artifact_type = detect_artifact_type(&value).unwrap();
        assert!(deserialize_typed(&value, artifact_type).is_err());
    }

    #[test]
    fn canonical_hash_stable() {
        let value = load("science_claim_bundle.valid.json");
        let h1 = crate::hash::canonical_hash(&value);
        let h2 = crate::hash::canonical_hash(&value);
        assert_eq!(h1, h2);
    }
}
