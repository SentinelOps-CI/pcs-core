# Changelog

## PF-Core v0.1.0-pf-core (2026-06-29)

Release tag for the PF-Core production kernel on `pcs-core` `main`. Bounded claim: machine-checkable trace certificates for catalog-driven, resource-pattern-scoped agentic tool-use traces. Release-grade tool-use `LeanKernelChecked` requires the TraceSafeR evidence chain.

**Release SHA:** tag `v0.1.0-pf-core` at `5ddb36e` (see GitHub Releases).

### Added

- CertifyEdge attestation classes (`live`, `stub`, `mock`) with release-gate hardening (`a31a347`).
- Catalog `workflow_certificate_modes` map with release-grade `resolve_certificate_mode` parity across Python, Rust, TypeScript (`1fadcfd`).
- Release-grade enforcement of TraceSafeR as sole tool-use `LeanKernelChecked` path (`748601d`).
- Adversarial fixture `certificate_mode_contractcheckedcertificate_missing_contract_file` (`e061495`).
- PCS envelope generated-lean-proof conformance and multi-artifact witness codegen (`0aaee97`).

### Changed

- Release gate rejects `mock://` attestation without explicit staging flag; stub requires `PF_CORE_CERTIFYEDGE_ALLOW_STUB=1`.
- `claim-boundary.md` documents TraceSafeR-as-release claim for tool-use kernel checks.

### Documented deferrals (v0.2+)

- Full global non-interference, full JSON contract Lean discharge, write-footprint theorem, live fabric orchestration — see `docs/pf-core/non-interference.md` and `current-gap-audit.md`.

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
