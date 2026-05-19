/-!
# PCS trust-envelope theorems (first family)
-/

import PCS.ReleaseChain

namespace PCS

theorem admissible_release_has_matching_trace_hash
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash)
    (h : ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash) :
    cert.traceHash = receipt.traceHash := by
  exact h.left.left

theorem admissible_release_has_certificate_checked
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash)
    (h : ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash) :
    cert.status = ArtifactStatus.CertificateChecked := by
  exact certificateCheckedInAdmissibleRelease cert receipt verification bundleHash signedInputHash h

theorem admissible_release_has_proof_checked_verification
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash)
    (h : ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash) :
    verification.status = ArtifactStatus.ProofChecked := by
  exact verificationProofCheckedInAdmissibleRelease cert receipt verification bundleHash signedInputHash h

theorem admissible_release_has_verified_input_hash_equal_to_bundle_hash
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash)
    (h : ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash) :
    verification.verifiedInputBundleHash = bundleHash := by
  exact h.right.left.right

theorem admissible_release_has_signed_input_hash_equal_to_verified_input_hash
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash)
    (h : ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash) :
    signedInputHash = verification.verifiedInputBundleHash := by
  exact h.right.right

theorem rejected_certificate_cannot_produce_admissible_release
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash)
    (hCert : cert.status = ArtifactStatus.Rejected) :
    ¬ ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash := by
  intro h
  have hChecked := certificateCheckedInAdmissibleRelease cert receipt verification bundleHash signedInputHash h
  rw [hCert] at hChecked
  cases hChecked

theorem stale_certificate_cannot_produce_admissible_release
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash)
    (hCert : cert.status = ArtifactStatus.Stale) :
    ¬ ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash := by
  intro h
  have hChecked := certificateCheckedInAdmissibleRelease cert receipt verification bundleHash signedInputHash h
  rw [hCert] at hChecked
  cases hChecked

theorem failed_release_blocking_check_prevents_admissible_release
    (cert : Certificate)
    (receipt : RuntimeReceipt)
    (verification : VerificationResult)
    (bundleHash : Hash)
    (signedInputHash : Hash)
    (hFailed : verification.releaseBlockingChecksPassed = false) :
    ¬ ReleaseChainAdmissible cert receipt verification bundleHash signedInputHash := by
  intro h
  have hAdmits := h.right.left
  rw [hFailed] at hAdmits
  cases hAdmits

end PCS
