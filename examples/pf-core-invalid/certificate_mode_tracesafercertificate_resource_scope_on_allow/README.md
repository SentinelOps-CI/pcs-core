# Certificate Mode Tracesafercertificate Resource Scope On Allow

Intentionally invalid PF-Core adversarial fixture for **`TraceSafeRCertificate`** certificate mode.

Allow event resource path outside capability pattern scope.

- **Expected error:** `ResourceScopeViolation`
- **Fail stage:** `validate_pfcore_trace_hash_chain`

Used by `check_pf_core_invalid_fixtures()` and `pcs conformance run --suite pf-core --release-grade`.
