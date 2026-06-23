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
