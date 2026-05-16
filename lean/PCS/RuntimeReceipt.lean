namespace PCS

structure RuntimeReceiptV0 where
  receiptId : String
  schemaVersion : String := "v0"
  runId : String
  startedAt : String
  endedAt : String
  status : String
  eventsHash : String
  policyHash : String
  traceHash : String
  producer : String
  producerVersion : String
  sourceRepo : String
  sourceCommit : String
  signatureOrDigest : String
  deriving Repr

end PCS
