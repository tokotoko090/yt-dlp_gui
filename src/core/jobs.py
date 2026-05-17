from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DownloadJob:
    url: str
    output_dir: str
    mode: str
    container: str
    quality: str
    video_codec: str
    audio_codec: str
    playlist: bool
    subtitles: bool
    thumbnail: bool
    metadata: bool
    cookies_path: str
    retry_count: int


@dataclass(slots=True)
class ProgressEvent:
    percent: float | None = None
    speed: str = ""
    eta: str = ""
    status: str = ""
    line: str = ""
