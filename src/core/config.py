from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from src.core.paths import user_data_dir


@dataclass(slots=True)
class AppConfig:
    download_dir: str = str(Path.home() / "Downloads")
    default_container: str = "mp4"
    default_mode: str = "video"
    video_codec_preference: str = "auto"
    audio_codec: str = "auto"
    max_parallel_downloads: int = 2
    retry_count: int = 2
    cookies_path: str = ""
    history_limit: int = 100


class ConfigStore:
    def __init__(self) -> None:
        self.path = user_data_dir() / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppConfig()
        defaults = asdict(AppConfig())
        defaults.update({k: v for k, v in data.items() if k in defaults})
        return AppConfig(**defaults)

    def save(self, config: AppConfig) -> None:
        self.path.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
