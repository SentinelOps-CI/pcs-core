# PCS protocol (v0.1)

Proof-Carrying Science (PCS) is a cross-repository artifact protocol. **pcs-core** defines artifact shapes, status values, validation rules, and canonical hashing. Consumer repositories validate against these definitions; they do not publish competing schema versions.

## Core artifacts

| Artifact | Schema |
|----------|--------|
| AssumptionSet.v0 | `schemas/AssumptionSet.v0.schema.json` |
| SourceSpan.v0 | `schemas/SourceSpan.v0.schema.json` |
| ClaimArtifact.v0 | `schemas/ClaimArtifact.v0.schema.json` |
| RuntimeReceipt.v0 | `schemas/RuntimeReceipt.v0.schema.json` |
| TraceCertificate.v0 | `schemas/TraceCertificate.v0.schema.json` |
| EvidenceBundle.v0 | `schemas/EvidenceBundle.v0.schema.json` |
| ScienceClaimBundle.v0 | `schemas/ScienceClaimBundle.v0.schema.json` |
| VerificationResult.v0 | `schemas/VerificationResult.v0.schema.json` |
| SignedScienceClaimBundle.v0 | `schemas/SignedScienceClaimBundle.v0.schema.json` |

Release, workflow, and benchmark extensions are documented in [release-protocol.md](release-protocol.md) and [benchmarks.md](benchmarks.md).

## `schema_version` vs artifact class

`schema_version` is the **PCS protocol version**, not the artifact class. For v0.1, every artifact uses `schema_version: "v0"` (including `SignedScienceClaimBundle.v0`).

The artifact class comes from the schema file, JSON Schema `title`, and required ID fields (`bundle_id`, `receipt_id`, `signed_bundle_id`, and so on). Do not encode the class name in `schema_version`.

Mirror schemas as read-only copies only: [downstream-schema-sync.md](downstream-schema-sync.md).

## Producer metadata

Every major artifact includes:

| Field | Requirement |
|-------|-------------|
| `schema_version` | `"v0"` for v0.1 |
| `created_at` | ISO 8601 UTC |
| `producer`, `producer_version` | Emitting component |
| `source_repo`, `source_commit` | Git provenance (40-char SHA for releases) |
| `status` | Registry-allowed value |
| `signature_or_digest` | `sha256:<64 hex>` canonical digest |

## Guarantee types

Rendered claims and public pages must use exactly one label per evidence item:

- `formally_checked`
- `certificate_checked`
- `runtime_observed`
- `empirically_measured`
- `human_reviewed`
- `unchecked_advisory`

See [trust-model.md](trust-model.md).

## Validate and hash

```bash
pcs validate path/to/artifact.json
pcs hash path/to/artifact.json
```

Validation uses JSON Schema Draft 2020-12 plus semantic rules (trace hash alignment, assumption sets, release-mode provenance). Details: [hash-canonicalization.md](hash-canonicalization.md).

## Language bindings

| Language | Integration |
|----------|-------------|
| Python | `pip install -e python/` → `pcs` CLI and `pcs_core.validate` |
| Rust | `pcs-core` crate in `rust/` |
| TypeScript | `@pcs/core` in `typescript/` |
| Other | Copy `schemas/*.schema.json`; pin by git tag |

## Adding a future artifact type

1. Add `NewArtifact.v1.schema.json` under `schemas/` (do not mutate frozen `*.v0` schemas in place).
2. Add valid and invalid examples under `examples/`.
3. Extend Python, Rust, TypeScript, and Lean bindings.
4. Document hashing and release notes.
5. v0.1 consumers continue using `*.v0` unchanged.

## Related documentation

| Document | Topic |
|----------|--------|
| [README.md](README.md) | Documentation index |
| [release-protocol.md](release-protocol.md) | Release manifests and handoffs |
| [workflow-profiles.md](workflow-profiles.md) | Multi-domain workflows |
| [artifact-lifecycle.md](artifact-lifecycle.md) | Status flows |
| [downstream-schema-sync.md](downstream-schema-sync.md) | Vendoring policy |
