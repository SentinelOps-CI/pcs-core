//! Generated PF-Core catalog (do not edit by hand).

pub const EFFECT_KINDS: &[&str] = &[
    "file.read",
    "file.write",
    "network.egress",
    "email.send",
    "handoff.delegate",
    "mcp.invoke",
    "lab.release",
];

pub const CAPABILITY_CATALOG: &[(&str, &str, &str)] = &[
    ("cap:file-read", "file.read", "/data/*"),
    ("cap:file-write", "file.write", "/data/*"),
    ("cap:network", "network.egress", "*"),
    ("cap:email-send", "email.send", "mailto:*"),
    ("cap:handoff", "handoff.delegate", "agent:*"),
    ("cap:mcp-invoke", "mcp.invoke", "mcp:*"),
    ("cap:lab-release", "lab.release", "lab:*"),
];

pub const ROLE_CAPABILITY_MAP: &[(&str, &[&str])] = &[
    ("file_reader", &["cap:file-read"]),
    ("file_admin", &["cap:file-read", "cap:file-write"]),
    ("network_user", &["cap:network"]),
    ("email_user", &["cap:email-send"]),
    ("handoff_delegate", &["cap:handoff"]),
    ("mcp_user", &["cap:mcp-invoke"]),
    ("lab_operator", &["cap:lab-release"]),
    (
        "agent",
        &[
            "cap:file-read",
            "cap:email-send",
            "cap:handoff",
            "cap:mcp-invoke",
        ],
    ),
];
