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
| ReleaseManifest.v0 | `schemas/ReleaseManifest.v0.schema.json` |
| HandoffManifest.v0 | `schemas/HandoffManifest.v0.schema.json` |
| ReleaseChainValidationResult.v0 | `schemas/ReleaseChainValidationResult.v0.schema.json` |
| WorkflowProfile.v0 | `schemas/WorkflowProfile.v0.schema.json` |
| ToolUseTrace.v0 | `schemas/ToolUseTrace.v0.schema.json` |
| ToolUseCertificate.v0 | `schemas/ToolUseCertificate.v0.schema.json` |

## Multi-domain workflows (v0.1 extension)

Workflows are declared in `WorkflowProfile.v0` (see [docs/workflow-profiles.md](docs/workflow-profiles.md)):

| Workflow | Profile | Conformance train |
|----------|---------|-------------------|
| LabTrust QC release | `examples/workflow_profiles/labtrust_qc_release.valid.json` | `examples/labtrust-release/` |
| Agent tool-use safety | `examples/workflow_profiles/agent_tool_use_safety.valid.json` | `examples/tool-use-release/` |

```bash
pcs conformance run --suite workflow-profile
pcs conformance run --suite tool-use
pcs conformance run --suite multidomain
just materialize-protocol
```

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

## PCS v0.1 release-candidate fixtures

**Canonical set:** [`examples/labtrust-release/`](examples/labtrust-release/) with [`RELEASE_FIXTURE_MANIFEST.json`](examples/labtrust-release/RELEASE_FIXTURE_MANIFEST.json) and Phase 2 protocol artifacts (`release_manifest.v0.json`, handoff manifests, `release_chain_validation_result.v0.json`). See [docs/protocol-phase2.md](docs/protocol-phase2.md).

Downstream repos must sync against this directory or prove canonical-hash equivalence to the manifest (do not partially regenerate). Pin values and the 30-check validator: [docs/labtrust-rc-canonical.md](docs/labtrust-rc-canonical.md). RC tag checklist: [docs/releases/pcs-v0.1.0-rc1.md](docs/releases/pcs-v0.1.0-rc1.md).

```bash
pcs validate-release-chain examples/labtrust-release/
just validate-labtrust-release-fixtures
```

## Benchmark ingest (cross-repo)

Producer repos export **`PcsBenchIngest.v0`** to pcs-bench: embedded v0 objects plus optional **`BenchmarkArtifactRef.v0`** file provenance.

```bash
pcs conformance run --suite benchmark-ingest
pcs benchmark materialize-ingest
pcs benchmark validate
```

Goldens: `examples/benchmark_ingest/` (sync from sibling `make pcs-bench-producer`; set `PCS_PRODUCER_REPOS_ROOT` if repos are not parent siblings). Spec: [docs/benchmark-ingest-contract.md](docs/benchmark-ingest-contract.md), [docs/release-grade-benchmark-evidence.md](docs/release-grade-benchmark-evidence.md), [docs/producer-benchmark-ingest.md](docs/producer-benchmark-ingest.md).

## CLI

| Command | Description |
|---------|-------------|
| `pcs validate <file>` | JSON Schema + semantic validation |
| `pcs hash <file>` | Canonical `sha256:` digest |
| `pcs validate-release-chain [dir]` | Atomic LabTrust RC chain consistency (default: `examples/labtrust-release/`) |
| `pcs schema check` | Validate all JSON schemas |
| `pcs examples check` | Validate valid/invalid fixtures |
| `pcs hash-vectors verify` | Verify frozen canonical hash vectors |
| `pcs shared-hash-vectors verify` | Verify cross-language vectors in `test_vectors/hash/` |
| `pcs registry list` | List registered PCS artifact types |
| `pcs registry validate <file>` | Validate `ArtifactRegistry.v0` drift |
| `pcs conformance run --suite <name>` | Protocol conformance (`multidomain`, `tool-use`, `benchmark-ingest`, …) |
| `pcs benchmark materialize-ingest` | Regenerate `examples/benchmark_ingest/` from sibling producer exports (dialect fallback) |
| `pcs benchmark validate` | Benchmark fixtures + ingest contract |
| `pcs shared-hash-vectors verify` | Cross-language hash parity (`test_vectors/hash/`) |
| `pcs explain-status <status>` | Explain status transitions |
| `pcs migrate --from v0 --to v0 <file>` | Identity migration report |
| `just pcs-schema-diff <dir>` | Compare vendored schemas to pcs-core |

## Layout

```
schemas/          JSON Schema (Draft 2020-12)
examples/         Valid and invalid fixtures
examples/labtrust/          Schema conformance fixtures (stable `pcs validate` examples)
examples/labtrust-release/  Generated release evidence (`RELEASE_FIXTURE_MANIFEST.json`)
docs/             Protocol, trust model, LabTrust profile
python/           `pcs` CLI and validation library
rust/             Rust bindings (semantic checks + hash)
typescript/       `@pcs/core` package
python/tests/hash_vectors/   Frozen canonical hash test vectors
test_vectors/hash/           Shared cross-language hash vectors
```

## Downstream integration

1. Add **pcs-core** as a git submodule or package dependency.
2. Validate artifacts with `pcs validate` before publish/import.
3. Hash with `pcs hash` — see [docs/hash-canonicalization.md](docs/hash-canonicalization.md).
4. Import schemas from `schemas/`; pin by release tag.
5. Follow [docs/downstream-schema-sync.md](docs/downstream-schema-sync.md) for vendoring and `just pcs-schema-diff`.
6. Validate cross-repo fixtures under `examples/labtrust/`.
7. Follow [docs/labtrust-v0.1-profile.md](docs/labtrust-v0.1-profile.md) for the QC-release workflow.
8. Run the **PCS v0.1 clean-checkout chain** from LabTrust-Gym (`scripts/run-pcs-v01-clean-chain.ps1` here delegates to the sibling repo).
9. Copy [`examples/labtrust-release/`](examples/labtrust-release/) for cross-repo release fixture tests; verify with `pcs validate-release-chain`.

## License

Apache-2.0 — see [LICENSE](LICENSE).
