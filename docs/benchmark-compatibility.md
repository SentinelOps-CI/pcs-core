# Benchmark compatibility (cross-repo)

pcs-core is the **normative** owner of benchmark JSON schemas. Other repos may emit dialect JSON internally; CI in pcs-core verifies that each dialect **normalizes** to the v0 schemas.

## Producers

| Producer ID | Typical artifacts | Normalizer |
|-------------|-------------------|------------|
| `pcs-core` | `BenchmarkReport.v0`, `BenchmarkCase.v0`, fixtures under `benchmarks/` | Native |
| `pcs-bench` | Suite reports (`suite_id` alias) | `normalize_pcs_bench_report` |
| `certifyedge` | Certificate benchmark checks | `build_certifyedge_pcs_bench_ingest` → `PcsBenchIngest.v0` |
| `labtrust-gym` | Case manifests | `normalize_labtrust_case_manifest` → `BenchmarkCase.v0` |
| `scientific-memory` | Render / import audit | `build_scientific_memory_pcs_bench_ingest` → `PcsBenchIngest.v0` |
| `provability-fabric` | Admission + profile | `build_pf_pcs_bench_ingest` → `PcsBenchIngest.v0` |

Producer repos should emit **`PcsBenchIngest.v0`** (or dialect JSON that normalizes to it) for pcs-bench ingestion. Golden ingest bundles live under `examples/benchmark_ingest/*.pcs_bench_ingest.valid.json` (see [benchmark-ingest-contract.md](benchmark-ingest-contract.md)).

## Compatibility corpus

`examples/benchmarks/compatibility/` contains:

- `*.dialect.json` — representative upstream shapes
- `*.normalized.json` — expected pcs-core v0 output

`examples/benchmark_ingest/` contains **producer-validated** `PcsBenchIngest.v0` bundles (one per owning repo), copied from live `make pcs-bench-producer` exports via `materialize_benchmark_producer_examples.py` (dialect fallback when siblings are absent). They are checked by `run_benchmark_ingest_contract_checks()`, `pcs benchmark validate-ingest --release-grade`, and `pcs conformance run --suite benchmark-ingest`.

The `benchmark-report` conformance suite validates canonical `examples/benchmarks/*.valid.json`, normalized compatibility outputs, and `examples/benchmark/*.valid.json`. The `benchmark-ingest` suite validates ingest bundles and embedded artifact types. Producer integration: [producer-benchmark-ingest.md](producer-benchmark-ingest.md).

## pcs-bench integration

pcs-bench should:

1. Pin a `pcs-core` commit.
2. Import `BenchmarkRegistry.v0` and `BenchmarkMetricRegistry.v0` from `examples/`.
3. Emit `BenchmarkReport.v0` with `metrics` as `benchmark_metric_id` values and a `metric_summaries` array (`MetricSummary.v0`).
4. Run `pcs validate` on reports before publishing (or `pcs benchmark normalize` on dialect JSON).

## Metric registry

Canonical metric definitions (numerator, denominator, applicability, failure interpretation, thresholds) live in `examples/benchmark_metric_registry.valid.json`. See [benchmark-metrics.md](benchmark-metrics.md).
