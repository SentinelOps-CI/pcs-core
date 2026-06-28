# CertifyEdge in CI and production

PF-Core can attach external CertifyEdge attestations to `PFCoreCertificate.v0` via
`pcs pf-core certifyedge-check`. CI exercises this path on the LabTrust replay fixture.

## Install (live path)

1. Install [CertifyEdge](https://github.com/fraware/CertifyEdge) per upstream instructions.
2. Ensure the `certifyedge` CLI is on `PATH`.
3. Verify:

```bash
certifyedge --version
which certifyedge
```

4. Run a live check:

```bash
pcs pf-core certifyedge-check \
  --trace examples/pf-core-valid/labtrust_replay/trace.json \
  --property qc_release.temporal.safety \
  --out /tmp/PFCoreCertificate.certifyedge.json
```

Expected: `claim_class: CertificateChecked` (never `LeanKernelChecked`).

## Mock path (CI fallback)

When CertifyEdge is unavailable, set:

```bash
export PCS_CERTIFYEDGE_MOCK=1
```

CI logs a warning and uses mock attestation without failing the pipeline.

## CI behavior

The `python` job step **PF-Core CertifyEdge check (live or mock)**:

1. Runs `command -v certifyedge` and optionally `certifyedge --version`.
2. If present: runs live `pcs pf-core certifyedge-check` on the LabTrust fixture.
3. If live check fails: logs a warning and falls back to `PCS_CERTIFYEDGE_MOCK=1`.
4. If absent: logs a warning and uses mock mode.

## Optional pinned binary

For reproducible CI without building from source, operators may pin a release artifact URL
from the CertifyEdge repository and install it in a custom runner image. No Docker image is
shipped from pcs-core by default; add one only after explicit approval.

## Trust boundary

CertifyEdge attestation yields `CertificateChecked` only. It does not discharge PF-Core
Lean kernel proofs or PCS release-envelope `EnvelopeLeanChecked` obligations.
