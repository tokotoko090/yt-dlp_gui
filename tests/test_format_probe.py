import json
import subprocess
from pathlib import Path

from src.core import format_probe
from src.core.format_probe import parse_format_data


def test_parse_split_video_and_audio_formats() -> None:
    result = parse_format_data({
        "title": "sample",
        "formats": [
            {
                "format_id": "137",
                "ext": "mp4",
                "height": 1080,
                "fps": 30,
                "vcodec": "avc1.640028",
                "acodec": "none",
                "tbr": 2500,
                "filesize_approx": 100000000,
            },
            {
                "format_id": "251",
                "ext": "webm",
                "vcodec": "none",
                "acodec": "opus",
                "abr": 160,
                "filesize_approx": 5000000,
            },
        ],
    })
    assert result.title == "sample"
    assert result.video_options[0].format_id == "137"
    assert result.video_options[0].height == 1080
    assert result.audio_options[0].format_id == "251"


def test_parse_webm_vp9_high_quality_format() -> None:
    result = parse_format_data({
        "formats": [
            {
                "format_id": "248",
                "ext": "webm",
                "height": 1080,
                "fps": 60,
                "vcodec": "vp9",
                "acodec": "none",
                "tbr": 3200,
            },
            {
                "format_id": "18",
                "ext": "mp4",
                "height": 360,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "tbr": 600,
            },
        ],
    })
    assert result.video_options[0].format_id == "248"
    assert result.muxed_options[0].format_id == "18"


def test_rich_video_formats_are_sorted_above_360p_muxed() -> None:
    result = parse_format_data({
        "formats": [
            {
                "format_id": "18",
                "ext": "mp4",
                "height": 360,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "tbr": 600,
            },
            {
                "format_id": "399",
                "ext": "mp4",
                "height": 1080,
                "fps": 30,
                "vcodec": "av01",
                "acodec": "none",
                "tbr": 1200,
            },
            {
                "format_id": "140",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a",
                "abr": 129,
            },
        ],
    })
    assert result.video_options[0].format_id == "399"
    assert result.audio_options[0].format_id == "140"
    assert result.muxed_options[0].format_id == "18"


def test_parse_thumbnail_url_from_top_level_thumbnail() -> None:
    result = parse_format_data({
        "title": "sample",
        "thumbnail": "https://img.example/thumb.jpg",
        "formats": [],
    })

    assert result.thumbnail_url == "https://img.example/thumb.jpg"


def test_parse_thumbnail_url_from_thumbnail_list() -> None:
    result = parse_format_data({
        "title": "sample",
        "thumbnails": [
            {"url": "https://img.example/small.jpg"},
            {"url": "https://img.example/large.webp"},
        ],
        "formats": [],
    })

    assert result.thumbnail_url == "https://img.example/large.webp"


def test_probe_format_data_can_use_chrome_browser_cookies(monkeypatch) -> None:
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"formats": []}), stderr="")

    monkeypatch.setattr(format_probe.subprocess, "run", fake_run)

    format_probe._probe_format_data(
        Path("vendor/yt-dlp.exe"),
        "https://youtu.be/example",
        use_browser_cookies=True,
    )

    assert "--cookies-from-browser" in captured["cmd"]
    assert "chrome:Profile 2" in captured["cmd"]
