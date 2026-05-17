# LabTrust v0.1 Profile

## Dependency contract (cross-repo)

| Step | Repo | Output |
|------|------|--------|
| 1 | **LabTrust-Gym** | Pending `ScienceClaimBundle.v0` (`certificates: []`) |
| 2 | **CertifyEdge** | `TraceCertificate.v0` |
| 3 | **LabTrust-Gym** | Certified `ScienceClaimBundle.v0` (certificate attached) |
| 4 | **Provability Fabric** | Verifies certified bundle; emits `VerificationResult.v0` |
| 5 | **Provability Fabric** | Signs and emits `SignedScienceClaimBundle.v0` |
| 6 | **Scientific Memory** | Imports `SignedScienceClaimBundle.v0` for durable display |

Downstream repos must depend on **pcs-core** for schemas, validation, and hash. Vendored schema mirrors are allowed only as read-only copies; see [downstream-schema-sync.md](downstream-schema-sync.md). All artifacts use `schema_version: "v0"` including `SignedScienceClaimBundle.v0`.

## Fixture types

| Directory | Purpose |
|-----------|---------|
| `examples/labtrust/` | **Schema conformance** fixtures — stable example values for `pcs validate`, CI, and bindings tests |
| `examples/labtrust-release/` | **Generated release** fixtures — end-to-end cross-repo pipeline outputs and `RELEASE_FIXTURE_MANIFEST.json` |

Only `examples/labtrust-release/` may be used as **PCS v0.1 release evidence**. Regenerate with `just generate-labtrust-release-fixtures` and verify with `just validate-labtrust-release-fixtures`.

## Release fixture authority

`examples/labtrust/` is the canonical **conformance** fixture set. Downstream repos may copy these fixtures for schema tests, but any local copy must be **byte-for-byte identical** to pcs-core at the pinned commit. Schema mirrors follow the same rule; see [downstream-schema-sync.md](downstream-schema-sync.md).

`examples/labtrust-release/` is the canonical **release** fixture set. The manifest records exact commits for pcs-core, LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory plus the SHA-256 digest of every release artifact file.

| Valid fixture | Producer stage |
|---------------|----------------|
| `science_claim_bundle.pending.valid.json` | LabTrust-Gym |
| `trace_certificate.valid.json` | CertifyEdge |
| `science_claim_bundle.certified.valid.json` | LabTrust-Gym |
| `verification_result.valid.json` | Provability Fabric |
| `signed_science_claim_bundle.valid.json` | Provability Fabric → Scientific Memory |

| Invalid fixture | Expected failure |
|-----------------|-------------------|
| `invalid_singular_runtime_receipt_bundle.json` | `runtime_receipt` instead of `runtime_receipts` |
| `invalid_signed_schema_version_artifact_name.json` | `schema_version` encodes artifact class |
| `invalid_failed_verification_result.json` | failed checks with import-ready status |
| `invalid_missing_trace_certificate.json` | certified bundle without certificates |

## Repos in scope

| Repo | Role |
|------|------|
| [pcs-core](https://github.com/SentinelOps-CI/pcs-core) | Canonical schemas, validation, hash |
| [LabTrust-Gym](https://github.com/fraware/LabTrust-Gym) | Simulation, receipts, bundle export |
| [CertifyEdge](https://github.com/fraware/CertifyEdge) | `TraceCertificate.v0` |
| [provability-fabric](https://github.com/SentinelOps-CI/provability-fabric) | Verify and sign |
| [scientific-memory](https://github.com/fraware/scientific-memory) | Import and render |

## PCS v0.1 clean-checkout chain (release gate)

PCS v0.1 is **release-ready** only when the full cross-repo chain succeeds. Run from a **LabTrust-Gym** checkout with sibling repos (`pcs-core`, `CertifyEdge`, `provability-fabric`, `scientific-memory`):

```powershell
$env:PCS_DETERMINISTIC = "1"
& examples\pcs_qc_release\scripts\run_pcs_v01_clean_chain.ps1
```

```bash
export PCS_DETERMINISTIC=1
bash examples/pcs_qc_release/scripts/run_pcs_v01_clean_chain.sh
```

Canonical manual steps and environment variables: [LabTrust-Gym `docs/pcs_v01_clean_chain.md`](https://github.com/fraware/LabTrust-Gym/blob/main/docs/pcs_v01_clean_chain.md).

### Manual chain (same commands as the release gate)

```bash
# LabTrust-Gym
PCS_DETERMINISTIC=1 labtrust run-demo qc-release
PCS_DETERMINISTIC=1 labtrust run-demo qc-release-invalid-missing-qc
PCS_DETERMINISTIC=1 labtrust run-demo qc-release-invalid-unauthorized

labtrust export-trace --run runs/qc-release --out trace.json
labtrust export-runtime-receipt --run runs/qc-release --out runtime_receipt.json
labtrust export-pcs --run runs/qc-release --out science_claim_bundle.pending.json
pcs validate science_claim_bundle.pending.json

# CertifyEdge
certifyedge emit-pcs-certificate \
  --spec templates/hospital_lab/qc_release.stl \
  --trace trace.json \
  --out trace_certificate.json
pcs validate trace_certificate.json
certifyedge verify-certificate trace_certificate.json --trace trace.json

# LabTrust-Gym
labtrust attach-certificate \
  --bundle science_claim_bundle.pending.json \
  --certificate trace_certificate.json \
  --out science_claim_bundle.certified.json
pcs validate science_claim_bundle.certified.json

# Provability Fabric
pf verify science-claim science_claim_bundle.certified.json \
  --out verification_result.json
pcs validate verification_result.json

pf sign science-claim science_claim_bundle.certified.json \
  --out signed_science_claim_bundle.json
pcs validate signed_science_claim_bundle.json
pf inspect science-claim signed_science_claim_bundle.json

# Scientific Memory (positional just args)
cd ../scientific-memory
just pcs-import-bundle ../LabTrust-Gym/signed_science_claim_bundle.json
just pcs-render-claim claim-pcs-qc-release-v0.1
```

## pcs-core validation highlights

- Unknown `status` values are rejected.
- `ScienceClaimBundle` requires `assumption_set` and non-empty `runtime_receipts`.
- Certified bundles (`CertificateChecked`, etc.) require at least one `TraceCertificate`.
- `TraceCertificate.status` must be in the certificate enum.
- Receipt and certificate `trace_hash` values must align.
- Zero `source_commit` is rejected unless `local_dev: true` on that artifact.

## Simulation disclaimer

All claims in this profile are about **simulation artifacts**, not clinical production systems.
