from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AUDIO_PATH = (
    PROJECT_ROOT
    / "storage"
    / "recordings"
    / "5"
    / "344d63fd75074ab3a4a19e745f7aa090.mp4"
)

DIAGNOSTIC_JSON = (
    PROJECT_ROOT
    / "storage"
    / "processed"
    / "recording_7"
    / "diarization_clustering_experiments.json"
)

OUTPUT_ROOT = (
    PROJECT_ROOT
    / "storage"
    / "processed"
    / "recording_7"
    / "speaker_samples"
)


# ============================================================
# CONFIGURATION
# ============================================================

EXPERIMENT_NAME = "threshold_060_default"

# Speakers we specifically want to compare first.
TARGET_SPEAKERS = [
    "SPEAKER_02",
    "SPEAKER_04",
]

# We want reasonably long samples.
MIN_SEGMENT_DURATION = 1.5

# Maximum number of samples per speaker.
MAX_SAMPLES_PER_SPEAKER = 5

# Length of each extracted sample.
SAMPLE_DURATION = 8.0


# ============================================================
# LOAD DIAGNOSTIC
# ============================================================

def load_segments() -> list[dict]:

    if not DIAGNOSTIC_JSON.exists():
        raise FileNotFoundError(
            f"Diagnostic JSON not found:\n"
            f"{DIAGNOSTIC_JSON}"
        )

    with DIAGNOSTIC_JSON.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    for experiment in data["experiments"]:

        name = experiment["experiment"]["name"]

        if name == EXPERIMENT_NAME:

            return experiment["exclusive"]["segments"]

    raise RuntimeError(
        f"Experiment '{EXPERIMENT_NAME}' not found."
    )


# ============================================================
# SELECT SEGMENTS
# ============================================================

def select_segments(
    segments: list[dict],
) -> dict[str, list[dict]]:

    grouped: dict[str, list[dict]] = defaultdict(list)

    for segment in segments:

        speaker = segment["speaker"]

        if speaker not in TARGET_SPEAKERS:
            continue

        duration = float(segment["duration"])

        if duration < MIN_SEGMENT_DURATION:
            continue

        grouped[speaker].append(segment)

    for speaker in grouped:

        grouped[speaker].sort(
            key=lambda item: item["duration"],
            reverse=True,
        )

        grouped[speaker] = grouped[speaker][
            :MAX_SAMPLES_PER_SPEAKER
        ]

    return grouped


# ============================================================
# EXTRACT AUDIO
# ============================================================

def extract_sample(
    start: float,
    duration: float,
    output_path: Path,
) -> None:

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start),
        "-i",
        str(AUDIO_PATH),
        "-t",
        str(duration),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]

    print()
    print("Running:")
    print(" ".join(command))

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:

        print(result.stderr)

        raise RuntimeError(
            f"ffmpeg failed for {output_path}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("SPEAKER AUDIO SAMPLE EXTRACTION")
    print("=" * 80)

    print()
    print("Experiment:")
    print(EXPERIMENT_NAME)

    print()
    print("Audio:")
    print(AUDIO_PATH)

    if not AUDIO_PATH.exists():
        raise FileNotFoundError(
            f"Audio file does not exist:\n{AUDIO_PATH}"
        )

    segments = load_segments()

    grouped = select_segments(segments)

    print()
    print("=" * 80)
    print("SELECTED SEGMENTS")
    print("=" * 80)

    for speaker in TARGET_SPEAKERS:

        print()
        print(speaker)

        selected = grouped.get(
            speaker,
            [],
        )

        if not selected:

            print("  No suitable segments found.")

            continue

        for segment in selected:

            print(
                f"  "
                f"{segment['start']:.2f} - "
                f"{segment['end']:.2f} "
                f"({segment['duration']:.2f}s)"
            )

    # ========================================================
    # EXTRACT
    # ========================================================

    for speaker in TARGET_SPEAKERS:

        selected = grouped.get(
            speaker,
            [],
        )

        speaker_dir = (
            OUTPUT_ROOT
            / EXPERIMENT_NAME
            / speaker
        )

        speaker_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for index, segment in enumerate(
            selected,
            start=1,
        ):

            start = float(
                segment["start"]
            )

            segment_duration = float(
                segment["duration"]
            )

            # Give a little padding before the segment.
            actual_start = max(
                0.0,
                start - 0.5,
            )

            duration = min(
                SAMPLE_DURATION,
                segment_duration + 1.0,
            )

            output_path = (
                speaker_dir
                / f"sample_{index}.wav"
            )

            extract_sample(
                start=actual_start,
                duration=duration,
                output_path=output_path,
            )

    print()
    print("=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)

    print()
    print("Samples saved to:")

    print(
        OUTPUT_ROOT
        / EXPERIMENT_NAME
    )

    print()
    print("Compare these folders:")

    for speaker in TARGET_SPEAKERS:

        print(
            OUTPUT_ROOT
            / EXPERIMENT_NAME
            / speaker
        )


if __name__ == "__main__":
    main()