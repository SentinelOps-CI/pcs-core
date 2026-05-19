"""Fixed PCS Lean obligation kinds and theorem names (no heavy imports)."""

from __future__ import annotations

OBLIGATION_KIND_THEOREM: dict[str, str] = {
    "CertificateMatchesRuntime": "admissible_release_has_matching_trace_hash",
    "VerificationAdmitsBundle": "admissible_release_has_verified_input_hash_equal_to_bundle_hash",
    "SignedBundleAdmissible": "admissible_release_has_signed_input_hash_equal_to_verified_input_hash",
    "ToolTraceHashMatchesCertificate": "tool_trace_hash_matches_certificate",
    "ComputationWitnessHashAlignment": "witness_result_hashes_admissible",
}

KNOWN_OBLIGATION_KINDS = frozenset(OBLIGATION_KIND_THEOREM.keys())
LEAN_THEOREM_CATALOG = frozenset(OBLIGATION_KIND_THEOREM.values())
