# PF-Core runtime semantics (Phase 5)

This document states the Phase 5 execution-observation and deny-path model, and
how it relates to proved Lean predicates versus trusted instrumentation.

## Scope

Phases 0–4 establish declared capabilities, declared effects, effect frames, and
trace safety. Phase 5 adds:

| Item | Lean | Status |
|------|------|--------|
| Observed effects | `ObservedEffect`, `TrustedInstrumentation` | **Proved** undeclared-sensitive observation lemmas under instrumentation assumption |
| Deny-path closedness | `EventSafeDenyClosed` | **Proved** refinement of `EventSafe` (optional) |
| Tenant projection isolation | `TenantProjectionIsolation` | **Proved** (renamed observational property) |
| Paired-execution NI | `PairedExecutionNonInterference` | **Scaffolding only** — not proved; not a release claim |

## 5.1 Observed effects and instrumentation

```lean
structure ObservedEffect where
  kind : Effect
  resource : Option Resource
  resultDigest : Option Hash
```

Agreement (`ObservationsAgree` / `TrustedInstrumentation`) requires every
observed kind (and optional resource) to lie in the declared action footprint.

**Trusted-boundary assumption:** Observation faithfulness is **not** proved from
untrusted producer logs. Discharge requires:

- trusted runtime instrumentation in the TCB, or
- an external attestation that binds observation digests to the transition.

Documented in `assumptions.md`. Primary lemma:

`accepted_transition_no_undeclared_sensitive_observation`

Under `TrustedInstrumentation` and `ActionEffectsInFrame`, an accepted allow
transition cannot carry an observed `write`, `network`, `externalMessage`,
`codeExecution`, or `stateChange` absent from the declared frame.

Runtime mirror: `pcs_core.pf_core_runtime.validate_observed_effects_agree`
(callers must still attest instrumentation).

## 5.2 Deny-path closedness

Base `EventSafe` treats deny as vacuously safe. Optional refinement:

`EventSafeDenyClosed = EventSafe ∧ DenyPathClosed`

On deny, the declared action must have empty writes and no deny-path-forbidden
effects (`write`, `network`, `externalMessage`, `codeExecution`, `stateChange`).

Optional bundle properties (`DenyClosedBundle`):

| Property | Meaning |
|----------|---------|
| `NoToolInvocationAfterDenial` | Deny ⇒ empty observation list |
| `NoDelegatedAuthorityOnDeny` | Deny ⇒ no accompanying handoff |
| `DenyReasonConsistent` | Allow events must not carry a deny reason |

`TraceSafeDenyClosed` refines `TraceSafe` (`traceSafeDenyClosed_implies_traceSafe`).
Base `EventSafe` / `TraceSafe` remain unchanged.

Runtime mirror: `validate_event_safe_deny_closed`.

## 5.3 Naming: TenantProjectionIsolation vs NonInterference

| Name | Meaning | Status |
|------|---------|--------|
| `TenantProjectionIsolation` | Single-trace low/high projection isolation | **Proved** |
| `NonInterference` (Lean abbrev) | Compatibility alias of the above | Alias only |
| `PairedExecutionNonInterference` | Paired executions + scheduler + timing assumptions | **Unproved scaffolding** |

User-facing material must prefer **TenantProjectionIsolation** for the current
property. Reserve **NonInterference** for a future paired-execution theorem
family. CLI flag `--non-interference` remains for compatibility and checks
`TenantProjectionIsolation`.

See `non-interference.md` and `lean/PFCore/PairedExecution.lean`.

## What is not claimed

- Completeness of observations without trusted instrumentation / attestation
- Paired-execution non-interference under adversarial schedulers
- Covert channels or timing leaks
- Automatic deny-path suppression without deny-closed certificates
