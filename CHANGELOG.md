# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0]
- **Initial Release**: Launched **SPAudioTruth** — Audio Quality, Spectrum & Transcode Auditor with a PySide6 desktop GUI and standalone Windows `.exe` build (`_build_/SPAudioTruth.spec`).
- **Audio Analysis & Verdict**: Multi-format inspection (`MP3`, `M4A`, `M4B`, `AAC`, `WAV`, `FLAC`, `OGG`, `OPUS`) using `ffprobe`/`ffmpeg`, binary MP3 frame parsing, STFT spectral cutoff detection, stereo correlation/difference analysis, VBR re-encode saturation testing, and upconvert/transcode verdict evaluation with conversion recommendations.
- **Interactive Visualization & Export**: Added 5-tab UI with Summary & Evidence, Dual Spectrogram, Spectrum Profile, Bitrate/Stereo Timeline, and Cutoff/Dynamic Range plots, plus Drag & Drop support and PNG/JSON report export.
