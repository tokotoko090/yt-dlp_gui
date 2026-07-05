$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build"
$Name = "yt-dlp-webUI"
$PortableDir = Join-Path $Dist $Name
$ZipPath = Join-Path $Dist "yt-dlp-webui-portable.zip"

function Remove-PathIfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
        ForEach-Object {
            try {
                $_.Attributes = "Normal"
            } catch {
            }
        }

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        } catch {
            if ($attempt -eq 3) {
                throw
            }
            Start-Sleep -Milliseconds (300 * $attempt)
        }
    }
}

function Compress-DirectoryWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            if (Test-Path -LiteralPath $Destination) {
                Remove-Item -LiteralPath $Destination -Force
            }
            Compress-Archive -LiteralPath $Source -DestinationPath $Destination -Force -ErrorAction Stop
            return
        } catch {
            if ($attempt -eq 5) {
                throw
            }
            Start-Sleep -Milliseconds (500 * $attempt)
        }
    }
}

if (Test-Path -LiteralPath $Build) {
    Remove-PathIfExists -Path $Build
}
if (Test-Path -LiteralPath $PortableDir) {
    Remove-PathIfExists -Path $PortableDir
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
Compress-DirectoryWithRetry -Source $BuiltDir -Destination $ZipPath
Write-Host "Portable zip created: $ZipPath"
Write-Host "External tools are not bundled. The app downloads yt-dlp and ffmpeg into %APPDATA%\YtDlpWebUi\bin."
