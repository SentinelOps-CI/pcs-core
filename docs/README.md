# PCS documentation (v0.1)

Proof-Carrying Science (**PCS**) is a cross-repository artifact protocol for binding scientific and operational claims to verifiable evidence. **pcs-core** is the reference implementation: JSON schemas, validation, canonical hashing, release-chain checks, and conformance suites.

Downstream repositories (LabTrust-Gym, CertifyEdge, Provability Fabric, Scientific Memory) import artifacts from here and must not fork schema shapes.

## Who should read what

| You are… | Start here |
|----------|------------|
| New to PCS | [protocol.md](protocol.md), [trust-model.md](trust-model.md) |
| Integrating a service | [downstream-schema-sync.md](downstream-schema-sync.md), [hash-canonicalization.md](hash-canonicalization.md) |
| Running a release train | [release-protocol.md](release-protocol.md), [labtrust-release-fixtures.md](labtrust-release-fixtures.md), [releases/v0.1.0.md](releases/v0.1.0.md) |
| Publishing benchmarks | [benchmarks.md](benchmarks.md), [benchmark-ingest-contract.md](benchmark-ingest-contract.md), [producer-benchmark-ingest.md](producer-benchmark-ingest.md) |
| Auditing evidence | [labtrust-release-fixtures.md](labtrust-release-fixtures.md), [semantic-check-policy.md](semantic-check-policy.md) |

## Core guides

| Topic | Document |
|-------|----------|
| Protocol overview | [protocol.md](protocol.md) |
| Trust and guarantee types | [trust-model.md](trust-model.md) |
| Release artifacts | [release-protocol.md](release-protocol.md) |
| LabTrust QC release chain | [labtrust-release-fixtures.md](labtrust-release-fixtures.md) |
| LabTrust workflow profile | [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md) |
| Workflow profiles (all domains) | [workflow-profiles.md](workflow-profiles.md) |
| Benchmarks | [benchmarks.md](benchmarks.md) |
| Canonical hashing | [hash-canonicalization.md](hash-canonicalization.md) |
| Vendoring schemas | [downstream-schema-sync.md](downstream-schema-sync.md) |
| Conformance suites | [../conformance/README.md](../conformance/README.md) |

## v0.1 release verification

Pin git tag **`v0.1.0`** (root `VERSION` and [releases/v0.1.0.md](releases/v0.1.0.md)).

```bash
cd python && pip install -e ".[dev]"

pcs schema check
pcs examples check
pcs shared-hash-vectors verify
pcs validate-release-chain ../examples/labtrust-release/
pcs conformance run --suite all
pcs benchmark validate-ingest --release-grade
```

One-command gate:

| Platform | Command |
|----------|---------|
| Linux / macOS / Git Bash | `bash scripts/run-release-verify.sh` or `just release-verify` |
| Windows | `powershell -File scripts/run-release-verify.ps1` |
| Full CI (build + lint) | `just ci` |

## Policy reference

| Document | Purpose |
|----------|---------|
| [artifact-lifecycle.md](artifact-lifecycle.md) | Status values and typical flows |
| [artifact-registry.md](artifact-registry.md) | `ArtifactRegistry.v0` |
| [semantic-check-policy.md](semantic-check-policy.md) | Registry semantic checks |
| [status-transition-policy.md](status-transition-policy.md) | Allowed status changes |
| [migration-policy.md](migration-policy.md) | Version migrations |
| [versioning.md](versioning.md) | `schema_version` rules |
| [lean-trust-kernel.md](lean-trust-kernel.md) | Lean formal checks |

## Repository layout

| Path | Contents |
|------|----------|
| `schemas/` | Normative JSON Schema (Draft 2020-12) |
| `examples/` | Valid and invalid fixtures |
| `examples/labtrust/` | Schema conformance only (not release evidence) |
| `examples/labtrust-release/` | Canonical LabTrust release chain |
| `examples/tool-use-release/` | Tool-use safety release fixtures |
| `examples/computation-release/` | Computation reproducibility fixtures |
| `examples/benchmark_ingest/` | Producer `PcsBenchIngest.v0` goldens |
| `benchmarks/` | Executable benchmark case trees |
| `test_vectors/hash/` | Cross-language canonical hash vectors |
