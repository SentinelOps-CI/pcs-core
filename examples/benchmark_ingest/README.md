# Producer PcsBenchIngest examples

Release-grade `PcsBenchIngest.v0` bundles for each benchmark producer are generated through materialize scripts from live producer exports when available, otherwise from pcs-core dialect fallbacks, and maintainers refresh them instead of editing JSON by hand.

The contract and evidence tiers appear in [docs/benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md), and producer setup appears in [docs/producer-benchmark-ingest.md](../../docs/producer-benchmark-ingest.md).

## Generate from producer repos (preferred)

Check out producer repositories as siblings of pcs-core, then run `make pcs-bench-producer` in each producer repository according to the table below.

| Golden file | Producer repo | Command | Producer export path |
|-------------|---------------|---------|----------------------|
| `labtrust.pcs_bench_ingest.valid.json` | LabTrust-Gym | `make pcs-bench-producer` | `benchmark_runs/labtrust_reproducibility/pcs_bench_ingest.v0.json` |
| `certifyedge.pcs_bench_ingest.valid.json` | CertifyEdge | `make pcs-bench-producer` | `benchmark_runs/tool_use_safety/pcs_bench_ingest.v0.json` |
| `provability_fabric.pcs_bench_ingest.valid.json` | provability-fabric | `make pcs-bench-producer` | `benchmark_runs/labtrust_admission/pcs_bench_ingest.v0.json` |
| `scientific_memory.pcs_bench_ingest.valid.json` | scientific-memory | `make pcs-bench-producer` | `benchmark_runs/labtrust_rendering/pcs_bench_ingest.v0.json` |

Materialize copies sibling exports into pcs-core goldens when the paths exist.

```bash
cd pcs-core/python
python scripts/materialize_benchmark_producer_examples.py
# or
pcs benchmark materialize-ingest
```

The default sibling layout uses the parent directory of pcs-core, and you can override discovery with `PCS_PRODUCER_REPOS_ROOT`.

```text
../LabTrust-Gym/benchmark_runs/labtrust_reproducibility/pcs_bench_ingest.v0.json
../CertifyEdge/benchmark_runs/tool_use_safety/pcs_bench_ingest.v0.json
../provability-fabric/benchmark_runs/labtrust_admission/pcs_bench_ingest.v0.json
../scientific-memory/benchmark_runs/labtrust_rendering/pcs_bench_ingest.v0.json
```

## Dialect fallback for continuous integration without sibling repos

When a producer export is missing, materialize builds from `examples/benchmarks/compatibility/*.dialect.json` through `pcs_core.benchmark_compat` normalizers, and maintainers refresh dialect captures from a fresh `make pcs-bench-producer` run before pinning.

## Validate

```bash
python ../scripts/validate_benchmark_ingest_examples.py --release-grade --write-provenance
pcs benchmark validate-ingest --release-grade
pcs conformance run --suite benchmark-ingest
just benchmark-ingest-conformance
```

`provenance.manifest.json` lists each golden together with producer export path, dialect fallback, and adequacy tier when you pass `--write-provenance`.

## Contract

Embedded arrays hold canonical v0 objects, and `artifact_refs` record on-disk paths and content digests for producer file provenance.

- [benchmarks.md](../../docs/benchmarks.md)
- [benchmark-ingest-contract.md](../../docs/benchmark-ingest-contract.md)
- [producer-benchmark-ingest.md](../../docs/producer-benchmark-ingest.md)
