# PCS documentation (v0.1)

Proof-Carrying Science (**PCS**) is a cross-repository artifact protocol. **pcs-core** owns schemas, validation, canonical hashing, and conformance suites. Downstream repositories import artifacts from here; they must not fork schema shapes.

## Start here

| Topic | Document |
|-------|----------|
| Protocol overview | [protocol.md](protocol.md) |
| Release fixtures and validation | [release-protocol.md](release-protocol.md) |
| LabTrust QC release chain | [labtrust-release-fixtures.md](labtrust-release-fixtures.md) |
| Workflow profiles | [workflow-profiles.md](workflow-profiles.md) |
| Benchmarks (suites, ingest, producers) | [benchmarks.md](benchmarks.md) |
| Hashing | [hash-canonicalization.md](hash-canonicalization.md) |
| Vendoring schemas in other repos | [downstream-schema-sync.md](downstream-schema-sync.md) |
| Conformance suites | [../conformance/README.md](../conformance/README.md) |

## v0.1 release checklist

Pin tag **`v0.1.0`** (see root `VERSION` and [releases/v0.1.0.md](releases/v0.1.0.md)).

```bash
cd python && pip install -e ".[dev]"

# Core validation
pcs schema check
pcs examples check
python -m pcs_core.hash_vectors --verify
pcs shared-hash-vectors verify

# Release chains
pcs validate-release-chain ../examples/labtrust-release/
pcs validate-release-chain ../examples/tool-use-release/
pcs validate-release-chain ../examples/computation-release/

# Conformance
pcs conformance run --suite all
pcs conformance run --suite multidomain
pcs conformance run --suite benchmark-ingest
pcs conformance run --suite benchmark-report

# Benchmarks
pcs benchmark validate
pcs benchmark validate-ingest --release-grade
python ../scripts/validate_benchmark_ingest_examples.py --release-grade

# Registry
pcs registry validate ../examples/artifact_registry.valid.json
pcs registry audit
```

Full local gate (Linux/macOS/Git Bash): `just ci` from the repository root.

Windows: `powershell -File scripts/run-release-verify.ps1` from the repository root (CI parity: all suites, benchmark runs, materialize, Rust/TS lint).

## Policy and reference

| Document | Purpose |
|----------|---------|
| [artifact-lifecycle.md](artifact-lifecycle.md) | Draft → validated → deprecated |
| [artifact-registry.md](artifact-registry.md) | `ArtifactRegistry.v0` |
| [semantic-check-policy.md](semantic-check-policy.md) | Registry semantic checks |
| [status-transition-policy.md](status-transition-policy.md) | Allowed status changes |
| [migration-policy.md](migration-policy.md) | Version migrations |
| [versioning.md](versioning.md) | `schema_version` rules |
| [trust-model.md](trust-model.md) | Guarantee types |
| [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md) | LabTrust QC workflow profile |
| [lean-trust-kernel.md](lean-trust-kernel.md) | Lean formal checks |

## Examples layout

| Directory | Contents |
|-----------|----------|
| `examples/` | Valid and invalid schema fixtures |
| `examples/labtrust-release/` | Canonical LabTrust release chain (do not hand-edit) |
| `examples/tool-use-release/` | Tool-use safety release fixtures |
| `examples/computation-release/` | Computation reproducibility fixtures |
| `examples/benchmark_ingest/` | Producer `PcsBenchIngest.v0` goldens |
| `benchmarks/` | Executable benchmark case trees |
