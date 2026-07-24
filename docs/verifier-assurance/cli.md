# Verifier Assurance CLI

Exit codes for VA commands: `0` OK, `1` validation/build failure, `2` usage / argument errors (argparse).

## Commands

```bash
# Typed validators (release-grade schema + semantics)
pcs verifier profile validate profile.json
pcs verifier result validate result.json
pcs reward validate reward.json
pcs campaign validate campaign.json
pcs adjudication validate adjudication.json

# Offline report construction / verify
pcs assurance build-report \
  --campaign camp.json \
  --results ./results \
  --adjudications ./adj \
  --out report.json \
  --release-grade
pcs assurance verify-report report.json

# Generic detect + validate (any registered artifact including VA)
pcs validate any-va-artifact.json

# Suite gate
pcs conformance run --suite verifier-assurance
```

`assurance build-report` also accepts `--report-id`, `--created-at`, and `--independent-adjudication` / `--release-grade` flags matching the report builder.

## `--json` shape

Typed validate commands and `assurance verify-report` accept `--json`.

Success:

```json
{"ok": true, "artifact_type": "VerifierProfile.v1", "path": "profile.json"}
```

Failure:

```json
{
  "ok": false,
  "artifact_type": "VerificationResult.v1",
  "path": "result.json",
  "errors": [
    {"code": "FailClosedDecision", "path": "decision", "message": "..."}
  ]
}
```

`assurance build-report --json` emits the same `ok` / `errors[]` envelope on failure; on success it writes the report to `--out` and prints a short OK line (or JSON success payload when `--json` is set).

## Offline only

VA CLI paths are local filesystem only. No network access is required or performed.

## Related

- [semantic-rules.md](semantic-rules.md) — stable error codes
- [protocol.md](protocol.md) — artifact family
