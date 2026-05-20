# Benchmark schema contract (v0 frozen)

PCS benchmark artifacts are **frozen at v0** for cross-repo alignment. Downstream repos (pcs-bench, Provability Fabric, CertifyEdge, LabTrust-Gym, Scientific Memory) must normalize outputs to these schemas before claiming benchmark compatibility.

## Core artifacts

| Schema | Role |
|--------|------|
| `BenchmarkTask.v0` | Evaluation goal, metrics, success criteria |
| `BenchmarkCase.v0` | One case: inputs, expected status, failure code, responsible component, repair hint |
| `BenchmarkRun.v0` | Observed execution of one case |
| `BenchmarkReport.v0` | Suite aggregation: runs, summary, coverage, failures, optional `conformance_refs` |
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
4. **Metric IDs** use the `*_score` form in `BenchmarkMetricRegistry.v0`; legacy short names remain in `BenchmarkReport.v0.metrics` for compatibility.
5. **Digests** use pcs-core canonical hashing; placeholder digests are allowed only in draft fixtures.

## Validation

```bash
cd python
python scripts/materialize_benchmark_examples.py
pcs benchmark validate
pcs conformance run --suite benchmark-report
```

Canonical examples live under `examples/benchmarks/`. Dialect fixtures under `examples/benchmarks/compatibility/` normalize through `pcs_core.benchmark_compat`.
