# CertifyEdge in CI and production

PF-Core attaches external CertifyEdge attestations to `PFCoreCertificate.v0` via
`pcs pf-core certifyedge-check`. Attestation classes are explicit:

| Class | `proof_ref` prefix | Allowed in |
|-------|-------------------|------------|
| **live** | real attestation URL/hash from CertifyEdge binary | release gate |
| **stub** | `stub://certifyedge/` | local/CI format validation only |
| **mock** | `mock://` | dev CI only |

See also [`certifyedge.md`](certifyedge.md) for the full environment contract and CLI usage.

## Environment contract

| Variable | Values | Default | Meaning |
|----------|--------|---------|---------|
| `PF_CORE_CERTIFYEDGE_MODE` | `auto`, `live`, `mock` | `auto` | Execution mode |
| `PF_CORE_CERTIFYEDGE_CLI` | path or command name | unset | Explicit CertifyEdge binary (or format stub script) |
| `PF_CORE_CERTIFYEDGE_MOCK` | `1`, `true`, `yes` | unset | Forces mock mode (same as `MODE=mock`) |
| `PF_CORE_CERTIFYEDGE_REQUIRE_LIVE` | `1`, `true`, `yes` | unset | Fail when live CLI absent (`--require-live` alias) |
| `PF_CORE_CERTIFYEDGE_ALLOW_STUB` | `1`, `true`, `yes` | unset | Allow format stub on `require_live` (staging only) |

Legacy alias: `PCS_CERTIFYEDGE_MOCK=1` (still honored).

## Dev CI vs release gate

| Context | CertifyEdge requirement |
|---------|-------------------------|
| Main CI (`ci.yml`) | Live when CLI present; `PCS_CERTIFYEDGE_MOCK=1` fallback |
| Release gate (`pf-core-release-gate.yml`) | Live CLI required; rejects `mock://` and `stub://` |
| Local dev | `PF_CORE_CERTIFYEDGE_MODE=mock` for demos |

Mock mode is **not** a substitute for release-gate live CertifyEdge attestation.

### Release gate matrix

| Step | When | Outcome |
|------|------|---------|
| Live certifyedge-check | `PF_CORE_CERTIFYEDGE_CLI` secret or `certifyedge` on PATH | `PF_CORE_CERTIFYEDGE_MODE=live` + `--require-live`; must succeed |
| Attestation validation | After live check | Reject `mock://`; reject `stub://` unless `PF_CORE_CERTIFYEDGE_ALLOW_STUB=1` |
| Mock certifyedge-check | Separate step | Validates mock fixture; does not claim live attestation |
| Hard fail | No live CLI on release runner | Workflow fails (no automatic stub fallback) |

Repository secret (optional): `PF_CORE_CERTIFYEDGE_CLI` — absolute path to the CertifyEdge binary on the release runner.

## Install (live path)

Preferred production path: pin an immutable CertifyEdge artifact in
`pins/certifyedge.json` (`status=pinned`) and provision via:

```bash
export PCS_RELEASE_MODE=release
bash scripts/provision-certifyedge.sh
# ALWAYS source the machine-readable env file (do not blank it with an empty secret):
set -a && . .tools/certifyedge/provision.env && set +a
export PF_CORE_CERTIFYEDGE_CLI
```

`provision.env` records executable path, binary digest, version, pin identity,
provision strategy, and trust grade. Workflows must source this file.

Approved production strategies: `oci_digest`, `signed_binary`, `source_commit_build`.
Release mode fails closed when the pin is `unpinned` — do not invent fake digests.
`dev_fixture` is test/preview only (`trust_grade=untrusted_development`).

Arbitrary executables on PATH that do not match the pin digest are classified
`untrusted_development` even when they exit 0.
Fallback (documented staging only): install [CertifyEdge](https://github.com/fraware/CertifyEdge)
per upstream instructions and set `PF_CORE_CERTIFYEDGE_CLI`.

1. Verify:

```bash
certifyedge --version
which certifyedge
```

2. Bind live attestation to an exact release bundle:

```bash
pcs pf-core bundle-release --trace PATH --cert PATH --out /tmp/bundle
pcs pf-core attest-bundle --bundle /tmp/bundle --property qc_release.temporal.safety --require-live
pcs pf-core validate-external-attestation --bundle /tmp/bundle --require-live
```

Expected: `ExternalAttestation.v0` with `attestation_class: live`, bound to the
bundle manifest digest. Claim class on the PF-Core certificate remains
`CertificateChecked` (never `LeanKernelChecked`).

## Mock path (dev CI fallback)

When CertifyEdge is unavailable in **main CI only**, set:

```bash
export PCS_CERTIFYEDGE_MOCK=1
# or
export PF_CORE_CERTIFYEDGE_MODE=mock
```

CI logs a warning and uses mock attestation (`mock://certifyedge/...`) without failing the pipeline.
Mock attestations must not be described as live external verification.

## Format-validation stub (local only)

`scripts/certifyedge-stub.py` mimics `check-trace` stdout (`attestation: stub://...`) for format
validation without a real CertifyEdge install. Set explicitly:

```bash
export PF_CORE_CERTIFYEDGE_CLI=/path/to/scripts/certifyedge-stub.py
export PF_CORE_CERTIFYEDGE_MODE=live
pcs pf-core certifyedge-check --trace ... --property ... --out /tmp/cert.json
```

The stub is **not** used automatically on the release gate. For documented staging exceptions only,
set `PF_CORE_CERTIFYEDGE_ALLOW_STUB=1` with `--require-live`.

## CI behavior (main `ci.yml`)

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

See [`claim-boundary.md`](claim-boundary.md) and [`python/pcs_core/pf_core_certifyedge.py`](../../python/pcs_core/pf_core_certifyedge.py).
