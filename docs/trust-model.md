# Trust model (v0.1)

PCS artifacts are **evidence containers**, not automatic truth claims. Trust is layered; each layer must be labeled separately in UIs and exports.

## Guarantee types

| Type | Meaning | Typical source |
|------|---------|----------------|
| `runtime_observed` | A run occurred; hashes bind inputs, outputs, and trace | `RuntimeReceipt.v0` |
| `certificate_checked` | Checker attests trace against a spec | `TraceCertificate.v0` |
| `formally_checked` | Proof or formal verification completed | Provability Fabric, Lean kernel |
| `human_reviewed` | Person reviewed assumptions or claims | `AssumptionSet`, `ClaimArtifact` |
| `empirically_measured` | Measured data without formal proof | External datasets (out of v0.1 scope) |
| `unchecked_advisory` | Commentary without verification | Documentation, UI notes |

Protocol rules: [protocol.md](protocol.md).

## What v0.1 does not guarantee

The LabTrust demonstration is a **proof-carrying simulation workflow**. It is not clinical validation, production medical certification, or a claim about a real hospital laboratory. Domain assumptions must state simulation scope explicitly.

## Hash binding

- `RuntimeReceipt.v0` binds `events_hash`, `policy_hash`, `trace_hash`.
- `TraceCertificate.v0` references the same `trace_hash` and `spec_hash`.
- `ScienceClaimBundle.v0` validation rejects receipt and certificate trace hash mismatches.

Algorithm: [hash-canonicalization.md](hash-canonicalization.md).

## Signatures

v0.1 includes `signature_or_digest` on artifacts. Full signing infrastructure is out of scope; downstream verifiers attach signatures after checks complete.

## Staleness

Status `Stale` marks artifacts superseded by newer commits, specs, or traces. Consumers must not treat stale certificates as current evidence.

Status policy: [artifact-lifecycle.md](artifact-lifecycle.md), [status-transition-policy.md](status-transition-policy.md).
