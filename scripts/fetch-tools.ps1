$ErrorActionPreference = "Stop"

$Destination = Join-Path $env:APPDATA "YtDlpWebUi\bin"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

$YtDlp = Join-Path $Destination "yt-dlp.exe"
$Temp = Join-Path ([System.IO.Path]::GetTempPath()) "YtDlpWebUi-tools"
$FfmpegZip = Join-Path $Temp "ffmpeg-release-essentials.zip"
$FfmpegExtract = Join-Path $Temp "ffmpeg"

New-Item -ItemType Directory -Force -Path $Temp | Out-Null

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
Copy-Item -LiteralPath $FfmpegExe.FullName -Destination (Join-Path $Destination "ffmpeg.exe") -Force

Write-Host "Done."
Write-Host "yt-dlp: $YtDlp"
Write-Host "ffmpeg: $(Join-Path $Destination 'ffmpeg.exe')"
