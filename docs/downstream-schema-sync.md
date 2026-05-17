# Downstream schema sync policy

pcs-core is the canonical source for all PCS v0.1 JSON Schemas. LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory must stay aligned with this repository.

## Vendoring rules

1. Downstream repos may vendor schemas **only as generated mirrors** of `pcs-core/schemas/`.
2. Mirrors must be copied from pcs-core **without local edits**. Do not patch vendored files in place.
3. Record the pcs-core git tag or commit in release notes when refreshing mirrors.
4. Typical mirror paths:
   - `schemas/pcs/` (Scientific Memory, Provability Fabric)
   - `vendor/pcs-core/schemas/` (submodule layouts)

## Schema drift checks

Every downstream repo must expose:

```bash
just pcs-schema-diff
```

That target runs the pcs-core script against the repo’s vendored mirror:

```bash
scripts/pcs-schema-diff.sh path/to/vendored/schemas
```

In pcs-core itself, the reference check is:

```bash
just pcs-schema-diff schemas
```

**Schema drift is a release blocker.** CI must fail when the mirror differs from the pinned pcs-core revision.

## Conformance fixtures

Cross-repo validation must use the shared LabTrust flow fixtures under `examples/labtrust/`:

| File | Stage |
|------|--------|
| `science_claim_bundle.pending.valid.json` | LabTrust-Gym (pre-certification) |
| `trace_certificate.valid.json` | CertifyEdge |
| `science_claim_bundle.certified.valid.json` | LabTrust-Gym (post-certification) |
| `verification_result.valid.json` | Provability Fabric (verification) |
| `signed_science_claim_bundle.valid.json` | Provability Fabric (signed export) |

Negative fixtures under the same directory document known mismatches that must **fail** validation:

- `invalid_pf_legacy_singular_receipt.json` — uses `runtime_receipt` instead of `runtime_receipts`
- `invalid_signed_schema_version_artifact_name.json` — uses `schema_version: "SignedScienceClaimBundle.v0"` instead of `"v0"`

Downstream test suites should import or copy these paths and assert pass/fail accordingly.

## Validation and hash

- Use `pcs validate` (Python CLI) or language bindings from pcs-core for schema + semantic checks.
- Use `pcs hash` for canonical digests; do not reimplement canonicalization locally.
- Pin the same pcs-core version across all repos in a release train.

See also [protocol.md](protocol.md) and [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md).
