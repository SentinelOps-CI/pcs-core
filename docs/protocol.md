# PCS Protocol (v0.1)

Proof-Carrying Science (PCS) is a cross-repo artifact protocol. **pcs-core** is the single source of truth for artifact shapes, status values, validation, and canonical hashing.

## Required v0.1 artifacts

| Artifact | Schema |
|----------|--------|
| AssumptionSet.v0 | `schemas/AssumptionSet.v0.schema.json` |
| SourceSpan.v0 | `schemas/SourceSpan.v0.schema.json` |
| ClaimArtifact.v0 | `schemas/ClaimArtifact.v0.schema.json` |
| RuntimeReceipt.v0 | `schemas/RuntimeReceipt.v0.schema.json` |
| TraceCertificate.v0 | `schemas/TraceCertificate.v0.schema.json` |
| EvidenceBundle.v0 | `schemas/EvidenceBundle.v0.schema.json` |
| ScienceClaimBundle.v0 | `schemas/ScienceClaimBundle.v0.schema.json` |
| VerificationResult.v0 | `schemas/VerificationResult.v0.schema.json` |

Downstream repos must not define competing versions of these artifacts.

## Producer metadata

Every major artifact includes:

- `schema_version` (must be `v0` for v0.1)
- `created_at` (ISO 8601 UTC)
- `producer`, `producer_version`
- `source_repo`, `source_commit`
- `status`
- `signature_or_digest` (`sha256:<64 hex>`)

## Guarantee-type separation

Rendered claims and public pages must label evidence using exactly one of:

- `formally_checked`
- `certificate_checked`
- `runtime_observed`
- `empirically_measured`
- `human_reviewed`
- `unchecked_advisory`

## Validating artifacts

```bash
pcs validate path/to/artifact.json
```

Schema-only validation uses JSON Schema Draft 2020-12. Semantic checks (trace hash alignment, assumption set presence) run in addition for composite bundles.

## Canonical hash

```bash
pcs hash path/to/artifact.json
```

See [versioning.md](versioning.md) for the canonicalization algorithm.

## Importing schemas

- **Python**: `pip install -e python/` then `from pcs_core.validate import validate_file`
- **Rust**: depend on `pcs-core` crate; deserialize with `serde_json`
- **TypeScript**: `@pcs/core` package; `parseArtifact` / `validateFile`
- **Other**: copy `schemas/*.schema.json` from this repo; pin by git tag

## Adding a future artifact type

1. Add `NewArtifact.v1.schema.json` under `schemas/` (never mutate v0 schemas in place).
2. Add valid/invalid examples.
3. Extend bindings in Python, Rust, TypeScript, and Lean.
4. Document in `versioning.md` and release notes.
5. v0.1 consumers continue using `*.v0` unchanged.
