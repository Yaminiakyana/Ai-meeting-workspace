from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torchaudio


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RECORDING_ID = 7

RECORDING_PATH = (
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
    / f"recording_{RECORDING_ID}"
    / "speaker_identity_diagnostic"
    / "speaker_identity_results.json"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "storage"
    / "processed"
    / f"recording_{RECORDING_ID}"
    / "five_speaker_anchor_diagnostic"
)

MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

TARGET_SPEAKERS = [
    "SPEAKER_00",
    "SPEAKER_01",
    "SPEAKER_06",
]

# We want several representative clips from each original label.
SAMPLES_PER_SPEAKER = 5

# Prefer clips of at least this duration.
MIN_DURATION = 2.0

# Avoid extremely long clips.
MAX_DURATION = 8.0

TARGET_SAMPLE_RATE = 16000


# ============================================================
# LOAD SEGMENTS
# ============================================================

def load_segments():

    if not DIAGNOSTIC_JSON.exists():
        raise FileNotFoundError(
            f"Diagnostic file not found:\n{DIAGNOSTIC_JSON}"
        )

    with DIAGNOSTIC_JSON.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    segments = data.get("segments", [])

    if not segments:
        raise RuntimeError(
            "No segments found in diagnostic JSON."
        )

    result = []

    for index, segment in enumerate(segments):

        result.append(
            {
                "segment_index": index,
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "duration": float(segment["duration"]),
            }
        )

    return result


# ============================================================
# LOAD DIARIZATION LABELS
# ============================================================

def load_diarization_segments():

    cache = (
        PROJECT_ROOT
        / "storage"
        / "processed"
        / f"recording_{RECORDING_ID}"
        / "diarization_clustering_experiments.json"
    )

    if not cache.exists():
        raise FileNotFoundError(
            f"Diarization cache not found:\n{cache}"
        )

    with cache.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    experiments = data.get("experiments", [])

    selected = None

    for experiment in experiments:

        name = experiment.get(
            "experiment",
            {},
        ).get("name")

        if name == "threshold_060_default":
            selected = experiment
            break

    if selected is None:
        raise RuntimeError(
            "threshold_060_default not found."
        )

    return selected["exclusive"]["segments"]


# ============================================================
# MATCH LABELS
# ============================================================

def attach_speaker_labels(
    identity_segments,
    diarization_segments,
):

    result = []

    for segment in identity_segments:

        best = None
        best_overlap = 0.0

        for diar in diarization_segments:

            overlap_start = max(
                segment["start"],
                float(diar["start"]),
            )

            overlap_end = min(
                segment["end"],
                float(diar["end"]),
            )

            overlap = max(
                0.0,
                overlap_end - overlap_start,
            )

            if overlap > best_overlap:

                best_overlap = overlap
                best = diar

        if best is None:
            continue

        result.append(
            {
                **segment,
                "speaker": best["speaker"],
            }
        )

    return result


# ============================================================
# SELECT REPRESENTATIVE SAMPLES
# ============================================================

def select_samples(segments):

    selected = {}

    for speaker in TARGET_SPEAKERS:

        candidates = [
            segment
            for segment in segments
            if segment["speaker"] == speaker
            and MIN_DURATION
            <= segment["duration"]
            <= MAX_DURATION
        ]

        # Sort longest first so we prefer cleaner,
        # more information-rich samples.
        candidates.sort(
            key=lambda x: x["duration"],
            reverse=True,
        )

        if len(candidates) <= SAMPLES_PER_SPEAKER:

            chosen = candidates

        else:

            # Rather than taking five adjacent clips,
            # spread them across the recording.
            positions = np.linspace(
                0,
                len(candidates) - 1,
                SAMPLES_PER_SPEAKER,
                dtype=int,
            )

            chosen = [
                candidates[int(position)]
                for position in positions
            ]

        selected[speaker] = chosen

    return selected


# ============================================================
# LOAD AUDIO
# ============================================================

def load_audio():

    if not RECORDING_PATH.exists():
        raise FileNotFoundError(
            f"Recording not found:\n{RECORDING_PATH}"
        )

    waveform, sample_rate = torchaudio.load(
        str(RECORDING_PATH)
    )

    if waveform.shape[0] > 1:
        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    if sample_rate != TARGET_SAMPLE_RATE:

        resampler = torchaudio.transforms.Resample(
            sample_rate,
            TARGET_SAMPLE_RATE,
        )

        waveform = resampler(waveform)

        sample_rate = TARGET_SAMPLE_RATE

    return waveform, sample_rate


# ============================================================
# EXPORT WAV
# ============================================================

def export_segment(
    waveform,
    sample_rate,
    segment,
    output_path,
):

    start_sample = int(
        segment["start"] * sample_rate
    )

    end_sample = int(
        segment["end"] * sample_rate
    )

    start_sample = max(
        0,
        start_sample,
    )

    end_sample = min(
        waveform.shape[-1],
        end_sample,
    )

    audio = waveform[
        0,
        start_sample:end_sample,
    ].numpy()

    sf.write(
        str(output_path),
        audio,
        sample_rate,
        subtype="PCM_16",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("FIVE-SPEAKER ANCHOR DIAGNOSTIC")
    print("=" * 70)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    identity_segments = load_segments()

    diarization_segments = (
        load_diarization_segments()
    )

    segments = attach_speaker_labels(
        identity_segments,
        diarization_segments,
    )

    print(
        f"Total usable segments: {len(segments)}"
    )

    selected = select_samples(
        segments
    )

    waveform, sample_rate = load_audio()

    manifest = {
        "recording_id": RECORDING_ID,
        "recording_path": str(
            RECORDING_PATH
        ),
        "sample_rate": sample_rate,
        "speakers": {},
    }

    sample_number = 1

    for speaker in TARGET_SPEAKERS:

        speaker_dir = (
            OUTPUT_DIR / speaker
        )

        speaker_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        chosen = selected.get(
            speaker,
            [],
        )

        print()
        print(
            f"{speaker}: "
            f"{len(chosen)} samples"
        )

        manifest["speakers"][speaker] = []

        for sample in chosen:

            filename = (
                f"{sample_number:02d}_"
                f"{speaker}_"
                f"{sample['segment_index']:03d}_"
                f"{sample['start']:.2f}_"
                f"{sample['end']:.2f}.wav"
            )

            output_path = (
                speaker_dir / filename
            )

            export_segment(
                waveform,
                sample_rate,
                sample,
                output_path,
            )

            entry = {
                "sample_number": sample_number,
                "segment_index": sample[
                    "segment_index"
                ],
                "speaker": speaker,
                "start": sample["start"],
                "end": sample["end"],
                "duration": sample["duration"],
                "file": str(output_path),
            }

            manifest["speakers"][speaker].append(
                entry
            )

            print(
                f"  {filename}"
            )

            sample_number += 1

    with MANIFEST_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
        )

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

    print(
        f"Samples saved to:\n{OUTPUT_DIR}"
    )

    print(
        f"Manifest:\n{MANIFEST_PATH}"
    )


if __name__ == "__main__":
    main()