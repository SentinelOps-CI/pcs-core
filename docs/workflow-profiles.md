# Workflow profiles (v0.1)

`WorkflowProfile.v0` describes how a **domain workflow** maps onto the shared PCS trust loop without encoding domain-specific ontologies in core schemas. Release fixtures: [release-protocol.md](release-protocol.md).

## Purpose

Downstream repos declare workflows in data, not hardcoded assumptions:

| Field | Role |
|-------|------|
| `workflow_id` | Stable identifier (`agent_tool_use.safety_v0`, `labtrust.qc_release_v0.1`). |
| `domain` | Coarse domain label (`agent_tool_use`, `lab_science_simulation`). |
| `runtime_artifacts` | Artifact types produced at runtime before certification. |
| `certificate_artifacts` | Certificate types that attest runtime evidence. |
| `handoff_sequence` | Ordered `handoff_kind` values for the PCS handoff graph. |
| `required_registry_entries` | Artifact types that must appear in `ArtifactRegistry.v0`. |
| `required_admission_profile` | Scientific Memory admission profile id for import. |
| `status_policy` | Lifecycle constraints for the workflow. |
| `failure_modes` | Named failure classes consumers should handle. |
| `limitations_notice` | Non-goals and scope boundaries. |

## Examples

| Profile | Path |
|---------|------|
| LabTrust QC release | `examples/workflow_profiles/labtrust_qc_release.valid.json` |
| Agent tool-use safety | `examples/workflow_profiles/agent_tool_use_safety.valid.json` |
| Scientific computation reproducibility | `examples/workflow_profiles/scientific_computation_reproducibility.valid.json` |

## Tool-use policy hash convention

`ToolUseCertificate.v0.policy_hash` must equal the canonical digest of `{"policy_id": <ToolUseTrace.v0.policy_id>}`:

```python
from pcs_core.tool_use_validate import policy_hash_from_policy_id

policy_hash_from_policy_id("policy-no-secret-exfiltration-v0")
```

## Release manifest and Scientific Memory

`ReleaseManifest.v0` requires `workflow_profile_id` (same value as `validation_profile` for v0.1 fixtures). The tool-use train includes `scientific_memory_import_report.json` with `workflow_profile_id` and `workflow_profile_render_path` so SM consumers can surface the active workflow profile in rendered output.

## Release-chain coverage scoping

`ReleaseChainValidationResult.v0` includes `workflow_profile_id` for profile-scoped registry coverage. When omitted, coverage uses the LabTrust v0.1 profile scope.

## Conformance

```bash
pcs validate examples/workflow_profiles/agent_tool_use_safety.valid.json
pcs conformance run --suite workflow-profile
pcs conformance run --suite tool-use
pcs conformance run --suite multidomain
```

Valid tool-use train: `examples/tool-use-release/`.  
Invalid cases: `examples/tool-use-release-invalid/`.

Valid computation train: `examples/computation-release/`.  
Invalid cases: `examples/computation-release-invalid/` (one precise failure class per directory).

```bash
pcs conformance run --suite computation
```

See [artifact-registry.md](artifact-registry.md) and [semantic-check-policy.md](semantic-check-policy.md).
