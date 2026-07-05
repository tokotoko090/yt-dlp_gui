from pathlib import Path

from src.core import updater
from src.core.updates import UpdateActionResult


def test_update_with_versions_reports_current(monkeypatch) -> None:
    monkeypatch.setattr(
        updater,
        "install_or_update_ytdlp",
        lambda: UpdateActionResult(True, "current", "2026.06.01", "2026.06.01", "yt-dlp は最新版です。", "yt-dlp.exe"),
    )

    result = updater.update_ytdlp_with_versions()

    assert result.ok
    assert result.status == "current"
    assert result.before_version == "2026.06.01"
    assert result.after_version == "2026.06.01"


def test_update_with_versions_reports_updated(monkeypatch) -> None:
    monkeypatch.setattr(
        updater,
        "install_or_update_ytdlp",
        lambda: UpdateActionResult(True, "updated", "2026.06.01", "2026.06.20", "yt-dlp を更新しました。", "yt-dlp.exe"),
    )

    result = updater.update_ytdlp_with_versions()

    assert result.ok
    assert result.status == "updated"
    assert result.before_version == "2026.06.01"
    assert result.after_version == "2026.06.20"


def test_update_with_versions_reports_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        updater,
        "install_or_update_ytdlp",
        lambda: UpdateActionResult(False, "failed", "2026.06.01", "", "update failed", "yt-dlp.exe"),
    )

    result = updater.update_ytdlp_with_versions()

    assert not result.ok
    assert result.status == "failed"
    assert result.before_version == "2026.06.01"
    assert result.after_version == ""
    assert result.message == "update failed"

