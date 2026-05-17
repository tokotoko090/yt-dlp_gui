from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QStyle,
    QSystemTrayIcon,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.config import AppConfig, ConfigStore
from src.core.downloader import Downloader
from src.core.format_probe import FormatProbeResult, FormatProbeWorker
from src.core.jobs import DownloadJob, ProgressEvent, SelectedFormat
from src.core.updater import YtDlpUpdater
from src.ui.format_dialog import FormatSelectionDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("yt-dlp GUI")
        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.download_thread: QThread | None = None
        self.downloader: Downloader | None = None
        self.pending_urls: list[str] = []
        self.total_urls = 0
        self.current_url = ""
        self.format_thread: QThread | None = None
        self.format_worker: FormatProbeWorker | None = None
        self.update_thread: QThread | None = None
        self.updater: YtDlpUpdater | None = None
        self.tray_icon = self._build_tray_icon()

        tabs = QTabWidget()
        tabs.addTab(self._build_download_tab(), "ダウンロード")
        tabs.addTab(self._build_settings_tab(), "設定")
        self.setCentralWidget(tabs)

    def _build_download_tab(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)

        self.url_edit = QTextEdit()
        self.url_edit.setPlaceholderText("URLを1行に1つ入力")
        self.url_edit.setMinimumHeight(110)
        layout.addWidget(self.url_edit)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit(self.config.download_dir)
        browse_btn = QPushButton("参照")
        browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(QLabel("保存先"))
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_btn)
        layout.addLayout(output_row)

        options = QGroupBox("オプション")
        grid = QGridLayout(options)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["動画", "音声のみ"])
        self.mode_combo.currentIndexChanged.connect(self._sync_extension_options)

        self.ext_combo = QComboBox()
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "最高",
            "4320p以下",
            "2160p以下",
            "1440p以下",
            "1080p以下",
            "720p以下",
            "480p以下",
            "360p以下",
        ])

        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(["自動", "H.264優先", "VP9優先", "AV1優先"])

        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(["自動", "aac", "opus", "mp3"])

        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, 4)
        self.parallel_spin.setValue(self.config.max_parallel_downloads)

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(self.config.retry_count)

        self.playlist_check = QCheckBox("プレイリストを含める")
        self.subtitles_check = QCheckBox("字幕を保存")
        self.thumbnail_check = QCheckBox("サムネイルを保存")
        self.metadata_check = QCheckBox("メタデータを埋め込む")

        grid.addWidget(QLabel("種別"), 0, 0)
        grid.addWidget(self.mode_combo, 0, 1)
        grid.addWidget(QLabel("拡張子"), 0, 2)
        grid.addWidget(self.ext_combo, 0, 3)
        grid.addWidget(QLabel("画質"), 1, 0)
        grid.addWidget(self.quality_combo, 1, 1)
        grid.addWidget(QLabel("動画コーデック"), 1, 2)
        grid.addWidget(self.video_codec_combo, 1, 3)
        grid.addWidget(QLabel("音声コーデック"), 2, 0)
        grid.addWidget(self.audio_codec_combo, 2, 1)
        grid.addWidget(QLabel("同時DL数"), 2, 2)
        grid.addWidget(self.parallel_spin, 2, 3)
        grid.addWidget(QLabel("リトライ"), 3, 0)
        grid.addWidget(self.retry_spin, 3, 1)
        grid.addWidget(self.playlist_check, 3, 2)
        grid.addWidget(self.subtitles_check, 3, 3)
        grid.addWidget(self.thumbnail_check, 4, 0)
        grid.addWidget(self.metadata_check, 4, 1)

        layout.addWidget(options)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status_label = QLabel("待機中")
        controls = QHBoxLayout()
        self.start_btn = QPushButton("開始")
        self.cancel_btn = QPushButton("キャンセル")
        self.cancel_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start_downloads)
        self.cancel_btn.clicked.connect(self._cancel_download)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.cancel_btn)
        controls.addWidget(self.status_label)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)

        layout.addWidget(self.progress)
        layout.addLayout(controls)
        layout.addWidget(self.log_edit)

        self._sync_extension_options()
        return root

    def _build_tray_icon(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        tray_icon = QSystemTrayIcon(icon, self)
        tray_icon.setToolTip("yt-dlp GUI")
        tray_icon.show()
        return tray_icon

    def _build_settings_tab(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)

        cookie_row = QHBoxLayout()
        self.cookies_edit = QLineEdit(self.config.cookies_path)
        cookie_btn = QPushButton("Cookieファイル選択")
        cookie_btn.clicked.connect(self._browse_cookies)
        cookie_row.addWidget(QLabel("Cookie"))
        cookie_row.addWidget(self.cookies_edit)
        cookie_row.addWidget(cookie_btn)

        version_btn = QPushButton("yt-dlp バージョン確認")
        update_btn = QPushButton("yt-dlp 安定版へ更新")
        save_btn = QPushButton("設定を保存")
        version_btn.clicked.connect(self._check_version)
        update_btn.clicked.connect(self._update_ytdlp)
        save_btn.clicked.connect(self._save_config)

        layout.addLayout(cookie_row)
        layout.addWidget(version_btn)
        layout.addWidget(update_btn)
        layout.addWidget(save_btn)
        layout.addStretch()
        return root

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "保存先を選択", self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    def _browse_cookies(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Cookieファイルを選択")
        if path:
            self.cookies_edit.setText(path)

    def _sync_extension_options(self) -> None:
        current = self.ext_combo.currentText()
        self.ext_combo.clear()
        if self.mode_combo.currentText() == "音声のみ":
            self.ext_combo.addItems(["mp3", "m4a", "opus", "wav"])
            self.video_codec_combo.setEnabled(False)
            self.quality_combo.setEnabled(False)
            self.audio_codec_combo.setEnabled(True)
        else:
            self.ext_combo.addItems(["mp4", "mkv", "webm"])
            self.video_codec_combo.setEnabled(True)
            self.quality_combo.setEnabled(True)
            self.audio_codec_combo.setEnabled(True)
        index = self.ext_combo.findText(current)
        if index >= 0:
            self.ext_combo.setCurrentIndex(index)

    def _start_downloads(self) -> None:
        urls = [line.strip() for line in self.url_edit.toPlainText().splitlines() if line.strip()]
        if not urls:
            QMessageBox.warning(self, "URL未入力", "URLを入力してください。")
            return
        if len(urls) > 1:
            self._append_log("複数URLは順番に処理します。")
        self._save_config()
        self.pending_urls = urls
        self.total_urls = len(urls)
        self._run_next_job()

    def _run_next_job(self) -> None:
        if not self.pending_urls:
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("すべて完了")
            self._notify_download_complete()
            return
        self.current_url = self.pending_urls.pop(0)
        self._fetch_formats(self.current_url)

    def _fetch_formats(self, url: str) -> None:
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("画質/音質候補を取得中")
        self._append_log(f"候補を取得中: {url}")
        self.format_thread = QThread()
        self.format_worker = FormatProbeWorker(url, self.cookies_edit.text().strip())
        self.format_worker.moveToThread(self.format_thread)
        self.format_thread.started.connect(self.format_worker.run)
        self.format_worker.finished.connect(self._on_formats_finished)
        self.format_worker.finished.connect(self.format_thread.quit)
        self.format_thread.finished.connect(self.format_thread.deleteLater)
        self.format_thread.start()

    def _on_formats_finished(self, ok: bool, result: object, message: str) -> None:
        if not ok or not isinstance(result, FormatProbeResult):
            self.pending_urls.clear()
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("候補取得失敗")
            self._append_log(f"候補取得に失敗しました: {message}")
            QMessageBox.warning(self, "候補取得失敗", f"画質/音質候補を取得できませんでした。\n\n{message}")
            return

        mode = "audio" if self.mode_combo.currentText() == "音声のみ" else "video"
        dialog = FormatSelectionDialog(result, mode, self.ext_combo.currentText(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.pending_urls.clear()
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("キャンセル")
            self._append_log("ダウンロードをキャンセルしました。")
            return
        selected = dialog.selected_format()
        if selected.needs_recode:
            self._append_log("高画質取得後にmp4へ変換します。")
        self._run_job(self.current_url, selected)

    def _run_job(self, url: str, selected_format: SelectedFormat | None) -> None:
        job = DownloadJob(
            url=url,
            output_dir=self.output_edit.text(),
            mode="audio" if self.mode_combo.currentText() == "音声のみ" else "video",
            container=self.ext_combo.currentText(),
            quality=self.quality_combo.currentText(),
            video_codec=self.video_codec_combo.currentText(),
            audio_codec=self.audio_codec_combo.currentText(),
            playlist=self.playlist_check.isChecked(),
            subtitles=self.subtitles_check.isChecked(),
            thumbnail=self.thumbnail_check.isChecked(),
            metadata=self.metadata_check.isChecked(),
            cookies_path=self.cookies_edit.text().strip(),
            retry_count=self.retry_spin.value(),
            selected_format=selected_format,
            extractor_args=selected_format.extractor_args if selected_format else "",
        )
        self.download_thread = QThread()
        self.downloader = Downloader(job)
        self.downloader.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.downloader.run)
        self.downloader.progress.connect(self._on_progress)
        self.downloader.finished.connect(self._on_download_finished)
        self.downloader.finished.connect(self.download_thread.quit)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.download_thread.start()

    def _cancel_download(self) -> None:
        if self.downloader:
            self.downloader.cancel()
            self._append_log("キャンセルを要求しました。")

    def _on_progress(self, event: ProgressEvent) -> None:
        if event.percent is not None:
            self.progress.setValue(int(event.percent))
        status = event.status or "処理中"
        if event.speed:
            status += f" / {event.speed}"
        if event.eta:
            status += f" / ETA {event.eta}"
        self.status_label.setText(status)
        if event.line:
            self._append_log(event.line)

    def _on_download_finished(self, ok: bool, message: str) -> None:
        self.status_label.setText(message)
        self._append_log(message)
        if not ok:
            self.pending_urls.clear()
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            QMessageBox.warning(self, "ダウンロード失敗", message)
            return
        self._run_next_job()

    def _check_version(self) -> None:
        self._run_updater("version")

    def _update_ytdlp(self) -> None:
        self._run_updater("update")

    def _run_updater(self, mode: str) -> None:
        self.update_thread = QThread()
        self.updater = YtDlpUpdater()
        self.updater.moveToThread(self.update_thread)
        if mode == "version":
            self.update_thread.started.connect(self.updater.check_version)
        else:
            self.update_thread.started.connect(self.updater.update_stable)
        self.updater.line.connect(self._append_log)
        self.updater.finished.connect(self._on_update_finished)
        self.updater.finished.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.start()

    def _on_update_finished(self, ok: bool, message: str) -> None:
        self._append_log(message)
        if ok:
            QMessageBox.information(self, "yt-dlp", message)
        else:
            QMessageBox.warning(self, "yt-dlp", message)

    def _notify_download_complete(self) -> None:
        message = f"{self.total_urls}件のダウンロードが完了しました。"
        if self.tray_icon:
            self.tray_icon.showMessage(
                "ダウンロード完了",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )
        QApplication.alert(self, 8000)
        self._append_log(message)

    def _save_config(self) -> None:
        self.config = AppConfig(
            download_dir=self.output_edit.text(),
            default_container=self.ext_combo.currentText(),
            default_mode="audio" if self.mode_combo.currentText() == "音声のみ" else "video",
            video_codec_preference=self.video_codec_combo.currentText(),
            audio_codec=self.audio_codec_combo.currentText(),
            max_parallel_downloads=self.parallel_spin.value(),
            retry_count=self.retry_spin.value(),
            cookies_path=self.cookies_edit.text().strip(),
        )
        self.config_store.save(self.config)
        self._append_log("設定を保存しました。")

    def _append_log(self, message: str) -> None:
        if message:
            self.log_edit.append(message)
