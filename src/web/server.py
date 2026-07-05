from __future__ import annotations

import json
import mimetypes
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import urllib.request
import uuid
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.core.config import AppConfig, ConfigStore
from src.core.format_probe import FormatProbeResult, probe_formats
from src.core.paths import app_root, vendor_path
from src.core.updater import update_ytdlp_with_versions
from src.web.manager import DownloadManager


STATIC_DIR = Path(__file__).resolve().parent / "static"
THUMBNAIL_CACHE_DIR = Path(tempfile.gettempdir()) / "YtDlpWebUi" / "thumbnail-cache"
MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024


class WebApp:
    def __init__(self) -> None:
        _clear_thumbnail_cache()
        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.manager = DownloadManager(self.config)
        self.server: ThreadingHTTPServer | None = None


def run_server(host: str = "127.0.0.1", port: int = 0, open_browser: bool = True) -> int:
    app = WebApp()
    server = ThreadingHTTPServer((host, _pick_port(host, port)), _handler(app))
    app.server = server
    url = f"http://{server.server_address[0]}:{server.server_address[1]}"
    print(f"yt-dlp Web UI: {url}", flush=True)
    if open_browser:
        _open_browser(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _handler(app: WebApp) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_file(_static_dir() / "index.html")
                return
            if parsed.path.startswith("/static/"):
                self._send_file(_static_dir() / parsed.path.removeprefix("/static/"))
                return
            if parsed.path.startswith("/api/thumbnail/"):
                self._send_thumbnail(parsed.path.removeprefix("/api/thumbnail/"))
                return
            if parsed.path == "/api/config":
                self._send_json(_config_payload(app.config))
                return
            if parsed.path == "/api/jobs":
                self._send_json({"jobs": app.manager.list_jobs()})
                return
            if parsed.path.startswith("/api/jobs/"):
                job_id = parsed.path.rsplit("/", 1)[-1]
                job = app.manager.get_job(job_id)
                if not job:
                    self._send_error(HTTPStatus.NOT_FOUND, "job not found")
                    return
                self._send_json({"job": job})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/probe":
                payload = self._read_json()
                url = str(payload.get("url") or "").strip()
                if not url:
                    self._send_error(HTTPStatus.BAD_REQUEST, "URL is required")
                    return
                try:
                    result = probe_formats(
                        vendor_path("yt-dlp.exe"),
                        url,
                        str(payload.get("cookies_path") or app.config.cookies_path),
                        bool(payload.get("use_browser_cookies")),
                    )
                    result.thumbnail_url = _cache_thumbnail(result.thumbnail_url)
                except Exception as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json({"result": _probe_payload(result)})
                return
            if parsed.path == "/api/downloads":
                payload = self._read_json()
                jobs = app.manager.submit_many(payload)
                self._save_config_from_payload(payload)
                self._send_json({"jobs": [asdict(job) for job in jobs]}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/download-batch":
                payload = self._read_json()
                items = payload.get("items") or []
                if not isinstance(items, list):
                    self._send_error(HTTPStatus.BAD_REQUEST, "items must be a list")
                    return
                jobs = app.manager.submit_batch(
                    [item for item in items if isinstance(item, dict)],
                    int(payload.get("parallel") or app.config.max_parallel_downloads),
                )
                if items:
                    first = items[0] if isinstance(items[0], dict) else {}
                    self._save_config_from_payload(first)
                self._send_json({"jobs": [asdict(job) for job in jobs]}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/select-output-dir":
                payload = self._read_json()
                selected = _select_output_dir(str(payload.get("initial_dir") or app.config.download_dir))
                if not selected:
                    self._send_json({"cancelled": True, "path": ""})
                    return
                self._send_json({"cancelled": False, "path": selected})
                return
            if parsed.path == "/api/select-cookies-file":
                payload = self._read_json()
                selected = _select_cookies_file(str(payload.get("initial_path") or app.config.cookies_path))
                if not selected:
                    self._send_json({"cancelled": True, "path": ""})
                    return
                self._send_json({"cancelled": False, "path": selected})
                return
            if parsed.path == "/api/yt-dlp/update":
                result = update_ytdlp_with_versions()
                payload = result.as_dict()
                if not result.ok:
                    payload["error"] = result.message
                status = HTTPStatus.OK if result.ok else HTTPStatus.INTERNAL_SERVER_ERROR
                self._send_json(payload, status=status)
                return
            if parsed.path == "/api/shutdown":
                payload = self._read_json()
                force = bool(payload.get("force"))
                if app.manager.has_active_jobs() and not force:
                    self._send_error(HTTPStatus.CONFLICT, "active jobs")
                    return
                if force:
                    app.manager.cancel_all()
                self._send_json({"ok": True})
                if app.server:
                    threading.Thread(target=app.server.shutdown, daemon=True).start()
                return
            if parsed.path.endswith("/cancel") and parsed.path.startswith("/api/jobs/"):
                job_id = parsed.path.split("/")[-2]
                if not app.manager.cancel(job_id):
                    self._send_error(HTTPStatus.NOT_FOUND, "job not found")
                    return
                self._send_json({"ok": True})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not found")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            return data if isinstance(data, dict) else {}

        def _save_config_from_payload(self, payload: dict[str, Any]) -> None:
            app.config = AppConfig(
                download_dir=str(payload.get("output_dir") or app.config.download_dir),
                default_container=str(payload.get("container") or app.config.default_container),
                default_mode=str(payload.get("mode") or app.config.default_mode),
                video_codec_preference=str(payload.get("video_codec") or app.config.video_codec_preference),
                audio_codec=str(payload.get("audio_codec") or app.config.audio_codec),
                max_parallel_downloads=int(payload.get("parallel") or app.config.max_parallel_downloads),
                retry_count=int(payload.get("retry_count") or app.config.retry_count),
                cookies_path=str(payload.get("cookies_path") or app.config.cookies_path),
                history_limit=app.config.history_limit,
            )
            app.config_store.save(app.config)

        def _send_file(self, path: Path) -> None:
            static_dir = _static_dir().resolve()
            try:
                resolved = path.resolve()
                resolved.relative_to(static_dir)
            except ValueError:
                self._send_error(HTTPStatus.FORBIDDEN, "forbidden")
                return
            if not resolved.exists() or not resolved.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "not found")
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            body = resolved.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_thumbnail(self, name: str) -> None:
            cache_dir = THUMBNAIL_CACHE_DIR.resolve()
            try:
                resolved = (cache_dir / Path(name).name).resolve()
                resolved.relative_to(cache_dir)
            except ValueError:
                self._send_error(HTTPStatus.FORBIDDEN, "forbidden")
                return
            if not resolved.exists() or not resolved.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "not found")
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "image/jpeg"
            body = resolved.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"error": message}, status)

    return RequestHandler


def _config_payload(config: AppConfig) -> dict[str, Any]:
    audio_codec = config.audio_codec if config.audio_codec in {"auto", "aac", "opus", "mp3"} else "auto"
    return {
        "config": {**asdict(config), "audio_codec": audio_codec},
        "app_root": str(app_root()),
        "yt_dlp": str(vendor_path("yt-dlp.exe")),
        "ffmpeg": str(vendor_path("ffmpeg.exe")),
        "quality_options": ["最高", "4320p以下", "2160p以下", "1440p以下", "1080p以下", "720p以下", "480p以下", "360p以下"],
        "video_codecs": ["自動", "H.264優先", "VP9優先", "AV1優先"],
        "audio_codecs": ["auto", "aac", "opus", "mp3"],
        "video_encoders": _video_encoder_options(),
    }


def _probe_payload(result: FormatProbeResult) -> dict[str, Any]:
    return {
        "title": result.title,
        "thumbnail_url": result.thumbnail_url,
        "extractor_args": result.extractor_args,
        "video_options": [asdict(item) for item in result.video_options],
        "audio_options": [asdict(item) for item in result.audio_options],
        "muxed_options": [asdict(item) for item in result.muxed_options],
    }


def _clear_thumbnail_cache() -> None:
    if THUMBNAIL_CACHE_DIR.exists():
        shutil.rmtree(THUMBNAIL_CACHE_DIR, ignore_errors=True)
    THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_thumbnail(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read(MAX_THUMBNAIL_BYTES + 1)
    except Exception:
        return ""
    if not data or len(data) > MAX_THUMBNAIL_BYTES:
        return ""
    suffix = _thumbnail_suffix(parsed.path, content_type)
    name = f"{uuid.uuid4().hex}{suffix}"
    path = THUMBNAIL_CACHE_DIR / name
    try:
        path.write_bytes(data)
    except OSError:
        return ""
    return f"/api/thumbnail/{name}"


def _thumbnail_suffix(path: str, content_type: str) -> str:
    suffix = Path(urlparse(path).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return suffix
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
    return guessed if guessed in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def _pick_port(host: str, port: int) -> int:
    if port:
        return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _static_dir() -> Path:
    return STATIC_DIR


def _open_browser(url: str) -> None:
    chrome = _chrome_path()
    if chrome:
        subprocess.Popen([str(chrome), url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    webbrowser.open(url)


def _chrome_path() -> Path | None:
    candidates = [
        os.environ.get("CHROME_PATH"),
        str(Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe"),
        str(Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe"),
        str(Path(os.environ.get("LocalAppData", "")) / "Google" / "Chrome" / "Application" / "chrome.exe"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _select_output_dir(initial_dir: str) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return ""

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            initialdir=initial_dir if Path(initial_dir).exists() else str(Path.home()),
            title="保存先フォルダを選択",
            mustexist=True,
            parent=root,
        )
    finally:
        root.destroy()
    return selected or ""


def _select_cookies_file(initial_path: str) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return ""

    initial = Path(initial_path)
    initial_dir = initial.parent if initial_path and initial.parent.exists() else Path.home()
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilename(
            initialdir=str(initial_dir),
            title="Cookieファイルを選択",
            filetypes=[
                ("Cookie files", "*.txt *.cookies"),
                ("All files", "*.*"),
            ],
            parent=root,
        )
    finally:
        root.destroy()
    return selected or ""


def _video_encoder_options() -> list[dict[str, str]]:
    return [
        {"value": "auto", "label": "自動"},
        {"value": "h264_nvenc", "label": "NVIDIA GPU"},
        {"value": "libx264", "label": "CPU"},
    ]


def _ffmpeg_has_encoder(name: str) -> bool:
    try:
        completed = subprocess.run(
            [str(vendor_path("ffmpeg.exe")), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return name in completed.stdout or name in completed.stderr
