from __future__ import annotations

import json
import os
from pathlib import Path

import torch
import torchaudio
from pyannote.audio import Pipeline


# ============================================================
# CONFIGURATION
# ============================================================

RECORDING_ID = 7

BACKEND_DIR = Path(__file__).resolve().parents[2]

STORAGE_DIR = BACKEND_DIR / "storage"

PROCESSED_DIR = (
    STORAGE_DIR
    / "processed"
    / f"recording_{RECORDING_ID}"
)

DIAGNOSTIC_FILE = (
    PROCESSED_DIR
    / "speaker_identity_validation_diagnostic"
    / "speaker_identity_validation_results.json"
)

OUTPUT_DIR = (
    PROCESSED_DIR
    / "manual_voice_anchor_diagnostic"
)

AUDIO_FILE = (
    STORAGE_DIR
    / "recordings"
    / "5"
    / "344d63fd75074ab3a4a19e745f7aa090.mp4"
)

SAMPLE_RATE = 16000


# ============================================================
# MANUALLY VERIFIED RELATIONSHIPS
# ============================================================
#
# These are based ONLY on the listening verification you
# already performed.
#
# You told us:
#
#   SPEAKER_02 sample 1
#   SPEAKER_02 sample 2
#   SPEAKER_04 sample 1
#
# are the SAME person.
#
# And:
#
#   SPEAKER_02 sample 4
#
# is a DIFFERENT person.
#
# We therefore need to map those samples to their actual
# segment indexes.
#
# The validation diagnostic uses segment indexes, so we first
# print all SPEAKER_02 / SPEAKER_04 candidates and then select
# the intended ones below.
#
# IMPORTANT:
# These are intentionally left as segment indexes rather than
# guessed timestamps.
#
# We will determine them from the existing diagnostic output.
# ============================================================


# Candidate segment indexes from the validation output.
#
# SPEAKER_02:
#   [003] 18.96 -> 20.92
#   [004] 27.39 -> 28.97
#   [010] 80.41 -> 81.91
#   [019] 148.38 -> 149.97
#   [025] 197.74 -> 201.00
#   [027] 207.04 -> 208.76
#   [030] 226.95 -> 228.45
#   [032] 243.45 -> 245.46
#   [040] 327.86 -> 329.51
#   [043] 370.35 -> 371.97
#   [048] 408.22 -> 410.63
#   [052] 459.45 -> 461.21
#   [053] 482.98 -> 485.05
#   [061] 537.70 -> 541.08
#   [062] 546.88 -> 550.29
#   [066] 569.83 -> 572.30
#
# SPEAKER_04:
#   [016] 124.72 -> 126.97
#   [024] 188.96 -> 193.03
#   [034] 278.42 -> 279.97
#   [042] 356.21 -> 359.98
#   [045] 387.46 -> 389.98
#   [049] 437.97 -> 440.03
#   [060] 533.52 -> 535.96
#   [065] 561.72 -> 563.83
#   [067] 587.97 -> 589.83
#   [068] 589.95 -> 591.50
#
#
# We will NOT assume which ones you meant by "sample 1",
# "sample 2", etc.
#
# Instead this script extracts a compact set of candidate
# samples for you to listen to and identify explicitly.
# ============================================================


CANDIDATE_SEGMENTS = [
    # SPEAKER_02
    3,
    4,
    10,
    19,
    25,
    27,
    30,
    32,
    40,
    43,
    48,
    52,
    53,
    61,
    62,
    66,

    # SPEAKER_04
    16,
    24,
    34,
    42,
    45,
    49,
    60,
    65,
    67,
    68,
]


# ============================================================
# LOAD JSON
# ============================================================

def load_validation():

    if not DIAGNOSTIC_FILE.exists():

        raise FileNotFoundError(
            f"Validation diagnostic not found:\n"
            f"{DIAGNOSTIC_FILE}"
        )

    with DIAGNOSTIC_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


# ============================================================
# LOAD AUDIO
# ============================================================

def load_audio():

    if not AUDIO_FILE.exists():

        raise FileNotFoundError(
            f"Recording file not found:\n"
            f"{AUDIO_FILE}"
        )

    print()
    print(
        f"Loading:\n{AUDIO_FILE}"
    )

    waveform, sample_rate = (
        torchaudio.load(
            str(AUDIO_FILE)
        )
    )

    # Mono
    if waveform.shape[0] > 1:

        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    # 16 kHz
    if sample_rate != SAMPLE_RATE:

        resampler = (
            torchaudio.transforms.Resample(
                sample_rate,
                SAMPLE_RATE,
            )
        )

        waveform = resampler(
            waveform
        )

        sample_rate = SAMPLE_RATE

    print(
        f"Sample rate: {sample_rate}"
    )

    print(
        f"Channels: {waveform.shape[0]}"
    )

    return waveform, sample_rate


# ============================================================
# EXTRACT SAMPLE
# ============================================================

def extract_sample(
    waveform,
    sample_rate,
    segment,
    output_file,
):

    start_sample = int(
        segment["start"]
        * sample_rate
    )

    end_sample = int(
        segment["end"]
        * sample_rate
    )

    audio = waveform[
        :,
        start_sample:end_sample,
    ]

    torchaudio.save(
        str(output_file),
        audio,
        sample_rate,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("MANUAL VOICE ANCHOR DIAGNOSTIC")
    print("=" * 80)

    data = load_validation()

    assignments = data.get(
        "assignments",
        [],
    )

    if not assignments:

        raise RuntimeError(
            "No assignments found in validation diagnostic."
        )

    assignment_by_index = {
        item["segment_index"]: item
        for item in assignments
    }

    waveform, sample_rate = (
        load_audio()
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = []

    print()
    print(
        "Extracting candidate voice samples..."
    )

    for index in CANDIDATE_SEGMENTS:

        if index not in assignment_by_index:

            print(
                f"WARNING: segment {index} "
                f"not found."
            )

            continue

        segment = assignment_by_index[
            index
        ]

        original = segment[
            "original_speaker"
        ]

        output_file = (
            OUTPUT_DIR
            / f"{index:03d}_"
            f"{original}_"
            f"{segment['start']:.2f}_"
            f"{segment['end']:.2f}.wav"
        )

        extract_sample(
            waveform,
            sample_rate,
            segment,
            output_file,
        )

        manifest.append(
            {
                "segment_index":
                    index,

                "original_speaker":
                    original,

                "start":
                    segment["start"],

                "end":
                    segment["end"],

                "duration":
                    segment["duration"],

                "best_candidate":
                    segment.get(
                        "best_candidate"
                    ),

                "best_score":
                    segment.get(
                        "best_score"
                    ),

                "status":
                    segment.get(
                        "status"
                    ),

                "file":
                    str(output_file),
            }
        )

        print(
            f"[{index:03d}] "
            f"{original} "
            f"{segment['start']:.2f} -> "
            f"{segment['end']:.2f}"
        )

    manifest_file = (
        OUTPUT_DIR
        / "manifest.json"
    )

    with manifest_file.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
        )

    print()
    print("=" * 80)
    print("SAMPLES CREATED")
    print("=" * 80)

    print(
        f"Directory:\n{OUTPUT_DIR}"
    )

    print()
    print(
        f"Manifest:\n{manifest_file}"
    )

    print()
    print(
        f"Total samples: "
        f"{len(manifest)}"
    )


if __name__ == "__main__":
    main()