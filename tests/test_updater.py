from pathlib import Path

from src.core import updater


def test_update_with_versions_reports_current(monkeypatch) -> None:
    versions = iter([(True, "2026.06.01"), (True, "2026.06.01")])

    monkeypatch.setattr(updater, "get_ytdlp_version", lambda ytdlp=None: next(versions))
    monkeypatch.setattr(updater, "update_ytdlp_stable", lambda ytdlp=None, on_line=None: (True, "ok"))

    result = updater.update_ytdlp_with_versions(Path("yt-dlp.exe"))

    assert result.ok
    assert result.status == "current"
    assert result.before_version == "2026.06.01"
    assert result.after_version == "2026.06.01"
    assert result.message == "最新版です。"


def test_update_with_versions_reports_updated(monkeypatch) -> None:
    versions = iter([(True, "2026.06.01"), (True, "2026.06.20")])

    monkeypatch.setattr(updater, "get_ytdlp_version", lambda ytdlp=None: next(versions))
    monkeypatch.setattr(updater, "update_ytdlp_stable", lambda ytdlp=None, on_line=None: (True, "ok"))

    result = updater.update_ytdlp_with_versions(Path("yt-dlp.exe"))

    assert result.ok
    assert result.status == "updated"
    assert result.before_version == "2026.06.01"
    assert result.after_version == "2026.06.20"
    assert result.message == "更新しました。"


def test_update_with_versions_reports_failure(monkeypatch) -> None:
    monkeypatch.setattr(updater, "get_ytdlp_version", lambda ytdlp=None: (True, "2026.06.01"))
    monkeypatch.setattr(updater, "update_ytdlp_stable", lambda ytdlp=None, on_line=None: (False, "update failed"))

    result = updater.update_ytdlp_with_versions(Path("yt-dlp.exe"))

    assert not result.ok
    assert result.status == "failed"
    assert result.before_version == "2026.06.01"
    assert result.after_version == ""
    assert result.message == "update failed"
