# PF-Core Lean on Windows

PF-Core lean-check requires Lean 4 (`lake`) and optionally WSL when native tooling is unavailable.

## Recommended paths

| Approach | When to use |
|----------|-------------|
| WSL2 + elan | Primary recommendation on Windows; matches Linux CI |
| Native elan | When `lake` is on PATH and builds succeed locally |

## WSL2 setup

1. Install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) with an Ubuntu distribution.
2. Install elan inside WSL (checksum verified):

```bash
# From a pcs-core checkout
bash scripts/install-elan-verified.sh
# Or manually against pins/elan.json:
# curl -sSfL <url> -o elan.tar.gz && echo "<sha256>  elan.tar.gz" | sha256sum -c -
```

The CI pin lives in [`pins/elan.json`](../../pins/elan.json) (elan `4.2.3`, Lean toolchain still `leanprover/lean4:v4.14.0`).

3. Clone or access the pcs-core repo from the WSL filesystem (e.g. `/mnt/c/Users/.../pcs-core`) or a Linux home checkout for best I/O performance.
4. Build and lean-check:

```bash
cd lean
lake build PCS
lake build PFCore
cd ../python
pip install -e ".[dev]"
pcs pf-core lean-check --trace ../examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json
```

`pcs pf-core lean-check` detects missing native `lake` on Windows and retries via `wsl bash -lc 'cd … && lake …'` when WSL is installed.

## Native elan (optional)

Install elan for Windows from the [Lean releases](https://github.com/leanprover/elan/releases) page, pin `leanprover/lean4:v4.14.0`, and ensure `lake` is on PATH before running lean-check from PowerShell.

## PCS release-envelope checks

PCS `pcs pcs-envelope check` (and deprecated `pcs lean-check`) evaluate ProofObligation.v0 in Python; they do not require PF-Core `lake build PFCore` unless you also run PF-Core lean-check.

## Troubleshooting

- **`lake executable not found`**: Install elan or enable WSL fallback.
- **Path with spaces**: Prefer WSL paths or quote PowerShell arguments.
- **Generated proof stale**: Delete `lean/PFCore/Generated/Trace_*.lean` and re-run lean-check.

See also [generated-proofs.md](generated-proofs.md) and [trusted-boundary.md](trusted-boundary.md).
