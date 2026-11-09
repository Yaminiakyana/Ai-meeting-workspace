from typing import Any


MIN_SPEAKER_SEGMENT_DURATION = 0.20
MIN_SPEAKER_OVERLAP = 0.03


def calculate_overlap(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
) -> float:
    overlap_start = max(start_a, start_b)
    overlap_end = min(end_a, end_b)

    return max(
        0.0,
        overlap_end - overlap_start,
    )


def clean_diarization_segments(
    diarization_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cleaned = []

    for segment in diarization_segments:
        start = float(segment["start_time"])
        end = float(segment["end_time"])

        if end <= start:
            continue

        if (
            end - start
            < MIN_SPEAKER_SEGMENT_DURATION
        ):
            continue

        cleaned.append(
            {
                **segment,
                "start_time": start,
                "end_time": end,
            }
        )

    return cleaned


def find_speaker_for_word(
    word_start: float,
    word_end: float,
    diarization_segments: list[dict[str, Any]],
) -> str | None:

    best_speaker = None
    best_overlap = 0.0

    for segment in diarization_segments:

        overlap = calculate_overlap(
            word_start,
            word_end,
            segment["start_time"],
            segment["end_time"],
        )

        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = segment["speaker_label"]

    if best_overlap < MIN_SPEAKER_OVERLAP:
        return None

    return best_speaker


def align_words_with_speakers(
    words: list[dict[str, Any]],
    diarization_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    cleaned_segments = (
        clean_diarization_segments(
            diarization_segments
        )
    )

    aligned_words = []

    for word in words:

        word_start = float(word["start"])
        word_end = float(word["end"])

        speaker_label = find_speaker_for_word(
            word_start=word_start,
            word_end=word_end,
            diarization_segments=cleaned_segments,
        )

        aligned_words.append(
            {
                "word": word["word"].strip(),
                "start_time": word_start,
                "end_time": word_end,
                "speaker_label": speaker_label,
            }
        )

    return aligned_words


def group_words_by_speaker(
    aligned_words: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    if not aligned_words:
        return []

    grouped = []

    current = None

    for word in aligned_words:

        speaker = word["speaker_label"]

        # If a word falls into a tiny diarization gap,
        # inherit the previous speaker rather than creating
        # an UNKNOWN transcript segment.
        if speaker is None and current is not None:
            speaker = current["speaker_label"]

        if current is None:

            current = {
                "speaker_label": speaker,
                "start_time": word["start_time"],
                "end_time": word["end_time"],
                "text": word["word"],
            }

            continue

        if (
            current["speaker_label"]
            == speaker
        ):

            current["end_time"] = (
                word["end_time"]
            )

            if current["text"]:
                current["text"] += " "

            current["text"] += word["word"]

        else:

            grouped.append(current)

            current = {
                "speaker_label": speaker,
                "start_time": word["start_time"],
                "end_time": word["end_time"],
                "text": word["word"],
            }

    if current is not None:
        grouped.append(current)

    return grouped