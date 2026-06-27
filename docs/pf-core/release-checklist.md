# PF-Core release checklist

Pre-release verification for PF-Core in `pcs-core`. Run from repository root unless noted.

## CI gates (what they prove)

| Job / step | Proves |
|------------|--------|
| `pytest tests/test_pf_core_*.py` | Python runtime, contracts, codegen, CertifyEdge mock, fixtures |
| `pcs pf-core audit-claims` | No forbidden overclaim phrases in docs/examples |
| `pcs pf-core audit-boundary` | Trusted-boundary docs and registry consistency |
| `pcs pf-core audit-lean-catalog` | Catalog symbols exist in Lean sources |
| `pcs pf-core audit-lean-no-sorry` | No `sorry` / `axiom` in `lean/PFCore/` |
| `pcs examples check` | Valid/invalid PF-Core fixtures including replay and isolation |
| Lean job: `lake build PFCore` | Kernel compiles; decider soundness theorems check |
| Lean job: `pcs pf-core lean-check` | Concrete trace proof + `LeanKernelChecked` path on fixture |
| Lean job: `validate-contracts` | Contract runtime checker on `contract_checked/` |
| `PCS_CERTIFYEDGE_MOCK=1 pcs pf-core certifyedge-check` | External checker hook (mock attestation) |

## Local full demo

```bash
pip install -e python
bash scripts/pf-core-bridge-demo.sh
pcs pf-core lean-check --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json
pcs pf-core validate-contracts \
  examples/pf-core-valid/contract_checked/trace.json \
  --contracts-dir examples/pf-core-valid/contract_checked
PCS_CERTIFYEDGE_MOCK=1 pcs pf-core certifyedge-check \
  --trace examples/pf-core-valid/labtrust_replay/trace.json \
  --property qc_release.temporal.safety \
  --out /tmp/PFCoreCertificate.certifyedge.json
```

Optional Lean build (requires Lean 4 + `lake`):

```bash
cd lean && lake build PFCore
```

On Windows without native `lake`, use WSL for Lean steps.

## Claim boundaries for external release

| Claim class | May state | Must not state |
|-------------|-----------|----------------|
| `RuntimeChecked` | Python deciders aligned with Lean predicates | Lean kernel proof, CertifyEdge attestation |
| `LeanKernelChecked` | Concrete `traceSafeD` (+ contract deciders when refs present) proved in Lean | Global non-interference, full JSON contract discharge for role/policy/evidence fields |
| `ReplayValidated` | Hash-chain integrity | Upgrades to Lean or CertifyEdge |
| `CertificateChecked` | External checker attestation (CertifyEdge mock or live) | `LeanKernelChecked`, global non-interference |

Reference: `docs/pf-core/claim-boundary.md`, `docs/pf-core/non-interference.md`, `docs/pf-core/contract-semantics.md`.

## Phase F deliverables (this release)

- F1: `NonInterference.lean` + `validate_tenant_isolation` + `cross_tenant_leak/` fixture
- F2: `ContractDecide.lean` + Lean codegen contract discharge for mapped JSON fields
- F3: `pf_core_certifyedge.py` + `pcs pf-core certifyedge-check` + mock CI path
