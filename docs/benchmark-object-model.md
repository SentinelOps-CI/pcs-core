# Benchmark object model (v0)

PCS benchmarks keep cases as the definition of what is being tested, runs as the record of what happened during execution, and reports as the suite-level score aggregation, and downstream repositories including the benchmark runner, Provability Fabric, CertifyEdge, LabTrust-Gym, and Scientific Memory normalize into these artifacts while keeping separate status dimensions for execution, admission, certificates, and rendering.

## Core artifacts

| Artifact | Role |
|----------|------|
| `BenchmarkCase.v0` | Declares inputs and expected benchmark outcome for one case |
| `BenchmarkRun.v0` | Records one execution of a case with layered status fields |
| `BenchmarkReport.v0` | Aggregates runs with declared metric IDs, `metric_summaries`, and rollups |
| `MetricSummary.v0` | One measured or N/A score for a `metric_id` |
| `CoverageReport.v0` | Detailed coverage snapshot for a single legacy metric channel |
| `ExplainQualityReport.v0` | PF and SM explain-quality or render-audit sections |
| `ProfileCoverageReport.v0` | PF workflow profile coverage across artifacts, checks, and handoffs |
| `FailureLocalizationResult.v0` | Per-run verdict on failure-code and component alignment |
| `PcsBenchIngest.v0` | Normalized export bundle for the benchmark runner with embedded runs, coverage, explain and profile reports, commands, and logs |
| `BenchmarkArtifactRef.v0` | Optional on-disk path and content digest for an embedded ingest artifact |

## Status dimensions

### Benchmark execution status (`BenchmarkCase.v0.expected_status`, `BenchmarkRun.v0.observed_status`)

`expected_status` and `observed_status` use benchmark execution vocabulary exclusively, including `passed`, `failed`, `skipped`, and `error`, and admission or certificate semantics belong in the dedicated fields below.

### System outcome (`BenchmarkCase.v0.expected_system_outcome`, optional)

System outcome uses `benchmark_system_outcome` in `common.defs.json`, including `admitted`, `rejected`, `stale`, `import_failed`, `render_failed`, `query_failed`, `comparison_failed`, `formal_failed`, `certificate_rejected`, and `unknown`.

### Detection layer (`BenchmarkCase.v0.expected_detection_layer`, optional)

Detection layer uses `benchmark_detection_layer` values such as `labtrust`, `certifyedge`, and `formal_kernel` so the benchmark runner can score localization without overloading execution status.

### Benchmark run execution status (`BenchmarkRun.v0.observed_status`)

Execution status records whether the benchmark harness considers the case to have met its expectation, and suite pass or fail counts in `BenchmarkReport.v0.summary` rely on this field alone.

| Value | Meaning |
|-------|---------|
| `passed` | Observed outcome matches `BenchmarkCase.v0` expectation |
| `failed` | Mismatch such as wrong failure or silent pass |
| `skipped` | Case was skipped by the harness |
| `error` | Harness or infrastructure error |

### System admission outcome (`BenchmarkRun.v0.system_admission_outcome`)

Admission outcome records whether an admission gate such as Provability Fabric bundle admission or Scientific Memory import policy accepted the artifact bundle.

| Value | Meaning |
|-------|---------|
| `admitted` | Admission checks passed |
| `rejected` | Admission explicitly rejected |
| `deferred` | Admission pending or partial |
| `not_evaluated` | Admission step absent from this workflow |

### Release-chain status (`BenchmarkRun.v0.release_chain_status`)

Release-chain status records the result of pcs-core release-chain validation on the fixture directory.

| Value | Meaning |
|-------|---------|
| `valid` | Release-chain validation completed without blocking issues |
| `invalid` | One or more blocking issues |
| `not_applicable` | Case omits a full release tree |

### Certificate status (`BenchmarkRun.v0.certificate_status`)

Certificate status records the trust certificate artifact under test, including trace, tool-use, and computation witnesses, and it follows CertifyEdge and certificate producer semantics separate from benchmark pass or fail.

| Value | Meaning |
|-------|---------|
| `CertificateChecked` | Certificate in release-ready state |
| `Rejected` | Certificate rejected |
| `Stale` | Certificate stale |
| `not_applicable` | Certificate outside case scope |

### Scientific Memory import status (`BenchmarkRun.v0.scientific_memory_import_status`)

Import status mirrors `scientific_memory_import_report.verification_status` and related import gates.

| Value | Meaning |
|-------|---------|
| `passed` | Import verification passed |
| `failed` | Import failed |
| `not_applicable` | Scientific Memory import report absent from fixture |

### Scientific Memory render status (`BenchmarkRun.v0.scientific_memory_render_status`)

Render status records whether render and explain-quality requirements are satisfied as defined in `ExplainQualityReport.v0`.

| Value | Meaning |
|-------|---------|
| `rendered` | All required explain sections present |
| `incomplete` | Render or section gaps |
| `not_applicable` | SM render outside case scope |

## Valid and invalid cases

For `case_kind == valid_release`, `expected_system_outcome` is `admitted`, `expected_failure_code`, `expected_responsible_component`, and `expected_repair_hint_kind` are null, and `BenchmarkRun.v0` failure localization fields are null when the case expects success.

Invalid cases require non-null expected failure metadata.

## Metrics in `BenchmarkReport.v0`

Option A in v0 keeps `metrics` as the array of declared `benchmark_metric_id` values for the suite and `metric_summaries` as the array of `MetricSummary.v0` records with measured results and applicability.

Legacy short names such as `release_reproducibility` are deprecated in reports in favor of `release_reproducibility_score` and related identifiers, and `BenchmarkMetricRegistry.v0` maps IDs to definitions together with optional legacy aliases.

The `summary` object retains case counts and optional rollup floats for backward compatibility while canonical scores live in `metric_summaries`.

## Producer mapping

| Producer | Primary artifacts |
|----------|-------------------|
| pcs-bench | `BenchmarkReport.v0`, `MetricSummary.v0` |
| pcs-core | All types through the reference runner |
| Provability Fabric | `ExplainQualityReport.v0`, `ProfileCoverageReport.v0`, admission dialect normalized to v0 |
| CertifyEdge | `CoverageReport.v0` and certificate benchmark mapped to `MetricSummary.v0` |
| LabTrust-Gym | `BenchmarkCase.v0` manifests |
| Scientific Memory | `ExplainQualityReport.v0` for render benchmark |

Normalization paths appear in [producer-benchmark-ingest.md](producer-benchmark-ingest.md).
