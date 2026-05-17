from __future__ import annotations

import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from src.core.command_builder import build_ytdlp_command
from src.core.jobs import DownloadJob, ProgressEvent
from src.core.paths import vendor_path


PROGRESS_RE = re.compile(
    r"\[download\]\s+(?P<percent>\d+(?:\.\d+)?)%.*?(?:at\s+(?P<speed>\S+))?.*?(?:ETA\s+(?P<eta>\S+))?"
)

POSTPROCESS_STATUS = {
    "[Merger]": "映像と音声を結合中",
    "[VideoConvertor]": "動画を変換中",
    "[ExtractAudio]": "音声を変換中",
    "[EmbedSubtitle]": "字幕を埋め込み中",
    "[EmbedThumbnail]": "サムネイルを埋め込み中",
    "[Metadata]": "メタデータを埋め込み中",
    "[MoveFiles]": "ファイルを保存中",
}


class Downloader(QObject):
    progress = Signal(object)
    finished = Signal(bool, str)

    def __init__(self, job: DownloadJob) -> None:
        super().__init__()
        self.job = job
        self._process: subprocess.Popen[str] | None = None

    @Slot()
    def run(self) -> None:
        ytdlp = vendor_path("yt-dlp.exe")
        ffmpeg = vendor_path("ffmpeg.exe")
        if not ytdlp.exists():
            self.finished.emit(False, f"yt-dlp.exe が見つかりません: {ytdlp}")
            return
        if not ffmpeg.exists():
            self.finished.emit(False, f"ffmpeg.exe が見つかりません: {ffmpeg}")
            return

        Path(self.job.output_dir).mkdir(parents=True, exist_ok=True)
        cmd = build_ytdlp_command(ytdlp, ffmpeg, self.job)
        self.progress.emit(ProgressEvent(status="開始", line=" ".join(cmd)))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            assert self._process.stdout is not None
            for line in self._process.stdout:
                clean = line.strip()
                self.progress.emit(_parse_progress(clean))
            code = self._process.wait()
        except OSError as exc:
            self.finished.emit(False, str(exc))
            return
        finally:
            self._process = None

        self.finished.emit(code == 0, "完了" if code == 0 else f"失敗しました。終了コード: {code}")

    def cancel(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()


def _parse_progress(line: str) -> ProgressEvent:
    match = PROGRESS_RE.search(line)
    if not match:
        for marker, status in POSTPROCESS_STATUS.items():
            if marker in line:
                return ProgressEvent(status=status, line=line, indeterminate=True)
        return ProgressEvent(line=line)
    return ProgressEvent(
        percent=float(match.group("percent")),
        speed=match.group("speed") or "",
        eta=match.group("eta") or "",
        status="ダウンロード中",
        line=line,
    )
