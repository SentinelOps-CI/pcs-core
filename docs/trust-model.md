# Trust model (v0.1)

PCS artifacts function as **evidence containers** that carry attestations and measurements, and each container requires an explicit guarantee label in user interfaces and exports because trust is layered by design.

## Guarantee types

| Type | Meaning | Typical source |
|------|---------|----------------|
| `runtime_observed` | A run occurred and hashes bind inputs, outputs, and trace | `RuntimeReceipt.v0` |
| `certificate_checked` | A checker attests the trace against a specification | `TraceCertificate.v0` |
| `formally_checked` | Proof or formal verification completed | Provability Fabric and the Lean kernel |
| `human_reviewed` | A person reviewed assumptions or claims | `AssumptionSet` and `ClaimArtifact` |
| `empirically_measured` | Measured data without formal proof | External datasets outside v0.1 scope |
| `unchecked_advisory` | Commentary without verification | Documentation and user interface notes |

Protocol rules appear in [protocol.md](protocol.md).

## Scope limits in v0.1

The LabTrust demonstration implements a **proof-carrying simulation workflow** aimed at integration testing and protocol education, and the workflow targets simulated hospital-lab scenarios with explicit domain assumptions instead of clinical validation, production medical certification, or claims about real hospital operations.

## Hash binding

`RuntimeReceipt.v0` binds `events_hash`, `policy_hash`, and `trace_hash`. `TraceCertificate.v0` references the same `trace_hash` and `spec_hash`. `ScienceClaimBundle.v0` validation enforces alignment between receipt and certificate trace hashes.

The canonical algorithm is documented in [hash-canonicalization.md](hash-canonicalization.md).

## Signatures

v0.1 includes `signature_or_digest` on artifacts, while full signing infrastructure remains outside the initial release and downstream verifiers attach signatures after checks complete.

## Staleness

Status `Stale` marks artifacts superseded by newer commits, specifications, or traces, and consumers should treat stale certificates as historical evidence only.

Status policy appears in [artifact-lifecycle.md](artifact-lifecycle.md) and [status-transition-policy.md](status-transition-policy.md).
