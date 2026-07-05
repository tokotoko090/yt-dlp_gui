from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from src.core.command_builder import build_ytdlp_command
from src.core.jobs import DownloadJob, ProgressEvent
from src.core.paths import ffmpeg_path, ytdlp_path


ProgressCallback = Callable[[ProgressEvent], None]

PROGRESS_RE = re.compile(r"\[download\]\s+(?P<percent>\d+(?:\.\d+)?)%")
SPEED_RE = re.compile(r"\bat\s+(?P<speed>\S+)")
ETA_RE = re.compile(r"\bETA\s+(?P<eta>\S+)")

POSTPROCESS_STATUS = {
    "[Merger]": "映像と音声を結合中",
    "[VideoConvertor]": "mp4へ変換中",
    "[ExtractAudio]": "音声を抽出中",
    "[EmbedSubtitle]": "字幕を埋め込み中",
    "[EmbedThumbnail]": "サムネイルを埋め込み中",
    "[Metadata]": "メタデータを埋め込み中",
    "[MoveFiles]": "ファイルを保存中",
}


class DownloadProcess:
    def __init__(self, job: DownloadJob, on_progress: ProgressCallback) -> None:
        self.job = job
        self.on_progress = on_progress
        self._process: subprocess.Popen[str] | None = None

    def run(self) -> tuple[bool, str]:
        ytdlp = ytdlp_path()
        ffmpeg = ffmpeg_path()
        if not ytdlp.exists():
            return False, f"yt-dlp.exe が見つかりません: {ytdlp}"
        if not ffmpeg.exists():
            return False, f"ffmpeg.exe が見つかりません: {ffmpeg}"

        Path(self.job.output_dir).mkdir(parents=True, exist_ok=True)
        cmd = build_ytdlp_command(ytdlp, ffmpeg, self.job)
        self.on_progress(ProgressEvent(status="開始", line=" ".join(cmd)))

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
                self.on_progress(_parse_progress(line.strip()))
            code = self._process.wait()
        except OSError as exc:
            return False, str(exc)
        finally:
            self._process = None

        if code == 0:
            if self.job.mode == "audio":
                self._finalize_audio_output()
            return True, "完了"
        if self._try_fallback_merge(ffmpeg):
            return True, "完了"
        return False, f"失敗しました。終了コード: {code}"

    def cancel(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def _try_fallback_merge(self, ffmpeg_path: Path) -> bool:
        selected = self.job.selected_format
        if self.job.mode != "video" or not selected:
            return False
        if not selected.video_format_id or not selected.audio_format_id:
            return False

        output_dir = Path(self.job.output_dir)
        video = _newest_matching_part(output_dir, selected.video_format_id)
        audio = _newest_matching_part(output_dir, selected.audio_format_id)
        if not video or not audio:
            return False

        output = _merged_output_path(video, selected.video_format_id, self.job.container)
        if output.exists() and output.stat().st_size > 0:
            return True

        self.on_progress(
            ProgressEvent(
                status="映像と音声を結合中",
                line="ffmpeg -c copy でマージを再試行します",
                indeterminate=True,
            )
        )
        cmd = [
            str(ffmpeg_path),
            "-hide_banner",
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-c",
            "copy",
            str(output),
        ]
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
                if clean:
                    self.on_progress(ProgressEvent(status="映像と音声を結合中", line=clean, indeterminate=True))
            code = self._process.wait()
        except OSError as exc:
            self.on_progress(ProgressEvent(line=str(exc)))
            return False
        finally:
            self._process = None
        return code == 0 and output.exists() and output.stat().st_size > 0

    def _finalize_audio_output(self) -> None:
        output_dir = Path(self.job.output_dir)
        for source in sorted(output_dir.glob("*.audio-source.*"), key=lambda item: item.stat().st_mtime, reverse=True):
            target = source.with_name(source.name.replace(".audio-source", "", 1))
            if target.exists():
                target.unlink()
            source.rename(target)
            self.on_progress(ProgressEvent(status="メタデータを埋め込み中", line=f"音声ファイル名を確定しました: {target.name}"))
            break


def _parse_progress(line: str) -> ProgressEvent:
    if "Could not copy Chrome cookie database" in line:
        return ProgressEvent(
            status="Chrome Cookieを読み込めません",
            line="Chrome Cookieの直接読み込みに失敗しました。Chromeを閉じて再試行するか、Cookieファイルを指定してください。",
            indeterminate=True,
        )
    match = PROGRESS_RE.search(line)
    if not match:
        for marker, status in POSTPROCESS_STATUS.items():
            if marker in line:
                return ProgressEvent(status=status, line=line, indeterminate=True)
        return ProgressEvent(line=line)
    return ProgressEvent(
        percent=float(match.group("percent")),
        speed=_match_group(SPEED_RE, line, "speed"),
        eta=_match_group(ETA_RE, line, "eta"),
        status="ダウンロード中",
        line=line,
    )


def _newest_matching_part(output_dir: Path, format_id: str) -> Path | None:
    matches = list(output_dir.glob(f"*.f{format_id}.*"))
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def _merged_output_path(video_part: Path, video_format_id: str, container: str) -> Path:
    name = re.sub(rf"\.f{re.escape(video_format_id)}(?=\.[^.]+$)", "", video_part.name)
    path = video_part.with_name(name)
    if container not in {"", "auto", "自動"} and path.suffix.lower() != f".{container.lower()}":
        path = path.with_suffix(f".{container}")
    return path


def _match_group(pattern: re.Pattern[str], line: str, group: str) -> str:
    match = pattern.search(line)
    if not match:
        return ""
    return match.group(group) or ""

