import PCS.Bundle
import PCS.Certificate
import PCS.Hash

/-!
# PCS trust-envelope predicates
-/

namespace PCS

def CertificateMatchesRuntime (cert : Certificate) (receipt : RuntimeReceipt) : Prop :=
  cert.traceHash = receipt.traceHash ∧ cert.status = ArtifactStatus.CertificateChecked

def VerificationAdmitsBundle (verification : VerificationResult) (bundleHash : Hash) : Prop :=
  verification.status = ArtifactStatus.ProofChecked ∧
  verification.verifiedInputBundleHash = bundleHash ∧
  verification.releaseBlockingChecksPassed = true

def SignedBundleAdmissible (signedInputHash : Hash) (verifiedInputHash : Hash) : Prop :=
  signedInputHash = verifiedInputHash

def ReleaseChainAdmissible
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash) : Prop :=
  CertificateMatchesRuntime cert receipt ∧
  VerificationAdmitsBundle verification bundleHash ∧
  SignedBundleAdmissible signedInputHash verification.verifiedInputBundleHash

/-- Certificate status is CertificateChecked in any admissible release. -/
def certificateCheckedInAdmissibleRelease (cert : Certificate) (receipt : RuntimeReceipt)
    (verification : VerificationResult) (bundleHash signedInputHash : Hash)
    (h : ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash) :
    cert.status = ArtifactStatus.CertificateChecked :=
  h.left.right

/-- Verification status is ProofChecked in any admissible release. -/
def verificationProofCheckedInAdmissibleRelease (cert : Certificate) (receipt : RuntimeReceipt)
    (verification : VerificationResult) (bundleHash signedInputHash : Hash)
    (h : ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash) :
    verification.status = ArtifactStatus.ProofChecked :=
  h.right.left.left

end PCS
