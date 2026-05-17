# Downstream schema sync policy

pcs-core is the canonical source for all PCS v0.1 JSON Schemas. LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory must stay aligned with this repository.

## Mirroring rules

1. Downstream repos may mirror schemas **only as generated copies** of `pcs-core/schemas/`.
2. Mirrored schemas must be **byte-for-byte equivalent** to pcs-core at the pinned revision, unless a file is explicitly documented as a **legacy fixture** (read-only negative example, never used for publish/import).
3. Do not edit mirrored schema files in downstream repos. Refresh copies from pcs-core and record the git tag or commit in release notes.
4. Typical mirror paths:
   - `schemas/pcs/` (Scientific Memory, Provability Fabric)
   - `vendor/pcs-core/schemas/` (submodule layouts)

## Schema drift checks

Every downstream repo must provide a schema drift check (for example `just pcs-schema-diff`) that compares the vendored mirror to pcs-core:

```bash
scripts/pcs-schema-diff.sh path/to/vendored/schemas
```

pcs-core reference check:

```bash
just pcs-schema-diff schemas
```

**Schema drift blocks v0.1 release.** CI must fail when the mirror differs from the pinned pcs-core revision.

## LabTrust conformance fixtures

Cross-repo validation must use the shared fixture set under `examples/labtrust/`:

| File | Stage |
|------|--------|
| `science_claim_bundle.pending.valid.json` | LabTrust-Gym (pending bundle) |
| `trace_certificate.valid.json` | CertifyEdge |
| `science_claim_bundle.certified.valid.json` | LabTrust-Gym (certified bundle) |
| `verification_result.valid.json` | Provability Fabric (verification) |
| `signed_science_claim_bundle.valid.json` | Provability Fabric (signed export) → Scientific Memory import |

Negative fixtures (must fail validation):

| File | Failure reason |
|------|----------------|
| `invalid_signed_schema_version_artifact_name.json` | `schema_version: "SignedScienceClaimBundle.v0"` instead of `"v0"` |
| `invalid_singular_runtime_receipt_bundle.json` | `runtime_receipt` instead of required `runtime_receipts` |
| `invalid_failed_verification_result.json` | failed verification checks with import-ready top-level status |
| `invalid_missing_trace_certificate.json` | certified claim without attached `TraceCertificate` |

Downstream test suites should copy or reference these paths and assert pass/fail accordingly. Python conformance tests live in `python/tests/test_labtrust_conformance.py`.

Fixture authority is defined in [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md#release-fixture-authority).

## Release-candidate fixtures (canonical)

**Authority:** `pcs-core/examples/labtrust-release/` is the only canonical PCS v0.1 release-candidate fixture set.

| Rule | Detail |
|------|--------|
| Source of truth | Copy files from pcs-core at the pinned commit; do not regenerate partial fixtures in downstream repos |
| Atomic refresh | Regenerate only via the full clean-checkout chain and atomic promote (`just generate-labtrust-release-fixtures` in pcs-core) |
| Pin values | See [labtrust-rc-canonical.md](labtrust-rc-canonical.md) (`certificate_id`, `trace_hash`, certified bundle hash, per-repo commits) |
| Verification | `pcs validate-release-chain examples/labtrust-release/` or `just validate-labtrust-release-fixtures` |

Downstream release fixture tests must assert the same pin values as pcs-core. Schema conformance fixtures remain under `examples/labtrust/` (separate from release evidence).

## Validation and hash

- Use `pcs validate` or pcs-core language bindings for schema + semantic checks.
- Use `pcs hash` for canonical digests; do not reimplement canonicalization locally.
- Pin the same pcs-core version across all repos in a release train.

See also [protocol.md](protocol.md) and [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md).
