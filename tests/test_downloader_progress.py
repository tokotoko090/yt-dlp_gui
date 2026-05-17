from src.core.downloader import _parse_progress


def test_parse_download_percent_progress() -> None:
    event = _parse_progress("[download]  42.5% of 101.00MiB at 2.00MiB/s ETA 00:10")
    assert event.percent == 42.5
    assert event.status == "ダウンロード中"
    assert not event.indeterminate


def test_parse_merger_as_indeterminate_progress() -> None:
    event = _parse_progress("[Merger] Merging formats into \"sample.mp4\"")
    assert event.percent is None
    assert event.status == "映像と音声を結合中"
    assert event.indeterminate


def test_parse_video_convertor_as_indeterminate_progress() -> None:
    event = _parse_progress("[VideoConvertor] Converting video from webm to mp4")
    assert event.status == "動画を変換中"
    assert event.indeterminate
