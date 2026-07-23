# CertifyEdge integration (PF-Core)

PF-Core integrates the external [CertifyEdge](https://github.com/fraware/CertifyEdge) CLI for `CertificateChecked` attestations on traces. This path is separate from `LeanKernelChecked` trace safety.

## Environment contract

| Variable | Values | Default | Meaning |
|----------|--------|---------|---------|
| `PF_CORE_CERTIFYEDGE_MODE` | `auto`, `live`, `mock` | `auto` | Execution mode |
| `PF_CORE_CERTIFYEDGE_CLI` | path or command name | unset | Explicit CertifyEdge binary (or format stub script) |
| `PF_CORE_CERTIFYEDGE_MOCK` | `1`, `true`, `yes` | unset | Forces mock mode (same as `MODE=mock`) |
| `PF_CORE_CERTIFYEDGE_REQUIRE_LIVE` | `1`, `true`, `yes` | unset | Fail when live CLI absent (`--require-live` alias) |
| `PF_CORE_CERTIFYEDGE_ALLOW_STUB` | `1`, `true`, `yes` | unset | Allow format stub on `require_live` (staging only) |
| `PCS_CERTIFYEDGE_PROVISION_ENV` | path | `.tools/certifyedge/provision.env` | Machine-readable provision output |

Legacy alias: `PCS_CERTIFYEDGE_MOCK=1` (still honored).

Provisioning (`scripts/provision-certifyedge.sh`) always writes `provision.env` with executable
path, binary digest, version, pin identity, strategy, and `trust_grade`
(`pinned` | `untrusted_development` | `unpinned`). Workflows must source that file and must
not overwrite `PF_CORE_CERTIFYEDGE_CLI` with an empty secret. Arbitrary PATH checkers that
do not match the pin digest remain `untrusted_development` even when exit 0.

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

### Attestation classes

| Class | `proof_ref` prefix | Allowed in |
|-------|-------------------|------------|
| **live** | real attestation URL/hash from CertifyEdge binary | release gate |
| **stub** | `stub://certifyedge/` | local/CI format validation only |
| **mock** | `mock://` | dev CI only |

Format-validation stub (CI, no real attestation): `scripts/certifyedge-stub.py` — mimics `check-trace` stdout (`attestation: stub://...`). Must be set explicitly via `PF_CORE_CERTIFYEDGE_CLI`; never auto-selected on the release gate.

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
| Release gate (`pf-core-release-gate.yml`) | Live CLI required; rejects `mock://` and `stub://` |
| Local dev | `PF_CORE_CERTIFYEDGE_MODE=mock` for demos |

### Release gate matrix

| Step | When | Outcome |
|------|------|---------|
| Live certifyedge-check | `PF_CORE_CERTIFYEDGE_CLI` secret or `certifyedge` on PATH | `PF_CORE_CERTIFYEDGE_MODE=live` + `--require-live`; must succeed |
| Attestation validation | After live check | Reject `mock://`; reject `stub://` unless `PF_CORE_CERTIFYEDGE_ALLOW_STUB=1` |
| Mock certifyedge-check | Separate step | Validates mock fixture; does not claim live attestation |
| Hard fail | No live CLI on release runner | Workflow fails (no automatic stub fallback) |

Repository secret (optional): `PF_CORE_CERTIFYEDGE_CLI` — absolute path to the CertifyEdge binary on the release runner.

## Honest claim boundary

- `CertificateChecked` from CertifyEdge does **not** imply `LeanKernelChecked`.
- Mock attestations must not be described as live external verification.
- Install failures return `Rejected` with `CERTIFYEDGE_INSTALL_DOC` guidance.

See `docs/pf-core/claim-boundary.md` and `python/pcs_core/pf_core_certifyedge.py`.
