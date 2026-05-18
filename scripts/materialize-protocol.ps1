# Regenerate LabTrust RC artifacts, tool-use fixtures, registry, and hash vectors.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $Root "python")
try {
    python scripts/materialize_tool_use_fixtures.py
    python scripts/materialize_labtrust_protocol_artifacts.py
    Write-Host "OK materialized protocol artifacts (LabTrust + tool-use)"
} finally {
    Pop-Location
}
