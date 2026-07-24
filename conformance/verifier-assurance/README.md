# Conformance suite: `verifier-assurance`

Suite id: `verifier-assurance`.

## Run

```bash
pcs conformance run --suite verifier-assurance
```

## What it checks

| Check | Source |
|-------|--------|
| Valid nested + flat VA fixtures | `examples/verifier_assurance/valid/`, `*.valid.json` |
| Invalid cases with expected codes | `examples/verifier_assurance/invalid/*/manifest.json` |
| Report rebuild determinism | `examples/verifier_assurance/valid/report_rebuild/` |
| Golden report digest / tamper reject | same rebuild tree |
| Producer dialect gate | `benchmarks/verifier_assurance_conformance/` |

Implementation: `python/pcs_core/conformance.py` (`_suite_verifier_assurance`).

## Docs

- [docs/verifier-assurance/protocol.md](../../docs/verifier-assurance/protocol.md)
- [docs/verifier-assurance/semantic-rules.md](../../docs/verifier-assurance/semantic-rules.md)
- [docs/verifier-assurance/cli.md](../../docs/verifier-assurance/cli.md)
- [docs/verifier-assurance/non-claims.md](../../docs/verifier-assurance/non-claims.md)
