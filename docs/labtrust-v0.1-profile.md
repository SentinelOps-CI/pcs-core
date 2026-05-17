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

Conformance fixtures: `examples/labtrust/`.

## Repos in scope

| Repo | Role |
|------|------|
| [pcs-core](https://github.com/SentinelOps-CI/pcs-core) | Canonical schemas, validation, hash |
| [LabTrust-Gym](https://github.com/fraware/LabTrust-Gym) | Simulation, receipts, bundle export |
| [CertifyEdge](https://github.com/fraware/CertifyEdge) | `TraceCertificate.v0` |
| [provability-fabric](https://github.com/SentinelOps-CI/provability-fabric) | Verify and sign |
| [scientific-memory](https://github.com/fraware/scientific-memory) | Import and render |

## Command sketch

```bash
# LabTrust-Gym
labtrust run-demo qc-release
labtrust export-trace --run runs/qc-release --out trace.json
labtrust export-runtime-receipt --run runs/qc-release --out runtime_receipt.json
labtrust export-pcs --run runs/qc-release --out science_claim_bundle.pending.json

# CertifyEdge
certifyedge emit-pcs-certificate \
  --spec templates/hospital_lab/qc_release.stl \
  --trace trace.json \
  --out trace_certificate.json

# LabTrust-Gym
labtrust attach-certificate \
  --bundle science_claim_bundle.pending.json \
  --certificate trace_certificate.json \
  --out science_claim_bundle.certified.json

# Provability Fabric
pf verify science-claim science_claim_bundle.certified.json
pf sign science-claim science_claim_bundle.certified.json \
  --out signed_science_claim_bundle.json

# Scientific Memory
just pcs-import-bundle BUNDLE=signed_science_claim_bundle.json
just pcs-render-claim CLAIM_ID=<claim_id>
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
