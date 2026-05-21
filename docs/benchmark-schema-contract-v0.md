# Benchmark schema contract (v0 frozen)

PCS benchmark artifacts are **frozen at v0** for cross-repo alignment. Downstream repos (pcs-bench, Provability Fabric, CertifyEdge, LabTrust-Gym, Scientific Memory) must normalize outputs to these schemas before claiming benchmark compatibility.

## Core artifacts

| Schema | Role |
|--------|------|
| `BenchmarkTask.v0` | Evaluation goal, metrics, success criteria |
| `BenchmarkCase.v0` | One case: inputs, expected status, failure code, responsible component, repair hint |
| `BenchmarkRun.v0` | Observed execution of one case |
| `BenchmarkReport.v0` | Suite aggregation: declared metric IDs, `metric_summaries`, summary, coverage, failures |
| `MetricSummary.v0` | One measured metric with applicability |
| `PcsBenchIngest.v0` | Normalized producer export for pcs-bench ingestion (embedded objects + optional `artifact_refs`) |
| `BenchmarkArtifactRef.v0` | On-disk path and content digest for one embedded ingest artifact |
| `FailureCaseManifest.v0` | Expected failure metadata for invalid cases |
| `FailureLocalizationResult.v0` | Per-run localization verdict |
| `CoverageReport.v0` | Single-metric coverage snapshot |
| `BenchmarkRegistry.v0` | Registered suites, cases, thresholds |
| `BenchmarkMetricRegistry.v0` | Canonical metric definitions (numerator, denominator, thresholds) |
| `ExplainQualityReport.v0` | PF / SM explain-quality and render-audit scoring |
| `ProfileCoverageReport.v0` | PF profile coverage (artifacts, semantic checks, handoffs) |
| `ConformanceRun.v0` | Conformance suite bridge (no duplicated validation logic) |

## Stability rules (v0)

1. **No renames** of required fields without a new `schema_version`.
2. **`BenchmarkCase.v0.input_artifacts`** accepts either `release_directory` or `case_manifest_path`.
3. **`BenchmarkReport.v0.producer_id`** identifies the emitting repo (`pcs-bench`, `provability-fabric`, etc.).
4. **`BenchmarkReport.v0.metrics`** lists `benchmark_metric_id` values; **`metric_summaries`** holds `MetricSummary.v0` results. Coverage blocks may still use legacy short `metric` names.
5. **Digests** use pcs-core canonical hashing; placeholder digests are allowed only in draft fixtures.

## Validation

```bash
cd python
python scripts/materialize_benchmark_fixtures.py
python scripts/materialize_benchmark_producer_examples.py
pcs benchmark validate
pcs conformance run --suite benchmark-ingest
pcs conformance run --suite benchmark-report
```

Canonical examples live under `examples/benchmarks/`. `PcsBenchIngest.v0` producer bundles validate under `examples/benchmark_ingest/`. Other producer artifacts (`BenchmarkReport`, `BenchmarkCase`) live under `examples/benchmark/`. Dialect fixtures under `examples/benchmarks/compatibility/` normalize through `pcs_core.benchmark_compat`. See [benchmark-ingest-contract.md](benchmark-ingest-contract.md) and [benchmark-object-model.md](benchmark-object-model.md).
