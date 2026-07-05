from src.web.manager import ManagedJob, _title_from_download_line


def test_title_from_download_destination_removes_format_and_extension() -> None:
    job = ManagedJob(
        id="job",
        url="https://youtu.be/example",
        title="https://youtu.be/example",
        mode="video",
        container="mp4",
        video_format_id="137",
        audio_format_id="140",
    )

    title = _title_from_download_line('[download] Destination: C:\\Downloads\\Sample Video.f137.mp4', job)

    assert title == "Sample Video"


def test_title_from_download_line_keeps_existing_video_title() -> None:
    job = ManagedJob(
        id="job",
        url="https://youtu.be/example",
        title="Original Title",
        mode="video",
        container="mp4",
    )

    title = _title_from_download_line('[download] Destination: C:\\Downloads\\Other.mp4', job)

    assert title == ""


def test_create_job_keeps_thumbnail_url_in_list_payload() -> None:
    from src.core.config import AppConfig
    from src.web.manager import DownloadManager

    manager = DownloadManager(AppConfig())
    job = manager._create_job("https://youtu.be/example", {
        "title": "Example",
        "mode": "video",
        "container": "mp4",
        "thumbnail_url": "/api/thumbnail/example.jpg",
    })

    listed = manager.list_jobs()

    assert job.thumbnail_url == "/api/thumbnail/example.jpg"
    assert listed[0]["thumbnail_url"] == "/api/thumbnail/example.jpg"
