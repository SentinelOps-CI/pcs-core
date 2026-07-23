# PF-Core gap audit

Summary of gaps between the PF-Core vision and the current `pcs-core` repository.

## Tier 1 — production trusted kernel (complete)

**Status:** Tier 1 production kernel: complete

| Item | Status | Notes |
|------|--------|-------|
| `semantics_layer` on `PFCoreContract.v0` | Done | Flat field map: `lean` / `runtime` / `out_of_scope`; validator defaults |
| `contract_semantics_checked` on certificates | Done | Derived from semantics layers + checks |
| Cross-language semantic parity | Done | Rust `pf_core.rs`, TS `pfCore.ts`, `conformance run --suite pf-core-cross-language`; includes `contract_semantics_checked` read/validate |
| Rust/TS direct-trace effect/capability parity | Done | `validate_direct_trace_action_semantics` / `validateDirectTraceActionSemantics`; error codes `UnknownEffect`, `UnknownCapability`, `CapabilityEffectMismatch` |
| Trace vs certificate claim classes | Done | Separate enums; traces reject `LeanKernelChecked` / `CertificateChecked` |
| Direct-trace effect catalog | Done | Closed `effect_kind` enum + semantic validators |
| `proof_term_hash` on certificates | Done | sha256 of generated `.lean` bytes before `lake env lean` |
| Full semantic validation in lean-check | Done | `validate_artifact` on emitted certificates |
| Generated-lean-proof conformance | Done | Subcheck in `conformance run --suite pf-core` |
| `pcs pcs-envelope check` | Done | Alias; `pcs lean-check` deprecated with notice |
| PCS envelope-only framing (choice B) | Done | No `LeanKernelChecked` on PCS path; docs + tests |
| CertifyEdge live/stub/mock classes | Done | `pf_core_certifyedge.py`; dev CI mock; release gate live/stub only |
| `scripts/run-pf-core-adapter-ci.sh` | Done | Pinned provability-fabric-core hash parity |
| Tier 1 tests | Done | `test_pf_core_tier1.py` |

## Tier 2 — documented deferrals (complete)

| Item | Status | Notes |
|------|--------|-------|
| Full global non-interference | Partial | `TraceCrossTenantSafe` link in `NonInterference.lean`; full global NI still open |
| Lean RoleMap / role encoding | Partial | `runtimeRoleMap` parity with Python; kernel still uses explicit capabilities |
| Full Lean role/policy/evidence contract encoding | Deferred | Runtime-only fields in semantics_layer |

## Tier 3 — operational (complete)

| Item | Status | Notes |
|------|--------|-------|
| Gap audit (this file) | Done | |
| `generated-proofs.md` | Done | Regeneration policy for `lean/PFCore/Generated/` |
| `CHANGELOG.md` PF-Core section | Done | |
| `windows-lean.md` | Done | elan / WSL guide |

## Protocol and schemas

| Gap | Status | Notes |
|-----|--------|-------|
| PF-Core artifact JSON schemas | Done | Stage 2 |
| `LeanCheckResult.v0` JSON schema | Done | Stage 4 |
| PFCoreCertificate proof artifacts | Done | Stage 4 |
| Replay certificate fields | Done | Stage 5 |
| ToolUseTrace optional `handoffs` | Done | Stage 7 |

## Lean kernel

| Gap | Status | Notes |
|-----|--------|-------|
| Release-envelope theorems | Present | `lean/PCS/Theorems.lean` |
| Agent safety predicates (`EventSafe`, `TraceSafe`) | Done | Stage 3 `lean/PFCore/` |
| Concrete Lean proof terms per trace obligation | Done | Stage 4 codegen + `lake env lean` |
| Handoff non-expansion (`HandoffSafe`) | Done | `lean/PFCore/Handoff.lean` + runtime |

## Validation and claims

| Gap | Status | Notes |
|-----|--------|-------|
| `pcs pf-core lean-check` CLI | Done | Stage 3–4 |
| `pcs pf-core replay-trace` | Done | Stage 5 |
| `pcs pf-core validate-contracts` | Done | Stage 7 |
| Contract satisfaction runtime checker | Done | `pf_core_contract.py` |
| Resource scope enforcement | Done | Stage 7 deciders + trace validation |
| Handoff preservation in trace compiler | Done | Stage 7 optional `handoffs` |
| PCS release-envelope path clarity | Done | `pcs pcs-envelope check`; lean-check deprecated |

## Phase H (research: state, cross-tenant NI, RoleMap parity)

| Item | Status | Notes |
|------|--------|-------|
| H1 — Rich operational state + handoff | Done | `Transition.lean`, `State.lean`; `stepState`, frames, strong handoff lemmas |
| H2 — `TenantIsolation` + `TraceCrossTenantSafe` | Partial | `traceSafe_implies_tenant_isolation`; covert channels / timing open |
| H3 — `runtimeRoleMap` Python parity | Done | `RoleMap.lean` + `test_pf_core_research.py` |
| H4 — Research catalog tests | Done | `test_pf_core_research.py`, `test_pf_core_research_grade.py`, catalog updates |
| H5 — Effect frames | Done | `EffectFrame.lean` + independent `PFCoreEffectFrame.v0` certificate binding (PR4); write exclusion under explicit footprint alignment |
| H6 — Contract refinement | Done | `ContractRefinement`, `contract_refinement_preserves_trace_safe` |
| H7 — Replay claim boundary | Done | `replay_preserves_claim_boundary` in `pf_core_replay.py` |

## Remaining research (deferred)

1. **Paired-execution / full global cross-tenant non-interference** — `TenantProjectionIsolation` proved for single recorded traces; covert channels, timing, scheduler adversaries, and `PairedExecutionNonInterference` remain open (`non-interference.md`, `runtime-semantics.md`). Bare “non-interference” claims must name the formal predicate.
2. **DenyClosedCertificate** — declared-footprint `EventSafeDenyClosed` proved; post-deny runtime effect closure not yet evidenced; mode scaffolded/disabled.
3. **Write footprint ↔ effect linkage** — `WriteFootprintRequiresWriteEffect` explicit; derived from `ActionAdmissible` + `KnownCapabilityEffect` for catalog capabilities.
4. **Resource-pattern scope in Lean** — Done for A11 parity: Lean separates `ActionAdmissible` vs `ActionAdmissibleWithResourcePattern`; Python/Rust/TS base deciders exclude pattern scope; refined `*SafeR` include it. Shared vector: TraceSafe=true, TraceSafeR=false when URI is outside pattern.
5. **Full provability-fabric-core live adapter orchestration** — hash parity covered natively via adapter CI script.
6. **Full agent runtime, MCP, NL policy, model safety** — out of scope.

## External audit remediation (2026-06)

| Blocker | Status | Notes |
|---------|--------|-------|
| Lean `file_write_capability_aligns_write_footprint` soundness | Done | `KnownCapability` / `KnownCapabilityEffect` on `ActionAdmissible` |
| Resource-pattern scope certificate boundary | Done | `contract_semantics_checked.runtime` + claim-boundary doc |
| Conformance `--release-grade` for pf-core | Done | Fail closed without lake/WSL; verify-proof-binding gate |
| `run-release-verify.sh` release path | Done | Runtime smoke vs full lean-check + verify-proof-binding |
| CI lean job elan PATH + verify-proof-binding | Done | `.github/workflows/ci.yml` |
| Cross-language invalid hash vectors | Done | trace/previous hash mismatch, cross-tenant leak |
| TypeScript CI npm install in cross-language tests | Done | pytest + conformance suites |

## Phase G (compositional trust + proof binding)

| Item | Status | Notes |
|------|--------|-------|
| G1 — Compositional Lean layer | Done | `Compositional.lean`: safe extension, handoff chain, contract seq invariants |
| G2 — Minimal RoleMap Lean | Done | `RoleMap.lean`: alignment → `HasCapability` |
| G3 — `verify-proof-binding` CLI | Done | `pcs pf-core verify-proof-binding` |
| G4 — Compositional tests | Done | `test_pf_core_compositional.py` |

## Phase F (research-grade extensions)

| Item | Status | Notes |
|------|--------|-------|
| F1 — Conservative tenant non-interference | Done | `NonInterference.lean`, `validate_tenant_isolation` |
| F2 — JSON contract discharge in Lean codegen | Done | `ContractDecide.lean`, `contract-semantics.md` |
| F3 — CertifyEdge hook + mock CI | Done | `pf_core_certifyedge.py` |
| Release checklist + theorem sheet | Done | `release-checklist.md` |

## Phase I — Trust-boundary release fixes (2026-06)

| Item | Status | Notes |
|------|--------|-------|
| I1 — `pfcore_kernel_hash` + full `lean_environment_hash` | Done | PF-Core `*.lean` bytes + toolchain + lake files |
| I2 — Event sequence order validator | Done | `validate_event_sequence_order`; wired to validate-trace / lean-check |
| I3 — Release bundle CLI | Done | `bundle-release`, `validate-bundle`, `verify-bundle`; closed projection/evidence manifests |
| I4 — Compositional `certificate_mode` | Done | Six modes; `--certificate-mode` on lean-check; codegen obligations |
| I5 — Resource pattern Lean subset | Done | `ResourceWithinCapabilityPattern` in `ResourcePattern.lean` |
| I6 — Release gates | Done | `pf-core-release-gate.yml`; adapter blocking on main |
| I7 — Single-source catalog | Done | `schemas/pf_core.catalog.json` + `gen_pf_core_catalog.py` + CI drift check |

### Remaining gaps (post Phase I)

- Full global cross-tenant non-interference (covert channels / timing / scheduler adversaries).
- Live CertifyEdge on all developer machines (release gate requires live CLI; see `docs/pf-core/certifyedge.md`; local mock via `scripts/pf-core-certifyedge-dry-run.ps1`, stub via `scripts/pf-core-certifyedge-stub-dry-run.ps1`).
- Lean `ActionAdmissible` does not include `ResourceWithinCapabilityPattern`; scope discharged via runtime + generated `actionResourcesWithinCapabilityPatternD` obligations.
- Rust/TS certificate validation records contract-semantics metadata but does **not** emit or imply `LeanKernelChecked` (Python lean-check only).
- PCS per-obligation Lean term generation beyond release-chain triple (see `docs/pf-core/pcs-envelope-lean-roadmap.md`; incremental: component `*_prop` theorems for all three release-chain obligations; tool-use/computation deferred).

### Incremental improvements (2026-06-28)

| Item | Status | Notes |
|------|--------|-------|
| `nonInterferenceD_sound` + decider links | Done | `Observational.lean`: `nonInterferenceD_sound`, `traceSafeD_implies_nonInterferenceD`; `NonInterference.lean`: `traceSafeD_implies_tenantIsolationD`, `traceSafeD_implies_traceCrossTenantSafeD` |
| Runtime `validate_cross_tenant_safety` | Done | `TraceCrossTenantSafe` mirror; CLI `--cross-tenant-safety`; Rust/TS parity |
| Resource-pattern codegen hooks | Done | `actionResourcesWithinCapabilityPatternD` per allow event |
| CertifyEdge env contract | Done | `PF_CORE_CERTIFYEDGE_*`; `docs/pf-core/certifyedge.md`; mock fixture at `examples/pf-core-valid/certifyedge_mock/` |
| Windows release-grade script | Done | `scripts/pf-core-release-grade-local.ps1` (native lake) |
| `contract_semantics_checked` Rust/TS parity | Done | `parse_contract_semantics_checked` / `validateContractSemanticsChecked`; wired into certificate semantic validation; cross-language tests |
| Resource scope certificate obligations | Done | `lean_proof_checked` requires `resource_pattern_scope` (runtime) + `resource_within_capability_pattern` (lean) in Python/Rust/TS |
| CertifyEdge release-gate dry-run | Done | `scripts/pf-core-certifyedge-dry-run.{ps1,sh}`; integrated into release-grade local scripts (`PF_CORE_CERTIFYEDGE_MODE=mock`) |
| Rust/TS `TOOL_NAME_MAP` + tool-use mode default parity | Done | `resolve_tool_mapping` / `resolveCertificateModeDefault`; bundle manifest uses `TraceSafeRCertificate` for tool-use traces |
| Release-grade local script (full matrix) | Done | `scripts/pf-core-release-grade-local.{ps1,sh}`: all pf_core pytest, catalog drift, audit-lean-no-sorry, PFCore+PCS lake, bundle kernel manifest, CertifyEdge mock+stub |
| PCS component prop theorems (Lean codegen) | Done | `pcs_lean_codegen.py`: `*_prop` for `CertificateMatchesRuntime`, `VerificationAdmitsBundle`, `SignedBundleAdmissible`; `PCS.lean` imports `ReleaseChainCheck`; `hash_beq_iff_eq` in `Hash.lean` |

### Incremental improvements (2026-06-28 session — deferral research push)

| Item | Status | Notes |
|------|--------|-------|
| `TraceSafeR` / `EventSafeR` kernel chain | Done | `ResourcePattern.lean`; refines `TraceSafe`; migration path without breaking base proofs |
| Compositional append NI/safety | Done | `Compositional.lean`, `Observational.lean`: `traceSafe_append`, `trace_append_preserves_non_interference`, `traceProjection_append` |
| Handoff + NI precondition lemmas | Done | `handoffSafe_traceSafe_non_interference`, `handoffSafe_excludes_cross_tenant_handoff` |
| `traceSafeRD` decider + codegen | Done | `lean_check.py`, optional `concrete_trace_safe_r*` in codegen |
| CertifyEdge `--require-live` + stub | Done | `pf_core_certifyedge.py`, `scripts/certifyedge-stub.py`, release-gate matrix |

### Remaining honest deferrals (post push)

- Full global cross-tenant non-interference (covert channels / timing / scheduler adversaries).
- Base kernel `TraceSafe` / `ActionAdmissible` unchanged; `TraceSafeR` is opt-in refinement (codegen emits when scope validates).
- Live CertifyEdge attestation vs format stub (stub validates CLI contract only).

### Incremental improvements (2026-06-28 session — deferral research)

| Item | Status | Notes |
|------|--------|-------|
| NI adversary-model roadmap | Done | `non-interference.md` extension table |
| Deny-event / handoff NI precondition lemmas | Done | `Observational.lean`, `NonInterference.lean`, `Handoff.lean` |
| Runtime `validate_observational_non_interference` | Done | CLI `--non-interference`; Rust/TS parity; decider obligations in lean-check |
| `ActionAdmissibleWithResourcePattern` bridge | Done | `ResourcePattern.lean`; codegen `concrete_action_resource_scope_*` |
| Release gate CertifyEdge mock+live matrix | Done | `pf-core-release-gate.yml`; `certifyedge.md` |

### Remaining honest deferrals (post session)

- Full global cross-tenant non-interference (covert channels / timing / scheduler adversaries).
- Kernel `TraceSafe` / `ActionAdmissible` still omit `ResourceWithinCapabilityPattern` (bridge predicate only).
- Live CertifyEdge on all developer hosts (release gate skips live gracefully when CLI absent).
- Rust/TS certificate validation records contract-semantics metadata but does **not** emit or imply `LeanKernelChecked` (Python lean-check only).

### Honest limitations (Phase F + Tier 2)

- Tenant theorems cover **allowed events in safe traces**, not global cross-tenant non-interference.
- Lean contract discharge maps capability, effect, tenant, decision, event_safe, trace_safe only; role/policy/evidence refs remain runtime-only (`semantics_layer`).
- CertifyEdge live CLI depends on external install; CI uses mock when absent.
- PKI is documented out of scope for v0.1 only.

## Production hardening (B1–B7, 2026-06-29)

| Item | Status | Notes |
|------|--------|-------|
| B1 — CertifyEdge live/stub/mock separation | Done | `AttestationClass`; release gate hardening; `certifyedge-ci.md` matrix |
| B2 — workflow_certificate_modes + release-grade mode policy | Done | Catalog map; Rust/TS parity; sibling heuristic skipped under `--release-grade` |
| B5 — certificate-mode resolution hash vectors | Done | `hash_vectors/pf_core/certificate_mode_resolution/vectors.json`; release-grade normative digests |
| B3 — TraceSafeR sole tool-use LeanKernelChecked path | Done | Release-grade lean-check/codegen/conformance; `claim-boundary.md` updated |
| B6 — ContractChecked missing contract file fixture | Done | `certificate_mode_contractcheckedcertificate_missing_contract_file/` |
| B7 — Documentation sync | Done | merge-readiness, gap audit, README, audit-claims |
| Phase 3 — PCS envelope lean-proof | Done | PCS generated-lean-proof conformance; multi-artifact witness codegen |

### Remaining honest deferrals (post B1–B7)

- Paired-execution / full global cross-tenant non-interference (v0.2+ research; see `non-interference.md`, `runtime-semantics.md`). Proved bound: `TenantProjectionIsolation`.
- Full JSON contract Lean discharge for role/policy/evidence fields.
- Write footprint ↔ effect linkage as derived kernel theorem.
- Live provability-fabric-core orchestration beyond adapter hash parity.
- Rust/TS do not emit `LeanKernelChecked` (Python lean-check authority).
- Base `TraceSafe` kernel unchanged; release-grade tool-use requires TraceSafeR chain.
- Restricted Lean JSON decoder for `PFCoreSemanticProjection.v0` (Phase 4 optional stretch).

## Phase 5 — Runtime semantics and research completion (2026-07)

| Item | Status | Notes |
|------|--------|-------|
| 5.1 Observed effects + frame lemmas | Done | `ObservedEffect.lean`; `TrustedInstrumentation` assumption; `accepted_transition_no_undeclared_sensitive_observation` |
| 5.2 Deny-path closedness | Done | `DenyClosed.lean`; `EventSafeDenyClosed` refines `EventSafe`; runtime `validate_event_safe_deny_closed` |
| 5.3 TenantProjectionIsolation naming | Done | Proved property renamed in docs; Lean `NonInterference` kept as compatibility alias |
| 5.3 Paired-execution NI scaffolding | Done (unproved) | `PairedExecution.lean` vocabulary + assumptions; **no** paired-execution NI claim |
| Runtime semantics doc | Done | `docs/pf-core/runtime-semantics.md` |

## Phase 6 — Production external attestation (2026-07)

| Item | Status | Notes |
|------|--------|-------|
| 6.1 CertifyEdge provision from pin | Done | `pins/certifyedge.json` status=`unpinned`; `verify-certifyedge-pin.py` + `provision-certifyedge.sh` fail closed in release |
| 6.2 Bundle-bound ExternalAttestation.v0 | Done | Schema + `pcs pf-core attest-bundle`; digests vs ed25519 modes explicit |
| 6.3 Unified release/preview gates | Done | `release.yml` + `pf-core-release-gate.yml` + `scripts/release-gate.sh`; preview absence notice |

## PR14 — Authenticated integrity + CertifyEdge pin (B6 + B7)

| Item | Status | Notes |
|------|--------|-------|
| ArtifactIntegrity.v1 Ed25519 ops | Done | `pcs_core/artifact_integrity.py` (PyNaCl); domain-separated `PCS:<type>:<ver>:<digest>` |
| TrustedKeyRegistry.v0 | Done | Schema + validity intervals + revocation; `PCS_TRUSTED_KEY_REGISTRY` |
| Signature timestamp policy | Done | future skew + max age + key validity window |
| Release-root signature verify | Done | `verify_release_root_signatures` for stable artifact types |
| ExternalAttestation ed25519_signed | Done | Real sign/verify when seed + registry configured; digest-bound remains default |
| CertifyEdge pin machinery | Done | `provision.env` (path/digest/version/pin/strategy/trust grade); workflows source it |
| Fail-closed unpinned release | Done | `pins/certifyedge.json` remains `status=unpinned` (no fake production digest) |
| Dev fixture | Done | `dev_fixture` + `scripts/certifyedge-dev-fixture.py` for preview/tests only |
| Bundle pin record | Done | `certifyedge_pin.json` copied into release bundles |
| Arbitrary checker classification | Done | `trust_grade=untrusted_development` when digest ≠ pin |

### Remaining honest deferrals (post PR14)

- Org production ed25519 signing keys / published `TrustedKeyRegistry.v0` allowlist (operators must provision; pcs-core does not ship private keys).
- Real CertifyEdge OCI/binary/source pin (`status=pinned` with immutable digest) — blocked on upstream publishable artifact.
- External `CertificateChecked` remains preview until a production CertifyEdge pin exists.
- SLSA / consumer provenance verification remains PR15.
## PR1 — Release execution + claim-surface policy (B0 + A0)

| Item | Status | Notes |
|------|--------|-------|
| A0 mode status table | Done | `schemas/pf_core.certificate_mode_status.json`; TraceSafeR=`release_candidate`; TraceSafe=`legacy`; Handoff/Contract/EffectFrame/FramePreserved=`disabled`; Compositional=`experimental`; external CertificateChecked=`preview` |
| Disabled modes fail closed | Done | Public `pcs pf-core lean-check` + `--release-grade` reject `allowed_issuance=false` |
| lean-check artifact paths | Done | Deterministic paths printed/returned for certificate, LeanCheckResult, proof, projection/manifest placeholders |
| Release workflow lean-check-result | Done | `release.yml` + `pf-core-release-gate.yml` pass `--result-out` into `bundle-release --lean-check-result` |
| Preview dispatch path | Done | lean-check → bundle-release → validate-bundle → absence/attest → upload |

### Remaining honest deferrals (post PR1)

- Specialized modes remain disabled until evidence-fidelity PRs complete enablement (handoff, contract, effect frame, transitions repaired; public enablement deferred).
- External CertificateChecked remains preview until CertifyEdge pin (PR 14).
- Semantic projection and theorem manifest artifacts are written during lean-check and required in LeanKernelChecked closed bundles (`verify-bundle`).

## PR2 — Handoff evidence repair (A1 + A2)

| Item | Status | Notes |
|------|--------|-------|
| A1 `PFCoreResolvedEvidence` | Done | Single resolve in lean-check; threaded into projection/codegen/certificate |
| Explicit `evidence_selection.handoff_ids` | Done | Sibling auto-scan rejected for `HandoffSafeCertificate` |
| Projected `delegated_capabilities` | Done | Required non-empty; catalog-validated; Lean binds projected ID sequence |
| Public status | Disabled | Issuable only with `--allow-non-public-modes` until enablement pass |

## PR3 — Contract evidence repair (A3)

| Item | Status | Notes |
|------|--------|-------|
| Projection `semantics_layer` | Done | Replaces `field_semantics`; materialized per-field records after defaults |
| Per-field records | Done | section, field, normalized_value, effective_layer + lean theorem / runtime check id / out-of-scope rationale |
| Explicit `evidence_selection.contract_ids` | Done | Required for `ContractCheckedCertificate`; no sibling auto-pick |
| Certificate binding | Done | selected_contract_ids, contract_source_file_digests, contract_evidence_digest, contract_theorem_names; projection IDs must match |
| Canonical fixture e2e | Done | `examples/pf-core-valid/contract_checked/` via public CLI + `--allow-non-public-modes` + semantic validation |
| Public status | Disabled | Kept disabled for public RC consistency; issuance works with `--allow-non-public-modes` |

### Remaining honest deferrals (post PR3)

- `ContractCheckedCertificate` / `HandoffSafeCertificate` remain disabled for public RC until an enablement pass.
- Effect-frame and frame-preserved modes remain disabled for public RC (redesign landed; enablement deferred).
- External CertificateChecked remains preview until CertifyEdge pin (PR 14).

## PR4 — Effect-frame redesign (A4)

| Item | Status | Notes |
|------|--------|-------|
| `PFCoreEffectFrame.v0` schema + artifact | Done | frame_id, allowed_effect_kinds, resource_constraints, workflow/contract scope, source_policy_ref, provenance, integrity digest; `frame_scope_policy=global` |
| Non-tautological codegen | Done | `actionEffectsInFrameD concreteAction concreteDeclaredFrame = true`; frame emitted from independent artifact (never `action.effects`) |
| v0 multi-event policy | Done | One global frame per trace (documented on schema + fixture README) |
| Certificate path + digest | Done | `effect_frame_id`, `effect_frame_path`, `effect_frame_digest` on `PFCoreCertificate.v0` |
| Resolved evidence wiring | Done | `evidence_selection.effect_frame_id` required for `EffectFrameCertificate` |
| Adversarial extra-effect fail | Done | Action with undeclared effect omitted from frame → resolution/codegen fail |
| Public status | Disabled | Kept disabled for public RC; issuance works with `--allow-non-public-modes` |

### Remaining honest deferrals (post PR4)

- `EffectFrameCertificate` / `ContractCheckedCertificate` / `HandoffSafeCertificate` remain disabled for public RC until an enablement pass.
- Frame-preserved mode remains disabled pending PR5 transition redesign.
- External CertificateChecked remains preview until CertifyEdge pin (PR 14).

## PR5 — Transition-certificate redesign (A5)

| Item | Status | Notes |
|------|--------|-------|
| Explicit `stepState` witnesses | Done | Allow: `stepState pre = some post`; deny: identity; no `applyEvent` fallback in codegen |
| FramePreserved obligations | Done | Valid initial; allow applications; deny identity; frameValid at each post-state; resource/active-principal/tenant/capability-frame update equalities |
| Resolved evidence wiring | Done | `initial_state` + `transition_states` + `transition_chain_digest` on certificate |
| Cross-tenant no-op reject | Done | Sequential cross-tenant allow fixture rejected (`stepState` none) |
| Public status | Disabled | Kept disabled for public RC; issuance works with `--allow-non-public-modes` |

### Remaining honest deferrals (post PR5)

- Specialized modes remain disabled for public RC until an enablement pass.
- External CertificateChecked remains preview until CertifyEdge pin (PR 14).
- Compositional redesign (A6) landed as experimental: `CompositionalSafeExtension` + codegen operational application; still not `release_candidate`.
- `DenyClosedCertificate` remains scaffolded/disabled (declared-footprint `EventSafeDenyClosed` only).
- `TrustedInstrumentation` is attested-execution (not mere `ObservationsAgree`); authenticity still assumption-discharged.
- Paired-execution NI remains unproved scaffolding (`PairedExecutionNonInterference`).

## PR6 — Theorem manifest and proof binding (A7 + A8)

| Item | Status | Notes |
|------|--------|-------|
| `PFCoreTheoremManifest.v0` | Done | Structured IR with normalized propositions; distinct from inventory hash |
| Extended `verify-proof-binding` | Done | Schema/integrity, digests, names, propositions, witness, projection replay, evidence digests |

## PR7 — Closed semantic-projection bundle (A9 + A10)

| Item | Status | Notes |
|------|--------|-------|
| Always write `PFCoreSemanticProjection.v0.json` | Done | Written during lean-check whenever codegen produced a projection |
| Closed release manifest fields | Done | `semantic_projection_*`, `theorem_manifest_*`, `evidence_manifest_*`, `lean_check_result_*` path+hash |
| `evidence/` + `PFCoreEvidenceManifest.v0` | Done | Selected contract/handoff/effect-frame/policy artifacts + per-file digests |
| `pcs pf-core verify-bundle` | Done | Manifest/digest checks, projection replay, theorem reconstruct, toolchain select, bundled-kernel compile, attestation, digest-bound result |
| `validate-bundle` vs `verify-bundle` | Done | validate=structural; stable releases require verify-bundle |

### Remaining honest deferrals (post PR7)

- Specialized modes remain disabled for public RC until an enablement pass.
- External CertificateChecked remains preview until CertifyEdge pin (PR 14).
- Mandatory PCS projection binding (PR9) remains ahead.

## PR8 — Base/refined cross-language decider parity (A11)

| Item | Status | Notes |
|------|--------|-------|
| Base `action_admissible_d` excludes resource pattern | Done | Python/Rust/TS mirrors Lean `ActionAdmissible` |
| Refined `action_admissible_with_resource_pattern_d` combines both | Done | Distinct event/trace deciders (`*Safe` vs `*SafeR`) |
| Shared differential vector | Done | `examples/pf-core-invalid/resource_scope_violation`: TraceSafe=true, TraceSafeR=false in Lean/Python/Rust/TS |

## PR15 — Real release provenance (B8)

| Item | Status | Notes |
|------|--------|-------|
| Replace provenance stub | Done | `actions/attest-build-provenance` + `actions/attest-sbom` (SHA-pinned) |
| `ReleaseProvenanceBinding.v0` | Done | Binds commit, workflow/builder, lockfiles, verifier image digest, wheels, SBOM, bundle root |
| Consumer verification job | Done | `release-provenance.yml` + `release.yml` download artifact → `scripts/verify-release-provenance.sh` (+ `gh attestation verify` when signed) |
| Fail-closed gated honesty | Done | `attestation.status=gated` + `PROVENANCE_ATTESTATION_GATED.json` when org/plan blocks signing; stable requires signed unless `PCS_PROVENANCE_ALLOW_GATED` |

### Remaining honest deferrals (post PR15)

- Signed attestations still require GitHub artifact-attestation availability (public repos OK on current plans; private needs GHEC). Until org enables them, set `PCS_PROVENANCE_ALLOW_GATED=true` only as a temporary bridge — do not claim SLSA-attested releases while gated.
- OCI cosign image signing remains a separate org-infra gap (see `docs/distribution.md` / `docs/security-governance.md`).

## Phase 7 — Verification quality (2026-07)

| Item | Status | Notes |
|------|--------|-------|
| Python ruff/pyright/pytest/hypothesis/coverage | Done | CI quality step; coverage fail-under on trust-critical modules |
| Mutation testing | Deferred | Documented in `docs/mutation-testing.md` |
| Rust fmt/clippy/test + proptest | Done | Property digest test; fuzz scaffold in `rust/FUZZING.md` |
| TypeScript lint/test + property loops | Done | DenyClosed / ObservedEffectsAgree parity; digest property loop |
| Lean no-sorry + lake build | Done (existing) | Release workflow builds PCS + PFCore |
| Cross-language deny/observed effects | Done | Python/Rust/TS |

## v0.2+ research backlog (deferred)

Track as separate milestones; no public claim upgrade without proofs + fixtures + CI subchecks:

| Item | Deliverable |
|------|-------------|
| Full global cross-tenant NI | Extend `non-interference.md` adversary model + prove paired-execution family |
| Full JSON contract Lean discharge | Extend `ContractDecide.lean` for policy/evidence refs |
| Write footprint ↔ effect linkage | Derived theorem from `ActionAdmissible` + catalog |
| Live provability-fabric-core orchestration | Beyond `scripts/run-pf-core-adapter-ci.sh` hash parity |
| Agent runtime / MCP / NL policy | Out of scope per `mission.md` |
