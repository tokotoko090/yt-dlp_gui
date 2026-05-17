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
