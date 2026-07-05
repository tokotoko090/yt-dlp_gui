from __future__ import annotations

from pathlib import Path

from src.core.jobs import DownloadJob


VIDEO_EXTENSIONS = {"mp4", "mkv", "webm"}
AUDIO_EXTENSIONS = {"mp3", "m4a", "opus", "wav"}
AUTO_CONTAINERS = {"", "auto", "自動"}


def build_ytdlp_command(ytdlp_path: Path, ffmpeg_path: Path, job: DownloadJob) -> list[str]:
    args = [
        str(ytdlp_path),
        "--ignore-config",
        "--newline",
        "--no-color",
        "--js-runtimes",
        "node",
        "--progress",
        "--retries",
        str(job.retry_count),
        "--ffmpeg-location",
        str(ffmpeg_path.parent),
        "-P",
        job.output_dir,
        "-o",
        _output_template(job),
    ]

    extractor_args = job.extractor_args
    if job.selected_format and job.selected_format.extractor_args:
        extractor_args = job.selected_format.extractor_args
    if extractor_args:
        args[1:1] = ["--extractor-args", extractor_args]

    if not job.playlist:
        args.append("--no-playlist")

    if job.cookies_path:
        args.extend(["--cookies", job.cookies_path])

    if job.subtitles and job.mode == "video":
        args.extend(["--write-subs", "--write-auto-subs", "--sub-langs", "ja,en.*"])

    if job.thumbnail and job.mode == "video":
        args.append("--write-thumbnail")

    if job.artist_metadata:
        args.extend([
            "--embed-metadata",
            "--parse-metadata",
            "%(uploader)s:%(meta_artist)s",
            "--postprocessor-args",
            "Metadata+ffmpeg_o:-metadata date= -metadata genre=",
        ])

    if job.metadata and job.mode == "video":
        args.append("--embed-thumbnail")

    if job.mode == "audio":
        codec = job.container if job.container in AUDIO_EXTENSIONS else "mp3"
        selector = "bestaudio/best"
        if job.selected_format and job.selected_format.audio_format_id:
            selector = f"{job.selected_format.audio_format_id}/bestaudio/best"
        args.extend(["-f", selector, "-x", "--audio-format", codec])
        if job.audio_codec not in {"", "auto", "自動"}:
            args.extend(["--postprocessor-args", f"ffmpeg:-c:a {job.audio_codec}"])
    else:
        video_container = _safe_video_container(job.container)
        if video_container:
            args.extend(["--merge-output-format", video_container])
        if job.selected_format and job.selected_format.format_selector:
            args.extend(["-f", job.selected_format.format_selector])
            if job.selected_format.needs_recode:
                args.extend(["--recode-video", job.selected_format.output_ext])
                args.extend(_video_recode_args(job))
        else:
            args.extend(["-f", _format_selector(job)])

    args.append(job.url)
    return args


def _safe_video_container(container: str) -> str:
    if container in AUTO_CONTAINERS:
        return ""
    return container if container in VIDEO_EXTENSIONS else "mp4"


def _output_template(job: DownloadJob) -> str:
    if job.mode == "audio":
        return "%(title).200B.audio-source.%(ext)s"
    return "%(title).200B.%(ext)s"


def _video_recode_args(job: DownloadJob) -> list[str]:
    encoder = str(getattr(job, "video_encoder", "") or "auto")
    if encoder in {"", "auto", "自動", "h264_nvenc", "NVIDIA NVENC"}:
        return [
            "--postprocessor-args",
            "VideoConvertor+ffmpeg_o:-c:v h264_nvenc -preset p5 -cq 23 -pix_fmt yuv420p -c:a aac -b:a 192k",
        ]
    if encoder in {"libx264", "CPU"}:
        return [
            "--postprocessor-args",
            "VideoConvertor+ffmpeg_o:-c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p -c:a aac -b:a 192k",
        ]
    return []


def _height_filter(quality: str) -> str:
    limit = _height_limit(quality)
    if limit:
        return f"[height<={limit}]"
    return ""


def _height_limit(quality: str) -> int | None:
    height_limits = {
        "4320p以下": 4320,
        "2160p以下": 2160,
        "1440p以下": 1440,
        "1080p以下": 1080,
        "720p以下": 720,
        "480p以下": 480,
        "360p以下": 360,
    }
    return height_limits.get(quality)


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
    container = _safe_video_container(job.container)

    if codec:
        preferred = f"bestvideo{height}{codec}+bestaudio"
        fallback = f"bestvideo{height}+bestaudio/best{height}/best"
        return f"{preferred}/{fallback}"

    if container == "mp4":
        preferred = f"bestvideo{height}[ext=mp4]+bestaudio[ext=m4a]"
        fallback = f"bestvideo{height}+bestaudio/best{height}/best"
        return f"{preferred}/{fallback}"

    if container == "webm":
        preferred = f"bestvideo{height}[ext=webm]+bestaudio[ext=webm]"
        fallback = f"bestvideo{height}+bestaudio/best{height}/best"
        return f"{preferred}/{fallback}"

    return f"bestvideo{height}+bestaudio/best{height}/best"
