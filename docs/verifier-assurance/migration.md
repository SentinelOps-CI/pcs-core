# Verifier Assurance migration

## Coexistence with v0

- Frozen `*.v0` schemas are immutable. Do not mutate `VerificationResult.v0`.
- VA artifacts are new `*.v1` files only (`common.defs.json#/$defs/schema_version_v1`).
- LabTrust/PF import checks continue on v0; assurance decision records use `VerificationResult.v1`.
- There is **no** auto-upgrade from `VerificationResult.v0` to `VerificationResult.v1`.

## Downstream sync

1. Pin pcs-core (git SHA or tagged release) in producer CI.
2. Vendor or install schemas via [../downstream-schema-sync.md](../downstream-schema-sync.md).
3. Emit the six VA types only; do not invent parallel schema forks under producer trees.
4. Keep decimal strings for rates/rewards; keep nested `integrity`; omit `signature_or_digest` on VA roots.
5. Re-run `pcs schema check`, `pcs conformance run --suite verifier-assurance`, and producer dialect fixtures after each pcs-core bump.

## Breaking producer expectations

If a producer previously expected Invocation / Replay / Mutation PCS artifact types: those are **not** part of the public six-artifact family. Bind local run evidence with opaque `invocation_ref` on `VerificationResult.v1`, or keep producer-private evidence packs outside pcs-core schemas.
