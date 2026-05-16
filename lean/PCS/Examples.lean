import PCS.Claim
import PCS.Status

namespace PCS.Examples

/-- Minimal LabTrust QC-release claim stub for v0.1 Lean build. -/
def sampleClaim : ClaimArtifactV0 :=
  { artifactId := "claim-qc-release-v0.1"
    claimText := "QC release simulation temporal claim (not clinical)."
    claimKind := "temporal_claim"
    status := ArtifactStatus.certificateChecked.toJsonString
    assumptionSetRef := "as-labtrust-qc-v0.1"
    sourceSpanRefs := ["span-qc-release-spec-1"]
    formalStatement := "G (release_ready -> F[0,24h] verified)"
    certificateRefs := ["cert-trace-qc-release-v0.1"]
    runtimeReceiptRefs := ["receipt-qc-release-run-001"]
    createdAt := "2026-05-16T12:05:00Z"
    producer := "labtrust-gym"
    producerVersion := "0.1.0"
    sourceRepo := "https://github.com/fraware/LabTrust-Gym"
    sourceCommit := "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    signatureOrDigest := "sha256:2222222222222222222222222222222222222222222222222222222222222222" }

#check sampleClaim

end PCS.Examples
