# SPAudioTruth

**Audio Quality, Spectrum & Transcode Auditor** for Windows.

SPAudioTruth helps you verify whether an audio file's quality matches its declared bitrate and format, detect lossy-to-lossless or low-to-high bitrate upconverts (transcodes), and inspect spectral and stereo characteristics through an interactive desktop interface.

[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)](https://pypi.org/project/PySide6/)
[![Latest Release](https://img.shields.io/github/v/release/SPluzh/SPAudioTruth)](https://github.com/SPluzh/SPAudioTruth/releases)

---

## Features

- **Multi-Format Support**: Inspects `MP3`, `M4A`, `M4B`, `AAC`, `WAV`, `FLAC`, `OGG`, and `OPUS` files.
- **Transcode & Upconvert Detection**: Compares declared bitrate/codec parameters against measured spectral cutoffs and VBR re-encode saturation tests to identify fake lossless or re-encoded files.
- **Binary MP3 Frame Inspection**: Parses MP3 frame headers (CBR/VBR, Xing/Info/LAME tags) and checks frame-level consistency.
- **Interactive 5-Tab Analysis**:
  1. **Findings & Recommendations** — Verdict cards, declared vs. measured comparison, evidence breakdown, and conversion recommendations.
  2. **Aggregate Spectrum (PSD)** — Power Spectral Density profile and detected frequency cutoff.
  3. **Spectrograms** — High-resolution time-frequency spectrograms.
  4. **Frames & Bands** — Bitrate/frame distribution and frequency band energy.
  5. **Segments & Stereo** — Per-segment cutoff, dynamic range, and stereo correlation/difference metrics.
- **Drag & Drop + CLI Support**: Drop any supported audio file directly into the window, use **Open Audio File…**, or pass a file path as a command-line argument.
- **Report Export**: Export a complete analysis report (`JSON` summary + `3 PNG` charts) to any folder with one click.

---

## Quick Start (Windows)

1. Download the latest `SPAudioTruth_v*.zip` from [Releases](https://github.com/SPluzh/SPAudioTruth/releases).
2. Extract the archive to any folder.
3. Run `SPAudioTruth.exe` and drag & drop an audio file into the window.
