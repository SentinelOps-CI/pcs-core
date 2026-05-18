/-!
# Workflow profiles (skeleton)
-/

namespace PCS

structure WorkflowProfileV0 where
  workflowId : String
  domain : String
  requiredAdmissionProfile : String
  runtimeArtifacts : List String
  certificateArtifacts : List String
  requiredRegistryEntries : List String
  deriving Repr

/-- Invariant: workflow-declared artifact types are a subset of the registry catalog. -/
def workflowEntriesRegistered (profile : WorkflowProfileV0) (registryTypes : List String) : Prop :=
  ∀ entry ∈ profile.requiredRegistryEntries, entry ∈ registryTypes

end PCS
