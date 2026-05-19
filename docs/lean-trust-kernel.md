# PCS Lean trust kernel

pcs-core owns a **dependency-light** Lean package under `lean/` that models the PCS trust envelope (structural coherence only — no scientific-domain truth claims).

## Layout

| Path | Role |
|------|------|
| `lean/lakefile.lean` | Lake build (`lake build` in CI) |
| `lean/PCS/Basic.lean` | Core types (`Hash`, `ArtifactStatus`, …) |
| `lean/PCS/ReleaseChain.lean` | Predicates: `CertificateMatchesRuntime`, `VerificationAdmitsBundle`, `ReleaseChainAdmissible`, … |
| `lean/PCS/Theorems.lean` | First theorem family (admissible release implications and impossibility lemmas) |

## JSON bridge

| Artifact | Schema | Purpose |
|----------|--------|---------|
| `ProofObligation.v0` | `schemas/ProofObligation.v0.schema.json` | Machine-readable obligations extracted from a release directory |
| `LeanCheckResult.v0` | `schemas/LeanCheckResult.v0.schema.json` | Outcome of checking obligations against the fixed Lean catalog |

`ReleaseManifest.v0` may optionally reference `proof_obligation` and `lean_check_result` path refs. `ReleaseChainValidationResult.v0` may include `formal_checks` derived from a `lean_check_result.v0.json` on disk.

## CLI

From `python/` (or with `pcs` on `PATH`):

```bash
pcs extract-proof-obligations \
  --release examples/labtrust-release/release_manifest.v0.json \
  --out examples/labtrust-release/proof_obligation.v0.json

pcs lean-check \
  --obligations examples/labtrust-release/proof_obligation.v0.json \
  --out examples/labtrust-release/lean_check_result.v0.json
```

Supported workflow profiles for extraction:

- `labtrust.qc_release_v0.1`
- `agent_tool_use.safety_v0`
- `scientific_computation.reproducibility_v0`

`lean-check` evaluates obligations against a **fixed** Python mirror of the Lean predicates, then runs `lake build` unless `--skip-lean-build` is set (tests only).

## Regeneration

Windows (repo root):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/materialize-protocol.ps1
```

This refreshes tool-use, computation, and LabTrust protocol artifacts, including `proof_obligation.v0.json` and `lean_check_result.v0.json` per release directory.

## Bundle identity vs file digest

Manifest artifact `sha256` fields are **file digests**. PF `verified_input.bundle_hash` and handoff `certified_bundle_hash` use the **semantic bundle identity** hash when they differ. Release-chain and obligation extraction resolve identity via handoff invariants (`pcs_core.bundle_identity`).

## Conformance

```bash
pcs conformance run --suite lean-trust
```
