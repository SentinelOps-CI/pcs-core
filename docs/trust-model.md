# Trust model (v0.1 / Phase 1 integrity)

PCS artifacts function as **evidence containers** that carry attestations and measurements, and each container requires an explicit guarantee label in user interfaces and exports because trust is layered by design.

## Guarantee types

| Type | Meaning | Typical source |
|------|---------|----------------|
| `runtime_observed` | A run occurred and hashes bind inputs, outputs, and trace | `RuntimeReceipt.v0` |
| `certificate_checked` | A checker attests the trace against a specification | `TraceCertificate.v0` |
| `formally_checked` | Proof or formal verification completed | Provability Fabric and the Lean kernel |
| `human_reviewed` | A person reviewed assumptions or claims | `AssumptionSet` and `ClaimArtifact` |
| `empirically_measured` | Measured data without formal proof | External datasets outside v0.1 scope |
| `unchecked_advisory` | Commentary without verification | Documentation and user interface notes |

Protocol rules appear in [protocol.md](protocol.md).

## Scope limits in v0.1

The LabTrust demonstration implements a **proof-carrying simulation workflow** aimed at integration testing and protocol education, and the workflow targets simulated hospital-lab scenarios with explicit domain assumptions instead of clinical validation, production medical certification, or claims about real hospital operations.

## Hash binding

`RuntimeReceipt.v0` binds `events_hash`, `policy_hash`, and `trace_hash`. `TraceCertificate.v0` references the same `trace_hash` and `spec_hash`. `ScienceClaimBundle.v0` validation enforces alignment between receipt and certificate trace hashes.

The canonical algorithm is **PCS Canonical JSON v1**, documented in [hash-canonicalization.md](hash-canonicalization.md).

## Digests vs signatures

### v0 compatibility (`signature_or_digest`)

v0 artifacts carry a single `signature_or_digest` field that is an integrity digest of
canonical JSON, not a cryptographic signature. v0 readers continue to accept this field.
New producers should prefer the v1 envelope when signing.

### v1 integrity envelope

```json
{
  "schema_version": "v1",
  "artifact_type": "…",
  "canonicalization_version": "v1",
  "artifact_digest": "sha256:…",
  "signature": {
    "algorithm": "ed25519",
    "key_id": "…",
    "signed_at": "…",
    "value": "…"
  }
}
```

Normative schema: `schemas/ArtifactIntegrity.v1.schema.json`.

`artifact_digest` hashes the artifact with `signature`, `artifact_digest`, and
`signature_or_digest` stripped. The signature covers the domain-separated message:

```text
PCS:<artifact_type>:<schema_version>:<artifact_digest>
```

### Trust roots, rotation, and revocation

| Concern | Policy |
|---------|--------|
| Trust root | Downstream verifiers pin an allowlist of ed25519 public keys by `key_id` (file or HSM). pcs-core does not ship production private keys. |
| Registry | `TrustedKeyRegistry.v0` (`schemas/TrustedKeyRegistry.v0.schema.json`); load via `PCS_TRUSTED_KEY_REGISTRY` or `pcs_core.artifact_integrity`. |
| Rotation | Publish a new `key_id` before retiring the old key. Artifacts must carry the `key_id` used at `signed_at`. Overlap windows are verifier policy. |
| Revocation | Set `revoked_at` on the key entry. Revoked keys must not verify signatures with `signed_at >= revoked_at`. |
| Validity | Keys carry `valid_from` / optional `valid_until`; `signed_at` must fall inside the interval. |
| Timestamp policy | Reject future `signed_at` (small skew allowed) and optionally reject signatures older than `max_age`. |
| Algorithm agility | v1 fixes `algorithm` to `ed25519`. Future algorithms require a new schema version. |

Operational Python API: `pcs_core.artifact_integrity` (`sign_artifact`, `verify_artifact_signature`,
`verify_release_root_signatures`). Stable releases authenticate PCS/PF-Core manifests,
PF-Core certificates, Lean-check results, external attestations, and publication bundles.
Digest-only integrity remains valid for development and explicitly labeled previews.
Operator steps to publish `TrustedKeyRegistry.v0` and close stable gates:
[pf-core/operator-release-gates.md](pf-core/operator-release-gates.md).

Signing seed for local/CI experiments (never commit production seeds):

- `PCS_RELEASE_SIGNING_SEED_B64` — 32-byte ed25519 seed (base64url)
- `PCS_RELEASE_SIGNING_KEY_ID` — matching `key_id` in the trusted registry

## Staleness

Status `Stale` marks artifacts superseded by newer commits, specifications, or traces, and consumers should treat stale certificates as historical evidence only.

Status policy appears in [artifact-lifecycle.md](artifact-lifecycle.md) and [status-transition-policy.md](status-transition-policy.md).
