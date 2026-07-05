from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "YtDlpWebUi"


def app_root() -> Path:
    return Path(__file__).resolve().parents[2]


def vendor_path(filename: str) -> Path:
    return app_root() / "vendor" / filename


def user_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        path = Path(base) / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tools_dir() -> Path:
    path = user_data_dir() / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tool_path(filename: str) -> Path:
    return tools_dir() / filename


def ytdlp_path() -> Path:
    return tool_path("yt-dlp.exe")


def ffmpeg_path() -> Path:
    return tool_path("ffmpeg.exe")
