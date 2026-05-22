# Benchmarks

PCS benchmarks separate **cases** (what to test), **runs** (what happened), **ingest** (producer exports), and **reports** (suite scores). Schemas are frozen at **v0**; downstream tools normalize dialect JSON into these shapes.

## Documents

| Document | When to read |
|----------|----------------|
| [benchmark-ingest-contract.md](benchmark-ingest-contract.md) | Exporting or validating `PcsBenchIngest.v0` |
| [producer-benchmark-ingest.md](producer-benchmark-ingest.md) | Wiring `make pcs-bench-producer` in a producer repo |
| [benchmark-object-model.md](benchmark-object-model.md) | Status fields and metric rollups |
| [benchmark-registry.md](benchmark-registry.md) | Suite IDs, case layout, conformance suites |
| [benchmark-metrics.md](benchmark-metrics.md) | Metric IDs and thresholds |

## Schema types (v0)

| Schema | Role |
|--------|------|
| `BenchmarkTask.v0` | Evaluation goal and success criteria |
| `BenchmarkCase.v0` | One case: inputs and expected outcome |
| `BenchmarkRun.v0` | One execution of a case |
| `BenchmarkReport.v0` | Suite aggregation with `metric_summaries` |
| `MetricSummary.v0` | One measured metric |
| `PcsBenchIngest.v0` | Producer export bundle (embedded objects + optional refs) |
| `BenchmarkArtifactRef.v0` | On-disk path and digest for one embedded artifact |
| `CoverageReport.v0` | Single-metric coverage |
| `FailureLocalizationResult.v0` | Failure code and repair hint |
| `ExplainQualityReport.v0` | Explainability / interpretability quality |
| `ProfileCoverageReport.v0` | Workflow profile field coverage |
| `BenchmarkRegistry.v0` | Registered suites and cases |
| `BenchmarkMetricRegistry.v0` | Canonical metric definitions |
| `FailureCaseManifest.v0` | Expected failure metadata for invalid cases |
| `ConformanceRun.v0` | Conformance suite bridge |

Stability: no required field renames without a new `schema_version`. Digests use pcs-core canonical hashing.

## Producer ingest (summary)

- **Embedded arrays are authoritative** — full v0 objects in `benchmark_runs`, `coverage_reports`, and related arrays.
- **`artifact_refs` are optional sidecar provenance** — `path` + `sha256` must match the embedded object digest.
- **Path-only arrays are invalid.**

Goldens: `examples/benchmark_ingest/<producer>.pcs_bench_ingest.valid.json` (regenerate; do not hand-edit).

## Validate

```bash
cd python
pcs benchmark validate
pcs benchmark validate-ingest --release-grade
pcs conformance run --suite benchmark-ingest
pcs conformance run --suite benchmark-report
pcs conformance run --suite benchmark
python ../scripts/validate_benchmark_ingest_examples.py --release-grade
python scripts/materialize_benchmark_producer_examples.py   # refresh goldens
```

Fixture roots: `examples/benchmarks/`, `examples/benchmark/`, `examples/benchmark_ingest/`, `benchmarks/<suite>/`. Dialect captures: `examples/benchmarks/compatibility/*.dialect.json`.

See [../examples/benchmark_ingest/README.md](../examples/benchmark_ingest/README.md) and [../benchmarks/README.md](../benchmarks/README.md).
