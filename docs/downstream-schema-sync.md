# Downstream schema sync

pcs-core is the canonical source for all PCS v0.1 JSON schemas. LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory must stay aligned with this repository.

## Mirroring rules

1. Downstream repos may mirror schemas **only as generated copies** of `pcs-core/schemas/`.
2. Mirrored schemas must be **byte-for-byte equivalent** to pcs-core at the pinned revision, unless a file is explicitly documented as a **legacy fixture** (read-only negative example, never used for publish or import).
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

Schema drift **blocks release**. CI must fail when the mirror differs from the pinned pcs-core revision.

## LabTrust conformance fixtures

Cross-repo schema tests use `examples/labtrust/`:

| File | Stage |
|------|--------|
| `science_claim_bundle.pending.valid.json` | LabTrust-Gym (pending bundle) |
| `trace_certificate.valid.json` | CertifyEdge |
| `science_claim_bundle.certified.valid.json` | LabTrust-Gym (certified bundle) |
| `verification_result.valid.json` | Provability Fabric |
| `signed_science_claim_bundle.valid.json` | Provability Fabric → Scientific Memory import |

Negative fixtures (must fail validation):

| File | Failure reason |
|------|----------------|
| `invalid_signed_schema_version_artifact_name.json` | `schema_version` must be `"v0"`, not the artifact class name |
| `invalid_singular_runtime_receipt_bundle.json` | `runtime_receipts` array required |
| `invalid_failed_verification_result.json` | failed checks with import-ready top-level status |
| `invalid_missing_trace_certificate.json` | certified claim without `TraceCertificate` |

Python tests: `python/tests/test_labtrust_conformance.py`.

Fixture roles: [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md).

## LabTrust release fixtures (canonical)

**Authority:** `examples/labtrust-release/` is the canonical PCS v0.1 LabTrust release chain for v0.1.0.

| Rule | Detail |
|------|--------|
| Source of truth | Sync this directory at the pinned pcs-core tag, or prove canonical-hash equivalence to `RELEASE_FIXTURE_MANIFEST.json` |
| Atomic refresh | Regenerate only via the full clean-checkout chain and `just generate-labtrust-release-fixtures` |
| Pin values and checks | [labtrust-release-fixtures.md](labtrust-release-fixtures.md) |
| Verification | `pcs validate-release-chain examples/labtrust-release/` (30 checks; CI on `main`) |

Schema conformance fixtures under `examples/labtrust/` are separate from release evidence.

Other workflow release trees: `examples/tool-use-release/`, `examples/computation-release/`.

## Validation and hashing

- `pcs validate` — JSON Schema plus semantic checks.
- `pcs hash` — canonical digest; do not reimplement locally ([hash-canonicalization.md](hash-canonicalization.md)).
- Pin the same pcs-core version across all repos in a release train.
- `pcs registry audit` — semantic check catalog after registry upgrades.
- `pcs conformance run --suite <name>` — protocol conformance ([../conformance/README.md](../conformance/README.md)).

```python
from pcs_core.conformance import build_conformance_report_data, run_conformance

exit_code, errors = run_conformance("hash")
report = build_conformance_report_data("hash")
```

Cross-language hash vectors: `pcs shared-hash-vectors verify`.

## Related documentation

- [protocol.md](protocol.md)
- [release-protocol.md](release-protocol.md)
- [artifact-registry.md](artifact-registry.md)
- [semantic-check-policy.md](semantic-check-policy.md)
- [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md)
