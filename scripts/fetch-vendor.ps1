$ErrorActionPreference = "Stop"

Write-Host "scripts\fetch-vendor.ps1 is deprecated. Tools are now stored in %APPDATA%\YtDlpWebUi\bin."
& (Join-Path $PSScriptRoot "fetch-tools.ps1")
