# Producer PcsBenchIngest examples

Release-grade-shaped `PcsBenchIngest.v0` bundles per benchmark producer. **Do not hand-edit.** Regenerate from captured producer dialects:

```bash
cd python
python scripts/materialize_benchmark_producer_examples.py
```

Validate:

```bash
python ../scripts/validate_benchmark_ingest_examples.py
pcs benchmark validate-ingest
pcs conformance run --suite benchmark-ingest
```

`provenance.manifest.json` lists each golden file, dialect capture, producer command, and adequacy tier (regenerated with materialize).

## Golden files (generated from producer output)

| File | Producer repo | Representative command | Dialect capture |
|------|---------------|----------------------|-----------------|
| `labtrust.pcs_bench_ingest.valid.json` | LabTrust-Gym | `python benchmark_reproducibility.py` | `examples/benchmarks/compatibility/labtrust_case_manifest.dialect.json` + live gallery run |
| `certifyedge.pcs_bench_ingest.valid.json` | CertifyEdge | `certifyedge benchmark certificates` | `certifyedge_certificate_benchmark.dialect.json` |
| `provability_fabric.pcs_bench_ingest.valid.json` | Provability Fabric | `pf benchmark admission` | `pf_admission_explain_quality.dialect.json` + `pf_profile_coverage.dialect.json` |
| `scientific_memory.pcs_bench_ingest.valid.json` | Scientific Memory | `pcs-benchmark-rendering` | `scientific_memory_render_benchmark.dialect.json` |

pcs-core normalizers in `pcs_core.benchmark_compat` map dialect JSON to v0 ingest. Update the dialect file from a fresh producer run, then rerun materialization.

## Contract

Embedded arrays hold canonical v0 objects. `artifact_refs` record on-disk paths and content digests for producer file provenance only.

- [benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md)
- [release-grade-benchmark-evidence.md](../../docs/release-grade-benchmark-evidence.md)
- [producer-benchmark-ingest.md](../../docs/producer-benchmark-ingest.md)
