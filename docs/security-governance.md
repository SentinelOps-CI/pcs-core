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
| Org/infra gate checker | [`pcs release check-gates`](pf-core/operator-release-gates.md), [scripts/check-release-gates.py](../scripts/check-release-gates.py) |
| Mutation testing (deferred) | [docs/mutation-testing.md](mutation-testing.md) |
| Cargo lock enforcement | `cargo … --locked` in CI |
| npm lock enforcement | `npm ci` in CI |
| Python lock | [python/requirements.lock](../python/requirements.lock) |
| SBOM scaffold | [scripts/generate-sbom.sh](../scripts/generate-sbom.sh) |
| Release provenance (SLSA / attestations) | [.github/workflows/release-provenance.yml](../.github/workflows/release-provenance.yml), [scripts/build-release-provenance.sh](../scripts/build-release-provenance.sh), [scripts/verify-release-provenance.sh](../scripts/verify-release-provenance.sh) |
| OCI verifier scaffold | [docker/verifier/Dockerfile](../docker/verifier/Dockerfile) |

## Required status checks (branch protection — org admin)

Configure protection on `main` (and release branches) with **require status checks to pass**
and **require branches to be up to date**. Prefer the aggregator checks, or require each matrix job
(see [pf-core/release-checklist.md](pf-core/release-checklist.md) mandatory CI matrix):

| Job / workflow | Workflow file | Purpose |
|----------------|---------------|---------|
| `CI matrix gate` | `ci.yml` | Aggregates mandatory PR CI matrix |
| `Distribution matrix gate` | `distribution.yml` | Validator/verifier wheel + OCI clean execution |
| `Python full tests` | `ci.yml` | Full pytest + schemas/conformance/benchmarks |
| `Python full-package typecheck` | `ci.yml` | Full-package pyright |
| `Python branch coverage` | `ci.yml` | Branch coverage (trust-critical fail-under) |
| `Rust fmt/clippy/tests/fuzz-smoke` | `ci.yml` | Rust quality + proptest smoke |
| `TypeScript lint/tests/property-vectors` | `ci.yml` | TS lint/tests/hash vectors |
| `Lean PCS build` / `Lean PF-Core build` | `ci.yml` | Split lake builds + PF-Core lean-check |
| `Certificate-mode end-to-end` | `ci.yml` | All mode evidence e2e suites |
| `Cross-language differential` | `ci.yml` | Python/Rust/TS differential |
| `Semantic-projection replay` | `ci.yml` | Projection replay |
| `Theorem-manifest replay` | `ci.yml` | Theorem manifest replay |
| `Scientific payload mutation` | `ci.yml` | ResultArtifact mutation fixtures |
| `Signature and key-revocation` | `ci.yml` | Ed25519 integrity + revocation |
| `Preview release workflow` | `ci.yml` | Preview lean-check→bundle→absence |
| `Stable release dry-run` | `ci.yml` | Stable dry-run (live checker org-gated) |
| `Provenance verification` | `ci.yml` | Provenance digest binding (signed org-gated) |
| `PF-Core adapter parity` | `ci.yml` | Adapter parity (required on `main`) |
| `Validate CLI contract` | `ci.yml` | CLI contract smoke |
| `validate-release-chain` | `release-chain.yml` | LabTrust release-chain gate |
| `analyze` | `codeql.yml` | CodeQL |

**Org-gated (not fail-closed on every PR without secrets):** live CertifyEdge
(`secrets.PF_CORE_CERTIFYEDGE_CLI` + `pins/certifyedge.json` status=`pinned`), signed GitHub
attestations (GHEC / OIDC), and published signed OCI verifier images (cosign keys).

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

## SLSA provenance (GitHub artifact attestations)

`release-provenance.yml` builds release subjects (wheels, SBOM, lockfile copies,
verifier image pin, optional PF-Core release-bundle archive) and emits
`ReleaseProvenanceBinding.v0` binding:

| Binding | Source |
|---------|--------|
| Source commit | `GITHUB_SHA` / git HEAD |
| Workflow identity | `GITHUB_WORKFLOW_REF` + run id |
| Builder identity | Actions run URL + runner metadata |
| Lockfiles | `python/requirements.lock`, `rust/Cargo.lock`, `typescript/package-lock.json` |
| Verifier image digest | `pins/python-base-image.json` index digest |
| Wheel digests | Built `pcs_core-*.whl` |
| SBOM digest | `dist/sbom/pcs-core.cdx.json` |
| Bundle root digest | Archive SHA-256 + manifest `signature_or_digest` when bundle present |

Signed provenance uses `actions/attest-build-provenance` + `actions/attest-sbom`
(Sigstore keyless via GitHub OIDC). A clean **consumer-verify** job downloads only
the provenance artifact and runs `scripts/verify-release-provenance.sh` (digest
checks + `gh attestation verify` when `attestation.status=signed`).

### Fail-closed honesty (gated)

If attestations cannot be created (private repo without GitHub Enterprise Cloud,
missing `id-token`/`attestations` permissions, org OIDC policy), the workflow
sets `attestation.status=gated`, writes `PROVENANCE_ATTESTATION_GATED.json`, and
**does not** claim signed SLSA provenance. Tag / stable-release runs fail unless
repository variable `PCS_PROVENANCE_ALLOW_GATED=true` is set while org setup is
incomplete.

`release.yml` publishes the same binding into the release artifact upload and
runs the consumer verification job after the unified gate.

## Gaps requiring org admin / external infra

Operator how-to: [pf-core/operator-release-gates.md](pf-core/operator-release-gates.md)
(`pcs release check-gates --mode release`).

1. Enable branch protection + required checks listed above.
2. Enable secret scanning / push protection.
3. Provision cosign/sigstore keys (or GitHub OIDC) for OCI image signing.
4. Replace `pins/certifyedge.json` (`status=unpinned`) with a real immutable CertifyEdge
   artifact (`status=pinned`, `provision_strategy=oci_digest|signed_binary|source_commit_build`).
   Do not invent placeholder digests. Until then, release mode fails closed; preview may use
   absence notices or `dev_fixture` (untrusted_development) for machinery tests only.
5. Enable GitHub artifact attestations for private repos (GitHub Enterprise Cloud) if
   the repository is private; public repos can attest on current plans. Clear
   `PCS_PROVENANCE_ALLOW_GATED` once signed provenance is green on version tags.
6. Provision org ed25519 release / CertifyEdge signing keys and publish a
   `TrustedKeyRegistry.v0` allowlist so stable releases can require
   `authentication_mode=ed25519_signed` instead of digest-bound integrity.
