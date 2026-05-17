use serde_json::Value;
use sha2::{Digest, Sha256};

const SIGNATURE_FIELD: &str = "signature_or_digest";

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

pub fn canonicalize_for_hash(data: &serde_json::Value) -> serde_json::Value {
    let mut obj = data
        .as_object()
        .expect("artifact root must be object")
        .clone();
    obj.remove(SIGNATURE_FIELD);
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
