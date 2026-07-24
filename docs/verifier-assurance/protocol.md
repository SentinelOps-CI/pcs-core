# Verifier Assurance Protocol

PCS-VA defines six portable `*.v1` assurance artifacts owned by pcs-core. Producers (OVK, LabTrust, optimization harnesses, adjudication workflows) emit records; pcs-core validates schemas, digests, semantics, and offline report rebuilds.

This family coexists with the v0.1 core protocol (`*.v0`). It does **not** replace LabTrust/PF release-chain artifacts. In particular, `VerificationResult.v1` is distinct from frozen `VerificationResult.v0` — there is no auto-upgrade.

## Artifact family

| Artifact | Schema | Typical producer |
|----------|--------|------------------|
| `VerifierProfile.v1` | `schemas/VerifierProfile.v1.schema.json` | OVK |
| `VerificationResult.v1` | `schemas/VerificationResult.v1.schema.json` | OVK |
| `RewardEvidenceEnvelope.v1` | `schemas/RewardEvidenceEnvelope.v1.schema.json` | LabTrust / harness |
| `OptimizationCampaignManifest.v1` | `schemas/OptimizationCampaignManifest.v1.schema.json` | Optimization harness |
| `AdjudicationRecord.v1` | `schemas/AdjudicationRecord.v1.schema.json` | Adjudication workflow |
| `VerifierAssuranceReport.v1` | `schemas/VerifierAssuranceReport.v1.schema.json` | pcs-core offline builder |

Shared definitions: `schemas/verifier_assurance.defs.json`.

## Integrity

Nested `integrity` follows ArtifactIntegrity.v1 fields (`canonicalization_version`, `artifact_digest`, optional `signature`). `signature_or_digest` is forbidden on VA roots.

## Numbers

Rates and rewards use decimal **strings** (Canonical JSON v1 release policy; no JSON floats).

## Opaque invocation pins

`VerificationResult.v1` may include optional `invocation_ref` with `invocation_id` and `invocation_digest` only. Producers may use this to bind local run evidence; pcs-core does not register a separate InvocationRecord artifact type.

## Validation surfaces

| Surface | Command / API |
|---------|----------------|
| Schema registry | `pcs schema check` |
| Single artifact | `pcs validate <file>` or typed VA CLI (see [cli.md](cli.md)) |
| Semantic rules | Python / Rust / TypeScript validators (see [semantic-rules.md](semantic-rules.md)) |
| Conformance | `pcs conformance run --suite verifier-assurance` |
| Shared digests | `pcs shared-hash-vectors verify` (six VA vector files under `test_vectors/hash/`) |

## Layout

| Path | Role |
|------|------|
| `examples/verifier_assurance/valid/` | Positive fixtures (including multi-file report rebuild) |
| `examples/verifier_assurance/invalid/` | Negative fixtures with `manifest.json` expected codes |
| `examples/verifier_assurance/*.valid.json` | Flat pin samples for profile/result |
| `benchmarks/verifier_assurance_conformance/` | Producer dialect rejection gate |
| `conformance/verifier-assurance/` | Suite documentation index |

## Non-claims

See [non-claims.md](non-claims.md) and [ownership.md](ownership.md).
