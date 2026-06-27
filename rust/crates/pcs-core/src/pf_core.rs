use serde_json::{Map, Value};

use crate::hash::canonical_hash;

pub const GENESIS_HASH: &str = "sha256:0000000000000000000000000000000000000000000000000000000000000000";

const LEAN_CLAIM_CLASSES: &[&str] = &["LeanKernelChecked"];

fn object_mut(value: &Value) -> Option<&Map<String, Value>> {
    value.as_object()
}

fn strip_digest_fields(obj: &mut Map<String, Value>, keys: &[&str]) {
    for key in keys {
        obj.remove(*key);
    }
    obj.remove("signature_or_digest");
}

pub fn compute_event_hash(event: &Value) -> String {
    let mut obj = object_mut(event).expect("event must be object").clone();
    strip_digest_fields(&mut obj, &["event_hash"]);
    canonical_hash(&Value::Object(obj))
}

pub fn compute_trace_hash(trace: &Value) -> String {
    let mut obj = object_mut(trace).expect("trace must be object").clone();
    strip_digest_fields(&mut obj, &["trace_hash"]);
    canonical_hash(&Value::Object(obj))
}

fn normalize_hash(value: &str) -> Result<String, String> {
    let trimmed = value.trim();
    if !trimmed.starts_with("sha256:") || trimmed.len() != 71 {
        return Err(format!("invalid hash {value:?}"));
    }
    Ok(trimmed.to_string())
}

pub fn validate_pfcore_trace_hash_chain(trace: &Value) -> Vec<String> {
    let mut errors = Vec::new();
    let events = match trace.get("events") {
        Some(Value::Array(items)) => items,
        _ => return vec!["TraceInvalid: events must be an array".into()],
    };

    let mut previous = match normalize_hash(GENESIS_HASH) {
        Ok(value) => value,
        Err(message) => return vec![message],
    };

    for (index, event) in events.iter().enumerate() {
        let base = format!("events[{index}]");
        let Some(event_obj) = object_mut(event) else {
            errors.push(format!("EventInvalid: {base} must be an object"));
            continue;
        };
        let prev_field = match event_obj
            .get("previous_event_hash")
            .and_then(|v| v.as_str())
            .map(normalize_hash)
        {
            Some(Ok(value)) => value,
            _ => {
                errors.push(format!("EventHashMismatch: invalid previous_event_hash at {base}"));
                continue;
            }
        };
        if prev_field != previous {
            errors.push(format!(
                "EventHashMismatch: previous_event_hash mismatch at {base} (expected {previous}, got {prev_field})"
            ));
        }
        let actual_hash = match event_obj
            .get("event_hash")
            .and_then(|v| v.as_str())
            .map(normalize_hash)
        {
            Some(Ok(value)) => value,
            _ => {
                errors.push(format!("EventHashMismatch: invalid event_hash at {base}"));
                continue;
            }
        };
        let expected_hash = compute_event_hash(event);
        if actual_hash != expected_hash {
            errors.push(format!(
                "EventHashMismatch: event_hash mismatch at {base} (expected {expected_hash}, got {actual_hash})"
            ));
        }
        previous = actual_hash;
    }

    if let Some(trace_hash) = trace.get("trace_hash") {
        if let Some(raw) = trace_hash.as_str() {
            match normalize_hash(raw) {
                Ok(actual_trace_hash) => {
                    let expected_trace_hash = compute_trace_hash(trace);
                    if actual_trace_hash != expected_trace_hash {
                        errors.push(format!(
                            "TraceHashMismatch: trace_hash mismatch (expected {expected_trace_hash}, got {actual_trace_hash})"
                        ));
                    }
                }
                Err(_) => errors.push("TraceHashMismatch: invalid trace_hash".into()),
            }
        } else {
            errors.push("TraceHashMismatch: missing trace_hash".into());
        }
    }

    if let Some(claim_class) = trace.get("claim_class").and_then(|v| v.as_str()) {
        if let Err(message) = validate_claim_class_overclaim(
            claim_class,
            trace.get("proof_ref").or(trace.get("proof_term_ref")),
            trace.get("lean_proof_checked"),
        ) {
            errors.push(message);
        }
    }

    errors
}

pub fn validate_claim_class_overclaim(
    claim_class: &str,
    proof_ref: Option<&Value>,
    lean_proof_checked: Option<&Value>,
) -> Result<(), String> {
    let has_proof = proof_ref
        .and_then(|v| v.as_str())
        .is_some_and(|s| !s.is_empty());
    if LEAN_CLAIM_CLASSES.contains(&claim_class) && !has_proof {
        return Err(format!(
            "ClaimClassOverclaim: claim_class {claim_class:?} exceeds available assurance"
        ));
    }
    if claim_class == "CertificateChecked" {
        return Err(
            "ClaimClassOverclaim: claim_class \"CertificateChecked\" exceeds available assurance"
                .into(),
        );
    }
    if claim_class == "LeanKernelChecked" && lean_proof_checked != Some(&Value::Bool(true)) {
        return Err(
            "ClaimClassOverclaim: claim_class LeanKernelChecked requires lean_proof_checked=true"
                .into(),
        );
    }
    Ok(())
}

pub fn validate_pfcore_certificate_semantics(certificate: &Value) -> Vec<String> {
    let mut errors = Vec::new();
    let claim_class = certificate
        .get("claim_class")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if let Err(message) = validate_claim_class_overclaim(
        claim_class,
        certificate
            .get("proof_ref")
            .or(certificate.get("proof_term_ref")),
        certificate.get("lean_proof_checked"),
    ) {
        errors.push(message);
    }
    if claim_class == "LeanKernelChecked" {
        if certificate.get("lean_proof_checked") != Some(&Value::Bool(true)) {
            errors.push(
                "root: claim_class LeanKernelChecked requires lean_proof_checked=true".into(),
            );
        }
        if certificate
            .get("proof_term_ref")
            .and_then(|v| v.as_str())
            .map(|s| s.is_empty())
            .unwrap_or(true)
        {
            errors.push(
                "root: claim_class LeanKernelChecked requires proof_term_ref (ClaimClassOverclaim)"
                    .into(),
            );
        }
        if certificate
            .get("lean_environment_hash")
            .and_then(|v| v.as_str())
            .is_none_or(|s| !s.starts_with("sha256:"))
        {
            errors.push("root: claim_class LeanKernelChecked requires lean_environment_hash".into());
        }
        let build_ok = certificate
            .get("lean_build_status")
            .and_then(|v| v.get("ok"))
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if !build_ok {
            errors.push("root: lean_proof_checked requires lean_build_status.ok=true".into());
        }
    }
    errors
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;

    fn repo_root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("..")
    }

    #[test]
    fn pf_core_trace_hash_chain_valid_fixture() {
        let path = repo_root().join("examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json");
        let text = fs::read_to_string(path).expect("fixture");
        let trace: Value = serde_json::from_str(&text).expect("json");
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors.is_empty(), "{errors:?}");
    }

    #[test]
    fn pf_core_trace_hash_recompute_matches_fixture() {
        let path = repo_root().join("examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json");
        let text = fs::read_to_string(path).expect("fixture");
        let trace: Value = serde_json::from_str(&text).expect("json");
        let expected = trace
            .get("trace_hash")
            .and_then(|v| v.as_str())
            .expect("trace_hash");
        assert_eq!(compute_trace_hash(&trace), expected);
    }
}
