from __future__ import annotations

from pathlib import Path

from src.core.jobs import DownloadJob


VIDEO_EXTENSIONS = {"mp4", "mkv", "webm"}
AUDIO_EXTENSIONS = {"mp3", "m4a", "opus", "wav"}


def build_ytdlp_command(ytdlp_path: Path, ffmpeg_path: Path, job: DownloadJob) -> list[str]:
    args = [
        str(ytdlp_path),
        "--newline",
        "--no-color",
        "--progress",
        "--retries",
        str(job.retry_count),
        "--ffmpeg-location",
        str(ffmpeg_path.parent),
        "-P",
        job.output_dir,
        "-o",
        "%(title).200B [%(id)s].%(ext)s",
    ]

    if not job.playlist:
        args.append("--no-playlist")

    if job.cookies_path:
        args.extend(["--cookies", job.cookies_path])

    if job.subtitles:
        args.extend(["--write-subs", "--write-auto-subs", "--sub-langs", "ja,en.*"])

    if job.thumbnail:
        args.append("--write-thumbnail")

    if job.metadata:
        args.append("--embed-metadata")
        args.append("--embed-thumbnail")

    if job.mode == "audio":
        codec = job.container if job.container in AUDIO_EXTENSIONS else "mp3"
        args.extend(["-x", "--audio-format", codec])
        if job.audio_codec != "auto":
            args.extend(["--postprocessor-args", f"ffmpeg:-c:a {job.audio_codec}"])
    else:
        args.extend(["--merge-output-format", _safe_video_container(job.container)])
        args.extend(["-f", _format_selector(job)])

    args.append(job.url)
    return args


def _safe_video_container(container: str) -> str:
    return container if container in VIDEO_EXTENSIONS else "mp4"


def _height_filter(quality: str) -> str:
    if quality == "1080p以下":
        return "[height<=1080]"
    if quality == "720p以下":
        return "[height<=720]"
    return ""


def _codec_filter(video_codec: str) -> str:
    if video_codec == "H.264優先":
        return "[vcodec^=avc1]"
    if video_codec == "VP9優先":
        return "[vcodec^=vp9]"
    if video_codec == "AV1優先":
        return "[vcodec^=av01]"
    return ""


def _format_selector(job: DownloadJob) -> str:
    height = _height_filter(job.quality)
    codec = _codec_filter(job.video_codec)
    if codec:
        preferred = f"bv*{height}{codec}+ba/b{height}{codec}"
        fallback = f"bv*{height}+ba/b{height}/best"
        return f"{preferred}/{fallback}"
    return f"bv*{height}+ba/b{height}/best"
