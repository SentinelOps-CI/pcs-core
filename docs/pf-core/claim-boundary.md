# PF-Core claim boundary

PF-Core provides machine-checkable trace certificates for a bounded, catalog-driven, resource-pattern-scoped subset of agentic tool-use traces. It does not claim global AI safety, full JSON contract discharge in the Lean kernel, or operational guarantees for deployed agents outside the stated catalog and claim class.

PF-Core separates **lifecycle status** (PCS `status` field) from **claim class** (what assurance was obtained). A certificate may carry `status: CertificateChecked` while `claim_class: RuntimeChecked` if only runtime predicates were evaluated.

## PFCoreTraceClaimClass vs PFCoreCertificateClaimClass

Traces and certificates use **different closed claim-class enums**. Traces record compiler/runtime assurance only; kernel and external-checker claims belong on certificates.

### PFCoreTrace.v0 (`PFCoreTraceClaimClass`)

| Claim class | Meaning |
|-------------|---------|
| `SchemaValidated` | JSON Schema and PF-Core semantic checks passed |
| `RuntimeChecked` | Runtime observation compiled and hash chain validated |
| `ReplayValidated` | Trace replayed and hashes reproduced |
| `AssumptionDeclared` | Claim rests on documented assumptions only |
| `OutOfScope` | Explicitly outside PF-Core trusted kernel |

**Forbidden on traces:** `LeanKernelChecked`, `CertificateChecked` (schema + semantic rejection).

### PFCoreCertificate.v0 (`PFCoreCertificateClaimClass`)

| Claim class | Meaning |
|-------------|---------|
| `SchemaValidated` | JSON Schema and PF-Core semantic checks passed |
| `RuntimeChecked` | Runtime/decider checks without Lean kernel proof |
| `CertificateChecked` | External checker attestation (e.g. CertifyEdge) |
| `LeanKernelChecked` | Concrete trace obligation proved in the Lean kernel (`traceSafeD tr = true`; tool-use release-grade requires `traceSafeRD` / `TraceSafeRCertificate`) |
| `ReplayValidated` | Deterministic replay certificate |
| `AssumptionDeclared` | Documented assumptions only |
| `OutOfScope` | Outside PF-Core trusted kernel |

`LeanKernelChecked` certificates require `proof_term_ref`, `proof_term_hash` (sha256 of generated `.lean` bytes), `lean_environment_hash`, `pfcore_kernel_hash`, `lean_proof_checked: true`, passed concrete obligations (mode-specific via `certificate_mode`), and contract grounding.

Do **not** use PCS `ProofChecked` alone as a PF-Core formal claim.

## Forbidden public phrases

The claim-boundary linter (`pcs pf-core audit-claims`) fails on these phrases in `docs/` and `examples/`:

| Forbidden phrase | Use instead |
|------------------|-------------|
| verified agent | trace-level safety preservation under stated assumptions |
| guarantees AI safety | contracted action safety under stated assumptions |
| model is safe | schema-validated runtime observation |
| agent is safe | Lean-kernel-checked trace theorem (only when `claim_class` is `LeanKernelChecked`) |
| fully verified runtime | runtime-checked trace with explicit claim class |
| formally verified platform | release-envelope consistency theorem family (for PCS Lean scope) |

## PCS release-envelope consistency (`pcs pcs-envelope check`)

PCS release-envelope checks validate `ProofObligation.v0` against the PCS theorem catalog in `lean/PCS/Theorems.lean`.

- Preferred command: `pcs pcs-envelope check --obligations … --out …`
- Legacy alias: `pcs lean-check` (prints deprecation notice; same behavior)
- Emits `LeanCheckResult.v0` with lifecycle status `ProofChecked` when obligations pass
- Does **not** prove PF-Core trace safety; does not emit `LeanKernelChecked`

Use `pcs pf-core lean-check --trace …` for PF-Core kernel assurance (`LeanKernelChecked` when concrete proof succeeds).

## PF-Core lean-check (`pcs pf-core lean-check`)

PF-Core `pcs pf-core lean-check` emits a registered `LeanCheckResult.v0` object alongside optional `PFCoreCertificate.v0` output.

- `status: LeanProofChecked` means Python deciders passed, the no-sorry audit passed, `lake build PFCore` succeeded, and a generated concrete proof file checked `traceSafeD tr = true` via the Lean kernel.
- `status: DecidersPassed` means deciders (and no-sorry audit) passed but Lean proof was skipped (`--skip-build` or `--skip-lean-proof`) or only runtime assurance was requested.
- `status: Rejected` means one or more checks failed.
- `claim_class` is mandatory: `LeanKernelChecked` only when `lean_proof_checked` is true; otherwise `RuntimeChecked` on success or `OutOfScope` on failure.
- `obligations[]` records concrete checks performed (deciders and, when run, `ConcreteTraceSafe`).
- `theorems_checked` lists catalog theorem symbols the check family is aligned with.
- `assumption_refs` points at documented assumptions (`docs/pf-core/assumptions.md`, `docs/pf-core/trusted-boundary.md`).
- `lean_build_status` records whether `lake build PFCore` ran and its outcome.
- `lean_environment_hash` (optional) fingerprints the pinned Lean toolchain and lake manifest.
- `disclaimer` states the assurance boundary for the selected pipeline mode.

Do **not** treat PCS lifecycle `ProofChecked` as a PF-Core formal claim. PF-Core lean-check does not emit unqualified `ProofChecked`.

### PFCoreCertificate.v0 output

Successful lean-check writes a certificate with matching `claim_class`, `assumption_refs`, `theorems_checked`, `obligations`, `lean_build_status`, `lean_proof_checked`, and `disclaimer`.

- `LeanKernelChecked` requires `proof_term_ref`, `proof_ref`, `proof_term_hash`, `lean_environment_hash`, `lean_proof_checked: true`, successful concrete Lean proof, and **contract grounding** (non-empty event `contract_refs` or `default_contract_ref: "trace-safe"` aligned with `PFCore.traceSafeContract`).
- `--skip-build` or `--skip-lean-proof` yields `RuntimeChecked` only (no `proof_term_ref`).
- `LeanKernelChecked` does **not** prove capability `resource_pattern` scope inside kernel `TraceSafe` / `ActionAdmissible`. Certificates list `resource_pattern_scope` under `contract_semantics_checked.runtime` and emit generated `concrete_action_resource_scope_*` obligations bridging to `ActionAdmissibleWithResourcePattern` when lean-check validates scope in Python.

#### Resource pattern: Lean vs runtime

| Layer | Field / check | Discharged in Lean kernel? |
|-------|----------------|----------------------------|
| Capability JSON | `capability.resource_pattern` | No — encoded in `ResourcePattern.lean` for parity only |
| Runtime compiler | `validate_resource_scope` in `pf_core_runtime.py` | N/A (pre-trace) |
| lean-check certificate | `contract_semantics_checked.runtime` includes `resource_pattern_scope` when Python scope check passes | No — runtime assurance recorded on certificate |
| Trace safety proof | `TraceSafe` / `EventSafe` / `ActionAdmissible` | No — tenant and capability rules only |
| Stronger trace safety (optional) | `TraceSafeR` / `EventSafeR` / `ActionAdmissibleR` | Yes — catalog glob subset via `globMatchCharsFuel` when codegen emits `concrete_trace_safe_r*` |
| lean-check generated proof | `concrete_action_resource_scope_*` → `ActionAdmissibleWithResourcePattern` | Bridge; `TraceSafeR` when scope validates for all allow events |

**Release-grade tool-use policy:** Under `pcs pf-core lean-check --release-grade`, tool-use traces must resolve to `TraceSafeRCertificate` (via `required_certificate_mode`, WorkflowProfile, or catalog `workflow_certificate_modes`). The sibling `tool_use_trace.json` heuristic is disabled. Successful `LeanKernelChecked` certificates require passed `concrete_trace_safe_r` and `concrete_trace_safe_r_prop` obligations; base `traceSafeD` alone is insufficient. Base `TraceSafeCertificate` remains for legacy / non–tool-use traces only. Refinement to base `TraceSafe` is documented via `traceSafeR_implies_traceSafe`.

### Public certificate-mode claim surface (A0)

Authoritative machine-readable table: [`schemas/pf_core.certificate_mode_status.json`](../../schemas/pf_core.certificate_mode_status.json).

| Mode / claim | Status | `allowed_issuance` | Notes |
|--------------|--------|--------------------|-------|
| `TraceSafeRCertificate` | `release_candidate` | true | Sole RC for tool-use `LeanKernelChecked` |
| `TraceSafeCertificate` | `legacy` | true | Non–tool-use / legacy only |
| `HandoffSafeCertificate` | `disabled` | false | Fail closed on public CLI and `--release-grade` |
| `ContractCheckedCertificate` | `disabled` | false | Evidence repair landed; public issuance still fail-closed until enablement pass (`--allow-non-public-modes`) |
| `EffectFrameCertificate` | `disabled` | false | Evidence redesign landed; public issuance still fail-closed (`--allow-non-public-modes`) |
| `FramePreservedCertificate` | `disabled` | false | Transition redesign landed; public issuance still fail-closed (`--allow-non-public-modes`) |
| `CompositionalExtensionCertificate` | `experimental` | true | A6 substantive predicate (`CompositionalSafeExtension`); not `--release-grade` |
| External `CertificateChecked` | `preview` | true | Until CertifyEdge pin |

Scaffolded (not in `CERTIFICATE_MODES` issuance surface; see status table `scaffolded_modes`):

| Mode / claim | Status | Notes |
|--------------|--------|-------|
| `TracePrefixSafeCertificate` | `experimental` alias | Prefix-only `TracePrefixSafe` / `TraceSafe` chaining — narrower than A6 |
| `DenyClosedCertificate` | `disabled` | Runtime evidence insufficient for post-deny effect closure; use `EventSafeDenyClosed` declared-footprint refinement only |

Issuance of disabled modes fails closed under the default public `pcs pf-core lean-check` CLI and under `--release-grade`. Codegen/fixture paths may still exercise disabled modes for conformance.

Non-interference claim boundary: prefer **`TenantProjectionIsolation`** (proved, single-trace observational). Do not use bare “non-interference” without naming the formal predicate; `PairedExecutionNonInterference` remains unproved scaffolding.

Reference: `lean/PFCore/ResourcePattern.lean`, Python `resource_matches_pattern`.

### Mapping guidance for PF-Core certificates

| Actual check performed | Required `claim_class` |
|------------------------|------------------------|
| Schema validation only | `SchemaValidated` |
| Runtime compiler + hash chain | `RuntimeChecked` |
| External checker | `CertificateChecked` |
| Lean theorem + concrete proof term | `LeanKernelChecked` |
| Documented assumption only | `AssumptionDeclared` |
| Deterministic trace replay | `ReplayValidated` |
| Outside kernel | `OutOfScope` |

## ReplayValidated (`pcs pf-core replay-trace`)

Stage 5 adds deterministic trace replay:

- Loads `PFCoreTrace.v0` (or recompiles from `ToolUseTrace.v0` / `PFCoreRuntimeObservation.v0` when `--source` is provided).
- Recomputes event hashes and `trace_hash` using the same rules as the runtime compiler.
- Emits `PFCoreCertificate.v0` or `LeanCheckResult.v0` with `claim_class: ReplayValidated` only when stored and recomputed hashes match.
- On mismatch, emits `claim_class: OutOfScope` or `Rejected` with detailed diff entries in `issues[]`.

Replay validates hash-chain integrity and compiler determinism. It does not imply `LeanKernelChecked`.

### `replay_preserves_claim_boundary` (Python operational theorem)

Replay certificates must not rank above the source trace `claim_class`. Implemented in `pcs_core.pf_core_replay.replay_preserves_claim_boundary` and enforced in `build_replay_certificate`.

**Does not imply:** Lean kernel proof, contract discharge, or upgrade to `LeanKernelChecked`.

## AssumptionDeclared enforcement

Registry semantic checks marked `allowed_to_skip: true` (for example `lean_kernel_proof` and `lean_library_build` on `PFCoreCertificate.v0`) are not treated as proved when skipped.

When such checks are deferred:

- Certificates must **not** claim `LeanKernelChecked` or PCS `ProofChecked`.
- Certificates must include non-empty `assumption_refs` pointing to `AssumptionSet.v0` ids (for example `as-labtrust-qc-v0.1`) or documented paths under `docs/pf-core/`.
- Prefer `claim_class: AssumptionDeclared` when assurance rests on documented assumptions only.

`enforce_assumption_declared()` in `registry_data.py` implements these rules; `validate.py` applies them to `PFCoreCertificate.v0`.

## CertificateChecked vs LeanKernelChecked

| Aspect | `CertificateChecked` | `LeanKernelChecked` |
|--------|---------------------|---------------------|
| Checker | External (e.g. CertifyEdge) | PF-Core Lean kernel (`traceSafeD`) |
| Proof artifact | External attestation ref | Generated `proof_term_ref` + `proof_term_hash` |
| Lean build | Not required | Required (`lake build PFCore`) |
| Typical source | PCS `TraceCertificate.v0` bridge | `pcs pf-core lean-check` full pipeline |

`pcs pf-core attach-certificate-check` wraps an external checker attestation into `PFCoreCertificate.v0` with `claim_class: CertificateChecked`. It does not run Lean proof or imply kernel-checked assurance.

See [bridge-artifact.md](bridge-artifact.md) for PCS `TraceCertificate.v0` mapping.

## Release-envelope vs agent safety

PCS Lean theorems in `lean/PCS/Theorems.lean` belong to the **release-envelope consistency theorem family**. PF-Core Lean theorems in `lean/PFCore/` model trace-level action safety. Documentation and certificates must not conflate the two families.
