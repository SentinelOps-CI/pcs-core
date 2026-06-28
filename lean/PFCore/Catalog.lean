/-!
# PF-Core generated capability catalog (do not edit by hand).
-/

namespace PFCore.Catalog

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

end PFCore.Catalog
