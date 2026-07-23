# Security governance (Phase 2)

This document records controls that live in the repository and those that require
GitHub organization administrator action. Repository files cannot enable org-level
branch protection by themselves.

## In-repo controls

| Control | Location |
|---------|----------|
| Vulnerability reporting | [SECURITY.md](../SECURITY.md) |
| CODEOWNERS | [.github/CODEOWNERS](../.github/CODEOWNERS) |
| Dependabot | [.github/dependabot.yml](../.github/dependabot.yml) |
| CodeQL | [.github/workflows/codeql.yml](../.github/workflows/codeql.yml) |
| Action SHA pins | [pins/github-actions.json](../pins/github-actions.json) + workflows |
| Elan checksum | [pins/elan.json](../pins/elan.json), [scripts/install-elan-verified.sh](../scripts/install-elan-verified.sh) |
| CertifyEdge pin + provision | [pins/certifyedge.json](../pins/certifyedge.json), [scripts/verify-certifyedge-pin.py](../scripts/verify-certifyedge-pin.py), [scripts/provision-certifyedge.sh](../scripts/provision-certifyedge.sh) |
| External attestation schema | [schemas/ExternalAttestation.v0.schema.json](../schemas/ExternalAttestation.v0.schema.json) |
| Unified release gate | [.github/workflows/release.yml](../.github/workflows/release.yml) (`PCS_RELEASE_MODE=release\|preview`) |
| Mutation testing (deferred) | [docs/mutation-testing.md](mutation-testing.md) |
| Cargo lock enforcement | `cargo … --locked` in CI |
| npm lock enforcement | `npm ci` in CI |
| Python lock | [python/requirements.lock](../python/requirements.lock) |
| SBOM scaffold | [scripts/generate-sbom.sh](../scripts/generate-sbom.sh) |
| SLSA scaffold | [.github/workflows/release-provenance.yml](../.github/workflows/release-provenance.yml) |
| OCI verifier scaffold | [docker/verifier/Dockerfile](../docker/verifier/Dockerfile) |

## Required status checks (branch protection — org admin)

Configure protection on `main` (and release branches) with **require status checks to pass**
and **require branches to be up to date**. Required job names from CI:

| Job / workflow | Workflow file | Purpose |
|----------------|---------------|---------|
| `python` | `ci.yml` | Schema, semantic, conformance, benchmarks |
| `lean` | `ci.yml` | Lake build + PF-Core lean-check |
| `rust` | `ci.yml` | Rust validator + hash vectors |
| `typescript` | `ci.yml` | TypeScript validator + lint |
| `pf-core-adapter` | `ci.yml` | Adapter parity (required on `main`) |
| `validate-cli-contract` | `ci.yml` | CLI contract smoke |
| `validate-release-chain` | `release-chain.yml` | LabTrust release-chain gate |
| `analyze` | `codeql.yml` | CodeQL |

Also recommended: require CODEOWNERS review, dismiss stale reviews, and disallow force pushes.

## Signed release tags

See [SECURITY.md](../SECURITY.md). Release workflow [release.yml](../.github/workflows/release.yml)
verifies the tag matches `VERSION`. Prefer annotated GPG/SSH-signed tags.

## Secret scanning

Enable GitHub **secret scanning** and **push protection** for `SentinelOps-CI/pcs-core`.
Local option: `gitleaks detect --source .`. Do not commit signing keys or CertifyEdge
credentials; use repository secrets for `PF_CORE_CERTIFYEDGE_CLI` paths only when needed.

## Artifact retention policy

| Artifact class | Retention | Notes |
|----------------|-----------|-------|
| GitHub Actions logs | 90 days (default) | Increase only if audit requires |
| CI build caches | 7 days | Ephemeral |
| GitHub Release assets (wheels, SBOM, provenance) | Indefinite while tag exists | Prefer digest-addressed OCI |
| Benchmark / conformance reports in PRs | Ephemeral (workflow logs) | Do not publish secrets |
| Signed OCI verifier images | Per registry policy (recommend ≥ 1 year) | Pin by digest |

Document any longer legal hold in the corresponding GitHub Release notes.

## SLSA provenance (scaffold)

`release-provenance.yml` attaches provenance scaffolding on version tags. Full SLSA
Build L3 generators (for example official slsa-github-generator) require org trust
setup; until then the workflow emits a provenance statement stub and SBOM alongside
release verification.

## Gaps requiring org admin / external infra

1. Enable branch protection + required checks listed above.
2. Enable secret scanning / push protection.
3. Provision cosign/sigstore keys (or GitHub OIDC) for OCI image signing.
4. Replace `pins/certifyedge.json` placeholders with a real image digest (`status=pinned`, `provision_strategy=oci_digest|signed_binary|source_commit_build`).
5. Optional: attach official SLSA generator once org permissions allow.
6. Provision ed25519 release / CertifyEdge signing keys so `ExternalAttestation.v0` can use `authentication_mode=ed25519_signed` instead of digest-bound integrity.
