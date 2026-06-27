$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "python")
python scripts/materialize_labtrust_protocol_artifacts.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
pcs shared-hash-vectors verify
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
