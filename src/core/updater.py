from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from src.core.paths import vendor_path


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


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def get_ytdlp_version(ytdlp: Path | None = None) -> tuple[bool, str]:
    executable = ytdlp or vendor_path("yt-dlp.exe")
    if not executable.exists():
        return False, f"yt-dlp.exe が見つかりません: {executable}"
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
            check=False,
        )
    except OSError as exc:
        return False, str(exc)
    version = result.stdout.strip() or result.stderr.strip()
    if result.returncode != 0:
        return False, version or f"yt-dlp version check failed: {result.returncode}"
    return True, version


def check_ytdlp_version(ytdlp: Path | None = None) -> tuple[bool, str]:
    ok, version = get_ytdlp_version(ytdlp)
    if not ok:
        return False, version
    return True, f"yt-dlp version: {version}"


def update_ytdlp_stable(ytdlp: Path | None = None, on_line: LineCallback | None = None) -> tuple[bool, str]:
    executable = ytdlp or vendor_path("yt-dlp.exe")
    if not executable.exists():
        return False, f"yt-dlp.exe が見つかりません: {executable}"
    try:
        process = subprocess.Popen(
            [str(executable), "--update-to", "stable"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
        )
        assert process.stdout is not None
        for output in process.stdout:
            line = output.strip()
            if line and on_line:
                on_line(line)
        code = process.wait()
    except OSError as exc:
        return False, str(exc)
    if code == 0:
        return True, "yt-dlp の更新が完了しました。"
    return False, f"更新に失敗しました。終了コード: {code}"


def update_ytdlp_with_versions(ytdlp: Path | None = None) -> YtDlpUpdateResult:
    lines: list[str] = []
    before_ok, before_version = get_ytdlp_version(ytdlp)
    if not before_ok:
        return YtDlpUpdateResult(
            ok=False,
            status="failed",
            before_version="",
            after_version="",
            message=f"更新前のバージョン確認に失敗しました: {before_version}",
            lines=lines,
        )

    update_ok, update_message = update_ytdlp_stable(ytdlp, on_line=lines.append)
    if not update_ok:
        return YtDlpUpdateResult(
            ok=False,
            status="failed",
            before_version=before_version,
            after_version="",
            message=update_message,
            lines=lines,
        )

    after_ok, after_version = get_ytdlp_version(ytdlp)
    if not after_ok:
        return YtDlpUpdateResult(
            ok=False,
            status="failed",
            before_version=before_version,
            after_version="",
            message=f"更新後のバージョン確認に失敗しました: {after_version}",
            lines=lines,
        )

    if before_version == after_version:
        return YtDlpUpdateResult(
            ok=True,
            status="current",
            before_version=before_version,
            after_version=after_version,
            message="最新版です。",
            lines=lines,
        )
    return YtDlpUpdateResult(
        ok=True,
        status="updated",
        before_version=before_version,
        after_version=after_version,
        message="更新しました。",
        lines=lines,
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
