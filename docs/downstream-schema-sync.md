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

**Authority:** `pcs-core/examples/labtrust-release/` is the canonical PCS v0.1 RC fixture chain.

| Rule | Detail |
|------|--------|
| Source of truth | Sync against this directory at the pinned pcs-core commit, or prove canonical-hash equivalence to `RELEASE_FIXTURE_MANIFEST.json` |
| Atomic refresh | Regenerate only via the full clean-checkout chain and atomic promote (`just generate-labtrust-release-fixtures` in pcs-core) |
| Pin values | See [labtrust-release-fixtures.md](labtrust-release-fixtures.md) |
| Verification | `pcs validate-release-chain examples/labtrust-release/` (30 checks; CI gate on `main`) |

Downstream release fixture tests must assert the same pin values as pcs-core. Schema conformance fixtures remain under `examples/labtrust/` (separate from release evidence).

## Validation and hash

- Use `pcs validate` or pcs-core language bindings for schema + semantic checks.
- Use `pcs hash` for canonical digests; do not reimplement canonicalization locally.
- Pin the same pcs-core version across all repos in a release train.
- Run `pcs registry audit` after upgrading the registry pin.
- Run `pcs conformance run --suite all` (or a subset from `conformance/`) in downstream CI.
- Conformance reports are `ConformanceReport.v0` artifacts (`checks_passed`, `checks_failed`, `failures`).

Python API (same behavior as the CLI):

```python
from pcs_core.conformance import build_conformance_report_data, run_conformance

exit_code, errors = run_conformance("hash")
report = build_conformance_report_data("hash")
```

Shared hash vectors: `pcs shared-hash-vectors verify` (Python, Rust, TypeScript must agree).

Protocol authority: [artifact-registry.md](artifact-registry.md), [semantic-check-policy.md](semantic-check-policy.md), [release-protocol.md](release-protocol.md).

See also [protocol.md](protocol.md) and [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md).
