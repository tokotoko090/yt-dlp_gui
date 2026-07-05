from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from src.core.updates import get_ytdlp_version as _get_ytdlp_version
from src.core.updates import install_or_update_ytdlp
from src.core.updates import ytdlp_path


LineCallback = Callable[[str], None]


@dataclass(slots=True)
class YtDlpUpdateResult:
    ok: bool
    status: str
    before_version: str
    after_version: str
    message: str
    lines: list[str]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def get_ytdlp_version(ytdlp: Path | None = None) -> tuple[bool, str]:
    return _get_ytdlp_version(ytdlp or ytdlp_path())


def check_ytdlp_version(ytdlp: Path | None = None) -> tuple[bool, str]:
    ok, version = get_ytdlp_version(ytdlp)
    if not ok:
        return False, version
    return True, f"yt-dlp version: {version}"


def update_ytdlp_stable(ytdlp: Path | None = None, on_line: LineCallback | None = None) -> tuple[bool, str]:
    result = install_or_update_ytdlp()
    if on_line:
        for line in result.lines or []:
            on_line(line)
    return result.ok, result.message


def update_ytdlp_with_versions(ytdlp: Path | None = None) -> YtDlpUpdateResult:
    if ytdlp is not None:
        before_ok, before_version = get_ytdlp_version(ytdlp)
        if not before_ok:
            return YtDlpUpdateResult(False, "failed", "", "", f"更新前のバージョン確認に失敗しました: {before_version}", [])
    result = install_or_update_ytdlp()
    return YtDlpUpdateResult(
        ok=result.ok,
        status=result.status,
        before_version=result.before_version,
        after_version=result.after_version,
        message=result.message,
        lines=result.lines or [],
    )


try:
    from PySide6.QtCore import QObject, Signal, Slot
except ImportError:
    QObject = object  # type: ignore[assignment,misc]
    Signal = None  # type: ignore[assignment]

    def Slot(*args, **kwargs):  # type: ignore[no-untyped-def]
        def decorator(func):  # type: ignore[no-untyped-def]
            return func

        return decorator


if Signal is not None:

    class YtDlpUpdater(QObject):
        line = Signal(str)
        finished = Signal(bool, str)

        @Slot()
        def check_version(self) -> None:
            ok, message = check_ytdlp_version()
            self.finished.emit(ok, message)

        @Slot()
        def update_stable(self) -> None:
            ok, message = update_ytdlp_stable(on_line=self.line.emit)
            self.finished.emit(ok, message)
