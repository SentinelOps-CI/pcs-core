#!/usr/bin/env pwsh
# Delegate to LabTrust-Gym PCS v0.1 clean-checkout chain (requires sibling checkout).
$ErrorActionPreference = "Stop"

$PcsCoreRoot = Split-Path -Parent $PSScriptRoot
$Parent = Split-Path -Parent $PcsCoreRoot
$LabtrustRoot = if ($env:LABTRUST_GYM_ROOT) { $env:LABTRUST_GYM_ROOT } else { Join-Path $Parent "LabTrust-Gym" }
$ChainScript = Join-Path $LabtrustRoot "examples\pcs_qc_release\scripts\run_pcs_v01_clean_chain.ps1"

if (-not (Test-Path $ChainScript)) {
    throw "LabTrust-Gym clean-chain script not found: $ChainScript`nClone LabTrust-Gym beside pcs-core or set LABTRUST_GYM_ROOT."
}

if (-not $env:PCS_DETERMINISTIC) { $env:PCS_DETERMINISTIC = "1" }

& $ChainScript @args
