# Benchmark metrics (v0)

PCS benchmarks measure release-chain trust properties using portable `BenchmarkReport.v0` artifacts.

**Report shape (v0):**

- `metrics` — declared `benchmark_metric_id` values for the suite
- `metric_summaries` — measured `MetricSummary.v0` rows (score, applicability, numerator, denominator)
- `summary` / `coverage` — rollups and detailed coverage snapshots (legacy-friendly)

**Canonical machine-readable definitions:** `examples/benchmark_metric_registry.valid.json` (`BenchmarkMetricRegistry.v0`). Metric IDs use the `*_score` suffix. Coverage blocks may still use legacy short `metric` names; scores in `metric_summaries` always use metric IDs.

See also [benchmarks.md](benchmarks.md) and [producer-benchmark-ingest.md](producer-benchmark-ingest.md).

## Release reproducibility

A release is **reproducible** when a clean checkout of the pinned `source_repo` at `source_commit` can regenerate or revalidate the full release chain and obtain the same canonical hashes for every declared artifact, except fields explicitly excluded by the canonical hashing rules (for example placeholder digests during draft materialization).

**Measured as:** the proportion of benchmark cases in a suite whose `observed_status` is `passed` for `valid_release` cases, combined with successful re-validation of the release directory without hash drift.

## Failure localization accuracy

A failure is **correctly localized** when `BenchmarkRun.v0.observed_responsible_component` equals `BenchmarkCase.v0.expected_responsible_component`.

**Responsible components (v0):**

| Component | Typical failure domain |
|-----------|------------------------|
| `runtime_producer` | Runtime receipt, trace, placeholder commits, unauthorized tool calls |
| `certificate_producer` | Trace certificate, tool-use certificate, rejected witnesses |
| `verifier` | Verification result, verified-input hash binding |
| `registry` | Artifact registry coverage, schema validation against registry |
| `formal_kernel` | Proof obligations and Lean check results |
| `scientific_memory` | Scientific memory import and render |
| `release_manifest` | Release manifest presence and artifact listing |
| `handoff` | Handoff manifest hash alignment |
| `hashing` | Trace hash, bundle hash, manifest hash mismatches |
| `unknown` | Unmapped failure codes |

**Measured as:** `failure_localization_accuracy = hits / invalid_cases` in `BenchmarkReport.v0.summary`.

## Certificate completeness

A certificate is **complete** when all release-required fields are present, every expected hash is bound to the correct upstream artifact, and each required semantic check has either passed or failed with an explicit status without silent gaps.

**Measured as:** suite coverage snapshot `certificate_completeness` (passed valid releases over total cases that exercise certificate binding).

## Registry coverage

**Registry coverage** is the proportion of artifacts in a release whose artifact type, producer, required fields, allowed statuses, and semantic checks are represented in `ArtifactRegistry.v0`.

**Measured as:** `registry_coverage` in `BenchmarkReport.v0.coverage`, derived from `ReleaseChainValidationResult.v0` checks and deferred registry audit gaps.

## Formal-check coverage

**Formal-check coverage** is the proportion of release-blocking trust-envelope invariants that appear in `ProofObligation.v0` and are checked by `LeanCheckResult.v0` (including per-obligation pass/fail in `formal_checks`).

**Measured as:** `formal_check_coverage` in `BenchmarkReport.v0.summary` and the `formal_checks` block under `coverage`.

## Scientific Memory interpretability

**Scientific Memory interpretability** measures whether the rendered claim exposes all required audit sections, including provenance, hashes, handoffs, verification, formal checks, limitations, lineage, and repair hints.

**Measured as:** `scientific_memory_render_coverage` in `BenchmarkReport.v0.summary`, derived from `scientific_memory_import_report.json` required keys on releases that exercise memory import.

## Repair hint accuracy

When a case expects a repair hint kind, the run **matches** when `BenchmarkRun.v0.observed_repair_hint` equals the hint implied by the expected responsible component (`benchmark_localization.REPAIR_HINT_BY_COMPONENT`).

**Measured as:** `repair_hint_accuracy` in `BenchmarkReport.v0.summary`.
