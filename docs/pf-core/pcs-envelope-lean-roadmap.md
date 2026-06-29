# PCS envelope Lean path roadmap

This document records the PCS `pcs pcs-envelope check` Lean path and its trust boundary relative to PF-Core kernel proofs.

## Current scope (v0.1 — Stage PCS-Lean partial)

| Path | Emits | Lean work |
|------|-------|-----------|
| `pcs pcs-envelope check` | `LeanCheckResult.v0` with `claim_class: ProofChecked` | Obligations vs Python deciders + `lean/PCS/Theorems.lean` catalog |
| `pcs pcs-envelope check --lean-proof` | `LeanCheckResult.v0` with `claim_class: EnvelopeLeanChecked` when proof compiles | Generated module in `lean/PCS/Generated/` + `lake env lean` |
| `pcs pf-core lean-check --trace` | `PFCoreCertificate.v0` with `LeanKernelChecked` | Generated concrete trace proof in `lean/PFCore/Generated/` |

There is **no silent upgrade** from envelope consistency to per-trace PF-Core kernel proofs. See `docs/pf-core/trusted-boundary.md`.

## Stage PCS-Lean (partial implementation)

Implemented:

- `python/pcs_core/pcs_lean_codegen.py` — generates `Certificate`, `RuntimeReceipt`, `VerificationResult`, and bundle hashes from `ProofObligation.v0`.
- `lean/PCS/ReleaseChainCheck.lean` — decidable mirrors of `ReleaseChainAdmissible` predicates.
- `lean/PCS/Generated/Obligation_*.lean` — concrete fixture proofs (LabTrust release example).
- Generated proofs emit **both** decidable (`*D = true` via `decide`) and propositional (`*Prop` via `*D_sound`) theorems for each release-chain obligation component (`CertificateMatchesRuntime`, `VerificationAdmitsBundle`, `SignedBundleAdmissible`) plus aggregate `ReleaseChainAdmissible`.
- `--lean-proof` on `pcs pcs-envelope check` — emits `EnvelopeLeanChecked` with `proof_term_ref`, `proof_term_hash`, and disclaimer.

Not implemented (deferred):

- Full schema revision for all PCS benchmark ingest paths.
- Conformance suite `pcs-envelope-lean-proof` with mandatory `--release-grade` gate in all CI jobs.
- Full computation witness admissibility codegen over all `result_hashes` (single-artifact `witnessResultHashesAdmissibleD` path implemented for declared digest set; multi-artifact witness sets remain deferred).

## Stage PCS-Lean (tool-use + computation partial)

Implemented (2026-06-29):

- `generate_proof_obligation_file` routes by `workflow_id`: LabTrust release chain, tool-use hash alignment + release chain, computation witness result-hash listing + verification/signed bundle.
- `lean/PCS/Generated/release_pcs_v0_1_tool_use_safety.lean` — `concrete_tool_use_release_admissible_prop`.
- `lean/PCS/Generated/release_pcs_v0_1_scientific_computation.lean` — `concrete_computation_release_admissible_prop`.
- `witnessResultHashesAdmissibleD` decidable mirror in `lean/PCS/ComputationWitness.lean` (declared artifact digest set; multi-artifact witness listing deferred).
- `witnessResultHashListedD` decidable mirror in `lean/PCS/ComputationWitness.lean`.

Boundaries: these modules discharge PCS envelope obligations only. They do **not** emit PF-Core `LeanKernelChecked` or tool-use resource-scope proofs.

Previously deferred (still out of scope):

- Unified PF-Core kernel codegen for tool-use traces (use `pcs pf-core lean-check` instead).

## Claim classes (honest)

| Class | Meaning |
|-------|---------|
| `ProofChecked` | Python obligation deciders passed; optional `lake build PCS` succeeded |
| `EnvelopeLeanChecked` | Above plus generated PCS module compiled; **not** PF-Core `LeanKernelChecked` |
| `Rejected` | Obligation or Lean proof path failed |

## Regeneration policy

Regenerate PCS generated modules when `ProofObligation.v0` fixtures change:

```bash
python -c "
from pathlib import Path
from pcs_core.pcs_lean_codegen import generate_from_release_dir
generate_from_release_dir(Path('examples/labtrust-release'), Path('lean/PCS/Generated'))
"
```

Run `pcs pf-core audit-lean-no-sorry` after regeneration (scope includes `lean/PCS/` when present).

## Related documents

- `docs/pf-core/trusted-boundary.md` — trusted vs untrusted components
- `docs/pf-core/generated-proofs.md` — PF-Core regeneration policy
- `docs/pf-core/claim-boundary.md` — PCS `ProofChecked` vs PF-Core `LeanKernelChecked`
