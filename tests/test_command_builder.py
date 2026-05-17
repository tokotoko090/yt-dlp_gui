from pathlib import Path

from src.core.command_builder import build_ytdlp_command
from src.core.jobs import DownloadJob


def make_job(**overrides: object) -> DownloadJob:
    data = {
        "url": "https://example.com/watch?v=test",
        "output_dir": "C:/Downloads",
        "mode": "video",
        "container": "mp4",
        "quality": "最高",
        "video_codec": "自動",
        "audio_codec": "自動",
        "playlist": False,
        "subtitles": False,
        "thumbnail": False,
        "metadata": False,
        "cookies_path": "",
        "retry_count": 2,
    }
    data.update(overrides)
    return DownloadJob(**data)


def test_video_mp4_h264_command() -> None:
    cmd = build_ytdlp_command(
        Path("vendor/yt-dlp.exe"),
        Path("vendor/ffmpeg.exe"),
        make_job(video_codec="H.264優先"),
    )
    joined = " ".join(cmd)
    assert "--merge-output-format mp4" in joined
    assert "[vcodec^=avc1]" in joined
    assert "--no-playlist" in cmd


def test_audio_mp3_command() -> None:
    cmd = build_ytdlp_command(
        Path("vendor/yt-dlp.exe"),
        Path("vendor/ffmpeg.exe"),
        make_job(mode="audio", container="mp3"),
    )
    joined = " ".join(cmd)
    assert "-x" in cmd
    assert "--audio-format mp3" in joined


def test_cookies_and_playlist_command() -> None:
    cmd = build_ytdlp_command(
        Path("vendor/yt-dlp.exe"),
        Path("vendor/ffmpeg.exe"),
        make_job(cookies_path="C:/cookies.txt", playlist=True),
    )
    assert "--cookies" in cmd
    assert "C:/cookies.txt" in cmd
    assert "--no-playlist" not in cmd
