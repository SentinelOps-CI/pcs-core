"""Cross-language PF-Core schema registration and artifact_type detection parity."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pcs_core.pf_core_contract import validate_trace_contracts
from pcs_core.pf_core_runtime import (
    CAPABILITY_CATALOG,
    compute_event_hash,
    compute_trace_hash,
    resource_matches_pattern,
    validate_cross_tenant_safety,
    validate_denied_events_preserved,
    validate_observational_non_interference,
    validate_observational_non_interference_all_pairs,
    validate_pfcore_trace_hash_chain,
    validate_tenant_isolation,
)
from pcs_core.validate import ARTIFACT_SCHEMAS, detect_artifact_type, validate_semantics

REPO = Path(__file__).resolve().parents[2]
INVALID_VECTORS = REPO / "python" / "tests" / "hash_vectors" / "pf_core" / "invalid"
INVALID_EXAMPLES = REPO / "examples" / "pf-core-invalid"

PF_CORE_TYPES = sorted(
    key
    for key in ARTIFACT_SCHEMAS
    if key.startswith("PFCore")
    or key in {"ToolUseTrace.v0", "LeanCheckResult.v0", "PCSBridgeCertificate.v0"}
)

# Audit-list invalid vectors: Python/Rust/TS must reject the same error class.
INVALID_AUDIT_CASES: tuple[tuple[str, str, str, str], ...] = (
    ("hash_vectors", "invalid/trace_hash_chain_break.json", "PFCoreTrace.v0", "EventHashMismatch"),
    (
        "hash_vectors",
        "invalid/claim_class_overclaim_trace.json",
        "PFCoreTrace.v0",
        "ClaimClassOverclaim",
    ),
    ("hash_vectors", "invalid/trace_hash_mismatch.json", "PFCoreTrace.v0", "TraceHashMismatch"),
    (
        "hash_vectors",
        "invalid/previous_event_hash_mismatch.json",
        "PFCoreTrace.v0",
        "EventHashMismatch",
    ),
    ("hash_vectors", "invalid/cross_tenant_leak.json", "PFCoreTrace.v0", "TenantIsolation"),
    (
        "examples",
        "lean_kernel_checked_on_trace/trace.json",
        "PFCoreTrace.v0",
        "ClaimClassOverclaim",
    ),
    (
        "examples",
        "lean_kernel_checked_without_proof_ref/trace.json",
        "PFCoreTrace.v0",
        "ClaimClassOverclaim",
    ),
    (
        "examples",
        "lean_kernel_checked_without_proof_term_hash/certificate.json",
        "PFCoreCertificate.v0",
        "proof_term_hash",
    ),
    (
        "examples",
        "lean_kernel_checked_without_proof_term_ref/certificate.json",
        "PFCoreCertificate.v0",
        "proof_term_ref",
    ),
    (
        "examples",
        "lean_kernel_checked_with_skipped_build/certificate.json",
        "PFCoreCertificate.v0",
        "lean_build_status",
    ),
    (
        "examples",
        "unknown_direct_trace_effect/trace.json",
        "PFCoreTrace.v0",
        "UnknownEffect",
    ),
    (
        "examples",
        "capability_effect_mismatch/trace.json",
        "PFCoreTrace.v0",
        "CapabilityEffectMismatch",
    ),
    (
        "examples",
        "unknown_direct_trace_capability/trace.json",
        "PFCoreTrace.v0",
        "UnknownCapability",
    ),
    (
        "hash_vectors",
        "invalid/unknown_direct_trace_effect.json",
        "PFCoreTrace.v0",
        "UnknownEffect",
    ),
    (
        "hash_vectors",
        "invalid/capability_effect_mismatch.json",
        "PFCoreTrace.v0",
        "CapabilityEffectMismatch",
    ),
    (
        "hash_vectors",
        "invalid/unknown_direct_trace_capability.json",
        "PFCoreTrace.v0",
        "UnknownCapability",
    ),
)

TS_SCHEMAS = REPO / "typescript" / "packages" / "core" / "src" / "schema.ts"
RUST_SCHEMAS = REPO / "rust" / "crates" / "pcs-core" / "src" / "validation.rs"
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_fixture_path(source: str, relative: str) -> Path:
    if source == "hash_vectors":
        return REPO / "python" / "tests" / "hash_vectors" / "pf_core" / relative
    if source == "examples":
        return INVALID_EXAMPLES / relative
    raise ValueError(f"unknown source {source!r}")


def _python_semantic_errors(source: str, relative: str, artifact_type: str) -> list[str]:
    payload = _load_json(_audit_fixture_path(source, relative))
    if artifact_type == "PFCoreTrace.v0" and relative.endswith("cross_tenant_leak.json"):
        return validate_tenant_isolation(payload)
    if artifact_type == "PFCoreTrace.v0":
        return validate_semantics(payload, artifact_type)
    return validate_semantics(payload, artifact_type)


def _extract_quoted_types(path: Path, marker: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    block = text.split(marker, 1)[-1]
    return set(
        re.findall(r'"((?:PFCore|ToolUseTrace|LeanCheckResult|PCSBridgeCertificate)[^"]+)"', block)
    )


def test_python_pf_core_schemas_registered() -> None:
    for artifact_type in PF_CORE_TYPES:
        assert artifact_type in ARTIFACT_SCHEMAS


def test_typescript_registers_same_pf_core_schemas() -> None:
    ts_types = _extract_quoted_types(TS_SCHEMAS, "const ARTIFACT_SCHEMAS")
    assert set(PF_CORE_TYPES).issubset(ts_types)


def test_rust_registers_same_pf_core_schemas() -> None:
    rust_types = _extract_quoted_types(RUST_SCHEMAS, "const ARTIFACT_SCHEMAS")
    assert set(PF_CORE_TYPES).issubset(rust_types)


@pytest.mark.parametrize(
    "relative",
    [
        "examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json",
        "examples/pf-core-valid/contract_checked/trace.json",
        "examples/pf-core-valid/handoff_subset_authority/handoff.json",
        "examples/pf-core-valid/assumption_declared/certificate.json",
    ],
)
def test_python_explicit_artifact_type_detection(relative: str) -> None:
    path = REPO / relative
    data = _load_json(path)
    detected = detect_artifact_type(data)
    assert detected == data["artifact_type"]


def test_pf_core_trace_not_detected_as_trace_certificate() -> None:
    trace = _load_json(REPO / "examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json")
    assert detect_artifact_type(trace) == "PFCoreTrace.v0"
    assert detect_artifact_type(trace) != "TraceCertificate.v0"


@pytest.mark.parametrize("artifact_type", PF_CORE_TYPES)
def test_pf_core_schema_files_exist(artifact_type: str) -> None:
    schema_path = REPO / "schemas" / ARTIFACT_SCHEMAS[artifact_type]
    assert schema_path.is_file(), f"missing schema for {artifact_type}"


def test_python_pf_core_trace_hash_chain_valid_fixture() -> None:
    trace = _load_json(VALID_TRACE)
    assert validate_pfcore_trace_hash_chain(trace) == []


def test_python_pf_core_trace_hash_recompute() -> None:
    trace = _load_json(VALID_TRACE)
    assert compute_trace_hash(trace) == trace["trace_hash"]
    for event in trace["events"]:
        assert compute_event_hash(event) == event["event_hash"]


def test_python_claim_class_overclaim_on_trace() -> None:
    trace = _load_json(VALID_TRACE)
    trace = dict(trace)
    trace["claim_class"] = "LeanKernelChecked"
    errors = validate_pfcore_trace_hash_chain(trace)
    assert any("ClaimClassOverclaim" in err for err in errors)


def test_python_pf_core_shared_hash_vectors() -> None:
    vector_root = REPO / "python" / "tests" / "hash_vectors" / "pf_core"
    for name in ("PFCoreEvent.v0", "PFCoreTrace.v0", "PFCoreContract.v0"):
        payload = _load_json(vector_root / name / "input.json")
        digest = (vector_root / name / "digest.txt").read_text(encoding="utf-8").strip()
        if name == "PFCoreEvent.v0":
            assert compute_event_hash(payload) == digest
        elif name == "PFCoreTrace.v0":
            assert compute_trace_hash(payload) == digest
        else:
            from pcs_core.hash import canonical_hash

            assert canonical_hash(payload) == digest


@pytest.mark.parametrize(
    "relative,needle",
    [
        ("invalid/trace_hash_chain_break.json", "EventHashMismatch"),
        ("invalid/claim_class_overclaim_trace.json", "ClaimClassOverclaim"),
        ("invalid/trace_hash_mismatch.json", "TraceHashMismatch"),
        ("invalid/previous_event_hash_mismatch.json", "EventHashMismatch"),
    ],
)
def test_python_invalid_pf_core_vectors(relative: str, needle: str) -> None:
    trace = _load_json(REPO / "python" / "tests" / "hash_vectors" / "pf_core" / relative)
    errors = validate_pfcore_trace_hash_chain(trace)
    assert any(needle in err for err in errors)


def test_python_denied_event_preserved_invalid_vector() -> None:
    from pcs_core.pf_core_runtime import DroppedDeniedEvent, validate_denied_events_preserved

    root = (
        REPO / "python" / "tests" / "hash_vectors" / "pf_core" / "invalid" / "denied_event_dropped"
    )
    tool_use = _load_json(root / "tool_use_trace.json")
    pfcore = _load_json(root / "pfcore_trace.json")
    with pytest.raises(DroppedDeniedEvent):
        validate_denied_events_preserved(tool_use, pfcore)


def test_rust_pf_core_detection_tests_pass() -> None:
    result = subprocess.run(
        ["cargo", "test", "pf_core", "--", "--nocapture"],
        cwd=REPO / "rust",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_typescript_pf_core_detection_tests_pass() -> None:
    if sys.platform == "win32":
        pytest.skip("typescript workspace test runner uses shell globs unavailable on Windows")
    ts_root = REPO / "typescript"
    install = subprocess.run(
        ["npm", "install", "--silent"],
        cwd=ts_root,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    result = subprocess.run(
        ["npm", "test"],
        cwd=ts_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_shared_negative_vectors_python() -> None:
    trace = _load_json(INVALID_VECTORS / "trace_hash_chain_break.json")
    assert any("EventHashMismatch" in err for err in validate_pfcore_trace_hash_chain(trace))

    overclaim = _load_json(INVALID_VECTORS / "claim_class_overclaim_trace.json")
    assert any("ClaimClassOverclaim" in err for err in validate_pfcore_trace_hash_chain(overclaim))

    trace_mismatch = _load_json(INVALID_VECTORS / "trace_hash_mismatch.json")
    assert any(
        "TraceHashMismatch" in err for err in validate_pfcore_trace_hash_chain(trace_mismatch)
    )

    prev_mismatch = _load_json(INVALID_VECTORS / "previous_event_hash_mismatch.json")
    assert any(
        "EventHashMismatch" in err for err in validate_pfcore_trace_hash_chain(prev_mismatch)
    )

    from pcs_core.pf_core_runtime import validate_tenant_isolation

    cross_tenant = _load_json(INVALID_VECTORS / "cross_tenant_leak.json")
    assert any("TenantIsolation" in err for err in validate_tenant_isolation(cross_tenant))
    assert any("CrossTenantSafe" in err for err in validate_cross_tenant_safety(cross_tenant))

    allowed = _load_json(REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json")
    assert validate_cross_tenant_safety(allowed) == []
    assert validate_tenant_isolation(allowed) == []

    tenant = allowed["events"][0]["principal"]["tenant"]
    assert validate_observational_non_interference(allowed, tenant, "other-tenant") == []
    assert validate_observational_non_interference_all_pairs(allowed) == []

    contract_dir = INVALID_VECTORS / "contract_capability_missing"
    contract_trace = _load_json(contract_dir / "trace.json")
    contract = _load_json(contract_dir / "contract.json")
    issues = validate_trace_contracts(contract_trace, {contract["contract_id"]: contract})
    assert any(issue.code == "ContractCapabilityRequired" for issue in issues)

    denied_dir = INVALID_VECTORS / "denied_event_dropped"
    with pytest.raises(Exception):
        validate_denied_events_preserved(
            _load_json(denied_dir / "tool_use_trace.json"),
            _load_json(denied_dir / "pfcore_trace.json"),
        )


def test_rust_negative_vector_tests_in_pf_core_suite() -> None:
    result = subprocess.run(
        ["cargo", "test", "pf_core_", "--", "--nocapture"],
        cwd=REPO / "rust",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("source,relative,artifact_type,needle", INVALID_AUDIT_CASES)
def test_python_invalid_audit_vectors(
    source: str, relative: str, artifact_type: str, needle: str
) -> None:
    errors = _python_semantic_errors(source, relative, artifact_type)
    assert any(needle in err for err in errors), errors


def test_resource_pattern_catalog_python_glob_match() -> None:
    """Parity anchor for Lean ResourcePattern.lean / runtime validate_resource_scope."""
    samples = {
        "*": [("/any/uri", True), ("mailto:x@y", True)],
        "/data/*": [("/data/report.txt", True), ("/etc/passwd", False)],
        "mailto:*": [("mailto:a@b.c", True), ("http://x", False)],
        "agent:*": [("agent:worker-1", True), ("mcp:tool", False)],
        "mcp:*": [("mcp:filesystem.read", True), ("agent:x", False)],
        "lab:*": [("lab:run-1", True), ("/data/x", False)],
    }
    for cap in CAPABILITY_CATALOG.values():
        pattern = str(cap["resource_pattern"])
        assert pattern in samples, f"add parity samples for catalog pattern {pattern!r}"
        for uri, expected in samples[pattern]:
            assert resource_matches_pattern(uri, pattern) is expected, (pattern, uri)


def test_resource_pattern_rejects_fnmatch_only_features() -> None:
    """Catalog glob subset does not treat ``?`` or ``[]`` as wildcards."""
    assert not resource_matches_pattern("a", "?")
    assert not resource_matches_pattern("a", "[a]")


def test_observational_and_resource_pattern_lean_modules_exist() -> None:
    for module in ("Observational.lean", "ResourcePattern.lean"):
        path = REPO / "lean" / "PFCore" / module
        text = path.read_text(encoding="utf-8")
        assert "sorry" not in text, module
        assert "theorem" in text, module


def test_contract_semantics_checked_resource_obligations_parity() -> None:
    """Rust/TS/Python reject lean_proof_checked certs missing resource scope metadata."""
    from pcs_core.validate_pf_core import _validate_pfcore_certificate

    missing_lean = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "test-missing-lean-resource-semantics",
        "trace_hash": "sha256:" + "0" * 64,
        "contract_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "claim_class": "LeanKernelChecked",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "assumption_refs": ["docs/pf-core/trusted-boundary.md"],
        "lean_proof_checked": True,
        "proof_term_ref": "lean/PFCore/Generated/example.lean",
        "proof_term_hash": "sha256:" + "f" * 64,
        "lean_environment_hash": "sha256:" + "e" * 64,
        "pfcore_kernel_hash": "sha256:" + "d" * 64,
        "lean_build_status": {"ok": True, "target": "PFCore", "detail": "ok"},
        "default_contract_ref": "trace-safe",
        "contract_semantics_checked": {
            "lean": [],
            "runtime": ["resource_pattern_scope"],
        },
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    errors = _validate_pfcore_certificate(missing_lean)
    assert any("resource_within_capability_pattern" in err for err in errors)

    ok = dict(missing_lean)
    ok["contract_semantics_checked"] = {
        "lean": ["resource_within_capability_pattern"],
        "runtime": ["resource_pattern_scope"],
    }
    resource_errors = [
        err
        for err in _validate_pfcore_certificate(ok)
        if "resource_within_capability_pattern" in err or "resource_pattern_scope" in err
    ]
    assert resource_errors == []


def test_trace_safe_rd_decider_parity() -> None:
    """Python lean_check TraceSafeR decider matches TraceSafe on catalog-valid traces."""
    from pcs_core.lean_check import trace_safe_d, trace_safe_rd

    trace = _load_json(VALID_TRACE)
    events = trace["events"]
    assert trace_safe_d(events)
    assert trace_safe_rd(events)
    assert trace_safe_rd(events) == trace_safe_d(events)

    bad_path = REPO / "examples" / "pf-core-invalid" / "resource_scope_violation" / "trace.json"
    bad = _load_json(bad_path)
    bad_events = bad["events"]
    assert not trace_safe_rd(bad_events)


def test_codegen_emits_trace_safe_r_obligations_on_valid_trace(tmp_path: Path) -> None:
    from pcs_core.pf_core_lean_codegen import generate_proof_obligation_file

    trace = _load_json(VALID_TRACE)
    proof_path = generate_proof_obligation_file(trace, tmp_path, trace_path=VALID_TRACE)
    text = proof_path.read_text(encoding="utf-8")
    assert "theorem concrete_trace_safe_r" in text
    assert "traceSafeRD" in text


def test_workflow_catalog_certificate_mode_without_sibling_file(tmp_path: Path) -> None:
    from pcs_core.pf_core_lean_codegen import resolve_certificate_mode

    trace = dict(_load_json(REPO / "examples/pf-core-valid/file_read_allowed/trace.json"))
    trace["workflow_id"] = "agent_tool_use.safety_v0"
    trace.pop("required_certificate_mode", None)
    trace_file = tmp_path / "pfcore_trace.json"
    trace_file.write_text(json.dumps(trace), encoding="utf-8")
    assert (
        resolve_certificate_mode(trace, trace_path=trace_file, release_grade=False)
        == "TraceSafeRCertificate"
    )
    assert (
        resolve_certificate_mode(trace, trace_path=trace_file, release_grade=True)
        == "TraceSafeRCertificate"
    )


def test_valid_tool_use_trace_has_required_certificate_mode() -> None:
    trace = _load_json(VALID_TRACE)
    assert trace.get("required_certificate_mode") == "TraceSafeRCertificate"
