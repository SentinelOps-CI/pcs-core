# PCS protocol conformance suite

Downstream repos can run subsets against a pinned **pcs-core** install.

## CLI

```bash
pcs conformance run --suite all
pcs conformance run --suite handoff-manifest
pcs conformance run --suite release-chain
pcs conformance run --suite hash
```

Available suites: `release-manifest`, `handoff-manifest`, `artifact-registry`, `release-chain-validation`, `release-chain`, `component-release-fragment`, `hash`, `migration`, `status-transition`, `all`.

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

Integration tests: `pytest tests/test_protocol_conformance.py`.

Semantic check policy: [docs/semantic-check-policy.md](../docs/semantic-check-policy.md).
