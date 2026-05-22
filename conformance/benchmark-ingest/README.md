# Benchmark ingest conformance suite

Validates the cross-repo **`PcsBenchIngest.v0`** contract: embedded canonical objects, optional **`BenchmarkArtifactRef.v0`** provenance, producer golden bundles, and dialect normalization drift.

## Run

```bash
pcs conformance run --suite benchmark-ingest
pcs benchmark validate
pcs benchmark materialize-ingest
```

## What is checked

| Check | Location |
|-------|----------|
| Producer ingest bundles | `examples/benchmark_ingest/*.pcs_bench_ingest.valid.json` |
| Standalone artifact ref | `examples/benchmarks/benchmark_artifact_ref.valid.json` |
| Embedded artifact types | `examples/benchmarks/benchmark_run.valid.json`, coverage, explain/profile, metric summary, failure localization |
| Normalized dialect ingests | `examples/benchmarks/compatibility/*.pcs_bench_ingest.normalized.json` |
| Compatibility corpus | `pcs_core.benchmark_compat.validate_compatibility_corpus()` |

## Producer requirements

Repos that export file-oriented benchmark output (Scientific Memory, CertifyEdge, Provability Fabric, LabTrust-Gym) must:

1. Embed full v0 objects in ingest arrays (not path-only payloads).
2. Add `artifact_refs` with `path`, `sha256` (matching embedded `signature_or_digest`), and provenance.
3. Regenerate golden JSON via pcs-core normalizers from captured dialect fixtures.

See [docs/benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md), [docs/release-grade-benchmark-evidence.md](../../docs/release-grade-benchmark-evidence.md), and [docs/producer-benchmark-ingest.md](../../docs/producer-benchmark-ingest.md).

## Invalid fixtures

These must fail `pcs validate` (semantic ref contract, zero commit, or empty runs with orphan refs):

- `invalid_pcs_bench_ingest_missing_refs.json`
- `invalid_pcs_bench_ingest_bad_ref_digest.json`
- `invalid_pcs_bench_ingest_zero_commit.json`
- `invalid_pcs_bench_ingest_empty_runs.json`
- `invalid_pcs_bench_ingest_path_only.json`

Golden bundles must pass with `--release-grade` (non-placeholder commit, producer-specific non-empty arrays, bidirectional `artifact_refs`). All four producer goldens are copied from sibling `make pcs-bench-producer` exports when available.
