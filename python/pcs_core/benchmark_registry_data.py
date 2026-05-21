"""Canonical BenchmarkRegistry.v0 suite definitions."""

from __future__ import annotations

from typing import Any

PCS_CORE_REPO = "https://github.com/SentinelOps-CI/pcs-core"

_STANDARD_METRICS = [
    "release_reproducibility_score",
    "failure_localization_accuracy",
    "certificate_completeness_score",
    "registry_coverage_score",
    "formal_check_coverage_score",
    "scientific_memory_interpretability_score",
]

_STANDARD_THRESHOLDS = {
    "minimum_pass_rate": 1.0,
    "minimum_failure_localization_accuracy": 1.0,
    "minimum_formal_check_coverage": 1.0,
    "minimum_registry_coverage": 0.95,
    "minimum_scientific_memory_render_coverage": 1.0,
}

_LABTRUST_ARTIFACTS = [
    "RuntimeReceipt.v0",
    "TraceCertificate.v0",
    "ScienceClaimBundle.v0",
    "VerificationResult.v0",
    "SignedScienceClaimBundle.v0",
    "ReleaseManifest.v0",
    "ReleaseChainValidationResult.v0",
    "ProofObligation.v0",
    "LeanCheckResult.v0",
]

_TOOL_USE_ARTIFACTS = [
    "ToolUseTrace.v0",
    "ToolUseCertificate.v0",
    "RuntimeReceipt.v0",
    "ScienceClaimBundle.v0",
    "VerificationResult.v0",
    "SignedScienceClaimBundle.v0",
    "ReleaseManifest.v0",
    "ReleaseChainValidationResult.v0",
    "ProofObligation.v0",
    "LeanCheckResult.v0",
]

_COMPUTATION_ARTIFACTS = [
    "DatasetReceipt.v0",
    "EnvironmentReceipt.v0",
    "ComputationRunReceipt.v0",
    "ResultArtifact.v0",
    "ComputationWitness.v0",
    "ScienceClaimBundle.v0",
    "VerificationResult.v0",
    "SignedScienceClaimBundle.v0",
    "ReleaseManifest.v0",
    "ReleaseChainValidationResult.v0",
    "ProofObligation.v0",
    "LeanCheckResult.v0",
]


def benchmark_suite_entries() -> dict[str, dict[str, Any]]:
    return {
        "labtrust-qc-release-v0": {
            "suite_id": "labtrust-qc-release-v0",
            "task_id": "labtrust-qc-release-v0",
            "fixture_root": "benchmarks/labtrust-qc-release",
            "workflow_ids": ["hospital_lab.qc_release", "labtrust.qc_release_v0.1"],
            "required_artifacts": _LABTRUST_ARTIFACTS,
            "valid_cases": ["labtrust-valid-release-v0"],
            "invalid_cases": [
                "labtrust-certificate-id-tamper-v0",
                "labtrust-lean-rejected-certificate-v0",
                "labtrust-lean-signed-hash-mismatch-v0",
                "labtrust-lean-stale-certificate-v0",
                "labtrust-lean-trace-hash-mismatch-v0",
                "labtrust-legacy-handoff-file-v0",
                "labtrust-missing-qc-result-v0",
                "labtrust-placeholder-commit-v0",
                "labtrust-scientific-memory-import-failure-v0",
                "labtrust-stale-trace-after-certificate-v0",
                "labtrust-trace-hash-tamper-v0",
                "labtrust-unauthorized-release-v0",
            ],
            "metrics": list(_STANDARD_METRICS),
            "minimum_passing_thresholds": dict(_STANDARD_THRESHOLDS),
        },
        "tool-use-safety-v0": {
            "suite_id": "tool-use-safety-v0",
            "task_id": "tool-use-safety-v0",
            "fixture_root": "benchmarks/tool-use-safety",
            "workflow_ids": ["agent_tool_use.safety_v0"],
            "required_artifacts": _TOOL_USE_ARTIFACTS,
            "valid_cases": ["valid-release-chain"],
            "invalid_cases": [
                "invalid-trace-hash",
                "invalid-unauthorized-tool-call",
                "invalid-rejected-certificate",
            ],
            "metrics": list(_STANDARD_METRICS),
            "minimum_passing_thresholds": dict(_STANDARD_THRESHOLDS),
        },
        "computation-reproducibility-v0": {
            "suite_id": "computation-reproducibility-v0",
            "task_id": "computation-reproducibility-v0",
            "fixture_root": "benchmarks/computation-reproducibility",
            "workflow_ids": ["scientific_computation.reproducibility_v0"],
            "required_artifacts": _COMPUTATION_ARTIFACTS,
            "valid_cases": ["valid-release-chain"],
            "invalid_cases": [
                "invalid-witness-hash",
            ],
            "metrics": list(_STANDARD_METRICS),
            "minimum_passing_thresholds": dict(_STANDARD_THRESHOLDS),
        },
        "cross-domain-release-chain-v0": {
            "suite_id": "cross-domain-release-chain-v0",
            "task_id": "cross-domain-release-chain-v0",
            "fixture_root": "benchmarks/cross-domain",
            "workflow_ids": [
                "labtrust.qc_release_v0.1",
                "agent_tool_use.safety_v0",
                "scientific_computation.reproducibility_v0",
            ],
            "required_artifacts": sorted(
                set(_LABTRUST_ARTIFACTS + _TOOL_USE_ARTIFACTS + _COMPUTATION_ARTIFACTS),
            ),
            "valid_cases": [
                "valid-labtrust-release",
                "valid-tool-use-release",
                "valid-computation-release",
            ],
            "invalid_cases": [],
            "metrics": [
                "release_reproducibility_score",
                "failure_localization_accuracy",
                "registry_coverage_score",
                "cross_domain_portability_score",
            ],
            "minimum_passing_thresholds": {
                "minimum_pass_rate": 1.0,
                "minimum_failure_localization_accuracy": 1.0,
                "minimum_registry_coverage": 0.95,
            },
        },
        "formal-trust-kernel-v0": {
            "suite_id": "formal-trust-kernel-v0",
            "task_id": "formal-trust-kernel-v0",
            "fixture_root": "benchmarks/cross-domain",
            "workflow_ids": [
                "labtrust.qc_release_v0.1",
                "agent_tool_use.safety_v0",
                "scientific_computation.reproducibility_v0",
            ],
            "required_artifacts": ["ProofObligation.v0", "LeanCheckResult.v0"],
            "valid_cases": [
                "formal-labtrust-lean-check",
                "formal-tool-use-lean-check",
                "formal-computation-lean-check",
            ],
            "invalid_cases": [],
            "metrics": ["formal_check_coverage_score", "failure_localization_accuracy"],
            "minimum_passing_thresholds": {
                "minimum_pass_rate": 1.0,
                "minimum_formal_check_coverage": 1.0,
            },
        },
        "scientific-memory-rendering-v0": {
            "suite_id": "scientific-memory-rendering-v0",
            "task_id": "scientific-memory-rendering-v0",
            "fixture_root": "benchmarks/labtrust-qc-release",
            "workflow_ids": ["hospital_lab.qc_release", "labtrust.qc_release_v0.1"],
            "required_artifacts": ["ScientificMemory.ImportReport.v0"],
            "valid_cases": ["labtrust-valid-release-v0"],
            "invalid_cases": ["labtrust-scientific-memory-import-failure-v0"],
            "metrics": [
                "scientific_memory_interpretability_score",
                "failure_localization_accuracy",
            ],
            "minimum_passing_thresholds": {
                "minimum_pass_rate": 1.0,
                "minimum_scientific_memory_render_coverage": 1.0,
                "minimum_failure_localization_accuracy": 1.0,
            },
        },
    }
