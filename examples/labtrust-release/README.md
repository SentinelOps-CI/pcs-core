# LabTrust v0.1 release fixtures

Generated **PCS v0.1 release evidence** for the LabTrust QC workflow. Files must come from one atomic cross-repo chain (LabTrust-Gym → CertifyEdge → Provability Fabric → Scientific Memory). Do not edit individual files by hand.

Schema-only conformance examples live in [`../labtrust/`](../labtrust/). They are not release evidence.

## Regenerate

1. From a sibling [LabTrust-Gym](https://github.com/fraware/LabTrust-Gym) checkout, run the clean chain:

   ```bash
   export PCS_DETERMINISTIC=0
   export CERTIFYEDGE_SOURCE_COMMIT="$(git -C ../CertifyEdge rev-parse HEAD)"
   export PF_SOURCE_COMMIT="$(git -C ../provability-fabric rev-parse HEAD)"
   bash examples/pcs_qc_release/scripts/run_pcs_v01_clean_chain.sh
   ```

2. Import into pcs-core (validates, then replaces this directory):

   ```bash
   export PCS_CHAIN_WORK=../LabTrust-Gym
   just generate-labtrust-release-fixtures
   ```

`RELEASE_FIXTURE_MANIFEST.json` records producer commits and SHA-256 digests for every file.

## Protocol artifacts

Digest-signed protocol layer (regenerate with `just materialize-labtrust-protocol`):

| File | Type |
|------|------|
| `release_manifest.v0.json` | `ReleaseManifest.v0` |
| `handoff_manifest.*.v0.json` | Stage handoffs |
| `handoff_to_pf.json` | Alias for bundle-to-verifier handoff |
| `release_chain_validation_result.v0.json` | 30-check attestation |
| `RELEASE_FIXTURE_MANIFEST.json` | Digest manifest used by `pcs validate-release-chain` |

Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/materialize-labtrust-protocol.ps1
```

## Formal checks

Optional Lean trust-kernel artifacts: `proof_obligation.v0.json`, `lean_check_result.v0.json`. See [docs/lean-trust-kernel.md](../../docs/lean-trust-kernel.md).

## Validate

```bash
pcs validate-release-chain examples/labtrust-release/
just validate-labtrust-release-fixtures
cd python && pytest -q tests/test_release_chain.py tests/test_release_fixtures.py
```

The validator runs **30 checks** documented in [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).

Negative fixtures: [../labtrust-release-invalid/](../labtrust-release-invalid/).

## Authority

Use this directory (at a pinned pcs-core tag) as **PCS v0.1 LabTrust release evidence** in downstream repos. Policy: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md), profile: [docs/labtrust-v0.1-profile.md](../../docs/labtrust-v0.1-profile.md).
