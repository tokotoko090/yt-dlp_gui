from pathlib import Path

from src.core.command_builder import build_ytdlp_command
from src.core.jobs import DownloadJob, SelectedFormat


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
    assert "bestvideo" in joined
    assert "bestaudio" in joined
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


def test_video_quality_limit_command() -> None:
    cmd = build_ytdlp_command(
        Path("vendor/yt-dlp.exe"),
        Path("vendor/ffmpeg.exe"),
        make_job(quality="2160p以下"),
    )
    joined = " ".join(cmd)
    assert "[height<=2160]" in joined


def test_mp4_prefers_split_1080p_capable_formats() -> None:
    cmd = build_ytdlp_command(
        Path("vendor/yt-dlp.exe"),
        Path("vendor/ffmpeg.exe"),
        make_job(container="mp4", quality="1080p以下", video_codec="自動"),
    )
    joined = " ".join(cmd)
    assert "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]" in joined
    assert "best[height<=1080]" in joined


def test_selected_video_and_audio_format_ids_are_used() -> None:
    cmd = build_ytdlp_command(
        Path("vendor/yt-dlp.exe"),
        Path("vendor/ffmpeg.exe"),
        make_job(selected_format=SelectedFormat(video_format_id="248", audio_format_id="251")),
    )
    joined = " ".join(cmd)
    assert "-f 248+251" in joined


def test_selected_webm_to_mp4_adds_recode() -> None:
    cmd = build_ytdlp_command(
        Path("vendor/yt-dlp.exe"),
        Path("vendor/ffmpeg.exe"),
        make_job(
            container="mp4",
            selected_format=SelectedFormat(
                video_format_id="248",
                audio_format_id="251",
                output_ext="mp4",
                needs_recode=True,
            ),
        ),
    )
    joined = " ".join(cmd)
    assert "-f 248+251" in joined
    assert "--recode-video mp4" in joined


def test_selected_format_extractor_args_are_used() -> None:
    cmd = build_ytdlp_command(
        Path("vendor/yt-dlp.exe"),
        Path("vendor/ffmpeg.exe"),
        make_job(
            selected_format=SelectedFormat(
                video_format_id="137",
                audio_format_id="140",
                extractor_args="youtube:player-client=all",
            ),
        ),
    )
    joined = " ".join(cmd)
    assert "--extractor-args youtube:player-client=all" in joined
    assert "-f 137+140" in joined
