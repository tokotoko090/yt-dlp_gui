from pathlib import Path

from src.core.downloader import DownloadProcess, _merged_output_path, _parse_progress
from src.core.jobs import DownloadJob


def test_parse_download_percent_progress() -> None:
    event = _parse_progress("[download]  42.5% of 101.00MiB at 2.00MiB/s ETA 00:10")
    assert event.percent == 42.5
    assert event.speed == "2.00MiB/s"
    assert event.eta == "00:10"
    assert event.status == "ダウンロード中"
    assert not event.indeterminate


def test_parse_merger_as_indeterminate_progress() -> None:
    event = _parse_progress("[Merger] Merging formats into \"sample.mp4\"")
    assert event.percent is None
    assert event.status == "映像と音声を結合中"
    assert event.indeterminate


def test_parse_video_convertor_as_indeterminate_progress() -> None:
    event = _parse_progress("[VideoConvertor] Converting video from webm to mp4")
    assert event.status == "mp4へ変換中"
    assert event.indeterminate


def test_parse_chrome_cookie_database_copy_error() -> None:
    event = _parse_progress("ERROR: Could not copy Chrome cookie database.")
    assert event.status == "Chrome Cookieを読み込めません"
    assert "Cookieファイル" in event.line
    assert event.indeterminate


def test_fallback_merge_output_path_removes_format_suffix() -> None:
    path = _merged_output_path(Path("C:/Downloads/sample [id].f313.webm"), "313", "webm")
    assert path == Path("C:/Downloads/sample [id].webm")


def test_finalize_audio_output_removes_audio_source_suffix(tmp_path: Path) -> None:
    source = tmp_path / "sample.audio-source.m4a"
    source.write_bytes(b"audio")
    job = DownloadJob(
        url="https://example.com",
        output_dir=str(tmp_path),
        mode="audio",
        container="m4a",
        quality="最高",
        video_codec="自動",
        audio_codec="auto",
        playlist=False,
        subtitles=False,
        thumbnail=False,
        metadata=False,
        cookies_path="",
        retry_count=1,
    )
    process = DownloadProcess(job, lambda event: None)

    process._finalize_audio_output()

    assert not source.exists()
    assert (tmp_path / "sample.m4a").read_bytes() == b"audio"
