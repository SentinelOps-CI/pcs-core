# Producer benchmark examples

Golden JSON from each benchmark producer, normalized to pcs-core v0 schemas. Do not hand-edit; regenerate:

```bash
cd python
python scripts/materialize_benchmark_producer_examples.py
```

| File | Producer | Schema |
|------|----------|--------|
| `pcs_bench_report.valid.json` | pcs-bench | `BenchmarkReport.v0` |
| `pcs_core_benchmark_report.valid.json` | pcs-core (reference runner) | `BenchmarkReport.v0` |
| `labtrust_case.valid.json` | LabTrust-Gym | `BenchmarkCase.v0` |
| `certifyedge_certificate_benchmark.valid.json` | CertifyEdge | `CoverageReport.v0` |
| `pf_admission_benchmark.valid.json` | Provability Fabric | `ExplainQualityReport.v0` |
| `scientific_memory_rendering_benchmark.valid.json` | Scientific Memory | `ExplainQualityReport.v0` |

Dialect sources live under `examples/benchmarks/compatibility/`. See [benchmark-object-model.md](../../docs/benchmark-object-model.md).
