"""Source-ID aligned synthetic sampled-RGB labels, never policy observations."""

import math

from media_rl.native_frame_metrics import summarize_native_frames

QUALITY_PROTOCOL = dict(
    metric="paired_sampled_rgb_psnr",
    width=640,
    height=360,
    grid_step=16,
    grid_start=8,
    exclude_marker_y_min=318,
    exclude_marker_y_max=347,
    max_pixel_value=255,
    channels_per_frame=2400,
    source="deterministic generated canvas; source ID decoded from received pixels",
    labels_only=True,
)


def compute_rgb_quality(observed, reference):
    if not observed or len(observed) != len(reference) or len(observed) % 3:
        raise ValueError("aligned nonempty RGB samples required")
    if any(type(x) is not int or not 0 <= x <= 255 for x in (*observed, *reference)):
        raise ValueError("byte RGB samples required")
    mse = sum((a - b) ** 2 for a, b in zip(observed, reference, strict=True)) / len(observed)
    return dict(
        rgb_mse=mse,
        psnr_db=None if mse == 0 else 10 * math.log10(255**2 / mse),
        exact_match=mse == 0,
        channels=len(observed),
    )


def summarize_native_quality(evidence):
    """Independent pixel math + raw-CRC verified opportunity weighted label utility.

    Utility is mean on-time sampled PSNR dB per eligible source request (zero
    for missed/late/unidentified frames), capped at 100 dB for exact matches.
    It is a synthetic research proxy, NOT human perceptual QoE or native capture.
    """
    frame = summarize_native_frames(evidence)
    if evidence["quality_protocol"] != QUALITY_PROTOCOL or not frame["measurement_qualified"]:
        raise ValueError("qualified pixel identities and declared RGB sampling required")
    first = {}
    pairs = 0
    for row in evidence["observations"]:
        quality = row.get("quality")
        if not row.get("known_source"):
            if quality is not None:
                raise ValueError("quality assigned to unidentified source")
            continue
        if quality is None:
            raise ValueError("known readback missing paired RGB samples")
        computed = compute_rgb_quality(quality["observed_rgb"], quality["reference_rgb"])
        if (
            computed["channels"] != 2400
            or quality["channels"] != 2400
            or quality["exact_match"] is not computed["exact_match"]
            or type(quality["rgb_mse"]) not in (int, float)
            or not math.isfinite(quality["rgb_mse"])
            or abs(quality["rgb_mse"] - computed["rgb_mse"]) > 1e-10
        ):
            raise ValueError("paired pixel MSE/geometry mismatch")
        if computed["psnr_db"] is None:
            if quality["psnr_db"] is not None:
                raise ValueError("exact match serialized as finite/infinite PSNR")
        elif (
            type(quality["psnr_db"]) not in (int, float)
            or not math.isfinite(quality["psnr_db"])
            or abs(quality["psnr_db"] - computed["psnr_db"]) > 1e-9
        ):
            raise ValueError("paired pixel PSNR mismatch")
        pairs += 1
        first.setdefault(row["source_id"], (row["readback_ms"], computed))
    start, cutoff = evidence["measurement_start_ms"], evidence["measurement_cutoff_ms"]
    deadline = evidence["protocol"]["deadline_ms"]
    labels = []
    for source in evidence["sources"]:
        born = source["capture_request_ms"]
        if born < start or born + deadline > cutoff:
            continue
        observed = first.get(source["source_id"])
        ontime = observed is not None and observed[0] - born <= deadline
        psnr = (
            100 if observed and observed[1]["exact_match"] else observed[1]["psnr_db"] if observed else None
        )
        contribution = min(100, max(0, psnr)) if ontime else 0
        labels.append(
            dict(
                source_id=source["source_id"],
                capture_request_ms=born,
                phase=source["phase"],
                decision_id=source.get("decision_id"),
                action_transition_inflight=source.get("action_transition_inflight"),
                encoder_cap_bps=source.get("encoder_cap_bps"),
                receiver_target_ms=source.get("receiver_target_ms"),
                identifiable_ontime=ontime,
                readback_age_ms=observed[0] - born if observed else None,
                rgb_mse=observed[1]["rgb_mse"] if observed else None,
                psnr_db=psnr,
                ontime_sampled_psnr_contribution=contribution,
            )
        )
    if (
        len(labels) != frame["overall"]["eligible"]
        or sum(x["identifiable_ontime"] for x in labels) != frame["overall"]["identifiable_ontime"]
    ):
        raise ValueError("quality opportunity denominator mismatch")
    utility = sum(x["ontime_sampled_psnr_contribution"] for x in labels) / len(labels) if labels else None
    return dict(
        metric="ontime_sampled_rgb_psnr_db_per_eligible_source_request",
        research_proxy_not_perceptual_QoE=True,
        exact_match_psnr_cap_db=100,
        verified_pairs=pairs,
        eligible_requests=len(labels),
        identified_ontime=sum(x["identifiable_ontime"] for x in labels),
        utility=utility,
        source_labels=labels,
        physical_capture_or_scanout_verified=False,
    )
