# Benchmark ingest contract (PcsBenchIngest.v0)

Normative schemas: [schemas/](../schemas/). Overview: [benchmarks.md](benchmarks.md). Producer setup: [producer-benchmark-ingest.md](producer-benchmark-ingest.md).

## Rules (v0)

1. **Embedded canonical objects are authoritative.** Ingest arrays contain full `BenchmarkRun.v0`, `CoverageReport.v0`, `FailureLocalizationResult.v0`, `ExplainQualityReport.v0`, and `ProfileCoverageReport.v0` objects — never path-only entries.
2. **`artifact_refs` are sidecar provenance only.** Each `BenchmarkArtifactRef.v0` records `path`, content `sha256`, and export metadata; refs must not replace embedded objects.
3. **Native producer reports belong in `details` or separate files.** Dialect JSON from producer repos is normalized into v0 artifacts before ingest validation.
4. **pcs-bench consumes embedded objects first.** Aggregation, metrics, and suite summaries read embedded arrays; refs are audit-only.
5. **Path references alone are invalid.** Arrays must contain embedded v0 objects, not file paths.

## What it is

`PcsBenchIngest.v0` is the **release-grade export bundle** that benchmark producers hand to pcs-bench (or pcs-core CI) before suite aggregation into `BenchmarkReport.v0`. It carries normalized sub-artifacts (runs, coverage, explain/profile quality, localization) plus execution metadata (`commands`, `logs`) and producer provenance (`source_repo`, `source_commit`, `signature_or_digest`).

`BenchmarkArtifactRef.v0` is an optional companion record that points at the **on-disk file** a producer wrote, without replacing the embedded canonical object.

## Producers

| Producer ID | Typical ingest contents |
|-------------|-------------------------|
| `labtrust-gym` | `benchmark_reproducibility.py` → runs + release reproducibility `coverage_reports` |
| `certifyedge` | certificate benchmark → `coverage_reports` + `profile_coverage_reports` |
| `provability-fabric` | admission benchmark → `failure_localization_reports`, `explain_quality_reports`, `profile_coverage_reports` |
| `scientific-memory` | `pcs-benchmark-rendering` → `explain_quality_reports` + interpretability `coverage_reports` |
| `pcs-bench` | Aggregator; may assemble ingest from multiple producers |

Golden examples (generated, not hand-authored): `examples/benchmark_ingest/*.pcs_bench_ingest.valid.json`, copied from sibling `make pcs-bench-producer` exports when present (`PCS_PRODUCER_REPOS_ROOT` or parent of pcs-core), else normalized from `examples/benchmarks/compatibility/*.dialect.json`.

## Required producer provenance

Every `PcsBenchIngest.v0` export must include:

- `source_repo` — HTTPS URI of the producer repository that generated the bundle.
- `source_commit` — 40-character git SHA of that repo at export time (not all zeros or pattern placeholders for release-grade).
- `signature_or_digest` — canonical hash of the ingest body excluding that field.

Sub-artifacts and `BenchmarkArtifactRef.v0` records repeat `source_repo` / `source_commit` when emitted from the same revision.

## Schema types (v1.0 contract surface)

| Schema | Role in ingest |
|--------|----------------|
| **PcsBenchIngest.v0** | Root producer export: embedded arrays, `commands`, `logs`, provenance, optional `artifact_refs`. |
| **BenchmarkRun.v0** | One executed benchmark case (`benchmark_runs[]`). |
| **CoverageReport.v0** | Coverage ratio for a metric (`coverage_reports[]`). |
| **FailureLocalizationResult.v0** | Failure code, responsible component, repair hint (`failure_localization_reports[]`). |
| **ExplainQualityReport.v0** | Explainability / interpretability quality (`explain_quality_reports[]`). |
| **ProfileCoverageReport.v0** | Workflow profile field coverage (`profile_coverage_reports[]`). |
| **BenchmarkArtifactRef.v0** | Sidecar file provenance (`artifact_refs[]` only). |
| **BenchmarkReport.v0** | Suite aggregation output (pcs-bench / `pcs benchmark run`), not embedded in ingest. |
| **MetricSummary.v0** | Per-metric rollup inside `BenchmarkReport.v0`. |

### PcsBenchIngest.v0

Producer bundle handed to pcs-bench before suite aggregation. All array fields are required (may be empty). `artifact_refs` is optional for `pcs-core` / `pcs-bench` aggregators; **required** for file-exporting producers at release-grade.

### BenchmarkRun.v0

Records one case execution: timing, commands, observed status/failure fields, produced artifact names, and provenance. Embedded runs are authoritative; path strings in `benchmark_runs` are invalid.

### CoverageReport.v0

Numerator/denominator coverage for a declared metric (`metric_id`), with optional `details` for producer-specific context (e.g. release reproducibility, certificate completeness).

### FailureLocalizationResult.v0

Maps an observed failure to `failure_code`, `responsible_component`, and `repair_hint_kind` per the pcs-core localization catalog.

### ExplainQualityReport.v0

Scores explainability or interpretability quality for a benchmark slice (admission, rendering, etc.).

### ProfileCoverageReport.v0

Reports which workflow-profile fields were exercised vs declared in the profile registry.

### BenchmarkArtifactRef.v0

Sidecar only: `path` (repo-relative), `sha256` (must equal embedded object `signature_or_digest`), `role`, and ref-level digest. Does not replace embedded objects.

### BenchmarkReport.v0

Post-ingest suite report: `runs`, declared `metrics`, `metric_summaries`, `summary`, `coverage`, `failures`. Built from validated ingest or native pcs-core suite execution.

### MetricSummary.v0

One metric’s `score`, `applicability`, and rollup fields inside `BenchmarkReport.v0`.

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

## Evidence tiers

| Tier | Meaning |
|------|---------|
| **schema-valid** | Passes JSON Schema and semantic checks (array shapes, ref consistency when refs exist). |
| **developer-grade** | Representative embedded content; ingest `source_commit` may be a fixture placeholder; `artifact_refs` optional. |
| **release-grade** | Live producer export: real 40-char ingest `source_commit`, non-empty `commands`, producer-specific non-empty arrays (below), matching `artifact_refs` when files are exported. |
| **audit-ready** | Release-grade plus stable digests, documented `commands`, and provenance in `examples/benchmark_ingest/provenance.manifest.json`. |

Enforced by `pcs_core.benchmark_ingest.assess_ingest_adequacy_tier()` and `validate_benchmark_ingest_examples.py --release-grade`. The CLI and provenance manifest may label this tier `external-review-grade`; the meaning is the same as **audit-ready** here.

### Release-grade minimum (all producers)

- Non-placeholder ingest `source_commit` (40 hex characters).
- Non-empty `commands` recording how the bundle was produced.
- When `artifact_refs` exist: every ref `sha256` equals the embedded object `signature_or_digest`, and every embedded export has a ref.

### Per-producer non-empty arrays

| Producer | Required arrays |
|----------|-----------------|
| LabTrust-Gym | `benchmark_runs`, `coverage_reports` |
| CertifyEdge | `coverage_reports`, `profile_coverage_reports` |
| Provability Fabric | `failure_localization_reports`, `explain_quality_reports`, `profile_coverage_reports` |
| Scientific Memory | `explain_quality_reports`, `coverage_reports` |

`BenchmarkReport.v0` is suite output (from pcs-bench or `pcs benchmark run`), not part of ingest. Publish reports only after validated ingest passes `pcs conformance run --suite benchmark-report`.

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
python scripts/validate_benchmark_ingest_examples.py --release-grade
```

The `benchmark-ingest` suite validates:

- `PcsBenchIngest.v0`, `BenchmarkArtifactRef.v0`, and embedded types (`BenchmarkRun`, `CoverageReport`, `FailureLocalizationResult`, `ExplainQualityReport`, `ProfileCoverageReport`, `BenchmarkReport`, `MetricSummary`)
- All four golden producer bundles at **release-grade** / **audit-ready**
- Compatibility normalization corpus drift
- Invalid fixtures under `examples/invalid_pcs_bench_ingest_*.json` (must fail `pcs validate`)

The suite fails when producers emit path-only ingest, all-zero `source_commit`, mismatched or orphan `artifact_refs`, empty `benchmark_runs` or `commands` on release-grade exports, or missing producer-specific reports (LabTrust coverage, CertifyEdge profile coverage, PF failure localization / explain quality, Scientific Memory explain quality).

Producer integration checklist: [producer-benchmark-ingest.md](producer-benchmark-ingest.md).
