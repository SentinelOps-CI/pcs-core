import json
from pathlib import Path

import pytest

from pcs_core.paths import package_dir, schemas_dir


@pytest.fixture
def schema_root() -> Path:
    root = schemas_dir()
    assert (root / "ScienceClaimBundle.v0.schema.json").is_file()
    return root


def test_bundled_or_checkout_schemas_present(schema_root: Path) -> None:
    assert schema_root.is_dir()


def test_schema_ids_unique(schema_root: Path) -> None:
    ids: set[str] = set()
    for path in schema_root.glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schema_id = schema.get("$id")
        assert isinstance(schema_id, str)
        assert schema_id not in ids, f"duplicate $id {schema_id} in {path.name}"
        ids.add(schema_id)


def test_wheel_layout_has_package_schemas_after_build() -> None:
    bundled = package_dir() / "schemas"
    if not bundled.is_dir():
        pytest.skip("schemas bundled at wheel build time (dev uses checkout schemas/)")
