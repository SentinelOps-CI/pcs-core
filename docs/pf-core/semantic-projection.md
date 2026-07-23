# PF-Core semantic projection

Phase 4 binds JSON semantics to Lean terms through a **semantic projection**
artifact (`PFCoreSemanticProjection.v0`) rather than a full Lean JSON decoder.

## Design

1. Extract Lean-relevant fields from `PFCoreTrace.v0` (principals, actions,
   effects, resources, decisions, handoffs, lean-layer contract fields,
   certificate mode).
2. Hash the projection independently (`projection_hash` / certificate
   `semantic_projection_hash`).
3. Emit concrete Lean terms from the projection (Python codegen bridge).
4. Bind generated theorem inventory via `theorem_inventory_hash` /
   `theorem_manifest_hash`.

Envelope fields that are not Lean-relevant (source commit metadata, unused
extensions) must not change the projection hash.

## Lean JSON decoder status

A restricted PF-Core Lean JSON decoder is **deferred**. Until one exists,
Python projection + codegen remains the trusted bridge into Lean. Differential
tests compare Python / Rust / TypeScript decider outcomes and generated Lean
theorem inventories; Lean-decoded JSON results are out of scope for v0.

## Theorem availability vs execution

Certificates distinguish:

- `kernel_theorems_available` — theorems present in the PF-Core Lean kernel catalog
- `concrete_theorems_generated` — theorems emitted into the concrete proof module
- `concrete_theorems_compiled` — generated theorems that successfully compiled

Legacy `theorems_checked` remains for v0 compatibility readers and continues to
reflect fixed catalog unions (not live inventory honesty). Inventory honesty
still uses `theorem_inventory` / `theorem_inventory_hash`.
