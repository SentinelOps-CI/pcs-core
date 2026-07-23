import PFCore.Effect

/-!
# PF-Core generated catalog (do not edit by hand).

Emits capability ids, resource patterns, capability→effect mappings, effect
constructors, role map, tool map, and workflow certificate modes from
`catalog/pf_core.catalog.json`.
-/

namespace PFCore.Catalog
open PFCore

def knownCatalogCaps : List String :=
  [ "cap:file-read"
  , "cap:file-write"
  , "cap:network"
  , "cap:email-send"
  , "cap:handoff"
  , "cap:mcp-invoke"
  , "cap:lab-release"
  ]

def catalogResourcePatternStrings : List String :=
  [ "/data/*"
  , "/data/*"
  , "*"
  , "mailto:*"
  , "agent:*"
  , "mcp:*"
  , "lab:*"
  ]

def capabilityPatternString (cap : String) : String :=
  match cap with
  | "cap:file-read" => "/data/*"
  | "cap:file-write" => "/data/*"
  | "cap:network" => "*"
  | "cap:email-send" => "mailto:*"
  | "cap:handoff" => "agent:*"
  | "cap:mcp-invoke" => "mcp:*"
  | "cap:lab-release" => "lab:*"
  | _ => ""

/-- Catalog pairs mapping capability ids to canonical embedded effects. -/
def knownCapabilityEffectCatalog : List (String × Effect) :=
  [ ("cap:file-read", Effect.read)
  , ("cap:file-write", Effect.write)
  , ("cap:network", Effect.network)
  , ("cap:email-send", Effect.externalMessage)
  , ("cap:handoff", Effect.stateChange)
  , ("cap:mcp-invoke", Effect.codeExecution)
  , ("cap:lab-release", Effect.custom "lab.release")
  ]

/-- JSON effect_kind string → Lean ``Effect`` constructor. -/
def effectKindToEffect (kind : String) : Effect :=
  match kind with
  | "file.read" => Effect.read
  | "file.write" => Effect.write
  | "network.egress" => Effect.network
  | "email.send" => Effect.externalMessage
  | "handoff.delegate" => Effect.stateChange
  | "mcp.invoke" => Effect.codeExecution
  | "lab.release" => Effect.custom "lab.release"
  | other => Effect.custom other

/-- Custom effect labels admitted by ``EffectKnown``. -/
def knownCustomEffectLabels : List String :=
  [ "lab.release" ]

/-- Closed effect_kind vocabulary from the catalog JSON. -/
def knownEffectKindStrings : List String :=
  [ "file.read"
  , "file.write"
  , "network.egress"
  , "email.send"
  , "handoff.delegate"
  , "mcp.invoke"
  , "lab.release"
  ]

/-- Runtime role → capability entries (mirrors Python ``ROLE_CAPABILITY_MAP``). -/
def runtimeRoleMapEntries : List (String × List String) :=
  [
      ("file_reader", ["cap:file-read"])
      , ("file_admin", ["cap:file-read", "cap:file-write"])
      , ("network_user", ["cap:network"])
      , ("email_user", ["cap:email-send"])
      , ("handoff_delegate", ["cap:handoff"])
      , ("mcp_user", ["cap:mcp-invoke"])
      , ("lab_operator", ["cap:lab-release"])
      , ("agent", ["cap:file-read", "cap:email-send", "cap:handoff", "cap:mcp-invoke"])
  ]

/-- Tool name/category → capability id triples. -/
def toolMapEntries : List (String × String × String) :=
  [ ("filesystem.read", "filesystem", "cap:file-read")
  , ("filesystem.write", "filesystem", "cap:file-write")
  , ("network.request", "network", "cap:network")
  , ("email.send", "email", "cap:email-send")
  , ("handoff.delegate", "handoff", "cap:handoff")
  , ("mcp.invoke", "mcp", "cap:mcp-invoke")
  , ("lab.release", "lab", "cap:lab-release")
  ]

/-- Workflow id → required certificate mode. -/
def workflowCertificateModeEntries : List (String × String) :=
  [ ("agent_tool_use.safety_v0", "TraceSafeRCertificate")
  ]

end PFCore.Catalog
