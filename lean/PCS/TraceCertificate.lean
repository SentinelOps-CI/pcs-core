namespace PCS

structure TraceCertificateV0 where
  certificateId : String
  schemaVersion : String := "v0"
  traceHash : String
  specHash : String
  propertyId : String
  checker : String
  checkerVersion : String
  status : String
  createdAt : String
  producer : String
  producerVersion : String
  sourceRepo : String
  sourceCommit : String
  signatureOrDigest : String
  deriving Repr

end PCS
