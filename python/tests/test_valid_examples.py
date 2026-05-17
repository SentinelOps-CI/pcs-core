from pathlib import Path

import pytest

from pcs_core.validate import validate_file

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _valid_example_paths() -> list[Path]:
    return sorted(p for p in EXAMPLES.rglob("*.json") if ".valid." in p.name)


@pytest.mark.parametrize("path", _valid_example_paths(), ids=lambda p: str(p.relative_to(EXAMPLES)))
def test_valid_examples(path: Path) -> None:
    artifact_type = validate_file(path)
    assert artifact_type
