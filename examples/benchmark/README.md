# Producer benchmark examples

Golden JSON from each benchmark producer, normalized to pcs-core v0 schemas. Do not hand-edit; regenerate:

```bash
cd python
python scripts/materialize_benchmark_producer_examples.py
```

| File | Producer | Schema |
|------|----------|--------|
| `pcs_bench_report.valid.json` | pcs-bench | `BenchmarkReport.v0` |
| `labtrust_benchmark_case.valid.json` | LabTrust-Gym | `BenchmarkCase.v0` |
| `certifyedge_pcs_bench_ingest.valid.json` | CertifyEdge | `PcsBenchIngest.v0` |
| `pf_pcs_bench_ingest.valid.json` | Provability Fabric | `PcsBenchIngest.v0` |
| `scientific_memory_pcs_bench_ingest.valid.json` | Scientific Memory | `PcsBenchIngest.v0` |

Dialect sources: `examples/benchmarks/compatibility/*.dialect.json`. See [benchmark-object-model.md](../../docs/benchmark-object-model.md) and [benchmark-compatibility.md](../../docs/benchmark-compatibility.md).
