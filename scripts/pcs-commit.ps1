# Commit with hooks disabled so Cursor cannot append Co-authored-by trailers.
# Usage: .\scripts\pcs-commit.ps1 -m "Your message"
#        .\scripts\pcs-commit.ps1 -F path\to\message.txt
param(
    [string]$m,
    [string]$F
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EmptyHooks = Join-Path $Root ".git\empty-hooks"

if (-not (Test-Path $EmptyHooks)) {
    New-Item -ItemType Directory -Force -Path $EmptyHooks | Out-Null
}

$gitArgs = @("-C", $Root, "-c", "core.hooksPath=.git/empty-hooks", "commit")
if ($F) {
    $gitArgs += @("-F", $F)
} elseif ($m) {
    $gitArgs += @("-m", $m)
} else {
    Write-Error "Provide -m or -F"
    exit 1
}

& git @gitArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git -C $Root log -1 --format=%B
