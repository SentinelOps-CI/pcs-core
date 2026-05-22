# Producer PcsBenchIngest examples

Release-grade `PcsBenchIngest.v0` bundles per benchmark producer. **Do not hand-edit.** Regenerate from live producer exports (preferred) or pcs-core dialect fallbacks.

## Generate from producer repos (preferred)

Check out producer repos as siblings of `pcs-core`, then in each producer repo:

| Golden file | Producer repo | Command | Producer export path |
|-------------|---------------|---------|----------------------|
| `labtrust.pcs_bench_ingest.valid.json` | LabTrust-Gym | `make pcs-bench-producer` | `benchmark_runs/labtrust_reproducibility/pcs_bench_ingest.v0.json` |
| `certifyedge.pcs_bench_ingest.valid.json` | CertifyEdge | `make pcs-bench-producer` | `benchmark_runs/tool_use_safety/pcs_bench_ingest.v0.json` |
| `provability_fabric.pcs_bench_ingest.valid.json` | provability-fabric | `make pcs-bench-producer` | `benchmark_runs/labtrust_admission/pcs_bench_ingest.v0.json` |
| `scientific_memory.pcs_bench_ingest.valid.json` | scientific-memory | `make pcs-bench-producer` | `benchmark_runs/labtrust_rendering/pcs_bench_ingest.v0.json` |

Copy into pcs-core goldens (materialize does this when sibling paths exist):

```bash
cd pcs-core/python
python scripts/materialize_benchmark_producer_examples.py
# or
pcs benchmark materialize-ingest
```

Sibling layout (default: parent directory of `pcs-core`). Override with `PCS_PRODUCER_REPOS_ROOT`:

```text
../LabTrust-Gym/benchmark_runs/labtrust_reproducibility/pcs_bench_ingest.v0.json
../CertifyEdge/benchmark_runs/tool_use_safety/pcs_bench_ingest.v0.json
../provability-fabric/benchmark_runs/labtrust_admission/pcs_bench_ingest.v0.json
../scientific-memory/benchmark_runs/labtrust_rendering/pcs_bench_ingest.v0.json
```

## Dialect fallback (CI without sibling repos)

When a producer export is missing, materialize builds from `examples/benchmarks/compatibility/*.dialect.json` via `pcs_core.benchmark_compat` normalizers. Refresh dialect captures from a fresh `make pcs-bench-producer` run before pinning.

## Validate

```bash
python ../scripts/validate_benchmark_ingest_examples.py --release-grade --write-provenance
pcs benchmark validate-ingest --release-grade
pcs conformance run --suite benchmark-ingest
just benchmark-ingest-conformance
```

`provenance.manifest.json` lists each golden, producer export path, dialect fallback, and adequacy tier (refresh with `--write-provenance`).

## Contract

Embedded arrays hold canonical v0 objects. `artifact_refs` record on-disk paths and content digests for producer file provenance only.

- [benchmarks.md](../../docs/benchmarks.md)
- [benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md)
- [producer-benchmark-ingest.md](../../docs/producer-benchmark-ingest.md)
