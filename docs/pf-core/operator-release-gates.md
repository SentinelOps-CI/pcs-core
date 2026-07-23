# Operator runbook: remaining org / infrastructure release gates

How to close the honest remaining gates that block **stable** (`PCS_RELEASE_MODE=release`)
pcs-core releases. Preview may remain digest-only / absence-notice / gated with disclosure.

Machine check (one command):

```bash
# Preview (current repo should pass)
pcs release check-gates --mode preview
# or: python3 scripts/check-release-gates.py --mode preview

# Stable (fails until org pins/keys/attestations exist — expected today)
PCS_RELEASE_MODE=release pcs release check-gates --mode release
```

After assemble, re-check with optional roots:

```bash
pcs release check-gates --mode release \
  --registry /path/to/TrustedKeyRegistry.v0.json \
  --release-root dist/release-bundle \
  --provenance-dir dist/provenance
```

Unified local gate (`scripts/release-gate.sh`) and CI (`release.yml`,
`pf-core-release-gate.yml`) invoke the same checker first.

Do **not** invent placeholder CertifyEdge digests or commit production private keys.

---

## 1. Ed25519 keys / TrustedKeyRegistry.v0 (ArtifactIntegrity.v1)

**Why:** Stable releases must authenticate manifests, certificates, Lean-check results,
external attestations, and publication bundles via domain-separated Ed25519 signatures
(`docs/trust-model.md`). pcs-core does not ship production private keys.

**Close the gate**

1. Generate an org release key pair offline (HSM or sealed secret store preferred).
   Local experiment only: `PCS_RELEASE_SIGNING_SEED_B64` + `PCS_RELEASE_SIGNING_KEY_ID`
   (never commit the seed).
2. Publish a `TrustedKeyRegistry.v0` allowlist of **public** keys (`key_id`,
   `valid_from` / `valid_until`, `purposes` including `release_signing`). Schema:
   `schemas/TrustedKeyRegistry.v0.schema.json`.
3. Distribute the registry to verifiers and CI as a pinned artifact or secret file.
   Set `PCS_TRUSTED_KEY_REGISTRY` to that path.
4. At release assemble time, sign with the matching private seed / key_id
   (`pcs_core.artifact_integrity.sign_artifact` / integrity sidecars).
5. Rotate by publishing a new `key_id` before retiring the old; revoke with `revoked_at`.

**Private keys live:** org secret store / HSM / GitHub Actions encrypted secrets —
not in this repository.

**Stable check:** `artifact_integrity_registry` fails if the registry is missing or has
no usable `release_signing` key. With `--release-root`, signatures are verified
(`allow_digest_only` only in preview).

---

## 2. Real CertifyEdge production pin

**Why:** `pins/certifyedge.json` is currently `status=unpinned`. Stable live
`CertificateChecked` attestation requires an immutable pin and `trust_grade=pinned`.

**Close the gate**

1. Obtain a real CertifyEdge artifact: OCI image digest, signed binary URL+sha256, or
   locked `source_commit` (40-char SHA) build. Do not invent digests.
2. Update `pins/certifyedge.json`:
   - `status=pinned`
   - `provision_strategy` one of `oci_digest` | `signed_binary` | `source_commit_build`
   - Fill the matching digest / URL / commit fields
3. Run `bash scripts/provision-certifyedge.sh` and **source**
   `.tools/certifyedge/provision.env` (do not overwrite `PF_CORE_CERTIFYEDGE_CLI` with
   an empty secret).
4. Confirm `PCS_CERTIFYEDGE_TRUST_GRADE=pinned`.
5. Flip external `CertificateChecked` from preview only after authenticated pin + live
   attest path is green (`schemas/pf_core.certificate_mode_status.json` /
   `docs/pf-core/certifyedge.md`).

`dev_fixture` remains test/preview only (`untrusted_development`).

**Stable check:** `certifyedge_pin` + `certifyedge_trust_grade` fail closed when unpinned
or trust grade is not `pinned`. Helpers:
`scripts/verify-certifyedge-pin.py`, `pins/README.md`.

---

## 3. Sigstore / GHEC signed provenance

**Why:** `ReleaseProvenanceBinding.v0` may finalize as `attestation.status=gated` when
GitHub artifact attestations are unavailable (private repo without GHEC, missing
OIDC/`attestations` permissions, org policy).

**Close the gate**

| Repo visibility | Action |
|-----------------|--------|
| Public | Ensure workflow `permissions: id-token: write` + `attestations: write`; run `release.yml` / `release-provenance.yml` |
| Private | Enable GitHub Enterprise Cloud artifact attestations (or equivalent org capability), then same permissions |

Consumer verify: `scripts/verify-release-provenance.sh` (+ `gh attestation verify` when
`status=signed`).

**Break-glass only:** `PCS_PROVENANCE_ALLOW_GATED=true` (repository variable / env).
Forbidden for claimed SLSA-attested stable releases. Clear the variable once signed
provenance is green on version tags.

**Stable check:** with `--provenance-dir`, `provenance_attestation` fails on `gated`
unless allow-gated is set. CI mirrors this after finalize in `release.yml`.

---

## 4. Cosign + GHCR verifier image publish

**Why:** `docker/verifier` + `distribution.yml` build/test the image; signed GHCR publish
is still org-gated.

**Close the gate**

1. Build/push by digest to GHCR (see `docs/distribution.md`).
2. Attach SBOM + provenance; `cosign sign` / `cosign attest` (keyless OIDC preferred).
3. Publish digest + signature references in the GitHub Release.
4. Optionally set `PCS_VERIFIER_OCI_DIGEST=sha256:…` so `check-gates
   --require-oci-publish` can machine-check presence (still confirm `cosign verify`
   out of band).

**Stable check:** `oci_cosign_publish` is advisory by default; pass
`--require-oci-publish` only when org policy mandates it.

---

## 5. Certificate mode status policy

Authoritative table: `schemas/pf_core.certificate_mode_status.json`.

| Mode / claim | Policy |
|--------------|--------|
| `TraceSafeRCertificate` | Sole tool-use **release_candidate** |
| Specialized modes (Handoff / Contract / EffectFrame / FramePreserved) | **disabled** (`allowed_issuance=false`) until a later enablement pass |
| `CompositionalExtensionCertificate` | **experimental** (not RC) |
| External `CertificateChecked` | **preview** until authenticated CertifyEdge pin |

Do not advertise disabled/experimental modes as stable public claims.
`certificate_mode_policy` in `check-gates` enforces TraceSafeR RC + closed disabled modes.

---

## Cross-links

- Release checklist: [release-checklist.md](release-checklist.md)
- Trust / signing: [../trust-model.md](../trust-model.md)
- Distribution / OCI: [../distribution.md](../distribution.md)
- Security / org admin: [../security-governance.md](../security-governance.md)
- CertifyEdge: [certifyedge.md](certifyedge.md), [certifyedge-ci.md](certifyedge-ci.md)
- Pins contract: [../../pins/README.md](../../pins/README.md)
- Gap audit (remaining honesty): [current-gap-audit.md](current-gap-audit.md)
