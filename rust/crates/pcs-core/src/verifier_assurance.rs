//! Verifier Assurance (VA) *.v1 semantic validation and report verify.
//! Error codes and message shapes mirror `python/pcs_core/verifier_assurance_validate.py`.

use serde_json::{json, Map, Value};

use crate::hash::{canonical_hash, SIGNATURE_FIELD};

const FAIL_CLOSED: &[&str] = &[
    "timeout",
    "unavailable",
    "malformed_input",
    "unsupported_scope",
    "error",
    "cancelled",
    "resource_exhausted",
];

const SECRET_KEY_HINTS: &[&str] = &[
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "private_key",
    "access_key",
];

fn guarantee_rank(class: &str) -> Option<i32> {
    match class {
        "unchecked_advisory" => Some(0),
        "observational" | "runtime_observed" => Some(1),
        "empirically_measured" => Some(2),
        "human_reviewed" => Some(3),
        "certificate_checked" => Some(4),
        "formally_checked" => Some(5),
        _ => None,
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SemanticIssue {
    pub code: String,
    pub path: String,
    pub message: String,
}

impl SemanticIssue {
    pub fn new(code: impl Into<String>, path: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            path: path.into(),
            message: message.into(),
        }
    }

    pub fn format(&self) -> String {
        format!("{} at {}: {}", self.code, self.path, self.message)
    }
}

fn issue_strings(issues: &[SemanticIssue]) -> Vec<String> {
    issues.iter().map(SemanticIssue::format).collect()
}

fn forbid_legacy_signature(data: &Map<String, Value>, artifact_type: &str) -> Vec<SemanticIssue> {
    if data.contains_key(SIGNATURE_FIELD) {
        vec![SemanticIssue::new(
            "LegacySignatureOrDigest",
            SIGNATURE_FIELD,
            format!("{artifact_type}: {SIGNATURE_FIELD} is forbidden on VA *.v1 roots"),
        )]
    } else {
        Vec::new()
    }
}

fn require_integrity(data: &Map<String, Value>, artifact_type: &str) -> Vec<SemanticIssue> {
    let Some(integrity) = data.get("integrity").and_then(|v| v.as_object()) else {
        return vec![SemanticIssue::new(
            "MissingIntegrity",
            "integrity",
            format!("{artifact_type}: nested integrity envelope is required"),
        )];
    };
    let mut issues = Vec::new();
    if integrity.get("canonicalization_version").and_then(|v| v.as_str()) != Some("v1") {
        issues.push(SemanticIssue::new(
            "BadCanonicalizationVersion",
            "integrity.canonicalization_version",
            "must be v1",
        ));
    }
    let digest = integrity.get("artifact_digest").and_then(|v| v.as_str());
    if digest.map(|d| !d.starts_with("sha256:")).unwrap_or(true) {
        issues.push(SemanticIssue::new(
            "BadArtifactDigest",
            "integrity.artifact_digest",
            "must be sha256:<64 hex>",
        ));
    }
    issues
}

fn check_zero_commit(commit: Option<&str>, path: &str) -> Vec<SemanticIssue> {
    if let Some(c) = commit {
        if c.len() == 40 && c.chars().all(|ch| ch == '0') {
            return vec![SemanticIssue::new(
                "PlaceholderCommit",
                path,
                "placeholder zero git commit rejected",
            )];
        }
    }
    Vec::new()
}

fn is_full_hex_commit(commit: &str) -> bool {
    commit.len() == 40 && commit.chars().all(|c| matches!(c, '0'..='9' | 'a'..='f'))
}

fn check_secret_leaks(env_entries: Option<&Value>, path: &str) -> Vec<SemanticIssue> {
    let Some(obj) = env_entries.and_then(|v| v.as_object()) else {
        return Vec::new();
    };
    let mut issues = Vec::new();
    for (key, value) in obj {
        let key_l = key.to_lowercase();
        if SECRET_KEY_HINTS.iter().any(|hint| key_l.contains(hint)) {
            issues.push(SemanticIssue::new(
                "SecretKeyName",
                format!("{path}.{key}"),
                format!("redacted_environment key {key:?} looks like a secret name"),
            ));
        }
        if let Some(v) = value.as_str() {
            let value_l = v.to_lowercase();
            if v.starts_with("sk-") || value_l.contains("begin private key") {
                issues.push(SemanticIssue::new(
                    "SecretValue",
                    format!("{path}.{key}"),
                    "value appears to contain a secret",
                ));
            }
        }
    }
    issues
}

/// Parse a decimal string into (mantissa, scale) where value = mantissa / 10^scale.
fn parse_decimal(value: &Value, path: &str) -> Result<(i128, u32), SemanticIssue> {
    let Some(s) = value.as_str() else {
        return Err(SemanticIssue::new(
            "DecimalType",
            path,
            "decimal values must be strings",
        ));
    };
    parse_decimal_str(s).ok_or_else(|| {
        SemanticIssue::new("DecimalParse", path, format!("invalid decimal string {s:?}"))
    })
}

fn parse_decimal_str(s: &str) -> Option<(i128, u32)> {
    let s = s.trim();
    if s.is_empty() {
        return None;
    }
    let negative = s.starts_with('-');
    let body = if negative || s.starts_with('+') {
        &s[1..]
    } else {
        s
    };
    if body.is_empty() || !body.chars().all(|c| c.is_ascii_digit() || c == '.') {
        return None;
    }
    if body.matches('.').count() > 1 {
        return None;
    }
    let (int_part, frac_part) = match body.split_once('.') {
        Some((i, f)) => (i, f),
        None => (body, ""),
    };
    if int_part.is_empty() && frac_part.is_empty() {
        return None;
    }
    let int_digits = if int_part.is_empty() { "0" } else { int_part };
    let combined = format!("{int_digits}{frac_part}");
    let mantissa: i128 = combined.parse().ok()?;
    let scale = frac_part.len() as u32;
    Some((if negative { -mantissa } else { mantissa }, scale))
}

fn rescale(mantissa: i128, from_scale: u32, to_scale: u32) -> Option<i128> {
    if to_scale >= from_scale {
        let factor = 10i128.checked_pow(to_scale - from_scale)?;
        mantissa.checked_mul(factor)
    } else {
        let factor = 10i128.checked_pow(from_scale - to_scale)?;
        Some(mantissa / factor)
    }
}

fn decimals_equal(a: (i128, u32), b: (i128, u32)) -> bool {
    let scale = a.1.max(b.1);
    match (rescale(a.0, a.1, scale), rescale(b.0, b.1, scale)) {
        (Some(x), Some(y)) => x == y,
        _ => false,
    }
}

fn add_decimals(a: (i128, u32), b: (i128, u32)) -> Option<(i128, u32)> {
    let scale = a.1.max(b.1);
    let x = rescale(a.0, a.1, scale)?;
    let y = rescale(b.0, b.1, scale)?;
    Some((x.checked_add(y)?, scale))
}

pub fn validate_verifier_profile_semantics(data: &Value) -> Vec<SemanticIssue> {
    let Some(obj) = data.as_object() else {
        return vec![SemanticIssue::new(
            "RootType",
            "$",
            "VerifierProfile.v1 root must be an object",
        )];
    };
    let mut issues = forbid_legacy_signature(obj, "VerifierProfile.v1");
    issues.extend(require_integrity(obj, "VerifierProfile.v1"));
    let commit = obj.get("source_commit").and_then(|v| v.as_str());
    if commit.map(is_full_hex_commit) != Some(true) {
        issues.push(SemanticIssue::new(
            "InvalidSourceCommit",
            "source_commit",
            "source_commit must be a full 40-char lowercase hex SHA",
        ));
    }
    issues.extend(check_zero_commit(commit, "source_commit"));
    if let Some(configuration) = obj.get("configuration").and_then(|v| v.as_object()) {
        for key in [
            "policy_digest",
            "model_digest",
            "prompt_digest",
            "resource_limit_digest",
        ] {
            if !configuration.contains_key(key) {
                issues.push(SemanticIssue::new(
                    "MissingNullDigestSlot",
                    format!("configuration.{key}"),
                    "inapplicable config digests must be present as explicit null",
                ));
            }
        }
    }
    if let Some(impl_) = obj.get("implementation").and_then(|v| v.as_object()) {
        let digest = impl_.get("implementation_digest");
        let missing = match digest {
            None => true,
            Some(Value::Null) => true,
            Some(Value::String(s)) => s.is_empty(),
            Some(_) => false,
        };
        if missing {
            issues.push(SemanticIssue::new(
                "MissingImplementationDigest",
                "implementation.implementation_digest",
                "implementation_digest is required",
            ));
        }
    }
    if let Some(applicability) = obj.get("applicability").and_then(|v| v.as_object()) {
        let status = applicability.get("status").and_then(|v| v.as_str());
        if status == Some("revoked")
            && applicability
                .get("revocation_reason")
                .and_then(|v| v.as_str())
                .map(|s| s.is_empty())
                .unwrap_or(true)
        {
            issues.push(SemanticIssue::new(
                "MissingRevocationReason",
                "applicability.revocation_reason",
                "revoked profiles require revocation_reason",
            ));
        }
        if status == Some("superseded")
            && applicability
                .get("superseded_by_profile_id")
                .and_then(|v| v.as_str())
                .map(|s| s.is_empty())
                .unwrap_or(true)
        {
            issues.push(SemanticIssue::new(
                "MissingSupersededBy",
                "applicability.superseded_by_profile_id",
                "superseded profiles require superseded_by_profile_id",
            ));
        }
    }
    if let Some(redacted) = obj.get("redacted_environment").and_then(|v| v.as_object()) {
        issues.extend(check_secret_leaks(redacted.get("entries"), "redacted_environment.entries"));
    }
    if let (Some(schema_doc), Some(schema_digest)) = (
        obj.get("configuration_schema").filter(|v| v.is_object()),
        obj.get("configuration_schema_digest").and_then(|v| v.as_str()),
    ) {
        let recomputed = canonical_hash(schema_doc);
        if recomputed != schema_digest {
            issues.push(SemanticIssue::new(
                "ConfigSchemaDigestMismatch",
                "configuration_schema_digest",
                format!("recorded {schema_digest:?} != recomputed {recomputed:?}"),
            ));
        }
    }
    issues
}

pub fn validate_verification_result_semantics(data: &Value) -> Vec<SemanticIssue> {
    let Some(obj) = data.as_object() else {
        return vec![SemanticIssue::new(
            "RootType",
            "$",
            "VerificationResult.v1 root must be an object",
        )];
    };
    let mut issues = forbid_legacy_signature(obj, "VerificationResult.v1");
    issues.extend(require_integrity(obj, "VerificationResult.v1"));
    let commit = obj.get("source_commit").and_then(|v| v.as_str());
    if commit.map(is_full_hex_commit) != Some(true) {
        issues.push(SemanticIssue::new(
            "InvalidSourceCommit",
            "source_commit",
            "source_commit must be a full 40-char lowercase hex SHA",
        ));
    }
    let decision = obj.get("decision").and_then(|v| v.as_str());
    let execution_status = obj.get("execution_status").and_then(|v| v.as_str());
    if let (Some(status), Some(dec)) = (execution_status, decision) {
        if FAIL_CLOSED.contains(&status) && matches!(dec, "accept" | "reject") {
            issues.push(SemanticIssue::new(
                "FailClosedDecision",
                "decision",
                format!("execution_status {status:?} cannot yield accept/reject"),
            ));
        }
    }
    if obj.get("normalization_applied").and_then(|v| v.as_bool()) == Some(true) {
        let raw = obj.get("raw_backend_output_digest").and_then(|v| v.as_str());
        let normalized = obj.get("normalized_result_digest").and_then(|v| v.as_str());
        match (raw, normalized) {
            (Some(r), Some(n)) if r == n => {
                issues.push(SemanticIssue::new(
                    "IdenticalNormalizationDigests",
                    "normalized_result_digest",
                    "raw and normalized digests must be distinct when normalization occurs",
                ));
            }
            (Some(_), Some(_)) => {}
            _ => {
                issues.push(SemanticIssue::new(
                    "MissingNormalizationDigests",
                    "normalized_result_digest",
                    "normalization_applied requires raw and normalized digests",
                ));
            }
        }
    }
    let mut mandatory_failed = false;
    if let Some(groups) = obj.get("check_groups").and_then(|v| v.as_array()) {
        for (g_index, group) in groups.iter().enumerate() {
            let Some(gobj) = group.as_object() else {
                continue;
            };
            let Some(checks) = gobj.get("checks").and_then(|v| v.as_array()) else {
                continue;
            };
            for (c_index, check) in checks.iter().enumerate() {
                let Some(cobj) = check.as_object() else {
                    continue;
                };
                if cobj.get("mandatory").and_then(|v| v.as_bool()) == Some(true)
                    && cobj.get("status").and_then(|v| v.as_str()) == Some("failed")
                {
                    mandatory_failed = true;
                }
                if cobj.get("status").and_then(|v| v.as_str()) == Some("skipped") {
                    let has_reason = cobj
                        .get("reason_code")
                        .and_then(|v| v.as_str())
                        .map(|s| !s.is_empty())
                        .unwrap_or(false)
                        || cobj
                            .get("skip_reason_code")
                            .and_then(|v| v.as_str())
                            .map(|s| !s.is_empty())
                            .unwrap_or(false);
                    if !has_reason {
                        issues.push(SemanticIssue::new(
                            "MissingSkipReason",
                            format!("check_groups[{g_index}].checks[{c_index}].reason_code"),
                            "skipped checks require reason_code",
                        ));
                    }
                }
            }
        }
    }
    if decision == Some("accept") && mandatory_failed {
        issues.push(SemanticIssue::new(
            "AcceptWithMandatoryFailure",
            "decision",
            "accept cannot coexist with a mandatory failed check",
        ));
    }
    if let (Some(declared), Some(result_class)) = (
        obj.get("declared_input_guarantee_class")
            .and_then(|v| v.as_str()),
        obj.get("guarantee_class").and_then(|v| v.as_str()),
    ) {
        if let (Some(d_rank), Some(r_rank)) = (guarantee_rank(declared), guarantee_rank(result_class))
        {
            if r_rank > d_rank {
                issues.push(SemanticIssue::new(
                    "GuaranteeUpgrade",
                    "guarantee_class",
                    format!(
                        "must not upgrade declared_input_guarantee_class ({declared:?} -> {result_class:?})"
                    ),
                ));
            }
        }
    }
    issues
}

pub fn validate_reward_envelope_semantics(data: &Value) -> Vec<SemanticIssue> {
    let Some(obj) = data.as_object() else {
        return Vec::new();
    };
    let mut issues = forbid_legacy_signature(obj, "RewardEvidenceEnvelope.v1");
    issues.extend(require_integrity(obj, "RewardEvidenceEnvelope.v1"));
    issues.extend(check_zero_commit(
        obj.get("source_commit").and_then(|v| v.as_str()),
        "source_commit",
    ));
    let total = match obj.get("scalar_total") {
        Some(v) => match parse_decimal(v, "scalar_total") {
            Ok(t) => Some(t),
            Err(issue) => {
                issues.push(issue);
                None
            }
        },
        None => None,
    };
    if let (Some(components), Some(total_dec)) = (obj.get("components").and_then(|v| v.as_array()), total)
    {
        if obj.get("composition_function").and_then(|v| v.as_str()) == Some("sum") {
            let mut acc = (0i128, 0u32);
            let mut ok = true;
            for (index, component) in components.iter().enumerate() {
                let Some(cobj) = component.as_object() else {
                    continue;
                };
                match cobj.get("value") {
                    Some(v) => match parse_decimal(v, &format!("components[{index}].value")) {
                        Ok(value) => {
                            if let Some(sum) = add_decimals(acc, value) {
                                acc = sum;
                            } else {
                                ok = false;
                            }
                        }
                        Err(issue) => {
                            issues.push(issue);
                            ok = false;
                        }
                    },
                    None => {}
                }
            }
            if ok && !decimals_equal(acc, total_dec) {
                issues.push(SemanticIssue::new(
                    "RewardCompositionMismatch",
                    "scalar_total",
                    format!("sum of components != scalar_total"),
                ));
            }
        }
    }
    let claims = obj
        .get("claims_issued")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    if !claims.is_empty() {
        let refs = obj.get("verifier_result_refs").and_then(|v| v.as_array());
        if refs.map(|r| r.is_empty()).unwrap_or(true) {
            issues.push(SemanticIssue::new(
                "ClaimsNeedVerifierRefs",
                "verifier_result_refs",
                "claims_issued requires at least one verifier_result_ref",
            ));
        }
    }
    if let Some(prefs) = obj.get("profile_refs").and_then(|v| v.as_array()) {
        let lifecycle = obj.get("lifecycle").and_then(|v| v.as_object());
        let lifecycle_status = lifecycle.and_then(|l| l.get("status")).and_then(|v| v.as_str());
        let migration = lifecycle
            .and_then(|l| l.get("migration_record_id"))
            .and_then(|v| v.as_str())
            .map(|s| !s.is_empty())
            .unwrap_or(false);
        for (index, pref) in prefs.iter().enumerate() {
            let status = pref
                .as_object()
                .and_then(|p| p.get("applicability_status"))
                .and_then(|v| v.as_str());
            if matches!(status, Some("revoked") | Some("expired"))
                && lifecycle_status == Some("active")
                && !migration
            {
                issues.push(SemanticIssue::new(
                    "RevokedProfileGate",
                    format!("profile_refs[{index}]"),
                    format!(
                        "{} profiles cannot support new active rewards without migration_record_id",
                        status.unwrap_or("revoked")
                    ),
                ));
            } else if status == Some("revoked") && lifecycle_status != Some("active") && !claims.is_empty()
            {
                issues.push(SemanticIssue::new(
                    "RevokedProfileGate",
                    format!("profile_refs[{index}]"),
                    "revoked profiles cannot authorize reward claims",
                ));
            }
        }
    }
    let mandatory = obj
        .get("mandatory_unresolved_claim_ids")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    if obj
        .get("lifecycle")
        .and_then(|v| v.as_object())
        .and_then(|l| l.get("status"))
        .and_then(|v| v.as_str())
        == Some("active")
        && !mandatory.is_empty()
    {
        issues.push(SemanticIssue::new(
            "ActiveRewardUnresolvedClaims",
            "mandatory_unresolved_claim_ids",
            "unresolved mandatory claims block active release-grade envelopes",
        ));
    }
    issues
}

pub fn validate_campaign_manifest_semantics(data: &Value) -> Vec<SemanticIssue> {
    let Some(obj) = data.as_object() else {
        return Vec::new();
    };
    let mut issues = forbid_legacy_signature(obj, "OptimizationCampaignManifest.v1");
    issues.extend(require_integrity(obj, "OptimizationCampaignManifest.v1"));
    issues.extend(check_zero_commit(
        obj.get("source_commit").and_then(|v| v.as_str()),
        "source_commit",
    ));
    if obj
        .get("access_class")
        .and_then(|v| v.as_str())
        .map(|s| s.is_empty())
        .unwrap_or(true)
    {
        issues.push(SemanticIssue::new(
            "AccessClassRequired",
            "access_class",
            "access_class is required",
        ));
    }
    if let Some(cohorts) = obj.get("cohorts").and_then(|v| v.as_array()) {
        for (index, cohort) in cohorts.iter().enumerate() {
            let Some(cobj) = cohort.as_object() else {
                continue;
            };
            if !cobj.get("compute_exposure").map(|v| v.is_object()).unwrap_or(false) {
                issues.push(SemanticIssue::new(
                    "CohortComputeExposure",
                    format!("cohorts[{index}].compute_exposure"),
                    "compute_exposure is required",
                ));
            }
            if cobj
                .get("access_class")
                .and_then(|v| v.as_str())
                .map(|s| s.is_empty())
                .unwrap_or(true)
            {
                issues.push(SemanticIssue::new(
                    "CohortAccessClass",
                    format!("cohorts[{index}].access_class"),
                    "every cohort must declare access_class",
                ));
            }
        }
    }
    issues
}

pub fn validate_adjudication_record_semantics(
    data: &Value,
    release_grade: bool,
) -> Vec<SemanticIssue> {
    let Some(obj) = data.as_object() else {
        return Vec::new();
    };
    let mut issues = forbid_legacy_signature(obj, "AdjudicationRecord.v1");
    issues.extend(require_integrity(obj, "AdjudicationRecord.v1"));
    issues.extend(check_zero_commit(
        obj.get("source_commit").and_then(|v| v.as_str()),
        "source_commit",
    ));
    if let Some(protected) = obj.get("protected_rationale").and_then(|v| v.as_object()) {
        if protected
            .get("commitment_digest")
            .and_then(|v| v.as_str())
            .map(|s| s.is_empty())
            .unwrap_or(true)
        {
            issues.push(SemanticIssue::new(
                "RationaleCommitment",
                "protected_rationale.commitment_digest",
                "commitment_digest is required",
            ));
        }
    }
    if release_grade && obj.get("independence_declared").and_then(|v| v.as_bool()) != Some(true) {
        issues.push(SemanticIssue::new(
            "IndependenceForReleaseGrade",
            "independence_declared",
            "release-grade adjudication requires independence_declared=true",
        ));
    }
    issues
}

pub fn validate_assurance_report_semantics(data: &Value) -> Vec<SemanticIssue> {
    let Some(obj) = data.as_object() else {
        return Vec::new();
    };
    let mut issues = forbid_legacy_signature(obj, "VerifierAssuranceReport.v1");
    issues.extend(require_integrity(obj, "VerifierAssuranceReport.v1"));
    issues.extend(check_zero_commit(
        obj.get("source_commit").and_then(|v| v.as_str()),
        "source_commit",
    ));
    let mut claims_gap = false;
    if let Some(metrics) = obj.get("metrics").and_then(|v| v.as_object()) {
        let sample = metrics.get("sample_size").and_then(|v| v.as_i64());
        let excluded = metrics.get("excluded_count").and_then(|v| v.as_i64());
        let unadj = metrics.get("unadjudicated_count").and_then(|v| v.as_i64());
        if let (Some(sample), Some(excluded), Some(unadj)) = (sample, excluded, unadj) {
            if excluded + unadj > sample && sample > 0 {
                issues.push(SemanticIssue::new(
                    "AggregateCountReconcile",
                    "metrics",
                    "excluded_count + unadjudicated_count exceeds sample_size",
                ));
            }
        }
        for key in [
            "false_accept_rate",
            "false_reject_rate",
            "abstention_rate",
            "adjudication_coverage",
        ] {
            if let Some(rate) = metrics.get(key).and_then(|v| v.as_object()) {
                let ci = rate.get("confidence_interval").and_then(|v| v.as_object());
                let method_ok = ci
                    .and_then(|c| c.get("method"))
                    .and_then(|v| v.as_str())
                    .map(|s| !s.is_empty())
                    .unwrap_or(false);
                if !method_ok {
                    issues.push(SemanticIssue::new(
                        "CIMethodsDeclared",
                        format!("metrics.{key}.confidence_interval.method"),
                        "CI method must be declared",
                    ));
                } else if ci
                    .and_then(|c| c.get("parameters"))
                    .map(|v| v.is_object())
                    .unwrap_or(false)
                    == false
                {
                    issues.push(SemanticIssue::new(
                        "CIParametersDeclared",
                        format!("metrics.{key}.confidence_interval.parameters"),
                        "CI parameters must be declared (no silent denominator invention)",
                    ));
                }
            }
        }
        let gap = metrics.get("optimization_gap").and_then(|v| v.as_str());
        let gap_nonzero = matches!(gap, Some(g) if g != "0" && g != "0.0" && g != "0.000000");
        let ordinary_den = metrics
            .get("ordinary_accept_rate")
            .and_then(|v| v.as_object())
            .and_then(|o| o.get("denominator"))
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        let optimized_den = metrics
            .get("optimized_accept_rate")
            .and_then(|v| v.as_object())
            .and_then(|o| o.get("denominator"))
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        claims_gap = gap_nonzero || (ordinary_den > 0 && optimized_den > 0);

        let excluded_items = obj.get("excluded_items").and_then(|v| v.as_array());
        let unadj_items = obj.get("unadjudicated_items").and_then(|v| v.as_array());
        if let Some(excluded_count) = metrics.get("excluded_count").and_then(|v| v.as_i64()) {
            match excluded_items {
                Some(items) if items.len() as i64 != excluded_count => {
                    issues.push(SemanticIssue::new(
                        "ExcludedItemsVisible",
                        "excluded_items",
                        "excluded_count must equal len(excluded_items)",
                    ));
                }
                None if excluded_count > 0 => {
                    issues.push(SemanticIssue::new(
                        "ExcludedItemsVisible",
                        "excluded_items",
                        "excluded_count > 0 requires visible excluded_items",
                    ));
                }
                _ => {}
            }
        }
        if let Some(unadj_count) = metrics.get("unadjudicated_count").and_then(|v| v.as_i64()) {
            match unadj_items {
                Some(items) if items.len() as i64 != unadj_count => {
                    issues.push(SemanticIssue::new(
                        "UnadjudicatedItemsVisible",
                        "unadjudicated_items",
                        "unadjudicated_count must equal len(unadjudicated_items)",
                    ));
                }
                None if unadj_count > 0 => {
                    issues.push(SemanticIssue::new(
                        "UnadjudicatedItemsVisible",
                        "unadjudicated_items",
                        "unadjudicated_count > 0 requires visible unadjudicated_items",
                    ));
                }
                _ => {}
            }
        }
    }
    if let Some(cohorts) = obj.get("cohorts").and_then(|v| v.as_array()) {
        let mut has_ordinary = false;
        let mut has_optimized = false;
        for (index, cohort) in cohorts.iter().enumerate() {
            let Some(cobj) = cohort.as_object() else {
                continue;
            };
            match cobj.get("cohort_kind").and_then(|v| v.as_str()) {
                Some("ordinary") => has_ordinary = true,
                Some("optimized") => has_optimized = true,
                _ => {}
            }
            if cobj
                .get("access_class")
                .and_then(|v| v.as_str())
                .map(|s| s.is_empty())
                .unwrap_or(true)
            {
                issues.push(SemanticIssue::new(
                    "CohortAccessClass",
                    format!("cohorts[{index}].access_class"),
                    "every cohort must declare access_class",
                ));
            }
            if !cobj.get("compute_exposure").map(|v| v.is_object()).unwrap_or(false) {
                issues.push(SemanticIssue::new(
                    "CohortComputeExposure",
                    format!("cohorts[{index}].compute_exposure"),
                    "every cohort must declare compute_exposure",
                ));
            }
            let accept = cobj.get("accept_count").and_then(|v| v.as_i64());
            let reject = cobj.get("reject_count").and_then(|v| v.as_i64());
            let indeterminate = cobj.get("indeterminate_count").and_then(|v| v.as_i64());
            let included = cobj.get("included_result_count").and_then(|v| v.as_i64());
            if let (Some(a), Some(r), Some(i), Some(n)) = (accept, reject, indeterminate, included) {
                if a + r + i != n {
                    issues.push(SemanticIssue::new(
                        "CohortCountMismatch",
                        format!("cohorts[{index}]"),
                        "aggregate counts must reconcile exactly with included records",
                    ));
                }
                if i < 0 || a < 0 || r < 0 {
                    issues.push(SemanticIssue::new(
                        "IndeterminateMisclassification",
                        format!("cohorts[{index}]"),
                        "cohort decision counts must be non-negative distinct buckets",
                    ));
                }
            }
        }
        if claims_gap && !(has_ordinary && has_optimized) {
            issues.push(SemanticIssue::new(
                "OptimizationGapCohorts",
                "cohorts",
                "optimization-gap metrics require ordinary and optimized cohorts",
            ));
        }
    } else if claims_gap {
        issues.push(SemanticIssue::new(
            "OptimizationGapCohorts",
            "cohorts",
            "optimization-gap metrics require ordinary and optimized cohorts",
        ));
    }
    if obj.get("release_grade").and_then(|v| v.as_bool()) == Some(true)
        && obj.get("independent_adjudication").and_then(|v| v.as_bool()) != Some(true)
    {
        issues.push(SemanticIssue::new(
            "ReleaseGradeAdjudication",
            "independent_adjudication",
            "release-grade reports require independent_adjudication=true",
        ));
    }
    issues
}

/// Dispatch used by `validate_semantics` for all VA *.v1 types.
pub fn validate_va_semantics(data: &Value, artifact_type: &str) -> Vec<SemanticIssue> {
    match artifact_type {
        "VerifierProfile.v1" => validate_verifier_profile_semantics(data),
        "VerificationResult.v1" => validate_verification_result_semantics(data),
        "RewardEvidenceEnvelope.v1" => validate_reward_envelope_semantics(data),
        "OptimizationCampaignManifest.v1" => validate_campaign_manifest_semantics(data),
        "AdjudicationRecord.v1" => validate_adjudication_record_semantics(data, false),
        "VerifierAssuranceReport.v1" => validate_assurance_report_semantics(data),
        other => vec![SemanticIssue::new(
            "UnknownArtifactType",
            "artifact_type",
            format!("unknown verifier-assurance artifact type: {other}"),
        )],
    }
}

pub fn validate_va_semantics_strings(data: &Value, artifact_type: &str) -> Vec<String> {
    issue_strings(&validate_va_semantics(data, artifact_type))
}

pub fn is_va_artifact_type(artifact_type: &str) -> bool {
    matches!(
        artifact_type,
        "VerifierProfile.v1"
            | "VerificationResult.v1"
            | "RewardEvidenceEnvelope.v1"
            | "OptimizationCampaignManifest.v1"
            | "AdjudicationRecord.v1"
            | "VerifierAssuranceReport.v1"
    )
}

/// Verify a VerifierAssuranceReport.v1: semantics + integrity digest match.
pub fn verify_assurance_report(report: &Value) -> Vec<SemanticIssue> {
    let mut issues = validate_assurance_report_semantics(report);
    if let Some(obj) = report.as_object() {
        if let Some(integrity) = obj.get("integrity").and_then(|v| v.as_object()) {
            let mut body = obj.clone();
            body.remove("integrity");
            let expected = canonical_hash(&Value::Object(body));
            let got = integrity.get("artifact_digest").and_then(|v| v.as_str());
            if got != Some(expected.as_str()) {
                issues.push(SemanticIssue::new(
                    "ReportDigestMismatch",
                    "integrity.artifact_digest",
                    "artifact_digest does not match report body",
                ));
            }
        }
    }
    issues
}

fn require_keys(obj: &Map<String, Value>, keys: &[&str], artifact: &str) -> Result<(), String> {
    for key in keys {
        if !obj.contains_key(*key) {
            return Err(format!("{artifact}: missing mandatory field {key}"));
        }
    }
    Ok(())
}

/// Constructor: rejects missing mandatory top-level fields; does not silently drop unknowns
/// (callers must pass an exact object; extras are preserved for schema to reject).
pub fn construct_va_artifact(artifact_type: &str, fields: Map<String, Value>) -> Result<Value, String> {
    let required: &[&str] = match artifact_type {
        "VerifierProfile.v1" => &[
            "schema_version",
            "artifact_type",
            "verifier_profile_id",
            "created_at",
            "producer",
            "producer_version",
            "source_repo",
            "source_commit",
            "implementation",
            "configuration",
            "mechanism",
            "claim_surface",
            "applicability",
            "assumptions",
            "known_blind_spots",
            "integrity",
        ],
        "VerificationResult.v1" => &[
            "schema_version",
            "artifact_type",
            "verification_result_id",
            "created_at",
            "producer",
            "producer_version",
            "source_repo",
            "source_commit",
            "verifier_profile",
            "claim_ids",
            "raw_backend_output_digest",
            "normalized_result_digest",
            "normalization_applied",
            "check_groups",
            "resource_limits",
            "execution_status",
            "decision",
            "integrity",
        ],
        "RewardEvidenceEnvelope.v1" => &[
            "schema_version",
            "artifact_type",
            "reward_envelope_id",
            "created_at",
            "producer",
            "producer_version",
            "source_repo",
            "source_commit",
            "scalar_total",
            "components",
            "composition_function",
            "integrity",
        ],
        "OptimizationCampaignManifest.v1" => &[
            "schema_version",
            "artifact_type",
            "campaign_id",
            "created_at",
            "producer",
            "producer_version",
            "source_repo",
            "source_commit",
            "access_class",
            "cohorts",
            "integrity",
        ],
        "AdjudicationRecord.v1" => &[
            "schema_version",
            "artifact_type",
            "adjudication_id",
            "created_at",
            "producer",
            "producer_version",
            "source_repo",
            "source_commit",
            "subject",
            "label",
            "independence_declared",
            "integrity",
        ],
        "VerifierAssuranceReport.v1" => &[
            "schema_version",
            "artifact_type",
            "report_id",
            "created_at",
            "producer",
            "producer_version",
            "source_repo",
            "source_commit",
            "campaign_ref",
            "release_grade",
            "independent_adjudication",
            "metrics",
            "cohorts",
            "integrity",
        ],
        other => return Err(format!("unsupported VA constructor type: {other}")),
    };
    require_keys(&fields, required, artifact_type)?;
    if fields.get("artifact_type").and_then(|v| v.as_str()) != Some(artifact_type) {
        return Err(format!(
            "{artifact_type}: artifact_type must be {artifact_type:?}"
        ));
    }
    // Unknown fields are retained intentionally so schema validation can reject them
    // (no silent drop).
    Ok(Value::Object(fields))
}

/// Attach nested integrity envelope (Python `attach_nested_integrity` equivalent).
pub fn attach_nested_integrity(data: &Value) -> Value {
    let mut body = match data {
        Value::Object(map) => map.clone(),
        other => {
            let mut m = Map::new();
            m.insert("_".into(), other.clone());
            m
        }
    };
    body.remove("integrity");
    let digest = canonical_hash(&Value::Object(body.clone()));
    body.insert(
        "integrity".into(),
        json!({
            "canonicalization_version": "v1",
            "artifact_digest": digest,
        }),
    );
    Value::Object(body)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::fs;
    use std::path::PathBuf;

    fn examples_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../..")
            .join("examples")
            .join("verifier_assurance")
    }

    fn load(rel: &str) -> Value {
        let path = examples_dir().join(rel);
        serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap()
    }

    #[test]
    fn va_valid_fixtures_pass_semantics() {
        for rel in [
            "valid/profile_basic/profile.json",
            "valid/result_accept/result.json",
            "valid/reward_scalar/reward.json",
            "valid/campaign_basic/campaign.json",
            "valid/adjudication_basic/adjudication.json",
            "valid/report_rebuild/report.json",
        ] {
            let data = load(rel);
            let artifact_type = data
                .get("artifact_type")
                .and_then(|v| v.as_str())
                .unwrap();
            let issues = validate_va_semantics(&data, artifact_type);
            assert!(issues.is_empty(), "{rel}: {issues:?}");
        }
    }

    #[test]
    fn va_invalid_fixtures_emit_expected_codes() {
        let cases = [
            ("invalid/timeout_accept", "FailClosedDecision"),
            ("invalid/accept_mandatory_failure", "AcceptWithMandatoryFailure"),
            ("invalid/identical_normalization_digests", "IdenticalNormalizationDigests"),
            ("invalid/reward_total_mismatch", "RewardCompositionMismatch"),
            ("invalid/revoked_profile_active_reward", "RevokedProfileGate"),
            ("invalid/missing_rationale_commitment", "RationaleCommitment"),
            ("invalid/short_source_commit", "InvalidSourceCommit"),
            ("invalid/release_grade_no_adjudication", "ReleaseGradeAdjudication"),
            ("invalid/optimization_gap_missing_cohort", "OptimizationGapCohorts"),
            ("invalid/cohort_missing_access", "CohortAccessClass"),
            ("invalid/cohort_count_mismatch", "CohortCountMismatch"),
            ("invalid/excluded_items_invisible", "ExcludedItemsVisible"),
            ("invalid/missing_ci_method", "CIMethodsDeclared"),
            ("invalid/indeterminate_misclassification", "IndeterminateMisclassification"),
            ("invalid/active_reward_unresolved", "ActiveRewardUnresolvedClaims"),
        ];
        for (dir, code) in cases {
            let manifest: Value = load(&format!("{dir}/manifest.json"));
            let artifact_file = manifest
                .get("artifact_file")
                .and_then(|v| v.as_str())
                .unwrap_or("artifact.json");
            let artifact_type = manifest
                .get("artifact_type")
                .and_then(|v| v.as_str())
                .unwrap();
            let data = load(&format!("{dir}/{artifact_file}"));
            let issues = validate_va_semantics(&data, artifact_type);
            assert!(
                issues.iter().any(|i| i.code == code),
                "{dir}: expected {code}, got {issues:?}"
            );
        }
    }

    #[test]
    fn va_verify_report_accepts_valid_and_rejects_digest_tamper() {
        let report = load("valid/report_rebuild/report.json");
        assert!(verify_assurance_report(&report).is_empty());
        let mut tampered = report.clone();
        if let Some(obj) = tampered.as_object_mut() {
            obj.insert("report_id".into(), json!("tampered"));
        }
        let issues = verify_assurance_report(&tampered);
        assert!(
            issues.iter().any(|i| i.code == "ReportDigestMismatch"),
            "{issues:?}"
        );
    }

    #[test]
    fn va_constructor_requires_mandatory_fields() {
        let err = construct_va_artifact("VerifierProfile.v1", Map::new()).unwrap_err();
        assert!(err.contains("missing mandatory field"));
        let mut fields = Map::new();
        for key in [
            "schema_version",
            "artifact_type",
            "verifier_profile_id",
            "created_at",
            "producer",
            "producer_version",
            "source_repo",
            "source_commit",
            "implementation",
            "configuration",
            "mechanism",
            "claim_surface",
            "applicability",
            "assumptions",
            "known_blind_spots",
            "integrity",
        ] {
            fields.insert(
                key.into(),
                if key == "artifact_type" {
                    json!("VerifierProfile.v1")
                } else if key == "assumptions" || key == "known_blind_spots" {
                    json!([])
                } else {
                    json!("x")
                },
            );
        }
        // Retain unknown field — must not be dropped.
        fields.insert("extra_field".into(), json!(true));
        let built = construct_va_artifact("VerifierProfile.v1", fields).unwrap();
        assert!(built.get("extra_field").is_some());
    }

    #[test]
    fn va_reward_sum_parity() {
        let mut reward = load("valid/reward_scalar/reward.json");
        assert!(validate_reward_envelope_semantics(&reward).is_empty());
        if let Some(obj) = reward.as_object_mut() {
            obj.insert("scalar_total".into(), json!("9.9"));
        }
        let issues = validate_reward_envelope_semantics(&reward);
        assert!(issues.iter().any(|i| i.code == "RewardCompositionMismatch"));
    }
}
