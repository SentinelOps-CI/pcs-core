# Benchmark registry (v0)

The PCS benchmark layer is a **protocol extension**, not a script collection. `BenchmarkRegistry.v0` lists suites; `BenchmarkTask.v0` defines evaluation goals; `BenchmarkCase.v0` defines inputs and expected outcomes; `BenchmarkRun.v0` records execution; `BenchmarkReport.v0` aggregates portable results.

## Canonical registry

The machine-readable registry is built from `python/pcs_core/benchmark_registry_data.py` and materialized to:

- `examples/benchmark_registry.valid.json`
- Schema: `schemas/BenchmarkRegistry.v0.schema.json`

Regenerate after changing suite definitions:

```bash
cd python
python scripts/materialize_benchmark_fixtures.py
```

## Suites (v0)

| Suite ID | Workflows | Fixture root |
|----------|-----------|----------------|
| `labtrust-qc-release-v0` | `hospital_lab.qc_release`, `labtrust.qc_release_v0.1` | `benchmarks/labtrust-qc-release/` |
| `tool-use-safety-v0` | `agent_tool_use.safety_v0` | `benchmarks/tool-use-safety/` |
| `computation-reproducibility-v0` | `scientific_computation.reproducibility_v0` | `benchmarks/computation-reproducibility/` |
| `cross-domain-release-chain-v0` | All three workflow profiles | `benchmarks/cross-domain/` |
| `formal-trust-kernel-v0` | Cross-domain Lean checks | `benchmarks/cross-domain/` (formal cases) |
| `scientific-memory-rendering-v0` | LabTrust + memory import | `benchmarks/labtrust-qc-release/` |

Each suite entry includes:

- `workflow_ids` — profiles under test
- `required_artifacts` — artifact types that must appear in valid releases
- `valid_cases` / `invalid_cases` — case directory names under `valid/` and `invalid/`
- `metrics` — standard PCS benchmark metrics (see [benchmark-metrics.md](benchmark-metrics.md))
- `minimum_passing_thresholds` — pass rate, localization accuracy, formal and registry coverage floors

LabTrust-Gym gallery exports also ship `benchmark_manifest.v0.json` (`BenchmarkSuiteManifest.v0`) listing gallery case IDs, paths, and polarity. Registry entries for `labtrust-qc-release-v0` must stay aligned with that manifest (`registry_matches_manifest` in tests).

## Case layout

```
benchmarks/<suite>/
  benchmark_task.v0.json
  valid/<case-id>/
    benchmark_case.v0.json
  invalid/<case-id>/
    benchmark_case.v0.json
    expected_failure.json      # FailureCaseManifest.v0
    expected_repair_hint.json
  expected_reports/            # optional golden BenchmarkReport.v0
```

Cases reference release directories via `input_artifacts.release_directory` (repo-relative path), typically under `examples/*-release` or synthesized under `benchmarks/*/input_releases/`.

## Running benchmarks

```bash
cd python
python -m pcs_core.cli benchmark run --suite labtrust-qc-release-v0
python -m pcs_core.cli benchmark run --suite labtrust-qc-release-v0 --json --out /tmp/report.json
```

Conformance validation can feed benchmark reports without duplicating check logic via `BenchmarkReport.v0.conformance_refs` pointing at `ConformanceRun.v0` records (see `schemas/ConformanceRun.v0.schema.json`).

## Metric registry

Canonical metric definitions: `examples/benchmark_metric_registry.valid.json` (`BenchmarkMetricRegistry.v0`). Each entry specifies numerator, denominator, applicability, failure interpretation, and recommended thresholds.

Additional report types for cross-repo alignment:

- `ExplainQualityReport.v0` — PF admission / SM render explain-quality
- `ProfileCoverageReport.v0` — PF workflow profile coverage

## Conformance bridge

| Benchmark suite | Conformance suite ref |
|-----------------|----------------------|
| `labtrust-qc-release-v0` | `release-chain` |
| `tool-use-safety-v0` | `tool-use` |
| `computation-reproducibility-v0` | `computation` |
| `cross-domain-release-chain-v0` | `multidomain` |
| `formal-trust-kernel-v0` | `lean-trust` |
| `benchmark-report` | Cross-repo dialect normalization corpus |
| `benchmark-ingest` | `PcsBenchIngest.v0` producer bundles and embedded artifact types |

```bash
pcs conformance run --suite benchmark-ingest
pcs conformance run --suite benchmark-report
pcs benchmark normalize --dialect examples/benchmarks/compatibility/pf_admission_explain_quality.dialect.json --out /tmp/out.json
```

## pcs-bench

pcs-core owns schemas, registry, metrics, fixtures, and the reference runner. The pcs-bench repository pins pcs-core commits, imports the registry, and runs suites without forking protocol definitions. See [benchmarks.md](benchmarks.md).
