from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FormatOption:
    format_id: str
    kind: str
    label: str
    ext: str
    resolution: str = ""
    height: int = 0
    fps: float = 0
    vcodec: str = ""
    acodec: str = ""
    bitrate: float = 0
    filesize: int = 0


@dataclass(slots=True)
class SelectedFormat:
    video_format_id: str = ""
    audio_format_id: str = ""
    output_ext: str = ""
    needs_recode: bool = False

    @property
    def format_selector(self) -> str:
        if self.video_format_id and self.audio_format_id:
            return f"{self.video_format_id}+{self.audio_format_id}"
        return self.video_format_id or self.audio_format_id


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
    selected_format: SelectedFormat | None = None


@dataclass(slots=True)
class ProgressEvent:
    percent: float | None = None
    speed: str = ""
    eta: str = ""
    status: str = ""
    line: str = ""
