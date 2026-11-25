import json
import math
import os
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile

TARGET_FILE = r"W:\Энди Вейер. Проект «Аве Мария». Аудиокнига.Фантастика.mp3"
BIN_DIR = Path(r"C:\Users\user\Desktop\python\mp3_test\bin")
FFMPEG = str(BIN_DIR / "ffmpeg.exe")
FFPROBE = str(BIN_DIR / "ffprobe.exe")
REPORT_DIR = Path(r"C:\Users\user\Desktop\python\mp3_test\report")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# MPEG-1 Layer III lookup tables
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


def run_ffprobe(filepath: str) -> dict:
    cmd = [
        FFPROBE, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        filepath,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(res.stdout)


def check_libmp3lame() -> bool:
    res = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True, encoding="utf-8")
    return "libmp3lame" in res.stdout


def parse_mp3_header(hdr_bytes: bytes):
    if len(hdr_bytes) < 4:
        return None
    b0, b1, b2, b3 = hdr_bytes[0], hdr_bytes[1], hdr_bytes[2], hdr_bytes[3]
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return None

    version_bits = (b1 >> 3) & 0x03
    layer_bits = (b1 >> 1) & 0x03
    if version_bits == 1 or layer_bits != 1:  # layer 1 == Layer III
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
        if head[:3] == b"ID3":
            id3_size = (
                ((head[6] & 0x7F) << 21)
                | ((head[7] & 0x7F) << 14)
                | ((head[8] & 0x7F) << 7)
                | (head[9] & 0x7F)
            )
            audio_start = 10 + id3_size

        # Find first valid frame near audio_start
        f.seek(audio_start)
        buf = f.read(65536)
        first_offset = None
        first_hdr = None
        for i in range(len(buf) - 4):
            hdr = parse_mp3_header(buf[i : i + 4])
            if hdr and i + hdr["frame_len"] + 4 <= len(buf):
                next_hdr = parse_mp3_header(buf[i + hdr["frame_len"] : i + hdr["frame_len"] + 4])
                if next_hdr:
                    first_offset = audio_start + i
                    first_hdr = hdr
                    break

        xing_info = None
        if first_offset is not None:
            f.seek(first_offset)
            frame_data = f.read(max(first_hdr["frame_len"], 512))
            xing_pos = 4 + first_hdr["side_info_len"]
            tag = frame_data[xing_pos : xing_pos + 4]
            if tag in (b"Xing", b"Info"):
                flags = struct.unpack(">I", frame_data[xing_pos + 4 : xing_pos + 8])[0]
                pos = xing_pos + 8
                frames_cnt = None
                bytes_cnt = None
                if flags & 0x01:
                    frames_cnt = struct.unpack(">I", frame_data[pos : pos + 4])[0]
                    pos += 4
                if flags & 0x02:
                    bytes_cnt = struct.unpack(">I", frame_data[pos : pos + 4])[0]
                    pos += 4
                if flags & 0x04:
                    pos += 100  # TOC
                vbr_scale = None
                if flags & 0x08:
                    vbr_scale = struct.unpack(">I", frame_data[pos : pos + 4])[0]
                    pos += 4

                lame_data = None
                lame_pos = xing_pos + 120
                if lame_pos + 36 <= len(frame_data):
                    lame_tag = frame_data[lame_pos : lame_pos + 9]
                    if lame_tag.startswith(b"LAME") or lame_tag.startswith(b"Lavc") or lame_tag.startswith(b"GOGO"):
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

        # Sample frames across 20 evenly spaced positions in the file
        bitrate_counts = Counter()
        sr_counts = Counter()
        ch_counts = Counter()
        sample_points = 20
        usable_size = max(file_size - audio_start - 10000, 1)
        for p in range(sample_points):
            offset = audio_start + int((usable_size * p) / sample_points)
            f.seek(offset)
            chunk = f.read(32768)
            idx = 0
            found_here = 0
            # sync to first valid pair
            while idx < len(chunk) - 8 and found_here < 30:
                h = parse_mp3_header(chunk[idx : idx + 4])
                if h and idx + h["frame_len"] + 4 <= len(chunk):
                    h2 = parse_mp3_header(chunk[idx + h["frame_len"] : idx + h["frame_len"] + 4])
                    if h2:
                        bitrate_counts[h["bitrate"]] += 1
                        sr_counts[h["sr"]] += 1
                        ch_counts[h["ch_mode"]] += 1
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
        "sampled_bitrates_kbps": dict(bitrate_counts),
        "sampled_sample_rates": dict(sr_counts),
        "sampled_channel_modes": dict(ch_counts),
    }


def decode_segment(filepath: str, start_sec: float, duration_sec: float, sr: int, channels: int) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cmd = [
            FFMPEG, "-y", "-v", "error",
            "-ss", f"{start_sec:.3f}",
            "-t", f"{duration_sec:.3f}",
            "-i", filepath,
            "-f", "wav",
            tmp_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        read_sr, data = wavfile.read(tmp_path)
        if np.issubdtype(data.dtype, np.integer):
            max_val = float(np.iinfo(data.dtype).max)
            audio = data.astype(np.float32) / max_val
        else:
            audio = data.astype(np.float32)
        if audio.ndim == 1:
            audio = audio.reshape(-1, 1)
        return audio
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def analyze_stereo(audio: np.ndarray) -> dict:
    if audio.shape[1] < 2:
        return {"is_stereo": False}
    left = audio[:, 0].astype(np.float64)
    right = audio[:, 1].astype(np.float64)
    mid = 0.5 * (left + right)
    side = 0.5 * (left - right)
    rms_mid = np.sqrt(np.mean(mid ** 2) + 1e-20)
    rms_side = np.sqrt(np.mean(side ** 2) + 1e-20)
    side_to_mid_db = 20.0 * np.log10(rms_side / rms_mid)
    max_abs_diff = float(np.max(np.abs(left - right)))
    corr = float(np.corrcoef(left, right)[0, 1]) if np.std(left) > 1e-9 and np.std(right) > 1e-9 else 1.0
    return {
        "is_stereo": True,
        "side_to_mid_db": round(side_to_mid_db, 2),
        "max_abs_diff": max_abs_diff,
        "correlation": round(corr, 6),
        "pseudo_stereo": bool(max_abs_diff < 1e-5 or side_to_mid_db < -60.0),
    }


def compute_spectrum_metrics(mono: np.ndarray, sr: int) -> dict:
    nfft = 4096
    hop = 1024
    win = signal.windows.hann(nfft, sym=False)
    freqs, times, Zxx = signal.stft(
        mono, fs=sr, window=win, nperseg=nfft, noverlap=nfft - hop, boundary=None
    )
    mag_db = 20.0 * np.log10(np.abs(Zxx) + 1e-12)

    # Filter active frames (top 50% by energy in 1-8 kHz to exclude silence)
    speech_mask = (freqs >= 1000) & (freqs <= 8000)
    frame_energy = np.mean(mag_db[speech_mask, :], axis=0)
    thresh = np.percentile(frame_energy, 50)
    active_idx = frame_energy >= thresh
    active_db = mag_db[:, active_idx] if np.any(active_idx) else mag_db

    mean_db = np.mean(active_db, axis=1)
    p95_db = np.percentile(active_db, 95, axis=1)
    p99_db = np.percentile(active_db, 99, axis=1)
    peak_db = np.max(active_db, axis=1)

    # Noise floor estimation above 20.5 kHz (or top 10% of band)
    top_band = freqs >= min(20500, sr * 0.45)
    noise_floor_p99 = float(np.median(p99_db[top_band]))
    noise_floor_mean = float(np.median(mean_db[top_band]))

    # Find brickwall cutoff using p99_db: last frequency where 200Hz-smoothed p99_db is >= noise_floor + 8 dB
    kernel_bins = max(1, int(round(200.0 / (sr / nfft))))
    smooth_p99 = np.convolve(p99_db, np.ones(kernel_bins) / kernel_bins, mode="same")
    # Also check drop slope
    above_floor = np.where((freqs >= 2000) & (smooth_p99 > noise_floor_p99 + 8.0))[0]
    cutoff_p99_hz = float(freqs[above_floor[-1]]) if len(above_floor) > 0 else 0.0

    # Band energy summary (p99 & mean)
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

    # Check step around 8000, 11025, 12000, 16000 Hz (+/- 300 Hz vs +300..+900 Hz)
    step_checks = {}
    for edge in [8000, 11025, 12000, 16000, 18000, 19000, 20000]:
        if edge + 800 < sr / 2:
            below = (freqs >= edge - 600) & (freqs < edge - 100)
            above = (freqs > edge + 100) & (freqs <= edge + 600)
            drop_p99 = float(np.mean(p99_db[below]) - np.mean(p99_db[above]))
            step_checks[f"{edge}Hz"] = round(drop_p99, 2)

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
        "estimated_cutoff_p99_hz": round(cutoff_p99_hz, 1),
        "band_stats": band_stats,
        "edge_drops_db": step_checks,
    }


def reencode_saturation_test(filepath: str, start_sec: float, duration_sec: float) -> dict:
    results = {}
    for q in [0, 2, 4]:
        cmd = [
            FFMPEG, "-v", "error",
            "-ss", f"{start_sec:.3f}",
            "-t", f"{duration_sec:.3f}",
            "-i", filepath,
            "-c:a", "libmp3lame",
            "-q:a", str(q),
            "-f", "mp3",
            "pipe:1",
        ]
        res = subprocess.run(cmd, capture_output=True, check=True)
        size_bytes = len(res.stdout)
        kbps = (size_bytes * 8) / (duration_sec * 1000.0)
        results[f"vbr_q{q}_kbps"] = round(kbps, 1)
    return results


REF_MARKERS = [
    (8.0, "8 kHz (~32-48 kbps | 16k SR)"),
    (11.025, "11.025 kHz (~64 kbps | 22k SR)"),
    (12.0, "12 kHz (~64-80 kbps | 24k SR)"),
    (16.0, "16 kHz (~128 kbps MP3 / AAC)"),
    (18.0, "18 kHz (~192 kbps)"),
    (20.0, "20 kHz (~256-320 kbps)"),
]


def plot_spectrogram(spec_data: dict, title: str, out_path: Path, sr: int):
    freqs = spec_data["freqs"]
    times = spec_data["times"]
    mag_db = spec_data["mag_db"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [1.4, 1]})

    vmax = float(np.percentile(mag_db, 99.5))
    vmin = max(vmax - 95, -120)

    im = ax1.pcolormesh(times, freqs / 1000.0, mag_db, shading="auto", cmap="inferno", vmin=vmin, vmax=vmax)
    ax1.set_title(title, fontsize=12, fontweight="bold")
    ax1.set_ylabel("Frequency (kHz)")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylim(0, sr / 2000.0)
    for ref, lbl in REF_MARKERS:
        if ref < sr / 2000.0:
            ax1.axhline(ref, color="cyan", linestyle="--", linewidth=0.8, alpha=0.65)
            ax1.text(times[0] + 0.3, ref + 0.25, lbl, color="cyan", fontsize=7.5)
    cbar = fig.colorbar(im, ax=ax1, pad=0.01)
    cbar.set_label("Magnitude (dB)")

    # Zoom 6 - Nyquist
    ax2.pcolormesh(times, freqs / 1000.0, mag_db, shading="auto", cmap="inferno", vmin=vmin, vmax=vmax)
    ax2.set_title("Upper Band Zoom (6 kHz - Nyquist)", fontsize=10)
    ax2.set_ylabel("Frequency (kHz)")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylim(6.0, sr / 2000.0)
    for ref, lbl in REF_MARKERS:
        if 6.0 < ref < sr / 2000.0:
            ax2.axhline(ref, color="cyan", linestyle="--", linewidth=0.8, alpha=0.75)
            ax2.text(times[0] + 0.3, ref + 0.2, lbl, color="cyan", fontsize=7.5)

    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_summary_psd(segment_specs: list, out_path: Path, sr: int):
    freqs = segment_specs[0]["spec"]["freqs"]
    all_p99 = np.max([s["spec"]["p99_db"] for s in segment_specs], axis=0)
    all_mean = np.mean([s["spec"]["mean_db"] for s in segment_specs], axis=0)

    fig, ax = plt.subplots(figsize=(13, 6))
    for s in segment_specs:
        ax.plot(freqs / 1000.0, s["spec"]["p99_db"], alpha=0.35, linewidth=1.0, label=f"p99: {s['label']}")
    ax.plot(freqs / 1000.0, all_p99, color="crimson", linewidth=2.0, label="Max p99 across all segments")
    ax.plot(freqs / 1000.0, all_mean, color="navy", linewidth=1.8, label="Mean active speech spectrum")

    for ref, lbl in REF_MARKERS:
        if ref < sr / 2000.0:
            ax.axvline(ref, color="gray", linestyle="--", linewidth=0.9, alpha=0.7)
            ax.text(ref + 0.15, np.max(all_p99) - 2, lbl, rotation=90, va="top", fontsize=7.5, color="#222")

    ax.set_title("Aggregate Spectrum Profile (Active Speech + Intro/Outro)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Frequency (kHz)")
    ax.set_ylabel("Level (dB)")
    ax.set_xlim(0, sr / 2000.0)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left", fontsize=8, ncol=2)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    print("1. Probing file metadata...")
    probe = run_ffprobe(TARGET_FILE)
    fmt = probe["format"]
    stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    duration = float(fmt["duration"])
    sr = int(stream["sample_rate"])
    channels = int(stream["channels"])
    declared_kbps = round(int(fmt["bit_rate"]) / 1000.0, 2)

    print("2. Parsing binary MP3 frames & Xing/LAME headers...")
    binary_info = analyze_mp3_binary(TARGET_FILE)

    print("3. Sampling 7 segments across the audiobook...")
    positions = [
        ("00_intro_0_30s", 0.0, 30.0),
        ("01_intro_30_60s", 30.0, 30.0),
        ("02_20pct", duration * 0.20, 30.0),
        ("03_40pct", duration * 0.40, 30.0),
        ("04_60pct", duration * 0.60, 30.0),
        ("05_80pct", duration * 0.80, 30.0),
        ("06_outro_last_60s", max(0.0, duration - 60.0), 55.0),
    ]

    segment_results = []
    richest_seg = None
    richest_high_energy = -999.0

    for label, start_s, dur_s in positions:
        audio = decode_segment(TARGET_FILE, start_s, dur_s, sr, channels)
        stereo_info = analyze_stereo(audio)
        mono = np.mean(audio, axis=1)
        spec = compute_spectrum_metrics(mono, sr)

        # Measure energy in 8-16 kHz to find richest speech segment
        e_high = spec["band_stats"].get("8000-11025Hz", {}).get("p99_db", -120)
        if label.startswith("02_") or label.startswith("03_") or label.startswith("04_") or label.startswith("05_"):
            if e_high > richest_high_energy:
                richest_high_energy = e_high
                richest_seg = (label, start_s, dur_s, spec)

        segment_results.append({
            "label": label,
            "start_sec": round(start_s, 1),
            "duration_sec": dur_s,
            "stereo": stereo_info,
            "spec": spec,
        })

    print("4. Plotting spectrograms and summary PSD...")
    plot_spectrogram(
        segment_results[0]["spec"],
        f"Intro Spectrogram (0-30s) | {Path(TARGET_FILE).name}",
        REPORT_DIR / "01_intro_spectrogram.png",
        sr,
    )
    if richest_seg:
        plot_spectrogram(
            richest_seg[3],
            f"Richest Speech Spectrogram ({richest_seg[0]} @ {richest_seg[1]:.0f}s)",
            REPORT_DIR / "02_richest_speech_spectrogram.png",
            sr,
        )
    plot_summary_psd(segment_results, REPORT_DIR / "03_summary_psd.png", sr)

    has_lame = check_libmp3lame()
    sat_test = {}
    if has_lame and richest_seg:
        print("5. Running VBR re-encoding saturation test...")
        sat_test["intro_0_60s"] = reencode_saturation_test(TARGET_FILE, 0.0, 60.0)
        sat_test["speech_60s"] = reencode_saturation_test(TARGET_FILE, richest_seg[1], 60.0)

    # Compute unambiguous verdict on real sample rate & upconvert
    max_drops = {
        edge: max(s["spec"]["edge_drops_db"].get(edge, 0.0) for s in segment_results)
        for edge in ["8000Hz", "11025Hz", "12000Hz", "16000Hz", "18000Hz", "19000Hz", "20000Hz"]
    }
    if max_drops["8000Hz"] > 18.0:
        real_sr = 16000
        oversampling = True
    elif max_drops["11025Hz"] > 18.0:
        real_sr = 22050
        oversampling = True
    elif max_drops["12000Hz"] > 18.0:
        real_sr = 24000
        oversampling = True
    else:
        real_sr = sr
        oversampling = False

    if max_drops["16000Hz"] > 18.0:
        cutoff_label = "16.0 кГц (~128 kbps MP3 / 96-128 kbps AAC)"
    elif max_drops["18000Hz"] > 18.0:
        cutoff_label = "18.0 кГц (~192 kbps)"
    elif max_drops["19000Hz"] > 18.0:
        cutoff_label = "19.0 кГц (~224-256 kbps)"
    else:
        cutoff_label = "20+ кГц (~256-320 kbps)"

    has_mp4_tags = any(k in fmt.get("tags", {}) for k in ("major_brand", "compatible_brands"))
    upconvert = oversampling or has_mp4_tags or (declared_kbps > 140 and max_drops["16000Hz"] > 18.0)

    verdict = {
        "real_sample_rate_hz": real_sr,
        "declared_sample_rate_hz": sr,
        "oversampling_detected": oversampling,
        "upconvert_detected": upconvert,
        "cutoff_and_bitrate_equivalent": cutoff_label,
        "inherited_mp4_tags": has_mp4_tags,
    }

    # Build clean JSON summary (excluding big numpy arrays)
    summary = {
        "file": TARGET_FILE,
        "duration_sec": round(duration, 2),
        "duration_hms": f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m {int(duration % 60)}s",
        "verdict": verdict,
        "ffprobe_stream": {
            "codec": stream.get("codec_name"),
            "sample_rate": sr,
            "channels": channels,
            "channel_layout": stream.get("channel_layout"),
            "declared_bitrate_kbps": declared_kbps,
            "tags": fmt.get("tags", {}),
        },
        "binary_analysis": binary_info,
        "has_libmp3lame": has_lame,
        "saturation_test": sat_test,
        "segments": [
            {
                "label": s["label"],
                "start_sec": s["start_sec"],
                "stereo": s["stereo"],
                "estimated_cutoff_p99_hz": s["spec"]["estimated_cutoff_p99_hz"],
                "noise_floor_p99_db": s["spec"]["noise_floor_p99_db"],
                "edge_drops_db": s["spec"]["edge_drops_db"],
                "band_stats": s["spec"]["band_stats"],
            }
            for s in segment_results
        ],
    }

    summary_path = REPORT_DIR / "analysis_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Done! Report saved to {summary_path}")


if __name__ == "__main__":
    main()
