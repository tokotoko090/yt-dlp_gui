$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build"
$Name = "yt-dlp-webUI"
$PortableDir = Join-Path $Dist $Name
$ZipPath = Join-Path $Dist "yt-dlp-webui-portable.zip"

if (Test-Path -LiteralPath $Build) {
    Remove-Item -LiteralPath $Build -Recurse -Force
}
if (Test-Path -LiteralPath $PortableDir) {
    Remove-Item -LiteralPath $PortableDir -Recurse -Force
}
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --name $Name `
    --onedir `
    --add-data "src\web\static;src\web\static" `
    --exclude-module PySide6 `
    "src\main.py"

$BuiltDir = Join-Path $Dist $Name
if (-not (Test-Path -LiteralPath $BuiltDir)) {
    throw "PyInstaller output was not found: $BuiltDir"
}

Get-ChildItem -Path $BuiltDir -Recurse -Include "yt-dlp.exe", "ffmpeg.exe" | Remove-Item -Force
Compress-Archive -LiteralPath $BuiltDir -DestinationPath $ZipPath -Force
Write-Host "Portable zip created: $ZipPath"
Write-Host "External tools are not bundled. The app downloads yt-dlp and ffmpeg into %APPDATA%\YtDlpWebUi\bin."
