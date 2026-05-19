use serde_json::Value;

use crate::schema::{compile_schema, validate_schema};
use crate::status::{
    ARTIFACT_STATUSES, CERTIFIED_CLAIM_STATUSES, IMPORT_READY_VERIFICATION_STATUSES,
    TRACE_CERTIFICATE_STATUSES,
};

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
    ("ReleaseManifest.v0", "ReleaseManifest.v0.schema.json"),
    ("HandoffManifest.v0", "HandoffManifest.v0.schema.json"),
    (
        "ReleaseChainValidationResult.v0",
        "ReleaseChainValidationResult.v0.schema.json",
    ),
    ("ArtifactRegistry.v0", "ArtifactRegistry.v0.schema.json"),
    ("MigrationReport.v0", "MigrationReport.v0.schema.json"),
    ("WorkflowProfile.v0", "WorkflowProfile.v0.schema.json"),
    ("ToolUseTrace.v0", "ToolUseTrace.v0.schema.json"),
    ("ToolUseCertificate.v0", "ToolUseCertificate.v0.schema.json"),
    ("DatasetReceipt.v0", "DatasetReceipt.v0.schema.json"),
    ("EnvironmentReceipt.v0", "EnvironmentReceipt.v0.schema.json"),
    ("ComputationRunReceipt.v0", "ComputationRunReceipt.v0.schema.json"),
    ("ResultArtifact.v0", "ResultArtifact.v0.schema.json"),
    ("ComputationWitness.v0", "ComputationWitness.v0.schema.json"),
    ("ProofObligation.v0", "ProofObligation.v0.schema.json"),
    ("LeanCheckResult.v0", "LeanCheckResult.v0.schema.json"),
    ("BenchmarkRegistry.v0", "BenchmarkRegistry.v0.schema.json"),
    ("BenchmarkTask.v0", "BenchmarkTask.v0.schema.json"),
    ("BenchmarkCase.v0", "BenchmarkCase.v0.schema.json"),
    ("BenchmarkRun.v0", "BenchmarkRun.v0.schema.json"),
    ("BenchmarkReport.v0", "BenchmarkReport.v0.schema.json"),
    ("ConformanceRun.v0", "ConformanceRun.v0.schema.json"),
    ("FailureCaseManifest.v0", "FailureCaseManifest.v0.schema.json"),
    (
        "FailureLocalizationResult.v0",
        "FailureLocalizationResult.v0.schema.json",
    ),
    ("CoverageReport.v0", "CoverageReport.v0.schema.json"),
    ("ConformanceReport.v0", "ConformanceReport.v0.schema.json"),
    (
        "SemanticCheckExecution.v0",
        "SemanticCheckExecution.v0.schema.json",
    ),
    (
        "ComponentReleaseFragment.v0",
        "ComponentReleaseFragment.v0.schema.json",
    ),
];

const PROTOCOL_ARTIFACT_TYPES: &[&str] = &[
    "ReleaseManifest.v0",
    "HandoffManifest.v0",
    "ReleaseChainValidationResult.v0",
    "ArtifactRegistry.v0",
    "MigrationReport.v0",
];

pub fn detect_artifact_type(value: &Value) -> Option<&'static str> {
    let obj = value.as_object()?;
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("registry_id").and_then(|v| v.as_str()).is_some()
        && obj.get("suites").map(|v| v.is_object()).unwrap_or(false)
        && obj.contains_key("registry_version")
    {
        return Some("BenchmarkRegistry.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("report_id").and_then(|v| v.as_str()).is_some()
        && obj.get("benchmark_suite_id").and_then(|v| v.as_str()).is_some()
        && obj.get("summary").map(|v| v.is_object()).unwrap_or(false)
    {
        return Some("BenchmarkReport.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("run_id").and_then(|v| v.as_str()).is_some()
        && obj.get("case_id").and_then(|v| v.as_str()).is_some()
        && obj.contains_key("duration_ms")
        && obj.contains_key("observed_status")
    {
        return Some("BenchmarkRun.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("case_id").and_then(|v| v.as_str()).is_some()
        && obj.get("case_kind").and_then(|v| v.as_str()).is_some()
        && obj.contains_key("input_artifacts")
    {
        return Some("BenchmarkCase.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("task_id").and_then(|v| v.as_str()).is_some()
        && obj.get("metrics").map(|v| v.is_array()).unwrap_or(false)
        && obj.contains_key("success_criteria")
    {
        return Some("BenchmarkTask.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("coverage_id").and_then(|v| v.as_str()).is_some()
        && obj.contains_key("coverage_ratio")
        && obj.contains_key("numerator")
    {
        return Some("CoverageReport.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("result_id").and_then(|v| v.as_str()).is_some()
        && obj.contains_key("localized_correctly")
    {
        return Some("FailureLocalizationResult.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("manifest_id").and_then(|v| v.as_str()).is_some()
        && obj.get("failure_code").and_then(|v| v.as_str()).is_some()
        && obj.contains_key("repair_hint_kind")
    {
        return Some("FailureCaseManifest.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("run_id").and_then(|v| v.as_str()).is_some()
        && obj.get("suite").and_then(|v| v.as_str()).is_some()
        && obj.contains_key("started_at")
        && obj.contains_key("completed_at")
    {
        return Some("ConformanceRun.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("suite").is_some()
        && obj.get("checks_passed").is_some()
        && obj.get("failures").map(|v| v.is_array()).unwrap_or(false)
    {
        return Some("ConformanceReport.v0");
    }
    if obj.contains_key("policy_id")
        && obj.contains_key("severity_definitions")
        && obj.get("checks").map(|v| v.is_array()).unwrap_or(false)
    {
        return Some("SemanticCheckExecution.v0");
    }
    if obj.contains_key("from_version")
        && obj.contains_key("to_version")
        && obj.contains_key("changes")
        && obj.contains_key("artifact_type")
    {
        return Some("MigrationReport.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("check_id").and_then(|v| v.as_str()).is_some()
        && obj.get("proof_obligation_id").and_then(|v| v.as_str()).is_some()
        && obj.contains_key("lean_theorem")
        && obj.contains_key("lean_version")
    {
        return Some("LeanCheckResult.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("obligation_id").and_then(|v| v.as_str()).is_some()
        && obj.get("obligations").map(|v| v.is_array()).unwrap_or(false)
        && obj.contains_key("lean_module")
    {
        return Some("ProofObligation.v0");
    }
    if obj.contains_key("validation_id") && obj.contains_key("artifacts_checked") {
        return Some("ReleaseChainValidationResult.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("component").is_some()
        && obj.get("artifacts").map(|v| v.is_object()).unwrap_or(false)
        && obj.contains_key("signature_or_digest")
        && obj.contains_key("source_commit")
    {
        return Some("ComponentReleaseFragment.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("workflow_id").is_some()
        && obj.get("domain").is_some()
        && obj.get("handoff_sequence").map(|v| v.is_array()).unwrap_or(false)
        && obj.get("runtime_artifacts").map(|v| v.is_array()).unwrap_or(false)
    {
        return Some("WorkflowProfile.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("witness_id").is_some()
        && obj.get("dataset_hash").is_some()
        && obj.get("run_receipt_hash").is_some()
    {
        return Some("ComputationWitness.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("dataset_id").is_some()
        && obj.get("aggregate_hash").is_some()
        && obj.get("files").map(|v| v.is_array()).unwrap_or(false)
    {
        return Some("DatasetReceipt.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("environment_id").is_some()
        && obj.get("environment_kind").is_some()
    {
        return Some("EnvironmentReceipt.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("run_id").is_some()
        && obj.get("command").is_some()
        && obj.contains_key("dataset_receipt_ref")
    {
        return Some("ComputationRunReceipt.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("result_id").is_some()
        && obj.get("result_kind").is_some()
    {
        return Some("ResultArtifact.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("trace_id").is_some()
        && obj.get("tool_calls").map(|v| v.is_array()).unwrap_or(false)
    {
        return Some("ToolUseTrace.v0");
    }
    if obj.get("schema_version") == Some(&Value::String("v0".into()))
        && obj.get("certificate_id").is_some()
        && obj.contains_key("policy_hash")
        && obj.get("violations").map(|v| v.is_array()).unwrap_or(false)
        && !obj.contains_key("spec_hash")
    {
        return Some("ToolUseCertificate.v0");
    }
    if obj.contains_key("handoff_id") && obj.contains_key("handoff_kind") {
        return Some("HandoffManifest.v0");
    }
    if obj.contains_key("registry_id")
        && obj.contains_key("entries")
        && obj.contains_key("registry_version")
    {
        return Some("ArtifactRegistry.v0");
    }
    if obj.contains_key("release_id")
        && obj.contains_key("producer_repos")
        && obj.contains_key("validation_profile")
        && obj.contains_key("workflow_profile_id")
    {
        return Some("ReleaseManifest.v0");
    }
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

fn validate_verification_result(obj: &serde_json::Map<String, Value>, errors: &mut Vec<String>) {
    let checks = match obj.get("checks").and_then(|v| v.as_array()) {
        Some(c) => c,
        None => return,
    };
    let has_failed = checks.iter().any(|check| {
        check
            .as_object()
            .and_then(|c| c.get("status"))
            .and_then(|s| s.as_str())
            == Some("failed")
    });
    let top_status = obj.get("status").and_then(|v| v.as_str()).unwrap_or("");
    if has_failed
        && IMPORT_READY_VERIFICATION_STATUSES
            .iter()
            .any(|s| *s == top_status)
    {
        errors.push(format!(
            "VerificationResult.v0 with failed checks cannot use import-ready status {top_status:?} (Scientific Memory import contract)"
        ));
    }
}

pub fn validate_semantics(value: &Value, artifact_type: &str) -> Result<(), ValidationError> {
    if PROTOCOL_ARTIFACT_TYPES.contains(&artifact_type) {
        return Ok(());
    }
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
        if artifact_type == "VerificationResult.v0" {
            validate_verification_result(obj, &mut errors);
        }
        if artifact_type == "SignedScienceClaimBundle.v0" {
            if let Some(scb) = obj.get("science_claim_bundle").and_then(|v| v.as_object()) {
                validate_science_claim_bundle(scb, &mut errors);
            }
            if let Some(vr) = obj.get("verification_result").and_then(|v| v.as_object()) {
                validate_verification_result(vr, &mut errors);
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

    fn shared_hash_vectors_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../test_vectors/hash")
    }

    #[test]
    fn valid_examples_pass_jsonschema_and_semantics() {
        for entry in WalkDir::new(examples_dir())
            .into_iter()
            .filter_map(Result::ok)
        {
            let path = entry.path();
            if !entry.file_type().is_file() {
                continue;
            }
            let path_str = path.to_string_lossy();
            if path_str.contains("tool-use-release-invalid")
                || path_str.contains("computation-release-invalid")
            {
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

    #[test]
    fn hash_vectors_match_shared_fixtures() {
        shared_hash_vectors_match_repo_fixtures_inner();
    }

    #[test]
    fn shared_hash_vectors_match_repo_fixtures() {
        shared_hash_vectors_match_repo_fixtures_inner();
    }

    #[test]
    fn detect_benchmark_registry() {
        let examples = examples_dir();
        let path = examples.join("benchmark_registry.valid.json");
        if !path.is_file() {
            return;
        }
        let data: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(detect_artifact_type(&data), Some("BenchmarkRegistry.v0"));
    }

    fn shared_hash_vectors_match_repo_fixtures_inner() {
        let examples = examples_dir();
        for file_name in std::fs::read_dir(shared_hash_vectors_dir()).unwrap() {
            let path = file_name.unwrap().path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }
            let vector: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
            let artifact_type = vector["artifact_type"].as_str().unwrap();
            let example_name = vector["input"]
                .as_str()
                .or_else(|| vector["input_file"].as_str())
                .unwrap();
            let example_path = if example_name.starts_with("examples/") {
                PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("../../..")
                    .join(example_name)
            } else {
                examples.join(example_name)
            };
            let data: Value =
                serde_json::from_str(&fs::read_to_string(&example_path).unwrap()).unwrap();
            let expected_digest = vector["expected_digest"].as_str().unwrap();
            let expected_canonical = vector["canonical_json"].as_str().unwrap();
            assert_eq!(canonical_json_string(&data), expected_canonical, "{artifact_type}");
            assert_eq!(canonical_hash(&data), expected_digest, "{artifact_type}");
        }
    }
}
