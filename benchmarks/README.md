# PCS benchmark fixtures

The benchmark evaluation protocol for pcs-core defines tasks, cases, runs, and reports as versioned JSON artifacts under `schemas/`.

The overview guide is [docs/benchmarks.md](../docs/benchmarks.md).

## Layout

Each suite directory (for example `labtrust-qc-release/`) contains:

```
<suite>/
  benchmark_task.v0.json
  benchmark_manifest.v0.json    # optional gallery index (LabTrust)
  valid/<case-id>/
    benchmark_case.v0.json
    benchmark_run.<case-id>.v0.json
  invalid/<case-id>/
    benchmark_case.v0.json
    expected_failure.json
    expected_repair_hint.json
  expected_reports/
    benchmark_report.v0.json
```

Cases reference release trees via `input_artifacts.release_directory`, usually under `examples/*-release/` or `benchmarks/*/input_releases/`.

## Suites

Suite definitions live in `examples/benchmark_registry.valid.json`, built from `python/pcs_core/benchmark_registry_data.py`.

| Suite ID | Purpose |
|----------|---------|
| `labtrust-qc-release-v0` | Hospital lab QC release chain |
| `tool-use-safety-v0` | Agent tool-use safety |
| `computation-reproducibility-v0` | Scientific computation witnesses |
| `cross-domain-release-chain-v0` | All three valid release profiles |
| `formal-trust-kernel-v0` | Lean proof obligations and checks |
| `scientific-memory-rendering-v0` | Scientific Memory interpretability |

## Commands

```bash
cd python
python scripts/materialize_benchmark_fixtures.py
pcs benchmark list
pcs benchmark validate
pcs benchmark run --suite labtrust-qc-release-v0
pcs conformance run --suite benchmark
pcs conformance run --suite benchmark-ingest
pcs benchmark validate-ingest --release-grade
```

## Examples

| Path | Contents |
|------|----------|
| `examples/benchmarks/` | Reference types (`BenchmarkCase`, `BenchmarkRun`, `BenchmarkReport`, …) |
| `examples/benchmark/` | Producer report snapshots |
| `examples/benchmark_ingest/` | `PcsBenchIngest.v0` goldens |
| `examples/benchmark_metric_registry.valid.json` | Metric definitions |

Regenerate fixtures with the commands below.

```bash
cd python
python scripts/materialize_benchmark_fixtures.py
python scripts/materialize_benchmark_producer_examples.py
```

## Documentation

- [docs/benchmark-object-model.md](../docs/benchmark-object-model.md)
- [docs/benchmark-metrics.md](../docs/benchmark-metrics.md)
- [docs/benchmark-registry.md](../docs/benchmark-registry.md)
- [docs/benchmark-ingest-contract.md](../docs/benchmark-ingest-contract.md)
- [docs/producer-benchmark-ingest.md](../docs/producer-benchmark-ingest.md)

## pcs-bench

Downstream benchmark runners should pin a pcs-core commit, import `BenchmarkRegistry.v0`, and add suites without redefining schemas. pcs-core remains the normative owner.
