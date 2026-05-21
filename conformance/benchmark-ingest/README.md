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

See [docs/benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md) and [docs/producer-benchmark-ingest.md](../../docs/producer-benchmark-ingest.md).

## Invalid fixtures

`examples/invalid_pcs_bench_ingest_*.json` must fail `pcs validate` (semantic ref contract).
