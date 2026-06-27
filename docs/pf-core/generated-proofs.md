# Generated PF-Core Lean proofs

Concrete trace proof files under `lean/PFCore/Generated/` are **generated artifacts**, not hand-maintained source.

## What gets generated

When `pcs pf-core lean-check --trace <PFCoreTrace.v0.json>` runs the full pipeline (default), it writes a module such as:

```
lean/PFCore/Generated/Trace_<digest-prefix>.lean
```

Each file contains:

- Concrete `Principal`, `Action`, `Event`, and `Trace` definitions for the input trace
- Optional `ContractPreSpec` / `PostSpec` / `Inv` defs when event `contract_refs` bind contracts
- `decide`-based theorems (`concrete_trace_safe`, per-event `eventSafeD`, contract discharge)

The certificate records `proof_term_ref` pointing at the generated module path and `proof_term_hash` as the sha256 digest of that file's bytes (computed before `lake env lean`).

## Trust binding chain

1. **Lean** proves properties of the generated model in `lean/PFCore/Generated/Trace_*.lean`.
2. **Python** validates JSON traces/certificates (`validate_artifact`) and generates the model from `PFCoreTrace.v0`.
3. **Certificate** binds assurance via matching `trace_hash`, `proof_term_hash`, and `lean_environment_hash` on `LeanKernelChecked` outputs.

## Regeneration

From a clean checkout with Lean 4 (`lake`) available:

```bash
cd lean
lake build PFCore
cd ../python
pcs pf-core lean-check --trace ../examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json
```

For contract-bound traces:

```bash
pcs pf-core validate-contracts \
  ../examples/pf-core-valid/contract_checked/trace.json \
  --contracts-dir ../examples/pf-core-valid/contract_checked
pcs pf-core lean-check --trace ../examples/pf-core-valid/contract_checked/trace.json
```

## Git policy

Generated modules may appear locally after lean-check but are not required in release tags unless a fixture explicitly pins an example (see `examples/pf-core-valid/tool_use_trace_compiled/generated_proof.example.lean`).

Do not edit generated files by hand; re-run lean-check after trace or contract changes.

## Semantics layer alignment

Lean codegen emits contract deciders only for fields marked `lean` in the source contract's `semantics_layer` (or canonical defaults). Runtime-only fields (`require_role`, policy/evidence refs) are validated by `pcs pf-core validate-contracts` and listed under `contract_semantics_checked.runtime` on certificates.

See [contract-semantics.md](contract-semantics.md).
