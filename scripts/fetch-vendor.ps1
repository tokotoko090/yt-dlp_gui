$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Vendor = Join-Path $Root "vendor"
$Temp = Join-Path $Vendor ".downloads"

New-Item -ItemType Directory -Force -Path $Vendor | Out-Null
New-Item -ItemType Directory -Force -Path $Temp | Out-Null

$YtDlp = Join-Path $Vendor "yt-dlp.exe"
$FfmpegZip = Join-Path $Temp "ffmpeg-release-essentials.zip"
$FfmpegExtract = Join-Path $Temp "ffmpeg"

Write-Host "Downloading yt-dlp.exe..."
Invoke-WebRequest `
    -Uri "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" `
    -OutFile $YtDlp

Write-Host "Downloading ffmpeg essentials build..."
Invoke-WebRequest `
    -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" `
    -OutFile $FfmpegZip

if (Test-Path $FfmpegExtract) {
    Remove-Item -LiteralPath $FfmpegExtract -Recurse -Force
}

Expand-Archive -LiteralPath $FfmpegZip -DestinationPath $FfmpegExtract -Force

$FfmpegExe = Get-ChildItem -Path $FfmpegExtract -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if (-not $FfmpegExe) {
    throw "ffmpeg.exe was not found in the downloaded archive."
}

Copy-Item -LiteralPath $FfmpegExe.FullName -Destination (Join-Path $Vendor "ffmpeg.exe") -Force

Write-Host "Done."
Write-Host "yt-dlp: $(Join-Path $Vendor 'yt-dlp.exe')"
Write-Host "ffmpeg: $(Join-Path $Vendor 'ffmpeg.exe')"
