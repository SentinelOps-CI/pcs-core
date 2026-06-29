use std::collections::HashSet;

use serde_json::{Map, Value};

use crate::hash::canonical_hash;
use crate::pf_core_catalog::{
    CAPABILITY_CATALOG, EFFECT_KINDS, TOOL_NAME_MAP, WORKFLOW_CERTIFICATE_MODES,
};

pub const GENESIS_HASH: &str =
    "sha256:0000000000000000000000000000000000000000000000000000000000000000";

fn known_effect_kinds() -> HashSet<&'static str> {
    EFFECT_KINDS.iter().copied().collect()
}

fn lookup_capability(
    capability_id: &str,
) -> Option<&'static (&'static str, &'static str, &'static str)> {
    CAPABILITY_CATALOG
        .iter()
        .find(|(id, _, _)| *id == capability_id)
}

fn runtime_error(code: &str, message: &str, path: &str) -> String {
    format!("{code}: {message} (at {path})")
}

fn glob_match(pattern: &str, text: &str) -> bool {
    let pattern_chars: Vec<char> = pattern.chars().collect();
    let text_chars: Vec<char> = text.chars().collect();
    fn rec(pattern: &[char], pi: usize, text: &[char], ti: usize) -> bool {
        if pi == pattern.len() {
            return ti == text.len();
        }
        if pattern[pi] == '*' {
            if pi + 1 == pattern.len() {
                return true;
            }
            for j in ti..=text.len() {
                if rec(pattern, pi + 1, text, j) {
                    return true;
                }
            }
            return false;
        }
        if ti >= text.len() || pattern[pi] != text[ti] {
            return false;
        }
        rec(pattern, pi + 1, text, ti + 1)
    }
    rec(&pattern_chars, 0, &text_chars, 0)
}

pub fn resource_matches_pattern(uri: &str, pattern: &str) -> bool {
    if pattern == "*" {
        return true;
    }
    glob_match(pattern, uri)
}

fn validate_action_effects_known(action: &Value, path: &str) -> Option<String> {
    let effects = action.get("effects")?;
    let Some(items) = effects.as_array() else {
        return Some(runtime_error(
            "UnknownEffect",
            "unknown effect: <missing>",
            &format!("{path}.effects"),
        ));
    };
    if items.is_empty() {
        return Some(runtime_error(
            "UnknownEffect",
            "unknown effect: <missing>",
            path,
        ));
    };
    let known = known_effect_kinds();
    for (index, effect) in items.iter().enumerate() {
        let Some(effect_obj) = object_mut(effect) else {
            return Some(runtime_error(
                "UnknownEffect",
                "unknown effect: <invalid>",
                &format!("{path}.effects[{index}]"),
            ));
        };
        let kind = effect_obj
            .get("effect_kind")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if kind.is_empty() || !known.contains(kind) {
            return Some(runtime_error(
                "UnknownEffect",
                &format!(
                    "unknown effect: {}",
                    if kind.is_empty() { "<missing>" } else { kind }
                ),
                &format!("{path}.effects[{index}].effect_kind"),
            ));
        }
    }
    None
}

fn validate_action_capabilities_known(action: &Value, path: &str) -> Option<String> {
    let capability = action.get("capability")?;
    let Some(cap_obj) = object_mut(capability) else {
        return Some(runtime_error(
            "UnknownCapability",
            "unknown capability: <missing>",
            &format!("{path}.capability"),
        ));
    };
    let cap_id = cap_obj
        .get("capability_id")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if cap_id.is_empty() || lookup_capability(cap_id).is_none() {
        return Some(runtime_error(
            "UnknownCapability",
            &format!(
                "unknown capability: {}",
                if cap_id.is_empty() {
                    "<missing>"
                } else {
                    cap_id
                }
            ),
            &format!("{path}.capability"),
        ));
    }
    let effect_kind = cap_obj
        .get("effect_kind")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let known = known_effect_kinds();
    if effect_kind.is_empty() || !known.contains(effect_kind) {
        return Some(runtime_error(
            "UnknownEffect",
            &format!(
                "unknown effect: {}",
                if effect_kind.is_empty() {
                    "<missing>"
                } else {
                    effect_kind
                }
            ),
            &format!("{path}.capability.effect_kind"),
        ));
    }
    None
}

fn validate_action_capability_effects(action: &Value, path: &str) -> Option<String> {
    let capability = action.get("capability")?;
    let Some(cap_obj) = object_mut(capability) else {
        return Some(runtime_error(
            "UnknownCapability",
            "unknown capability: <missing>",
            &format!("{path}.capability"),
        ));
    };
    let cap_id = cap_obj
        .get("capability_id")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let Some(catalog) = lookup_capability(cap_id) else {
        return Some(runtime_error(
            "UnknownCapability",
            &format!(
                "unknown capability: {}",
                if cap_id.is_empty() {
                    "<missing>"
                } else {
                    cap_id
                }
            ),
            &format!("{path}.capability"),
        ));
    };
    if validate_action_effects_known(action, path).is_some() {
        return validate_action_effects_known(action, path);
    }
    let (cap_id, cap_effect, _) = catalog;
    if !action_has_effect(action, cap_effect) {
        return Some(runtime_error(
            "CapabilityEffectMismatch",
            &format!(
                "capability {:?} effect_kind {:?} not listed in action effects",
                cap_id, cap_effect
            ),
            &format!("{path}.effects"),
        ));
    }
    None
}

fn validate_resource_scope(action: &Value, path: &str) -> Option<String> {
    let capability = action.get("capability")?;
    let cap_obj = object_mut(capability)?;
    let pattern = cap_obj
        .get("resource_pattern")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if pattern.is_empty() {
        return None;
    }
    for key in ["reads", "writes"] {
        let Some(resources) = action.get(key).and_then(|v| v.as_array()) else {
            continue;
        };
        for (index, resource) in resources.iter().enumerate() {
            let Some(resource_obj) = object_mut(resource) else {
                continue;
            };
            let uri = resource_obj
                .get("uri")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if !uri.is_empty() && !resource_matches_pattern(uri, pattern) {
                return Some(runtime_error(
                    "ResourceScopeViolation",
                    &format!("resource {uri:?} outside declared pattern {pattern:?}"),
                    &format!("{path}.{key}[{index}].uri"),
                ));
            }
        }
    }
    None
}

pub fn validate_direct_trace_action_semantics(trace: &Value) -> Vec<String> {
    let mut errors = Vec::new();
    let Some(events) = trace.get("events").and_then(|v| v.as_array()) else {
        return errors;
    };
    for (index, event) in events.iter().enumerate() {
        let Some(action) = event.get("action") else {
            continue;
        };
        let base = format!("events[{index}].action");
        if let Some(error) = validate_action_effects_known(action, &base) {
            errors.push(error);
        }
        if let Some(error) = validate_action_capabilities_known(action, &base) {
            errors.push(error);
        }
        if let Some(error) = validate_action_capability_effects(action, &base) {
            errors.push(error);
        }
    }
    errors
}

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

const DEFAULT_TRACE_SAFE_CONTRACT_ID: &str = "trace-safe";
const RUNTIME_RESOURCE_PATTERN_SCOPE: &str = "resource_pattern_scope";
const LEAN_RESOURCE_WITHIN_CAPABILITY_PATTERN: &str = "resource_within_capability_pattern";

const DEFAULT_CERTIFICATE_MODE: &str = "TraceSafeCertificate";
const TOOL_USE_DEFAULT_CERTIFICATE_MODE: &str = "TraceSafeRCertificate";

const CERTIFICATE_MODES: &[&str] = &[
    "TraceSafeCertificate",
    "TraceSafeRCertificate",
    "FramePreservedCertificate",
    "EffectFrameCertificate",
    "HandoffSafeCertificate",
    "CompositionalExtensionCertificate",
    "ContractCheckedCertificate",
];

fn mode_obligation_theorems(mode: &str) -> &'static [&'static str] {
    match mode {
        "TraceSafeCertificate" => CONCRETE_PROOF_OBLIGATIONS,
        "TraceSafeRCertificate" => &[
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_trace_safe_r",
            "concrete_trace_safe_r_prop",
            "concrete_trace_safe_r_implies_trace_safe",
        ],
        "FramePreservedCertificate" => &[
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "frame_valid_initial",
            "frame_preserved_steps",
        ],
        "EffectFrameCertificate" => &[
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_action_effects_in_frame",
        ],
        "HandoffSafeCertificate" => &[
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_handoff_safe",
        ],
        "CompositionalExtensionCertificate" => &[
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_compositional_extension",
        ],
        "ContractCheckedCertificate" => &[
            "concrete_trace_safe",
            "concrete_trace_safe_prop",
            "concrete_allowed_events_allowed",
            "concrete_contract_checked",
        ],
        _ => &[],
    }
}

fn certificate_mode_is_valid(mode: &str) -> bool {
    CERTIFICATE_MODES.contains(&mode)
}

pub fn resolve_tool_mapping(
    tool_name: &str,
    tool_category: &str,
) -> Result<(&'static str, &'static str, &'static str), String> {
    for (name, category, cap_id, effect_kind, pattern) in TOOL_NAME_MAP {
        if *name == tool_name && *category == tool_category {
            return Ok((cap_id, effect_kind, pattern));
        }
    }
    Err(format!(
        "UnknownCapability: {tool_name}/{tool_category} (at tool_calls.tool_name)"
    ))
}

fn workflow_certificate_mode(workflow_id: &str) -> Option<&'static str> {
    for (id, mode) in WORKFLOW_CERTIFICATE_MODES {
        if *id == workflow_id {
            return Some(mode);
        }
    }
    None
}

pub fn resolve_certificate_mode_default(
    certificate: &Value,
    trace: Option<&Value>,
    trace_path: Option<&str>,
    release_grade: bool,
) -> String {
    if let Some(mode) = certificate
        .get("certificate_mode")
        .and_then(|v| v.as_str())
        .filter(|mode| certificate_mode_is_valid(mode))
    {
        return mode.to_string();
    }
    if let Some(trace) = trace {
        if let Some(required) = trace
            .get("required_certificate_mode")
            .and_then(|v| v.as_str())
            .filter(|mode| certificate_mode_is_valid(mode))
        {
            return required.to_string();
        }
        if let Some(workflow_id) = trace.get("workflow_id").and_then(|v| v.as_str()) {
            if let Some(mode) = workflow_certificate_mode(workflow_id) {
                return mode.to_string();
            }
        }
    }
    if !release_grade {
        if let Some(path) = trace_path {
            let trace_dir = std::path::Path::new(path).parent();
            if trace_dir
                .map(|dir| dir.join("tool_use_trace.json").is_file())
                .unwrap_or(false)
            {
                return TOOL_USE_DEFAULT_CERTIFICATE_MODE.to_string();
            }
        }
    }
    DEFAULT_CERTIFICATE_MODE.to_string()
}

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
                errors.push(format!(
                    "EventHashMismatch: invalid previous_event_hash at {base}"
                ));
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

    for (index, event) in events.iter().enumerate() {
        let Some(action) = event.get("action") else {
            continue;
        };
        let path = format!("events[{index}].action");
        if let Some(error) = validate_resource_scope(action, &path) {
            errors.push(error);
        }
    }

    errors
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ContractSemanticsChecked {
    pub lean: Vec<String>,
    pub runtime: Vec<String>,
}

fn contract_semantics_string_list(value: Option<&Value>) -> Option<Vec<String>> {
    match value {
        None => Some(Vec::new()),
        Some(Value::Array(items)) => {
            let mut out = Vec::with_capacity(items.len());
            for item in items {
                out.push(item.as_str()?.to_string());
            }
            Some(out)
        }
        Some(_) => None,
    }
}

/// Parse `contract_semantics_checked` metadata when present and well-formed.
pub fn parse_contract_semantics_checked(certificate: &Value) -> Option<ContractSemanticsChecked> {
    let semantics = certificate.get("contract_semantics_checked")?;
    let obj = semantics.as_object()?;
    let lean = contract_semantics_string_list(obj.get("lean"))?;
    let runtime = contract_semantics_string_list(obj.get("runtime"))?;
    Some(ContractSemanticsChecked { lean, runtime })
}

/// Validate certificate contract-semantics metadata (does not imply LeanKernelChecked).
pub fn validate_contract_semantics_checked(certificate: &Value) -> Vec<String> {
    let mut errors = Vec::new();
    let claim_class = certificate
        .get("claim_class")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let lean_proof_checked = certificate.get("lean_proof_checked") == Some(&Value::Bool(true));

    if let Some(semantics) = certificate.get("contract_semantics_checked") {
        let Some(obj) = semantics.as_object() else {
            errors.push("root: contract_semantics_checked must be an object".into());
            return errors;
        };
        for key in ["lean", "runtime"] {
            if let Some(value) = obj.get(key) {
                let valid = value
                    .as_array()
                    .is_some_and(|items| items.iter().all(|item| item.as_str().is_some()));
                if !valid {
                    errors.push(format!(
                        "root: contract_semantics_checked.{key} must be a string array"
                    ));
                }
            }
        }
    }

    if claim_class == "LeanKernelChecked" {
        let default_ref = certificate
            .get("default_contract_ref")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let has_semantics = parse_contract_semantics_checked(certificate)
            .is_some_and(|semantics| !semantics.lean.is_empty() || !semantics.runtime.is_empty());
        if default_ref != DEFAULT_TRACE_SAFE_CONTRACT_ID && !has_semantics {
            errors.push(format!(
                "root: claim_class LeanKernelChecked requires contract_refs or \
                 default_contract_ref {DEFAULT_TRACE_SAFE_CONTRACT_ID:?}"
            ));
        }
    }

    if lean_proof_checked {
        match parse_contract_semantics_checked(certificate) {
            Some(semantics) => {
                if !semantics
                    .runtime
                    .iter()
                    .any(|item| item == RUNTIME_RESOURCE_PATTERN_SCOPE)
                {
                    errors.push(format!(
                        "root: lean_proof_checked contract_semantics_checked.runtime missing \
                         {RUNTIME_RESOURCE_PATTERN_SCOPE:?}"
                    ));
                }
                if !semantics
                    .lean
                    .iter()
                    .any(|item| item == LEAN_RESOURCE_WITHIN_CAPABILITY_PATTERN)
                {
                    errors.push(format!(
                        "root: lean_proof_checked contract_semantics_checked.lean missing \
                         {LEAN_RESOURCE_WITHIN_CAPABILITY_PATTERN:?}"
                    ));
                }
            }
            None => {
                if certificate.get("contract_semantics_checked").is_some() {
                    errors.push("root: contract_semantics_checked has invalid shape".into());
                } else {
                    errors.push(
                        "root: lean_proof_checked requires contract_semantics_checked".into(),
                    );
                }
            }
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
            errors
                .push("root: claim_class LeanKernelChecked requires lean_environment_hash".into());
        }
        if certificate
            .get("pfcore_kernel_hash")
            .and_then(|v| v.as_str())
            .is_none_or(|s| !s.starts_with("sha256:"))
        {
            errors.push("root: claim_class LeanKernelChecked requires pfcore_kernel_hash".into());
        }
        let build_ok = certificate
            .get("lean_build_status")
            .and_then(|v| v.get("ok"))
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if !build_ok {
            errors.push("root: lean_proof_checked requires lean_build_status.ok=true".into());
        }
        let cert_mode = certificate
            .get("certificate_mode")
            .and_then(|v| v.as_str())
            .unwrap_or(DEFAULT_CERTIFICATE_MODE);
        if !certificate_mode_is_valid(cert_mode) {
            errors.push(format!("root: invalid certificate_mode {cert_mode:?}"));
        } else if certificate.get("lean_proof_checked") == Some(&Value::Bool(true)) {
            let mut mode_required: std::collections::HashSet<String> =
                mode_obligation_theorems(cert_mode)
                    .iter()
                    .map(|s| (*s).to_string())
                    .collect();
            if let Some(obligations) = certificate.get("obligations").and_then(|v| v.as_array()) {
                for item in obligations {
                    if let Some(theorem) = item.get("theorem").and_then(|v| v.as_str()) {
                        if theorem.starts_with("concrete_action_resource_scope_") {
                            mode_required.insert(theorem.to_string());
                        }
                    }
                }
            }
            let passed: std::collections::HashSet<String> = certificate
                .get("obligations")
                .and_then(|v| v.as_array())
                .map(|obligations| {
                    obligations
                        .iter()
                        .filter(|item| item.get("passed").and_then(|v| v.as_bool()) == Some(true))
                        .filter_map(|item| {
                            item.get("theorem")
                                .and_then(|v| v.as_str())
                                .map(str::to_string)
                        })
                        .collect()
                })
                .unwrap_or_default();
            for theorem in CONCRETE_PROOF_OBLIGATIONS {
                if !passed.contains(*theorem) {
                    errors.push(format!(
                        "root: lean_proof_checked obligations missing passed proofs for {theorem:?}"
                    ));
                }
            }
            if !mode_required.is_empty() {
                let missing_mode: Vec<String> = mode_required
                    .iter()
                    .filter(|theorem| !passed.contains(*theorem))
                    .cloned()
                    .collect();
                if !missing_mode.is_empty() {
                    errors.push(format!(
                        "root: certificate_mode obligations missing passed proofs for {missing_mode:?}"
                    ));
                }
            }
            if cert_mode == "ContractCheckedCertificate"
                && certificate.get("lean_proof_checked") == Some(&Value::Bool(true))
            {
                if let Some(runtime) = certificate
                    .get("contract_semantics_checked")
                    .and_then(|v| v.get("runtime"))
                    .and_then(|v| v.as_array())
                {
                    for item in runtime {
                        if let Some(item_str) = item.as_str() {
                            if item_str.starts_with("missing_contract:") {
                                errors.push(format!(
                                    "root: ContractCheckedCertificate cannot claim lean_proof_checked with unresolved contract ref {item_str:?}"
                                ));
                            }
                        }
                    }
                }
            }
        }
    }
    errors.extend(validate_contract_semantics_checked(certificate));
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

fn action_within_tenant_d(principal: &Value, action: &Value) -> bool {
    let tenant = principal
        .get("tenant")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    for key in ["reads", "writes"] {
        let Some(resources) = action.get(key).and_then(|v| v.as_array()) else {
            return false;
        };
        for resource in resources {
            let Some(resource_obj) = object_mut(resource) else {
                return false;
            };
            if resource_obj
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

fn action_admissible_d(principal: &Value, action: &Value) -> bool {
    let Some(capability) = action.get("capability") else {
        return false;
    };
    let Some(cap_obj) = object_mut(capability) else {
        return false;
    };
    let cap_id = cap_obj
        .get("capability_id")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    const PATH: &str = "action";
    if validate_action_capabilities_known(action, PATH).is_some()
        || validate_action_effects_known(action, PATH).is_some()
        || validate_action_capability_effects(action, PATH).is_some()
        || validate_resource_scope(action, PATH).is_some()
    {
        return false;
    }
    principal_has_capability(principal, cap_id) && action_within_tenant_d(principal, action)
}

/// Mirror Lean ``actionAdmissibleWithResourcePatternD`` (kernel + catalog resource scope).
pub fn action_admissible_with_resource_pattern_d(principal: &Value, action: &Value) -> bool {
    action_admissible_d(principal, action)
}

/// Mirror Lean ``eventSafeD`` on allow events (deny is vacuously safe).
pub fn event_safe_d(event: &Value) -> bool {
    let decision = event.get("decision").and_then(|v| v.as_str()).unwrap_or("");
    if decision == "deny" {
        return true;
    }
    if decision != "allow" {
        return false;
    }
    let Some(principal) = event.get("principal") else {
        return false;
    };
    let Some(action) = event.get("action") else {
        return false;
    };
    action_admissible_d(principal, action)
}

/// Mirror Lean ``eventSafeRD`` (allow branch uses resource-pattern admissibility).
pub fn event_safe_rd(event: &Value) -> bool {
    let decision = event.get("decision").and_then(|v| v.as_str()).unwrap_or("");
    if decision == "deny" {
        return true;
    }
    if decision != "allow" {
        return false;
    }
    let Some(principal) = event.get("principal") else {
        return false;
    };
    let Some(action) = event.get("action") else {
        return false;
    };
    action_admissible_with_resource_pattern_d(principal, action)
}

/// Mirror Lean ``traceSafeD`` decider.
pub fn trace_safe_d(events: &[Value]) -> bool {
    events.iter().all(event_safe_d)
}

/// Mirror Lean ``traceSafeRD`` (resource-pattern trace safety decider).
pub fn trace_safe_rd(events: &[Value]) -> bool {
    events.iter().all(event_safe_rd)
}

pub fn validate_event_against_contract(event: &Value, contract: &Value, path: &str) -> Vec<String> {
    let mut errors = Vec::new();
    let Some(principal) = event.get("principal") else {
        return vec![format!(
            "ContractEventInvalid: event missing principal or action at {path}"
        )];
    };
    let Some(action) = event.get("action") else {
        return vec![format!(
            "ContractEventInvalid: event missing principal or action at {path}"
        )];
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

fn event_cross_tenant_safe(principal: &Value, action: &Value, decision: &str) -> bool {
    if decision == "deny" {
        return true;
    }
    tenant_matches(principal, action)
}

pub fn validate_cross_tenant_safety(trace: &Value) -> Vec<String> {
    let mut errors = Vec::new();
    let events = match trace.get("events").and_then(|v| v.as_array()) {
        Some(items) => items,
        None => return vec!["TraceInvalid: events must be an array".into()],
    };
    for (index, event) in events.iter().enumerate() {
        let base = format!("events[{index}]");
        let Some(principal) = event.get("principal") else {
            errors.push(format!(
                "CrossTenantSafe: {base} missing principal or action"
            ));
            continue;
        };
        let Some(action) = event.get("action") else {
            errors.push(format!(
                "CrossTenantSafe: {base} missing principal or action"
            ));
            continue;
        };
        let decision = event.get("decision").and_then(|v| v.as_str()).unwrap_or("");
        if !event_cross_tenant_safe(principal, action, decision) {
            let tenant = principal
                .get("tenant")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            errors.push(format!(
                "CrossTenantSafe: cross-tenant allow at {base} (principal tenant {tenant:?})"
            ));
        }
    }
    errors
}

pub fn validate_tenant_isolation(trace: &Value) -> Vec<String> {
    let mut errors = Vec::new();
    let events = match trace.get("events").and_then(|v| v.as_array()) {
        Some(items) => items,
        None => return vec!["TraceInvalid: events must be an array".into()],
    };
    for (index, event) in events.iter().enumerate() {
        let base = format!("events[{index}]");
        let Some(principal) = event.get("principal") else {
            errors.push(format!(
                "TenantIsolation: {base} missing principal or action"
            ));
            continue;
        };
        let Some(action) = event.get("action") else {
            errors.push(format!(
                "TenantIsolation: {base} missing principal or action"
            ));
            continue;
        };
        let tenant = principal
            .get("tenant")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if tenant.is_empty() {
            errors.push(format!("TenantIsolation: {base}.principal.tenant is empty"));
            continue;
        }
        if !tenant_matches(principal, action) {
            errors.push(format!(
                "TenantIsolation: cross-tenant resource access at {base} (principal tenant {tenant:?})"
            ));
        }
    }
    errors
}

fn low_event_for_tenant(tenant: &str, event: &Value) -> bool {
    let decision = event.get("decision").and_then(|v| v.as_str()).unwrap_or("");
    if decision != "allow" {
        return false;
    }
    let Some(principal) = event.get("principal") else {
        return false;
    };
    principal
        .get("tenant")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        == tenant
}

fn trace_projection_for_tenant<'a>(trace: &'a Value, tenant: &str) -> Vec<&'a Value> {
    let mut projection = Vec::new();
    let Some(events) = trace.get("events").and_then(|v| v.as_array()) else {
        return projection;
    };
    for event in events {
        if low_event_for_tenant(tenant, event) {
            projection.push(event);
        }
    }
    projection
}

pub fn validate_observational_non_interference(
    trace: &Value,
    tenant_low: &str,
    tenant_high: &str,
) -> Vec<String> {
    if tenant_low == tenant_high {
        return Vec::new();
    }
    let mut errors = Vec::new();
    let events = match trace.get("events").and_then(|v| v.as_array()) {
        Some(items) => items,
        None => return vec!["TraceInvalid: events must be an array".into()],
    };
    let projection = trace_projection_for_tenant(trace, tenant_low);
    for (index, event) in projection.iter().enumerate() {
        if !low_event_for_tenant(tenant_low, event) {
            errors.push(format!(
                "NonInterference: projected event at projection[{index}] is not LowEvent for tenant {tenant_low:?}"
            ));
        }
    }
    for (index, event) in events.iter().enumerate() {
        let Some(principal) = event.get("principal") else {
            continue;
        };
        if principal
            .get("tenant")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            != tenant_high
        {
            continue;
        }
        if low_event_for_tenant(tenant_low, event) {
            errors.push(format!(
                "NonInterference: high-tenant event at events[{index}] is low-visible to tenant {tenant_low:?}"
            ));
        }
    }
    errors
}

pub fn validate_observational_non_interference_all_pairs(trace: &Value) -> Vec<String> {
    let mut tenants: Vec<String> = Vec::new();
    if let Some(events) = trace.get("events").and_then(|v| v.as_array()) {
        for event in events {
            if let Some(principal) = event.get("principal") {
                let tenant = principal
                    .get("tenant")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                if !tenant.is_empty() && !tenants.iter().any(|t| t == tenant) {
                    tenants.push(tenant.to_string());
                }
            }
        }
    }
    let mut errors = Vec::new();
    for tenant_low in &tenants {
        for tenant_high in &tenants {
            if tenant_low == tenant_high {
                continue;
            }
            errors.extend(validate_observational_non_interference(
                trace,
                tenant_low,
                tenant_high,
            ));
        }
    }
    errors
}

pub fn validate_denied_events_preserved(
    tool_use_trace: &Value,
    pfcore_trace: &Value,
) -> Vec<String> {
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
        let path =
            repo_root().join("examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json");
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
        let path = repo_root()
            .join("python/tests/hash_vectors/pf_core/invalid/trace_hash_chain_break.json");
        let trace = load_json(path);
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors.iter().any(|err| err.contains("EventHashMismatch")));
    }

    #[test]
    fn pf_core_claim_class_overclaim_vector() {
        let path = repo_root()
            .join("python/tests/hash_vectors/pf_core/invalid/claim_class_overclaim_trace.json");
        let trace = load_json(path);
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors.iter().any(|err| err.contains("ClaimClassOverclaim")));
    }

    #[test]
    fn pf_core_contract_violation_vector() {
        let root = repo_root()
            .join("python/tests/hash_vectors/pf_core/invalid/contract_capability_missing");
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
        assert!(errors
            .iter()
            .any(|err| err.contains("ContractCapabilityRequired")));
    }

    #[test]
    fn pf_core_denied_event_dropped_vector() {
        let root =
            repo_root().join("python/tests/hash_vectors/pf_core/invalid/denied_event_dropped");
        let tool_use = load_json(root.join("tool_use_trace.json"));
        let pfcore = load_json(root.join("pfcore_trace.json"));
        let errors = validate_denied_events_preserved(&tool_use, &pfcore);
        assert!(errors.iter().any(|err| err.contains("DroppedDeniedEvent")));
    }

    #[test]
    fn pf_core_trace_hash_mismatch_vector() {
        let path =
            repo_root().join("python/tests/hash_vectors/pf_core/invalid/trace_hash_mismatch.json");
        let trace = load_json(path);
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors.iter().any(|err| err.contains("TraceHashMismatch")));
    }

    #[test]
    fn pf_core_cross_tenant_leak_vector() {
        let path =
            repo_root().join("python/tests/hash_vectors/pf_core/invalid/cross_tenant_leak.json");
        let trace = load_json(path);
        let tenant_errors = validate_tenant_isolation(&trace);
        assert!(tenant_errors
            .iter()
            .any(|err| err.contains("TenantIsolation")));
        let cross_tenant_errors = validate_cross_tenant_safety(&trace);
        assert!(cross_tenant_errors
            .iter()
            .any(|err| err.contains("CrossTenantSafe")));
    }

    #[test]
    fn pf_core_cross_tenant_safety_ok_on_allowed_fixture() {
        let path = repo_root().join("examples/pf-core-valid/file_read_allowed/trace.json");
        let trace = load_json(path);
        assert!(validate_cross_tenant_safety(&trace).is_empty());
        assert!(validate_tenant_isolation(&trace).is_empty());
        assert!(
            validate_observational_non_interference(&trace, "tenant-a", "other-tenant").is_empty()
        );
        assert!(validate_observational_non_interference_all_pairs(&trace).is_empty());
    }

    #[test]
    fn pf_core_previous_event_hash_mismatch_vector() {
        let path = repo_root()
            .join("python/tests/hash_vectors/pf_core/invalid/previous_event_hash_mismatch.json");
        let trace = load_json(path);
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors.iter().any(|err| err.contains("EventHashMismatch")));
    }

    #[test]
    fn pf_core_direct_trace_semantics_invalid_vectors() {
        let cases: &[(&str, &str)] = &[
            (
                "examples/pf-core-invalid/unknown_direct_trace_effect/trace.json",
                "UnknownEffect",
            ),
            (
                "examples/pf-core-invalid/capability_effect_mismatch/trace.json",
                "CapabilityEffectMismatch",
            ),
            (
                "examples/pf-core-invalid/unknown_direct_trace_capability/trace.json",
                "UnknownCapability",
            ),
        ];
        for (relative, needle) in cases {
            let trace = load_json(repo_root().join(relative));
            let errors = validate_direct_trace_action_semantics(&trace);
            assert!(
                errors.iter().any(|err| err.contains(needle)),
                "{relative}: expected {needle} in {errors:?}"
            );
        }
    }

    #[test]
    fn pf_core_trace_safe_r_decider_parity() {
        let trace = load_json(
            repo_root().join("examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json"),
        );
        let events = trace
            .get("events")
            .and_then(|v| v.as_array())
            .expect("events array");
        assert!(trace_safe_d(events));
        assert!(trace_safe_rd(events));
        let bad = load_json(
            repo_root().join("examples/pf-core-invalid/resource_scope_violation/trace.json"),
        );
        let bad_events = bad
            .get("events")
            .and_then(|v| v.as_array())
            .expect("events array");
        assert!(!trace_safe_rd(bad_events));
    }

    #[test]
    fn pf_core_resource_scope_violation_vector() {
        let path = repo_root().join("examples/pf-core-invalid/resource_scope_violation/trace.json");
        let trace = load_json(path);
        let errors = validate_pfcore_trace_hash_chain(&trace);
        assert!(errors
            .iter()
            .any(|err| err.contains("ResourceScopeViolation")));
    }

    #[test]
    fn pf_core_resource_pattern_catalog_parity() {
        let samples: &[(&str, &[(&str, bool)])] = &[
            ("*", &[("/any/uri", true), ("mailto:x@y", true)]),
            (
                "/data/*",
                &[("/data/report.txt", true), ("/etc/passwd", false)],
            ),
            ("mailto:*", &[("mailto:a@b.c", true), ("http://x", false)]),
            ("agent:*", &[("agent:worker-1", true), ("mcp:tool", false)]),
            (
                "mcp:*",
                &[("mcp:filesystem.read", true), ("agent:x", false)],
            ),
            ("lab:*", &[("lab:run-1", true), ("/data/x", false)]),
        ];
        for (_, _, pattern) in CAPABILITY_CATALOG {
            let pattern = *pattern;
            let Some((_, cases)) = samples.iter().find(|(pat, _)| *pat == pattern) else {
                panic!("missing parity samples for pattern {pattern:?}");
            };
            for (uri, expected) in *cases {
                assert_eq!(
                    resource_matches_pattern(uri, pattern),
                    *expected,
                    "pattern={pattern:?} uri={uri:?}"
                );
            }
        }
    }

    #[test]
    fn pf_core_contract_semantics_checked_resource_obligations() {
        use serde_json::json;

        let missing = json!({
            "claim_class": "LeanKernelChecked",
            "lean_proof_checked": true,
            "default_contract_ref": "trace-safe",
            "contract_semantics_checked": {
                "lean": [],
                "runtime": ["resource_pattern_scope"]
            }
        });
        let errors = validate_contract_semantics_checked(&missing);
        assert!(errors
            .iter()
            .any(|err| err.contains("resource_within_capability_pattern")));

        let ok = json!({
            "claim_class": "LeanKernelChecked",
            "lean_proof_checked": true,
            "default_contract_ref": "trace-safe",
            "contract_semantics_checked": {
                "lean": ["resource_within_capability_pattern"],
                "runtime": ["resource_pattern_scope"]
            }
        });
        assert!(validate_contract_semantics_checked(&ok).is_empty());
    }

    #[test]
    fn pf_core_audit_invalid_vectors() {
        let cases: &[(&str, &str, &str)] = &[
            (
                "examples/pf-core-invalid/lean_kernel_checked_on_trace/trace.json",
                "PFCoreTrace.v0",
                "ClaimClassOverclaim",
            ),
            (
                "examples/pf-core-invalid/lean_kernel_checked_without_proof_ref/trace.json",
                "PFCoreTrace.v0",
                "ClaimClassOverclaim",
            ),
            (
                "examples/pf-core-invalid/lean_kernel_checked_without_proof_term_hash/certificate.json",
                "PFCoreCertificate.v0",
                "proof_term_hash",
            ),
            (
                "examples/pf-core-invalid/lean_kernel_checked_without_proof_term_ref/certificate.json",
                "PFCoreCertificate.v0",
                "proof_term_ref",
            ),
            (
                "examples/pf-core-invalid/lean_kernel_checked_with_skipped_build/certificate.json",
                "PFCoreCertificate.v0",
                "lean_build_status",
            ),
            (
                "examples/pf-core-invalid/certificate_mode_effectframecertificate_missing_obligations/certificate.json",
                "PFCoreCertificate.v0",
                "certificate_mode obligations",
            ),
        ];
        for (relative, artifact_type, needle) in cases {
            let path = repo_root().join(relative);
            let value = load_json(path);
            let errors = if *artifact_type == "PFCoreTrace.v0" {
                validate_pfcore_trace_hash_chain(&value)
            } else {
                validate_pfcore_certificate_semantics(&value)
            };
            assert!(
                errors.iter().any(|err| err.contains(needle)),
                "{relative}: expected {needle} in {errors:?}"
            );
        }
    }

    #[test]
    fn pf_core_tool_name_map_matches_catalog_fixture() {
        let (cap_id, effect_kind, pattern) =
            resolve_tool_mapping("filesystem.read", "filesystem").expect("mapping");
        assert_eq!(cap_id, "cap:file-read");
        assert_eq!(effect_kind, "file.read");
        assert_eq!(pattern, "/data/*");
        assert!(resolve_tool_mapping("unknown.tool", "misc").is_err());
    }

    #[test]
    fn pf_core_tool_use_certificate_mode_default() {
        let trace_path =
            repo_root().join("examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json");
        let trace = load_json(trace_path.clone());
        let certificate = serde_json::json!({});
        let mode = resolve_certificate_mode_default(
            &certificate,
            Some(&trace),
            Some(trace_path.to_str().expect("utf8")),
            false,
        );
        assert_eq!(mode, TOOL_USE_DEFAULT_CERTIFICATE_MODE);
    }

    #[test]
    fn pf_core_workflow_catalog_mode_without_sibling_file() {
        let trace = serde_json::json!({
            "workflow_id": "agent_tool_use.safety_v0",
        });
        let mode =
            resolve_certificate_mode_default(&serde_json::json!({}), Some(&trace), None, false);
        assert_eq!(mode, TOOL_USE_DEFAULT_CERTIFICATE_MODE);
    }

    #[test]
    fn pf_core_release_grade_skips_sibling_heuristic() {
        let trace_path =
            repo_root().join("examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json");
        let trace = load_json(trace_path.clone());
        let sibling_mode = resolve_certificate_mode_default(
            &serde_json::json!({}),
            Some(&trace),
            Some(trace_path.to_str().expect("utf8")),
            false,
        );
        assert_eq!(sibling_mode, TOOL_USE_DEFAULT_CERTIFICATE_MODE);
        let stripped = serde_json::json!({
            "trace_id": "trace-no-workflow",
        });
        let non_release = resolve_certificate_mode_default(
            &serde_json::json!({}),
            Some(&stripped),
            Some(trace_path.to_str().expect("utf8")),
            false,
        );
        assert_eq!(non_release, TOOL_USE_DEFAULT_CERTIFICATE_MODE);
        let release_mode = resolve_certificate_mode_default(
            &serde_json::json!({}),
            Some(&stripped),
            Some(trace_path.to_str().expect("utf8")),
            true,
        );
        assert_eq!(release_mode, DEFAULT_CERTIFICATE_MODE);
    }
}
