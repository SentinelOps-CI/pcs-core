# PCS migration policy (v0.1)

## Principles

1. **pcs-core owns schemas** — downstream repos vendor or submodule; they do not fork shapes.
2. **Migration is explicit** — every transform emits a machine-readable report.
3. **Release mode is strict** — migrations that weaken provenance or hashes are rejected for release tags.

## Patch-compatible changes

- Add JSON Schema `description` text
- Add optional object properties not required in release mode
- Add new enum values only when registry and status policy are updated in the same release

## Minor-compatible changes

- Add optional top-level fields consumed only by new tooling
- Add new semantic checks that existing valid artifacts already satisfy

## Breaking changes

- Remove or rename required fields
- Narrow `status` enums without migration path
- Change canonical hash rules (requires new digest namespace and coordinated SDK release)

## Deprecation windows

Breaking changes require:

1. A pcs-core release note in `docs/releases/`
2. Updated `ArtifactRegistry.v0` entries marking old types `Deprecated`
3. A documented migration command path (`pcs migrate`)

## `pcs migrate` (v0.1 baseline)

```bash
pcs migrate --from v0 --to v0 examples/runtime_receipt.valid.json
```

v0.1 ships **identity migration** for `v0 -> v0` (validation + report only). Non-identity version pairs return an error until a future schema version is defined.

## Legacy aliases

Both `examples/labtrust-release/RELEASE_FIXTURE_MANIFEST.json` and `release_manifest.v0.json` are maintained in sync; `pcs validate-release-chain` continues to use the legacy manifest while protocol tooling consumes `ReleaseManifest.v0`.

## Migration reports

Reports include `from_version`, `to_version`, `artifact_type`, `changes`, and `status` (`noop` or `migrated`).
