# PCS conformance suites

Run protocol checks against a pinned **pcs-core** install. Each suite maps to documentation under this directory and to tests in `python/tests/test_protocol_conformance.py`.

The documentation index is [docs/README.md](../docs/README.md).

## CLI

```bash
pcs conformance run --suite all
pcs conformance run --suite release-chain
pcs conformance run --suite benchmark-ingest
pcs conformance run --suite multidomain
pcs conformance run --suite all --json   # ConformanceReport.v0
```

Available suites include `release-manifest`, `handoff-manifest`, `artifact-registry`, `semantic-check-execution`, `release-chain-validation`, `release-chain`, `component-release-fragment`, `hash`, `migration`, `status-transition`, `workflow-profile`, `tool-use`, `computation`, `benchmark`, `benchmark-report`, `benchmark-ingest`, `multidomain`, `verifier-assurance`, `all`.

## Downstream CI

```python
from pcs_core.conformance import build_conformance_report_data, list_suites, run_conformance

code, errors = run_conformance("all")
assert code == 0, errors
```

Continuous integration may also invoke `pcs conformance run --suite all` in a subprocess.

The registry catalog is listed through `pcs registry audit` as described in [docs/semantic-check-policy.md](../docs/semantic-check-policy.md).

## Suite index

| Suite | Directory | Focus |
|-------|-----------|--------|
| Release manifest | `release-manifest/` | `ReleaseManifest.v0` |
| Handoff manifest | `handoff-manifest/` | `HandoffManifest.v0` |
| Artifact registry | `artifact-registry/` | `ArtifactRegistry.v0` |
| Release chain validation | `release-chain-validation/` | `ReleaseChainValidationResult.v0` |
| Hash vectors | `hash/` | Canonical digests |
| Migration | `migration/` | `pcs migrate` reports |
| Status transitions | `status-transition/` | Status policy |
| Workflow profiles | `workflow-profile/` | `WorkflowProfile.v0` |
| Tool-use | `tool-use/` | Agent tool-use safety |
| Computation | `computation/` | Computation reproducibility |
| Multi-domain | `multidomain/` | LabTrust + tool-use + computation |
| Benchmark | `benchmark/` | Benchmark fixture trees |
| Benchmark report | `benchmark-report/` | `BenchmarkReport.v0` and corpus |
| Benchmark ingest | `benchmark-ingest/` | `PcsBenchIngest.v0` — [docs/benchmark-ingest-contract.md](../docs/benchmark-ingest-contract.md) |
| Verifier Assurance | `verifier-assurance/` | PCS-VA six-artifact family — [docs/verifier-assurance/protocol.md](../docs/verifier-assurance/protocol.md) |
