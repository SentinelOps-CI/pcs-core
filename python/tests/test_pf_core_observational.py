"""Tests for PF-Core observational non-interference vocabulary."""

from __future__ import annotations

from pathlib import Path

from pcs_core.paths import repo_root


def test_observational_lean_defines_non_interference() -> None:
    path = repo_root() / "lean" / "PFCore" / "Observational.lean"
    text = path.read_text(encoding="utf-8")
    for name in (
        "NonInterference",
        "nonInterferenceD",
        "HighTenantEvent",
        "traceSafe_implies_non_interference",
        "tenantIsolation_implies_non_interference",
        "traceCrossTenantSafe_implies_high_tenant_not_low",
        "non_interference_observational_equivalence",
    ):
        assert name in text, f"missing {name} in Observational.lean"


def test_non_interference_doc_mentions_limits() -> None:
    doc = repo_root() / "docs" / "pf-core" / "non-interference.md"
    text = doc.read_text(encoding="utf-8")
    for phrase in (
        "NonInterference",
        "covert channels",
        "timing",
        "handoff",
    ):
        assert phrase.lower() in text.lower(), f"missing {phrase!r} in non-interference.md"
