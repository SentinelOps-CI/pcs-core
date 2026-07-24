# Downstream schema sync

pcs-core is the canonical source for all PCS v0.1 JSON schemas, and LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory stay aligned with this repository when they refresh their mirrors at pinned revisions.

## Mirroring rules

Downstream repositories may mirror schemas only as generated copies of `pcs-core/schemas/`, and each mirrored file must be byte-for-byte equivalent to pcs-core at the pinned revision unless the file is explicitly documented as a legacy fixture that serves as a read-only negative example.

Maintainers refresh mirrored schema files from pcs-core and record the git tag or commit in release notes instead of editing mirrors locally.

Typical mirror paths include `schemas/pcs/` in Scientific Memory and Provability Fabric and `vendor/pcs-core/schemas/` in submodule layouts.

## Schema drift checks

Every downstream repository should provide a schema drift check, for example `just pcs-schema-diff`, that compares the vendored mirror to pcs-core.

```bash
scripts/pcs-schema-diff.sh path/to/vendored/schemas
```

The pcs-core reference check runs as follows.

```bash
just pcs-schema-diff schemas
```

Schema drift blocks release, and continuous integration should fail when the mirror differs from the pinned pcs-core revision.

## LabTrust conformance fixtures

Cross-repository schema tests use `examples/labtrust/`.

| File | Stage |
|------|--------|
| `science_claim_bundle.pending.valid.json` | LabTrust-Gym pending bundle |
| `trace_certificate.valid.json` | CertifyEdge |
| `science_claim_bundle.certified.valid.json` | LabTrust-Gym certified bundle |
| `verification_result.valid.json` | Provability Fabric |
| `signed_science_claim_bundle.valid.json` | Provability Fabric through Scientific Memory import |

Negative fixtures must fail validation as listed below.

| File | Failure reason |
|------|----------------|
| `invalid_signed_schema_version_artifact_name.json` | `schema_version` must remain `"v0"` instead of the artifact class name |
| `invalid_singular_runtime_receipt_bundle.json` | `runtime_receipts` array is required |
| `invalid_failed_verification_result.json` | failed checks conflict with import-ready top-level status |
| `invalid_missing_trace_certificate.json` | certified claim lacks `TraceCertificate` |

Python tests live in `python/tests/test_labtrust_conformance.py`, and fixture roles are explained in [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md).

## LabTrust release fixtures (canonical)

`examples/labtrust-release/` is the canonical PCS v0.1 LabTrust release chain for v0.1.0.

| Rule | Detail |
|------|--------|
| Source of truth | Sync this directory at the pinned pcs-core tag, or prove canonical-hash equivalence to `RELEASE_FIXTURE_MANIFEST.json` |
| Atomic refresh | Regenerate through the full clean-checkout chain and `just generate-labtrust-release-fixtures` |
| Pin values and checks | [labtrust-release-fixtures.md](labtrust-release-fixtures.md) |
| Verification | `pcs validate-release-chain examples/labtrust-release/` runs 30 checks on every push to `main` |

Schema conformance fixtures under `examples/labtrust/` remain separate from release evidence, and additional workflow release trees include `examples/tool-use-release/` and `examples/computation-release/`.

## Validation and hashing

`pcs validate` applies JSON Schema together with semantic checks, `pcs hash` computes the canonical digest documented in [hash-canonicalization.md](hash-canonicalization.md), release trains pin the same pcs-core version across repositories, `pcs registry audit` lists the semantic check catalog after registry upgrades, and `pcs conformance run --suite <name>` exercises protocol conformance described in [../conformance/README.md](../conformance/README.md).

```python
from pcs_core.conformance import build_conformance_report_data, run_conformance

exit_code, errors = run_conformance("hash")
report = build_conformance_report_data("hash")
```

Cross-language hash vectors are verified with `pcs shared-hash-vectors verify`.

## Verifier Assurance (PCS-VA) sync notes

Producers (OVK, LabTrust, optimization harnesses) should:

1. Pin pcs-core SHA/tag and vendor only the six VA schemas plus `verifier_assurance.defs.json` / `common.defs.json` as needed.
2. Emit `VerifierProfile.v1` / `VerificationResult.v1` (and campaign types as applicable); do not fork Invocation/Replay/Mutation schemas.
3. Gate CI with `pcs conformance run --suite verifier-assurance` and the producer dialect tree under `benchmarks/verifier_assurance_conformance/`.
4. Follow [verifier-assurance/migration.md](verifier-assurance/migration.md) and [verifier-assurance/non-claims.md](verifier-assurance/non-claims.md).

## Related documentation

- [protocol.md](protocol.md)
- [verifier-assurance/protocol.md](verifier-assurance/protocol.md)
- [release-protocol.md](release-protocol.md)
- [artifact-registry.md](artifact-registry.md)
- [semantic-check-policy.md](semantic-check-policy.md)
- [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md)
