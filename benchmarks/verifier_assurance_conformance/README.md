# Verifier Assurance producer conformance

Producer-shaped fixtures for OVK / LabTrust dialect rejection until real exports land.
Exercised by `pcs conformance run --suite verifier-assurance`.

## Layout

```text
benchmarks/verifier_assurance_conformance/
  valid/          # must pass schema + semantics
  invalid/        # manifest.json with expected_error
  README.md
```

## Required producer emission rules

- Explicit `artifact_type` and `schema_version: "v1"`.
- Nested `integrity` (no `signature_or_digest`).
- Decimal strings for rates/rewards (no JSON floats).
- Typed indeterminate decisions (never collapse indeterminate to reject/accept).
- Explicit `null` for unused profile config digest slots.
- Adjudication: commitment + location class; no protected rationale content in public exports.
- Fail-closed: timeout / unavailable / error execution statuses must not yield `accept`.

## Six-artifact surface only

Producers pin the PCS-VA six-artifact family documented in
[docs/verifier-assurance/protocol.md](../../docs/verifier-assurance/protocol.md).
Do not fork schemas under producer trees.

Sync downstream mirrors via [docs/downstream-schema-sync.md](../../docs/downstream-schema-sync.md).
