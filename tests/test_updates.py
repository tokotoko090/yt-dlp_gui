from __future__ import annotations

import io
import zipfile
from pathlib import Path

from src.core import updates


def test_check_updates_reports_missing_tools(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(updates, "ytdlp_path", lambda: tmp_path / "yt-dlp.exe")
    monkeypatch.setattr(updates, "ffmpeg_path", lambda: tmp_path / "ffmpeg.exe")
    monkeypatch.setattr(updates, "_run_version", lambda path, args: (False, f"not found: {path}"))

    payload = updates.check_updates(fetch_json=lambda url: {})

    assert not payload["yt_dlp"]["installed"]
    assert payload["yt_dlp"]["available"]
    assert not payload["ffmpeg"]["installed"]
    assert payload["ffmpeg"]["available"]


def test_check_ytdlp_update_detects_newer_release(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(updates, "ytdlp_path", lambda: tmp_path / "yt-dlp.exe")
    monkeypatch.setattr(updates, "get_ytdlp_version", lambda path=None: (True, "2026.06.01"))

    item = updates.check_ytdlp_update(fetch_json=lambda url: {"tag_name": "2026.06.20"})

    assert item.installed
    assert item.current == "2026.06.01"
    assert item.latest == "2026.06.20"
    assert item.available


def test_install_or_update_ytdlp_downloads_exe(monkeypatch, tmp_path) -> None:
    versions = iter([(False, "missing"), (True, "2026.06.20")])
    monkeypatch.setattr(updates, "tools_dir", lambda: tmp_path)
    monkeypatch.setattr(updates, "ytdlp_path", lambda: tmp_path / "yt-dlp.exe")
    monkeypatch.setattr(updates, "get_ytdlp_version", lambda path=None: next(versions))

    def download(url: str, destination: Path) -> None:
        destination.write_bytes(b"exe")

    result = updates.install_or_update_ytdlp(download=download)

    assert result.ok
    assert result.status == "updated"
    assert (tmp_path / "yt-dlp.exe").read_bytes() == b"exe"


def test_install_or_update_ytdlp_reports_download_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(updates, "tools_dir", lambda: tmp_path)
    monkeypatch.setattr(updates, "ytdlp_path", lambda: tmp_path / "yt-dlp.exe")
    monkeypatch.setattr(updates, "get_ytdlp_version", lambda path=None: (False, "missing"))

    def download(url: str, destination: Path) -> None:
        raise OSError("network down")

    result = updates.install_or_update_ytdlp(download=download)

    assert not result.ok
    assert result.status == "failed"
    assert "network down" in result.message


def test_install_or_update_ffmpeg_extracts_exe(monkeypatch, tmp_path) -> None:
    versions = iter([(False, "missing"), (True, "7.1 essentials")])
    monkeypatch.setattr(updates, "ffmpeg_path", lambda: tmp_path / "ffmpeg.exe")
    monkeypatch.setattr(updates, "get_ffmpeg_version", lambda path=None: next(versions))

    def download(url: str, destination: Path) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("ffmpeg/bin/ffmpeg.exe", b"ffmpeg")
        destination.write_bytes(buffer.getvalue())

    result = updates.install_or_update_ffmpeg(download=download)

    assert result.ok
    assert result.status == "updated"
    assert (tmp_path / "ffmpeg.exe").read_bytes() == b"ffmpeg"


def test_install_or_update_ffmpeg_fails_without_exe(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(updates, "ffmpeg_path", lambda: tmp_path / "ffmpeg.exe")
    monkeypatch.setattr(updates, "get_ffmpeg_version", lambda path=None: (False, "missing"))

    def download(url: str, destination: Path) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("readme.txt", "no exe")
        destination.write_bytes(buffer.getvalue())

    result = updates.install_or_update_ffmpeg(download=download)

    assert not result.ok
    assert result.status == "failed"
    assert "ffmpeg.exe" in result.message


def test_prepare_app_update_downloads_portable_zip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(updates, "APP_VERSION", "0.1.0")
    monkeypatch.setattr(updates, "_install_dir", lambda: tmp_path / "app")

    release = {
        "tag_name": "0.2.0",
        "assets": [{"name": updates.PORTABLE_ZIP_ASSET, "browser_download_url": "https://example.test/app.zip"}],
    }

    def download(url: str, destination: Path) -> None:
        destination.write_bytes(b"zip")

    result = updates.prepare_app_update(fetch_json=lambda url: release, download=download)

    assert result.ok
    assert result.status == "ready"
    assert result.after_version == "0.2.0"
    assert result.lines and result.lines[0].endswith("apply-update.ps1")
    assert result.lines[1].endswith(updates.PORTABLE_ZIP_ASSET)


def test_launch_app_update_helper_uses_stage_working_directory(monkeypatch, tmp_path) -> None:
    helper = tmp_path / "stage" / "apply-update.ps1"
    helper.parent.mkdir()
    helper.write_text("# helper", encoding="utf-8")
    zip_path = tmp_path / "stage" / updates.PORTABLE_ZIP_ASSET
    zip_path.write_bytes(b"zip")
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    captured = {}

    monkeypatch.setattr(updates, "_install_dir", lambda: app_dir)
    monkeypatch.setattr(updates, "creation_flags", lambda: 0)
    monkeypatch.setattr(updates.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updates.sys, "executable", str(app_dir / "yt-dlp-webUI.exe"))
    monkeypatch.setattr(updates.os, "getpid", lambda: 1234)

    class DummyProcess:
        pass

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return DummyProcess()

    monkeypatch.setattr(updates.subprocess, "Popen", fake_popen)

    process = updates.launch_app_update_helper(str(helper), str(zip_path))

    assert isinstance(process, DummyProcess)
    assert captured["kwargs"]["cwd"] == str(helper.parent)
    assert str(helper) in captured["args"]
    assert str(app_dir) in captured["args"]


def test_helper_script_retries_install_directory_replacement() -> None:
    script = updates._helper_script()

    assert "function Invoke-WithRetry" in script
    assert "Rename-Item -LiteralPath $install" in script
    assert "Copy-Item -LiteralPath (Join-Path $source '*')" in script
    assert "YtDlpWebUi-update-error.log" in script
