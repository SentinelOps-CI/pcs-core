# LabTrust v0.1 release fixtures

This directory contains **generated PCS v0.1 release artifacts** (release evidence only). Files must come from one atomic cross-repo chain run (LabTrust → CertifyEdge → Provability Fabric → Scientific Memory) and must not be updated file-by-file. **Placeholder commits are prohibited** for final release tags.

Schema conformance fixtures live in [`../labtrust/`](../labtrust/) and must not be used as release evidence.

## Regeneration

1. Run the clean-checkout chain from a sibling [LabTrust-Gym](https://github.com/fraware/LabTrust-Gym) checkout:

   ```bash
   export PCS_DETERMINISTIC=0
   export CERTIFYEDGE_SOURCE_COMMIT="$(git -C ../CertifyEdge rev-parse HEAD)"
   export PF_SOURCE_COMMIT="$(git -C ../provability-fabric rev-parse HEAD)"
   bash examples/pcs_qc_release/scripts/run_pcs_v01_clean_chain.sh
   ```

2. Import into pcs-core (builds `release-run/`, validates, then atomically replaces this directory):

   ```bash
   export PCS_CHAIN_WORK=../LabTrust-Gym
   just generate-labtrust-release-fixtures
   ```

`RELEASE_FIXTURE_MANIFEST.json` records five repository commits (derived from artifact provenance) and SHA-256 digests of every file.

Protocol artifacts (same pins as the legacy manifest, digest-signed):

- `release_manifest.v0.json` — `ReleaseManifest.v0` (superset of the legacy manifest)
- `handoff_manifest.*.v0.json` — stage handoffs (`runtime_to_certificate`, `certificate_to_bundle`, `bundle_to_verifier`, `signed_bundle_to_memory`)
- `handoff_to_pf.json` — PF `--handoff` alias for `handoff_manifest.bundle_to_verifier.v0.json` (`HandoffManifest.v0`; legacy `pf_handoff.json` is not used in release mode)
- `release_chain_validation_result.v0.json` — 30-check `ReleaseChainValidationResult.v0` attestation (pinned `checked_at` to legacy `generated_at`)

Regenerate protocol JSON:

```bash
just materialize-labtrust-protocol
```

Windows PowerShell (repo root, no `just` required):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/materialize-labtrust-protocol.ps1
```

## Formal checks (Lean trust kernel)

After materializing protocol artifacts, each release directory includes:

- `proof_obligation.v0.json` — extracted structural obligations
- `lean_check_result.v0.json` — catalog check outcome (`ProofChecked` when the envelope is coherent)

See [docs/lean-trust-kernel.md](../../docs/lean-trust-kernel.md).

```bash
pcs extract-proof-obligations --release examples/labtrust-release/ --out examples/labtrust-release/proof_obligation.v0.json
pcs lean-check --obligations examples/labtrust-release/proof_obligation.v0.json --out examples/labtrust-release/lean_check_result.v0.json
cd lean && lake build
```

## Validation

```bash
pcs validate-release-chain examples/labtrust-release/
just validate-labtrust-release-fixtures

# from repo root (requires pcs-core on PYTHONPATH; install once: pip install -e python/.[dev])
pytest python/tests/test_release_chain.py python/tests/test_release_fixtures.py

# recommended (matches CI):
cd python && pytest -q tests/test_release_chain.py tests/test_release_fixtures.py
# or: just test-release-chain
```

`validate-release-chain` enforces the 30 checks in [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).

Invalid mixed-run example: [`../labtrust-release-invalid/mixed_certificate_id/`](../labtrust-release-invalid/mixed_certificate_id/).

## Authority

Only this directory may be used as **PCS v0.1 release evidence**. Canonical pin values and downstream copy policy: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md). Profile: [docs/labtrust-v0.1-profile.md](../../docs/labtrust-v0.1-profile.md).
