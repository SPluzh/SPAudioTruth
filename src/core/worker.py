from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal

from src.core.analyzer import AnalysisCancelled, analyze_file
from src.core.verdict import build_conversion_recommendations, evaluate_verdict


class AnalysisWorker(QThread):
    progress = Signal(int, str)
    finished_result = Signal(dict)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, filepath: str, parent=None) -> None:
        super().__init__(parent)
        self.filepath = filepath
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def _is_cancelled(self) -> bool:
        return self._cancel_requested

    def run(self) -> None:
        try:
            analysis = analyze_file(
                self.filepath,
                progress_cb=self.progress.emit,
                cancel_cb=self._is_cancelled,
            )
            if self._cancel_requested:
                self.cancelled.emit()
                return

            verdict = evaluate_verdict(analysis)
            recs = build_conversion_recommendations(analysis, verdict)
            payload = {
                "analysis": analysis,
                "verdict": verdict,
                "recommendations": recs,
            }
            self.progress.emit(100, "Analysis complete")
            self.finished_result.emit(payload)
        except AnalysisCancelled:
            self.cancelled.emit()
        except Exception as exc:
            err_msg = f"{exc}\n\n{traceback.format_exc()}"
            self.failed.emit(err_msg)
