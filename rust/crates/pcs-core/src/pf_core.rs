use serde_json::{Map, Value};

use crate::hash::canonical_hash;

pub const GENESIS_HASH: &str = "sha256:0000000000000000000000000000000000000000000000000000000000000000";

const TRACE_CLAIM_CLASSES: &[&str] = &[
    "SchemaValidated",
    "RuntimeChecked",
    "ReplayValidated",
    "AssumptionDeclared",
    "OutOfScope",
];

const CERTIFICATE_CLAIM_CLASSES: &[&str] = &[
    "SchemaValidated",
    "RuntimeChecked",
    "CertificateChecked",
    "LeanKernelChecked",
    "ReplayValidated",
    "AssumptionDeclared",
    "OutOfScope",
];

const LEAN_CLAIM_CLASSES: &[&str] = &["LeanKernelChecked"];

const CONCRETE_PROOF_OBLIGATIONS: &[&str] = &[
    "concrete_trace_safe",
    "concrete_trace_safe_prop",
    "concrete_allowed_events_allowed",
];

const AUTHORIZATION_TO_DECISION: &[(&str, &str)] = &[
    ("authorized", "allow"),
    ("rejected", "deny"),
    ("unknown", "deny"),
    ("policy_missing", "deny"),
];

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

pub fn validate_claim_class_overclaim(
    claim_class: &str,
    proof_ref: Option<&Value>,
    lean_proof_checked: Option<&Value>,
) -> Result<(), String> {
    validate_certificate_claim_class_overclaim(claim_class, proof_ref, lean_proof_checked)
}

pub fn validate_trace_claim_class_overclaim(claim_class: &str) -> Result<(), String> {
    if !TRACE_CLAIM_CLASSES.contains(&claim_class) {
        if claim_class == "LeanKernelChecked" || claim_class == "CertificateChecked" {
            return Err(format!(
                "ClaimClassOverclaim: claim_class {claim_class:?} is not valid on PFCoreTrace.v0"
            ));
        }
        return Err(format!(
            "ClaimClassOverclaim: invalid claim_class {claim_class:?} for trace"
        ));
    }
    Ok(())
}

pub fn validate_certificate_claim_class_overclaim(
    claim_class: &str,
    proof_ref: Option<&Value>,
    lean_proof_checked: Option<&Value>,
) -> Result<(), String> {
    if !CERTIFICATE_CLAIM_CLASSES.contains(&claim_class) {
        return Err(format!(
            "ClaimClassOverclaim: invalid claim_class {claim_class:?} for certificate"
        ));
    }
    let has_proof = proof_ref
        .and_then(|v| v.as_str())
        .is_some_and(|s| !s.is_empty());
    if LEAN_CLAIM_CLASSES.contains(&claim_class) && !has_proof {
        return Err(format!(
            "ClaimClassOverclaim: claim_class {claim_class:?} exceeds available assurance"
        ));
    }
    if claim_class == "LeanKernelChecked" && lean_proof_checked != Some(&Value::Bool(true)) {
        return Err(
            "ClaimClassOverclaim: claim_class LeanKernelChecked requires lean_proof_checked=true"
                .into(),
        );
    }
    Ok(())
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
        if let Err(message) = validate_trace_claim_class_overclaim(claim_class) {
            errors.push(message);
        }
    }

    errors
}

pub fn validate_pfcore_certificate_semantics(certificate: &Value) -> Vec<String> {
    let mut errors = Vec::new();
    let claim_class = certificate
        .get("claim_class")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if let Err(message) = validate_certificate_claim_class_overclaim(
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
            .get("proof_term_hash")
            .and_then(|v| v.as_str())
            .is_none_or(|s| !s.starts_with("sha256:"))
        {
            errors.push("root: claim_class LeanKernelChecked requires proof_term_hash".into());
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
        if certificate.get("lean_proof_checked") == Some(&Value::Bool(true)) {
            if let Some(obligations) = certificate.get("obligations").and_then(|v| v.as_array()) {
                let passed: std::collections::HashSet<String> = obligations
                    .iter()
                    .filter(|item| {
                        item.get("passed").and_then(|v| v.as_bool()) == Some(true)
                    })
                    .filter_map(|item| {
                        item.get("theorem")
                            .and_then(|v| v.as_str())
                            .map(str::to_string)
                    })
                    .collect();
                for theorem in CONCRETE_PROOF_OBLIGATIONS {
                    if !passed.contains(*theorem) {
                        errors.push(format!(
                            "root: lean_proof_checked obligations missing passed proofs for {theorem:?}"
                        ));
                    }
                }
            } else {
                for theorem in CONCRETE_PROOF_OBLIGATIONS {
                    errors.push(format!(
                        "root: lean_proof_checked obligations missing passed proofs for {theorem:?}"
                    ));
                }
            }
        }
    }
    errors
}

fn default_field_layer(section: &str, field: &str) -> &'static str {
    match (section, field) {
        ("pre", "require_capability") => "lean",
        ("pre", "require_effect") => "lean",
        ("pre", "require_tenant_match") => "lean",
        ("pre", "require_role") => "runtime",
        ("pre", "require_policy_ref") => "runtime",
        ("pre", "require_evidence_ref") => "runtime",
        ("post", "require_decision") => "lean",
        ("post", "require_event_safe") => "lean",
        ("invariant", "require_trace_safe") => "lean",
        _ => "runtime",
    }
}

fn field_layer(contract: &Value, section: &str, field: &str) -> String {
    let _ = section;
    contract
        .get("semantics_layer")
        .and_then(|v| v.get(field))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .unwrap_or_else(|| default_field_layer(section, field).to_string())
}

fn principal_has_capability(principal: &Value, capability_id: &str) -> bool {
    let Some(caps) = principal.get("capabilities").and_then(|v| v.as_array()) else {
        return false;
    };
    caps.iter()
        .filter_map(|v| v.as_str())
        .any(|cap| cap == capability_id)
}

fn action_has_effect(action: &Value, effect_kind: &str) -> bool {
    let Some(effects) = action.get("effects").and_then(|v| v.as_array()) else {
        return false;
    };
    effects.iter().any(|effect| {
        effect
            .get("effect_kind")
            .and_then(|v| v.as_str())
            .is_some_and(|kind| kind == effect_kind)
    })
}

fn tenant_matches(principal: &Value, action: &Value) -> bool {
    let tenant = principal
        .get("tenant")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    for key in ["reads", "writes"] {
        let Some(resources) = action.get(key).and_then(|v| v.as_array()) else {
            continue;
        };
        for resource in resources {
            if resource
                .get("tenant")
                .and_then(|v| v.as_str())
                .is_some_and(|value| value != tenant)
            {
                return false;
            }
        }
    }
    true
}

pub fn validate_event_against_contract(event: &Value, contract: &Value, path: &str) -> Vec<String> {
    let mut errors = Vec::new();
    let Some(principal) = event.get("principal") else {
        return vec![format!("ContractEventInvalid: event missing principal or action at {path}")];
    };
    let Some(action) = event.get("action") else {
        return vec![format!("ContractEventInvalid: event missing principal or action at {path}")];
    };
    let contract_id = contract
        .get("contract_id")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    if let Some(pre) = contract.get("pre").and_then(|v| v.as_object()) {
        if pre.get("require_tenant_match").and_then(|v| v.as_bool()) == Some(true)
            && field_layer(contract, "pre", "require_tenant_match") != "out_of_scope"
            && !tenant_matches(principal, action)
        {
            errors.push(format!(
                "ContractTenantMismatch: contract {contract_id:?} requires tenant match at {path}"
            ));
        }
        if let Some(required_cap) = pre.get("require_capability").and_then(|v| v.as_str()) {
            if !required_cap.is_empty()
                && field_layer(contract, "pre", "require_capability") != "out_of_scope"
                && !principal_has_capability(principal, required_cap)
            {
                errors.push(format!(
                    "ContractCapabilityRequired: contract {contract_id:?} requires capability {required_cap:?} at {path}.principal"
                ));
            }
        }
        if let Some(required_effect) = pre.get("require_effect").and_then(|v| v.as_str()) {
            if !required_effect.is_empty()
                && field_layer(contract, "pre", "require_effect") != "out_of_scope"
                && !action_has_effect(action, required_effect)
            {
                errors.push(format!(
                    "ContractEffectRequired: contract {contract_id:?} requires effect {required_effect:?} at {path}.action.effects"
                ));
            }
        }
        if let Some(required_role) = pre.get("require_role").and_then(|v| v.as_str()) {
            if !required_role.is_empty()
                && field_layer(contract, "pre", "require_role") != "out_of_scope"
            {
                let roles = principal.get("roles").and_then(|v| v.as_array());
                let has_role = roles.is_some_and(|items| {
                    items
                        .iter()
                        .filter_map(|v| v.as_str())
                        .any(|role| role == required_role)
                });
                if !has_role {
                    errors.push(format!(
                        "ContractRoleRequired: contract {contract_id:?} requires role {required_role:?} at {path}.principal.roles"
                    ));
                }
            }
        }
        if let Some(required_policy) = pre.get("require_policy_ref").and_then(|v| v.as_str()) {
            if !required_policy.is_empty()
                && field_layer(contract, "pre", "require_policy_ref") != "out_of_scope"
            {
                let refs = event.get("contract_refs").and_then(|v| v.as_array());
                let has_ref = refs.is_some_and(|items| {
                    items
                        .iter()
                        .filter_map(|v| v.as_str())
                        .any(|value| value == required_policy)
                });
                if !has_ref {
                    errors.push(format!(
                        "ContractPolicyRefRequired: contract {contract_id:?} requires policy ref {required_policy:?} at {path}.contract_refs"
                    ));
                }
            }
        }
        if let Some(required_evidence) = pre.get("require_evidence_ref").and_then(|v| v.as_str()) {
            if !required_evidence.is_empty()
                && field_layer(contract, "pre", "require_evidence_ref") != "out_of_scope"
            {
                let evidence = event.get("evidence_refs").and_then(|v| v.as_array());
                let has_ref = evidence.is_some_and(|items| {
                    items
                        .iter()
                        .filter_map(|v| v.as_str())
                        .any(|value| value == required_evidence)
                });
                if !has_ref {
                    errors.push(format!(
                        "ContractEvidenceRefRequired: contract {contract_id:?} requires evidence ref {required_evidence:?} at {path}.evidence_refs"
                    ));
                }
            }
        }
    }

    if let Some(post) = contract.get("post").and_then(|v| v.as_object()) {
        if let Some(required_decision) = post.get("require_decision").and_then(|v| v.as_str()) {
            if !required_decision.is_empty()
                && field_layer(contract, "post", "require_decision") != "out_of_scope"
            {
                let decision = event.get("decision").and_then(|v| v.as_str()).unwrap_or("");
                if decision != required_decision {
                    errors.push(format!(
                        "ContractDecisionMismatch: contract {contract_id:?} requires decision {required_decision:?}, got {decision:?} at {path}.decision"
                    ));
                }
            }
        }
        if post.get("require_event_safe").and_then(|v| v.as_bool()) == Some(true)
            && field_layer(contract, "post", "require_event_safe") != "out_of_scope"
        {
            let decision = event.get("decision").and_then(|v| v.as_str()).unwrap_or("");
            if decision == "allow" {
                let cap_id = action
                    .get("capability")
                    .and_then(|v| v.get("capability_id"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                if cap_id.is_empty() || !principal_has_capability(principal, cap_id) {
                    errors.push(format!(
                        "ContractEventUnsafe: allowed event violates contract {contract_id:?} event safety at {path}"
                    ));
                } else if !tenant_matches(principal, action) {
                    errors.push(format!(
                        "ContractEventUnsafe: allowed event violates contract {contract_id:?} tenant safety at {path}"
                    ));
                }
            }
        }
    }

    errors
}

pub fn validate_trace_contracts(
    trace: &Value,
    contracts: &std::collections::HashMap<String, Value>,
) -> Vec<String> {
    let mut errors = Vec::new();
    let Some(events) = trace.get("events").and_then(|v| v.as_array()) else {
        return vec!["TraceInvalid: events must be an array".into()];
    };
    for (index, event) in events.iter().enumerate() {
        let base = format!("events[{index}]");
        let Some(refs) = event.get("contract_refs").and_then(|v| v.as_array()) else {
            continue;
        };
        if refs.is_empty() {
            continue;
        }
        for (ref_index, reference) in refs.iter().enumerate() {
            let Some(contract_id) = reference.as_str() else {
                continue;
            };
            let Some(contract) = contracts.get(contract_id) else {
                errors.push(format!(
                    "ContractRefMissing: unknown contract reference {contract_id:?} at {base}.contract_refs[{ref_index}]"
                ));
                continue;
            };
            errors.extend(validate_event_against_contract(event, contract, &base));
        }
    }
    errors
}

fn authorization_decision(status: &str) -> &'static str {
    AUTHORIZATION_TO_DECISION
        .iter()
        .find_map(|(auth, decision)| (*auth == status).then_some(*decision))
        .unwrap_or("deny")
}

pub fn validate_denied_events_preserved(tool_use_trace: &Value, pfcore_trace: &Value) -> Vec<String> {
    let Some(tool_calls) = tool_use_trace.get("tool_calls").and_then(|v| v.as_array()) else {
        return Vec::new();
    };
    let Some(events) = pfcore_trace.get("events").and_then(|v| v.as_array()) else {
        return vec!["DroppedDeniedEvent: denied event \"<missing-events>\" missing from compiled trace (at events)".into()];
    };
    let compiled_ids: std::collections::HashSet<String> = events
        .iter()
        .filter_map(|event| {
            event
                .get("event_id")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        })
        .collect();
    let mut errors = Vec::new();
    for tool_call in tool_calls {
        let auth = tool_call
            .get("authorization_status")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if authorization_decision(auth) != "deny" {
            continue;
        }
        let event_id = tool_call
            .get("event_id")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if !event_id.is_empty() && !compiled_ids.contains(event_id) {
            errors.push(format!(
                "DroppedDeniedEvent: denied event {event_id:?} missing from compiled trace (at events)"
            ));
        }
    }
    errors
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::fs;
    use std::path::PathBuf;

    fn repo_root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("..")
    }

    fn load_json(path: PathBuf) -> Value {
        let text = fs::read_to_string(path).expect("fixture");
        serde_json::from_str(&text).expect("json")
    }

    #[test]
    fn pf_core_trace_hash_chain_valid_fixture() {
        let path = repo_root().join("examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json");
        let trace = load_json(path);
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors.is_empty(), "{errors:?}");
    }

    #[test]
    fn pf_core_shared_hash_vectors() {
        let root = repo_root();
        for name in ["PFCoreEvent.v0", "PFCoreTrace.v0"] {
            let base = root.join(format!("python/tests/hash_vectors/pf_core/{name}"));
            let input_text = fs::read_to_string(base.join("input.json")).expect("input.json");
            let expected_digest = fs::read_to_string(base.join("digest.txt"))
                .expect("digest.txt")
                .trim()
                .to_string();
            let value: Value = serde_json::from_str(&input_text).expect("json");
            let actual = if name == "PFCoreEvent.v0" {
                compute_event_hash(&value)
            } else {
                compute_trace_hash(&value)
            };
            assert_eq!(actual, expected_digest, "{name} digest mismatch");
        }
    }

    #[test]
    fn pf_core_invalid_hash_chain_vector() {
        let path = repo_root().join("python/tests/hash_vectors/pf_core/invalid/trace_hash_chain_break.json");
        let trace = load_json(path);
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors.iter().any(|err| err.contains("EventHashMismatch")));
    }

    #[test]
    fn pf_core_claim_class_overclaim_vector() {
        let path = repo_root().join("python/tests/hash_vectors/pf_core/invalid/claim_class_overclaim_trace.json");
        let trace = load_json(path);
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors.iter().any(|err| err.contains("ClaimClassOverclaim")));
    }

    #[test]
    fn pf_core_contract_violation_vector() {
        let root = repo_root().join("python/tests/hash_vectors/pf_core/invalid/contract_capability_missing");
        let trace = load_json(root.join("trace.json"));
        let contract = load_json(root.join("contract.json"));
        let contract_id = contract
            .get("contract_id")
            .and_then(|v| v.as_str())
            .expect("contract_id")
            .to_string();
        let mut contracts = HashMap::new();
        contracts.insert(contract_id, contract);
        let errors = validate_trace_contracts(&trace, &contracts);
        assert!(errors.iter().any(|err| err.contains("ContractCapabilityRequired")));
    }

    #[test]
    fn pf_core_denied_event_dropped_vector() {
        let root = repo_root().join("python/tests/hash_vectors/pf_core/invalid/denied_event_dropped");
        let tool_use = load_json(root.join("tool_use_trace.json"));
        let pfcore = load_json(root.join("pfcore_trace.json"));
        let errors = validate_denied_events_preserved(&tool_use, &pfcore);
        assert!(errors.iter().any(|err| err.contains("DroppedDeniedEvent")));
    }
}
