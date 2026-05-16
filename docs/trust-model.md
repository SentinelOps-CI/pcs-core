# PCS Trust Model (v0.1)

PCS artifacts are **evidence containers**, not automatic truth claims. Trust is layered and must be displayed separately.

## Layers

| Layer | Meaning | Typical source |
|-------|---------|----------------|
| `runtime_observed` | A run occurred; hashes bind inputs/outputs/trace | LabTrust-Gym `RuntimeReceipt.v0` |
| `certificate_checked` | Temporal (or other) checker attests trace vs spec | CertifyEdge `TraceCertificate.v0` |
| `formally_checked` | Proof or formal verification completed | Provability Fabric (deferred depth in v0.1) |
| `human_reviewed` | Assumptions or claims reviewed by a person | AssumptionSet, ClaimArtifact status |
| `empirically_measured` | Measured data, not proof | External datasets (out of v0.1 scope) |
| `unchecked_advisory` | Commentary without verification | Docs, UI notes |

## What v0.1 does not guarantee

The LabTrust-Gym demonstration is a **proof-carrying simulation workflow**. It is not:

- Clinical validation
- Production medical certification
- A guarantee about a real hospital laboratory

Domain assumptions must state simulation scope explicitly.

## Hash binding

- `RuntimeReceipt.v0` binds `events_hash`, `policy_hash`, `trace_hash`.
- `TraceCertificate.v0` references the same `trace_hash` and `spec_hash`.
- `ScienceClaimBundle.v0` semantic validation rejects receipt/certificate trace hash mismatch.

## Signatures

v0.1 includes `signature_or_digest` on artifacts. Full signing services are out of scope; downstream repos (e.g. Provability Fabric) attach signatures after verification.

## Staleness

Status `Stale` marks artifacts superseded by newer commits, specs, or traces. Consumers must not treat stale certificates as current evidence.
