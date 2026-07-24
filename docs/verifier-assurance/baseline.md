# Verifier Assurance Protocol — baseline (PCS-VA-00)

Recorded before functional schema changes for the Verifier Assurance (`*.v1`) artifact family.

## Repository pin

| Field | Value |
|-------|-------|
| Branch | `main` (tracking `origin/main`) |
| HEAD SHA | `e068794683959c52a19594a6d271dd5e69f3c999` |
| Recorded | 2026-07-24 |

## Toolchain

| Tool | Version |
|------|---------|
| Python | 3.13.11 |
| rustc | 1.86.0 (05f9846f8 2025-03-31) |
| Node.js | v20.10.0 |
| elan | 4.2.3 (b6cec7e10 2026-06-08) |
| Lake / Lean | Lake 5.0.0-410fab7 / Lean 4.14.0 |
| just | 1.47.1 |

## Baseline commands

| Command | Result | Notes |
|---------|--------|-------|
| `pcs schema check` | **OK** (exit 0) | All registered JSON Schema Draft 2020-12 schemas |
| `pcs shared-hash-vectors verify` | **OK** (exit 0) | Shared cross-language digests |
| `pcs examples check` | **FAIL** (exit 1) | Pre-existing: `Unknown must_fail_at 'lean_check'` in `examples/pf-core-invalid/certificate_mode_effectframecertificate_extra_effect` — documented, not repaired in PCS-VA-00 (does not block VA schema work; VA fixtures use a dedicated harness) |
| `pcs conformance run --suite hash` | **OK** (exit 0) | Hash suite only (full `--suite all` is long-running) |

### Follow-up command results (PCS-VA-00 session)

```text
pcs schema check
→ OK all schemas (exit 0)

pcs shared-hash-vectors verify
→ OK shared hash vectors (exit 0)

pcs examples check
→ FAIL examples: Unknown must_fail_at 'lean_check' in
  .../examples/pf-core-invalid/certificate_mode_effectframecertificate_extra_effect
```

Full `just ci` / `pcs conformance run --suite all` remain release-gate commands; VA work adds suite `verifier-assurance` and does not require repairing the unrelated pf-core invalid-fixture dispatch until a dedicated fix PR.

## Inventory of reusable PCS building blocks

| Asset | Role for VA |
|-------|-------------|
| `common.defs.json` digests (`hex_digest`), `schema_version_v1`, `canonicalization_version`, Ed25519 envelope | Shared primitives |
| `ArtifactIntegrity.v1` | Nested `integrity` pattern on VA roots; forbid `signature_or_digest` on VA roots |
| PCS Canonical JSON v1 (`docs/hash-canonicalization.md`) | Release-grade hashing; **decimal strings** for rates/rewards (no JSON floats) |
| Guarantee labels (`docs/trust-model.md`) | Observational / empirical / human-reviewed / certificate-checked / formally-checked — do **not** upgrade `runtime_observed` to formal |
| Producer metadata patterns | OVK / LabTrust / pcs-core as applicable producers |
| Detection / registry / semantics / CLI / `@_record` conformance | Wiring checklist from `docs/protocol.md` |

## Versioning strategy (locked)

- New artifacts are **`*.v1` files only**; frozen `*.v0` schemas are immutable.
- Especially: do **not** mutate `VerificationResult.v0` (LabTrust/PF import checks). New decision record is `VerificationResult.v1`.
- Additive defs only in `verifier_assurance.defs.json` (and additive refs in `common.defs.json` only when truly shared).
- Migration: **coexistence** — no auto-upgrade of `VerificationResult.v0` → `VerificationResult.v1`.
