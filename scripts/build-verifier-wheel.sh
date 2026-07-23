#!/usr/bin/env bash
# Build an optional full verifier wheel that embeds Lean sources via importlib.resources.
# Default `pip wheel ./python` remains the validator distribution (schemas + catalog only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/python"

export PCS_BUILD_VERIFIER=1
python3 <<'PY'
from pathlib import Path
import re

pyproject = Path("pyproject.toml")
text = pyproject.read_text(encoding="utf-8")
insert = (
    "[tool.hatch.build.targets.wheel.force-include]\n"
    '"../schemas" = "pcs_core/schemas"\n'
    '"../catalog" = "pcs_core/catalog"\n'
    '"../test_vectors/hash" = "pcs_core/test_vectors/hash"\n'
    '"../lean" = "pcs_core/lean"\n'
    '"../pins" = "pcs_core/pins"\n'
)
text2 = re.sub(
    r"\[tool\.hatch\.build\.targets\.wheel\.force-include\][\s\S]*?(?=\n\[|\Z)",
    insert + "\n",
    text,
    count=1,
)
override = Path("pyproject.verifier.toml")
override.write_text(text2, encoding="utf-8")
print(f"Wrote {override}")
PY

pip install --upgrade build
# Hatchling reads pyproject.toml; temporarily swap for the verifier override.
cp pyproject.toml pyproject.validator.toml.bak
cp pyproject.verifier.toml pyproject.toml
trap 'cp pyproject.validator.toml.bak pyproject.toml; rm -f pyproject.validator.toml.bak' EXIT
python -m build --wheel
echo "OK verifier wheel under python/dist/ (Lean assets embedded under pcs_core/lean)"
