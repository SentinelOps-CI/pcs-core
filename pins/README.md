# Supply-chain pins

| File | Purpose |
|------|---------|
| `elan.json` | Elan installer URL + sha256 + default Lean toolchain |
| `python-base-image.json` | Verifier OCI base image index + amd64 digests |
| `github-actions.json` | Immutable commit SHAs for CI Actions (includes attest + download-artifact) |
| `certifyedge.json` | CertifyEdge provision strategy (`status`, `provision_strategy`, digests) |

CI installs elan only after checksum verification (`scripts/install-elan-verified.sh`).
Workflows reference Actions as `owner/name@<40-char-sha> # <tag>`.
The verifier Dockerfile must reference `python-base-image.json` digests (no floating tags).

Release provenance (`release-provenance.yml` / `release.yml`) uses
`actions/attest-build-provenance` and `actions/attest-sbom` (pinned in
`github-actions.json`). Consumer verification is
`scripts/verify-release-provenance.sh`. Until GitHub artifact attestations are
available for the repository plan, set `PCS_PROVENANCE_ALLOW_GATED=true` and
treat `attestation.status=gated` as non-claimable for SLSA marketing.

Unified fail-closed checker (CertifyEdge + TrustedKeyRegistry + provenance policy):
`pcs release check-gates` / `scripts/check-release-gates.py` — see
`docs/pf-core/operator-release-gates.md`.

## CertifyEdge pin contract

`pins/certifyedge.json` uses an honest pin strategy:

| `status` | Meaning |
|----------|---------|
| `unpinned` | No immutable digest yet — **fail closed in release mode** |
| `pinned` | One of `oci_digest` / `signed_binary` / `source_commit_build` is fully specified |

`dev_fixture` (`scripts/certifyedge-dev-fixture.py`) is **test/preview only**. It exercises
provision → `provision.env` → trust-grade classification without inventing a production digest.
Release mode rejects `dev_fixture`.

Scripts:

- `scripts/verify-certifyedge-pin.py --mode release|preview`
- `scripts/provision-certifyedge.sh` (honors `PCS_RELEASE_MODE`; writes `.tools/certifyedge/provision.env`)

### provision.env contract

Every successful provision writes a machine-readable env file:

| Variable | Meaning |
|----------|---------|
| `PCS_CERTIFYEDGE_EXECUTABLE` | Canonical executable path |
| `PCS_CERTIFYEDGE_BINARY_DIGEST` | SHA-256 of the provisioned bytes |
| `PCS_CERTIFYEDGE_VERSION` | Pin version string |
| `PCS_CERTIFYEDGE_PIN_IDENTITY` | Stable pin identity (`oci:…@sha256:…`, `binary:…`, …) |
| `PCS_CERTIFYEDGE_PROVISION_STRATEGY` | Strategy used |
| `PCS_CERTIFYEDGE_TRUST_GRADE` | `pinned` \| `untrusted_development` \| `unpinned` |
| `PF_CORE_CERTIFYEDGE_CLI` | Compatibility alias for the executable path |

Workflows **must source** this file and **must not** overwrite `PF_CORE_CERTIFYEDGE_CLI`
with an empty repository secret. Arbitrary PATH executables that do not match the pin
digest are classified `untrusted_development` even when the process exits 0.

Release bundles carry `certifyedge_pin.json` (pin snapshot) alongside `tool_versions.json`.

Do **not** invent placeholder digests that pretend to verify. Preview / technical
preview releases may proceed with an explicit
`ABSENCE_OF_EXTERNAL_ATTESTATION.json` notice; stable release mode may not.
