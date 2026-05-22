# Benchmark object model (v0)

PCS benchmarks separate **what is being tested** (cases), **what happened when it ran** (runs), and **how the suite scored** (reports). Downstream repos (pcs-bench, Provability Fabric, CertifyEdge, LabTrust-Gym, Scientific Memory) normalize into these artifacts; they must not overload a single `status` field.

## Core artifacts

| Artifact | Role |
|----------|------|
| `BenchmarkCase.v0` | Declares inputs and expected benchmark outcome for one case |
| `BenchmarkRun.v0` | Records one execution of a case, with layered status fields |
| `BenchmarkReport.v0` | Aggregates runs: declared metric IDs + `metric_summaries` + rollups |
| `MetricSummary.v0` | One measured (or N/A) score for a `metric_id` |
| `CoverageReport.v0` | Detailed coverage snapshot for a single legacy metric channel |
| `ExplainQualityReport.v0` | PF/SM explain-quality or render-audit sections |
| `ProfileCoverageReport.v0` | PF workflow profile coverage (artifacts, checks, handoffs) |
| `FailureLocalizationResult.v0` | Per-run verdict on failure-code / component alignment |
| `PcsBenchIngest.v0` | Normalized export bundle for pcs-bench (embedded runs, coverage, explain/profile, commands, logs) |
| `BenchmarkArtifactRef.v0` | Optional on-disk path + content digest for an embedded ingest artifact |

## Status dimensions (do not conflate)

### Benchmark execution status (`BenchmarkCase.v0.expected_status`, `BenchmarkRun.v0.observed_status`)

`expected_status` / `observed_status` use **benchmark execution** vocabulary only (`passed`, `failed`, `skipped`, `error`). Do not overload these for admission or certificate semantics.

### System outcome (`BenchmarkCase.v0.expected_system_outcome`, optional)

Uses `benchmark_system_outcome` in `common.defs.json`: `admitted`, `rejected`, `stale`, `import_failed`, `render_failed`, `query_failed`, `comparison_failed`, `formal_failed`, `certificate_rejected`, `unknown`.

### Detection layer (`BenchmarkCase.v0.expected_detection_layer`, optional)

Uses `benchmark_detection_layer` (e.g. `labtrust`, `certifyedge`, `formal_kernel`) so pcs-bench can score localization without overloading `expected_status`.

### Benchmark run execution status (`BenchmarkRun.v0.observed_status`)

Whether the **benchmark harness** considers the case to have met its expectation.

| Value | Meaning |
|-------|---------|
| `passed` | Observed outcome matches `BenchmarkCase.v0` expectation |
| `failed` | Mismatch (wrong failure, silent pass, etc.) |
| `skipped` | Case not executed |
| `error` | Harness or infrastructure error |

This is the only status used for suite pass/fail counts in `BenchmarkReport.v0.summary`.

### System admission outcome (`BenchmarkRun.v0.system_admission_outcome`)

Whether an **admission gate** (e.g. PF bundle admission, SM import policy) accepted the artifact bundle.

| Value | Meaning |
|-------|---------|
| `admitted` | Admission checks passed |
| `rejected` | Admission explicitly rejected |
| `deferred` | Admission pending or partial |
| `not_evaluated` | No admission step in this workflow |

### Release-chain status (`BenchmarkRun.v0.release_chain_status`)

Result of **pcs-core release-chain validation** on the fixture directory.

| Value | Meaning |
|-------|---------|
| `valid` | No blocking release-chain issues |
| `invalid` | One or more blocking issues |
| `not_applicable` | Case does not include a full release tree |

### Certificate status (`BenchmarkRun.v0.certificate_status`)

Status of the **trust certificate** artifact under test (trace, tool-use, computation witness).

| Value | Meaning |
|-------|---------|
| `CertificateChecked` | Certificate in release-ready state |
| `Rejected` | Certificate rejected |
| `Stale` | Certificate stale |
| `not_applicable` | No certificate in scope |

Maps to CertifyEdge / certificate producer semantics, not benchmark pass/fail.

### Scientific Memory import status (`BenchmarkRun.v0.scientific_memory_import_status`)

`scientific_memory_import_report.verification_status` and related import gates.

| Value | Meaning |
|-------|---------|
| `passed` | Import verification passed |
| `failed` | Import failed |
| `not_applicable` | No SM import report in fixture |

### Scientific Memory render status (`BenchmarkRun.v0.scientific_memory_render_status`)

Whether **render / explain-quality** requirements are satisfied (see `ExplainQualityReport.v0`).

| Value | Meaning |
|-------|---------|
| `rendered` | All required explain sections present |
| `incomplete` | Render or section gaps |
| `not_applicable` | SM render not in scope |

## Valid vs invalid cases

For `case_kind == valid_release`:

- `expected_system_outcome` is **`admitted`**
- `expected_failure_code`, `expected_responsible_component`, and `expected_repair_hint_kind` are **`null`**
- `BenchmarkRun.v0` failure localization fields are **`null`** when no failure is expected

For invalid cases, expected failure metadata is **required** (non-null).

## Metrics in `BenchmarkReport.v0`

**Option A (v0):**

- `metrics`: array of `benchmark_metric_id` values — **declared** metrics for the suite
- `metric_summaries`: array of `MetricSummary.v0` — **measured** results with applicability

Legacy short names (`release_reproducibility`) are deprecated in reports; use `release_reproducibility_score` and friends. `BenchmarkMetricRegistry.v0` maps IDs to definitions and optional legacy aliases.

`summary` retains case counts and optional rollup floats for backward compatibility; canonical scores live in `metric_summaries`.

## Producer mapping

| Producer | Primary artifacts |
|----------|-------------------|
| pcs-bench | `BenchmarkReport.v0`, `MetricSummary.v0` |
| pcs-core | All types (reference runner) |
| Provability Fabric | `ExplainQualityReport.v0`, `ProfileCoverageReport.v0`, admission dialect → normalized |
| CertifyEdge | `CoverageReport.v0` / certificate benchmark → `MetricSummary.v0` |
| LabTrust-Gym | `BenchmarkCase.v0` manifests |
| Scientific Memory | `ExplainQualityReport.v0` (render benchmark) |

See [producer-benchmark-ingest.md](producer-benchmark-ingest.md) for normalization paths.
