from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.core.jobs import FormatOption
from src.core.paths import vendor_path


@dataclass(slots=True)
class FormatProbeResult:
    title: str
    video_options: list[FormatOption]
    audio_options: list[FormatOption]
    muxed_options: list[FormatOption]
    extractor_args: str = ""


class FormatProbeWorker(QObject):
    finished = Signal(bool, object, str)

    def __init__(self, url: str, cookies_path: str = "") -> None:
        super().__init__()
        self.url = url
        self.cookies_path = cookies_path

    @Slot()
    def run(self) -> None:
        ytdlp = vendor_path("yt-dlp.exe")
        if not ytdlp.exists():
            self.finished.emit(False, None, f"yt-dlp.exe が見つかりません: {ytdlp}")
            return
        try:
            result = probe_formats(ytdlp, self.url, self.cookies_path)
        except Exception as exc:
            self.finished.emit(False, None, str(exc))
            return
        self.finished.emit(True, result, "")


def probe_formats(ytdlp_path: Path, url: str, cookies_path: str = "") -> FormatProbeResult:
    default_data = _probe_format_data(ytdlp_path, url, cookies_path)
    default_result = parse_format_data(default_data)
    if not _is_youtube_url(url) or _has_rich_video_formats(default_result):
        return default_result

    enhanced_args = "youtube:player-client=all"
    enhanced_data = _probe_format_data(ytdlp_path, url, cookies_path, enhanced_args)
    enhanced_result = parse_format_data(enhanced_data)
    enhanced_result.extractor_args = enhanced_args
    return _better_result(default_result, enhanced_result)


def _probe_format_data(
    ytdlp_path: Path,
    url: str,
    cookies_path: str = "",
    extractor_args: str = "",
) -> dict[str, Any]:
    cmd = [str(ytdlp_path), "-J", "--no-playlist", url]
    if cookies_path:
        cmd[1:1] = ["--cookies", cookies_path]
    if extractor_args:
        cmd[1:1] = ["--extractor-args", extractor_args]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "フォーマット取得に失敗しました。"
        raise RuntimeError(message)
    return json.loads(completed.stdout)


def parse_format_json(raw_json: str) -> FormatProbeResult:
    data = json.loads(raw_json)
    return parse_format_data(data)


def _is_youtube_url(url: str) -> bool:
    lowered = url.lower()
    return "youtube.com" in lowered or "youtu.be" in lowered


def _has_rich_video_formats(result: FormatProbeResult) -> bool:
    return len(result.video_options) >= 2 or _max_height(result) > 360


def _better_result(first: FormatProbeResult, second: FormatProbeResult) -> FormatProbeResult:
    first_score = (_max_height(first), len(first.video_options), len(first.audio_options), len(first.muxed_options))
    second_score = (_max_height(second), len(second.video_options), len(second.audio_options), len(second.muxed_options))
    if second_score > first_score:
        return second
    return first


def _max_height(result: FormatProbeResult) -> int:
    heights = [item.height for item in result.video_options + result.muxed_options]
    return max(heights, default=0)


def parse_format_data(data: dict[str, Any]) -> FormatProbeResult:
    video_options: list[FormatOption] = []
    audio_options: list[FormatOption] = []
    muxed_options: list[FormatOption] = []

    for fmt in data.get("formats", []):
        option = _format_option(fmt)
        if not option:
            continue
        has_video = option.vcodec and option.vcodec != "none"
        has_audio = option.acodec and option.acodec != "none"
        if has_video and has_audio:
            muxed_options.append(option)
        elif has_video:
            video_options.append(option)
        elif has_audio:
            audio_options.append(option)

    video_options.sort(key=lambda item: (item.height, item.fps, item.bitrate), reverse=True)
    audio_options.sort(key=lambda item: (item.bitrate, item.filesize), reverse=True)
    muxed_options.sort(key=lambda item: (item.height, item.fps, item.bitrate), reverse=True)
    return FormatProbeResult(
        title=data.get("title") or "",
        video_options=video_options,
        audio_options=audio_options,
        muxed_options=muxed_options,
    )


def _format_option(fmt: dict[str, Any]) -> FormatOption | None:
    format_id = str(fmt.get("format_id") or "")
    if not format_id:
        return None
    ext = str(fmt.get("ext") or "")
    vcodec = str(fmt.get("vcodec") or "")
    acodec = str(fmt.get("acodec") or "")
    height = int(fmt.get("height") or 0)
    fps = float(fmt.get("fps") or 0)
    bitrate = float(fmt.get("tbr") or fmt.get("abr") or fmt.get("vbr") or 0)
    filesize = int(fmt.get("filesize") or fmt.get("filesize_approx") or 0)
    resolution = str(fmt.get("resolution") or "")
    if not resolution and height:
        resolution = f"{height}p"

    has_video = vcodec and vcodec != "none"
    has_audio = acodec and acodec != "none"
    if has_video and has_audio:
        kind = "muxed"
    elif has_video:
        kind = "video"
    elif has_audio:
        kind = "audio"
    else:
        return None

    label = _format_label(format_id, kind, ext, resolution, fps, vcodec, acodec, bitrate, filesize)
    return FormatOption(
        format_id=format_id,
        kind=kind,
        label=label,
        ext=ext,
        resolution=resolution,
        height=height,
        fps=fps,
        vcodec=vcodec,
        acodec=acodec,
        bitrate=bitrate,
        filesize=filesize,
    )


def _format_label(
    format_id: str,
    kind: str,
    ext: str,
    resolution: str,
    fps: float,
    vcodec: str,
    acodec: str,
    bitrate: float,
    filesize: int,
) -> str:
    parts = [format_id]
    if kind == "audio":
        parts.append("音声")
    if resolution:
        parts.append(resolution)
    if fps:
        parts.append(f"{fps:g}fps")
    if ext:
        parts.append(ext)
    if vcodec and vcodec != "none":
        parts.append(vcodec)
    if acodec and acodec != "none":
        parts.append(acodec)
    if bitrate:
        parts.append(f"{bitrate:g}kbps")
    if filesize:
        parts.append(_human_size(filesize))
    return " / ".join(parts)


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{size}B"
