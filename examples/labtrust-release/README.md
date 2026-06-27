# LabTrust v0.1 release fixtures

Generated PCS v0.1 release evidence for the LabTrust QC workflow comes from one atomic cross-repo chain spanning LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory, and maintainers refresh the directory through the materialize workflow instead of editing individual files by hand.

Schema-only conformance examples live in [`../labtrust/`](../labtrust/) and serve validation tests separate from release evidence.

## Regenerate

From a sibling [LabTrust-Gym](https://github.com/fraware/LabTrust-Gym) checkout, run the clean chain.

```bash
export PCS_DETERMINISTIC=0
export CERTIFYEDGE_SOURCE_COMMIT="$(git -C ../CertifyEdge rev-parse HEAD)"
export PF_SOURCE_COMMIT="$(git -C ../provability-fabric rev-parse HEAD)"
bash examples/pcs_qc_release/scripts/run_pcs_v01_clean_chain.sh
```

Import into pcs-core with validation before replacing this directory.

```bash
export PCS_CHAIN_WORK=../LabTrust-Gym
just generate-labtrust-release-fixtures
```

`RELEASE_FIXTURE_MANIFEST.json` records producer commits and SHA-256 digests for every file.

## Protocol artifacts

The digest-signed protocol layer regenerates through `just materialize-labtrust-protocol`.

| File | Type |
|------|------|
| `release_manifest.v0.json` | `ReleaseManifest.v0` |
| `handoff_manifest.*.v0.json` | Stage handoffs |
| `handoff_to_pf.json` | Alias for bundle-to-verifier handoff |
| `release_chain_validation_result.v0.json` | 30-check attestation |
| `RELEASE_FIXTURE_MANIFEST.json` | Digest manifest used by `pcs validate-release-chain` |

On Windows run the PowerShell materialize script.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/materialize-labtrust-protocol.ps1
```

## Formal checks

Optional Lean trust-kernel artifacts include `proof_obligation.v0.json` and `lean_check_result.v0.json` as described in [docs/lean-trust-kernel.md](../../docs/lean-trust-kernel.md).

## Validate

```bash
pcs validate-release-chain examples/labtrust-release/
just validate-labtrust-release-fixtures
cd python && pytest -q tests/test_release_chain.py tests/test_release_fixtures.py
```

The validator runs 30 checks documented in [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).

Negative fixtures live under [../labtrust-release-invalid/](../labtrust-release-invalid/).

## Authority

Downstream repositories use this directory at a pinned pcs-core tag as PCS v0.1 LabTrust release evidence, with policy in [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md) and profile notes in [docs/labtrust-v0.1-profile.md](../../docs/labtrust-v0.1-profile.md).
