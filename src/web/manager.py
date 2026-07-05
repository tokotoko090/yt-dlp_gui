from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.core.config import AppConfig
from src.core.downloader import DownloadProcess
from src.core.jobs import DownloadJob, ProgressEvent, SelectedFormat


MAX_LOG_LINES = 250


@dataclass(slots=True)
class ManagedJob:
    id: str
    url: str
    title: str
    mode: str
    container: str
    status: str = "queued"
    message: str = "待機中"
    percent: float | None = None
    speed: str = ""
    eta: str = ""
    detail: str = ""
    steps: list[str] = field(default_factory=list)
    current_step: str = ""
    failed_step: str = ""
    video_format_id: str = ""
    audio_format_id: str = ""
    thumbnail_url: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    log: list[str] = field(default_factory=list)


class DownloadManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._jobs: dict[str, ManagedJob] = {}
        self._processes: dict[str, DownloadProcess] = {}
        self._executor = ThreadPoolExecutor(max_workers=8)

    def submit_many(self, payload: dict[str, Any]) -> list[ManagedJob]:
        urls = [line.strip() for line in str(payload.get("urls", "")).splitlines() if line.strip()]
        parallel = _bounded_int(payload.get("parallel"), self.config.max_parallel_downloads, 1, 8)
        gate = threading.BoundedSemaphore(parallel)
        jobs = [self._create_job(url, payload) for url in urls]
        for job in jobs:
            self._executor.submit(self._run_job_with_gate, gate, job.id, payload)
        return jobs

    def submit_batch(self, payloads: list[dict[str, Any]], parallel: int) -> list[ManagedJob]:
        gate = threading.BoundedSemaphore(max(1, min(8, parallel)))
        jobs: list[ManagedJob] = []
        for payload in payloads:
            url = str(payload.get("urls") or payload.get("url") or "").splitlines()[0].strip()
            if not url:
                continue
            job = self._create_job(url, payload)
            jobs.append(job)
            self._executor.submit(self._run_job_with_gate, gate, job.id, payload)
        return jobs

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._job_dict(job, include_log=False) for job in sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return self._job_dict(job, include_log=True)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            process = self._processes.get(job_id)
            job = self._jobs.get(job_id)
            if not job:
                return False
            if process:
                process.cancel()
            elif job.status == "queued":
                job.status = "cancelled"
                job.message = "キャンセル済み"
            return True

    def has_active_jobs(self) -> bool:
        with self._lock:
            return any(job.status in {"queued", "running"} for job in self._jobs.values())

    def cancel_all(self) -> None:
        with self._lock:
            job_ids = list(self._jobs)
        for job_id in job_ids:
            self.cancel(job_id)

    def _create_job(self, url: str, payload: dict[str, Any]) -> ManagedJob:
        selected = payload.get("selected_format") or {}
        job = ManagedJob(
            id=uuid.uuid4().hex,
            url=url,
            title=str(payload.get("title") or url),
            mode=str(payload.get("mode") or "video"),
            container=str(payload.get("container") or "mp4"),
            steps=list(payload.get("steps") or _default_steps(payload)),
            video_format_id=str(selected.get("video_format_id") or ""),
            audio_format_id=str(selected.get("audio_format_id") or ""),
            thumbnail_url=str(payload.get("thumbnail_url") or ""),
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def _run_job_with_gate(self, gate: threading.BoundedSemaphore, job_id: str, payload: dict[str, Any]) -> None:
        with gate:
            self._run_job(job_id, payload)

    def _run_job(self, job_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            managed = self._jobs[job_id]
            if managed.status == "cancelled":
                return
            managed.status = "running"
            managed.message = "開始準備中"
            managed.started_at = time.time()

        selected = payload.get("selected_format") or {}
        selected_format = SelectedFormat(
            video_format_id=str(selected.get("video_format_id") or ""),
            audio_format_id=str(selected.get("audio_format_id") or ""),
            output_ext=str(selected.get("output_ext") or payload.get("container") or "mp4"),
            needs_recode=bool(selected.get("needs_recode")),
            extractor_args=str(selected.get("extractor_args") or payload.get("extractor_args") or ""),
        )
        if not selected_format.format_selector:
            selected_format = None

        download_job = DownloadJob(
            url=managed.url,
            output_dir=str(payload.get("output_dir") or self.config.download_dir),
            mode=managed.mode,
            container=managed.container,
            quality=str(payload.get("quality") or "最高"),
            video_codec=str(payload.get("video_codec") or "自動"),
            audio_codec=str(payload.get("audio_codec") or "auto"),
            video_encoder=str(payload.get("video_encoder") or "auto"),
            playlist=bool(payload.get("playlist")),
            subtitles=bool(payload.get("subtitles")),
            thumbnail=bool(payload.get("thumbnail")),
            metadata=bool(payload.get("metadata")),
            cookies_path=str(payload.get("cookies_path") or self.config.cookies_path),
            retry_count=int(payload.get("retry_count") or self.config.retry_count),
            artist_metadata=bool(payload.get("artist_metadata", True)),
            use_browser_cookies=bool(payload.get("use_browser_cookies")),
            selected_format=selected_format,
            extractor_args=str(payload.get("extractor_args") or ""),
        )
        process = DownloadProcess(download_job, lambda event: self._on_progress(job_id, event))
        with self._lock:
            self._processes[job_id] = process

        ok, message = process.run()
        with self._lock:
            managed = self._jobs[job_id]
            managed.status = "done" if ok else "failed"
            managed.message = message
            if not ok:
                managed.failed_step = managed.current_step or _infer_step_for_job(managed, managed.message, managed.detail)
            managed.percent = 100 if ok else managed.percent
            managed.finished_at = time.time()
            self._processes.pop(job_id, None)
            managed.log.append(message)

    def _on_progress(self, job_id: str, event: ProgressEvent) -> None:
        with self._lock:
            job = self._jobs[job_id]
            title = _title_from_download_line(event.line, job)
            if title:
                job.title = title
            if event.percent is not None:
                job.percent = event.percent
            if event.speed:
                job.speed = event.speed
            if event.eta:
                job.eta = event.eta
            if event.status:
                job.message = event.status
                job.current_step = _infer_step_for_job(job, event.status, event.line)
            if event.line:
                job.detail = event.line
                if not job.current_step:
                    job.current_step = _infer_step_for_job(job, job.message, event.line)
                job.log.append(event.line)
                if len(job.log) > MAX_LOG_LINES:
                    del job.log[:-MAX_LOG_LINES]

    def _job_dict(self, job: ManagedJob, include_log: bool) -> dict[str, Any]:
        data = asdict(job)
        if not include_log:
            data.pop("log", None)
        return data


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _default_steps(payload: dict[str, Any]) -> list[str]:
    if str(payload.get("mode") or "video") == "audio":
        steps = ["音声ダウンロード", "音声変換"]
        if payload.get("artist_metadata", True):
            steps.append("メタデータ埋め込み")
        return steps
    selected = payload.get("selected_format") or {}
    steps = ["映像ダウンロード", "音声ダウンロード"]
    steps.append("mp4変換" if selected.get("needs_recode") else "結合")
    if payload.get("artist_metadata", True):
        steps.append("メタデータ埋め込み")
    if payload.get("thumbnail") or payload.get("metadata"):
        steps.append("サムネイル処理")
    if payload.get("subtitles"):
        steps.append("字幕処理")
    return steps


def _infer_step(status: str, line: str, mode: str) -> str:
    text = f"{status} {line}"
    if "mp4" in text or "VideoConvertor" in text:
        return "mp4変換"
    if "結合" in text or "Merger" in text:
        return "結合"
    if "音声を抽出" in text or "ExtractAudio" in text:
        return "音声変換"
    if "サムネイル" in text or "Thumbnail" in text:
        return "サムネイル処理"
    if "字幕" in text or "Subtitle" in text:
        return "字幕処理"
    if "メタデータ" in text or "Metadata" in text:
        return "メタデータ埋め込み"
    if "download" in text.lower() or "ダウンロード" in text:
        return "音声ダウンロード" if mode == "audio" else "映像ダウンロード"
    return ""


def _infer_step_for_job(job: ManagedJob, status: str, line: str) -> str:
    text = f"{status} {line}"
    if job.mode == "video":
        if _mentions_format(text, job.audio_format_id):
            return "音声ダウンロード"
        if _mentions_format(text, job.video_format_id):
            return "映像ダウンロード"
    return _infer_step(status, line, job.mode)


def _mentions_format(text: str, format_id: str) -> bool:
    if not format_id:
        return False
    return f".f{format_id}." in text or f"format {format_id}" in text


def _title_from_download_line(line: str, job: ManagedJob) -> str:
    if not line or (job.title and job.title != job.url):
        return ""
    filename = ""
    if "[download] Destination:" in line:
        filename = line.split("[download] Destination:", 1)[1].strip()
    elif "[download]" in line and "has already been downloaded" in line:
        filename = line.split("[download]", 1)[1].split("has already been downloaded", 1)[0].strip()
    if not filename:
        return ""
    name = Path(filename.strip('"')).name
    for format_id in (job.video_format_id, job.audio_format_id):
        if format_id:
            name = name.replace(f".f{format_id}", "")
    suffix = Path(name).suffix
    if suffix:
        name = name[: -len(suffix)]
    return name.strip() or ""
