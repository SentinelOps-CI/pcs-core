# Distribution: validator vs verifier

pcs-core ships two supported products. `pcs capabilities` reports which backends are
actually available on the current machine and never claims Lean or live CertifyEdge
when those assets are absent.

Asset locations (Lean root, PF-Core / PCS kernels, generated proofs, pins, catalogs,
schemas) are resolved exclusively through
[`python/pcs_core/asset_resolver.py`](../python/pcs_core/asset_resolver.py). Compilers,
hashers, bundle assembly, and proof-reference paths must not hardcode
`repo_root() / "lean"`. Override with `PCS_DISTRIBUTION_ROOT`, `PCS_LEAN_ROOT`,
`PCS_PINS_DIR`, or `PCS_CATALOG_DIR` when needed.

## Validator package (default Python wheel)

**Contains**

- Python validators and `pcs` CLI
- JSON schemas (`pcs_core/schemas` via wheel force-include)
- PF-Core capability catalog
- Shared hash vectors
- Runtime semantic checks and release-chain validation

**Does not contain**

- Lean toolchain
- `lean/PFCore` or `lean/PCS` kernel sources
- Proof-binding / lake build environment

Install:

```bash
cd python
pip install -e ".[dev]"
# or: pip install pcs-core
pcs capabilities
```

Expected product line: `pcs product: validator` unless a full checkout plus `lake`
are present. Lean subcommands may still be listed for developer checkouts; capability
detection and command failures remain the source of truth for what is available.

### Clean-environment acceptance (validator wheel)

From a fresh virtualenv with only the built validator wheel installed (no repo checkout
on `PYTHONPATH`, no `lake` on `PATH`):

1. Schema validation succeeds (`pcs validate <fixture>`).
2. Semantic validation succeeds (`pcs examples check` or release-chain validate).
3. `pcs capabilities --json` reports `product: validator` and
   `lean_toolchain` / `pf_core_kernel` / `pcs_envelope_kernel` as `false`.

CI job: `validator-wheel` in [`.github/workflows/distribution.yml`](../.github/workflows/distribution.yml).
Local: `bash scripts/test-validator-wheel.sh`.

## Verifier distribution

**Contains**

- Pinned Lean toolchain (via elan; see `pins/elan.json`)
- Lake project under `lean/`
- PF-Core and PCS Lean sources
- Generated-proof and proof-binding tooling
- Release-bundle tooling (`pcs pf-core bundle-release`, `pcs pf-core verify-bundle`)

### OCI image (primary ship vehicle)

Dockerfile: [`docker/verifier/Dockerfile`](../docker/verifier/Dockerfile).

- Base image pinned by **digest** (`pins/python-base-image.json`).
- Runs as non-root user `pcs` (uid/gid `10001`).
- Elan / Lean tools live under `/opt/elan` (owned by `pcs`).

```bash
docker build -f docker/verifier/Dockerfile -t pcs-core-verifier:local .
docker run --rm --user 10001:10001 pcs-core-verifier:local capabilities
```

### Signed images, SBOM, and provenance

Publish path (once org signing keys / GitHub OIDC are configured):

1. Build and push by digest:

   ```bash
   docker buildx build --push \
     -f docker/verifier/Dockerfile \
     -t ghcr.io/sentinelops-ci/pcs-core-verifier:vX.Y.Z \
     -t ghcr.io/sentinelops-ci/pcs-core-verifier:sha-<gitsha> \
     .
   ```

2. Attach SBOM (CycloneDX) and provenance attestations:

   ```bash
   # SBOM (example with syft)
   syft packages pcs-core-verifier:vX.Y.Z -o cyclonedx-json > pcs-core-verifier.cdx.json

   # GitHub artifact attestations / build provenance
   # (.github/workflows/release-provenance.yml:
   #  actions/attest-build-provenance + actions/attest-sbom;
   #  consumer job: scripts/verify-release-provenance.sh)
   ```

3. Sign with cosign (keyless OIDC preferred):

   ```bash
   cosign sign --yes ghcr.io/sentinelops-ci/pcs-core-verifier@sha256:<digest>
   cosign attest --yes --predicate pcs-core-verifier.cdx.json --type cyclonedx \
     ghcr.io/sentinelops-ci/pcs-core-verifier@sha256:<digest>
   cosign verify ghcr.io/sentinelops-ci/pcs-core-verifier@sha256:<digest>
   ```

4. Publish the image digest, cosign signature, SBOM digest, and provenance statement
   in the GitHub Release assets. Consumers verify:

   ```bash
   cosign verify ghcr.io/sentinelops-ci/pcs-core-verifier@sha256:<digest>
   cosign verify-attestation --type cyclonedx \
     ghcr.io/sentinelops-ci/pcs-core-verifier@sha256:<digest>
   ```

CI job: `Verifier OCI clean execution` in [`.github/workflows/distribution.yml`](../.github/workflows/distribution.yml)
(`scripts/test-verifier-oci.sh`). Local:

```bash
bash scripts/test-verifier-oci.sh
```

Signed image publish (cosign / GHCR) remains org-gated until signing keys / OIDC are provisioned.
Operator runbook: [pf-core/operator-release-gates.md](pf-core/operator-release-gates.md).

### Optional full wheel

```bash
bash scripts/build-verifier-wheel.sh
```

Embeds `lean/` and `pins/` under `pcs_core/` for `importlib.resources` style layouts.
Prefer the OCI image for production verifiers.

### Clean-environment acceptance (verifier wheel)

From a fresh virtualenv with the verifier wheel installed and pinned `lake` on `PATH`:

1. Bundled Lean assets are located (`asset_resolver.lean_root()` / capabilities paths).
2. `compute_pfcore_kernel_hash()` is non-empty and matches checkout kernel hash.
3. `compute_lean_environment_hash()` matches the bundled lake/toolchain inputs.
4. PF-Core proof compiles (`pcs pf-core lean-check` on TraceSafeR fixture).
5. PCS envelope proof path remains available (`lake build PCS`).
6. Bundle assembly succeeds (`pcs pf-core bundle-release`).
7. Independent bundle verification succeeds (`pcs pf-core verify-bundle`).

CI jobs: `Validator-wheel clean install`, `Verifier-wheel clean install`, and
`Verifier OCI clean execution` in [`.github/workflows/distribution.yml`](../.github/workflows/distribution.yml).
Local: `bash scripts/test-validator-wheel.sh`, `bash scripts/test-verifier-wheel.sh` (requires elan/lake),
`bash scripts/test-verifier-oci.sh` (requires Docker).

## Capability matrix

| Capability | Validator wheel | Full checkout + lake | Verifier OCI |
|------------|-----------------|----------------------|--------------|
| Schema validation | yes | yes | yes |
| Rust validator | no* | if `cargo` + crate | no* |
| TypeScript validator | no* | if `node` + package | no* |
| Lean toolchain | no | yes | yes |
| PF-Core kernel | no | yes | yes |
| PCS envelope kernel | no | yes | yes |
| Live CertifyEdge | if CLI on PATH | if CLI on PATH | if CLI installed |

\* Language bindings ship in-repo but are not part of the Python validator wheel.

## Related pins

| File | Purpose |
|------|---------|
| `pins/elan.json` | Elan archive URL + sha256 |
| `pins/python-base-image.json` | Verifier OCI base image digests |
| `pins/certifyedge.json` | CertifyEdge image digest placeholder |
| `pins/github-actions.json` | Immutable Action SHAs |
| `lean/lean-toolchain` | Lean 4 version |
| `rust/Cargo.lock` | Rust dependency lock |
| `typescript/package-lock.json` | npm lock |
| `python/requirements.lock` | Pip constraint lock |
