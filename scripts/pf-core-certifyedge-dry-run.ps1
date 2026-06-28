# CertifyEdge release-gate dry-run (mock mode). Run from repository root. No git operations.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "python"
$mockDir = Join-Path $root "examples\pf-core-valid\certifyedge_mock"
$outCert = Join-Path $env:TEMP "pfcore-certifyedge-dry-run.json"

$env:PF_CORE_CERTIFYEDGE_MODE = "mock"

Set-Location $py
pip install -e ".[dev]" -q | Out-Null

Write-Host "=== CertifyEdge mock certifyedge-check ===" -ForegroundColor Cyan
pcs pf-core certifyedge-check `
  --trace (Join-Path $mockDir "trace.json") `
  --property qc_release.temporal.safety `
  --out $outCert

Write-Host "=== Validate mock fixture ===" -ForegroundColor Cyan
pcs pf-core validate-trace (Join-Path $mockDir "trace.json")
pcs validate (Join-Path $mockDir "certificate.json")

Write-Host "OK CertifyEdge dry-run (mock; not live release-gate attestation)" -ForegroundColor Green
