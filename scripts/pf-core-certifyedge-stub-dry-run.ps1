# CertifyEdge stub CLI dry-run (format contract, not live attestation). Run from repository root.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "python"
$stub = Join-Path $root "scripts\certifyedge-stub.py"
$trace = Join-Path $root "examples\pf-core-valid\labtrust_replay\trace.json"
$outCert = Join-Path $env:TEMP "pfcore-certifyedge-stub-dry-run.json"

if (-not (Test-Path $stub)) {
    throw "missing certifyedge-stub.py"
}

$env:PF_CORE_CERTIFYEDGE_MODE = "live"
$env:PF_CORE_CERTIFYEDGE_CLI = $stub

Set-Location $py
pip install -e ".[dev]" -q | Out-Null

Write-Host "=== CertifyEdge stub certifyedge-check ===" -ForegroundColor Cyan
pcs pf-core certifyedge-check `
  --trace $trace `
  --property qc_release.temporal.safety `
  --out $outCert

$cert = Get-Content $outCert -Raw | ConvertFrom-Json
if (-not $cert.checker_version) { throw "stub certificate missing checker_version" }
if ($cert.checker_version -ne "0.1.0") {
    throw "unexpected checker_version: $($cert.checker_version)"
}
$attestation = $null
foreach ($ob in $cert.obligations) {
    if ($ob.proof_ref) { $attestation = $ob.proof_ref; break }
}
if (-not $attestation) { throw "stub certificate missing proof_ref attestation" }
if ($attestation -notlike "stub://certifyedge/*") {
    throw "expected stub:// attestation, got $attestation"
}
$refs = @($cert.assumption_refs)
if ($refs -notcontains $attestation) {
    throw "attestation_ref not present in assumption_refs: $attestation"
}

Write-Host "OK CertifyEdge stub dry-run (format contract; not release-grade live attestation)" -ForegroundColor Green
