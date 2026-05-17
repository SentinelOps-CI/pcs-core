# pcs-core

**Proof-Carrying Science (PCS)** — canonical protocol repository for v0.1 artifact schemas, validation, and hash canonicalization.

This repo is the single source of truth for LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory. Downstream repos must not fork artifact shapes.

## v0.1 artifacts

| Artifact | Schema |
|----------|--------|
| AssumptionSet.v0 | `schemas/AssumptionSet.v0.schema.json` |
| SourceSpan.v0 | `schemas/SourceSpan.v0.schema.json` |
| ClaimArtifact.v0 | `schemas/ClaimArtifact.v0.schema.json` |
| RuntimeReceipt.v0 | `schemas/RuntimeReceipt.v0.schema.json` |
| TraceCertificate.v0 | `schemas/TraceCertificate.v0.schema.json` |
| EvidenceBundle.v0 | `schemas/EvidenceBundle.v0.schema.json` |
| ScienceClaimBundle.v0 | `schemas/ScienceClaimBundle.v0.schema.json` |
| VerificationResult.v0 | `schemas/VerificationResult.v0.schema.json` |
| SignedScienceClaimBundle.v0 | `schemas/SignedScienceClaimBundle.v0.schema.json` |

## Release pin

Downstream repos should pin git tag **`v0.1.0`**:

```bash
git clone https://github.com/SentinelOps-CI/pcs-core.git
cd pcs-core && git checkout v0.1.0
```

The repo root `VERSION` file matches the Python package version (`0.1.0`).

## Quick start

```bash
cd python && pip install -e ".[dev]"

pcs validate ../examples/science_claim_bundle.certified.valid.json
pcs validate ../examples/signed_science_claim_bundle.valid.json
pcs validate ../examples/labtrust/signed_science_claim_bundle.valid.json
pcs hash ../examples/science_claim_bundle.certified.valid.json
pcs examples check
pcs schema check
python -m pcs_core.hash_vectors --verify
just pcs-schema-diff schemas

just ci
```

## CLI

| Command | Description |
|---------|-------------|
| `pcs validate <file>` | JSON Schema + semantic validation |
| `pcs hash <file>` | Canonical `sha256:` digest |
| `pcs schema check` | Validate all JSON schemas |
| `pcs examples check` | Validate valid/invalid fixtures |
| `pcs hash-vectors verify` | Verify frozen canonical hash vectors |
| `just pcs-schema-diff <dir>` | Compare vendored schemas to pcs-core |

## Layout

```
schemas/          JSON Schema (Draft 2020-12)
examples/         Valid and invalid fixtures
examples/labtrust/  Cross-repo conformance fixtures (LabTrust → PF → SM)
docs/             Protocol, trust model, LabTrust profile
python/           `pcs` CLI and validation library
rust/             Rust bindings (semantic checks + hash)
typescript/       `@pcs/core` package
python/tests/hash_vectors/   Frozen canonical hash test vectors
```

## Downstream integration

1. Add **pcs-core** as a git submodule or package dependency.
2. Validate artifacts with `pcs validate` before publish/import.
3. Hash with `pcs hash` — see [docs/hash-canonicalization.md](docs/hash-canonicalization.md).
4. Import schemas from `schemas/`; pin by release tag.
5. Follow [docs/downstream-schema-sync.md](docs/downstream-schema-sync.md) for vendoring and `just pcs-schema-diff`.
6. Validate cross-repo fixtures under `examples/labtrust/`.
7. Follow [docs/labtrust-v0.1-profile.md](docs/labtrust-v0.1-profile.md) for the QC-release workflow.

## License

Apache-2.0 — see [LICENSE](LICENSE).
