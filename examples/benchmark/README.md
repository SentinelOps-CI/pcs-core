# Producer benchmark examples

Golden JSON from each benchmark producer is normalized to pcs-core v0 schemas through materialize scripts instead of manual edits.

```bash
# In each producer repo (sibling of pcs-core)
make pcs-bench-producer

# In pcs-core
cd python
python scripts/materialize_benchmark_producer_examples.py
```

Set `PCS_PRODUCER_REPOS_ROOT` when producer repositories live outside the default parent directory of pcs-core.

| File | Producer | Schema |
|------|----------|--------|
| `pcs_bench_report.valid.json` | pcs-bench | `BenchmarkReport.v0` |
| `labtrust_benchmark_case.valid.json` | LabTrust-Gym | `BenchmarkCase.v0` |

`PcsBenchIngest.v0` producer bundles live in `examples/benchmark_ingest/` and copy from live producer exports when available.

```bash
python ../scripts/validate_benchmark_ingest_examples.py --release-grade
pcs benchmark validate-ingest --release-grade
pcs conformance run --suite benchmark-ingest
```

See [docs/benchmarks.md](../../docs/benchmarks.md), [benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md), and [producer-benchmark-ingest.md](../../docs/producer-benchmark-ingest.md).
