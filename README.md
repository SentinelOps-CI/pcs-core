# pcs-core

**Proof-Carrying Science (PCS)** — canonical protocol repository for v0.1 artifact schemas, validation, and hash canonicalization.

Single source of truth for LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory. Downstream repos must not fork artifact shapes.

**Documentation index:** [docs/README.md](docs/README.md)  
**v0.1 release checklist:** [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md)

## Release pin

Pin git tag **`v0.1.0`**:

```bash
git clone https://github.com/SentinelOps-CI/pcs-core.git
cd pcs-core && git checkout v0.1.0
```

Root `VERSION` matches the Python package (`0.1.0`).

## Quick start

```bash
cd python && pip install -e ".[dev]"

pcs validate ../examples/science_claim_bundle.certified.valid.json
pcs validate ../examples/signed_science_claim_bundle.valid.json
pcs hash ../examples/science_claim_bundle.certified.valid.json
pcs examples check
pcs schema check
python -m pcs_core.hash_vectors --verify
pcs shared-hash-vectors verify
```

Release verification (CI parity):

```bash
bash scripts/run-release-verify.sh    # Linux/macOS/Git Bash
just release-verify
powershell -File scripts/run-release-verify.ps1   # Windows
```

Full build + lint gate: `just ci` (see [docs/README.md](docs/README.md)).

## v0.1 core artifacts

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

Protocol overview: [docs/protocol.md](docs/protocol.md). Release artifacts: [docs/release-protocol.md](docs/release-protocol.md).

## Workflows

| Workflow | Profile fixture | Release fixtures |
|----------|-----------------|------------------|
| LabTrust QC release | `examples/workflow_profiles/labtrust_qc_release.valid.json` | `examples/labtrust-release/` |
| Agent tool-use safety | `examples/workflow_profiles/agent_tool_use_safety.valid.json` | `examples/tool-use-release/` |
| Scientific computation | `examples/workflow_profiles/scientific_computation_reproducibility.valid.json` | `examples/computation-release/` |

```bash
pcs validate-release-chain ../examples/labtrust-release/
pcs conformance run --suite multidomain
just materialize-protocol
```

LabTrust chain details: [docs/labtrust-release-fixtures.md](docs/labtrust-release-fixtures.md).

## Benchmark ingest

Producers export **`PcsBenchIngest.v0`** (embedded v0 objects; optional **`BenchmarkArtifactRef.v0`** file provenance).

```bash
pcs conformance run --suite benchmark-ingest
pcs benchmark validate-ingest --release-grade
```

Goldens: `examples/benchmark_ingest/`. Guide: [docs/benchmarks.md](docs/benchmarks.md).

## CLI

| Command | Description |
|---------|-------------|
| `pcs validate <file>` | JSON Schema + semantic validation |
| `pcs hash <file>` | Canonical `sha256:` digest |
| `pcs validate-release-chain [dir]` | Release directory consistency |
| `pcs schema check` | Validate all JSON schemas |
| `pcs examples check` | Valid/invalid fixtures |
| `pcs shared-hash-vectors verify` | Cross-language hash vectors |
| `pcs registry validate <file>` | Artifact registry drift check |
| `pcs registry audit` | Semantic check catalog |
| `pcs conformance run --suite <name>` | Protocol conformance suites |
| `pcs benchmark validate` | Benchmark fixtures |
| `pcs benchmark validate-ingest --release-grade` | Producer ingest goldens |
| `pcs benchmark materialize-ingest` | Regenerate ingest examples |
| `pcs explain-status <status>` | Status transition help |
| `pcs migrate --from v0 --to v0 <file>` | Migration report |
| `just pcs-schema-diff <dir>` | Compare vendored schemas |

## Layout

```
schemas/              JSON Schema (Draft 2020-12)
examples/             Valid and invalid fixtures
examples/labtrust-release/   Canonical LabTrust release chain
docs/                 Protocol and integration docs
python/               pcs CLI and validation library
rust/                 Rust bindings
typescript/           @pcs/core package
benchmarks/           Benchmark case trees
conformance/          Conformance suite notes
test_vectors/hash/    Shared cross-language hash vectors
```

## Downstream integration

1. Add pcs-core as a submodule or package dependency; pin tag `v0.1.0`.
2. Validate artifacts with `pcs validate` before publish or import.
3. Hash with `pcs hash` — [docs/hash-canonicalization.md](docs/hash-canonicalization.md).
4. Import schemas from `schemas/`; verify drift with `just pcs-schema-diff` — [docs/downstream-schema-sync.md](docs/downstream-schema-sync.md).
5. Copy `examples/labtrust-release/` for cross-repo release tests; verify with `pcs validate-release-chain`.
6. Run `pcs conformance run --suite <name>` in CI for the workflows you use.

## License

Apache-2.0 — see [LICENSE](LICENSE).
