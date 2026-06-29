# CertifyEdge mock fixture

Pre-generated `CertificateChecked` certificate using `PF_CORE_CERTIFYEDGE_MODE=mock`. No live CertifyEdge CLI is required to validate this fixture.

## Mock vs live (honest claim classes)

| Path | Attestation | Use |
|------|-------------|-----|
| **Mock** (this fixture) | `mock://certifyedge/...` | Local dev, CI demos, `pcs examples check` |
| **Stub** | `stub://...` from `scripts/certifyedge-stub.py` | Format contract / dry-run only; not production attestation |
| **Live** | Real CertifyEdge CLI output | Required on release tags via `.github/workflows/pf-core-release-gate.yml` |

Mock attestations must not be described as live external verification. They do **not** imply `LeanKernelChecked` PF-Core trace safety.

## Regenerate

```bash
export PF_CORE_CERTIFYEDGE_MODE=mock
pcs pf-core certifyedge-check \
  --trace examples/pf-core-valid/certifyedge_mock/trace.json \
  --property qc_release.temporal.safety \
  --out examples/pf-core-valid/certifyedge_mock/certificate.json
```

On Windows PowerShell:

```powershell
$env:PF_CORE_CERTIFYEDGE_MODE = "mock"
pcs pf-core certifyedge-check `
  --trace examples/pf-core-valid/certifyedge_mock/trace.json `
  --property qc_release.temporal.safety `
  --out examples/pf-core-valid/certifyedge_mock/certificate.json
```

## Verify

```bash
pcs pf-core validate-trace examples/pf-core-valid/certifyedge_mock/trace.json
pcs validate examples/pf-core-valid/certifyedge_mock/certificate.json
pcs examples check
```

## Local release-gate dry-run matrix

```powershell
# Mock dev path (this fixture):
powershell -File scripts/pf-core-certifyedge-dry-run.ps1

# Stub format contract (labtrust replay trace):
powershell -File scripts/pf-core-certifyedge-stub-dry-run.ps1
```

See [docs/pf-core/certifyedge.md](../../docs/pf-core/certifyedge.md) for the env contract and GitHub `workflow_dispatch` release-gate steps.
