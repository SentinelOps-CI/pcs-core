# PF-Core threat model

## Assets

- PF-Core trace integrity (event hash chain, trace hash)
- Claim class accuracy (no upgrade from `RuntimeChecked` to `LeanKernelChecked` without proof)
- Lean trusted computing base (TCB) source files
- Registry authority (artifact type definitions, release-mode requirements)

## Adversary capabilities

| Threat | Description | Mitigation |
|--------|-------------|------------|
| Overclaiming in docs | Marketing language implies full AI safety | `pcs pf-core audit-claims` |
| Heuristic type confusion | Malformed JSON detected as wrong artifact type | Explicit `artifact_type` + schema `const` |
| Catalog inflation | Python catalog lists nonexistent Lean theorems | `pcs pf-core audit-lean-catalog` |
| Status / claim conflation | `ProofChecked` read as Lean kernel proof | Documented in claim-boundary; PCS `lean-check` disclaimer |
| Omitted denied events | Unsafe runs hide blocked attempts | Stage 2 compiler preserves denied events |
| Authority expansion via handoff | Delegate more capabilities than source holds | Stage 3 `HandoffSafe` theorem; Stage 7 compile gate |
| Registry deferral as proof | Skipped checks treated as verified | `AssumptionDeclared` / `OutOfScope`; `enforce_assumption_declared` |
| Hash collision | Forged digest matching valid trace | SHA-256 assumption; no claim beyond digest equality |
| Untrusted adapter tampering | Adapter rewrites release artifacts | Adapters untrusted; schema + hash validation |
| Fake Lean proof | Certificate claims kernel proof without `decide` success | Stage 4 codegen + `lake env lean`; `LeanKernelChecked` gated on proof |
| Replay forgery | Altered trace passes without hash-chain check | Stage 5 `replay-trace` (`ReplayValidated`) |
| Contract bypass | Events violate declared contracts | Stage 7 runtime checker + `validate-contracts` |

## Trust boundaries

```
Untrusted runtime / adapters / PCS external checkers
        |
        v  (schema-valid PF-Core artifacts, explicit artifact_type)
PF-Core validation + hash chain + contract checker (Python)
        |
        +--> ReplayValidated (Stage 5 hash-chain replay)
        |
        +--> RuntimeChecked (Python deciders aligned with Lean predicates)
        |
        v  (codegen + lake env lean on generated proof)
PF-Core trace-safety Lean kernel (lean/PFCore/)
        |
        v  LeanKernelChecked (concrete traceSafeD proof only)

Parallel PCS release-envelope path (NOT per-trace agent safety):
Untrusted producers --> PCS schema validation --> lake build PCS
        |
        v  Release-envelope consistency theorems (lean/PCS/Theorems.lean)
```

PCS `pcs lean-check` (without `--trace`) evaluates release obligations in Python only; it does **not** produce per-trace `LeanKernelChecked` claims. Use `pcs pf-core lean-check --trace` for trace-level kernel proofs.

## Residual risk

- PF-Core contract JSON predicates are richer than the Lean `Contract` structure; contract satisfaction in Lean is intentionally simplified (see [contract-semantics.md](contract-semantics.md)).
- Role names are not interpreted in the Lean kernel; runtime expands roles to capabilities, and lean-check requires explicit capability lists on traces (permanent assumption).
- Global non-interference and full compositional invariant research remain deferred (Phase F).
- Model correctness, NL policy, MCP semantics, and live CertifyEdge attestation are out of scope.
- Generated proofs cover `traceSafeD`, per-event `eventSafeD`, and optional `handoffSafeD`; they do not yet discharge arbitrary JSON contract invariants in Lean.
