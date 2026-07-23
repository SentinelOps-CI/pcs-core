use serde_json::{Number, Value};
use sha2::{Digest, Sha256};
use std::fmt;

/// v0 compatibility field: integrity digest historically named like a signature.
pub const SIGNATURE_FIELD: &str = "signature_or_digest";
/// v1 separated content digest.
pub const ARTIFACT_DIGEST_FIELD: &str = "artifact_digest";
/// v1 cryptographic signature object.
pub const SIGNATURE_OBJECT_FIELD: &str = "signature";

/// PCS Canonical JSON algorithm version.
pub const CANONICALIZATION_VERSION: &str = "v1";

pub const SAFE_INTEGER_MIN: i64 = -9007199254740991;
pub const SAFE_INTEGER_MAX: i64 = 9007199254740991;

/// Normalized rejection codes shared with Python and TypeScript release hashing.
pub const REJECTION_FLOAT_PROHIBITED: &str = "float_prohibited";
pub const REJECTION_INTEGER_OUT_OF_RANGE: &str = "integer_out_of_range";
pub const REJECTION_NEGATIVE_ZERO: &str = "negative_zero";

/// Error raised when a value cannot be represented under Canonical JSON v1 rules.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CanonicalizationError {
    pub code: String,
    pub message: String,
    pub path: String,
}

impl CanonicalizationError {
    pub fn new(code: impl Into<String>, message: impl Into<String>, path: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
            path: path.into(),
        }
    }
}

impl fmt::Display for CanonicalizationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl std::error::Error for CanonicalizationError {}

fn is_excluded_hash_field(key: &str) -> bool {
    key == SIGNATURE_FIELD || key == ARTIFACT_DIGEST_FIELD || key == SIGNATURE_OBJECT_FIELD
}

fn sort_value(value: Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut keys: Vec<_> = map.keys().cloned().collect();
            keys.sort();
            let mut sorted = serde_json::Map::new();
            for key in keys {
                if let Some(v) = map.get(&key) {
                    sorted.insert(key, sort_value(v.clone()));
                }
            }
            Value::Object(sorted)
        }
        Value::Array(items) => Value::Array(items.into_iter().map(sort_value).collect()),
        other => other,
    }
}

/// Domain-separated signing message: `PCS:<artifact_type>:<schema_version>:<artifact_digest>`.
pub fn domain_separated_signing_message(
    artifact_type: &str,
    schema_version: &str,
    artifact_digest: &str,
) -> Result<String, String> {
    if artifact_type.is_empty() || artifact_type.contains(':') {
        return Err(format!(
            "invalid artifact_type for domain separation: {artifact_type}"
        ));
    }
    if schema_version.is_empty() || schema_version.contains(':') {
        return Err(format!(
            "invalid schema_version for domain separation: {schema_version}"
        ));
    }
    if !artifact_digest.starts_with("sha256:") || artifact_digest.len() != 71 {
        return Err(format!(
            "invalid artifact_digest for domain separation: {artifact_digest}"
        ));
    }
    Ok(format!(
        "PCS:{artifact_type}:{schema_version}:{artifact_digest}"
    ))
}

fn is_negative_zero(num: &Number) -> bool {
    num.as_f64()
        .is_some_and(|f| f == 0.0 && f.is_sign_negative())
}

fn assert_number_policy_number(num: &Number, path: &str) -> Result<(), CanonicalizationError> {
    if is_negative_zero(num) {
        return Err(CanonicalizationError::new(
            REJECTION_NEGATIVE_ZERO,
            format!("{path}: negative zero is prohibited under Canonical JSON v1"),
            path,
        ));
    }
    if let Some(i) = num.as_i64() {
        if i < SAFE_INTEGER_MIN || i > SAFE_INTEGER_MAX {
            return Err(CanonicalizationError::new(
                REJECTION_INTEGER_OUT_OF_RANGE,
                format!(
                    "{path}: integer {i} outside safe-integer range [{SAFE_INTEGER_MIN}, {SAFE_INTEGER_MAX}]"
                ),
                path,
            ));
        }
        return Ok(());
    }
    if let Some(u) = num.as_u64() {
        if u > SAFE_INTEGER_MAX as u64 {
            return Err(CanonicalizationError::new(
                REJECTION_INTEGER_OUT_OF_RANGE,
                format!(
                    "{path}: integer {u} outside safe-integer range [{SAFE_INTEGER_MIN}, {SAFE_INTEGER_MAX}]"
                ),
                path,
            ));
        }
        return Ok(());
    }
    // Non-integer / float form (including values that only fit in f64).
    Err(CanonicalizationError::new(
        REJECTION_FLOAT_PROHIBITED,
        format!(
            "{path}: float values are prohibited under Canonical JSON v1; \
             use a normalized decimal string instead"
        ),
        path,
    ))
}

/// Enforce Canonical JSON v1 number policy (strict / release hashing).
pub fn assert_canonical_number_policy(value: &Value, path: &str) -> Result<(), CanonicalizationError> {
    match value {
        Value::Null | Value::Bool(_) | Value::String(_) => Ok(()),
        Value::Number(num) => assert_number_policy_number(num, path),
        Value::Array(items) => {
            for (index, child) in items.iter().enumerate() {
                assert_canonical_number_policy(child, &format!("{path}[{index}]"))?;
            }
            Ok(())
        }
        Value::Object(map) => {
            for (key, child) in map {
                assert_canonical_number_policy(child, &format!("{path}.{key}"))?;
            }
            Ok(())
        }
    }
}

pub fn canonicalize_for_hash(data: &serde_json::Value) -> serde_json::Value {
    canonicalize_for_hash_with_policy(data, false).expect("legacy canonicalization cannot fail")
}

pub fn canonicalize_for_hash_with_policy(
    data: &serde_json::Value,
    enforce_number_policy: bool,
) -> Result<serde_json::Value, CanonicalizationError> {
    let mut obj = data
        .as_object()
        .expect("artifact root must be object")
        .clone();
    obj.retain(|k, _| !is_excluded_hash_field(k));
    let payload = Value::Object(obj);
    if enforce_number_policy {
        assert_canonical_number_policy(&payload, "$")?;
    }
    Ok(sort_value(payload))
}

pub fn canonical_json_string(data: &serde_json::Value) -> String {
    canonical_json_string_with_policy(data, false).expect("legacy canonicalization cannot fail")
}

pub fn canonical_json_string_with_policy(
    data: &serde_json::Value,
    enforce_number_policy: bool,
) -> Result<String, CanonicalizationError> {
    let canonical = canonicalize_for_hash_with_policy(data, enforce_number_policy)?;
    Ok(serde_json::to_string(&canonical).expect("serialize canonical json"))
}

pub fn canonical_json_bytes(data: &serde_json::Value) -> Vec<u8> {
    canonical_json_string(data).into_bytes()
}

pub fn canonical_hash(data: &serde_json::Value) -> String {
    canonical_hash_legacy(data)
}

/// Hash without the strict number policy (Phase 0 / legacy digest compatibility).
pub fn canonical_hash_legacy(data: &serde_json::Value) -> String {
    let digest = Sha256::digest(canonical_json_bytes(data));
    format!("sha256:{:x}", digest)
}

/// Hash with the strict number policy always enforced (release integrity envelopes).
pub fn canonical_hash_release(data: &serde_json::Value) -> Result<String, CanonicalizationError> {
    let bytes = canonical_json_string_with_policy(data, true)?.into_bytes();
    let digest = Sha256::digest(bytes);
    Ok(format!("sha256:{:x}", digest))
}

/// Return `Ok(digest)` or `Err(rejection_code)` for cross-language vectors.
pub fn try_canonical_hash_release(data: &serde_json::Value) -> Result<String, String> {
    canonical_hash_release(data).map_err(|err| err.code)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::fs;
    use std::path::PathBuf;

    fn canon_v1_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../test_vectors/hash/canonical_json_v1")
    }

    #[test]
    fn release_rejects_float_with_normalized_code() {
        let err = canonical_hash_release(&json!({"x": 1.5})).unwrap_err();
        assert_eq!(err.code, REJECTION_FLOAT_PROHIBITED);
    }

    #[test]
    fn release_rejects_out_of_range_integer() {
        let err = canonical_hash_release(&json!({"x": SAFE_INTEGER_MAX + 1})).unwrap_err();
        assert_eq!(err.code, REJECTION_INTEGER_OUT_OF_RANGE);
        let err = canonical_hash_release(&json!({"x": SAFE_INTEGER_MIN - 1})).unwrap_err();
        assert_eq!(err.code, REJECTION_INTEGER_OUT_OF_RANGE);
    }

    #[test]
    fn release_rejects_negative_zero() {
        let value = serde_json::from_str::<Value>(r#"{"x":-0.0}"#).unwrap();
        let err = canonical_hash_release(&value).unwrap_err();
        assert_eq!(err.code, REJECTION_NEGATIVE_ZERO);
    }

    #[test]
    fn release_accepts_safe_integer_boundaries() {
        let value = json!({
            "artifact_type": "CanonicalProbe.v0",
            "hi": SAFE_INTEGER_MAX,
            "lo": SAFE_INTEGER_MIN,
            "schema_version": "v0",
        });
        let digest = canonical_hash_release(&value).unwrap();
        assert_eq!(digest, canonical_hash_legacy(&value));
        assert!(digest.starts_with("sha256:"));
    }

    #[test]
    fn legacy_still_hashes_floats() {
        let digest = canonical_hash_legacy(&json!({"x": 1.5}));
        assert!(digest.starts_with("sha256:"));
    }

    #[test]
    fn canonical_json_v1_accept_vectors() {
        let root = canon_v1_dir();
        let catalog: Value =
            serde_json::from_str(&fs::read_to_string(root.join("vectors.json")).unwrap()).unwrap();
        assert_eq!(
            catalog["canonicalization_version"].as_str().unwrap(),
            CANONICALIZATION_VERSION
        );
        for case in catalog["cases"].as_array().unwrap() {
            let case_id = case["case_id"].as_str().unwrap();
            let data: Value = serde_json::from_str(
                &fs::read_to_string(root.join(case_id).join("input.json")).unwrap(),
            )
            .unwrap();
            let expected_digest = case["expected_digest"].as_str().unwrap();
            let expected_canonical = case["canonical_json"].as_str().unwrap();
            assert_eq!(
                canonical_json_string(&data),
                expected_canonical,
                "{case_id} canonical"
            );
            assert_eq!(
                canonical_hash_legacy(&data),
                expected_digest,
                "{case_id} legacy"
            );
            assert_eq!(
                canonical_hash_release(&data).unwrap(),
                expected_digest,
                "{case_id} release"
            );
        }
    }

    #[test]
    fn canonical_json_v1_release_reject_vectors() {
        let root = canon_v1_dir();
        let catalog: Value =
            serde_json::from_str(&fs::read_to_string(root.join("vectors.json")).unwrap()).unwrap();
        for case in catalog["release_reject_cases"].as_array().unwrap() {
            let case_id = case["case_id"].as_str().unwrap();
            let data: Value = serde_json::from_str(
                &fs::read_to_string(root.join(case_id).join("input.json")).unwrap(),
            )
            .unwrap();
            let expected = case["expected_rejection"].as_str().unwrap();
            let legacy_digest = case["legacy_digest"].as_str().unwrap();
            assert_eq!(
                try_canonical_hash_release(&data).unwrap_err(),
                expected,
                "{case_id} rejection"
            );
            assert_eq!(
                canonical_hash_legacy(&data),
                legacy_digest,
                "{case_id} legacy digest"
            );
        }
    }
}
