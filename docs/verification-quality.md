# Verification quality gates (Phase 7)

## Wired in CI

| Language | Gates |
|----------|-------|
| Python | `ruff check/format`, `pyright` (trust-critical modules), `pytest`, Hypothesis property tests, branch coverage fail-under on attestation/path/hash modules |
| Rust | `cargo fmt --check`, `clippy -D warnings`, `cargo test --locked`, `proptest` digest property |
| TypeScript | `npm ci`, `tsc --noEmit` (lint), `npm test`, digest property loop |
| Lean | `lake build PCS`, `lake build PFCore`, `pcs pf-core audit-lean-no-sorry`, generated proof compile via lean-check |
| Cross-language | shared hash vectors, deny-closed / observed-effects parity, certificate mode vectors |

## Deferred / optional

| Item | Status |
|------|--------|
| mutmut / cosmic-ray mutation testing | Deferred — see [mutation-testing.md](mutation-testing.md) |
| cargo-fuzz libfuzzer targets | Scaffolded — see [../rust/FUZZING.md](../rust/FUZZING.md) |
| fast-check npm dependency | Optional; TLS-restricted installs use native property loops |

## Local commands

```bash
# Python quality extras
cd python && pip install -c requirements.lock -e ".[dev,quality]"
ruff check pcs_core tests && ruff format --check pcs_core tests
pyright pcs_core/external_attestation.py pcs_core/safe_paths.py pcs_core/pf_core_certifyedge.py
pytest -q tests/test_property_based.py tests/test_external_attestation.py
coverage run -m pytest -q tests/test_external_attestation.py tests/test_safe_paths.py
coverage report --include='pcs_core/external_attestation.py,pcs_core/safe_paths.py' --fail-under=70

# Unified gate (preview by default)
PCS_RELEASE_MODE=preview bash scripts/release-gate.sh
```
