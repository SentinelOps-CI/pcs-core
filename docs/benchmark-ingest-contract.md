# Benchmark ingest contract (PcsBenchIngest.v0)

## What it is

`PcsBenchIngest.v0` is the **release-grade export bundle** that benchmark producers hand to pcs-bench (or pcs-core CI) before suite aggregation into `BenchmarkReport.v0`. It carries normalized sub-artifacts (runs, coverage, explain/profile quality, localization) plus execution metadata (`commands`, `logs`) and producer provenance (`source_repo`, `source_commit`, `signature_or_digest`).

`BenchmarkArtifactRef.v0` is an optional companion record that points at the **on-disk file** a producer wrote, without replacing the embedded canonical object.

## Producers

| Producer ID | Typical ingest contents |
|-------------|-------------------------|
| `labtrust-gym` | `benchmark_runs` from gallery execution |
| `certifyedge` | `coverage_reports` (certificate completeness) |
| `provability-fabric` | `explain_quality_reports`, `profile_coverage_reports` |
| `scientific-memory` | `explain_quality_reports` (render/import audit) |
| `pcs-bench` | Aggregator; may assemble ingest from multiple producers |

Golden examples (generated, not hand-authored): `examples/benchmark_ingest/*.pcs_bench_ingest.valid.json`, produced by `python/scripts/materialize_benchmark_producer_examples.py` from `examples/benchmarks/compatibility/*.dialect.json` or live LabTrust gallery runs.

## Embedded objects vs path references

**Required (canonical):** each ingest array holds **full v0 objects**, not paths:

- `benchmark_runs`: `BenchmarkRun.v0[]`
- `coverage_reports`: `CoverageReport.v0[]`
- `failure_localization_reports`: `FailureLocalizationResult.v0[]`
- `explain_quality_reports`: `ExplainQualityReport.v0[]`
- `profile_coverage_reports`: `ProfileCoverageReport.v0[]`

Empty arrays are valid when a producer has nothing to contribute for that slot.

**Optional (provenance only):** `artifact_refs`: `BenchmarkArtifactRef.v0[]`

Each ref documents where the producer stored the same logical artifact on disk:

```json
{
  "artifact_type": "ExplainQualityReport.v0",
  "path": "benchmarks/rendering/explain_quality_report.sm-render-benchmark-v0.v0.json",
  "sha256": "sha256:…",
  "role": "producer_export",
  "source_repo": "https://github.com/fraware/scientific-memory",
  "source_commit": "…",
  "signature_or_digest": "sha256:…"
}
```

Rules:

- Refs **do not replace** embedded objects. Consumers must read arrays first.
- `sha256` is the **content digest** of the embedded object (`signature_or_digest` of that artifact).
- `signature_or_digest` on the ref itself is the canonical hash of the ref record (excluding that field).
- `path` is relative to the producer repo export root (convention documented per producer).

Scientific Memory and similar repos that today emit only file paths should add `artifact_refs` alongside normalized embedded objects (via pcs-core normalizers or in-repo adapters).

## Digesting

1. Each embedded sub-artifact has its own `signature_or_digest` (canonical JSON hash per pcs-core rules).
2. `BenchmarkArtifactRef.sha256` must equal the matching embedded artifact’s `signature_or_digest`.
3. `PcsBenchIngest.signature_or_digest` covers the ingest body **excluding** that field (same as other v0 artifacts).

## Source commits

- `source_repo` / `source_commit` on the ingest identify the **producer repo revision** that generated the bundle.
- Sub-artifacts may repeat the same fields when they were emitted from that revision.
- Refs repeat them for the file export line of provenance.
- Resolution: pin `source_commit` to the git SHA of the producer run; pcs-bench records that pin in `BenchmarkReport.v0` and conformance metadata.

## pcs-bench consumption

1. Validate ingest: `pcs validate ingest.json` or `pcs conformance run --suite benchmark-ingest`.
2. Read embedded arrays; use `artifact_refs` only for audit trails, diffing on-disk exports, or re-fetching originals.
3. Map metrics via `BenchmarkMetricRegistry.v0`; aggregate into `BenchmarkReport.v0` with `metric_summaries`.
4. Dialect JSON from producers should be normalized with `pcs benchmark normalize` before ingest validation when not already v0-shaped.

## Release-grade benchmark evidence

Evidence is **release-grade** when:

- `PcsBenchIngest.v0` validates against schema + semantic checks (producer ID, required arrays, ref/embed consistency).
- Every non-empty embedded array contains digested v0 artifacts.
- `source_commit` is a full 40-character git SHA (not a placeholder) for production publishes.
- Optional `artifact_refs` align with embedded content digests.
- Downstream `BenchmarkReport.v0` is produced from validated ingest (or native pcs-core suite runs) and passes `pcs conformance run --suite benchmark`.

## Regeneration

Producer repos capture dialect JSON under `examples/benchmarks/compatibility/*.dialect.json`. pcs-core materializes golden ingest bundles:

```bash
cd python
python scripts/materialize_benchmark_producer_examples.py
# or
pcs benchmark materialize-ingest
```

## Conformance

```bash
pcs conformance run --suite benchmark-ingest
pcs benchmark validate
```

Validates `PcsBenchIngest.v0`, `BenchmarkArtifactRef.v0`, embedded artifact types (`BenchmarkRun`, `CoverageReport`, `FailureLocalizationResult`, `ExplainQualityReport`, `ProfileCoverageReport`, `MetricSummary`), producer ingest examples, and the compatibility normalization corpus.

Producer integration checklist: [producer-benchmark-ingest.md](producer-benchmark-ingest.md).
