# PF-Core trusted boundary

This document lists what PCS/PF-Core treats as trusted, untrusted, or assumed when interpreting PF-Core artifacts.

## Trusted (in-scope for PF-Core kernel claims)

| Component | Location | Trust basis |
|-----------|----------|-------------|
| PF-Core JSON schemas | `schemas/PFCore*.v0.schema.json` | Draft 2020-12 validation, `additionalProperties: false` |
| PF-Core artifact registry entries | `python/pcs_core/registry_data.py` | Protocol authority in pcs-core |
| Explicit `artifact_type` detection | `python/pcs_core/validate.py` | Schema-locked discriminator |
| Release-envelope Lean theorems | `lean/PCS/Theorems.lean` | Lean 4 proof check (`lake build PCS`) |
| PF-Core trace-safety Lean kernel | `lean/PFCore/` | Lean 4 proof check (`lake build PFCore`) |
| PF-Core claim-boundary linter | `python/pcs_core/pf_core_claims.py` | CI-enforced documentation scan |
| Lean theorem catalog (PCS trusted set) | `python/pcs_core/lean_catalog.py` | Audited against `lean/PCS/Theorems.lean` |
| Lean theorem catalog (PF-Core trusted set) | `python/pcs_core/lean_catalog.py` | Audited against `lean/PFCore/` |
| PF-Core lean-check deciders | `python/pcs_core/lean_check.py` | Aligned with PF-Core Lean predicates; uses explicit `principal.capabilities` only |
| Known capability catalog (Python) | `python/pcs_core/pf_core_runtime.py` | `CAPABILITY_CATALOG`, `validate_action_capabilities_known`, `validate_resource_scope` |
| Known capability catalog (Lean) | `lean/PFCore/Capability.lean`, `lean/PFCore/Action.lean` | `KnownCapability`, `KnownCapabilityEffect` on `ActionAdmissible`; no resource-pattern discharge |
| PF-Core concrete trace Lean proofs | `lean/PFCore/Generated/` (generated) | `lake env lean` on generated `concrete_trace_safe` theorem; certificate binds via `trace_hash`, `proof_term_hash`, `lean_environment_hash` |
| Python PF-Core semantic validation | `python/pcs_core/validate_pf_core.py` | Binds JSON artifacts to closed enums and direct-trace effect/capability rules before Lean codegen |
| Tool-use / witness hash alignment theorems | `lean/PCS/ToolUse.lean`, `lean/PCS/ComputationWitness.lean` | Promoted to trusted PCS catalog (Stage 4) |
| Role → capability expansion | `python/pcs_core/pf_core_runtime.py` | Compiler expands roles; lean-check requires explicit capabilities on traces |
| PF-Core no-sorry audit | `python/pcs_core/lean_check.py` | Scans `lean/PFCore/` for forbidden tokens |

## PCS release-envelope path (Choice B — permanent)

PCS `pcs pcs-envelope check` (and deprecated `pcs lean-check`) evaluate **release-envelope consistency** only (`ProofObligation.v0` against `lean/PCS/Theorems.lean`). This path is **envelope-only** and does not generate per-trace Lean proof terms or emit PF-Core `LeanKernelChecked` claims. Full PCS Lean term generation for arbitrary traces remains out of scope unless a future PCS-Lean stage is added.

PF-Core trace kernel assurance requires `pcs pf-core lean-check --trace`.

## Untrusted (must not produce LeanKernelChecked claims)

| Component | Reason |
|-----------|--------|
| Heuristic artifact type detection | Order-dependent field inference |
| Python obligation evaluators without Lean term generation | Predicate checks only unless concrete Lean proof succeeds |
| Runtime producers (`AgentRuntime`, adapters) | External code; evidence not proof |
| Deferred registry semantic checks | Explicitly skipped obligations |
| Documentation and examples | Organizational; scanned but not formally verified |
| LLM or network-dependent compilation | Forbidden in PF-Core runtime compiler |
| `pcs pf-core lean-check --skip-build` or `--skip-lean-proof` | Emits `RuntimeChecked`, not `LeanKernelChecked` |

## Assumed (explicit, not proved by PF-Core)

See [assumptions.md](assumptions.md). Assumptions must appear in `AssumptionSet.v0` or PF-Core certificate assumption refs before any external claim.

## PCS release-envelope path (permanent envelope-only framing)

PCS `pcs pcs-envelope check` (and deprecated `pcs lean-check`) validates `ProofObligation.v0` release-envelope consistency against the PCS theorem catalog. It emits `ProofChecked` on `LeanCheckResult.v0` when obligations pass; this is **not** PF-Core `LeanKernelChecked` trace safety.

There is no silent upgrade from envelope checks to per-trace Lean kernel proofs. PF-Core kernel assurance requires `pcs pf-core lean-check --trace …` with concrete generated proof terms (see [generated-proofs.md](generated-proofs.md)).

## PCS release-envelope path (permanent envelope-only scope)

PCS `pcs pcs-envelope check` (formerly `pcs lean-check`) validates **release-envelope consistency** only:

- Proof obligations against `lean/PCS/Theorems.lean`
- Emits `ProofChecked` on `LeanCheckResult.v0`; never `LeanKernelChecked`
- No per-trace PF-Core Lean term generation unless a future **Stage PCS-Lean** is added

PF-Core kernel assurance remains exclusively on `pcs pf-core lean-check --trace …`.

See `docs/pf-core/generated-proofs.md` for gitignored `lean/PFCore/Generated/` regeneration.

No PF-Core trusted Lean file may contain `sorry`, `admit`, `axiom`, or `unsafe` unless listed here.

| File | Exception | Rationale |
|------|-----------|-----------|
| (none) | — | Stage 3: no exceptions |

## Trusted file list (Stage 3)

### Documentation and Python

- `docs/pf-core/*.md`
- `python/pcs_core/registry_data.py` (PF-Core entries)
- `python/pcs_core/pf_core_claims.py`
- `python/pcs_core/lean_catalog.py`
- `python/pcs_core/lean_check.py`
- `python/pcs_core/pf_core_runtime.py`

### PCS release-envelope Lean

- `lean/PCS/ReleaseChain.lean`
- `lean/PCS/Theorems.lean`

### PF-Core trace-safety Lean (`lake build PFCore`)

- `lean/PFCore/Basic.lean`
- `lean/PFCore/Principal.lean`
- `lean/PFCore/Capability.lean`
- `lean/PFCore/Resource.lean`
- `lean/PFCore/Action.lean`
- `lean/PFCore/Event.lean`
- `lean/PFCore/Trace.lean`
- `lean/PFCore/Handoff.lean`
- `lean/PFCore/Contract.lean`
- `lean/PFCore/Certificate.lean`
- `lean/PFCore/Soundness.lean`
- `lean/PFCore/Theorems.lean`
- `lean/PFCore.lean` (root module for `lake build PFCore`)
- `lean/PCS.lean` (root module for `lake build PCS`)
