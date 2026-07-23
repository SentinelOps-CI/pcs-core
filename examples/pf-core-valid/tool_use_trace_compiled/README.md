# Tool-use trace compiled to PF-Core

Validates the **TraceSafeRCertificate** tool-use path: `ToolUseTrace.v0` compiles to `PFCoreTrace.v0` with explicit `required_certificate_mode: TraceSafeRCertificate`. Release-grade `pcs pf-core lean-check --release-grade` rejects tool-use traces that resolve to base `TraceSafeCertificate` only.

## Files

| File | Role |
|------|------|
| `tool_use_trace.json` | Source `ToolUseTrace.v0` (legacy sibling heuristic fallback for examples) |
| `pfcore_trace.json` | Compiled `PFCoreTrace.v0` with `required_certificate_mode` for lean-check and bundle-release |
| `manifest.json` | Example fixture metadata for `pcs examples check` |

## Lean kernel check

```bash
pcs pf-core lean-check --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json --release-grade
```

Expect `certificate_mode: TraceSafeRCertificate`, `claim_class: LeanKernelChecked`, and a substantive `concrete_trace_safe_r` obligation (not a trivial `:=` trivial aggregate).

## Release bundle

After lean-check writes a certificate (and LeanCheckResult via `--result-out`):

```bash
pcs pf-core bundle-release \
  --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json \
  --cert /tmp/pfcore-cert.json \
  --lean-check-result /tmp/lean-check.json \
  --out /tmp/pfcore-bundle
pcs pf-core validate-bundle /tmp/pfcore-bundle
pcs pf-core verify-bundle /tmp/pfcore-bundle
```

`validate-bundle` is the lower-cost structural check. Stable releases must run `verify-bundle` (projection replay, theorem reconstruction, Lean compile against the bundled kernel). The closed bundle includes semantic projection, theorem/evidence manifests, `lean-toolchain`, lake project files, `kernel_manifest.json`, and a self-contained `kernel/` tree.

See [docs/pf-core/claim-boundary.md](../../docs/pf-core/claim-boundary.md) for claim classes.
