# Workflow profiles (v0.1)

`WorkflowProfile.v0` describes how a domain workflow maps onto the shared PCS trust loop while keeping domain-specific ontologies in downstream data instead of core schemas, and release fixtures are documented in [release-protocol.md](release-protocol.md).

## Purpose

Downstream repositories declare workflows in data files instead of hardcoded assumptions.

| Field | Role |
|-------|------|
| `workflow_id` | Stable identifier such as `agent_tool_use.safety_v0` or `labtrust.qc_release_v0.1` |
| `domain` | Coarse domain label such as `agent_tool_use` or `lab_science_simulation` |
| `runtime_artifacts` | Artifact types produced at runtime before certification |
| `certificate_artifacts` | Certificate types that attest runtime evidence |
| `handoff_sequence` | Ordered `handoff_kind` values for the PCS handoff graph |
| `required_registry_entries` | Artifact types that must appear in `ArtifactRegistry.v0` |
| `required_admission_profile` | Scientific Memory admission profile id for import |
| `status_policy` | Lifecycle constraints for the workflow |
| `failure_modes` | Named failure classes consumers should handle |
| `limitations_notice` | Non-goals and scope boundaries |

## Examples

| Profile | Path |
|---------|------|
| LabTrust QC release | `examples/workflow_profiles/labtrust_qc_release.valid.json` |
| Agent tool-use safety | `examples/workflow_profiles/agent_tool_use_safety.valid.json` |
| Scientific computation reproducibility | `examples/workflow_profiles/scientific_computation_reproducibility.valid.json` |

## Tool-use policy hash convention

`ToolUseCertificate.v0.policy_hash` must equal the canonical digest of a JSON object containing `policy_id` copied from `ToolUseTrace.v0.policy_id`.

```python
from pcs_core.tool_use_validate import policy_hash_from_policy_id

policy_hash_from_policy_id("policy-no-secret-exfiltration-v0")
```

## Release manifest and Scientific Memory

`ReleaseManifest.v0` requires `workflow_profile_id` with the same value as `validation_profile` for v0.1 fixtures, and the tool-use train includes `scientific_memory_import_report.json` with `workflow_profile_id` and `workflow_profile_render_path` so Scientific Memory consumers can surface the active workflow profile in rendered output.

## Release-chain coverage scoping

`ReleaseChainValidationResult.v0` includes `workflow_profile_id` for profile-scoped registry coverage, and when the field is omitted coverage uses the LabTrust v0.1 profile scope.

## Conformance

```bash
pcs validate examples/workflow_profiles/agent_tool_use_safety.valid.json
pcs conformance run --suite workflow-profile
pcs conformance run --suite tool-use
pcs conformance run --suite multidomain
```

Valid tool-use trains live under `examples/tool-use-release/`, and invalid cases live under `examples/tool-use-release-invalid/`.

Valid computation trains live under `examples/computation-release/`, and invalid cases live under `examples/computation-release-invalid/` with one precise failure class per directory.

```bash
pcs conformance run --suite computation
```

See [artifact-registry.md](artifact-registry.md) and [semantic-check-policy.md](semantic-check-policy.md).
