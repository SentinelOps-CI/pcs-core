# Valid CompositionalExtensionCertificate fixture

Valid PF-Core trace exercising **`CompositionalExtensionCertificate`** certificate-mode
codegen obligations (A6).

Obligations: safe prefix + EventSafe extension + successful `stepState` application +
preserved `FrameValid` frames ⇒ `TraceSafe` extended trace (`CompositionalSafeExtension`).
Prefix-only `TraceSafe` chaining is the narrower `TracePrefixSafe` claim.

Status: `experimental` (not `release_candidate`).

Regenerate via `python/scripts/gen_certificate_mode_fixtures.py` when certificate-mode
obligations change.
