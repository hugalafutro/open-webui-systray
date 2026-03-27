# Clean and rebuild Release configuration for open-webui-systray.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$csproj = Join-Path $root 'open-webui-systray.csproj'

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
