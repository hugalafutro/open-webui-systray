# Clean and rebuild Release configuration for web-systray.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$csproj = Join-Path $root 'web-systray.csproj'

Push-Location $root
try {
    dotnet clean $csproj -c Release --verbosity minimal
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    dotnet build $csproj -c Release --verbosity minimal
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
