from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """Return application root directory (supports PyInstaller _MEIPASS and dev mode)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def get_bin_dir() -> Path:
    """Locate the directory containing ffmpeg.exe and ffprobe.exe."""
    candidates = [
        get_app_dir() / "bin",
        Path(sys.executable).resolve().parent / "bin",
        Path(__file__).resolve().parent.parent.parent / "bin",
    ]
    for candidate in candidates:
        if (candidate / "ffmpeg.exe").is_file() and (candidate / "ffprobe.exe").is_file():
            return candidate
    return candidates[0]


def get_ffmpeg_path() -> str:
    path = get_bin_dir() / "ffmpeg.exe"
    if not path.is_file():
        raise FileNotFoundError(f"ffmpeg.exe not found at: {path}")
    return str(path)


def get_ffprobe_path() -> str:
    path = get_bin_dir() / "ffprobe.exe"
    if not path.is_file():
        raise FileNotFoundError(f"ffprobe.exe not found at: {path}")
    return str(path)


def subprocess_flags() -> int:
    """Return CREATE_NO_WINDOW on Windows to prevent console window flashing."""
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0
