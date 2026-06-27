# PF-Core assumptions

PF-Core proofs and certificates are conditional on explicit assumptions. This document lists assumptions baked into the current implementation (Stages 1–7) and assumptions deferred to later research.

## Cryptographic assumptions

- SHA-256 collision resistance for canonical artifact hashes and event hash chains.
- `signature_or_digest` fields bind artifact bytes; **PKI signing, HSM integration, and X.509 certificate chains are out of scope for PF-Core v0.1** (documented assumption only).

## Producer assumptions

- Runtime producers (`AgentRuntime`, LabTrust-Gym, adapters) emit faithful observations unless contradicted by hash-chain validation.
- Adapters that compile PCS artifacts into PF-Core traces are **untrusted**; their output must pass schema and semantic validation.

## Lean bridge (Stages 3–4)

- Default `pcs pf-core lean-check` runs Python deciders aligned with `lean/PFCore/` predicates, then generates a concrete proof file under `lean/PFCore/Generated/` and checks it with `lake env lean`.
- `LeanKernelChecked` is emitted **only** when that concrete proof succeeds (`traceSafeD … = true` via `decide`). `--skip-build` or `--skip-lean-proof` yields `RuntimeChecked` only.
- `lake build PFCore` means the PF-Core library compiles; individual traces still require generated proof files for kernel claims.
- Theorem names in `PF_CORE_THEOREM_CATALOG` exist as Lean symbols (enforced by `pcs pf-core audit-lean-catalog`).
- PCS `pcs pcs-envelope check` (alias `pcs lean-check`) validates release-envelope consistency only; it must not be described as PF-Core kernel-verified trace safety.

## Role and capability alignment (permanent boundary)

- Lean `HasCapability` inspects `principal.capabilities` only; **roles are not expanded in the kernel**.
- The PF-Core runtime compiler expands known roles into explicit capability ids on compiled principals.
- Traces submitted to `pcs pf-core lean-check` must list those expanded capabilities explicitly; lean-check rejects principals where `capabilities` does not match role expansion.
- Runtime authorization may still consult roles during compilation; lean-check and Lean proofs rely on the explicit capability list only.
- This role-to-capability split is a **permanent trusted-boundary assumption** unless a future Lean RoleMap stage expands kernel capability resolution.

## Registry assumptions

- Registry semantic checks marked `allowed_to_skip: true` are not treated as proved.
- Deferred checks must surface as `AssumptionDeclared` or `OutOfScope` claim classes, never `LeanKernelChecked` or unjustified `ProofChecked`.
- PF-Core certificates with skipped deferrable checks require non-empty `assumption_refs` pointing at `AssumptionSet.v0` ids or documented paths under `docs/pf-core/`.

## Out of scope (not assumed by PF-Core)

- Model correctness or alignment.
- Clinical or production safety of real-world systems.
- Natural-language policy interpretation.
- Global non-interference across tenants before event-level trace safety is proved.

## Assumption artifacts

Domain assumptions must be recorded in `AssumptionSet.v0` (PCS) or referenced from PF-Core certificates. Simulation scope disclaimers from the LabTrust profile remain mandatory for QC-release demonstrations. Prefer citing `assumption_set_id` values (for example `as-labtrust-qc-v0.1`) over documentation paths alone when issuing `AssumptionDeclared` certificates.

## Contract and invariant simplification

See [contract-semantics.md](contract-semantics.md) for the mapping between `PFCoreContract.v0` JSON fields and runtime/Lean predicates.
