# PCS-VA release candidate notes

Working-tree landing of Verifier Assurance Protocol (PCS-VA).

## Released artifact classes (RC)

Treat merged `*.v1` schemas as immutable after merge:

1. `VerifierProfile.v1`
2. `VerificationResult.v1`
3. `RewardEvidenceEnvelope.v1`
4. `OptimizationCampaignManifest.v1`
5. `AdjudicationRecord.v1`
6. `VerifierAssuranceReport.v1`

Shared defs: `schemas/verifier_assurance.defs.json`.

## Acceptance checklist

- [x] Six artifacts + defs
- [x] Python schema/semantics/CLI/report builder
- [x] Fixtures valid/invalid with manifests
- [x] Conformance suite `verifier-assurance`
- [x] Rust/TS schema maps + semantic validators
- [x] Docs: ownership, baseline, protocol, semantic-rules, cli, non-claims, migration, threat-model
- [x] Producer conformance directory
- [x] `VerificationResult.v0` untouched
- [x] Public surface limited to the six planned artifacts (no half-baked OVK pin types)

## Downstream

OVK/LabTrust: vendor schemas via [../downstream-schema-sync.md](../downstream-schema-sync.md); emit digests, null config slots, and typed decisions as in [../verifier-assurance/protocol.md](../verifier-assurance/protocol.md). See [../verifier-assurance/migration.md](../verifier-assurance/migration.md) for coexistence with v0.
