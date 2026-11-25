from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.verdict import build_json_summary
from src.ui.styles import TEXT_DIM
from src.ui.widgets import FindingsAndRecommendationsTab, KpiCard

if TYPE_CHECKING:
    from src.core.worker import AnalysisWorker

AUDIO_FILTER = "Audio Files (*.mp3 *.m4a *.m4b *.aac *.wav *.flac *.ogg *.opus);;All Files (*.*)"


class _LazyTabHost(QWidget):
    """Lightweight placeholder container until a plot tab is first opened."""

    def __init__(self, placeholder_text: str = "Loading plot…", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.widget: QWidget | None = None
        self.dirty: bool = False
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(placeholder_text)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px;")
        self._layout.addWidget(self._placeholder)

    def set_real_widget(self, widget: QWidget) -> None:
        if self._placeholder is not None:
            self._layout.removeWidget(self._placeholder)
            self._placeholder.deleteLater()
            self._placeholder = None
        self.widget = widget
        self._layout.addWidget(widget)


class MainWindow(QMainWindow):
    def __init__(self, initial_file: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("SPAudioTruth — Audio Quality, Spectrum & Transcode Auditor")
        self.resize(1340, 880)
        self.setAcceptDrops(True)

        self._current_file: str | None = None
        self._payload: dict | None = None
        self._worker: AnalysisWorker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Top Control Bar ---
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(14, 10, 14, 10)
        top_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        self.open_btn = QPushButton("Open Audio File…")
        self.open_btn.setObjectName("PrimaryBtn")
        self.open_btn.clicked.connect(self._choose_file)

        self.reanalyze_btn = QPushButton("Re-analyze")
        self.reanalyze_btn.setEnabled(False)
        self.reanalyze_btn.clicked.connect(self._reanalyze)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("DangerBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_analysis)

        self.export_btn = QPushButton("Export Report (PNG + JSON)")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_report)

        self.file_lbl = QLabel("Drag & drop an audio file (MP3, M4B, FLAC, WAV…) here or click \"Open Audio File…\"")
        self.file_lbl.setStyleSheet(f"color: {TEXT_DIM};")
        self.file_lbl.setWordWrap(True)

        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.reanalyze_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.file_lbl, 1)
        top_layout.addLayout(btn_row)

        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet(f"color: {TEXT_DIM};")
        prog_row.addWidget(self.progress_bar, 1)
        prog_row.addSpacing(10)
        prog_row.addWidget(self.status_lbl, 1)
        top_layout.addLayout(prog_row)

        root.addWidget(top_bar)

        # --- Main Content ---
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 10, 12, 12)
        content_layout.setSpacing(10)

        # Dashboard: 5 KPI Cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.card_verdict = KpiCard("Verdict")
        self.card_bitrate = KpiCard("Real Equivalent")
        self.card_cutoff = KpiCard("Effective Cutoff")
        self.card_stereo = KpiCard("Stereo / Channels")
        self.card_rec = KpiCard("Recommendation")
        for c in (self.card_verdict, self.card_bitrate, self.card_cutoff, self.card_stereo, self.card_rec):
            cards_row.addWidget(c, 1)
        content_layout.addLayout(cards_row)

        # Tabs (tabs 2-5 are lazily initialized on first open or export)
        self.tabs = QTabWidget()
        self.tab_findings = FindingsAndRecommendationsTab()
        self._host_psd = _LazyTabHost("Select this tab to render the aggregate spectrum…")
        self._host_spec = _LazyTabHost("Select this tab to render the spectrogram…")
        self._host_frames = _LazyTabHost("Select this tab to render frame & band charts…")
        self._host_segments = _LazyTabHost("Select this tab to render segment & stereo analysis…")

        self.tabs.addTab(self.tab_findings, "1. Findings & Recommendations")
        self.tabs.addTab(self._host_psd, "2. Aggregate Spectrum (PSD)")
        self.tabs.addTab(self._host_spec, "3. Spectrograms")
        self.tabs.addTab(self._host_frames, "4. Frames & Bands")
        self.tabs.addTab(self._host_segments, "5. Segments & Stereo")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        content_layout.addWidget(self.tabs, 1)
        root.addWidget(content, 1)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        if initial_file:
            self.start_analysis(initial_file)

    # --- Drag & Drop ---
    @staticmethod
    def _extract_dropped_file(mime_data) -> str | None:
        if mime_data is not None and mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if Path(path).is_file():
                        return path
        return None

    def eventFilter(self, watched, event) -> bool:
        etype = event.type()
        if etype in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            if isinstance(watched, QWidget) and watched.window() is self:
                local_file = self._extract_dropped_file(event.mimeData())
                if local_file:
                    if etype == QEvent.Type.Drop:
                        event.acceptProposedAction()
                        QTimer.singleShot(0, lambda p=local_file: self.start_analysis(p))
                    else:
                        event.acceptProposedAction()
                    return True
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._extract_dropped_file(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._extract_dropped_file(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        local_file = self._extract_dropped_file(event.mimeData())
        if local_file:
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda p=local_file: self.start_analysis(p))
            return
        event.ignore()

    # --- Actions ---
    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", AUDIO_FILTER)
        if path:
            self.start_analysis(path)

    def _reanalyze(self) -> None:
        if self._current_file:
            self.start_analysis(self._current_file)

    def _cancel_analysis(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self.status_lbl.setText("Cancelling analysis…")
            self.cancel_btn.setEnabled(False)

    def start_analysis(self, filepath: str) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Analysis in Progress", "Please wait for the current analysis to finish or cancel it.")
            return

        p = Path(filepath)
        if not p.is_file():
            QMessageBox.critical(self, "Error", f"File not found:\n{filepath}")
            return

        self._current_file = str(p)
        size_mb = p.stat().st_size / (1024.0 * 1024.0)
        self.file_lbl.setText(f"<b>{p.name}</b> ({size_mb:.1f} MB) — {p}")

        self._set_busy(True)
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Starting analysis…")

        from src.core.worker import AnalysisWorker

        self._worker = AnalysisWorker(str(p), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_result.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.open_btn.setEnabled(not busy)
        self.reanalyze_btn.setEnabled((not busy) and (self._current_file is not None))
        self.cancel_btn.setEnabled(busy)
        self.export_btn.setEnabled((not busy) and (self._payload is not None))

    def _on_progress(self, pct: int, msg: str) -> None:
        self.progress_bar.setValue(pct)
        self.status_lbl.setText(msg)

    def _on_finished(self, payload: dict) -> None:
        self._payload = payload
        self._set_busy(False)
        analysis = payload["analysis"]
        verdict = payload["verdict"]
        recs = payload["recommendations"]

        size_mb = analysis["file_size_bytes"] / (1024.0 * 1024.0)
        self.file_lbl.setText(
            f"<b>{analysis['file_name']}</b> | {size_mb:.1f} MB | {analysis['duration_hms']} — {analysis['file']}"
        )

        # Update 5 KPI cards
        self.card_verdict.set_data(
            verdict["status_title"],
            verdict["status_reason"],
            status=verdict["status_code"],
        )
        self.card_bitrate.set_data(
            verdict["equivalent_label"],
            f"Declared: {verdict['declared_bitrate_kbps']} kbps"
            + (f" (~{verdict['waste_pct']:.0f}% wasted)" if verdict["waste_pct"] > 5 else ""),
        )
        self.card_cutoff.set_data(
            f"{verdict['effective_cutoff_hz'] / 1000.0:.1f} kHz" if verdict["effective_cutoff_hz"] else verdict["cutoff_desc"],
            f"Drop: {verdict['primary_drop_db']} dB | SR: {verdict['real_sample_rate_hz']} Hz"
            + (" (oversampled!)" if verdict["oversampling_detected"] else ""),
        )
        corr_str = f"corr: {verdict['avg_correlation']}" if verdict["avg_side_to_mid_db"] is not None else "1 ch"
        sm_str = f"Side/Mid: {verdict['avg_side_to_mid_db']} dB" if verdict["avg_side_to_mid_db"] is not None else "Mono"
        self.card_stereo.set_data(
            verdict["stereo_mode"],
            f"{sm_str} | {corr_str}",
        )
        self._update_rec_card(recs)

        # Update Tab 1 immediately; mark plot tabs dirty and update only the active one
        self.tab_findings.update_data(analysis, verdict, recs)
        for host in (self._host_psd, self._host_spec, self._host_frames, self._host_segments):
            host.dirty = True
        self._ensure_tab_ready(self.tabs.currentIndex())

        self.export_btn.setEnabled(True)
        self.status_lbl.setText("Done")

    def _on_tab_changed(self, index: int) -> None:
        self._ensure_tab_ready(index)

    def _ensure_tab_ready(self, index: int) -> None:
        if index < 1 or index > 4:
            return
        try:
            if index == 1:
                host = self._host_psd
                if host.widget is None:
                    from src.ui.plots import SummaryPsdTab
                    host.set_real_widget(SummaryPsdTab())
                if host.dirty and self._payload:
                    host.widget.update_data(self._payload["analysis"], self._payload["verdict"])
                    host.dirty = False
            elif index == 2:
                host = self._host_spec
                if host.widget is None:
                    from src.ui.plots import SpectrogramTab
                    host.set_real_widget(SpectrogramTab())
                if host.dirty and self._payload:
                    host.widget.update_data(self._payload["analysis"])
                    host.dirty = False
            elif index == 3:
                host = self._host_frames
                if host.widget is None:
                    from src.ui.plots import FramesAndBandsTab
                    host.set_real_widget(FramesAndBandsTab())
                if host.dirty and self._payload:
                    host.widget.update_data(self._payload["analysis"], self._payload["verdict"])
                    host.dirty = False
            elif index == 4:
                host = self._host_segments
                if host.widget is None:
                    from src.ui.plots import SegmentsStereoTab
                    host.set_real_widget(SegmentsStereoTab())
                if host.dirty and self._payload:
                    host.widget.update_data(self._payload["analysis"])
                    host.dirty = False
        except Exception as exc:
            QMessageBox.critical(self, "Tab Load Error", str(exc))

    def _update_rec_card(self, recs: dict) -> None:
        if not recs.get("should_reencode", False) or not recs.get("recommended_option"):
            self.card_rec.set_data(
                "Keep Original",
                "Re-encoding not required",
                status="clean",
            )
            return
        opt = recs["recommended_option"]
        self.card_rec.set_data(
            f"{opt['format']}",
            f"~{opt['estimated_mb']:.1f} MB (savings {opt['savings_pct']:+.0f}%)",
            status="suspect" if opt["savings_pct"] >= 10 else "",
        )

    def _on_failed(self, err_msg: str) -> None:
        self._set_busy(False)
        self.status_lbl.setText("Analysis failed")
        QMessageBox.critical(self, "Analysis Error", err_msg)

    def _on_cancelled(self) -> None:
        self._set_busy(False)
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Analysis cancelled")

    def _export_report(self) -> None:
        if not self._payload:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Select Folder to Save Report")
        if not out_dir:
            return
        out = Path(out_dir)
        summary = build_json_summary(
            self._payload["analysis"],
            self._payload["verdict"],
            self._payload["recommendations"],
        )
        json_path = out / "analysis_summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        self._ensure_tab_ready(1)
        self._ensure_tab_ready(2)
        self._ensure_tab_ready(3)
        self._host_psd.widget.export_png(out / "01_summary_psd.png")
        self._host_spec.widget.export_png(out / "02_spectrogram.png")
        self._host_frames.widget.export_png(out / "03_frames_and_bands.png")

        QMessageBox.information(
            self,
            "Report Saved",
            f"Report files (JSON + 3 PNGs) saved to:\n{out}",
        )
