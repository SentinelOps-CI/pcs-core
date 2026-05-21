# PCS benchmark fixtures

This directory holds the **benchmark evaluation protocol** fixtures for pcs-core. Benchmarks are a protocol extension: tasks, cases, runs, and reports are JSON artifacts with JSON Schema contracts under `schemas/`.

## Layout

Each suite has a fixture root (for example `labtrust-qc-release/`):

```
<suite>/
  benchmark_task.v0.json       # BenchmarkTask.v0
  benchmark_manifest.v0.json   # optional LabTrust-Gym gallery index (labtrust-qc-release)
  valid/<case-id>/
    benchmark_case.v0.json
    benchmark_run.<case-id>.v0.json   # produced by `pcs benchmark run`
  invalid/<case-id>/
    benchmark_case.v0.json
    expected_failure.json             # FailureCaseManifest.v0
    expected_repair_hint.json
  expected_reports/
    benchmark_report.v0.json          # golden BenchmarkReport.v0
```

Cases reference release trees via `input_artifacts.release_directory` (repo-relative), usually under `examples/*-release` or synthesized trees such as `benchmarks/tool-use-safety/input_releases/`.

## Registry

Suite definitions live in `examples/benchmark_registry.valid.json`, generated from `python/pcs_core/benchmark_registry_data.py`.

| Suite | Purpose |
|-------|---------|
| `labtrust-qc-release-v0` | Hospital lab QC release chain |
| `tool-use-safety-v0` | Agent tool-use safety releases |
| `computation-reproducibility-v0` | Scientific computation witnesses |
| `cross-domain-release-chain-v0` | All three valid release profiles |
| `formal-trust-kernel-v0` | Lean proof obligation / check results |
| `scientific-memory-rendering-v0` | Scientific Memory import interpretability |

## Commands

```bash
cd python
python scripts/materialize_benchmark_fixtures.py
pcs benchmark list
pcs benchmark validate
pcs benchmark run --suite labtrust-qc-release-v0
pcs benchmark run --suite formal-trust-kernel-v0 --json --out /tmp/report.json
pcs conformance run --suite benchmark
```

## Canonical examples

| Path | Contents |
|------|----------|
| `examples/benchmarks/` | pcs-core reference types (`BenchmarkCase`, `BenchmarkRun`, `BenchmarkReport`, coverage, explain-quality) |
| `examples/benchmark/` | Producer-shaped outputs (pcs-bench, LabTrust, CertifyEdge, PF, Scientific Memory) |
| `examples/benchmark_metric_registry.valid.json` | Canonical `benchmark_metric_id` definitions |

Regenerate everything:

```bash
cd python
python scripts/materialize_benchmark_fixtures.py
# or individually:
python scripts/materialize_benchmark_examples.py
python scripts/materialize_benchmark_producer_examples.py
```

## Documentation

- [docs/benchmark-object-model.md](../docs/benchmark-object-model.md) — artifacts and status dimensions
- [docs/benchmark-schema-contract-v0.md](../docs/benchmark-schema-contract-v0.md) — frozen v0 contract
- [docs/benchmark-metrics.md](../docs/benchmark-metrics.md) — metric definitions
- [docs/benchmark-registry.md](../docs/benchmark-registry.md) — suite registry
- [docs/benchmark-compatibility.md](../docs/benchmark-compatibility.md) — dialect normalization

## External pcs-bench

Downstream repos should pin a pcs-core commit, import `BenchmarkRegistry.v0`, and add suites without redefining schemas. pcs-core remains the normative protocol owner.
