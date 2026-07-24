# Verifier Assurance examples

Fixtures for the six release-grade PCS-VA artifact types.

## Layout

```text
examples/verifier_assurance/
  valid/<case>/...                 # positive cases (multi-file where needed)
  invalid/<case>/manifest.json     # expected_error + artifact_type
                     artifact.json # [+ optional profile.json / result(s) / campaign.json]
  VerifierProfile.v1.valid.json    # flat pin samples
  VerificationResult.v1.valid.json
  README.md
```

Invalid cases use `manifest.json` with `expected_error` set to a stable semantic
code (or a schema error substring). Multi-file rules load sibling context from
`profile.json`, `result.json`, `results/`, and/or `campaign.json`.

## Commands

```bash
pcs validate examples/verifier_assurance/VerifierProfile.v1.valid.json
pcs conformance run --suite verifier-assurance
```

See [docs/verifier-assurance/semantic-rules.md](../../docs/verifier-assurance/semantic-rules.md)
and [docs/verifier-assurance/protocol.md](../../docs/verifier-assurance/protocol.md).

Regenerate nested fixtures after schema changes (maintainers):

```bash
python scripts/gen_va_fixtures.py
```
