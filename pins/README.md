# Supply-chain pins

| File | Purpose |
|------|---------|
| `elan.json` | Elan installer URL + sha256 + default Lean toolchain |
| `github-actions.json` | Immutable commit SHAs for CI Actions |
| `certifyedge.json` | CertifyEdge provision strategy (`status`, `provision_strategy`, digests) |

CI installs elan only after checksum verification (`scripts/install-elan-verified.sh`).
Workflows reference Actions as `owner/name@<40-char-sha> # <tag>`.

## CertifyEdge pin contract

`pins/certifyedge.json` uses an honest pin strategy:

| `status` | Meaning |
|----------|---------|
| `unpinned` | No immutable digest yet — **fail closed in release mode** |
| `pinned` | One of `oci_digest` / `signed_binary` / `source_commit_build` is fully specified |

Scripts:

- `scripts/verify-certifyedge-pin.py --mode release|preview`
- `scripts/provision-certifyedge.sh` (honors `PCS_RELEASE_MODE`)

Do **not** invent placeholder digests that pretend to verify. Preview / technical
preview releases may proceed with an explicit
`ABSENCE_OF_EXTERNAL_ATTESTATION.json` notice; stable release mode may not.
