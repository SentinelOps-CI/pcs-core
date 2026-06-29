# Certificate Mode Framepreservedcertificate Invalid Frame Transition

Intentionally invalid PF-Core adversarial fixture for **`FramePreservedCertificate`** certificate mode.

Invalid effect-frame transition between allow events.

- **Expected error:** `TenantIsolation`
- **Fail stage:** `validate_tenant_isolation`

Used by `check_pf_core_invalid_fixtures()` and `pcs conformance run --suite pf-core --release-grade`.
