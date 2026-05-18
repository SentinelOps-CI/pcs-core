# PCS Phase 2 protocol substrate

Phase 2 moves pcs-core from schemas + fixtures to a **versioned protocol layer** that downstream repos consume without local variants.

## PR 1: release and handoff protocol artifacts

### Schemas

| Artifact | Schema |
|----------|--------|
| `ReleaseManifest.v0` | `schemas/ReleaseManifest.v0.schema.json` |
| `HandoffManifest.v0` | `schemas/HandoffManifest.v0.schema.json` |
| `ReleaseChainValidationResult.v0` | `schemas/ReleaseChainValidationResult.v0.schema.json` |

### Examples

| Valid | Invalid |
|-------|---------|
| `examples/release_manifest.valid.json` | `examples/invalid_release_manifest_placeholder_commit.json` |
| `examples/handoff_manifest.valid.json` | `examples/invalid_handoff_manifest_missing_input_hash.json` |
| `examples/release_chain_validation_result.valid.json` | `examples/invalid_release_chain_validation_failed_status.json` |

```bash
pcs validate examples/release_manifest.valid.json
pcs examples check
```

Builders: `pcs_core.protocol_fixtures`.

## PR 2: artifact registry

| Artifact | Schema |
|----------|--------|
| `ArtifactRegistry.v0` | `schemas/ArtifactRegistry.v0.schema.json` |
| `ComponentReleaseFragment.v0` | `schemas/ComponentReleaseFragment.v0.schema.json` |

Registry entries distinguish **schema_owner** (`pcs-core`) from **runtime_producer** and **allowed_runtime_producers**. Semantic checks are structured objects with `severity` and `responsible_component`.

```bash
pcs registry list
pcs registry explain HandoffManifest.v0
pcs registry audit
pcs registry validate examples/artifact_registry.valid.json
pcs registry check-artifact examples/labtrust-release/trace_certificate.json
```

Docs: [artifact-registry.md](artifact-registry.md), [semantic-check-policy.md](semantic-check-policy.md).

## PR 3: shared canonical hash vectors

Cross-language vectors under `test_vectors/hash/`:

```bash
pcs shared-hash-vectors verify
just shared-hash-vectors-verify
```

Legacy per-language vectors remain under `python/tests/hash_vectors/`.

## PR 4: migration and status policy

```bash
pcs explain-status ProofChecked
pcs check-status-transition old.json new.json
pcs migrate --from v0 --to v0 examples/runtime_receipt.valid.json
```

Docs: [versioning.md](versioning.md), [migration-policy.md](migration-policy.md), [status-transition-policy.md](status-transition-policy.md).

## PR 5: LabTrust release chain protocol artifacts

Committed under `examples/labtrust-release/`:

| File | Type |
|------|------|
| `release_manifest.v0.json` | `ReleaseManifest.v0` |
| `handoff_manifest.runtime_to_certificate.v0.json` | `HandoffManifest.v0` |
| `handoff_manifest.certificate_to_bundle.v0.json` | `HandoffManifest.v0` |
| `handoff_manifest.bundle_to_verifier.v0.json` | `HandoffManifest.v0` |
| `handoff_to_pf.json` | PF `--handoff` alias (same as bundle-to-verifier handoff) |
| `handoff_manifest.signed_bundle_to_memory.v0.json` | `HandoffManifest.v0` |
| `release_chain_validation_result.v0.json` | `ReleaseChainValidationResult.v0` |
| `labtrust_release_fragment.json` | `ComponentReleaseFragment.v0` |

`release_manifest.v0.json` is derived from `RELEASE_FIXTURE_MANIFEST.json` (same artifact hashes and producer commits). Each release-chain check includes `registry_check_refs` linking to registry semantic checks.

Regenerate after a full chain promotion (writes validation result first, then manifest digest pin):

```bash
just materialize-labtrust-protocol
```

`release_chain_validation_result.v0.json` is built from the live 30-check catalog with `checked_at` pinned to `RELEASE_FIXTURE_MANIFEST.json` `generated_at` so manifests and hash vectors stay stable.

## Protocol conformance suite

```bash
pcs conformance run --suite all
pcs conformance run --suite handoff-manifest
pcs conformance run --suite release-chain
```

Downstream repos can run subsets from `conformance/` (see [conformance/README.md](../conformance/README.md)).

Integration tests: `pytest tests/test_protocol_conformance.py` (also `just protocol-conformance`).

## Release-mode semantics (protocol artifacts)

- Real 40-character git commits on all pins
- No `local_dev`
- No zero commits
- No `aaaa`/`bbbb`/… pattern placeholders
- `Validated` release manifests require `sha256` on every artifact entry
- `Validated` handoffs require `sha256` on every `input_artifacts` entry
