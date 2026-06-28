"""Tests for PF-Core observational non-interference vocabulary."""

from __future__ import annotations

import json

from pcs_core.paths import repo_root
from pcs_core.pf_core_runtime import (
    validate_observational_non_interference,
    validate_observational_non_interference_all_pairs,
)


def test_observational_lean_defines_non_interference() -> None:
    path = repo_root() / "lean" / "PFCore" / "Observational.lean"
    text = path.read_text(encoding="utf-8")
    for name in (
        "NonInterference",
        "nonInterferenceD",
        "nonInterferenceD_sound",
        "traceSafeD_implies_nonInterferenceD",
        "HighTenantEvent",
        "traceSafe_implies_non_interference",
        "tenantIsolation_implies_non_interference",
        "traceCrossTenantSafe_implies_high_tenant_not_low",
        "non_interference_observational_equivalence",
        "deny_event_not_low",
        "deny_event_is_high",
        "deny_event_not_in_trace_projection",
        "traceProjection_append",
        "trace_append_preserves_non_interference",
        "handoffSafe_traceSafe_non_interference",
    ):
        assert name in text, f"missing {name} in Observational.lean"
    ni_text = (repo_root() / "lean" / "PFCore" / "NonInterference.lean").read_text(encoding="utf-8")
    for name in (
        "traceSafeD_implies_tenantIsolationD",
        "traceSafeD_implies_traceCrossTenantSafeD",
        "event_deny_implies_crossTenantDenied",
    ):
        assert name in ni_text, f"missing {name} in NonInterference.lean"
    handoff_text = (repo_root() / "lean" / "PFCore" / "Handoff.lean").read_text(encoding="utf-8")
    for name in ("handoffSafe_requires_same_tenant", "handoffSafe_forbids_distinct_tenant"):
        assert name in handoff_text, f"missing {name} in Handoff.lean"
    resource_text = (repo_root() / "lean" / "PFCore" / "ResourcePattern.lean").read_text(
        encoding="utf-8"
    )
    for name in (
        "ActionAdmissibleWithResourcePattern",
        "actionAdmissibleWithResourcePatternD_sound",
        "actionAdmissibleWithResourcePattern_implies_actionAdmissible",
        "TraceSafeR",
        "traceSafeR_implies_traceSafe",
        "eventSafeR_allow_implies_resource_pattern",
    ):
        assert name in resource_text, f"missing {name} in ResourcePattern.lean"
    compositional_text = (repo_root() / "lean" / "PFCore" / "Compositional.lean").read_text(
        encoding="utf-8"
    )
    for name in (
        "traceSafe_append",
        "traceSafeR_append",
        "trace_append_preserves_tenant_isolation",
    ):
        assert name in compositional_text, f"missing {name} in Compositional.lean"


def test_non_interference_doc_mentions_limits() -> None:
    doc = repo_root() / "docs" / "pf-core" / "non-interference.md"
    text = doc.read_text(encoding="utf-8")
    for phrase in (
        "NonInterference",
        "covert channels",
        "timing",
        "handoff",
        "Adversary model extension roadmap",
        "ActionAdmissibleWithResourcePattern",
    ):
        assert phrase.lower() in text.lower(), f"missing {phrase!r} in non-interference.md"


def test_validate_observational_non_interference_on_allowed_fixture() -> None:
    trace_path = repo_root() / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    tenant = trace["events"][0]["principal"]["tenant"]
    assert validate_observational_non_interference(trace, tenant, "other-tenant") == []
    assert validate_observational_non_interference_all_pairs(trace) == []


def test_validate_observational_non_interference_same_tenant_vacuous() -> None:
    trace_path = repo_root() / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    tenant = trace["events"][0]["principal"]["tenant"]
    assert validate_observational_non_interference(trace, tenant, tenant) == []
