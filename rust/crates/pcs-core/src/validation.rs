use serde_json::Value;

use crate::schema::{compile_schema, validate_schema};
use crate::status::{ARTIFACT_STATUSES, CERTIFIED_CLAIM_STATUSES, TRACE_CERTIFICATE_STATUSES};

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

const ARTIFACT_SCHEMAS: &[(&str, &str)] = &[
    ("AssumptionSet.v0", "AssumptionSet.v0.schema.json"),
    ("SourceSpan.v0", "SourceSpan.v0.schema.json"),
    ("ClaimArtifact.v0", "ClaimArtifact.v0.schema.json"),
    ("RuntimeReceipt.v0", "RuntimeReceipt.v0.schema.json"),
    ("TraceCertificate.v0", "TraceCertificate.v0.schema.json"),
    ("EvidenceBundle.v0", "EvidenceBundle.v0.schema.json"),
    ("ScienceClaimBundle.v0", "ScienceClaimBundle.v0.schema.json"),
    ("VerificationResult.v0", "VerificationResult.v0.schema.json"),
    (
        "SignedScienceClaimBundle.v0",
        "SignedScienceClaimBundle.v0.schema.json",
    ),
];

pub fn detect_artifact_type(value: &Value) -> Option<&'static str> {
    let obj = value.as_object()?;
    if obj.contains_key("signed_bundle_id") && obj.contains_key("science_claim_bundle") {
        return Some("SignedScienceClaimBundle.v0");
    }
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
    if obj.contains_key("claim_refs") && obj.contains_key("bundle_id") {
        return Some("EvidenceBundle.v0");
    }
    None
}

fn is_zero_commit(commit: &str) -> bool {
    !commit.is_empty() && commit.chars().all(|c| c == '0')
}

fn check_source_commits(value: &Value, path: &str, errors: &mut Vec<String>, local_dev: bool) {
    match value {
        Value::Object(map) => {
            let child_local =
                local_dev || map.get("local_dev").and_then(|v| v.as_bool()) == Some(true);
            if let Some(commit) = map.get("source_commit").and_then(|v| v.as_str()) {
                if is_zero_commit(commit) && !child_local {
                    errors.push(format!(
                        "{path}: zero source_commit not allowed without local_dev=true"
                    ));
                }
            }
            for (key, child) in map {
                let child_path = if path.is_empty() {
                    key.clone()
                } else {
                    format!("{path}.{key}")
                };
                check_source_commits(child, &child_path, errors, child_local);
            }
        }
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                check_source_commits(item, &format!("{path}[{index}]"), errors, local_dev);
            }
        }
        _ => {}
    }
}

fn validate_science_claim_bundle(obj: &serde_json::Map<String, Value>, errors: &mut Vec<String>) {
    let assumption_set = obj.get("assumption_set").and_then(|v| v.as_object());
    if assumption_set.is_none() {
        errors.push("ScienceClaimBundle.v0 requires assumption_set".into());
    } else if assumption_set
        .and_then(|a| a.get("assumptions"))
        .and_then(|v| v.as_array())
        .map(|a| a.is_empty())
        .unwrap_or(true)
    {
        errors.push("ScienceClaimBundle.v0 requires non-empty assumption_set.assumptions".into());
    }

    let receipts = obj.get("runtime_receipts").and_then(|v| v.as_array());
    if receipts.map(|r| r.is_empty()).unwrap_or(true) {
        errors.push("ScienceClaimBundle.v0 requires non-empty runtime_receipts".into());
    }

    let claim = obj.get("claim_artifact").and_then(|v| v.as_object());
    let claim_status = claim
        .and_then(|c| c.get("status"))
        .and_then(|s| s.as_str())
        .unwrap_or("");
    let certificates = obj
        .get("certificates")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    if CERTIFIED_CLAIM_STATUSES.iter().any(|s| *s == claim_status) && certificates.is_empty() {
        errors.push("certified ScienceClaimBundle requires at least one TraceCertificate".into());
    }

    if let Some(receipts) = receipts {
        for receipt in receipts {
            let Some(r_obj) = receipt.as_object() else {
                continue;
            };
            let r_hash = r_obj.get("trace_hash").and_then(|v| v.as_str());
            for cert in &certificates {
                let Some(c_obj) = cert.as_object() else {
                    continue;
                };
                let c_status = c_obj.get("status").and_then(|v| v.as_str()).unwrap_or("");
                if !c_status.is_empty()
                    && !TRACE_CERTIFICATE_STATUSES.iter().any(|s| *s == c_status)
                {
                    errors.push(format!(
                        "TraceCertificate {:?}: invalid status {c_status}",
                        c_obj.get("certificate_id")
                    ));
                }
                let c_hash = c_obj.get("trace_hash").and_then(|v| v.as_str());
                if let (Some(rh), Some(ch)) = (r_hash, c_hash) {
                    if rh != ch {
                        errors.push(format!(
                            "trace_hash mismatch: receipt {:?} vs certificate {:?}",
                            r_obj.get("receipt_id"),
                            c_obj.get("certificate_id")
                        ));
                    }
                }
            }
        }
    }
}

pub fn validate_semantics(value: &Value, artifact_type: &str) -> Result<(), ValidationError> {
    let mut errors = Vec::new();
    check_source_commits(value, "", &mut errors, false);

    if let Some(obj) = value.as_object() {
        if artifact_type == "RuntimeReceipt.v0" {
            if let Some(status) = obj.get("status").and_then(|v| v.as_str()) {
                if !ARTIFACT_STATUSES.iter().any(|s| *s == status) {
                    errors.push(format!("unknown status {status}"));
                }
            }
        }
        if artifact_type == "ScienceClaimBundle.v0" {
            validate_science_claim_bundle(obj, &mut errors);
        }
        if artifact_type == "SignedScienceClaimBundle.v0" {
            if let Some(scb) = obj.get("science_claim_bundle").and_then(|v| v.as_object()) {
                validate_science_claim_bundle(scb, &mut errors);
            }
        }
        if artifact_type == "TraceCertificate.v0" {
            if let Some(status) = obj.get("status").and_then(|v| v.as_str()) {
                if !status.is_empty() && !TRACE_CERTIFICATE_STATUSES.iter().any(|s| *s == status) {
                    errors.push(format!("TraceCertificate.v0 invalid status {status}"));
                }
            }
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(ValidationError {
            message: errors.join("; "),
        })
    }
}

pub fn validate_artifact(value: &Value, artifact_type: &str) -> Result<(), ValidationError> {
    let schema_name = ARTIFACT_SCHEMAS
        .iter()
        .find(|(name, _)| *name == artifact_type)
        .map(|(_, file)| *file)
        .ok_or_else(|| ValidationError {
            message: format!("unknown artifact type {artifact_type}"),
        })?;
    let compiled = compile_schema(schema_name)?;
    validate_schema(&compiled, value, artifact_type)?;
    validate_semantics(value, artifact_type)
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;

    use serde_json::Value;
    use walkdir::WalkDir;

    use crate::hash::{canonical_hash, canonical_json_string};

    use super::{detect_artifact_type, validate_artifact};

    fn examples_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../..")
            .join("examples")
    }

    fn hash_vectors_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../python/tests/hash_vectors")
    }

    #[test]
    fn valid_examples_pass_jsonschema_and_semantics() {
        for entry in WalkDir::new(examples_dir()).into_iter().filter_map(Result::ok) {
            let path = entry.path();
            if !entry.file_type().is_file() {
                continue;
            }
            let name = path.file_name().unwrap().to_string_lossy();
            if !name.contains(".valid.") {
                continue;
            }
            let value: Value = serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
            let artifact_type = detect_artifact_type(&value).unwrap();
            validate_artifact(&value, artifact_type).unwrap();
        }
    }

    #[test]
    fn hash_vectors_match_python_fixture() {
        for name in [
            "RuntimeReceipt.v0",
            "TraceCertificate.v0",
            "ScienceClaimBundle.v0",
            "SignedScienceClaimBundle.v0",
        ] {
            let dir = hash_vectors_dir().join(name);
            let data: Value =
                serde_json::from_str(&fs::read_to_string(dir.join("input.json")).unwrap()).unwrap();
            let expected = fs::read_to_string(dir.join("canonical.txt"))
                .unwrap()
                .trim()
                .to_string();
            let expected_digest = fs::read_to_string(dir.join("digest.txt"))
                .unwrap()
                .trim()
                .to_string();
            assert_eq!(canonical_json_string(&data), expected, "{name} canonical");
            assert_eq!(canonical_hash(&data), expected_digest, "{name} digest");
        }
    }
}
