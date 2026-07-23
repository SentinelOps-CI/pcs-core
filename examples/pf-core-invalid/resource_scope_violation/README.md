# resource_scope_violation (A11 differential vector)

All base `ActionAdmissible` / `TraceSafe` conditions pass (`cap:file-read`,
matching effects, in-tenant principal), but the read URI `/etc/passwd` lies
outside the declared capability pattern `/data/*`.

| Decider | Expected |
|---------|----------|
| `TraceSafe` / `traceSafeD` | `true` |
| `TraceSafeR` / `traceSafeRD` | `false` |

Hash-chain / runtime validation still reports `ResourceScopeViolation`.

Shared across Lean (`PFCore.ResourcePattern` A11 examples), Python
(`lean_check.trace_safe_d` / `trace_safe_rd`), Rust, and TypeScript.
