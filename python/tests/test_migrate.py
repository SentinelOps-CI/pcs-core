"""PCS v0 identity migration."""

import json
from pathlib import Path

import pytest

from pcs_core.migrate import migrate_artifact, migrate_file
from pcs_core.validate import ValidationError

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_migrate_v0_identity_noop() -> None:
    path = EXAMPLES / "runtime_receipt.valid.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    migrated, report = migrate_artifact(data, from_version="v0", to_version="v0")
    assert migrated == data
    assert report["status"] == "noop"
    assert report["artifact_type"] == "RuntimeReceipt.v0"


def test_migrate_unsupported_version_pair() -> None:
    data = json.loads((EXAMPLES / "runtime_receipt.valid.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        migrate_artifact(data, from_version="v0", to_version="v1")


def test_migrate_file_report(tmp_path: Path) -> None:
    src = EXAMPLES / "trace_certificate.valid.json"
    dest = tmp_path / "trace_certificate.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    report = migrate_file(dest, from_version="v0", to_version="v0")
    assert report["status"] == "noop"
    assert report["artifact_type"] == "TraceCertificate.v0"
