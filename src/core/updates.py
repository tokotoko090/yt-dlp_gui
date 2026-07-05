from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from src.core.paths import app_root, ffmpeg_path, tools_dir, ytdlp_path
from src.core.version import APP_RELEASE_REPO, APP_VERSION, PORTABLE_ZIP_ASSET


YTDLP_DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
YTDLP_RELEASE_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
APP_RELEASE_API = f"https://api.github.com/repos/{APP_RELEASE_REPO}/releases/latest"

DownloadHook = Callable[[str, Path], None]
JsonHook = Callable[[str], dict[str, Any]]


@dataclass(slots=True)
class UpdateItem:
    name: str
    installed: bool
    current: str
    latest: str
    available: bool
    path: str
    message: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class UpdateActionResult:
    ok: bool
    status: str
    before_version: str
    after_version: str
    message: str
    path: str = ""
    lines: list[str] | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["lines"] = self.lines or []
        return payload


def creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def check_updates(fetch_json: JsonHook | None = None) -> dict[str, dict[str, object]]:
    return {
        "app": check_app_update(fetch_json).as_dict(),
        "yt_dlp": check_ytdlp_update(fetch_json).as_dict(),
        "ffmpeg": check_ffmpeg_update().as_dict(),
    }


def check_app_update(fetch_json: JsonHook | None = None) -> UpdateItem:
    release = _latest_release(APP_RELEASE_API, fetch_json)
    latest = str(release.get("tag_name") or "") if release else ""
    asset_url = _asset_url(release, PORTABLE_ZIP_ASSET) if release else ""
    available = bool(latest and _version_newer(latest, APP_VERSION) and asset_url)
    message = "最新版です。" if latest and not available else "本体更新があります。"
    if not latest:
        message = "本体の最新版確認に失敗しました。"
    elif latest and not asset_url:
        message = f"最新版 {latest} に portable zip が見つかりません。"
    return UpdateItem(
        name="yt-dlp-webUI",
        installed=True,
        current=APP_VERSION,
        latest=latest,
        available=available,
        path=str(_install_dir()),
        message=message,
    )


def check_ytdlp_update(fetch_json: JsonHook | None = None) -> UpdateItem:
    path = ytdlp_path()
    installed, current = get_ytdlp_version(path)
    release = _latest_release(YTDLP_RELEASE_API, fetch_json)
    latest = str(release.get("tag_name") or "") if release else ""
    available = bool((not installed) or (latest and current and _version_newer(latest, current)))
    if not installed:
        message = "yt-dlp が未導入です。"
    elif available:
        message = "yt-dlp 更新があります。"
    elif latest:
        message = "yt-dlp は最新版です。"
    else:
        message = "yt-dlp の最新版確認に失敗しました。"
    return UpdateItem("yt-dlp", installed, current if installed else "", latest, available, str(path), message)


def check_ffmpeg_update() -> UpdateItem:
    path = ffmpeg_path()
    installed, current = get_ffmpeg_version(path)
    latest = "latest essentials build"
    available = not installed
    message = "ffmpeg が未導入です。" if not installed else "ffmpeg は導入済みです。手動更新で最新版を再取得できます。"
    return UpdateItem("ffmpeg", installed, current if installed else "", latest, available, str(path), message)


def get_ytdlp_version(path: Path | None = None) -> tuple[bool, str]:
    executable = path or ytdlp_path()
    return _run_version(executable, ["--version"])


def get_ffmpeg_version(path: Path | None = None) -> tuple[bool, str]:
    executable = path or ffmpeg_path()
    ok, output = _run_version(executable, ["-version"])
    if not ok:
        return False, output
    first = output.splitlines()[0] if output else ""
    return True, first.replace("ffmpeg version ", "", 1).strip()


def install_or_update_ytdlp(download: DownloadHook | None = None) -> UpdateActionResult:
    before_ok, before = get_ytdlp_version()
    path = ytdlp_path()
    temp = tools_dir() / "yt-dlp.exe.download"
    try:
        _download_file(YTDLP_DOWNLOAD_URL, temp, download)
        if temp.stat().st_size <= 0:
            raise RuntimeError("downloaded yt-dlp.exe is empty")
        temp.replace(path)
    except Exception as exc:
        if temp.exists():
            temp.unlink(missing_ok=True)
        return UpdateActionResult(False, "failed", before if before_ok else "", "", f"yt-dlp の取得に失敗しました: {exc}", str(path))

    after_ok, after = get_ytdlp_version(path)
    if not after_ok:
        return UpdateActionResult(False, "failed", before if before_ok else "", "", f"取得後の yt-dlp を実行できません: {after}", str(path))
    status = "current" if before_ok and before == after else "updated"
    message = "yt-dlp は最新版です。" if status == "current" else "yt-dlp を更新しました。"
    return UpdateActionResult(True, status, before if before_ok else "", after, message, str(path))


def install_or_update_ffmpeg(download: DownloadHook | None = None) -> UpdateActionResult:
    before_ok, before = get_ffmpeg_version()
    path = ffmpeg_path()
    with tempfile.TemporaryDirectory(prefix="YtDlpWebUi-ffmpeg-") as temp_dir:
        temp_root = Path(temp_dir)
        zip_path = temp_root / "ffmpeg.zip"
        extract_dir = temp_root / "extract"
        try:
            _download_file(FFMPEG_DOWNLOAD_URL, zip_path, download)
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_dir)
            source = next(extract_dir.rglob("ffmpeg.exe"), None)
            if source is None:
                raise RuntimeError("ffmpeg.exe was not found in the downloaded archive")
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, path)
        except Exception as exc:
            return UpdateActionResult(False, "failed", before if before_ok else "", "", f"ffmpeg の取得に失敗しました: {exc}", str(path))

    after_ok, after = get_ffmpeg_version(path)
    if not after_ok:
        return UpdateActionResult(False, "failed", before if before_ok else "", "", f"取得後の ffmpeg を実行できません: {after}", str(path))
    status = "current" if before_ok and before == after else "updated"
    message = "ffmpeg は最新版です。" if status == "current" else "ffmpeg を更新しました。"
    return UpdateActionResult(True, status, before if before_ok else "", after, message, str(path))


def prepare_app_update(fetch_json: JsonHook | None = None, download: DownloadHook | None = None) -> UpdateActionResult:
    release = _latest_release(APP_RELEASE_API, fetch_json)
    latest = str(release.get("tag_name") or "") if release else ""
    asset_url = _asset_url(release, PORTABLE_ZIP_ASSET) if release else ""
    if not latest or not asset_url:
        return UpdateActionResult(False, "failed", APP_VERSION, "", "本体更新用の portable zip が見つかりません。", str(_install_dir()))
    if not _version_newer(latest, APP_VERSION):
        return UpdateActionResult(True, "current", APP_VERSION, APP_VERSION, "本体は最新版です。", str(_install_dir()))

    stage = Path(tempfile.mkdtemp(prefix="YtDlpWebUi-app-update-"))
    zip_path = stage / PORTABLE_ZIP_ASSET
    helper = stage / "apply-update.ps1"
    try:
        _download_file(asset_url, zip_path, download)
        if zip_path.stat().st_size <= 0:
            raise RuntimeError("downloaded portable zip is empty")
        helper.write_text(_helper_script(), encoding="utf-8")
    except Exception as exc:
        shutil.rmtree(stage, ignore_errors=True)
        return UpdateActionResult(False, "failed", APP_VERSION, "", f"本体更新の準備に失敗しました: {exc}", str(_install_dir()))

    return UpdateActionResult(
        True,
        "ready",
        APP_VERSION,
        latest,
        "本体更新を準備しました。アプリ終了後に置換します。",
        str(_install_dir()),
        [str(helper), str(zip_path)],
    )


def launch_app_update_helper(helper_path: str, zip_path: str) -> subprocess.Popen[bytes]:
    exe_name = Path(sys.executable).name if getattr(sys, "frozen", False) else ""
    helper = Path(helper_path)
    args = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(helper),
        "-InstallDir",
        str(_install_dir()),
        "-ZipPath",
        zip_path,
        "-CurrentPid",
        str(os.getpid()),
    ]
    if exe_name:
        args.extend(["-ExeName", exe_name])
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
        cwd=str(helper.parent),
    )


def _run_version(executable: Path, args: list[str]) -> tuple[bool, str]:
    if not executable.exists():
        return False, f"not found: {executable}"
    try:
        completed = subprocess.run(
            [str(executable), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags(),
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (completed.stdout.strip() or completed.stderr.strip()).strip()
    if completed.returncode != 0:
        return False, output or f"version command failed: {completed.returncode}"
    return True, output


def _latest_release(url: str, fetch_json: JsonHook | None = None) -> dict[str, Any]:
    try:
        return (fetch_json or _fetch_json)(url)
    except Exception:
        return {}


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "YtDlpWebUi"})
    with urllib.request.urlopen(request, timeout=12) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _download_file(url: str, destination: Path, download: DownloadHook | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if download:
        download(url, destination)
        return
    request = urllib.request.Request(url, headers={"User-Agent": "YtDlpWebUi"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _asset_url(release: dict[str, Any], asset_name: str) -> str:
    assets = release.get("assets") or []
    if not isinstance(assets, list):
        return ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        if name == asset_name or (name.endswith(".zip") and "portable" in name.lower()):
            return str(asset.get("browser_download_url") or "")
    return ""


def _version_newer(latest: str, current: str) -> bool:
    latest_parts = _version_parts(latest)
    current_parts = _version_parts(current)
    if latest_parts and current_parts:
        return latest_parts > current_parts
    return _clean_version(latest) != _clean_version(current)


def _version_parts(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(item) for item in numbers[:4])


def _clean_version(value: str) -> str:
    return value.strip().lower().lstrip("v")


def _install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return app_root()


def _helper_script() -> str:
    return r'''
param(
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [Parameter(Mandatory=$true)][string]$ZipPath,
    [Parameter(Mandatory=$true)][int]$CurrentPid,
    [string]$ExeName = ""
)
$ErrorActionPreference = "Stop"
$install = Resolve-Path -LiteralPath $InstallDir
$parent = Split-Path -Parent $install
$name = Split-Path -Leaf $install
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$backup = Join-Path $parent "$name.backup.$stamp"
$extract = Join-Path ([System.IO.Path]::GetTempPath()) "YtDlpWebUi-extract-$stamp"
$log = Join-Path ([System.IO.Path]::GetTempPath()) "YtDlpWebUi-update-error.log"
function Invoke-WithRetry {
    param(
        [Parameter(Mandatory=$true)][scriptblock]$Action,
        [int]$Attempts = 20,
        [int]$DelayMilliseconds = 500
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            & $Action
            return
        } catch {
            if ($attempt -eq $Attempts) {
                throw
            }
            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }
}
try {
    try {
        Wait-Process -Id $CurrentPid -Timeout 120 -ErrorAction Stop
    } catch [Microsoft.PowerShell.Commands.ProcessCommandException] {
        throw
    } catch {
        throw "Current application process did not exit in time. Close yt-dlp Web UI and run the downloaded app again. Details: $($_.Exception.Message)"
    }
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $extract -Force
    $source = $extract
    $children = Get-ChildItem -LiteralPath $extract
    if ($children.Count -eq 1 -and $children[0].PSIsContainer) {
        $source = $children[0].FullName
    }
    Invoke-WithRetry -Action {
        Rename-Item -LiteralPath $install -NewName (Split-Path -Leaf $backup) -ErrorAction Stop
    }
    New-Item -ItemType Directory -Force -Path $install | Out-Null
    Invoke-WithRetry -Action {
        Copy-Item -LiteralPath (Join-Path $source '*') -Destination $install -Recurse -Force -ErrorAction Stop
    }
    if ($ExeName) {
        $exe = Join-Path $install $ExeName
        if (Test-Path -LiteralPath $exe) {
            Start-Process -FilePath $exe -WorkingDirectory $install
        }
    }
} catch {
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $install)) {
        Rename-Item -LiteralPath $backup -NewName $name
    }
    $_ | Out-String | Set-Content -LiteralPath $log -Encoding UTF8
    throw
} finally {
    Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
}
'''.strip()
