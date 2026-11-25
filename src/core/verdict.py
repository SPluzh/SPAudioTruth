from __future__ import annotations

from typing import Any


def _classify_cutoff_and_bitrate(cutoff_hz: float, max_drops: dict[str, float], declared_sr: int) -> dict[str, Any]:
    """Map effective cutoff & brickwall drops to real bitrate equivalent and sample rate."""
    drop_8k = max_drops.get("8000Hz", 0.0)
    drop_11k = max_drops.get("11025Hz", 0.0)
    drop_12k = max_drops.get("12000Hz", 0.0)
    drop_16k = max_drops.get("16000Hz", 0.0)
    drop_18k = max_drops.get("18000Hz", 0.0)
    drop_19k = max_drops.get("19000Hz", 0.0)

    oversampling = False
    real_sr = declared_sr
    oversample_reason = ""

    if drop_8k >= 15.0 and declared_sr > 16000:
        real_sr = 16000
        oversampling = True
        oversample_reason = f"Sharp cutoff at 8.0 kHz (drop {drop_8k:.1f} dB) with declared sample rate {declared_sr} Hz"
    elif drop_11k >= 15.0 and declared_sr > 22050:
        real_sr = 22050
        oversampling = True
        oversample_reason = f"Sharp cutoff at 11.025 kHz (drop {drop_11k:.1f} dB) with declared sample rate {declared_sr} Hz"
    elif drop_12k >= 15.0 and declared_sr > 24000:
        real_sr = 24000
        oversampling = True
        oversample_reason = f"Sharp cutoff at 12.0 kHz (drop {drop_12k:.1f} dB) with declared sample rate {declared_sr} Hz"

    # Determine effective cutoff & bitrate equivalent
    if drop_8k >= 15.0 or (0 < cutoff_hz <= 8500):
        eq_min, eq_max = 32, 48
        eq_label = "32–48 kbps MP3 (or 16 kHz SR)"
        cutoff_desc = "~8.0 kHz"
        primary_drop = drop_8k
    elif drop_11k >= 15.0 or (8500 < cutoff_hz <= 11300):
        eq_min, eq_max = 56, 64
        eq_label = "56–64 kbps MP3 (or 22.05 kHz SR)"
        cutoff_desc = "~11.025 kHz"
        primary_drop = drop_11k
    elif drop_12k >= 15.0 or (11300 < cutoff_hz <= 12800):
        eq_min, eq_max = 64, 80
        eq_label = "64–80 kbps MP3 (or 24 kHz SR)"
        cutoff_desc = "~12.0 kHz"
        primary_drop = drop_12k
    elif drop_16k >= 15.0 or (12800 < cutoff_hz <= 16500):
        eq_min, eq_max = 96, 128
        eq_label = "~128 kbps MP3 / 96–128 kbps AAC"
        cutoff_desc = "~15.0–16.0 kHz"
        primary_drop = drop_16k
    elif drop_18k >= 15.0 or (16500 < cutoff_hz <= 18500):
        eq_min, eq_max = 160, 192
        eq_label = "~192 kbps MP3"
        cutoff_desc = "~17.5–18.5 kHz"
        primary_drop = drop_18k
    elif drop_19k >= 15.0 or (18500 < cutoff_hz <= 19800):
        eq_min, eq_max = 224, 256
        eq_label = "~224–256 kbps MP3"
        cutoff_desc = "~19.0–19.5 kHz"
        primary_drop = drop_19k
    else:
        eq_min, eq_max = 256, 320
        eq_label = "256–320 kbps MP3 / Lossless"
        cutoff_desc = f"{cutoff_hz / 1000.0:.1f} kHz" if cutoff_hz > 0 else "20.0+ kHz"
        primary_drop = max(max_drops.values(), default=0.0)

    return {
        "real_sample_rate_hz": real_sr,
        "oversampling_detected": oversampling,
        "oversample_reason": oversample_reason,
        "equivalent_min_kbps": eq_min,
        "equivalent_max_kbps": eq_max,
        "equivalent_label": eq_label,
        "cutoff_desc": cutoff_desc,
        "primary_drop_db": round(primary_drop, 1),
    }


def evaluate_verdict(analysis: dict) -> dict:
    stream = analysis["ffprobe_stream"]
    sr = int(stream["sample_rate"])
    channels = int(stream["channels"])
    declared_kbps = float(stream["declared_bitrate_kbps"] or 0.0)
    tags = stream.get("tags") or {}
    binary = analysis.get("binary_analysis") or {}
    segments = analysis["segments"]

    # Aggregate cutoff and edge drops across segments
    cutoffs = [s["spec"]["estimated_cutoff_p99_hz"] for s in segments if s["spec"]["estimated_cutoff_p99_hz"] > 0]
    effective_cutoff_hz = round(max(cutoffs), 1) if cutoffs else 0.0

    all_edges = ["8000Hz", "11025Hz", "12000Hz", "16000Hz", "18000Hz", "19000Hz", "20000Hz"]
    max_drops = {
        edge: round(max((s["spec"]["edge_drops_db"].get(edge, 0.0) for s in segments), default=0.0), 2)
        for edge in all_edges
    }

    cls = _classify_cutoff_and_bitrate(effective_cutoff_hz, max_drops, sr)
    eq_max = cls["equivalent_max_kbps"]

    # Overpay / waste ratio
    waste_pct = 0.0
    waste_text = "Bitrate matches the actual spectrum"
    if declared_kbps > 0 and declared_kbps > eq_max * 1.05:
        waste_pct = round(((declared_kbps / eq_max) - 1.0) * 100.0, 1)
        waste_text = f"Declared {declared_kbps:.1f} kbps, real ceiling ~{eq_max} kbps — ~{waste_pct:.0f}% wasted bitrate"

    # Stereo summary
    stereo_segs = [s["stereo"] for s in segments if s["stereo"].get("is_stereo")]
    if channels == 1 or not stereo_segs:
        stereo_mode = "Mono"
        avg_side_mid = None
        avg_corr = 1.0
        is_pseudo_stereo = False
    else:
        side_mids = [st["side_to_mid_db"] for st in stereo_segs if st.get("side_to_mid_db") is not None]
        corrs = [st["correlation"] for st in stereo_segs]
        avg_side_mid = round(sum(side_mids) / len(side_mids), 2) if side_mids else 0.0
        avg_corr = round(sum(corrs) / len(corrs), 4) if corrs else 1.0
        is_pseudo_stereo = all(st.get("pseudo_stereo", False) for st in stereo_segs)
        stereo_mode = "Pseudo-Stereo (L ≈ R)" if is_pseudo_stereo else "True Stereo"

    # Evidence checklist
    evidences = []

    # 1. Oversampling
    evidences.append({
        "id": "oversampling",
        "title": "Sample Rate Oversampling",
        "detected": cls["oversampling_detected"],
        "severity": "high" if cls["oversampling_detected"] else "info",
        "status_label": "Confirmed" if cls["oversampling_detected"] else "Not Detected",
        "details": cls["oversample_reason"] if cls["oversampling_detected"] else (
            f"No brickwall cutoffs matching 16/22.05/24 kHz Nyquist limits (SR {sr} Hz)."
        ),
    })

    # 2. Bitrate vs cutoff mismatch
    mismatch = False
    mismatch_details = "Declared bitrate is consistent with the measured spectral bandwidth."
    if declared_kbps > 140 and (max_drops["16000Hz"] >= 15.0 or (0 < effective_cutoff_hz <= 16500)):
        mismatch = True
        mismatch_details = (
            f"Bitrate {declared_kbps:.1f} kbps with a hard cutoff at {cls['cutoff_desc']} "
            f"(drop {max_drops['16000Hz']:.1f} dB at 16 kHz) is typical of transcoding from ~128 kbps."
        )
    elif declared_kbps > 96 and effective_cutoff_hz > 0 and effective_cutoff_hz <= 12800:
        mismatch = True
        mismatch_details = (
            f"Bitrate {declared_kbps:.1f} kbps with a {cls['cutoff_desc']} cutoff indicates artificially inflated bitrate."
        )
    elif declared_kbps > 210 and (max_drops["18000Hz"] >= 15.0 or (16500 < effective_cutoff_hz <= 18500)):
        mismatch = True
        mismatch_details = (
            f"Bitrate {declared_kbps:.1f} kbps with a {cls['cutoff_desc']} cutoff matches a ~192 kbps source."
        )
    evidences.append({
        "id": "bitrate_cutoff_mismatch",
        "title": "Bitrate vs. High-Frequency Cutoff Mismatch",
        "detected": mismatch,
        "severity": "high" if mismatch else "info",
        "status_label": "Confirmed" if mismatch else "Not Detected",
        "details": mismatch_details,
    })

    # 3. Inherited MP4 / Lavf container tags
    tag_keys_lower = {k.lower(): v for k, v in tags.items()}
    has_mp4_brands = any(k in tag_keys_lower for k in ("major_brand", "compatible_brands"))
    enc_tag = str(tag_keys_lower.get("encoder", ""))
    has_lavf = "lavf" in enc_tag.lower()
    tag_detected = has_mp4_brands or (has_lavf and mismatch)
    if has_mp4_brands:
        tag_details = (
            f"MP4 container tags found (major_brand={tag_keys_lower.get('major_brand', '-')}, "
            f"compatible_brands={tag_keys_lower.get('compatible_brands', '-')}"
            + (f", encoder={enc_tag}" if enc_tag else "")
            + ") — clear sign of transcoding from MP4/M4A/AAC."
        )
    elif has_lavf:
        tag_details = f"Container encoder tag: {enc_tag} (FFmpeg/libavformat)."
    else:
        tag_details = "No foreign MP4/AAC container tags detected."

    evidences.append({
        "id": "container_tags",
        "title": "Inherited Container / Codec Tags",
        "detected": tag_detected,
        "severity": "high" if has_mp4_brands else ("medium" if tag_detected else "info"),
        "status_label": "Confirmed" if tag_detected else "Not Detected",
        "details": tag_details,
    })

    # 4. Pseudo-stereo
    evidences.append({
        "id": "pseudo_stereo",
        "title": "Pseudo-Stereo (Duplicated Mono)",
        "detected": is_pseudo_stereo,
        "severity": "medium" if is_pseudo_stereo else "info",
        "status_label": "Confirmed" if is_pseudo_stereo else "Not Detected",
        "details": (
            f"L and R channels are nearly identical (Side/Mid = {avg_side_mid} dB, correlation {avg_corr})."
            if is_pseudo_stereo
            else (
                f"Genuine stereo separation (Side/Mid = {avg_side_mid} dB, correlation {avg_corr})."
                if avg_side_mid is not None
                else "Single-channel audio (Mono)."
            )
        ),
    })

    # 5. LAME lowpass mismatch
    xing_lame = binary.get("xing_lame") or {}
    lame = xing_lame.get("lame") or {}
    lame_lp = lame.get("lowpass_hz")
    lp_mismatch = False
    if lame_lp and effective_cutoff_hz > 0 and (lame_lp - effective_cutoff_hz) > 1500:
        lp_mismatch = True
        lp_details = f"LAME header specifies lowpass {lame_lp} Hz, but actual cutoff is at {effective_cutoff_hz:.0f} Hz."
    elif lame_lp:
        lp_details = f"LAME lowpass ({lame_lp} Hz) matches measured cutoff ({effective_cutoff_hz:.0f} Hz)."
    else:
        lp_details = "LAME lowpass header is absent (or non-LAME encoder was used)."

    evidences.append({
        "id": "lame_lowpass_mismatch",
        "title": "LAME Lowpass vs. Actual Cutoff Mismatch",
        "detected": lp_mismatch,
        "severity": "medium" if lp_mismatch else "info",
        "status_label": "Confirmed" if lp_mismatch else "Not Detected",
        "details": lp_details,
    })

    # 6. Heterogeneous frames / splices
    sampled_srs = binary.get("sampled_sample_rates") or {}
    sampled_chs = binary.get("sampled_channel_modes") or {}
    sampled_vers = binary.get("sampled_versions") or {}
    splice_detected = len(sampled_srs) > 1 or len(sampled_vers) > 1 or ("Mono" in sampled_chs and len(sampled_chs) > 1)
    if splice_detected:
        splice_details = (
            f"Heterogeneous MP3 frames detected: SR={sampled_srs}, versions={sampled_vers}, channels={sampled_chs}."
        )
    else:
        splice_details = "All sampled frames are uniform in sample rate and MPEG version."

    evidences.append({
        "id": "heterogeneous_frames",
        "title": "Heterogeneous Frames / Splices",
        "detected": splice_detected,
        "severity": "medium" if splice_detected else "info",
        "status_label": "Confirmed" if splice_detected else "Not Detected",
        "details": splice_details,
    })

    # Overall status
    high_count = sum(1 for e in evidences if e["detected"] and e["severity"] == "high")
    total_detected = sum(1 for e in evidences if e["detected"])

    if cls["oversampling_detected"] or (mismatch and has_mp4_brands) or high_count >= 2:
        status_code = "upconvert"
        status_title = "Upconvert Confirmed"
        if mismatch and has_mp4_brands:
            status_reason = f"Cutoff {cls['cutoff_desc']} + MP4/AAC tags at {declared_kbps:.0f} kbps"
        elif cls["oversampling_detected"]:
            status_reason = f"Oversampled from {cls['real_sample_rate_hz']} Hz"
        else:
            status_reason = "Multiple upconvert indicators detected"
    elif total_detected >= 1:
        status_code = "suspect"
        status_title = "Suspected Transcode"
        first_hit = next(e["title"] for e in evidences if e["detected"])
        status_reason = first_hit
    else:
        status_code = "clean"
        status_title = "Authentic Quality"
        status_reason = f"Spectrum matches declared bitrate ({declared_kbps:.0f} kbps)"

    return {
        "status_code": status_code,
        "status_title": status_title,
        "status_reason": status_reason,
        "effective_cutoff_hz": effective_cutoff_hz,
        "cutoff_desc": cls["cutoff_desc"],
        "primary_drop_db": cls["primary_drop_db"],
        "max_edge_drops_db": max_drops,
        "real_sample_rate_hz": cls["real_sample_rate_hz"],
        "declared_sample_rate_hz": sr,
        "oversampling_detected": cls["oversampling_detected"],
        "equivalent_min_kbps": cls["equivalent_min_kbps"],
        "equivalent_max_kbps": cls["equivalent_max_kbps"],
        "equivalent_label": cls["equivalent_label"],
        "declared_bitrate_kbps": declared_kbps,
        "waste_pct": waste_pct,
        "waste_text": waste_text,
        "stereo_mode": stereo_mode,
        "pseudo_stereo": is_pseudo_stereo,
        "avg_side_to_mid_db": avg_side_mid,
        "avg_correlation": avg_corr,
        "inherited_mp4_tags": has_mp4_brands,
        "evidences": evidences,
    }


def _estimate_vbr_kbps(
    q: int,
    nominal_stereo_kbps: float,
    target_channels: int,
    source_channels: int,
    sat_test: dict,
) -> int:
    """Estimate VBR average bitrate using saturation_test if available, else nominal."""
    measured_kbps = None
    if sat_test:
        samples = [
            seg_res for seg_res in sat_test.values()
            if isinstance(seg_res, dict)
        ]
        if samples:
            key = f"vbr_q{q}_kbps"
            vals = [s[key] for s in samples if key in s]
            if vals:
                measured_kbps = sum(vals) / len(vals)
            elif "vbr_q4_kbps" in samples[0]:
                q4_vals = [s["vbr_q4_kbps"] for s in samples if "vbr_q4_kbps" in s]
                if q4_vals:
                    q4_avg = sum(q4_vals) / len(q4_vals)
                    # Approximate ratio relative to -q:a 4 (~165 kbps nominal stereo)
                    ratio_map = {0: 1.48, 2: 1.15, 3: 1.06, 4: 1.0, 5: 0.79, 6: 0.70, 7: 0.61, 8: 0.48}
                    measured_kbps = q4_avg * ratio_map.get(q, 0.8)

    if measured_kbps is not None:
        est = measured_kbps
        if target_channels == 1 and source_channels >= 2:
            est *= 0.65
        return max(32, int(round(est)))

    est = nominal_stereo_kbps
    if target_channels == 1:
        est *= 0.68
    return max(32, int(round(est)))


def build_conversion_recommendations(analysis: dict, verdict: dict) -> dict:
    """Build conversion options to eliminate upconvert bloat without losing real HF spectrum."""
    file_size_mb = round(analysis["file_size_bytes"] / (1024.0 * 1024.0), 2)
    duration = max(float(analysis["duration_sec"]), 1.0)
    declared_kbps = float(verdict["declared_bitrate_kbps"] or 128.0)
    eq_max = int(verdict["equivalent_max_kbps"])
    effective_cutoff_hz = float(verdict.get("effective_cutoff_hz") or 0.0)
    channels = int(analysis["ffprobe_stream"]["channels"])
    sr = int(verdict["declared_sample_rate_hz"])
    real_sr = int(verdict["real_sample_rate_hz"])
    sat_test = analysis.get("saturation_test") or {}

    should_reencode = (
        verdict["status_code"] != "clean"
        or float(verdict.get("waste_pct") or 0.0) > 5.0
        or bool(verdict.get("oversampling_detected"))
        or bool(verdict.get("pseudo_stereo"))
    )

    if not should_reencode:
        return {
            "should_reencode": False,
            "current_size_mb": file_size_mb,
            "target_channels": channels,
            "channel_reason": "Original channel layout preserved.",
            "target_sample_rate_hz": sr,
            "sample_rate_reason": f"Source sample rate {sr} Hz is optimal.",
            "options": [],
            "recommended_option": None,
            "ffmpeg_command": "",
            "advice": (
                "Re-encoding is not recommended: the file matches its actual spectral quality. "
                "Keep the original file."
            ),
        }

    # Channel decision: Mono (-ac 1) ONLY for confirmed pseudo-stereo or already mono
    if channels == 1:
        target_channels = 1
        ch_reason = "Source is already Mono (-ac 1)."
    elif verdict["pseudo_stereo"]:
        target_channels = 1
        ch_reason = (
            "Pseudo-Stereo (L ≈ R) confirmed: downmixing to Mono (-ac 1) "
            "preserves all information and saves bitrate."
        )
    else:
        target_channels = channels
        ch_reason = "Preserve True Stereo (-ac 2) to avoid losing stereo separation."

    # Sample rate decision: reduce ONLY if oversampling is confirmed
    if verdict["oversampling_detected"] and real_sr < sr:
        target_sr = real_sr
        sr_reason = f"Reduce sample rate to {real_sr} Hz (oversampling from {real_sr} to {sr} Hz confirmed)."
    else:
        target_sr = sr
        sr_reason = f"Keep source sample rate {sr} Hz (no oversampling detected)."

    is_mono = target_channels == 1

    # Select CBR, VBR (gentle & optimal), AAC, and Opus tiers preserving effective_cutoff_hz
    if eq_max <= 48:
        mp3_cbr = 48
        vbr_specs = [
            ("MP3 VBR (Optimal -q:a 8)", 8, 75.0, "~11–12 kHz", "Compact VBR for ~8 kHz bandwidth"),
        ]
        aac_kbps = 32 if is_mono else 48
        opus_kbps = 28 if is_mono else 40
    elif eq_max <= 80:
        mp3_cbr = 64 if is_mono else (64 if eq_max <= 64 else 80)
        vbr_specs = [
            ("MP3 VBR (Gentle -q:a 6)", 6, 115.0, "~15.0 kHz", "Extra HF headroom for ~11–12 kHz bandwidth"),
            ("MP3 VBR (Optimal -q:a 7)", 7, 100.0, "~14.0 kHz", "Space-saving VBR without clipping ~11–12 kHz"),
        ]
        aac_kbps = 48 if is_mono else 64
        opus_kbps = 40 if is_mono else 56
    elif eq_max <= 128:
        mp3_cbr = 96 if is_mono else 128
        vbr_specs = [
            ("MP3 VBR (Gentle -q:a 4)", 4, 165.0, "~17.5 kHz", "Minimal re-encoding artifacts (with headroom)"),
            ("MP3 VBR (Optimal -q:a 5)", 5, 130.0, "~16.5 kHz", "Matches 16 kHz band with maximum savings"),
        ]
        aac_kbps = 72 if is_mono else 104
        opus_kbps = 56 if is_mono else 88
    elif eq_max <= 192:
        mp3_cbr = 128 if is_mono else 192
        vbr_specs = [
            ("MP3 VBR (Gentle -q:a 2)", 2, 190.0, "~19.5 kHz", "High quality with headroom above ~18 kHz"),
            ("MP3 VBR (Optimal -q:a 3)", 3, 175.0, "~18.5 kHz", "Preserves ~18 kHz bandwidth accurately"),
        ]
        aac_kbps = 96 if is_mono else 144
        opus_kbps = 80 if is_mono else 128
    elif eq_max <= 256:
        mp3_cbr = 192 if is_mono else 256
        vbr_specs = [
            ("MP3 VBR (Gentle -q:a 2)", 2, 190.0, "~19.5 kHz", "Transparent VBR for ~19–19.5 kHz bandwidth"),
            ("MP3 VBR (Optimal -q:a 3)", 3, 175.0, "~18.5 kHz", "Slightly smaller with minimal difference"),
        ]
        aac_kbps = 128 if is_mono else 192
        opus_kbps = 96 if is_mono else 160
    else:
        mp3_cbr = 192 if is_mono else 256
        vbr_specs = [
            ("MP3 VBR (Gentle -q:a 0)", 0, 245.0, "~22.0 kHz", "Maximum VBR quality (V0)"),
            ("MP3 VBR (Optimal -q:a 2)", 2, 190.0, "~19.5 kHz", "Transparent V2 quality with size savings"),
        ]
        aac_kbps = 128 if is_mono else 192
        opus_kbps = 96 if is_mono else 160

    def _forecast(kbps: float) -> tuple[float, float]:
        est_mb = round((kbps * 1000.0 * duration) / (8.0 * 1024.0 * 1024.0), 2)
        sav = round((1.0 - est_mb / max(file_size_mb, 0.01)) * 100.0, 1)
        return est_mb, sav

    src_path = analysis["file"]
    stem = src_path.rsplit(".", 1)[0]
    ac_flag = f"-ac {target_channels}"
    ar_flag = f"-ar {target_sr} " if target_sr != sr else ""

    def _make_cmd(codec_args: str, ext: str) -> str:
        return f'ffmpeg -i "{src_path}" {ac_flag} {ar_flag}{codec_args} "{stem}_opt.{ext}"'

    options: list[dict[str, Any]] = []

    # Add VBR options first (preferred for removing upconvert bloat)
    for label, q_val, nom_kbps, lowpass_desc, note in vbr_specs:
        vbr_kbps = _estimate_vbr_kbps(q_val, nom_kbps, target_channels, channels, sat_test)
        est_mb, sav_pct = _forecast(vbr_kbps)
        codec_args = f"-c:a libmp3lame -q:a {q_val}"
        options.append({
            "format": label,
            "ext": "mp3",
            "codec_args": codec_args,
            "lowpass_desc": lowpass_desc,
            "target_kbps": vbr_kbps,
            "estimated_mb": est_mb,
            "savings_pct": sav_pct,
            "note": note,
            "ffmpeg_command": _make_cmd(codec_args, "mp3"),
        })

    # Add MP3 CBR, AAC/M4A, Opus
    cbr_note = (
        f"Matches source (preserves {effective_cutoff_hz / 1000.0:.1f} kHz cutoff)"
        if effective_cutoff_hz > 0
        else "Constant bitrate for maximum compatibility"
    )
    extra_specs = [
        ("MP3 CBR (Source Match)", "mp3", f"-c:a libmp3lame -b:a {mp3_cbr}k", mp3_cbr, verdict["cutoff_desc"], cbr_note),
        ("AAC / M4A", "m4a", f"-c:a aac -b:a {aac_kbps}k", aac_kbps, verdict["cutoff_desc"], "Modern format without losing detail"),
        ("Opus", "opus", f"-c:a libopus -b:a {opus_kbps}k", opus_kbps, verdict["cutoff_desc"], "Maximum space savings while preserving HF"),
    ]
    for name, fmt_ext, codec_arg, kbps_est, lp_desc, note in extra_specs:
        est_mb, sav_pct = _forecast(kbps_est)
        options.append({
            "format": name,
            "ext": fmt_ext,
            "codec_args": codec_arg,
            "lowpass_desc": lp_desc,
            "target_kbps": kbps_est,
            "estimated_mb": est_mb,
            "savings_pct": sav_pct,
            "note": note,
            "ffmpeg_command": _make_cmd(codec_arg, fmt_ext),
        })

    # Primary recommended option: optimal VBR (second VBR if two, else first)
    primary = options[1] if len(vbr_specs) > 1 else options[0]
    best_savings = max(o["savings_pct"] for o in options)

    if primary["savings_pct"] >= 10.0:
        advice = (
            f"Bitrate bloat detected ({declared_kbps:.0f} kbps vs. ~{eq_max} kbps real quality). "
            f"Recommended: {primary['format']} (~{primary['estimated_mb']:.1f} MB, "
            f"{primary['savings_pct']:.0f}% smaller, up to {best_savings:.0f}% with Opus) without HF loss."
        )
    else:
        advice = (
            f"Transcode signs detected, but size savings are modest (~{primary['savings_pct']:.0f}%). "
            "Re-encode only if needed."
        )

    return {
        "should_reencode": True,
        "current_size_mb": file_size_mb,
        "target_channels": target_channels,
        "channel_reason": ch_reason,
        "target_sample_rate_hz": target_sr,
        "sample_rate_reason": sr_reason,
        "options": options,
        "recommended_option": primary,
        "ffmpeg_command": primary["ffmpeg_command"],
        "advice": advice,
    }


def build_json_summary(analysis: dict, verdict: dict, recommendations: dict) -> dict:
    """Create a clean JSON-serializable report dict (without large numpy arrays)."""
    return {
        "file": analysis["file"],
        "file_size_bytes": analysis["file_size_bytes"],
        "duration_sec": analysis["duration_sec"],
        "duration_hms": analysis["duration_hms"],
        "verdict": verdict,
        "recommendations": recommendations,
        "ffprobe_stream": analysis["ffprobe_stream"],
        "binary_analysis": analysis["binary_analysis"],
        "has_libmp3lame": analysis["has_libmp3lame"],
        "saturation_test": analysis["saturation_test"],
        "segments": [
            {
                "label": s["label"],
                "display_name": s["display_name"],
                "start_sec": s["start_sec"],
                "duration_sec": s["duration_sec"],
                "sample_rate": s["sample_rate"],
                "stereo": s["stereo"],
                "estimated_cutoff_p99_hz": s["spec"]["estimated_cutoff_p99_hz"],
                "noise_floor_p99_db": s["spec"]["noise_floor_p99_db"],
                "edge_drops_db": s["spec"]["edge_drops_db"],
                "band_stats": s["spec"]["band_stats"],
            }
            for s in analysis["segments"]
        ],
    }
