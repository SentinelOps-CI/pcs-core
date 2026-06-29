# Certificate Mode Compositionalextensioncertificate Unsafe Extension

Intentionally invalid PF-Core adversarial fixture for **`CompositionalExtensionCertificate`** certificate mode.

Unsafe trace append breaks compositional safety invariant.

- **Expected error:** `TenantIsolation`
- **Fail stage:** `validate_tenant_isolation`

Used by `check_pf_core_invalid_fixtures()` and `pcs conformance run --suite pf-core --release-grade`.
