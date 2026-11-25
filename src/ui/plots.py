from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("QtAgg")
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.styles import (
    ACCENT,
    BG_DARK,
    BG_BLACK,
    BG_TABBAR,
    BORDER,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_WARNING,
    TEXT,
    TEXT_BRIGHT,
    TEXT_DIM,
)

REF_MARKERS = [
    (8.0, "8 kHz (~32-48k | 16k SR)"),
    (11.025, "11.025 kHz (~64k | 22k SR)"),
    (12.0, "12 kHz (~64-80k | 24k SR)"),
    (16.0, "16 kHz (~128k MP3/AAC)"),
    (18.0, "18 kHz (~192k)"),
    (20.0, "20 kHz (~256-320k)"),
]

DARK_BG = BG_DARK
DARK_AX = BG_BLACK
DARK_FG = TEXT
GRID_COLOR = "#3a3a3a"


def _style_axes(ax) -> None:
    ax.set_facecolor(DARK_AX)
    ax.tick_params(colors=DARK_FG, labelsize=8.5)
    ax.xaxis.label.set_color(DARK_FG)
    ax.yaxis.label.set_color(DARK_FG)
    ax.title.set_color(TEXT_BRIGHT)
    for spine in ax.spines.values():
        spine.set_color("#555555")
    ax.grid(True, color=GRID_COLOR, alpha=0.7, linewidth=0.7)


def _style_toolbar(toolbar: NavigationToolbar2QT) -> None:
    toolbar.setStyleSheet(
        f"QToolBar {{ background-color: {BG_TABBAR}; border: 1px solid #555555; border-radius: 3px; spacing: 3px; }}"
        f"QToolButton {{ background-color: transparent; color: {TEXT}; border: none; padding: 3px; border-radius: 3px; }}"
        f"QToolButton:hover {{ background-color: {ACCENT}; color: {TEXT_BRIGHT}; }}"
        f"QToolButton:checked {{ background-color: {ACCENT}; color: {TEXT_BRIGHT}; }}"
    )


class SummaryPsdTab(QWidget):
    """Tab 2: Interactive Aggregate Spectrum (PSD + Peak-Hold) with segment toggles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analysis: dict | None = None
        self._verdict: dict | None = None
        self._checkboxes: list[QCheckBox] = []
        self._segment_lines: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.seg_bar = QHBoxLayout()
        self.seg_bar.addWidget(QLabel("Segments:"))
        self.seg_bar.addStretch()
        layout.addLayout(self.seg_bar)

        self.figure = Figure(figsize=(10, 5.5), facecolor=DARK_BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        _style_toolbar(self.toolbar)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)

    def update_data(self, analysis: dict, verdict: dict) -> None:
        self._analysis = analysis
        self._verdict = verdict

        # Rebuild checkboxes
        for cb in self._checkboxes:
            self.seg_bar.removeWidget(cb)
            cb.deleteLater()
        self._checkboxes.clear()

        # Remove trailing stretch if present
        while self.seg_bar.count() > 1:
            item = self.seg_bar.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        for idx, seg in enumerate(analysis["segments"]):
            cb = QCheckBox(seg["display_name"])
            cb.setChecked(True)
            cb.stateChanged.connect(lambda _state, i=idx: self._toggle_line(i))
            self.seg_bar.addWidget(cb)
            self._checkboxes.append(cb)
        self.seg_bar.addStretch()

        self._redraw()

    def _toggle_line(self, idx: int) -> None:
        if 0 <= idx < len(self._segment_lines) and idx < len(self._checkboxes):
            self._segment_lines[idx].set_visible(self._checkboxes[idx].isChecked())
            self.canvas.draw_idle()

    def _redraw(self) -> None:
        if not self._analysis or not self._verdict:
            return
        segments = self._analysis["segments"]
        if not segments:
            return

        sr = int(self._analysis["ffprobe_stream"]["sample_rate"])
        freqs = segments[0]["spec"]["freqs"]
        all_p99 = np.max([s["spec"]["p99_db"] for s in segments], axis=0)
        all_mean = np.mean([s["spec"]["mean_db"] for s in segments], axis=0)
        noise_floor = float(np.median([s["spec"]["noise_floor_p99_db"] for s in segments]))
        cutoff_khz = float(self._verdict["effective_cutoff_hz"]) / 1000.0

        self.figure.clear()
        self._segment_lines.clear()
        ax = self.figure.add_subplot(111)
        _style_axes(ax)

        for cb, seg in zip(self._checkboxes, segments):
            (line,) = ax.plot(
                seg["spec"]["freqs"] / 1000.0,
                seg["spec"]["p99_db"],
                alpha=0.35,
                linewidth=1.0,
                label=f"p99: {seg['display_name']}",
            )
            line.set_visible(cb.isChecked())
            self._segment_lines.append(line)

        ax.plot(freqs / 1000.0, all_p99, color=STATUS_ERROR, linewidth=2.0, label="Max p99 (all segments)")
        ax.plot(freqs / 1000.0, all_mean, color=STATUS_OK, linewidth=1.8, label="Mean (active speech)")

        ax.axhline(noise_floor, color=TEXT_DIM, linestyle=":", linewidth=1.2, label=f"Noise floor ({noise_floor:.1f} dB)")

        nyq_khz = sr / 2000.0
        if 0.5 < cutoff_khz < nyq_khz:
            ax.axvspan(cutoff_khz - 0.25, cutoff_khz + 0.25, color=STATUS_ERROR, alpha=0.18)
            ax.axvline(cutoff_khz, color=STATUS_ERROR, linestyle="-", linewidth=1.4, label=f"Effective Cutoff (~{cutoff_khz:.1f} kHz)")

        y_top = float(np.max(all_p99)) - 2.0
        for ref, lbl in REF_MARKERS:
            if ref < nyq_khz:
                ax.axvline(ref, color="#777777", linestyle="--", linewidth=0.9, alpha=0.75)
                ax.text(ref + 0.15, y_top, lbl, rotation=90, va="top", fontsize=7.5, color=TEXT_DIM)

        ax.set_title(f"Aggregate Spectrum (PSD + Peak-Hold) — {self._analysis['file_name']}", fontsize=11, fontweight="bold")
        ax.set_xlabel("Frequency (kHz)")
        ax.set_ylabel("Power Spectral Density (dB)")
        ax.set_xlim(0, nyq_khz)
        ax.legend(loc="lower left", fontsize=7.5, ncol=2, facecolor=BG_TABBAR, edgecolor=BORDER, labelcolor=DARK_FG)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def export_png(self, out_path: Path) -> None:
        self.figure.savefig(out_path, dpi=150, facecolor=DARK_BG)


class SpectrogramTab(QWidget):
    """Tab 3: Dual-band Spectrogram (0-Nyquist & 6kHz-Nyquist) with contrast slider."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analysis: dict | None = None
        self._im1 = None
        self._im2 = None
        self._vmax: float = 0.0
        self._slider_timer = QTimer(self)
        self._slider_timer.setSingleShot(True)
        self._slider_timer.setInterval(45)
        self._slider_timer.timeout.connect(self._apply_contrast)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Segment:"))
        self.seg_combo = QComboBox()
        self.seg_combo.currentIndexChanged.connect(self._redraw)
        ctrl_row.addWidget(self.seg_combo, 1)

        ctrl_row.addSpacing(16)
        ctrl_row.addWidget(QLabel("Dynamic range (dB):"))
        self.dr_slider = QSlider(Qt.Orientation.Horizontal)
        self.dr_slider.setRange(60, 120)
        self.dr_slider.setValue(95)
        self.dr_slider.setFixedWidth(160)
        self.dr_val_lbl = QLabel("95 dB")
        self.dr_slider.valueChanged.connect(self._on_slider_changed)
        ctrl_row.addWidget(self.dr_slider)
        ctrl_row.addWidget(self.dr_val_lbl)
        layout.addLayout(ctrl_row)

        self.figure = Figure(figsize=(10, 6.5), facecolor=DARK_BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        _style_toolbar(self.toolbar)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)

    def _on_slider_changed(self, val: int) -> None:
        self.dr_val_lbl.setText(f"{val} dB")
        if self._im1 is not None and self._im2 is not None:
            self._slider_timer.start()

    def _apply_contrast(self) -> None:
        if self._im1 is None or self._im2 is None:
            return
        vmin = max(self._vmax - float(self.dr_slider.value()), -135.0)
        self._im1.set_clim(vmin, self._vmax)
        self._im2.set_clim(vmin, self._vmax)
        self.canvas.draw_idle()

    def update_data(self, analysis: dict) -> None:
        self._analysis = analysis
        self.seg_combo.blockSignals(True)
        self.seg_combo.clear()
        richest = analysis.get("richest_segment_label")
        richest_idx = 0
        for i, seg in enumerate(analysis["segments"]):
            tag = " ★ (max HF)" if seg["label"] == richest else ""
            self.seg_combo.addItem(f"{seg['display_name']} @ {seg['start_sec']:.0f}s{tag}")
            if seg["label"] == richest:
                richest_idx = i
        self.seg_combo.setCurrentIndex(richest_idx)
        self.seg_combo.blockSignals(False)
        self._redraw()

    def _redraw(self) -> None:
        if not self._analysis:
            return
        idx = self.seg_combo.currentIndex()
        segments = self._analysis["segments"]
        if idx < 0 or idx >= len(segments):
            return

        seg = segments[idx]
        spec = seg["spec"]
        freqs = spec["freqs"]
        times = spec["times"]
        mag_db = spec["mag_db"]
        sr = int(seg["sample_rate"])
        nyq_khz = sr / 2000.0

        self._vmax = float(np.percentile(mag_db, 99.5))
        vmin = max(self._vmax - float(self.dr_slider.value()), -135.0)
        extent = [float(times[0]), float(times[-1]), float(freqs[0]) / 1000.0, float(freqs[-1]) / 1000.0]

        self.figure.clear()
        gs = self.figure.add_gridspec(2, 2, width_ratios=[42, 1], wspace=0.025, hspace=0.28)
        ax1 = self.figure.add_subplot(gs[0, 0])
        ax2 = self.figure.add_subplot(gs[1, 0], sharex=ax1)
        cax = self.figure.add_subplot(gs[:, 1])
        _style_axes(ax1)
        _style_axes(ax2)

        self._im1 = ax1.imshow(
            mag_db,
            origin="lower",
            aspect="auto",
            extent=extent,
            cmap="inferno",
            vmin=vmin,
            vmax=self._vmax,
            interpolation="nearest",
        )
        ax1.set_title(f"Spectrogram: {seg['display_name']} ({seg['start_sec']:.0f}s)", fontsize=10.5, fontweight="bold")
        ax1.set_ylabel("Frequency (kHz)")
        ax1.set_ylim(0, nyq_khz)
        for ref, lbl in REF_MARKERS:
            if ref < nyq_khz:
                ax1.axhline(ref, color="cyan", linestyle="--", linewidth=0.8, alpha=0.65)
                ax1.text(times[0] + 0.3, ref + 0.25, lbl, color="cyan", fontsize=7.2)

        cbar = self.figure.colorbar(self._im1, cax=cax)
        cbar.set_label("Level (dB)", color=DARK_FG)
        cbar.ax.tick_params(axis="y", colors=DARK_FG)

        self._im2 = ax2.imshow(
            mag_db,
            origin="lower",
            aspect="auto",
            extent=extent,
            cmap="inferno",
            vmin=vmin,
            vmax=self._vmax,
            interpolation="nearest",
        )
        ax2.set_title("Upper Band Zoom (6 kHz – Nyquist)", fontsize=9.5)
        ax2.set_ylabel("Frequency (kHz)")
        ax2.set_xlabel("Time (s)")
        ax2.set_ylim(min(6.0, nyq_khz * 0.5), nyq_khz)
        for ref, lbl in REF_MARKERS:
            if 6.0 < ref < nyq_khz:
                ax2.axhline(ref, color="cyan", linestyle="--", linewidth=0.8, alpha=0.75)
                ax2.text(times[0] + 0.3, ref + 0.2, lbl, color="cyan", fontsize=7.2)

        self.figure.subplots_adjust(left=0.07, right=0.92, top=0.93, bottom=0.09)
        self.canvas.draw_idle()

    def export_png(self, out_path: Path) -> None:
        self.figure.savefig(out_path, dpi=150, facecolor=DARK_BG)


class FramesAndBandsTab(QWidget):
    """Tab 4: MP3 frame bitrate histogram, control edge drops, and Xing/LAME/ID3 info."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.figure = Figure(figsize=(10, 4.5), facecolor=DARK_BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        _style_toolbar(self.toolbar)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 3)

        self.info_box = QPlainTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setMaximumHeight(165)
        layout.addWidget(self.info_box, 1)

    def update_data(self, analysis: dict, verdict: dict) -> None:
        binary = analysis.get("binary_analysis") or {}
        br_counts = binary.get("sampled_bitrates_kbps") or {}
        edge_drops = verdict.get("max_edge_drops_db") or {}

        self.figure.clear()
        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)
        _style_axes(ax1)
        _style_axes(ax2)

        # Left: Bitrate histogram
        if br_counts:
            bitrates = [str(k) for k in sorted(br_counts.keys(), key=lambda x: int(x))]
            counts = [br_counts[k] for k in sorted(br_counts.keys(), key=lambda x: int(x))]
            ax1.bar(bitrates, counts, color=ACCENT, edgecolor=STATUS_OK, linewidth=0.8)
            mode_lbl = "VBR" if len(bitrates) > 1 else "CBR"
            ax1.set_title(f"Frame Bitrate Distribution ({mode_lbl})", fontsize=10, fontweight="bold")
            ax1.set_xlabel("Frame Bitrate (kbps)")
            ax1.set_ylabel("Frame Count (sampled)")
        else:
            ax1.text(0.5, 0.5, "Binary frame parsing\nis only available for MP3", ha="center", va="center", color=TEXT_DIM)
            ax1.set_title("Frame Bitrate Distribution", fontsize=10)

        # Right: Edge drops
        if edge_drops:
            labels = [k.replace("Hz", "") for k in edge_drops.keys()]
            vals = list(edge_drops.values())
            colors = [STATUS_ERROR if v >= 15.0 else (STATUS_WARNING if v >= 8.0 else STATUS_OK) for v in vals]
            ax2.bar(labels, vals, color=colors, edgecolor="#555555")
            ax2.axhline(15.0, color=STATUS_ERROR, linestyle="--", linewidth=1.0, label="Cutoff threshold (15 dB)")
            ax2.set_title("Energy Drops at Control Boundaries", fontsize=10, fontweight="bold")
            ax2.set_xlabel("Boundary (Hz)")
            ax2.set_ylabel("p99 Drop (dB)")
            ax2.legend(loc="upper right", fontsize=8, facecolor=BG_TABBAR, edgecolor=BORDER, labelcolor=DARK_FG)

        self.figure.tight_layout()
        self.canvas.draw_idle()

        # Text details
        xing = binary.get("xing_lame") or {}
        lame = xing.get("lame") or {}
        first = binary.get("first_frame") or {}
        tags = analysis["ffprobe_stream"].get("tags") or {}
        sat = analysis.get("saturation_test") or {}

        lines = [
            f"ID3v2 size: {binary.get('id3v2_size_bytes', 0)} bytes | First frame: {first or 'N/A'}",
            f"Xing/Info: {xing.get('tag', 'none')} | Frames: {xing.get('frames_count', 'N/A')} | VBR scale: {xing.get('vbr_scale', 'N/A')}",
            f"LAME/Lavc: encoder={lame.get('encoder_string', 'none')}, vbr_method={lame.get('vbr_method', 'none')}, lowpass_hz={lame.get('lowpass_hz', 'none')}",
            f"Sampled frame channel modes: {binary.get('sampled_channel_modes', {})}",
            f"Container tags: {tags}",
        ]
        if sat:
            lines.append(f"VBR saturation test (libmp3lame): {sat}")
        else:
            lines.append("VBR saturation test: skipped (libmp3lame not available in portable ffmpeg).")
        self.info_box.setPlainText("\n".join(lines))

    def export_png(self, out_path: Path) -> None:
        self.figure.savefig(out_path, dpi=150, facecolor=DARK_BG)


class SegmentsStereoTab(QWidget):
    """Tab 5: Per-segment table + Side/Mid and L/R correlation chart."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Segment", "Position (s)", "Cutoff (Hz)", "Noise Floor (dB)",
            "8–11 kHz (p99)", "12–16 kHz (p99)", "16–18 kHz (p99)",
            "Side/Mid (dB)", "L/R Corr. / Status",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        splitter.addWidget(self.table)

        plot_host = QWidget()
        p_layout = QVBoxLayout(plot_host)
        p_layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(figsize=(10, 3.2), facecolor=DARK_BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        _style_toolbar(self.toolbar)
        p_layout.addWidget(self.toolbar)
        p_layout.addWidget(self.canvas, 1)
        splitter.addWidget(plot_host)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    def update_data(self, analysis: dict) -> None:
        segments = analysis["segments"]
        self.table.setRowCount(len(segments))

        x_labels = []
        side_mids = []
        corrs = []

        for r, seg in enumerate(segments):
            spec = seg["spec"]
            st = seg["stereo"]
            bands = spec["band_stats"]
            e_8_11 = bands.get("8000-11025Hz", {}).get("p99_db", "—")
            e_12_16 = bands.get("12000-16000Hz", {}).get("p99_db", "—")
            e_16_18 = bands.get("16000-18000Hz", {}).get("p99_db", "—")

            sm = st.get("side_to_mid_db")
            corr = st.get("correlation", 1.0)
            st_lbl = "Mono" if not st.get("is_stereo") else ("Pseudo-Stereo" if st.get("pseudo_stereo") else "Stereo")

            vals = [
                seg["display_name"],
                f"{seg['start_sec']:.1f}",
                f"{spec['estimated_cutoff_p99_hz']:.0f}",
                f"{spec['noise_floor_p99_db']:.1f}",
                f"{e_8_11}",
                f"{e_12_16}",
                f"{e_16_18}",
                f"{sm:.2f}" if sm is not None else "—",
                f"{corr:.4f} ({st_lbl})",
            ]
            for c, val in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(val))

            x_labels.append(seg["display_name"])
            side_mids.append(sm if sm is not None else -100.0)
            corrs.append(corr)

        self.figure.clear()
        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)
        _style_axes(ax1)
        _style_axes(ax2)

        x = np.arange(len(x_labels))
        ax1.plot(x, side_mids, marker="o", color=STATUS_OK, linewidth=2.0)
        ax1.axhline(-40.0, color=STATUS_ERROR, linestyle="--", linewidth=1.0, label="Pseudo-stereo threshold (-40 dB)")
        ax1.set_title("Side/Mid Ratio by Segment", fontsize=10, fontweight="bold")
        ax1.set_ylabel("Side/Mid (dB)")
        ax1.set_xticks(x)
        ax1.set_xticklabels(x_labels, rotation=20, ha="right", fontsize=7.5)
        ax1.legend(loc="best", fontsize=8, facecolor=BG_TABBAR, edgecolor=BORDER, labelcolor=DARK_FG)

        ax2.plot(x, corrs, marker="s", color=ACCENT, linewidth=2.0)
        ax2.set_title("L/R Channel Correlation", fontsize=10, fontweight="bold")
        ax2.set_ylabel("Correlation (0..1)")
        ax2.set_ylim(-0.1, 1.05)
        ax2.set_xticks(x)
        ax2.set_xticklabels(x_labels, rotation=20, ha="right", fontsize=7.5)

        self.figure.tight_layout()
        self.canvas.draw_idle()
