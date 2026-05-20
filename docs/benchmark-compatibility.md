# Benchmark compatibility (cross-repo)

pcs-core is the **normative** owner of benchmark JSON schemas. Other repos may emit dialect JSON internally; CI in pcs-core verifies that each dialect **normalizes** to the v0 schemas.

## Producers

| Producer ID | Typical artifacts | Normalizer |
|-------------|-------------------|------------|
| `pcs-core` | `BenchmarkReport.v0`, `BenchmarkCase.v0`, fixtures under `benchmarks/` | Native |
| `pcs-bench` | Suite reports (`suite_id` alias) | `normalize_pcs_bench_report` |
| `provability-fabric` | Admission explain-quality, profile coverage | `normalize_pf_explain_quality`, `normalize_pf_profile_coverage` |
| `certifyedge` | Certificate benchmark checks | `normalize_certifyedge_certificate_benchmark` → `CoverageReport.v0` |
| `labtrust-gym` | Case manifests | `normalize_labtrust_case_manifest` → `BenchmarkCase.v0` |
| `scientific-memory` | Render / import audit | `normalize_scientific_memory_render_benchmark` → `ExplainQualityReport.v0` |

## Compatibility corpus

`examples/benchmarks/compatibility/` contains:

- `*.dialect.json` — representative upstream shapes
- `*.normalized.json` — expected pcs-core v0 output

The `benchmark-report` conformance suite validates both canonical `*.valid.json` examples and the normalized compatibility outputs.

## pcs-bench integration

pcs-bench should:

1. Pin a `pcs-core` commit.
2. Import `BenchmarkRegistry.v0` and `BenchmarkMetricRegistry.v0` from `examples/`.
3. Emit `BenchmarkReport.v0` with `producer_id: "pcs-bench"`.
4. Run `pcs validate` on reports before publishing.

## Metric registry

Canonical metric definitions (numerator, denominator, applicability, failure interpretation, thresholds) live in `examples/benchmark_metric_registry.valid.json`. See [benchmark-metrics.md](benchmark-metrics.md).
