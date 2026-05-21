# Producer PcsBenchIngest examples

Release-grade `PcsBenchIngest.v0` bundles per benchmark producer. Do not hand-edit; regenerate from captured producer dialects:

```bash
cd python
python scripts/materialize_benchmark_producer_examples.py
# or
pcs benchmark materialize-ingest
```

| File | Producer | Source |
|------|----------|--------|
| `labtrust.pcs_bench_ingest.valid.json` | LabTrust-Gym | Live `labtrust-valid-release-v0` gallery run |
| `certifyedge.pcs_bench_ingest.valid.json` | CertifyEdge | `examples/benchmarks/compatibility/certifyedge_certificate_benchmark.dialect.json` |
| `provability_fabric.pcs_bench_ingest.valid.json` | Provability Fabric | `pf_admission_explain_quality.dialect.json` + `pf_profile_coverage.dialect.json` |
| `scientific_memory.pcs_bench_ingest.valid.json` | Scientific Memory | `scientific_memory_render_benchmark.dialect.json` |

Embedded arrays hold canonical v0 objects. Optional `artifact_refs` record on-disk paths and content digests for producer file provenance. See [benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md).
