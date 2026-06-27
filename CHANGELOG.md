# Changelog

## PF-Core v0.1 production kernel (Tier 1–3)

### Added

- `semantics_layer` on `PFCoreContract.v0` declaring per-field discharge layers (`lean`, `runtime`, `out_of_scope`).
- `contract_semantics_checked` on `PFCoreCertificate.v0` derived from contract semantics layers and actual checks.
- Shared negative hash vectors under `python/tests/hash_vectors/pf_core/invalid/` with Rust and Python parity tests.
- `pcs pcs-envelope check` alias for PCS release-envelope consistency; `pcs lean-check` retained with deprecation notice.
- `scripts/run-pf-core-adapter-ci.sh` for provability-fabric-core hash-vector pin verification.
- Tier 1 tests in `python/tests/test_pf_core_tier1.py`.
- Documentation: `generated-proofs.md`, `windows-lean.md`, updated gap audit and contract semantics.

### Changed

- PCS release path framed as envelope-only (`ProofChecked`); not conflated with PF-Core `LeanKernelChecked`.
- Cross-language PF-Core parity extended to contract validation and denied-event preservation (Rust `pf_core.rs`, TypeScript `pfCore.ts`).
- CertifyEdge CI tries live CLI when present, falls back to `PCS_CERTIFYEDGE_MOCK=1`.

### Documented (deferred)

- Full global non-interference remains open research (`non-interference.md`).
- Role-to-capability split is a permanent trusted-boundary assumption (`assumptions.md`).
- PKI signing infrastructure out of scope for v0.1.
