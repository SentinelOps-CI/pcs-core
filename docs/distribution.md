# Distribution: validator vs verifier

pcs-core ships two supported products. `pcs capabilities` reports which backends are
actually available on the current machine and never claims Lean or live CertifyEdge
when those assets are absent.

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

## Verifier distribution

**Contains**

- Pinned Lean toolchain (via elan; see `pins/elan.json`)
- Lake project under `lean/`
- PF-Core and PCS Lean sources
- Generated-proof and proof-binding tooling
- Release-bundle tooling (`pcs pf-core bundle-release`)

### OCI image (primary ship vehicle)

Scaffold Dockerfile: [`docker/verifier/Dockerfile`](../docker/verifier/Dockerfile).

```bash
docker build -f docker/verifier/Dockerfile -t pcs-core-verifier:local .
docker run --rm pcs-core-verifier:local capabilities
```

**Image signing (gap until org keys exist)**

1. Build and tag by digest: `docker buildx build --push …` and record the digest in
   release notes.
2. Sign with cosign once SentinelOps-CI signing keys / GitHub OIDC are configured:

```bash
cosign sign --yes ghcr.io/sentinelops-ci/pcs-core-verifier@sha256:<digest>
cosign verify ghcr.io/sentinelops-ci/pcs-core-verifier@sha256:<digest>
```

3. Publish the digest + signature in the GitHub Release assets. Until signing infra is
   live, treat the Dockerfile + pin files as the reproducible build contract.

### Optional full wheel

```bash
bash scripts/build-verifier-wheel.sh
```

Embeds `lean/` and `pins/` under `pcs_core/` for `importlib.resources` style layouts.
Prefer the OCI image for production verifiers.

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
| `pins/certifyedge.json` | CertifyEdge image digest placeholder |
| `pins/github-actions.json` | Immutable Action SHAs |
| `lean/lean-toolchain` | Lean 4 version |
| `rust/Cargo.lock` | Rust dependency lock |
| `typescript/package-lock.json` | npm lock |
| `python/requirements.lock` | Pip constraint lock |
