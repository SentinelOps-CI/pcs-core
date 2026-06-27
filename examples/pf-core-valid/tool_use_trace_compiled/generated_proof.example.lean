import PFCore.TraceCheck

/-!
# Example generated concrete trace proof (fixture)

This file mirrors output from `pcs pf-core lean-check` for
`examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json`.
Live runs write sibling artifacts under `lean/PFCore/Generated/`.
-/

namespace PFCore.Generated.Trace_716cbed45d37ebe4

def evt_001Principal : Principal :=
  {
    id := "agent-safety-conformance-001",
    tenant := "tenant-a",
    roles := ["agent"],
    capabilities := ["cap:file-read", "cap:email-send", "cap:handoff", "cap:mcp-invoke"]
  }

def evt_001Action : Action :=
  {
    id := "act-evt-001",
    toolName := "filesystem.read",
    capability := "cap:file-read",
    effects := [Effect.read],
    reads := [{
      uri := "/data/report.txt",
      tenant := "tenant-a",
      labels := []
    }],
    writes := []
  }

def evt_001 : Event :=
  {
    id := "evt-001",
    principal := evt_001Principal,
    action := evt_001Action,
    decision := Decision.allow
  }

def evt_002Principal : Principal :=
  {
    id := "agent-safety-conformance-001",
    tenant := "tenant-a",
    roles := ["agent"],
    capabilities := ["cap:file-read", "cap:email-send", "cap:handoff", "cap:mcp-invoke"]
  }

def evt_002Action : Action :=
  {
    id := "act-evt-002",
    toolName := "network.request",
    capability := "cap:network",
    effects := [Effect.network],
    reads := [{
      uri := "https://example.com",
      tenant := "tenant-a",
      labels := []
    }],
    writes := []
  }

def evt_002 : Event :=
  {
    id := "evt-002",
    principal := evt_002Principal,
    action := evt_002Action,
    decision := Decision.deny
  }

def trace_agent_safety_001 : Trace := Trace.cons (Trace.cons (Trace.empty) evt_001) evt_002

theorem concrete_trace_safe : traceSafeD trace_agent_safety_001 = true := by
  decide

end PFCore.Generated.Trace_716cbed45d37ebe4
