# Release-grade benchmark evidence

This document defines **adequacy tiers** for `PcsBenchIngest.v0` bundles and related `BenchmarkReport.v0` outputs. pcs-core is the normative authority; producer repos materialize evidence through captured dialect fixtures and live benchmark commands.

Contract semantics: [benchmark-ingest-contract.md](benchmark-ingest-contract.md). Producer wiring: [producer-benchmark-ingest.md](producer-benchmark-ingest.md).

## Adequacy tiers

| Tier | Meaning | Typical use |
|------|---------|-------------|
| **schema-valid** | Passes JSON Schema and pcs-core semantic checks (arrays present, ref/embed consistency). | CI schema gates, early integration |
| **developer-grade** | Schema-valid plus representative embedded content from producer-shaped dialect captures. May use fixture `source_commit` placeholders on sub-artifacts. | pcs-core golden examples, local dev |
| **release-grade** | Ready for pcs-bench aggregation on a pinned producer SHA with non-empty producer-meaningful arrays, live `commands`, and `artifact_refs`. | Release trains, cross-repo pins |
| **external-review-grade** | Release-grade plus non-placeholder ingest `source_commit`, complete provenance, and producer-specific report coverage (below). | Third-party audit, publication evidence |

Tiers are assessed by `pcs_core.benchmark_ingest.assess_ingest_adequacy_tier()` and enforced optionally via `scripts/validate_benchmark_ingest_examples.py --release-grade`.

## v0 policy (locked)

1. **Embedded canonical objects are authoritative.** pcs-bench and pcs-core validators read `benchmark_runs`, `coverage_reports`, `failure_localization_reports`, `explain_quality_reports`, and `profile_coverage_reports` as full v0 objects.
2. **`artifact_refs` are sidecar provenance only.** Path + `sha256` document where the producer wrote a file; they must not replace embedded objects.
3. **Native producer reports belong in `details` or separate files.** Upstream JSON shapes are normalized into v0 artifacts; raw dialect fields are not ingested verbatim without normalization.
4. **pcs-bench consumes embedded objects first.** Refs are for audit, diff, and re-fetch only.
5. **Path references alone are not release-grade.** An ingest that lists only file paths in arrays is invalid under v0 semantics.

## Minimum release-grade requirements (all producers)

- `source_commit` on the ingest root is a **real 40-character git SHA**, not all zeros or all `f`.
- `commands` is **non-empty** and records the producer benchmark command(s) that produced the bundle.
- When `artifact_refs` are present, every ref `sha256` equals the matching embedded object `signature_or_digest`, and every embedded export has a ref.
- `signature_or_digest` on the ingest and each sub-artifact uses pcs-core canonical hashing.

## Producer-specific release-grade expectations

Golden files under `examples/benchmark_ingest/` are regenerated from dialect captures in `examples/benchmarks/compatibility/` and are held to **external-review-grade** in CI (`--release-grade`). Live producer pins can raise them further; the table below is the **release-grade bar** each repo must meet when publishing from source.

| Producer | Command (representative) | Non-empty arrays required |
|----------|--------------------------|---------------------------|
| **LabTrust-Gym** | `python benchmark_reproducibility.py` | `benchmark_runs`, `coverage_reports` (release reproducibility), `commands` |
| **CertifyEdge** | `certifyedge benchmark certificates` | `coverage_reports` (certificate completeness), `profile_coverage_reports`, `commands` |
| **Provability Fabric** | `pf benchmark admission` | `failure_localization_reports`, `explain_quality_reports`, `profile_coverage_reports`, `commands` |
| **Scientific Memory** | `pcs-benchmark-rendering` | `explain_quality_reports`, `coverage_reports` (interpretability), `commands` |

Dialect captures live in `examples/benchmarks/compatibility/*.dialect.json`. Regenerate goldens:

```bash
cd python
python scripts/materialize_benchmark_producer_examples.py
```

Validate:

```bash
python scripts/validate_benchmark_ingest_examples.py --release-grade
pcs conformance run --suite benchmark-ingest
```

## Golden ingest examples (generated, not hand-written)

| File | Producer source |
|------|-----------------|
| `labtrust.pcs_bench_ingest.valid.json` | LabTrust `benchmark_reproducibility.py` → pcs-core gallery normalization |
| `certifyedge.pcs_bench_ingest.valid.json` | CertifyEdge certificate benchmark dialect |
| `provability_fabric.pcs_bench_ingest.valid.json` | PF admission explain-quality + profile dialects |
| `scientific_memory.pcs_bench_ingest.valid.json` | Scientific Memory `pcs-benchmark-rendering` dialect |

Do not hand-edit these files. Update the dialect capture from the producer repo, then rerun materialization.

## Relationship to BenchmarkReport.v0

`PcsBenchIngest.v0` is **producer export evidence**. `BenchmarkReport.v0` is **suite aggregation** (pcs-bench or `pcs benchmark run`). Release-grade suite publication requires:

- Validated ingest(s) per contributing producer at release-grade tier, and
- A `BenchmarkReport.v0` with declared `metrics`, complete `metric_summaries`, and digest — validated by `pcs conformance run --suite benchmark-report`.

## Anti-patterns

| Pattern | Tier cap |
|---------|----------|
| Path-only arrays (no embedded objects) | Fails schema-valid |
| Missing `artifact_refs` on producer file exports | developer-grade |
| Placeholder ingest `source_commit` | developer-grade |
| Empty `commands` on claimed live runs | Below release-grade |
| Ref digest mismatch | Fails schema-valid |
