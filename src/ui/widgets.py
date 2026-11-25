from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.styles import ACCENT_LIGHT, STATUS_ERROR, STATUS_OK, STATUS_WARNING, TEXT_DIM


class KpiCard(QFrame):
    """Dashboard summary card with optional semantic status styling."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self.setProperty("status", "")
        self.setMinimumWidth(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("CardTitle")
        self.value_lbl = QLabel("—")
        self.value_lbl.setObjectName("CardValue")
        self.value_lbl.setWordWrap(True)
        self.sub_lbl = QLabel("")
        self.sub_lbl.setObjectName("CardSub")
        self.sub_lbl.setWordWrap(True)

        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addWidget(self.sub_lbl)
        layout.addStretch()

    def set_data(self, value: str, sub: str = "", status: str = "") -> None:
        self.value_lbl.setText(value)
        self.sub_lbl.setText(sub)
        if self.property("status") != status:
            self.setProperty("status", status)
            self.style().unpolish(self)
            self.style().polish(self)


def _fit_table_height(table: QTableWidget) -> None:
    """Resize table to fit all rows without an inner vertical scrollbar."""
    table.resizeRowsToContents()
    header = table.horizontalHeader()
    header_h = max(header.height(), header.sizeHint().height()) if header.isVisible() else 0
    rows_h = sum(table.rowHeight(r) for r in range(table.rowCount()))
    frame_h = table.frameWidth() * 2
    hbar_h = table.horizontalScrollBar().sizeHint().height() if table.horizontalScrollBar().isVisible() else 0
    total_h = header_h + rows_h + frame_h + hbar_h + 2
    table.setFixedHeight(max(total_h, header_h + frame_h + 2))


class FindingsAndRecommendationsTab(QWidget):
    """Tab 1: Declared vs Measured, Evidence Checklist, Conversion Recommendations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_options: list[dict] = []

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(14)

        # 1. Declared vs Measured table
        grp_compare = QGroupBox("Declared vs. Measured")
        cmp_layout = QVBoxLayout(grp_compare)
        self.compare_table = QTableWidget(0, 3)
        self.compare_table.setHorizontalHeaderLabels(["Parameter", "Declared (Metadata)", "Measured (Actual)"])
        self.compare_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.compare_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.compare_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.compare_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.compare_table.setAlternatingRowColors(True)
        self.compare_table.verticalHeader().setVisible(False)
        self.compare_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _fit_table_height(self.compare_table)
        cmp_layout.addWidget(self.compare_table)
        main_layout.addWidget(grp_compare)

        # 2. Evidence checklist
        grp_ev = QGroupBox("Evidence Checklist")
        ev_layout = QVBoxLayout(grp_ev)
        self.evidence_table = QTableWidget(0, 3)
        self.evidence_table.setHorizontalHeaderLabels(["Indicator", "Status", "Details"])
        self.evidence_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.evidence_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.evidence_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.evidence_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.evidence_table.setAlternatingRowColors(True)
        self.evidence_table.verticalHeader().setVisible(False)
        self.evidence_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _fit_table_height(self.evidence_table)
        ev_layout.addWidget(self.evidence_table)
        main_layout.addWidget(grp_ev)

        # 3. Recommendations
        grp_rec = QGroupBox("Recommendations")
        rec_layout = QVBoxLayout(grp_rec)
        rec_layout.setSpacing(10)

        self.advice_lbl = QLabel("Load an audio file to compute optimization recommendations.")
        self.advice_lbl.setWordWrap(True)
        self.advice_lbl.setStyleSheet(f"color: {ACCENT_LIGHT}; font-weight: 600;")
        rec_layout.addWidget(self.advice_lbl)

        self.ch_sr_lbl = QLabel("")
        self.ch_sr_lbl.setWordWrap(True)
        self.ch_sr_lbl.setStyleSheet(f"color: {TEXT_DIM};")
        self.ch_sr_lbl.setVisible(False)
        rec_layout.addWidget(self.ch_sr_lbl)

        self.rec_table = QTableWidget(0, 6)
        self.rec_table.setHorizontalHeaderLabels([
            "Format", "Arguments", "Lowpass / Cutoff", "Est. Bitrate", "Est. Size", "Notes"
        ])
        self.rec_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.rec_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.rec_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.rec_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.rec_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.rec_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.rec_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rec_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rec_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.rec_table.setAlternatingRowColors(True)
        self.rec_table.verticalHeader().setVisible(False)
        self.rec_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rec_table.cellClicked.connect(self._on_rec_row_clicked)
        self.rec_table.setVisible(False)
        rec_layout.addWidget(self.rec_table)

        self.cmd_widget = QWidget()
        cmd_row = QHBoxLayout(self.cmd_widget)
        cmd_row.setContentsMargins(0, 0, 0, 0)
        cmd_row.addWidget(QLabel("ffmpeg command:"))
        self.cmd_edit = QLineEdit()
        self.cmd_edit.setReadOnly(True)
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self._copy_command)
        cmd_row.addWidget(self.cmd_edit, 1)
        cmd_row.addWidget(self.copy_btn)
        self.cmd_widget.setVisible(False)
        rec_layout.addWidget(self.cmd_widget)

        main_layout.addWidget(grp_rec)
        main_layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_rec_row_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._current_options):
            cmd = self._current_options[row].get("ffmpeg_command", "")
            if cmd:
                self.cmd_edit.setText(cmd)

    def _copy_command(self) -> None:
        txt = self.cmd_edit.text().strip()
        if txt:
            QGuiApplication.clipboard().setText(txt)

    def update_data(self, analysis: dict, verdict: dict, recs: dict) -> None:
        stream = analysis["ffprobe_stream"]
        binary = analysis.get("binary_analysis") or {}
        xing = binary.get("xing_lame") or {}
        lame = xing.get("lame") or {}
        tags = stream.get("tags") or {}

        encoder_decl = tags.get("encoder") or (lame.get("encoder_string") if lame else "Not specified")
        tag_summary = ", ".join(f"{k}={v}" for k, v in list(tags.items())[:4]) or "None"

        rows = [
            (
                "Bitrate",
                f"{verdict['declared_bitrate_kbps']} kbps",
                f"{verdict['equivalent_label']} ({verdict['waste_text']})",
            ),
            (
                "Sample Rate",
                f"{verdict['declared_sample_rate_hz']} Hz",
                f"{verdict['real_sample_rate_hz']} Hz"
                + (" (oversampled)" if verdict["oversampling_detected"] else " (normal)"),
            ),
            (
                "Channels",
                f"{stream['channels']} ({stream['channel_layout']})",
                f"{verdict['stereo_mode']}"
                + (f" (Side/Mid: {verdict['avg_side_to_mid_db']} dB, corr: {verdict['avg_correlation']})"
                   if verdict["avg_side_to_mid_db"] is not None else ""),
            ),
            (
                "Encoder / Header",
                str(encoder_decl),
                f"{xing.get('tag', 'No Xing/Info')} | LAME: {lame.get('encoder_string', 'none')}, lowpass: {lame.get('lowpass_hz') or 'none'}",
            ),
            (
                "Container Tags",
                tag_summary,
                "Inherited MP4/AAC tags" if verdict["inherited_mp4_tags"] else "Clean container tags",
            ),
            (
                "Effective Cutoff",
                "—",
                f"{verdict['effective_cutoff_hz']:.0f} Hz ({verdict['cutoff_desc']}, drop {verdict['primary_drop_db']} dB)",
            ),
        ]

        self.compare_table.setRowCount(len(rows))
        for r, (p, d, m) in enumerate(rows):
            self.compare_table.setItem(r, 0, QTableWidgetItem(p))
            self.compare_table.setItem(r, 1, QTableWidgetItem(d))
            self.compare_table.setItem(r, 2, QTableWidgetItem(m))
        _fit_table_height(self.compare_table)

        evidences = verdict["evidences"]
        self.evidence_table.setRowCount(len(evidences))
        for r, ev in enumerate(evidences):
            self.evidence_table.setItem(r, 0, QTableWidgetItem(ev["title"]))
            st_item = QTableWidgetItem(ev["status_label"])
            if ev["detected"]:
                color = QColor(STATUS_ERROR) if ev["severity"] == "high" else QColor(STATUS_WARNING)
            else:
                color = QColor(STATUS_OK)
            st_item.setForeground(color)
            self.evidence_table.setItem(r, 1, st_item)
            self.evidence_table.setItem(r, 2, QTableWidgetItem(ev["details"]))
        _fit_table_height(self.evidence_table)

        self.update_recommendations(recs)

    def update_recommendations(self, recs: dict) -> None:
        should_reencode = bool(recs.get("should_reencode", False))
        self._current_options = recs.get("options") or []

        if not should_reencode:
            self.advice_lbl.setStyleSheet(f"color: {STATUS_OK}; font-weight: 600;")
            self.advice_lbl.setText(recs["advice"])
            self.ch_sr_lbl.setVisible(False)
            self.rec_table.setRowCount(0)
            self.rec_table.setVisible(False)
            self.cmd_edit.clear()
            self.cmd_widget.setVisible(False)
            return

        self.advice_lbl.setStyleSheet(f"color: {STATUS_WARNING}; font-weight: 600;")
        self.advice_lbl.setText(recs["advice"])
        self.ch_sr_lbl.setText(
            f"Channels: {recs['channel_reason']}   |   Sample Rate: {recs['sample_rate_reason']}"
        )
        self.ch_sr_lbl.setVisible(True)
        self.rec_table.setVisible(True)
        self.cmd_widget.setVisible(True)

        opts = self._current_options
        self.rec_table.setRowCount(len(opts))
        rec_opt = recs.get("recommended_option")
        rec_row = 0
        for r, opt in enumerate(opts):
            if rec_opt is not None and opt.get("format") == rec_opt.get("format"):
                rec_row = r
            self.rec_table.setItem(r, 0, QTableWidgetItem(opt["format"]))
            self.rec_table.setItem(r, 1, QTableWidgetItem(opt["codec_args"]))
            self.rec_table.setItem(r, 2, QTableWidgetItem(opt.get("lowpass_desc", "—")))
            self.rec_table.setItem(r, 3, QTableWidgetItem(f"~{opt['target_kbps']} kbps"))
            sav_str = f"{opt['estimated_mb']:.1f} MB ({opt['savings_pct']:+.1f}%)"
            self.rec_table.setItem(r, 4, QTableWidgetItem(sav_str))
            self.rec_table.setItem(r, 5, QTableWidgetItem(opt["note"]))

        _fit_table_height(self.rec_table)
        if opts:
            self.rec_table.selectRow(rec_row)
        self.cmd_edit.setText(recs.get("ffmpeg_command", ""))
