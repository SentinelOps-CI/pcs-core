# PCS artifact registry (v0.1)

The artifact registry is the canonical map from **artifact type** to schema file, producer, allowed statuses, required release fields, and semantic checks. Downstream repos must not invent local PCS schema variants; they consume this registry from pcs-core.

## Source of truth

| Artifact | Location |
|----------|----------|
| Machine-readable registry | `examples/artifact_registry.valid.json` |
| Registry builder | `python/pcs_core/registry_data.py` |
| Schema | `schemas/ArtifactRegistry.v0.schema.json` |

## CLI

```bash
pcs registry list
pcs registry explain TraceCertificate.v0
pcs registry validate examples/artifact_registry.valid.json
pcs registry check-artifact examples/labtrust-release/trace_certificate.json
```

## Registered artifact types

Core chain: `RuntimeReceipt.v0`, `TraceCertificate.v0`, `ScienceClaimBundle.v0`, `VerificationResult.v0`, `SignedScienceClaimBundle.v0`, supporting `AssumptionSet.v0`, `ClaimArtifact.v0`, `EvidenceBundle.v0`, `SourceSpan.v0`.

Protocol layer: `ReleaseManifest.v0`, `HandoffManifest.v0`, `ReleaseChainValidationResult.v0`, `ArtifactRegistry.v0`.

## Downstream sync

1. Pin pcs-core at the release tag.
2. Copy `examples/artifact_registry.valid.json` or call `pcs registry validate` on your mirror.
3. Use `pcs registry check-artifact` in CI for every release-mode artifact you publish.

See [artifact-lifecycle.md](artifact-lifecycle.md) and [status-transition-policy.md](status-transition-policy.md).
