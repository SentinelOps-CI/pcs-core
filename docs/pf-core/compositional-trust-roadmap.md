# PF-Core compositional trust roadmap

Future research work only. **Not implemented in pcs-core v0.1.**

## Goal

Extend PF-Core from per-trace concrete proofs to compositional theorems that preserve trace safety under controlled extension (new events, delegated authority, contract refinement) without re-running full Lean codegen for every composition step.

## Theorem targets (future)

| Theorem | Intent |
|---------|--------|
| `safe_extension_preserves_trace_safe` | Appending an `EventSafe` event to a `TraceSafe` trace yields `TraceSafe` |
| `handoff_preserves_trace_safe` | `HandoffSafe` delegation followed by in-bounds actions preserves `TraceSafe` |
| `contract_refinement_preserves_trace_safe` | Stricter contract discharge on a sub-trace preserves global trace safety |
| `replay_preserves_claim_boundary` | Hash replay match implies no silent claim-class upgrade |
| `certificate_binds_generated_model` | Certificate `trace_hash` + `proof_term_hash` + `lean_environment_hash` uniquely binds JSON to generated Lean model |

## Dependencies

- Stable `PFCoreTraceClaimClass` vs `PFCoreCertificateClaimClass` separation (implemented)
- Closed direct-trace effect catalog and capability/effect alignment (implemented)
- `proof_term_hash` binding on `LeanKernelChecked` certificates (implemented)
- Full semantic validation in `pcs pf-core lean-check` (implemented)

## Out of scope for this roadmap phase

- Global non-interference across tenants
- Lean RoleMap / role expansion discharge
- Full JSON contract field encoding in Lean for role, policy, and evidence refs

See [non-interference.md](non-interference.md) and [assumptions.md](assumptions.md) for current deferrals.
