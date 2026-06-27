/-!
# PCS registry semantic obligations (trust-boundary catalog)
-/

namespace PCS

/-- Registry semantic check identifiers for the core release trust envelope. -/
structure TrustEnvelopeRegistry where
  certificateMatchesRuntime : String := "CertificateMatchesRuntime"
  verificationAdmitsBundle : String := "VerificationAdmitsBundle"
  signedBundleAdmissible : String := "SignedBundleAdmissible"
  deriving Repr

def defaultTrustEnvelopeRegistry : TrustEnvelopeRegistry := {}

/-- Obligation kinds exported to ProofObligation.v0 map to these registry check ids. -/
def obligationKindToRegistryRef (kind : String) : Option String :=
  match kind with
  | "CertificateMatchesRuntime" => some "TraceCertificate.v0.trace_hash_matches_runtime_receipt"
  | "VerificationAdmitsBundle" => some "VerificationResult.v0.verified_input_bundle_hash_matches_certified"
  | "SignedBundleAdmissible" => some "SignedScienceClaimBundle.v0.signed_input_bundle_hash_matches_certified"
  | _ => none

end PCS
