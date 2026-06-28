# CertifyEdge integration (PF-Core)

PF-Core integrates the external [CertifyEdge](https://github.com/fraware/CertifyEdge) CLI for `CertificateChecked` attestations on traces. This path is separate from `LeanKernelChecked` trace safety.

## Environment contract

| Variable | Values | Default | Meaning |
|----------|--------|---------|---------|
| `PF_CORE_CERTIFYEDGE_MODE` | `auto`, `live`, `mock` | `auto` | Execution mode |
| `PF_CORE_CERTIFYEDGE_CLI` | path or command name | unset | Explicit CertifyEdge binary |
| `PF_CORE_CERTIFYEDGE_MOCK` | `1`, `true`, `yes` | unset | Forces mock mode (same as `MODE=mock`) |
| `PF_CORE_CERTIFYEDGE_REQUIRE_LIVE` | `1`, `true`, `yes` | unset | Fail when live CLI absent (`--require-live` alias) |

Legacy alias: `PCS_CERTIFYEDGE_MOCK=1` (still honored).

### Modes

- **auto** — use live CLI when found on PATH (or `PF_CORE_CERTIFYEDGE_CLI`); fail closed when absent.
- **live** — require live CLI; fail with install instructions when absent.
- **mock** — emit mock attestation (`mock://certifyedge/...`); clearly not live.

Mock mode prints a stderr warning and sets `mock: true` on the internal result. Live success message includes `(live)`.

## CLI

```bash
pcs pf-core certifyedge-check \
  --trace examples/pf-core-valid/labtrust_replay/trace.json \
  --property qc_release.temporal.safety \
  --out /tmp/PFCoreCertificate.certifyedge.json
```

Use `--require-live` (or `PF_CORE_CERTIFYEDGE_REQUIRE_LIVE=1`) on release runners to fail closed when the live CLI is absent.

Format-validation stub (CI, no real attestation): `scripts/certifyedge-stub.py` — mimics `check-trace` stdout (`attestation: stub://...`).

Status probe (Python):

```python
from pcs_core.pf_core_certifyedge import certifyedge_status
print(certifyedge_status())
```

## Local dev mock fixture

Pre-generated mock certificate (no live CLI required):

```bash
# Regenerate (optional):
$env:PF_CORE_CERTIFYEDGE_MODE = "mock"
pcs pf-core certifyedge-check \
  --trace examples/pf-core-valid/certifyedge_mock/trace.json \
  --property qc_release.temporal.safety \
  --out examples/pf-core-valid/certifyedge_mock/certificate.json

# Validate fixture:
pcs pf-core validate-trace examples/pf-core-valid/certifyedge_mock/trace.json
pcs validate examples/pf-core-valid/certifyedge_mock/certificate.json
pcs examples check
```

Fixture path: `examples/pf-core-valid/certifyedge_mock/` (`trace.json`, `certificate.json`, `manifest.json`).

## Release gate dry-run (local)

The release gate workflow requires live CertifyEdge. To dry-run PF-Core steps locally without live CLI:

```powershell
# Windows — CertifyEdge mock only:
powershell -File scripts/pf-core-certifyedge-dry-run.ps1
```

```bash
# Linux/macOS:
bash scripts/pf-core-certifyedge-dry-run.sh
```

Full PF-Core release-grade (Lean + conformance); CertifyEdge mock included in release-grade scripts when `PF_CORE_CERTIFYEDGE_MODE=mock`:

```powershell
$env:PF_CORE_CERTIFYEDGE_MODE = "mock"
powershell -File scripts/pf-core-release-grade-local.ps1
```

```bash
export PF_CORE_CERTIFYEDGE_MODE=mock
bash scripts/pf-core-release-grade-local.sh
```

| Step | Release gate (CI) | Local dry-run |
|------|-------------------|---------------|
| `lake build PFCore` | Required | Required when `lake` on PATH |
| `pcs conformance run --suite pf-core --release-grade` | Required | Required |
| CertifyEdge attestation | Live CLI required | `PF_CORE_CERTIFYEDGE_MODE=mock` |
| `verify-proof-binding` | Required | Required when lean-check succeeds |

Mock mode is **not** a substitute for release-gate live CertifyEdge attestation.

## CI vs release gate

| Context | CertifyEdge requirement |
|---------|-------------------------|
| Main CI (`ci.yml`) | Live when CLI present; `PCS_CERTIFYEDGE_MOCK=1` fallback |
| Release gate (`pf-core-release-gate.yml`) | Mock always; live with CLI/stub; `PF_CORE_CERTIFYEDGE_REQUIRE_LIVE=1` fails if absent |
| Local dev | `PF_CORE_CERTIFYEDGE_MODE=mock` for demos |

### Release gate matrix

| Step | When | Outcome |
|------|------|---------|
| Mock certifyedge-check | Always | Validates mock fixture; does not claim live attestation |
| Live certifyedge-check | CLI, stub, or `PF_CORE_CERTIFYEDGE_CLI` secret | `PF_CORE_CERTIFYEDGE_MODE=live` + `--require-live`; required success when run |
| Live skip / fail | No CLI; `REQUIRE_LIVE=0` | Workflow continues (mock validated) |
| Live hard fail | No CLI; `PF_CORE_CERTIFYEDGE_REQUIRE_LIVE=1` | Workflow fails |

Repository secret (optional): `PF_CORE_CERTIFYEDGE_CLI` — absolute path to the CertifyEdge binary on the release runner.

## Honest claim boundary

- `CertificateChecked` from CertifyEdge does **not** imply `LeanKernelChecked`.
- Mock attestations must not be described as live external verification.
- Install failures return `Rejected` with `CERTIFYEDGE_INSTALL_DOC` guidance.

See `docs/pf-core/claim-boundary.md` and `python/pcs_core/pf_core_certifyedge.py`.
