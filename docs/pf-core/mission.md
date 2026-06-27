# PF-Core mission

PF-Core is the minimal trusted action-trace kernel inside PCS. PCS defines evidence containers and release-chain artifacts; PF-Core defines the formal semantics of agentic actions, contracted traces, and trace-level safety preservation.

## Relationship to PCS

PF-Core is a **sub-protocol** inside PCS, not a replacement for it.

| Layer | Responsibility |
|-------|----------------|
| PCS | Artifact envelopes, release chains, hash canonicalization, cross-repo conformance |
| PF-Core | Principals, capabilities, actions, events, traces, contracts, trace-level safety |
| Runtime adapters | Untrusted producers that compile observations into PF-Core artifacts |

PCS v0.1 release-chain artifacts (`RuntimeReceipt.v0`, `TraceCertificate.v0`, `ScienceClaimBundle.v0`, and related types) remain authoritative for the LabTrust demonstration workflow. PF-Core adds a parallel trusted path for agentic action traces.

## Current Lean scope

Two theorem families coexist in `lean/` and must not be conflated in documentation or claim language.

### PCS release-envelope consistency (`lean/PCS/`)

The existing Lean package under `lean/PCS/` proves **release-envelope consistency** properties (trace hash alignment, verification admission, signed bundle coherence). Describe this family as:

> Release-envelope consistency theorem family

It covers PCS bundle and certificate coherence, not per-event agent authorization.

### PF-Core trace-safety (`lean/PFCore/`)

The PF-Core namespace (`lean/PFCore/`, `lake build PFCore`) defines agentic primitives and trace-safety predicates:

- `EventSafe`, `TraceSafe`, and decidable counterparts `eventSafeD`, `traceSafeD`
- `HandoffSafe` and non-expanding delegation
- Contract structures and trace-safety invariant preservation (conservative)
- Concrete per-trace proofs in `lean/PFCore/Generated/` checked by `pcs pf-core lean-check`

Describe this family as:

> PF-Core trace-safety theorem family

Do not describe PCS release-envelope theorems as agent safety theorems.

## Explicit artifact typing

No PF-Core trusted artifact may be inferred heuristically. Every trusted PF-Core artifact must declare:

```json
"artifact_type": "PFCoreTrace.v0"
```

(or the matching type for the artifact class). The PCS validator accepts explicit `artifact_type` only when the JSON Schema also requires the same constant.

## Status vs claim class

PCS `status` fields describe workflow lifecycle state. PF-Core **claim class** describes what kind of assurance was actually obtained. These must not be conflated. See [claim-boundary.md](claim-boundary.md).
