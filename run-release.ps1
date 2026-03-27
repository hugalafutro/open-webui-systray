# Launches the newest *.exe in bin\Release\net8.0-windows (detached; no wait).
# Silent (no PowerShell window): double-click run-release.cmd in this folder, or run:
#   powershell.exe -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ".\run-release.ps1"
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$releaseDir = Join-Path $PSScriptRoot 'bin\Release\net8.0-windows'
if (-not (Test-Path -LiteralPath $releaseDir)) {
    Write-Error "Release folder not found: $releaseDir — run build-release.ps1 first."
}

$exe = Get-ChildItem -LiteralPath $releaseDir -Filter '*.exe' -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $exe) {
    Write-Error "No .exe found in $releaseDir — run build-release.ps1 first."
}

Start-Process -FilePath $exe.FullName -WorkingDirectory $releaseDir
