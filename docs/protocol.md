# PCS protocol (v0.1)

Proof-Carrying Science (PCS) is a cross-repository artifact protocol, and **pcs-core** defines artifact shapes, status values, validation rules, and canonical hashing so consumer repositories validate against one shared definition set.

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

## Verifier Assurance family (`*.v1`)

pcs-core also owns the Verifier Assurance (PCS-VA) six-artifact family for portable verifier profiles, results, rewards, campaigns, adjudication commitments, and offline assurance reports. These use `schema_version` value `"v1"` and nested `integrity` (not root `signature_or_digest`). They coexist with the v0.1 core table above; `VerificationResult.v1` does not replace `VerificationResult.v0`.

See [verifier-assurance/protocol.md](verifier-assurance/protocol.md), [verifier-assurance/ownership.md](verifier-assurance/ownership.md), and [releases/verifier-assurance-rc.md](releases/verifier-assurance-rc.md).

## `schema_version` and artifact class

The `schema_version` field records the **PCS protocol version**, while the artifact class is identified separately through the schema file, the JSON Schema `title`, and required identifier fields such as `bundle_id`, `receipt_id`, and `signed_bundle_id`.

Every v0.1 artifact uses `schema_version` value `"v0"`, including `SignedScienceClaimBundle.v0`, and the class name belongs in those identifier fields and schema metadata alone.

Mirror schemas as read-only copies following [downstream-schema-sync.md](downstream-schema-sync.md).

## Producer metadata

Every major artifact includes the fields below.

| Field | Requirement |
|-------|-------------|
| `schema_version` | `"v0"` for v0.1 |
| `created_at` | ISO 8601 UTC |
| `producer`, `producer_version` | Emitting component |
| `source_repo`, `source_commit` | Git provenance with 40-character SHA for releases |
| `status` | Registry-allowed value |
| `signature_or_digest` | `sha256:<64 hex>` canonical digest |

## Guarantee types

Rendered claims and public pages must apply exactly one label per evidence item from the list below.

- `formally_checked`
- `certificate_checked`
- `runtime_observed`
- `empirically_measured`
- `human_reviewed`
- `unchecked_advisory`

Further explanation appears in [trust-model.md](trust-model.md).

## Validate and hash

```bash
pcs validate path/to/artifact.json
pcs hash path/to/artifact.json
```

Validation applies JSON Schema Draft 2020-12 together with semantic rules that cover trace hash alignment, assumption sets, and release-mode provenance, and the hashing algorithm is documented in [hash-canonicalization.md](hash-canonicalization.md).

## Language bindings

| Language | Integration |
|----------|-------------|
| Python | `pip install -e python/` provides the `pcs` CLI and `pcs_core.validate` |
| Rust | The `pcs-core` crate lives under `rust/` |
| TypeScript | The `@pcs/core` package lives under `typescript/` |
| Other | Copy `schemas/*.schema.json` and pin by git tag |

## Adding a future artifact type

Add `NewArtifact.v1.schema.json` under `schemas/` as a new file because frozen `*.v0` schemas remain immutable. Add valid and invalid examples under `examples/`. Extend Python, Rust, TypeScript, and Lean bindings. Document hashing and release notes. v0.1 consumers continue using `*.v0` unchanged.

## Related documentation

| Document | Topic |
|----------|--------|
| [README.md](README.md) | Documentation index |
| [release-protocol.md](release-protocol.md) | Release manifests and handoffs |
| [workflow-profiles.md](workflow-profiles.md) | Multi-domain workflows |
| [artifact-lifecycle.md](artifact-lifecycle.md) | Status flows |
| [downstream-schema-sync.md](downstream-schema-sync.md) | Vendoring policy |
| [verifier-assurance/protocol.md](verifier-assurance/protocol.md) | Verifier Assurance (PCS-VA) `*.v1` family |
