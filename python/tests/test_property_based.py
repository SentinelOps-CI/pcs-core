"""Hypothesis property-based tests for paths, manifests, and attestation fields."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytest.importorskip("hypothesis")

from hypothesis import given, settings
from hypothesis import strategies as st

from pcs_core.external_attestation import (
    build_external_attestation,
    validate_external_attestation,
)
from pcs_core.safe_paths import UnsafePathError, resolve_contained_file

DIGEST = st.from_regex(r"sha256:[a-f0-9]{64}", fullmatch=True)
UNSAFE_REL = st.sampled_from(
    [
        "../x",
        "..\\x",
        "/etc/passwd",
        r"C:\Windows\system.ini",
        "//server/share",
        r"\\server\share",
        "a/../../b",
        "",
        "a\x00b",
    ]
)


@given(ref=UNSAFE_REL)
@settings(max_examples=40)
def test_property_unsafe_paths_rejected(ref: str) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "ok.json").write_text("{}", encoding="utf-8")
        with pytest.raises(UnsafePathError):
            resolve_contained_file(root, ref)


@given(
    name=st.sampled_from(["ok.json", "a.json", "manifest.json", "trace.json", "nested_name.json"])
)
@settings(max_examples=20)
def test_property_safe_relative_accepted(name: str) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        path = root / name
        path.write_text("{}", encoding="utf-8")
        resolved = resolve_contained_file(root, name, allowed_suffixes=frozenset({".json"}))
        assert resolved.is_file()


@given(
    bundle_digest=DIGEST,
    trace_digest=DIGEST,
    binary_digest=DIGEST,
    property_id=st.from_regex(r"[a-z][a-z0-9_.-]{2,40}", fullmatch=True),
    checker_version=st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True),
)
@settings(max_examples=25)
def test_property_external_attestation_fields_validate(
    bundle_digest: str,
    trace_digest: str,
    binary_digest: str,
    property_id: str,
    checker_version: str,
) -> None:
    attestation = build_external_attestation(
        release_bundle_digest=bundle_digest,
        trace_digest=trace_digest,
        property_id=property_id,
        checker="certifyedge",
        checker_version=checker_version,
        checker_binary_digest=binary_digest,
        result="CertificateChecked",
        attestation_class="mock",
        issuer_identity="certifyedge-mock",
        attestation_ref=f"mock://certifyedge/{property_id}",
    )
    assert validate_external_attestation(attestation) == []
