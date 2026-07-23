# PF-Core runtime semantics (Phase 5 + Workstream C)

This document states the execution-observation and deny-path model, and how it
relates to proved Lean predicates versus trusted instrumentation.

## Scope

Phases 0–4 establish declared capabilities, declared effects, effect frames, and
trace safety. Phase 5 / Workstream C adds:

| Item | Lean | Status |
|------|------|--------|
| Observed effects | `ObservedEffect`, separated soundness/completeness/attribution/authenticity | **Proved** undeclared-sensitive observation lemmas under observation soundness |
| Attested execution | `AttestedExecution` / `TrustedInstrumentation` | **Defined**; authenticity is an assumption switch, not proved from producer logs |
| Deny-path closedness | `EventSafeDenyClosed` | **Proved** refinement of `EventSafe` (declared footprint only) |
| `DenyClosedCertificate` | scaffolded | **Disabled** — runtime evidence insufficient for post-deny effect closure |
| Tenant projection isolation | `TenantProjectionIsolation` | **Proved** (single-trace observational) |
| Paired-execution NI | `PairedExecutionNonInterference` | **Scaffolding only** — not proved; not a release claim |

## 5.1 Observed effects and instrumentation (C1)

```lean
structure ObservedEffect where
  kind : Effect
  resource : Option Resource
  resultDigest : Option Hash
```

### Separated predicates

| Predicate | Meaning |
|-----------|---------|
| `ObservationSoundness` / `ObservationsAgree` | Every observation agrees with the declared action footprint |
| `ObservationCompleteness` | Every frame-sensitive *actual* effect appears in observations |
| `EffectAttribution` | Observations are attributed to the given action |
| `InstrumentationAuthenticity` | TCB / attestation assumption (`authenticated = true`) |
| `AttestedExecution` | Conjunction of the four above on an `InstrumentationContext` |
| `TrustedInstrumentation` | **Definitionally** `AttestedExecution` — **not** mere `ObservationsAgree` |

Agreement alone never establishes trust. Lemma
`observation_soundness_not_trusted_without_authenticity` records that shape.

**Trusted-boundary assumption:** Observation faithfulness is **not** proved from
untrusted producer logs. Discharge requires:

- trusted runtime instrumentation in the TCB, or
- an external attestation that binds observation digests to the transition.

Documented in `assumptions.md`. Primary lemmas:

- `accepted_transition_no_undeclared_sensitive_observation` (needs soundness)
- `attested_execution_no_undeclared_sensitive_observation` (full trusted context)

Under observation soundness and `ActionEffectsInFrame`, an accepted allow
transition cannot carry an observed `write`, `network`, `externalMessage`,
`codeExecution`, or `stateChange` absent from the declared frame.

Runtime mirror: `pcs_core.pf_core_runtime.validate_observed_effects_agree`
mirrors **`ObservationsAgree` / `ObservationSoundness` only**. Callers must still
attest instrumentation authenticity separately before claiming
`TrustedInstrumentation`.

## 5.2 Deny-path closedness (C2)

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

**`DenyClosedCertificate`:** scaffolded and **disabled**. Declared-footprint
refinement is proved; post-deny runtime closure of tool/mutation/network/message/
code/release/state/delegation effects is **not** yet supported by runtime evidence.
Do not issue a public deny-closed certificate claim. See
`schemas/pf_core.certificate_mode_status.json` `scaffolded_modes`.

Runtime mirror: `validate_event_safe_deny_closed`.

## 5.3 Naming: TenantProjectionIsolation vs NonInterference (C3)

| Name | Meaning | Status |
|------|---------|--------|
| `TenantProjectionIsolation` | Single-trace low/high projection isolation | **Proved** |
| `NonInterference` (Lean abbrev) | Compatibility alias of the above | Alias only |
| `PairedExecutionNonInterference` | Paired executions + scheduler + timing assumptions | **Unproved scaffolding** |

User-facing material must prefer **TenantProjectionIsolation** for the current
property. No stable certificate or public claim may use the bare phrase
“non-interference” without naming which formal predicate is meant.

CLI flag `--non-interference` remains for compatibility and checks
`TenantProjectionIsolation`.

See `non-interference.md` and `lean/PFCore/PairedExecution.lean`.

## What is not claimed

- Completeness of observations without authenticity / attestation
- That `ObservationsAgree` equals `TrustedInstrumentation`
- Paired-execution non-interference under adversarial schedulers
- Covert channels or timing leaks
- Automatic deny-path suppression / `DenyClosedCertificate` without runtime evidence
- Full post-deny effect freedom beyond declared footprints
