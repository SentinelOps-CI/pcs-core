# PF-Core gap audit

Summary of gaps between the PF-Core vision and the current `pcs-core` repository.

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
| PCS `lean-check` honest disclaimer | Done | Stage 7 release polish |

## Stage 6 (complete)

| Item | Status | Notes |
|------|--------|-------|
| LabTrust replay example | Done | `examples/pf-core-valid/labtrust_replay/` |
| LabTrust adapter | Done | `pf_core_labtrust_adapter.py` |
| Examples check + replay gate | Done | `replay_required` in manifest |
| Hash vector parity | Done | Native checker `pf_core_hash_vector_parity.py` |
| Bridge artifact spec | Done | `docs/pf-core/bridge-artifact.md` |

## Stage 7 (complete subset)

1. `python/pcs_core/pf_core_contract.py` — contract load + trace validation.
2. Handoff events compiled from optional `ToolUseTrace.handoffs` with `HandoffAuthorityExpansion` gate.
3. Resource scope checks in runtime, trace validation, and lean deciders.
4. Fixtures: `contract_checked/`, `contract_violation/`, `resource_scope_violation/`, `handoff_compile_expansion/`.
5. Tests in `python/tests/test_pf_core_stage7.py`.

## Release polish (Phases A–E)

| Item | Status | Notes |
|------|--------|-------|
| Phase A — documentation accuracy | Done | threat-model, assumptions, mission, gap audit |
| Phase B — CI pf-core lean-check | Done | lean job runs full lean-check on fixture |
| Phase C — TS/Rust PF-Core schemas | Done | explicit `artifact_type` detection |
| Phase D — invariant theorem + richer codegen | Done | `Contract.lean`, per-event proofs, contract-semantics doc |
| Phase E — bridge demo + AssumptionSet fixtures | Done | `assumption_declared/`, bridge script, tests |
| Phase 6 partial — registry deferral consistency | Done | ProofChecked requires assumption refs when checks deferred |
| Presentation bundle (`docs/pf-core/presentation/`) | Done | |
| Registry merged with main PCS entries + PF-Core entries | Done | |
| Cross-language parity tests | Done | `test_pf_core_cross_language.py` |

## Remaining research (deferred)

1. **Full provability-fabric-core live adapter CI** — hash parity covered natively; full adapter orchestration remains cross-repo.
2. **Full agent runtime, MCP, NL policy, model safety** — out of scope.

## Phase F (research-grade extensions)

| Item | Status | Notes |
|------|--------|-------|
| F1 — Conservative tenant non-interference | Done | `NonInterference.lean`, `validate_tenant_isolation`, `cross_tenant_leak/` |
| F2 — JSON contract discharge in Lean codegen | Done | `ContractDecide.lean`, generated contract proofs, `contract-semantics.md` |
| F3 — CertifyEdge hook + mock CI | Done | `pf_core_certifyedge.py`, `certifyedge-check` CLI |
| Release checklist + theorem sheet | Done | `release-checklist.md`, updated presentation bundle |

### Honest limitations (Phase F)

- Tenant theorems cover **allowed events in safe traces**, not global cross-tenant non-interference.
- Lean contract discharge maps capability, effect, tenant, decision, event_safe, trace_safe only; role/policy/evidence refs remain runtime-only.
- CertifyEdge live CLI depends on external install; CI uses `PCS_CERTIFYEDGE_MOCK=1`.
