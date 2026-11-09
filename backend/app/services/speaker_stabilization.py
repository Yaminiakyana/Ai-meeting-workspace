
from __future__ import annotations

from typing import Any


def _get_timestamp(
    segment: dict[str, Any],
    primary_key: str,
    fallback_key: str,
) -> float:
    """Read timestamps from either supported segment schema."""
    value = segment.get(primary_key)

    if value is None:
        value = segment.get(fallback_key)

    if value is None:
        raise ValueError(
            f"Segment is missing '{primary_key}' and '{fallback_key}'. "
            f"Available keys: {list(segment.keys())}"
        )

    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid timestamp value {value!r} "
            f"for segment keys {list(segment.keys())}"
        ) from exc


def normalize_segments(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Normalize segment timestamps and speaker labels.

    Accepted timestamp fields:
        start_time / end_time
        start / end

    Accepted speaker fields:
        speaker_label
        speaker
        speaker_id

    The normalized output uses start_time/end_time and
    speaker_label, as expected by the transcript pipeline.
    """
    normalized: list[dict[str, Any]] = []

    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise TypeError(
                f"Segment at index {index} must be a dictionary; "
                f"received {type(segment).__name__}."
            )

        start = _get_timestamp(
            segment,
            "start_time",
            "start",
        )
        end = _get_timestamp(
            segment,
            "end_time",
            "end",
        )

        if start < 0:
            raise ValueError(
                f"Segment {index} has a negative start time: {start}"
            )

        if end <= start:
            # Ignore empty or invalid intervals rather than creating
            # negative-duration transcript segments.
            continue

        speaker_label = segment.get("speaker_label")

        if speaker_label is None:
            speaker_label = segment.get("speaker")

        if speaker_label is None:
            speaker_label = segment.get("speaker_id")

        item = dict(segment)
        item["start_time"] = start
        item["end_time"] = end
        item["speaker_label"] = (
            str(speaker_label)
            if speaker_label is not None
            else None
        )

        # Keep any existing extra metadata, including text and words.
        normalized.append(item)

    normalized.sort(
        key=lambda item: (
            item["start_time"],
            item["end_time"],
        )
    )

    return normalized


def stabilize_speaker_segments(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Normalize and chronologically order speaker segments.

    This function intentionally does not guess speaker identities,
    merge different speakers, or use text/grammar heuristics.
    """
    if not segments:
        return []

    normalized = normalize_segments(segments)

    print(
        "[Speaker stabilization] "
        f"Input segments: {len(segments)}; "
        f"valid normalized segments: {len(normalized)}"
    )

    return normalized
