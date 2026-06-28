"""Generated PF-Core catalog (do not edit by hand)."""

from __future__ import annotations

EFFECT_KINDS = frozenset(
    [
        "file.read",
        "file.write",
        "network.egress",
        "email.send",
        "handoff.delegate",
        "mcp.invoke",
        "lab.release",
    ]
)

CAPABILITY_CATALOG: dict[str, dict[str, str]] = {
    "cap:file-read": {
        "capability_id": "cap:file-read",
        "effect_kind": "file.read",
        "resource_pattern": "/data/*",
    },
    "cap:file-write": {
        "capability_id": "cap:file-write",
        "effect_kind": "file.write",
        "resource_pattern": "/data/*",
    },
    "cap:network": {
        "capability_id": "cap:network",
        "effect_kind": "network.egress",
        "resource_pattern": "*",
    },
    "cap:email-send": {
        "capability_id": "cap:email-send",
        "effect_kind": "email.send",
        "resource_pattern": "mailto:*",
    },
    "cap:handoff": {
        "capability_id": "cap:handoff",
        "effect_kind": "handoff.delegate",
        "resource_pattern": "agent:*",
    },
    "cap:mcp-invoke": {
        "capability_id": "cap:mcp-invoke",
        "effect_kind": "mcp.invoke",
        "resource_pattern": "mcp:*",
    },
    "cap:lab-release": {
        "capability_id": "cap:lab-release",
        "effect_kind": "lab.release",
        "resource_pattern": "lab:*",
    },
}

ROLE_CAPABILITY_MAP: dict[str, list[str]] = {
    "file_reader": ["cap:file-read"],
    "file_admin": ["cap:file-read", "cap:file-write"],
    "network_user": ["cap:network"],
    "email_user": ["cap:email-send"],
    "handoff_delegate": ["cap:handoff"],
    "mcp_user": ["cap:mcp-invoke"],
    "lab_operator": ["cap:lab-release"],
    "agent": ["cap:file-read", "cap:email-send", "cap:handoff", "cap:mcp-invoke"],
}

TOOL_NAME_MAP: dict[tuple[str, str], tuple[str, str, str]] = {
    ("filesystem.read", "filesystem"): ("cap:file-read", "file.read", "/data/*"),
    ("filesystem.write", "filesystem"): ("cap:file-write", "file.write", "/data/*"),
    ("network.request", "network"): ("cap:network", "network.egress", "*"),
    ("email.send", "email"): ("cap:email-send", "email.send", "mailto:*"),
    ("handoff.delegate", "handoff"): ("cap:handoff", "handoff.delegate", "agent:*"),
    ("mcp.invoke", "mcp"): ("cap:mcp-invoke", "mcp.invoke", "mcp:*"),
    ("lab.release", "lab"): ("cap:lab-release", "lab.release", "lab:*"),
}
