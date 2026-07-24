# ADR: Verifier Assurance ownership (PCS-VA-00)

## Status

Accepted for the Verifier Assurance Protocol (PCS-VA). Public surface is the six `*.v1` artifact family.

## Context

Producers outside pcs-core (OVK checkers, LabTrust exporters, optimization harnesses, adjudication workflows) need portable, hashable assurance **records**. pcs-core already owns schemas, Canonical JSON hashing, the artifact registry, and conformance. Execution, training, and private partner workflows must stay outside PCS.

## Decision

| Owner | Owns |
|-------|------|
| **pcs-core (PCS)** | Portable Verifier Assurance **records**: schemas, digests, semantic validation, offline report construction/verification, CLI, cross-language parity, conformance fixtures |
| **OVK** | Checker **invocation**, implementation binaries, runtime configuration applied at check time; pins PCS schemas (never forks); emits `VerifierProfile.v1` and `VerificationResult.v1` |
| **LabTrust** | Domain **producers** of evidence and reward envelopes for lab workflows |
| **PF-Core** | Small machine-checked **trace predicates** and Lean trust kernel — not campaign stats or VA orchestration |
| **PCS excludes** | Environment execution, RL/training loops, LLM judges, attack runners, private adjudication rationale storage |

## Six-artifact family

| Artifact type | Role |
|---------------|------|
| `VerifierProfile.v1` | Immutable verifier identity + configuration digests |
| `VerificationResult.v1` | Portable decision record (distinct from `VerificationResult.v0`) |
| `RewardEvidenceEnvelope.v1` | Reward composition + claim/result binding |
| `OptimizationCampaignManifest.v1` | Campaign declaration, access class, cohorts |
| `AdjudicationRecord.v1` | Labels, votes, protected rationale **commitment** only |
| `VerifierAssuranceReport.v1` | Deterministic aggregate metrics + CI declarations |

Optional opaque `invocation_ref` on `VerificationResult.v1` may bind a producer-local run id and digest. That field is **not** a registered PCS artifact type.

## Shared conventions

- Nested `integrity` follows the ArtifactIntegrity.v1 field pattern; `signature_or_digest` is forbidden on VA roots.
- Rates, rewards, and CI bounds use decimal **strings** under Canonical JSON v1 release policy.
- Shared defs live in `schemas/verifier_assurance.defs.json`.
- Authoritative fixtures: `examples/verifier_assurance/`.
- Producer dialect gate: `benchmarks/verifier_assurance_conformance/`.
- Conformance suite: `pcs conformance run --suite verifier-assurance`.

## Consequences

- OVK and LabTrust must pin these schema versions (git commit or package version) and validate emitted packs with `pcs validate` / the VA CLI.
- `VerificationResult.v0` remains immutable for LabTrust/PF release-chain consumers.

## Related

- [baseline.md](baseline.md)
- [protocol.md](protocol.md)
- [non-claims.md](non-claims.md)
- [../trust-model.md](../trust-model.md)
- [../downstream-schema-sync.md](../downstream-schema-sync.md)
