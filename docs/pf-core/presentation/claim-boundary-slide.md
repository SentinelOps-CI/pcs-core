# PF-Core claim class reference (external audience)

One-page summary of what each assurance label means and what it does **not** imply.

| Claim class | What we checked | What we did **not** check |
|-------------|-----------------|---------------------------|
| `SchemaValidated` | JSON Schema + PF-Core semantic fields | Runtime behavior, policies, Lean proofs |
| `RuntimeChecked` | Compiler + hash chain + Python deciders (capability, tenant, resource scope) | Lean kernel proof, external checker |
| `CertificateChecked` | External checker attestation recorded in PF-Core schema | Lean kernel, full platform safety |
| `LeanKernelChecked` | Concrete Lean proof of `traceSafeD` for this trace | Global non-interference, model safety, MCP/NL policy |
| `ReplayValidated` | Deterministic hash replay reproduced stored digests | Semantic re-execution of external tools |
| `AssumptionDeclared` | Documented assumptions for deferred registry checks | Execution of skipped Lean/build gates |
| `OutOfScope` | Explicitly outside PF-Core kernel | Any formal guarantee |

## Public language

Use trace-level safety preservation under stated assumptions. Avoid marketing phrases that imply full agent or platform verification unless the matching claim class and documentation are present.

## PCS vs PF-Core

- PCS `TraceCertificate.v0` / `CertificateChecked` status describes science-bundle lifecycle.
- PF-Core `claim_class` describes the PF-Core assurance obtained.
- `pcs lean-check` (PCS path) is **not** Lean-backed per trace; use `pcs pf-core lean-check --trace …` for PF-Core checking.
