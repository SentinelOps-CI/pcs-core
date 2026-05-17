"""PCS ArtifactRegistry.v0 and registry CLI helpers."""

import json
from pathlib import Path

import pytest

from pcs_core.registry import (
    build_artifact_registry,
    check_artifact_against_registry,
    default_registry_path,
    explain_artifact_type,
    list_artifact_types,
    validate_registry_file,
)
from pcs_core.validate import ValidationError, validate_file

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
RELEASE = EXAMPLES / "labtrust-release"


def test_registry_example_validates() -> None:
    assert validate_file(default_registry_path()) == "ArtifactRegistry.v0"


def test_build_registry_matches_on_disk() -> None:
    built = build_artifact_registry()
    on_disk = json_load(default_registry_path())
    assert built["entries"].keys() == on_disk["entries"].keys()
    assert built["signature_or_digest"] == on_disk["signature_or_digest"]


def test_registry_validate_no_drift() -> None:
    assert validate_registry_file(default_registry_path()) == []


def test_list_artifact_types_includes_core_chain() -> None:
    types = list_artifact_types()
    assert "TraceCertificate.v0" in types
    assert "ReleaseManifest.v0" in types
    assert len(types) >= 13


def test_explain_trace_certificate() -> None:
    entry = explain_artifact_type("TraceCertificate.v0")
    assert entry["producer"] == "CertifyEdge"
    assert "CertificateChecked" in entry["allowed_statuses"]


def test_check_labtrust_trace_certificate() -> None:
    path = RELEASE / "trace_certificate.json"
    assert check_artifact_against_registry(path) == []


def test_unknown_registry_type_raises() -> None:
    with pytest.raises(ValidationError):
        explain_artifact_type("NotAnArtifact.v0")


def json_load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
