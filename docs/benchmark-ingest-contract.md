# Benchmark ingest contract (PcsBenchIngest.v0)

Normative schemas live under [schemas/](../schemas/), the overview appears in [benchmarks.md](benchmarks.md), and producer setup is described in [producer-benchmark-ingest.md](producer-benchmark-ingest.md).

## Rules (v0)

The v0 rules establish embedded canonical objects as the authoritative source for validation and aggregation, with each ingest array holding full `BenchmarkRun.v0`, `CoverageReport.v0`, `FailureLocalizationResult.v0`, `ExplainQualityReport.v0`, and `ProfileCoverageReport.v0` records instead of path-only entries.

`artifact_refs` provide sidecar provenance only, meaning each `BenchmarkArtifactRef.v0` records `path`, content `sha256`, and export metadata while the embedded arrays remain the source that validators and aggregators read first.

Native producer reports belong in `details` or separate files, and dialect JSON from producer repositories normalizes into v0 artifacts before ingest validation runs.

The benchmark runner and pcs-core continuous integration read embedded objects first when they build aggregation, metrics, and suite summaries, and they treat refs as audit metadata.

Arrays must contain embedded v0 objects exclusively, and path-only array entries fail validation under v0 semantics.

## What it is

`PcsBenchIngest.v0` is the release-grade export bundle that benchmark producers publish to the benchmark runner or to pcs-core continuous integration before suite aggregation produces `BenchmarkReport.v0`, and the bundle carries normalized sub-artifacts together with execution metadata in `commands` and `logs` plus producer provenance in `source_repo`, `source_commit`, and `signature_or_digest`.

`BenchmarkArtifactRef.v0` is an optional companion record that points at the on-disk file a producer wrote while the embedded canonical object remains the authoritative copy inside the ingest arrays.

## Producers

| Producer ID | Typical ingest contents |
|-------------|-------------------------|
| `labtrust-gym` | `benchmark_reproducibility.py` produces runs and release reproducibility `coverage_reports` |
| `certifyedge` | Certificate benchmark produces `coverage_reports` and `profile_coverage_reports` |
| `provability-fabric` | Admission benchmark produces `failure_localization_reports`, `explain_quality_reports`, and `profile_coverage_reports` |
| `scientific-memory` | Rendering benchmark produces `explain_quality_reports` and interpretability `coverage_reports` |
| `pcs-bench` | Aggregator that may assemble ingest from multiple producers |

Golden examples are generated through materialize scripts instead of manual edits, and they live at `examples/benchmark_ingest/*.pcs_bench_ingest.valid.json`, copied from sibling `make pcs-bench-producer` exports when those exports are present at `PCS_PRODUCER_REPOS_ROOT` or the parent of pcs-core, otherwise normalized from `examples/benchmarks/compatibility/*.dialect.json`.

## Required producer provenance

Every `PcsBenchIngest.v0` export includes `source_repo` as the HTTPS URI of the producer repository that generated the bundle, `source_commit` as the 40-character git SHA of that repository at export time with real hex values for release-grade bundles, and `signature_or_digest` as the canonical hash of the ingest body computed with the same rules as other v0 artifacts.

Sub-artifacts and `BenchmarkArtifactRef.v0` records repeat `source_repo` and `source_commit` when they were emitted from the same revision.

## Schema types (v1.0 contract surface)

| Schema | Role in ingest |
|--------|----------------|
| **PcsBenchIngest.v0** | Root producer export with embedded arrays, `commands`, `logs`, provenance, and optional `artifact_refs` |
| **BenchmarkRun.v0** | One executed benchmark case in `benchmark_runs[]` |
| **CoverageReport.v0** | Coverage ratio for a metric in `coverage_reports[]` |
| **FailureLocalizationResult.v0** | Failure code, responsible component, and repair hint in `failure_localization_reports[]` |
| **ExplainQualityReport.v0** | Explainability and interpretability quality in `explain_quality_reports[]` |
| **ProfileCoverageReport.v0** | Workflow profile field coverage in `profile_coverage_reports[]` |
| **BenchmarkArtifactRef.v0** | Sidecar file provenance in `artifact_refs[]` only |
| **BenchmarkReport.v0** | Suite aggregation output from the benchmark runner or `pcs benchmark run`, separate from ingest |
| **MetricSummary.v0** | Per-metric rollup inside `BenchmarkReport.v0` |

### PcsBenchIngest.v0

The producer bundle arrives before suite aggregation, all array fields are required although they may be empty, `artifact_refs` is optional for pcs-core and benchmark-runner aggregators, and file-exporting producers include `artifact_refs` at release-grade.

### BenchmarkRun.v0

Each record documents one case execution with timing, commands, observed status and failure fields, produced artifact names, and provenance, and embedded runs supply the authoritative execution evidence.

### CoverageReport.v0

Each report states numerator and denominator coverage for a declared `metric_id` with optional `details` for producer-specific context such as release reproducibility or certificate completeness.

### FailureLocalizationResult.v0

Each result maps an observed failure to `failure_code`, `responsible_component`, and `repair_hint_kind` according to the pcs-core localization catalog.

### ExplainQualityReport.v0

Each report scores explainability or interpretability quality for a benchmark slice such as admission or rendering.

### ProfileCoverageReport.v0

Each report lists which workflow-profile fields were exercised compared with the declarations in the profile registry.

### BenchmarkArtifactRef.v0

Sidecar records include repo-relative `path`, `sha256` matching the embedded object `signature_or_digest`, `role`, and a ref-level digest, and validators always read the embedded object first.

### BenchmarkReport.v0

Suite reports include `runs`, declared `metrics`, `metric_summaries`, `summary`, `coverage`, and `failures`, and they are built from validated ingest or from native pcs-core suite execution.

### MetricSummary.v0

Each summary states one metric score, applicability, and rollup fields inside `BenchmarkReport.v0`.

## Embedded objects and path references

Each canonical ingest array holds full v0 objects as listed below.

- `benchmark_runs` contains `BenchmarkRun.v0[]`
- `coverage_reports` contains `CoverageReport.v0[]`
- `failure_localization_reports` contains `FailureLocalizationResult.v0[]`
- `explain_quality_reports` contains `ExplainQualityReport.v0[]`
- `profile_coverage_reports` contains `ProfileCoverageReport.v0[]`

Empty arrays remain valid when a producer has nothing to contribute for that slot.

Optional provenance appears in `artifact_refs` as `BenchmarkArtifactRef.v0[]`, and each ref documents where the producer stored the same logical artifact on disk.

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

Consumers read embedded arrays first, `sha256` on each ref matches the content digest of the embedded object through `signature_or_digest`, `signature_or_digest` on the ref itself is the canonical hash of the ref record, and `path` is relative to the producer repository export root according to per-producer convention.

Repositories that emit file paths today should add normalized embedded objects alongside `artifact_refs`, using pcs-core normalizers or in-repository adapters.

## Digesting

Each embedded sub-artifact carries its own `signature_or_digest` under pcs-core canonical JSON rules, each `BenchmarkArtifactRef.sha256` equals the matching embedded artifact `signature_or_digest`, and `PcsBenchIngest.signature_or_digest` covers the ingest body with the same exclusion rule used for other v0 artifacts.

## Source commits

`source_repo` and `source_commit` on the ingest identify the producer repository revision that generated the bundle, sub-artifacts may repeat the same fields when emitted from that revision, refs repeat them for the file export line of provenance, and reviewers pin `source_commit` to the git SHA of the producer run while the benchmark runner records that pin in `BenchmarkReport.v0` and conformance metadata.

## Benchmark runner consumption

Validation begins with `pcs validate` on the ingest file or `pcs conformance run --suite benchmark-ingest`, embedded arrays supply the data for metrics and aggregation, `artifact_refs` support audit trails and diffing of on-disk exports, metrics map through `BenchmarkMetricRegistry.v0` into `BenchmarkReport.v0` with `metric_summaries`, and dialect JSON from producers should pass through `pcs benchmark normalize` before ingest validation when the upstream shape still reflects a legacy dialect.

## Evidence tiers

| Tier | Meaning |
|------|---------|
| **schema-valid** | Passes JSON Schema and semantic checks for array shapes and ref consistency when refs exist |
| **developer-grade** | Representative embedded content where ingest `source_commit` may use fixture placeholders and `artifact_refs` may be absent |
| **release-grade** | Live producer export with a real 40-character ingest `source_commit`, non-empty `commands`, producer-specific non-empty arrays listed below, and matching `artifact_refs` when files are exported |
| **audit-ready** | Release-grade bundles with stable digests, documented `commands`, and provenance recorded in `examples/benchmark_ingest/provenance.manifest.json` |

`pcs_core.benchmark_ingest.assess_ingest_adequacy_tier()` and `validate_benchmark_ingest_examples.py --release-grade` enforce these tiers, and the command line interface together with the provenance manifest may label audit-ready bundles as `external-review-grade` with identical meaning.

### Release-grade minimum (all producers)

Release-grade bundles use a full 40-character hex ingest `source_commit`, include non-empty `commands` that record how the bundle was produced, and when `artifact_refs` are present every ref `sha256` equals the embedded object `signature_or_digest` while every embedded export receives a matching ref.

### Per-producer non-empty arrays

| Producer | Required arrays |
|----------|-----------------|
| LabTrust-Gym | `benchmark_runs`, `coverage_reports` |
| CertifyEdge | `coverage_reports`, `profile_coverage_reports` |
| Provability Fabric | `failure_localization_reports`, `explain_quality_reports`, `profile_coverage_reports` |
| Scientific Memory | `explain_quality_reports`, `coverage_reports` |

`BenchmarkReport.v0` is suite output from the benchmark runner or from `pcs benchmark run` and sits outside the ingest document, and publication should follow validated ingest together with a passing `pcs conformance run --suite benchmark-report`.

## Regeneration

Producer repositories capture dialect JSON under `examples/benchmarks/compatibility/*.dialect.json`, and pcs-core materializes golden ingest bundles through the commands below.

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

The `benchmark-ingest` suite exercises `PcsBenchIngest.v0`, `BenchmarkArtifactRef.v0`, embedded types, all four golden producer bundles at release-grade or audit-ready, compatibility normalization corpus drift, and invalid fixtures under `examples/invalid_pcs_bench_ingest_*.json` that must fail `pcs validate`.

The suite reports failure when producers publish path-only ingest, all-zero `source_commit` values, mismatched or orphan `artifact_refs`, empty `benchmark_runs` or `commands` on release-grade exports, or missing producer-specific reports for LabTrust coverage, CertifyEdge profile coverage, Provability Fabric localization and explain quality, or Scientific Memory explain quality.

Producer integration steps appear in [producer-benchmark-ingest.md](producer-benchmark-ingest.md).
