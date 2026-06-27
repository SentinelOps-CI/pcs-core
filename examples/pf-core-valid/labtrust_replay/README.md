# LabTrust replay example

This fixture demonstrates the untrusted adapter path from LabTrust PCS release
artifacts to `PFCoreTrace.v0`, as documented in
[docs/pf-core-trace-mapping.md](../../docs/pf-core-trace-mapping.md).

## Source artifacts

- `examples/labtrust/trace_certificate.valid.json` — PCS `TraceCertificate.v0`
- `examples/labtrust/science_claim_bundle.certified.valid.json` — runtime receipt

## Adapter

```python
from pcs_core.pf_core_labtrust_adapter import normalize_labtrust_release
```

The adapter builds a single-event trace with `lab.release` effect and principal
`lab-operator-1`. PCS `spec_hash` maps to PF-Core `contract_hash`; the PCS
`trace_hash` binding is recorded in `manifest.json` (organizational cross-reference).

## Verification

```bash
pcs pf-core validate-trace examples/pf-core-valid/labtrust_replay/trace.json
pcs pf-core replay-trace examples/pf-core-valid/labtrust_replay/trace.json
```
