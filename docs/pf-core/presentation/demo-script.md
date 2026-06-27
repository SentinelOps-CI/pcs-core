# PF-Core demo script

Scripted walkthrough: compile tool-use trace, validate, lean-check, replay-trace. Audience: technical reviewers.

## Prerequisites

- Repository root: `pcs-core`
- Python package installed: `pip install -e python`
- Optional: Lean 4 + `lake` for full `LeanKernelChecked` path

## 1. Compile ToolUseTrace to PFCoreTrace

```bash
pcs pf-core compile-trace examples/pf-core-valid/tool_use_trace_compiled/tool_use_trace.json
```

Expected: JSON `PFCoreTrace.v0` with `claim_class: RuntimeChecked`, denied network event preserved.

## 2. Validate hash chain

```bash
pcs pf-core validate-trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json
```

Expected: `OK PFCoreTrace hash chain …`

## 3. Validate contracts (Stage 7)

```bash
pcs pf-core validate-contracts \
  examples/pf-core-valid/contract_checked/trace.json \
  --contracts-dir examples/pf-core-valid/contract_checked
```

Expected: `OK PF-Core contract satisfaction …`

## 4. Lean-check (RuntimeChecked vs LeanKernelChecked)

Runtime-only (no Lean build):

```bash
pcs pf-core lean-check \
  --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json \
  --skip-build --skip-lean-proof
```

Expected: certificate / result with `claim_class: RuntimeChecked`.

Full kernel path (when Lean toolchain available):

```bash
pcs pf-core lean-check \
  --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json
```

Expected on success: `claim_class: LeanKernelChecked`, `lean_proof_checked: true`.

## 5. Replay-trace

```bash
pcs pf-core replay-trace \
  examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json \
  --source examples/pf-core-valid/tool_use_trace_compiled/tool_use_trace.json
```

Expected: `claim_class: ReplayValidated`, `replay_match: true`.

## 6. LabTrust bridge (Stage 6)

```bash
pcs validate examples/pf-core-valid/labtrust_replay/trace.json
pcs pf-core replay-trace examples/pf-core-valid/labtrust_replay/trace.json
```

Expected: schema validation OK; replay match (adapter output per `docs/pf-core-trace-mapping.md`).

## 7. PCS lean-check disclaimer (not per-trace Lean)

```bash
pcs lean-check
```

Expected: exit code 2, stderr explains PCS path is not Lean-backed per trace; directs to `pcs pf-core lean-check`.

## 8. LabTrust end-to-end bridge (Phase E)

Automated script:

```bash
bash scripts/pf-core-bridge-demo.sh
```

Manual steps:

```bash
pcs validate examples/labtrust/trace_certificate.valid.json
python -c "
from pathlib import Path
import json
from pcs_core.pf_core_labtrust_adapter import normalize_labtrust_release
root = Path('.')
tc = json.loads((root/'examples/labtrust/trace_certificate.valid.json').read_text())
scb = json.loads((root/'examples/labtrust/science_claim_bundle.certified.valid.json').read_text())
print(json.dumps(normalize_labtrust_release(tc, scb['runtime_receipts'][0]), indent=2))
"
pcs pf-core replay-trace examples/pf-core-valid/labtrust_replay/trace.json
pcs pf-core attach-certificate-check \
  --trace examples/pf-core-valid/labtrust_replay/trace.json \
  --checker certifyedge \
  --checker-version 0.1.0 \
  --attestation-ref examples/labtrust/trace_certificate.valid.json \
  --out /tmp/PFCoreCertificate.v0.json
```

Expected: bridged `PFCoreCertificate.v0` with `claim_class: CertificateChecked` (not `LeanKernelChecked`).

CertifyEdge check (mock for CI):

```bash
PCS_CERTIFYEDGE_MOCK=1 pcs pf-core certifyedge-check \
  --trace examples/pf-core-valid/labtrust_replay/trace.json \
  --property qc_release.temporal.safety \
  --out /tmp/PFCoreCertificate.certifyedge.json
```

Expected: `claim_class: CertificateChecked`, never `LeanKernelChecked`.

## 9. Tenant isolation (Phase F1)

```bash
pcs pf-core validate-trace --tenant-isolation \
  examples/pf-core-valid/file_read_allowed/trace.json
```

Expected: OK. Invalid fixture `examples/pf-core-invalid/cross_tenant_leak/` fails examples check.

## 10. Contract discharge in Lean (Phase F2)

```bash
pcs pf-core lean-check \
  --trace examples/pf-core-valid/contract_checked/trace.json
```

Expected (with Lean toolchain): generated proof includes `concrete_trace_satisfies_contract_*` theorems.

AssumptionSet-backed deferred assurance fixture:

```bash
pcs validate examples/pf-core-valid/assumption_declared/assumption_set.json
pcs validate examples/pf-core-valid/assumption_declared/certificate.json
```

Expected: `claim_class: AssumptionDeclared` with `assumption_refs` citing `as-pfcore-demo-v0.1`.

## Talking points

- **RuntimeChecked**: Python deciders aligned with Lean predicates; no kernel proof.
- **LeanKernelChecked**: same deciders plus concrete `traceSafeD` proof in Lean.
- **ReplayValidated**: hash-chain integrity only; does not upgrade to LeanKernelChecked.
