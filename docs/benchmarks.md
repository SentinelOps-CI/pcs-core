# Benchmarks

PCS benchmarks treat cases as the definition of what to test, runs as the record of what happened, ingest as the producer export bundle, and reports as the suite-level score aggregation, and all shapes are frozen at v0 while downstream tools normalize dialect JSON into these artifacts.

## Documents

| Document | When to read |
|----------|----------------|
| [benchmark-ingest-contract.md](benchmark-ingest-contract.md) | Exporting or validating `PcsBenchIngest.v0` |
| [producer-benchmark-ingest.md](producer-benchmark-ingest.md) | Wiring `make pcs-bench-producer` in a producer repository |
| [benchmark-object-model.md](benchmark-object-model.md) | Status fields and metric rollups |
| [benchmark-registry.md](benchmark-registry.md) | Suite IDs, case layout, conformance suites |
| [benchmark-metrics.md](benchmark-metrics.md) | Metric IDs and thresholds |

## Schema types (v0)

| Schema | Role |
|--------|------|
| `BenchmarkTask.v0` | Evaluation goal and success criteria |
| `BenchmarkCase.v0` | One case with inputs and expected outcome |
| `BenchmarkRun.v0` | One execution of a case |
| `BenchmarkReport.v0` | Suite aggregation with `metric_summaries` |
| `MetricSummary.v0` | One measured metric |
| `PcsBenchIngest.v0` | Producer export bundle with embedded objects and optional refs |
| `BenchmarkArtifactRef.v0` | On-disk path and digest for one embedded artifact |
| `CoverageReport.v0` | Single-metric coverage |
| `FailureLocalizationResult.v0` | Failure code and repair hint |
| `ExplainQualityReport.v0` | Explainability and interpretability quality |
| `ProfileCoverageReport.v0` | Workflow profile field coverage |
| `BenchmarkRegistry.v0` | Registered suites and cases |
| `BenchmarkMetricRegistry.v0` | Canonical metric definitions |
| `FailureCaseManifest.v0` | Expected failure metadata for invalid cases |
| `ConformanceRun.v0` | Conformance suite bridge |

Required field names remain stable until a new `schema_version` ships, and digests always use pcs-core canonical hashing.

## Producer ingest (summary)

Embedded arrays carry the authoritative full v0 objects inside `benchmark_runs`, `coverage_reports`, and related arrays, while `artifact_refs` supply optional sidecar provenance where each `path` and `sha256` pair must match the embedded object digest.

Path-only arrays fail validation under v0 semantics.

Golden bundles live at `examples/benchmark_ingest/<producer>.pcs_bench_ingest.valid.json` and maintainers refresh them through materialize scripts instead of manual edits.

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

Fixture roots include `examples/benchmarks/`, `examples/benchmark/`, `examples/benchmark_ingest/`, and `benchmarks/<suite>/`, while dialect captures appear under `examples/benchmarks/compatibility/*.dialect.json`.

Further detail appears in [../examples/benchmark_ingest/README.md](../examples/benchmark_ingest/README.md) and [../benchmarks/README.md](../benchmarks/README.md).
