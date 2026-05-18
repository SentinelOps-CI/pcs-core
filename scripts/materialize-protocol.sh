#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/python"
python scripts/materialize_tool_use_fixtures.py
python scripts/materialize_computation_fixtures.py
python scripts/materialize_labtrust_protocol_artifacts.py
echo "OK materialized protocol artifacts (LabTrust + tool-use + computation)"
