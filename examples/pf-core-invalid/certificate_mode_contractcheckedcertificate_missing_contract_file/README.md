# Certificate Mode Contractcheckedcertificate Missing Contract File

Intentionally invalid PF-Core adversarial fixture for **`ContractCheckedCertificate`** certificate mode.

Valid trace paired with a certificate that claims `ContractCheckedCertificate` discharge while referencing a non-existent contract JSON file (`contract-missing-v0`). Fails at certificate-mode obligation validation, not trace-level contract binding alone.

- **Expected error:** `ContractCheckedCertificate cannot claim lean_proof_checked`
- **Fail stage:** `validate_semantics`

Used by `check_pf_core_invalid_fixtures()` and `pcs conformance run --suite pf-core --release-grade`.
