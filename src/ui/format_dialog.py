from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from src.core.format_probe import FormatProbeResult
from src.core.jobs import FormatOption, SelectedFormat


class FormatSelectionDialog(QDialog):
    def __init__(self, result: FormatProbeResult, mode: str, output_ext: str, parent=None) -> None:
        super().__init__(parent)
        self.result = result
        self.mode = mode
        self.output_ext = output_ext
        self.setWindowTitle("画質/音質オプション確認")
        self.resize(760, 240)

        layout = QVBoxLayout(self)
        title = result.title or "取得可能な形式"
        layout.addWidget(QLabel(title))

        form = QFormLayout()
        self.video_combo = QComboBox()
        self.audio_combo = QComboBox()

        if mode == "audio":
            self._fill_combo(self.audio_combo, result.audio_options + result.muxed_options)
            form.addRow("音声", self.audio_combo)
        else:
            video_options = result.video_options + result.muxed_options
            self._fill_combo(self.video_combo, video_options)
            self._fill_combo(self.audio_combo, result.audio_options)
            form.addRow("映像", self.video_combo)
            if result.audio_options:
                form.addRow("音声", self.audio_combo)
            else:
                self.audio_combo.setEnabled(False)
                form.addRow("音声", QLabel("選択した映像に含まれる音声を使用"))

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("この設定で開始")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("キャンセル")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_format(self) -> SelectedFormat:
        if self.mode == "audio":
            audio = self._current_option(self.audio_combo)
            return SelectedFormat(
                audio_format_id=audio.format_id if audio else "",
                output_ext=self.output_ext,
                extractor_args=self.result.extractor_args,
            )

        video = self._current_option(self.video_combo)
        audio = self._current_option(self.audio_combo)
        video_id = video.format_id if video else ""
        audio_id = audio.format_id if audio and video and video.kind != "muxed" else ""
        source_ext = video.ext if video else ""
        needs_recode = self.output_ext == "mp4" and source_ext not in {"", "mp4"}
        return SelectedFormat(
            video_format_id=video_id,
            audio_format_id=audio_id,
            output_ext=self.output_ext,
            needs_recode=needs_recode,
            extractor_args=self.result.extractor_args,
        )

    def _fill_combo(self, combo: QComboBox, options: list[FormatOption]) -> None:
        combo.clear()
        for option in options:
            combo.addItem(option.label, option)

    def _current_option(self, combo: QComboBox) -> FormatOption | None:
        data = combo.currentData()
        if isinstance(data, FormatOption):
            return data
        return None
