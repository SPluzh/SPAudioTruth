"""SPAudioTruth — Audio Quality, Spectrum & Transcode Auditor."""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent / "version.txt"
__version__ = _VERSION_FILE.read_text(encoding="utf-8").strip() if _VERSION_FILE.is_file() else "1.0.0"
