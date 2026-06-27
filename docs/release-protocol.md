# Release protocol artifacts

PCS v0.1 adds versioned **release**, **handoff**, and **validation** artifacts on top of the core science-claim chain. Downstream repositories consume these types from pcs-core without local variants.

## Schemas

| Artifact | Schema file |
|----------|-------------|
| `ReleaseManifest.v0` | `schemas/ReleaseManifest.v0.schema.json` |
| `HandoffManifest.v0` | `schemas/HandoffManifest.v0.schema.json` |
| `ReleaseChainValidationResult.v0` | `schemas/ReleaseChainValidationResult.v0.schema.json` |
| `ArtifactRegistry.v0` | `schemas/ArtifactRegistry.v0.schema.json` |
| `ComponentReleaseFragment.v0` | `schemas/ComponentReleaseFragment.v0.schema.json` |
| `WorkflowProfile.v0` | `schemas/WorkflowProfile.v0.schema.json` |
| `ToolUseTrace.v0` / `ToolUseCertificate.v0` | `schemas/ToolUseTrace.v0.schema.json`, `schemas/ToolUseCertificate.v0.schema.json` |

## Example fixtures

| Valid examples | Invalid examples |
|----------------|------------------|
| `examples/release_manifest.valid.json` | `examples/invalid_release_manifest_placeholder_commit.json` |
| `examples/handoff_manifest.valid.json` | `examples/invalid_handoff_manifest_missing_input_hash.json` |
| `examples/release_chain_validation_result.valid.json` | `examples/invalid_release_chain_validation_failed_status.json` |

```bash
pcs validate examples/release_manifest.valid.json
pcs examples check
```

## Artifact registry

Registry entries record **schema owner** (`pcs-core`) separately from **runtime producer** and allowed producers. Semantic checks are structured objects with `severity` and `responsible_component`.

```bash
pcs registry list
pcs registry explain HandoffManifest.v0
pcs registry audit
pcs registry validate examples/artifact_registry.valid.json
```

See [artifact-registry.md](artifact-registry.md) and [semantic-check-policy.md](semantic-check-policy.md).

## Shared hash vectors

Cross-language vectors live under `test_vectors/hash/`:

```bash
pcs shared-hash-vectors verify
```

Per-language vectors remain under `python/tests/hash_vectors/`.

## Status and migration

```bash
pcs explain-status ProofChecked
pcs check-status-transition old.json new.json
pcs migrate --from v0 --to v0 examples/runtime_receipt.valid.json
```

See [versioning.md](versioning.md), [migration-policy.md](migration-policy.md), [status-transition-policy.md](status-transition-policy.md).

## LabTrust release chain fixtures

Committed under `examples/labtrust-release/`:

| File | Type |
|------|------|
| `release_manifest.v0.json` | `ReleaseManifest.v0` |
| `handoff_manifest.*.v0.json` | `HandoffManifest.v0` (per stage) |
| `release_chain_validation_result.v0.json` | `ReleaseChainValidationResult.v0` |
| `labtrust_release_fragment.json` | `ComponentReleaseFragment.v0` |
| `RELEASE_FIXTURE_MANIFEST.json` | Legacy manifest (hashes + producer commits) |

`release_manifest.v0.json` is derived from `RELEASE_FIXTURE_MANIFEST.json` (same artifact hashes and producer commits). Regenerate after a full chain promotion:

```bash
just materialize-labtrust-protocol
```

Further detail appears in [labtrust-release-fixtures.md](labtrust-release-fixtures.md).

## Multi-domain workflows

`WorkflowProfile.v0` maps a domain onto the shared PCS trust loop. LabTrust QC release uses the default 30-check catalog; tool-use and computation workflows use profile-scoped validation results.

```bash
just materialize-protocol
pcs validate-release-chain examples/labtrust-release/
pcs validate-release-chain examples/tool-use-release/
pcs validate-release-chain examples/computation-release/
pcs conformance run --suite workflow-profile
pcs conformance run --suite tool-use
pcs conformance run --suite computation
pcs conformance run --suite multidomain
```

Workflow profiles are documented in [workflow-profiles.md](workflow-profiles.md), and formal checks appear in [lean-trust-kernel.md](lean-trust-kernel.md).

## Conformance

```bash
pcs conformance run --suite all
pcs conformance run --suite release-chain
pcs conformance run --suite handoff-manifest
pcs conformance run --suite all --json   # validates as ConformanceReport.v0
```

The suite index is listed in [../conformance/README.md](../conformance/README.md).

## Release-mode rules

Release-mode validation requires real 40-character git commits on all pins, rejects `local_dev` and all-zero commits, rejects placeholder commit patterns such as `aaaa` and `bbbb`, requires `sha256` on every artifact entry in `Validated` release manifests, and requires `sha256` on every `input_artifacts` entry in `Validated` handoffs.
