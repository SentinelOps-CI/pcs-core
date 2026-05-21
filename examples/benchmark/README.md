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

`PcsBenchIngest.v0` producer bundles live in `examples/benchmark_ingest/`. Dialect sources: `examples/benchmarks/compatibility/*.dialect.json`. See [benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md), [benchmark-object-model.md](../../docs/benchmark-object-model.md), and [benchmark-compatibility.md](../../docs/benchmark-compatibility.md).
