# Artifact Lifecycle (v0.1)

## Canonical status enum

All repositories use the same status strings.

`Draft`, `Extracted`, `HumanReviewed`, `Formalized`, `ProofPending`, `ProofChecked`, `CertificatePending`, `CertificateChecked`, `RuntimeObserved`, `RuntimeChecked`, `Rejected`, `EmpiricalOnly`, `Deprecated`, `Stale`

## Demo-critical statuses

| Status | Role |
|--------|------|
| `Draft` | Work in progress |
| `RuntimeObserved` | Run completed with receipt recorded |
| `CertificatePending` | Awaiting CertifyEdge |
| `CertificateChecked` | Certificate attached and valid |
| `Rejected` | Checker or verifier failed |
| `Stale` | Superseded evidence |

## Typical LabTrust v0.1 flow

LabTrust produces run output with receipt status `RuntimeObserved`, then exports `RuntimeReceipt.v0`, `trace.json`, and a pending `ScienceClaimBundle.v0` that may ship with an empty `certificates` array.

CertifyEdge emits `TraceCertificate.v0` with status `CertificateChecked` or `Rejected`, the bundle is updated toward `CertificateChecked`, and Provability Fabric emits `VerificationResult.v0` followed by signing.

Scientific Memory imports and renders with guarantee-type labels, and pcs-core publishes `ReleaseManifest.v0`, stage `HandoffManifest.v0` files, and `ReleaseChainValidationResult.v0` under `examples/labtrust-release/` as described in [labtrust-release-fixtures.md](labtrust-release-fixtures.md).

## Pending and certified bundles

Pending bundles allow `certificates: []` while the claim may remain `CertificatePending`, and certified bundles include at least one `TraceCertificate.v0` with semantic trace-hash alignment enforced by validation.

## Rejection paths

Checkers may return `Rejected` on `TraceCertificate.v0`, verifiers may record failed checks on `VerificationResult.v0`, and invalid schema or semantic mismatch stops validation before any artifact promotion.

## Registry enforcement

`pcs registry check-artifact` verifies JSON Schema validity, registry-allowed status, required release fields, and schema file presence as documented in [artifact-registry.md](artifact-registry.md) and [status-transition-policy.md](status-transition-policy.md).
