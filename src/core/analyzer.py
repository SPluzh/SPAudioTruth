from __future__ import annotations

import json
import os
import struct
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np

from src.core.paths import get_ffmpeg_path, get_ffprobe_path, subprocess_flags

BITRATE_MPEG1_L3 = [
    0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0
]
BITRATE_MPEG2_L3 = [
    0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0
]
SR_MPEG1 = [44100, 48000, 32000, 0]
SR_MPEG2 = [22050, 24000, 16000, 0]
SR_MPEG25 = [11025, 12000, 8000, 0]
CHANNEL_MODES = {0: "Stereo", 1: "Joint Stereo", 2: "Dual Channel", 3: "Mono"}

CONTROL_EDGES_HZ = [8000, 11025, 12000, 16000, 18000, 19000, 20000]

ProgressCallback = Callable[[int, str], None]
CancelCallback = Callable[[], bool]


class AnalysisCancelled(Exception):
    """Raised when the user cancels a running analysis."""


def _check_cancel(cancel_cb: CancelCallback | None) -> None:
    if cancel_cb is not None and cancel_cb():
        raise AnalysisCancelled("Analysis cancelled by user.")


def _emit_progress(progress_cb: ProgressCallback | None, pct: int, msg: str) -> None:
    if progress_cb is not None:
        progress_cb(max(0, min(100, int(pct))), msg)


def run_ffprobe(filepath: str) -> dict:
    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath,
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess_flags(),
        check=True,
    )
    return json.loads(res.stdout)


@lru_cache(maxsize=1)
def check_libmp3lame() -> bool:
    ffmpeg = get_ffmpeg_path()
    res = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess_flags(),
    )
    return "libmp3lame" in res.stdout


def parse_mp3_header(hdr_bytes: bytes) -> dict | None:
    if len(hdr_bytes) < 4:
        return None
    b0, b1, b2, b3 = hdr_bytes[0], hdr_bytes[1], hdr_bytes[2], hdr_bytes[3]
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return None

    version_bits = (b1 >> 3) & 0x03
    layer_bits = (b1 >> 1) & 0x03
    if version_bits == 1 or layer_bits != 1:  # layer_bits == 1 -> Layer III
        return None

    bitrate_idx = (b2 >> 4) & 0x0F
    sr_idx = (b2 >> 2) & 0x03
    padding = (b2 >> 1) & 0x01
    ch_mode = (b3 >> 6) & 0x03

    if bitrate_idx in (0, 15) or sr_idx == 3:
        return None

    if version_bits == 3:  # MPEG 1
        version = "MPEG-1"
        sr = SR_MPEG1[sr_idx]
        bitrate = BITRATE_MPEG1_L3[bitrate_idx]
        samples_per_frame = 1152
        frame_len = (144 * bitrate * 1000) // sr + padding
        side_info_len = 17 if ch_mode == 3 else 32
    else:  # MPEG 2 / 2.5
        version = "MPEG-2" if version_bits == 2 else "MPEG-2.5"
        sr = SR_MPEG2[sr_idx] if version_bits == 2 else SR_MPEG25[sr_idx]
        bitrate = BITRATE_MPEG2_L3[bitrate_idx]
        samples_per_frame = 576
        frame_len = (72 * bitrate * 1000) // sr + padding
        side_info_len = 9 if ch_mode == 3 else 17

    if frame_len < 4 or bitrate == 0 or sr == 0:
        return None

    return {
        "version": version,
        "sr": sr,
        "bitrate": bitrate,
        "padding": padding,
        "ch_mode": CHANNEL_MODES[ch_mode],
        "frame_len": frame_len,
        "samples_per_frame": samples_per_frame,
        "side_info_len": side_info_len,
    }


def analyze_mp3_binary(filepath: str) -> dict:
    file_size = os.path.getsize(filepath)
    with open(filepath, "rb") as f:
        head = f.read(10)
        audio_start = 0
        id3_size = 0
        if head[:3] == b"ID3" and len(head) == 10:
            id3_size = (
                ((head[6] & 0x7F) << 21)
                | ((head[7] & 0x7F) << 14)
                | ((head[8] & 0x7F) << 7)
                | (head[9] & 0x7F)
            )
            audio_start = 10 + id3_size

        f.seek(min(audio_start, max(file_size - 1, 0)))
        buf = f.read(65536)
        first_offset = None
        first_hdr = None
        for i in range(max(0, len(buf) - 4)):
            hdr = parse_mp3_header(buf[i : i + 4])
            if hdr and i + hdr["frame_len"] + 4 <= len(buf):
                next_hdr = parse_mp3_header(buf[i + hdr["frame_len"] : i + hdr["frame_len"] + 4])
                if next_hdr:
                    first_offset = audio_start + i
                    first_hdr = hdr
                    break

        xing_info = None
        if first_offset is not None and first_hdr is not None:
            f.seek(first_offset)
            frame_data = f.read(max(first_hdr["frame_len"], 512))
            xing_pos = 4 + first_hdr["side_info_len"]
            tag = frame_data[xing_pos : xing_pos + 4]
            if tag in (b"Xing", b"Info") and xing_pos + 8 <= len(frame_data):
                flags = struct.unpack(">I", frame_data[xing_pos + 4 : xing_pos + 8])[0]
                pos = xing_pos + 8
                frames_cnt = None
                bytes_cnt = None
                if (flags & 0x01) and pos + 4 <= len(frame_data):
                    frames_cnt = struct.unpack(">I", frame_data[pos : pos + 4])[0]
                    pos += 4
                if (flags & 0x02) and pos + 4 <= len(frame_data):
                    bytes_cnt = struct.unpack(">I", frame_data[pos : pos + 4])[0]
                    pos += 4
                if flags & 0x04:
                    pos += 100  # TOC
                vbr_scale = None
                if (flags & 0x08) and pos + 4 <= len(frame_data):
                    vbr_scale = struct.unpack(">I", frame_data[pos : pos + 4])[0]
                    pos += 4

                lame_data = None
                lame_pos = xing_pos + 120
                if lame_pos + 16 <= len(frame_data):
                    lame_tag = frame_data[lame_pos : lame_pos + 9]
                    if lame_tag.startswith((b"LAME", b"Lavc", b"GOGO")):
                        enc_str = lame_tag.decode("ascii", errors="replace").strip("\x00")
                        rev_vbr = frame_data[lame_pos + 9]
                        lowpass_raw = frame_data[lame_pos + 10]
                        lowpass_hz = lowpass_raw * 100 if lowpass_raw > 0 else None
                        lame_data = {
                            "encoder_string": enc_str,
                            "vbr_method": rev_vbr & 0x0F,
                            "lowpass_hz": lowpass_hz,
                        }

                xing_info = {
                    "tag": tag.decode("ascii"),
                    "frames_count": frames_cnt,
                    "bytes_count": bytes_cnt,
                    "vbr_scale": vbr_scale,
                    "lame": lame_data,
                }

        bitrate_counts: Counter[int] = Counter()
        sr_counts: Counter[int] = Counter()
        ch_counts: Counter[str] = Counter()
        version_counts: Counter[str] = Counter()
        sample_points = 20
        usable_size = max(file_size - audio_start - 4096, 1)

        for p in range(sample_points):
            offset = audio_start + int((usable_size * p) / sample_points)
            f.seek(offset)
            chunk = f.read(32768)
            idx = 0
            found_here = 0
            while idx < len(chunk) - 8 and found_here < 30:
                h = parse_mp3_header(chunk[idx : idx + 4])
                if h and idx + h["frame_len"] + 4 <= len(chunk):
                    h2 = parse_mp3_header(chunk[idx + h["frame_len"] : idx + h["frame_len"] + 4])
                    if h2:
                        bitrate_counts[h["bitrate"]] += 1
                        sr_counts[h["sr"]] += 1
                        ch_counts[h["ch_mode"]] += 1
                        version_counts[h["version"]] += 1
                        idx += h["frame_len"]
                        found_here += 1
                        continue
                idx += 1

    return {
        "file_size_bytes": file_size,
        "id3v2_size_bytes": id3_size,
        "audio_start_offset": audio_start,
        "first_frame": first_hdr,
        "xing_lame": xing_info,
        "sampled_bitrates_kbps": dict(sorted(bitrate_counts.items())),
        "sampled_sample_rates": dict(sorted(sr_counts.items())),
        "sampled_channel_modes": dict(ch_counts),
        "sampled_versions": dict(version_counts),
    }


def _parse_wav_pipe(buf: bytes) -> tuple[int, np.ndarray]:
    if len(buf) < 12 or buf[:4] != b"RIFF" or buf[8:12] != b"WAVE":
        raise ValueError("Invalid WAV stream from ffmpeg.")

    pos = 12
    fmt_code = 0
    channels = 0
    sample_rate = 0
    bits_per_sample = 0
    pcm_bytes = b""

    while pos + 8 <= len(buf):
        chunk_id = buf[pos:pos + 4]
        chunk_size = struct.unpack_from("<I", buf, pos + 4)[0]
        pos += 8
        if chunk_id == b"fmt ":
            fmt_code, channels, sample_rate, _, _, bits_per_sample = struct.unpack_from("<HHIIHH", buf, pos)
            pos += chunk_size + (chunk_size & 1)
        elif chunk_id == b"data":
            if chunk_size == 0xFFFFFFFF or pos + chunk_size > len(buf):
                pcm_bytes = buf[pos:]
            else:
                pcm_bytes = buf[pos:pos + chunk_size]
            break
        else:
            pos += chunk_size + (chunk_size & 1)

    if channels <= 0 or sample_rate <= 0:
        raise ValueError("Missing fmt header in WAV stream.")

    sample_bytes = max(1, bits_per_sample // 8)
    frame_bytes = sample_bytes * channels
    valid_len = (len(pcm_bytes) // frame_bytes) * frame_bytes
    pcm_view = memoryview(pcm_bytes)[:valid_len]

    if bits_per_sample == 32 and fmt_code in (3, 0xFFFE):
        audio = np.frombuffer(pcm_view, dtype="<f4").reshape(-1, channels).copy()
    elif bits_per_sample == 16 and fmt_code in (1, 0xFFFE):
        audio = np.frombuffer(pcm_view, dtype="<i2").reshape(-1, channels).astype(np.float32) / 32768.0
    elif bits_per_sample == 32 and fmt_code == 1:
        audio = np.frombuffer(pcm_view, dtype="<i4").reshape(-1, channels).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV stream format: fmt={fmt_code}, bps={bits_per_sample}")

    return int(sample_rate), audio


def decode_segment(filepath: str, start_sec: float, duration_sec: float) -> tuple[int, np.ndarray]:
    ffmpeg = get_ffmpeg_path()
    cmd = [
        ffmpeg,
        "-v", "error",
        "-ss", f"{start_sec:.3f}",
        "-t", f"{duration_sec:.3f}",
        "-i", filepath,
        "-f", "wav",
        "-acodec", "pcm_f32le",
        "pipe:1",
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        creationflags=subprocess_flags(),
        check=True,
    )
    return _parse_wav_pipe(res.stdout)


def analyze_stereo(audio: np.ndarray) -> dict:
    if audio.shape[1] < 2:
        return {
            "is_stereo": False,
            "side_to_mid_db": None,
            "max_abs_diff": 0.0,
            "correlation": 1.0,
            "pseudo_stereo": False,
        }
    left = audio[:, 0].astype(np.float32, copy=False)
    right = audio[:, 1].astype(np.float32, copy=False)
    mid = 0.5 * (left + right)
    side = 0.5 * (left - right)
    rms_mid = float(np.sqrt(np.mean(mid ** 2, dtype=np.float64) + 1e-20))
    rms_side = float(np.sqrt(np.mean(side ** 2, dtype=np.float64) + 1e-20))
    side_to_mid_db = 20.0 * np.log10(rms_side / rms_mid)
    max_abs_diff = float(np.max(np.abs(left - right)))
    if float(np.std(left, dtype=np.float64)) > 1e-9 and float(np.std(right, dtype=np.float64)) > 1e-9:
        corr = float(np.corrcoef(left, right)[0, 1])
    else:
        corr = 1.0
    return {
        "is_stereo": True,
        "side_to_mid_db": round(float(side_to_mid_db), 2),
        "max_abs_diff": max_abs_diff,
        "correlation": round(corr, 6),
        "pseudo_stereo": bool(max_abs_diff < 1e-5 or side_to_mid_db < -40.0),
    }


def _estimate_cutoff_hz(
    freqs: np.ndarray,
    p99_db: np.ndarray,
    noise_floor_p99: float,
    edge_drops_db: dict[str, float],
    sr: int,
) -> float:
    bin_hz = float(sr) / 4096.0
    kernel_bins = max(3, int(round(200.0 / bin_hz)))
    # Use edge padding instead of zero-padding to avoid artificial rise near Nyquist
    pad_left = (kernel_bins - 1) // 2
    pad_right = kernel_bins - 1 - pad_left
    padded = np.pad(p99_db, (pad_left, pad_right), mode="edge")
    smooth_p99 = np.convolve(padded, np.ones(kernel_bins) / kernel_bins, mode="valid")

    # Sustained energy above noise_floor + 10 dB (at least ~200 Hz contiguous width)
    min_run = max(3, int(round(200.0 / bin_hz)))
    above = (freqs >= 2000.0) & (smooth_p99 > noise_floor_p99 + 10.0)

    sustained_cutoff = 0.0
    run_len = 0
    for idx, is_above in enumerate(above):
        if is_above:
            run_len += 1
            if run_len >= min_run:
                sustained_cutoff = float(freqs[idx])
        else:
            run_len = 0

    # Check brickwall drops >= 15 dB at standard encoder/SR boundaries
    brickwall_edges = []
    for edge in CONTROL_EDGES_HZ:
        key = f"{edge}Hz"
        drop = edge_drops_db.get(key)
        if drop is not None and drop >= 15.0:
            brickwall_edges.append((float(edge), float(drop)))

    if brickwall_edges:
        strongest_edge, strongest_drop = max(brickwall_edges, key=lambda x: x[1])
        if sustained_cutoff == 0.0:
            return round(strongest_edge, 1)
        if strongest_drop >= 20.0 and abs(sustained_cutoff - strongest_edge) <= 1800.0:
            return round(strongest_edge, 1)
        if sustained_cutoff > strongest_edge and strongest_drop >= 25.0:
            above_mask = (freqs > strongest_edge + 600.0) & (freqs < min(sr / 2.0 - 500.0, strongest_edge + 3500.0))
            if np.any(above_mask) and float(np.median(p99_db[above_mask])) < noise_floor_p99 + 8.0:
                return round(strongest_edge, 1)

    return round(sustained_cutoff, 1)


def compute_spectrum_metrics(mono: np.ndarray, sr: int) -> dict:
    nfft = 4096
    hop = 1024
    mono = np.asarray(mono, dtype=np.float32)
    if len(mono) < nfft:
        mono = np.pad(mono, (0, nfft - len(mono)))
    win = (0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(nfft, dtype=np.float32) / nfft)).astype(np.float32)
    win_scale = np.float32(1.0 / np.sum(win))
    frames = np.lib.stride_tricks.sliding_window_view(mono, nfft)[::hop]
    Zxx = (np.fft.rfft(frames * win, axis=1) * win_scale).T
    freqs = np.fft.rfftfreq(nfft, d=1.0 / sr)
    times = (np.arange(frames.shape[0], dtype=np.float64) * hop + nfft / 2.0) / sr
    mag_db = (20.0 * np.log10(np.abs(Zxx) + np.float32(1e-12))).astype(np.float32)

    hi_speech = min(8000.0, sr * 0.42)
    lo_speech = min(1000.0, hi_speech * 0.25)
    speech_mask = (freqs >= lo_speech) & (freqs <= hi_speech)
    frame_energy = np.mean(mag_db[speech_mask, :], axis=0)
    thresh = np.percentile(frame_energy, 50)
    active_idx = frame_energy >= thresh
    active_db = mag_db[:, active_idx] if np.any(active_idx) else mag_db

    mean_db = np.mean(active_db, axis=1)
    p95_db = np.percentile(active_db, 95, axis=1)
    p99_db = np.percentile(active_db, 99, axis=1)
    peak_db = np.max(active_db, axis=1)

    top_band = freqs >= min(20500.0, sr * 0.45)
    noise_floor_p99 = float(np.median(p99_db[top_band])) if np.any(top_band) else float(np.min(p99_db))
    noise_floor_mean = float(np.median(mean_db[top_band])) if np.any(top_band) else float(np.min(mean_db))

    bands = [
        (1000, 4000),
        (4000, 8000),
        (8000, 11025),
        (11025, 12000),
        (12000, 16000),
        (16000, 18000),
        (18000, 20000),
        (20000, int(sr / 2)),
    ]
    band_stats = {}
    for lo, hi in bands:
        m = (freqs >= lo) & (freqs < hi)
        if np.any(m):
            band_stats[f"{lo}-{hi}Hz"] = {
                "mean_db": round(float(np.mean(mean_db[m])), 2),
                "p99_db": round(float(np.mean(p99_db[m])), 2),
                "max_db": round(float(np.max(peak_db[m])), 2),
            }

    step_checks = {}
    for edge in CONTROL_EDGES_HZ:
        if edge + 800 < sr / 2:
            below = (freqs >= edge - 600) & (freqs < edge - 100)
            above = (freqs > edge + 100) & (freqs <= edge + 600)
            if np.any(below) and np.any(above):
                drop_p99 = float(np.mean(p99_db[below]) - np.mean(p99_db[above]))
                step_checks[f"{edge}Hz"] = round(drop_p99, 2)

    cutoff_p99_hz = _estimate_cutoff_hz(freqs, p99_db, noise_floor_p99, step_checks, sr)

    return {
        "freqs": freqs,
        "times": times,
        "mag_db": mag_db,
        "mean_db": mean_db,
        "p95_db": p95_db,
        "p99_db": p99_db,
        "peak_db": peak_db,
        "noise_floor_p99_db": round(noise_floor_p99, 2),
        "noise_floor_mean_db": round(noise_floor_mean, 2),
        "estimated_cutoff_p99_hz": cutoff_p99_hz,
        "band_stats": band_stats,
        "edge_drops_db": step_checks,
    }


def _run_saturation_quality(filepath: str, start_sec: float, duration_sec: float, q: int) -> tuple[str, float]:
    ffmpeg = get_ffmpeg_path()
    cmd = [
        ffmpeg,
        "-v", "error",
        "-ss", f"{start_sec:.3f}",
        "-t", f"{duration_sec:.3f}",
        "-i", filepath,
        "-c:a", "libmp3lame",
        "-q:a", str(q),
        "-f", "mp3",
        "pipe:1",
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        creationflags=subprocess_flags(),
        check=True,
    )
    size_bytes = len(res.stdout)
    kbps = (size_bytes * 8) / (max(duration_sec, 0.1) * 1000.0)
    return f"vbr_q{q}_kbps", round(kbps, 1)


def reencode_saturation_test(
    filepath: str,
    start_sec: float,
    duration_sec: float,
    cancel_cb: CancelCallback | None = None,
) -> dict:
    qualities = [0, 2, 4]
    results = {}
    with ThreadPoolExecutor(max_workers=len(qualities)) as pool:
        futures = {
            pool.submit(_run_saturation_quality, filepath, start_sec, duration_sec, q): q
            for q in qualities
        }
        for fut in as_completed(futures):
            _check_cancel(cancel_cb)
            key, val = fut.result()
            results[key] = val
    return {f"vbr_q{q}_kbps": results[f"vbr_q{q}_kbps"] for q in qualities}


def _build_segment_positions(duration: float) -> list[tuple[str, str, float, float]]:
    if duration <= 35.0:
        return [("00_full", "Full file", 0.0, max(1.0, duration))]
    if duration <= 95.0:
        half = duration / 2.0
        return [
            ("00_intro_0_30s", "Start (0–30s)", 0.0, min(30.0, half)),
            ("01_mid", "Middle", max(0.0, duration * 0.35), min(30.0, half)),
            ("06_outro_last", "Outro", max(0.0, duration - min(30.0, half)), min(30.0, half)),
        ]
    return [
        ("00_intro_0_30s", "Intro (0–30s)", 0.0, 30.0),
        ("01_intro_30_60s", "Intro (30–60s)", 30.0, 30.0),
        ("02_20pct", "20% position", duration * 0.20, 30.0),
        ("03_40pct", "40% position", duration * 0.40, 30.0),
        ("04_60pct", "60% position", duration * 0.60, 30.0),
        ("05_80pct", "80% position", duration * 0.80, 30.0),
        ("06_outro_last_60s", "Outro (last 60s)", max(0.0, duration - 60.0), 55.0),
    ]


def analyze_file(
    filepath: str,
    progress_cb: ProgressCallback | None = None,
    cancel_cb: CancelCallback | None = None,
) -> dict:
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {filepath}")

    _check_cancel(cancel_cb)
    _emit_progress(progress_cb, 5, "Reading metadata (ffprobe)…")
    probe = run_ffprobe(str(path))
    fmt = probe.get("format", {})
    audio_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise ValueError("No audio stream found in file.")
    stream = audio_streams[0]

    duration = float(fmt.get("duration") or stream.get("duration") or 0.0)
    sr = int(stream.get("sample_rate", 44100))
    channels = int(stream.get("channels", 2))
    raw_br = fmt.get("bit_rate") or stream.get("bit_rate") or 0
    declared_kbps = round(int(raw_br) / 1000.0, 2) if raw_br else 0.0
    file_size = os.path.getsize(path)

    _check_cancel(cancel_cb)
    _emit_progress(progress_cb, 12, "Parsing MP3 frames and Xing/LAME headers…")
    codec_name = (stream.get("codec_name") or "").lower()
    binary_info = analyze_mp3_binary(str(path)) if codec_name == "mp3" else {
        "file_size_bytes": file_size,
        "id3v2_size_bytes": 0,
        "audio_start_offset": 0,
        "first_frame": None,
        "xing_lame": None,
        "sampled_bitrates_kbps": {},
        "sampled_sample_rates": {},
        "sampled_channel_modes": {},
        "sampled_versions": {},
    }

    positions = _build_segment_positions(duration)
    n_pos = len(positions)
    segment_results: list[dict | None] = [None] * n_pos

    def _process_segment(idx: int, label: str, display_name: str, start_s: float, dur_s: float) -> tuple[int, dict]:
        _check_cancel(cancel_cb)
        read_sr, audio = decode_segment(str(path), start_s, dur_s)
        _check_cancel(cancel_cb)
        stereo_info = analyze_stereo(audio)
        mono = np.mean(audio, axis=1, dtype=np.float32)
        spec = compute_spectrum_metrics(mono, read_sr)
        return idx, {
            "label": label,
            "display_name": display_name,
            "start_sec": round(start_s, 1),
            "duration_sec": round(dur_s, 1),
            "sample_rate": read_sr,
            "stereo": stereo_info,
            "spec": spec,
            "_start_s": start_s,
            "_dur_s": dur_s,
        }

    max_workers = min(4, os.cpu_count() or 2, max(1, n_pos))
    _emit_progress(progress_cb, 18, f"Analyzing {n_pos} segments in parallel…")
    done_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_process_segment, idx, label, display_name, start_s, dur_s)
            for idx, (label, display_name, start_s, dur_s) in enumerate(positions)
        ]
        try:
            for fut in as_completed(futures):
                _check_cancel(cancel_cb)
                idx, seg_data = fut.result()
                segment_results[idx] = seg_data
                done_count += 1
                pct = 18 + int(65 * (done_count / max(n_pos, 1)))
                _emit_progress(
                    progress_cb,
                    pct,
                    f"Analyzed segment {done_count}/{n_pos}: {seg_data['display_name']}",
                )
        except Exception:
            for fut in futures:
                fut.cancel()
            raise

    richest_seg = None
    richest_high_energy = -999.0
    final_segments: list[dict] = []
    for seg_data in segment_results:
        assert seg_data is not None
        start_s = seg_data.pop("_start_s")
        dur_s = seg_data.pop("_dur_s")
        spec = seg_data["spec"]
        label = seg_data["label"]
        e_high = spec["band_stats"].get("8000-11025Hz", {}).get("p99_db", -120.0)
        if label.startswith(("02_", "03_", "04_", "05_")) or richest_seg is None:
            if e_high > richest_high_energy:
                richest_high_energy = e_high
                richest_seg = (label, seg_data["display_name"], start_s, dur_s, spec)
        final_segments.append(seg_data)

    segment_results = final_segments

    _check_cancel(cancel_cb)
    _emit_progress(progress_cb, 86, "Checking libmp3lame encoder and running saturation test…")
    has_lame = check_libmp3lame()
    sat_test = {}
    if has_lame and richest_seg and duration >= 30.0:
        sat_test["intro_0_60s"] = reencode_saturation_test(
            str(path), 0.0, min(60.0, duration), cancel_cb=cancel_cb
        )
        sat_test["speech_60s"] = reencode_saturation_test(
            str(path), richest_seg[2], min(60.0, max(10.0, duration - richest_seg[2])), cancel_cb=cancel_cb
        )

    _emit_progress(progress_cb, 94, "Generating verdict and recommendations…")

    hours = int(duration // 3600)
    mins = int((duration % 3600) // 60)
    secs = int(duration % 60)

    return {
        "file": str(path),
        "file_name": path.name,
        "file_size_bytes": file_size,
        "duration_sec": round(duration, 2),
        "duration_hms": f"{hours}h {mins:02d}m {secs:02d}s",
        "ffprobe_stream": {
            "codec": codec_name,
            "sample_rate": sr,
            "channels": channels,
            "channel_layout": stream.get("channel_layout") or ("mono" if channels == 1 else "stereo"),
            "declared_bitrate_kbps": declared_kbps,
            "tags": fmt.get("tags", {}),
        },
        "binary_analysis": binary_info,
        "has_libmp3lame": has_lame,
        "saturation_test": sat_test,
        "segments": segment_results,
        "richest_segment_label": richest_seg[0] if richest_seg else segment_results[0]["label"],
    }
