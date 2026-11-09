from typing import Any


# ============================================================
# V6 — Transcript-Aware Speaker Alignment
# ============================================================
#
# Pipeline:
#
# Whisper segments
#       +
# pyannote diarization
#       ↓
# segment speaker alignment
#       ↓
# transcript-aware validation
#       ↓
# conservative speaker correction
#
# Important:
# - Whisper is NOT rerun here.
# - pyannote is NOT rerun here.
# - Existing cached results are reused.
# - Strong diarization evidence is preserved.
# - Linguistic continuation is used only when appropriate.
# ============================================================


MIN_OVERLAP_SECONDS = 0.05

DOMINANT_SPEAKER_RATIO = 0.65
MIN_DOMINANT_OVERLAP = 0.20

FALLBACK_MIN_OVERLAP = 0.12
FALLBACK_MIN_RATIO = 0.25

NEIGHBOR_MAX_GAP = 1.50
NEIGHBOR_MAX_DURATION = 3.00

SHORT_SEGMENT_SECONDS = 1.20
VERY_SHORT_SEGMENT_SECONDS = 0.75

TINY_GAP_SECONDS = 0.20
MAX_CONTINUATION_GAP = 1.50

ABA_MAX_MIDDLE_DURATION = 1.50
ABA_MAX_GAP = 1.25

# V6
#
# When a segment looks like a continuation of the previous
# speaker's sentence, these thresholds control how aggressively
# we correct it.
#
# We intentionally require stronger linguistic evidence for
# longer segments.
MAX_LINGUISTIC_OVERRIDE_DURATION = 2.50
STRONG_CONTINUATION_MAX_GAP = 0.80


# ============================================================
# Basic utilities
# ============================================================

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



def normalize_diarization_segments(segments):
    """
    Normalize diarization segments to a consistent format.

    Supports both timestamp formats:
        {"start": 1.2, "end": 2.5, "speaker": "SPEAKER_00"}
        {"start_time": 1.2, "end_time": 2.5, "speaker_label": "SPEAKER_00"}

    Returns segments with start_time, end_time, and speaker_label.
    Does not modify the original segment dictionaries.
    """
    normalized_segments = []

    if not segments:
        return normalized_segments

    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise TypeError(
                f"Diarization segment {index} must be a dictionary; "
                f"got {type(segment).__name__}."
            )

        # Support both timestamp naming conventions.
        start_value = segment.get("start_time")
        if start_value is None:
            start_value = segment.get("start")

        end_value = segment.get("end_time")
        if end_value is None:
            end_value = segment.get("end")

        if start_value is None or end_value is None:
            raise ValueError(
                f"Diarization segment {index} has missing timestamps. "
                f"Available keys: {list(segment.keys())}"
            )

        try:
            start_time = float(start_value)
            end_time = float(end_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Diarization segment {index} has invalid timestamps: "
                f"start={start_value!r}, end={end_value!r}."
            ) from exc

        if start_time < 0:
            raise ValueError(
                f"Diarization segment {index} has negative start time: "
                f"{start_time}."
            )

        if end_time <= start_time:
            # Ignore invalid or zero-duration segments.
            continue

        # Support the speaker keys used by different pipeline stages.
        speaker_label = segment.get("speaker_label")
        if speaker_label is None:
            speaker_label = segment.get("speaker")
        if speaker_label is None:
            speaker_label = segment.get("speaker_id")

        normalized = dict(segment)
        normalized["start_time"] = start_time
        normalized["end_time"] = end_time
        normalized["speaker_label"] = (
            str(speaker_label)
            if speaker_label is not None
            else None
        )

        normalized_segments.append(normalized)

    normalized_segments.sort(
        key=lambda item: (
            item["start_time"],
            item["end_time"],
        )
    )

    return normalized_segments



def get_segment_duration(
    segment: dict[str, Any],
) -> float:
    return (
        float(segment["end"])
        - float(segment["start"])
    )


def get_gap(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> float:
    return max(
        0.0,
        float(current["start"])
        - float(previous["end"]),
    )


def ends_with_terminal_punctuation(
    text: str,
) -> bool:
    text = text.strip()

    if not text:
        return False

    return text[-1] in ".?!"


def ends_with_weak_punctuation(
    text: str,
) -> bool:
    text = text.strip()

    if not text:
        return False

    return text[-1] in ",;:-"


def starts_with_lowercase(
    text: str,
) -> bool:
    text = text.strip()

    if not text:
        return False

    return text[0].islower()


def get_first_word(
    text: str,
) -> str:
    text = text.strip()

    if not text:
        return ""

    cleaned = (
        text.replace(",", " ")
        .replace(".", " ")
        .replace("?", " ")
        .replace("!", " ")
        .replace(";", " ")
        .replace(":", " ")
        .replace("(", " ")
        .replace(")", " ")
    )

    parts = cleaned.split()

    if not parts:
        return ""

    return parts[0].lower()


def starts_like_continuation(
    text: str,
) -> bool:
    text = text.strip()

    if not text:
        return False

    if starts_with_lowercase(text):
        return True

    continuation_words = {
        "and",
        "or",
        "but",
        "so",
        "because",
        "while",
        "when",
        "which",
        "that",
        "than",
        "as",
        "if",
        "then",
        "also",
        "just",
        "to",
        "for",
        "with",
        "of",
        "in",
        "on",
        "from",
        "about",
        "like",
        "though",
        "although",
        "especially",
        "rather",
        "not",
    }

    return (
        get_first_word(text)
        in continuation_words
    )


def looks_like_incomplete_previous_sentence(
    text: str,
) -> bool:
    text = text.strip()

    if not text:
        return False

    if ends_with_terminal_punctuation(text):
        return False

    if ends_with_weak_punctuation(text):
        return True

    # Common incomplete constructions.
    incomplete_endings = {
        "and",
        "or",
        "but",
        "so",
        "because",
        "while",
        "when",
        "that",
        "which",
        "to",
        "of",
        "for",
        "with",
        "in",
        "on",
        "as",
        "than",
        "just",
        "not",
        "cannot",
        "can",
        "will",
        "would",
        "could",
        "should",
        "I",
        "you",
        "we",
        "they",
        "he",
        "she",
        "it",
        "my",
        "your",
        "the",
        "a",
        "an",
    }

    words = text.split()

    if not words:
        return False

    final_word = (
        words[-1]
        .strip(".,!?;:")
        .lower()
    )

    if final_word in incomplete_endings:
        return True

    # Whisper often produces segments that simply stop
    # before the grammatical continuation.
    #
    # If there is no terminal punctuation, consider it
    # incomplete unless it is clearly a complete short utterance.
    if len(words) >= 6:
        return True

    return False


def is_likely_sentence_continuation(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> bool:
    gap = get_gap(
        previous,
        current,
    )

    if gap > MAX_CONTINUATION_GAP:
        return False

    previous_text = (
        previous.get("text", "")
        .strip()
    )

    current_text = (
        current.get("text", "")
        .strip()
    )

    if not previous_text or not current_text:
        return False

    previous_incomplete = (
        looks_like_incomplete_previous_sentence(
            previous_text
        )
    )

    current_continuation = (
        starts_like_continuation(
            current_text
        )
    )

    # Strongest case:
    #
    # "... I just cannot"
    # "seem to catch a break."
    #
    if (
        previous_incomplete
        and current_continuation
    ):
        return True

    # Previous segment is clearly unfinished and
    # the next segment starts very quickly.
    if (
        previous_incomplete
        and gap <= STRONG_CONTINUATION_MAX_GAP
    ):
        return True

    return False


# ============================================================
# Speaker overlap calculation
# ============================================================

def calculate_speaker_overlaps(
    whisper_segment: dict[str, Any],
    diarization_segments: list[dict[str, Any]],
) -> dict[str, float]:

    start = float(
        whisper_segment["start"]
    )

    end = float(
        whisper_segment["end"]
    )

    speaker_overlaps: dict[str, float] = {}

    for diarization_segment in diarization_segments:
        overlap = calculate_overlap(
            start,
            end,
            float(
                diarization_segment[
                    "start_time"
                ]
            ),
            float(
                diarization_segment[
                    "end_time"
                ]
            ),
        )

        if overlap < MIN_OVERLAP_SECONDS:
            continue

        speaker = (
            diarization_segment[
                "speaker_label"
            ]
        )

        speaker_overlaps[speaker] = (
            speaker_overlaps.get(
                speaker,
                0.0,
            )
            + overlap
        )

    return speaker_overlaps


def select_dominant_speaker(
    speaker_overlaps: dict[str, float],
    segment_duration: float,
) -> tuple[str | None, float, str]:

    if not speaker_overlaps:
        return (
            None,
            0.0,
            "none",
        )

    ordered = sorted(
        speaker_overlaps.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    top_speaker = ordered[0][0]
    top_overlap = ordered[0][1]

    ratio = (
        top_overlap / segment_duration
        if segment_duration > 0
        else 0.0
    )

    if (
        top_overlap
        >= MIN_DOMINANT_OVERLAP
        and ratio
        >= DOMINANT_SPEAKER_RATIO
    ):
        return (
            top_speaker,
            top_overlap,
            "dominant",
        )

    if (
        top_overlap
        >= FALLBACK_MIN_OVERLAP
        and ratio
        >= FALLBACK_MIN_RATIO
    ):
        return (
            top_speaker,
            top_overlap,
            "fallback",
        )

    return (
        None,
        top_overlap,
        "weak",
    )


# ============================================================
# Whisper segment alignment
# ============================================================

def align_whisper_segments(
    whisper_segments: list[dict[str, Any]],
    diarization_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    diarization_segments = (
        normalize_diarization_segments(
            diarization_segments
        )
    )

    aligned = []

    for segment in whisper_segments:
        start = float(
            segment["start"]
        )

        end = float(
            segment["end"]
        )

        duration = max(
            0.0,
            end - start,
        )

        speaker_overlaps = (
            calculate_speaker_overlaps(
                segment,
                diarization_segments,
            )
        )

        speaker, selected_overlap, method = (
            select_dominant_speaker(
                speaker_overlaps,
                duration,
            )
        )

        confidence = (
            selected_overlap / duration
            if duration > 0 and speaker
            else 0.0
        )

        aligned.append(
            {
                "segment_index": segment.get(
                    "segment_index"
                ),
                "start": start,
                "end": end,
                "text": segment.get(
                    "text",
                    "",
                ).strip(),
                "words": segment.get(
                    "words",
                    [],
                ),
                "speaker_label": speaker,
                "speaker_confidence": confidence,
                "assignment_method": method,
                "speaker_overlaps": (
                    speaker_overlaps
                ),
            }
        )

    return aligned


# ============================================================
# Resolve unassigned segments
# ============================================================

def resolve_unassigned_segments(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    result = [
        segment.copy()
        for segment in segments
    ]

    for index, current in enumerate(
        result
    ):

        if current.get(
            "speaker_label"
        ) is not None:
            continue

        previous = (
            result[index - 1]
            if index > 0
            else None
        )

        following = (
            result[index + 1]
            if index + 1 < len(result)
            else None
        )

        duration = (
            get_segment_duration(
                current
            )
        )

        # ----------------------------------------------------
        # Previous + next agree
        # ----------------------------------------------------

        if previous and following:

            previous_speaker = (
                previous.get(
                    "speaker_label"
                )
            )

            next_speaker = (
                following.get(
                    "speaker_label"
                )
            )

            previous_gap = get_gap(
                previous,
                current,
            )

            next_gap = get_gap(
                current,
                following,
            )

            if (
                previous_speaker
                and previous_speaker
                == next_speaker
                and previous_gap
                <= NEIGHBOR_MAX_GAP
                and next_gap
                <= NEIGHBOR_MAX_GAP
                and duration
                <= NEIGHBOR_MAX_DURATION
            ):
                current[
                    "speaker_label"
                ] = previous_speaker

                current[
                    "speaker_confidence"
                ] = 0.40

                current[
                    "assignment_method"
                ] = "neighbor_consensus"

                continue

        # ----------------------------------------------------
        # Previous speaker
        # ----------------------------------------------------

        if previous:

            previous_speaker = (
                previous.get(
                    "speaker_label"
                )
            )

            previous_gap = get_gap(
                previous,
                current,
            )

            if (
                previous_speaker
                and previous_gap
                <= NEIGHBOR_MAX_GAP
                and duration
                <= NEIGHBOR_MAX_DURATION
            ):
                current[
                    "speaker_label"
                ] = previous_speaker

                current[
                    "speaker_confidence"
                ] = 0.25

                current[
                    "assignment_method"
                ] = "previous_neighbor"

                continue

        # ----------------------------------------------------
        # Next speaker
        # ----------------------------------------------------

        if following:

            next_speaker = (
                following.get(
                    "speaker_label"
                )
            )

            next_gap = get_gap(
                current,
                following,
            )

            if (
                next_speaker
                and next_gap
                <= NEIGHBOR_MAX_GAP
                and duration
                <= NEIGHBOR_MAX_DURATION
            ):
                current[
                    "speaker_label"
                ] = next_speaker

                current[
                    "speaker_confidence"
                ] = 0.20

                current[
                    "assignment_method"
                ] = "next_neighbor"

    return result


# ============================================================
# V6 — Transcript-aware correction
# ============================================================

def correct_transcript_continuations(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    result = [
        segment.copy()
        for segment in segments
    ]

    changes = 0

    for index in range(
        1,
        len(result),
    ):

        previous = result[index - 1]
        current = result[index]

        previous_speaker = (
            previous.get(
                "speaker_label"
            )
        )

        current_speaker = (
            current.get(
                "speaker_label"
            )
        )

        if not previous_speaker:
            continue

        if not current_speaker:
            continue

        if (
            previous_speaker
            == current_speaker
        ):
            continue

        current_duration = (
            get_segment_duration(
                current
            )
        )

        if (
            current_duration
            > MAX_LINGUISTIC_OVERRIDE_DURATION
        ):
            continue

        if not is_likely_sentence_continuation(
            previous,
            current,
        ):
            continue

        current_confidence = float(
            current.get(
                "speaker_confidence",
                0.0,
            )
        )

        current_method = current.get(
            "assignment_method"
        )

        gap = get_gap(
            previous,
            current,
        )

        # ----------------------------------------------------
        # Strong pyannote evidence:
        #
        # Do not override a strong assignment merely because
        # the text looks like a continuation.
        # ----------------------------------------------------

        if (
            current_method == "dominant"
            and current_confidence >= 0.85
        ):
            continue

        # ----------------------------------------------------
        # A tiny segment directly following an unfinished
        # sentence is highly suspicious.
        # ----------------------------------------------------

        if (
            current_duration
            <= VERY_SHORT_SEGMENT_SECONDS
            and gap
            <= STRONG_CONTINUATION_MAX_GAP
        ):
            current[
                "speaker_label"
            ] = previous_speaker

            current[
                "assignment_method"
            ] = (
                "transcript_continuation"
            )

            current[
                "speaker_confidence"
            ] = max(
                current_confidence,
                0.60,
            )

            changes += 1

            continue

        # ----------------------------------------------------
        # Longer continuation:
        #
        # Require stronger evidence from the text.
        # ----------------------------------------------------

        previous_text = (
            previous.get(
                "text",
                "",
            ).strip()
        )

        current_text = (
            current.get(
                "text",
                "",
            ).strip()
        )

        strong_previous_incomplete = (
            looks_like_incomplete_previous_sentence(
                previous_text
            )
        )

        strong_current_continuation = (
            starts_like_continuation(
                current_text
            )
        )

        if (
            strong_previous_incomplete
            and strong_current_continuation
            and gap
            <= STRONG_CONTINUATION_MAX_GAP
        ):
            current[
                "speaker_label"
            ] = previous_speaker

            current[
                "assignment_method"
            ] = (
                "strong_transcript_continuation"
            )

            current[
                "speaker_confidence"
            ] = max(
                current_confidence,
                0.55,
            )

            changes += 1

    print(
        "Transcript continuation "
        f"corrections: {changes}"
    )

    return result


# ============================================================
# A-B-A correction
# ============================================================

def correct_isolated_segment_switches(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    if len(segments) < 3:
        return segments

    result = [
        segment.copy()
        for segment in segments
    ]

    changes = 0

    for index in range(
        1,
        len(result) - 1,
    ):

        previous = result[index - 1]
        current = result[index]
        following = result[index + 1]

        previous_speaker = (
            previous.get(
                "speaker_label"
            )
        )

        current_speaker = (
            current.get(
                "speaker_label"
            )
        )

        following_speaker = (
            following.get(
                "speaker_label"
            )
        )

        if not (
            previous_speaker
            and current_speaker
            and following_speaker
        ):
            continue

        if not (
            previous_speaker
            == following_speaker
        ):
            continue

        if (
            current_speaker
            == previous_speaker
        ):
            continue

        duration = (
            get_segment_duration(
                current
            )
        )

        if (
            duration
            > ABA_MAX_MIDDLE_DURATION
        ):
            continue

        previous_gap = get_gap(
            previous,
            current,
        )

        next_gap = get_gap(
            current,
            following,
        )

        if (
            previous_gap
            > ABA_MAX_GAP
            or next_gap
            > ABA_MAX_GAP
        ):
            continue

        confidence = float(
            current.get(
                "speaker_confidence",
                0.0,
            )
        )

        method = current.get(
            "assignment_method"
        )

        if (
            method == "dominant"
            and confidence >= 0.80
        ):
            continue

        current[
            "speaker_label"
        ] = previous_speaker

        current[
            "assignment_method"
        ] = "aba_continuity"

        current[
            "speaker_confidence"
        ] = max(
            confidence,
            0.45,
        )

        changes += 1

    print(
        f"A-B-A corrections: {changes}"
    )

    return result


# ============================================================
# Short-turn continuity
# ============================================================

def correct_segment_continuity(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    result = [
        segment.copy()
        for segment in segments
    ]

    changes = 0

    for index in range(
        1,
        len(result),
    ):

        previous = result[index - 1]
        current = result[index]

        previous_speaker = (
            previous.get(
                "speaker_label"
            )
        )

        current_speaker = (
            current.get(
                "speaker_label"
            )
        )

        if not (
            previous_speaker
            and current_speaker
        ):
            continue

        if (
            previous_speaker
            == current_speaker
        ):
            continue

        duration = (
            get_segment_duration(
                current
            )
        )

        gap = get_gap(
            previous,
            current,
        )

        if not (
            duration
            <= VERY_SHORT_SEGMENT_SECONDS
            and gap
            <= TINY_GAP_SECONDS
        ):
            continue

        confidence = float(
            current.get(
                "speaker_confidence",
                0.0,
            )
        )

        method = current.get(
            "assignment_method"
        )

        if (
            method == "dominant"
            and confidence >= 0.85
        ):
            continue

        current[
            "speaker_label"
        ] = previous_speaker

        current[
            "assignment_method"
        ] = "short_turn_continuity"

        current[
            "speaker_confidence"
        ] = max(
            confidence,
            0.40,
        )

        changes += 1

    print(
        f"Short-turn corrections: {changes}"
    )

    return result


# ============================================================
# Merge same-speaker segments
# ============================================================

def merge_same_speaker_segments(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    if not segments:
        return []

    ordered = sorted(
        [
            segment.copy()
            for segment in segments
        ],
        key=lambda item: float(
            item["start"]
        ),
    )

    merged = []

    for current in ordered:

        if not current.get(
            "text",
            "",
        ).strip():
            continue

        if not merged:
            merged.append(current)
            continue

        previous = merged[-1]

        previous_speaker = (
            previous.get(
                "speaker_label"
            )
        )

        current_speaker = (
            current.get(
                "speaker_label"
            )
        )

        gap = max(
            0.0,
            float(current["start"])
            - float(previous["end"]),
        )

        if (
            previous_speaker
            and previous_speaker
            == current_speaker
            and gap <= 0.75
        ):

            previous["end"] = max(
                float(previous["end"]),
                float(current["end"]),
            )

            previous_text = (
                previous.get(
                    "text",
                    "",
                ).strip()
            )

            current_text = (
                current.get(
                    "text",
                    "",
                ).strip()
            )

            if current_text:

                if previous_text:
                    previous["text"] = (
                        previous_text
                        + " "
                        + current_text
                    )
                else:
                    previous["text"] = (
                        current_text
                    )

            previous[
                "speaker_confidence"
            ] = max(
                float(
                    previous.get(
                        "speaker_confidence",
                        0.0,
                    )
                ),
                float(
                    current.get(
                        "speaker_confidence",
                        0.0,
                    )
                ),
            )

            previous[
                "assignment_method"
            ] = "merged"

            continue

        merged.append(current)

    return merged


# ============================================================
# Legacy word alignment
# ============================================================

def align_words_with_speakers(
    words: list[dict[str, Any]],
    diarization_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    aligned_words = []

    diarization_segments = (
        normalize_diarization_segments(
            diarization_segments
        )
    )

    for word in words:

        word_start = float(
            word["start"]
        )

        word_end = float(
            word["end"]
        )

        best_speaker = None
        best_overlap = 0.0

        for segment in diarization_segments:

            overlap = calculate_overlap(
                word_start,
                word_end,
                float(
                    segment["start_time"]
                ),
                float(
                    segment["end_time"]
                ),
            )

            if overlap > best_overlap:

                best_overlap = overlap

                best_speaker = (
                    segment[
                        "speaker_label"
                    ]
                )

        aligned_words.append(
            {
                "word": word[
                    "word"
                ].strip(),
                "start_time": word_start,
                "end_time": word_end,
                "speaker_label": best_speaker,
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

        speaker = word.get(
            "speaker_label"
        )

        if (
            speaker is None
            and current is not None
        ):
            speaker = (
                current[
                    "speaker_label"
                ]
            )

        if current is None:

            current = {
                "speaker_label": speaker,
                "start_time": word[
                    "start_time"
                ],
                "end_time": word[
                    "end_time"
                ],
                "text": word["word"],
            }

            continue

        if (
            current[
                "speaker_label"
            ]
            == speaker
        ):

            current[
                "end_time"
            ] = word["end_time"]

            if current["text"]:
                current["text"] += " "

            current["text"] += word["word"]

        else:

            grouped.append(current)

            current = {
                "speaker_label": speaker,
                "start_time": word[
                    "start_time"
                ],
                "end_time": word[
                    "end_time"
                ],
                "text": word["word"],
            }

    if current is not None:
        grouped.append(current)

    return grouped