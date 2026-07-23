use serde_json::Value;
use sha2::{Digest, Sha256};

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

pub fn canonicalize_for_hash(data: &serde_json::Value) -> serde_json::Value {
    let mut obj = data
        .as_object()
        .expect("artifact root must be object")
        .clone();
    obj.retain(|k, _| !is_excluded_hash_field(k));
    sort_value(Value::Object(obj))
}

pub fn canonical_json_string(data: &serde_json::Value) -> String {
    let canonical = canonicalize_for_hash(data);
    serde_json::to_string(&canonical).expect("serialize canonical json")
}

pub fn canonical_json_bytes(data: &serde_json::Value) -> Vec<u8> {
    canonical_json_string(data).into_bytes()
}

pub fn canonical_hash(data: &serde_json::Value) -> String {
    let digest = Sha256::digest(canonical_json_bytes(data));
    format!("sha256:{:x}", digest)
}
