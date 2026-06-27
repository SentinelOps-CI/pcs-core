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
| PF-Core concrete trace Lean proofs | `lean/PFCore/Generated/` (generated) | `lake env lean` on generated `concrete_trace_safe` theorem |
| Tool-use / witness hash alignment theorems | `lean/PCS/ToolUse.lean`, `lean/PCS/ComputationWitness.lean` | Promoted to trusted PCS catalog (Stage 4) |
| Role → capability expansion | `python/pcs_core/pf_core_runtime.py` | Compiler expands roles; lean-check requires explicit capabilities on traces |
| PF-Core no-sorry audit | `python/pcs_core/lean_check.py` | Scans `lean/PFCore/` for forbidden tokens |

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

## Allowlisted Lean axioms

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
