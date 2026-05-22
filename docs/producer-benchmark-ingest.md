# Producer integration: PcsBenchIngest.v0

Guide for **CertifyEdge**, **LabTrust-Gym**, **Provability Fabric**, and **Scientific Memory** to emit pcs-bench-compatible benchmark exports without forking schemas.

## Contract summary

| Layer | Rule |
|-------|------|
| Arrays (`benchmark_runs`, `coverage_reports`, …) | **Full v0 JSON objects** (release-grade) |
| `artifact_refs` | **Sidecar provenance only** — paths + content digests; never a substitute for embedded objects |
| `signature_or_digest` | Canonical hash per pcs-core rules on each artifact and on the ingest root |
| `source_repo` / `source_commit` | Required on ingest and sub-artifacts; release-grade commits are real 40-char SHAs |

Normative spec: [benchmark-ingest-contract.md](benchmark-ingest-contract.md). Adequacy tiers: [release-grade-benchmark-evidence.md](release-grade-benchmark-evidence.md).

## Required producer target

Every producer repo must expose:

```makefile
pcs-bench-producer:
	# run benchmark, write pcs_bench_ingest.v0.json, validate against pcs-core + pcs-bench
```

| Producer | Export path (repo-relative) |
|----------|----------------------------|
| LabTrust-Gym | `benchmark_runs/labtrust_reproducibility/pcs_bench_ingest.v0.json` |
| CertifyEdge | `benchmark_runs/tool_use_safety/pcs_bench_ingest.v0.json` |
| provability-fabric | `benchmark_runs/labtrust_admission/pcs_bench_ingest.v0.json` |
| scientific-memory | `benchmark_runs/labtrust_rendering/pcs_bench_ingest.v0.json` |

Release-grade exports must pass `pcs validate` on the ingest file and `pcs-bench validate-ingest` in producer CI.

## Recommended export flow

```mermaid
flowchart LR
  A[make pcs-bench-producer] --> B[Write on-disk v0 files]
  B --> C[Build embedded objects in memory]
  C --> D[Add BenchmarkArtifactRef per file]
  D --> E[pcs_bench_ingest.v0.json]
  E --> F[pcs validate / benchmark-ingest suite]
```

1. Run `make pcs-bench-producer` and write canonical v0 files under a stable directory.
2. Load or generate the same content as in-memory v0 objects in the ingest arrays.
3. Compute `signature_or_digest` for each object (pcs-core `canonical_hash`).
4. Append `artifact_refs` with `path` (repo-relative), `sha256` equal to that object’s digest, `role: producer_export`, and producer `source_repo` / `source_commit`.
5. Hash the ingest body into `PcsBenchIngest.signature_or_digest`.

## pcs-core golden sync

With producer repos checked out as siblings of `pcs-core` (or set `PCS_PRODUCER_REPOS_ROOT` to their parent directory):

```bash
# In each producer repo
make pcs-bench-producer

# In pcs-core
cd python
python scripts/materialize_benchmark_producer_examples.py
python ../scripts/validate_benchmark_ingest_examples.py --release-grade
pcs conformance run --suite benchmark-ingest
```

Materialize copies sibling exports into `examples/benchmark_ingest/*.pcs_bench_ingest.valid.json` when present; otherwise it normalizes from `examples/benchmarks/compatibility/*.dialect.json`.

## Dialect fallback (CI without siblings)

Capture representative upstream JSON as:

`examples/benchmarks/compatibility/<producer>_<feature>.dialect.json`

Normalizers in `pcs_core.benchmark_compat` map dialect JSON to **`PcsBenchIngest.v0`**.

| Producer | Python entrypoint | Release-grade arrays |
|----------|-------------------|----------------------|
| `certifyedge` | `build_certifyedge_pcs_bench_ingest` | `coverage_reports`, `profile_coverage_reports` |
| `labtrust-gym` | `build_labtrust_pcs_bench_ingest` | `benchmark_runs`, `coverage_reports` |
| `provability-fabric` | `build_pf_pcs_bench_ingest` | `failure_localization_reports`, `explain_quality_reports`, `profile_coverage_reports` |
| `scientific-memory` | `build_scientific_memory_pcs_bench_ingest` | `explain_quality_reports`, `coverage_reports` |

```bash
pcs benchmark normalize \
  --dialect examples/benchmarks/compatibility/scientific_memory_render_benchmark.dialect.json \
  --out /tmp/scientific_memory.pcs_bench_ingest.json
```

## Pinning pcs-core

1. Submodule or package pin to a **full git SHA** of [pcs-core](https://github.com/SentinelOps-CI/pcs-core).
2. `pcs conformance run --suite benchmark-ingest` in producer CI after generating ingest JSON.
3. Set ingest `source_commit` to the producer repo SHA that produced the export.

## Anti-patterns

| Do not | Do instead |
|--------|------------|
| Emit only file paths in ingest arrays | Embed full v0 objects; use `artifact_refs` for paths |
| Omit `artifact_refs` when exporting files | One ref per embedded object with matching `sha256` |
| Hand-edit pcs-core `examples/benchmark_ingest/*.json` | Regenerate via materialize from producer export |
| Use placeholder `source_commit` in release publishes | Pin real 40-character git SHAs |
| Path-only ingest | Fails schema validation (not release-grade) |

## pcs-bench consumption

pcs-bench validates each producer ingest, reads **embedded arrays first**, aggregates metrics into `BenchmarkReport.v0` with `metric_summaries`, and runs suite cases under `benchmarks/` in pcs-core.
