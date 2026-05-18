# PCS protocol conformance suite

Downstream repos can run subsets against a pinned **pcs-core** install.

## CLI

```bash
pcs conformance run --suite all
pcs conformance run --suite handoff-manifest
pcs conformance run --suite release-chain
pcs conformance run --suite hash
pcs conformance run --suite workflow-profile
pcs conformance run --suite tool-use
pcs conformance run --suite computation
pcs conformance run --suite multidomain
```

Available suites: `release-manifest`, `handoff-manifest`, `artifact-registry`, `semantic-check-execution`, `release-chain-validation`, `release-chain`, `component-release-fragment`, `hash`, `migration`, `status-transition`, `workflow-profile`, `tool-use`, `computation`, `multidomain`, `all`.

Machine-readable output validates against `schemas/ConformanceReport.v0.schema.json`:

```bash
pcs conformance run --suite all --json
```

## Downstream integration

Install pcs-core and call from CI:

```python
from pcs_core.conformance import build_conformance_report_data, list_suites, run_conformance

code, errors = run_conformance("all")
report = build_conformance_report_data("all")
assert code == 0, errors
assert report["status"] == "passed"
```

Or invoke the CLI in a subprocess: `pcs conformance run --suite all`.

Registry semantic-check catalog:

```bash
pcs registry audit
```

## Per-suite docs

| Suite | Directory |
|-------|-----------|
| Release manifest | `conformance/release-manifest/` |
| Handoff manifest | `conformance/handoff-manifest/` |
| Artifact registry | `conformance/artifact-registry/` |
| Release chain validation | `conformance/release-chain-validation/` |
| Hash vectors | `conformance/hash/` |
| Migration | `conformance/migration/` |
| Status transitions | `conformance/status-transition/` |
| Workflow profiles | `conformance/workflow-profile/` |
| Tool-use workflow | `conformance/tool-use/` |
| Scientific computation reproducibility | `conformance/computation/` |
| Multi-domain (LabTrust + tool-use + computation) | `conformance/multidomain/` |

Integration tests: `pytest tests/test_protocol_conformance.py`.

Semantic check policy: [docs/semantic-check-policy.md](../docs/semantic-check-policy.md).
