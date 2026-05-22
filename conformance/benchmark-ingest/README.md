# Benchmark ingest conformance suite

The benchmark-ingest suite validates the cross-repo `PcsBenchIngest.v0` contract across embedded canonical objects, optional `BenchmarkArtifactRef.v0` provenance, producer golden bundles, and dialect normalization drift.

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

Repositories that export file-oriented benchmark output, including Scientific Memory, CertifyEdge, Provability Fabric, and LabTrust-Gym, embed full v0 objects in ingest arrays, add `artifact_refs` with `path`, `sha256` matching embedded `signature_or_digest`, and provenance fields, and regenerate golden JSON through pcs-core normalizers from captured dialect fixtures.

Further detail appears in [docs/benchmarks.md](../../docs/benchmarks.md), [docs/benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md), and [docs/producer-benchmark-ingest.md](../../docs/producer-benchmark-ingest.md).

## Invalid fixtures

The following fixtures must fail `pcs validate` because they exercise semantic ref contract violations, zero commit values, or empty runs with orphan refs.

- `invalid_pcs_bench_ingest_missing_refs.json`
- `invalid_pcs_bench_ingest_bad_ref_digest.json`
- `invalid_pcs_bench_ingest_zero_commit.json`
- `invalid_pcs_bench_ingest_empty_runs.json`
- `invalid_pcs_bench_ingest_path_only.json`

Golden bundles must pass with `--release-grade`, including non-placeholder commit values, producer-specific non-empty arrays, and bidirectional `artifact_refs`, and all four producer goldens copy from sibling `make pcs-bench-producer` exports when those exports are available.
