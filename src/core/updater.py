from __future__ import annotations

import subprocess

from PySide6.QtCore import QObject, Signal, Slot

from src.core.paths import vendor_path


class YtDlpUpdater(QObject):
    line = Signal(str)
    finished = Signal(bool, str)

    @Slot()
    def check_version(self) -> None:
        ytdlp = vendor_path("yt-dlp.exe")
        if not ytdlp.exists():
            self.finished.emit(False, f"yt-dlp.exe が見つかりません: {ytdlp}")
            return
        try:
            result = subprocess.run(
                [str(ytdlp), "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        except OSError as exc:
            self.finished.emit(False, str(exc))
            return
        version = result.stdout.strip() or result.stderr.strip()
        self.finished.emit(result.returncode == 0, f"yt-dlp version: {version}")

    @Slot()
    def update_stable(self) -> None:
        ytdlp = vendor_path("yt-dlp.exe")
        if not ytdlp.exists():
            self.finished.emit(False, f"yt-dlp.exe が見つかりません: {ytdlp}")
            return
        try:
            process = subprocess.Popen(
                [str(ytdlp), "--update-to", "stable"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            assert process.stdout is not None
            for output in process.stdout:
                self.line.emit(output.strip())
            code = process.wait()
        except OSError as exc:
            self.finished.emit(False, str(exc))
            return
        self.finished.emit(code == 0, "yt-dlpの更新が完了しました。" if code == 0 else f"更新に失敗しました。終了コード: {code}")
