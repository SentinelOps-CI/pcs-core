# PCS protocol conformance suite

Downstream repositories can run subsets of these checks against a vendored or installed **pcs-core** pin.

| Suite | Path | Entry command |
|-------|------|----------------|
| Release chain | `conformance/release-chain/` | `pcs validate-release-chain <fixtures>/` |
| Handoff | `conformance/handoff/` | `pcs validate examples/handoff_manifest.valid.json` |
| Registry | `conformance/registry/` | `pcs registry validate examples/artifact_registry.valid.json` |
| Hash | `conformance/hash/` | `pcs shared-hash-vectors verify` |
| Migration | `conformance/migration/` | `pcs migrate --from v0 --to v0 <artifact>` |
| Status | `conformance/status/` | `pcs check-status-transition <old> <new>` |

Python integration tests live in `python/tests/test_protocol_conformance.py`.
