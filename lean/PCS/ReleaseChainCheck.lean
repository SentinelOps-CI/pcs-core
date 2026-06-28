import PCS.ReleaseChain

/-!
# PCS release-chain decidable checks (concrete obligation discharge)

Boolean deciders mirror `ReleaseChain.lean` predicates for `#eval` and generated proofs.
-/

namespace PCS

def certificateMatchesRuntimeD (cert : Certificate) (receipt : RuntimeReceipt) : Bool :=
  decide (cert.traceHash == receipt.traceHash) &&
    match cert.status with
    | ArtifactStatus.CertificateChecked => true
    | _ => false

theorem certificateMatchesRuntimeD_sound (cert : Certificate) (receipt : RuntimeReceipt) :
    certificateMatchesRuntimeD cert receipt = true ↔
      CertificateMatchesRuntime cert receipt := by
  cases cert with
  | mk _ traceHash status =>
    cases receipt with
    | mk receiptHash _ =>
      cases status <;>
        simp [certificateMatchesRuntimeD, CertificateMatchesRuntime, decide_eq_true_iff, hash_beq_iff_eq]

def verificationAdmitsBundleD
    (verification : VerificationResult) (bundleHash : Hash) : Bool :=
  match verification.status with
  | ArtifactStatus.ProofChecked =>
    decide (verification.verifiedInputBundleHash == bundleHash) &&
      verification.releaseBlockingChecksPassed
  | _ => false

theorem verificationAdmitsBundleD_sound
    (verification : VerificationResult) (bundleHash : Hash) :
    verificationAdmitsBundleD verification bundleHash = true ↔
      VerificationAdmitsBundle verification bundleHash := by
  cases verification with
  | mk status verifiedHash blocking =>
    cases status <;>
      simp [verificationAdmitsBundleD, VerificationAdmitsBundle, decide_eq_true_iff, hash_beq_iff_eq]

def signedBundleAdmissibleD (signedInputHash : Hash) (verifiedInputHash : Hash) : Bool :=
  decide (signedInputHash == verifiedInputHash)

theorem signedBundleAdmissibleD_sound (signedInputHash : Hash) (verifiedInputHash : Hash) :
    signedBundleAdmissibleD signedInputHash verifiedInputHash = true ↔
      SignedBundleAdmissible signedInputHash verifiedInputHash := by
  simp [signedBundleAdmissibleD, SignedBundleAdmissible, decide_eq_true_iff, hash_beq_iff_eq]

def releaseChainAdmissibleD
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash) : Bool :=
  certificateMatchesRuntimeD cert receipt &&
    verificationAdmitsBundleD verification bundleHash &&
    signedBundleAdmissibleD signedInputHash verification.verifiedInputBundleHash

theorem releaseChainAdmissibleD_sound
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash) :
    releaseChainAdmissibleD cert receipt verification bundleHash signedInputHash = true ↔
      ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash := by
  simp [releaseChainAdmissibleD, ReleaseChainAdmissible,
    certificateMatchesRuntimeD_sound, verificationAdmitsBundleD_sound, signedBundleAdmissibleD_sound,
    and_assoc, and_left_comm, and_comm]

end PCS
