from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torchaudio
from pyannote.audio import Pipeline


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RECORDING_ID = 7

DIARIZATION_CACHE = (
    PROJECT_ROOT
    / "storage"
    / "processed"
    / f"recording_{RECORDING_ID}"
    / "diarization_clustering_experiments.json"
)

IDENTITY_DIAGNOSTIC = (
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
    / "manual_voice_identity_diagnostic"
)

OUTPUT_JSON = OUTPUT_DIR / "manual_voice_identity_results.json"

# Known physical recording discovered during the previous diagnostics.
RECORDING_PATH = (
    PROJECT_ROOT
    / "storage"
    / "recordings"
    / "5"
    / "344d63fd75074ab3a4a19e745f7aa090.mp4"
)

HF_TOKEN = None

EMBEDDING_SAMPLE_RATE = 16000

# Human-confirmed labels.
#
# The keys are the segment indexes from the identity diagnostic.
# A/B/C are arbitrary human voice identities.
#
# IMPORTANT:
# These are NOT the original Community-1 speaker IDs.
HUMAN_LABELS: Dict[str, Dict[int, str]] = {
    "SPEAKER_02": {
        3: "A",
        4: "B",
        10: "B",
        19: "B",
        25: "C",
        27: "C",
        30: "C",
        32: "A",
        40: "A",
        43: "B",
        48: "B",
        52: "A",
        53: "A",
        61: "A",
        62: "A",
        66: "B",
    },
    "SPEAKER_04": {
        16: "B",
        24: "A",
        34: "B",
        42: "B",
        45: "B",
        49: "A",
        60: "B",
        65: "A",
        67: "B",
        68: "B",
    },
}

# Only use reasonably long segments for the identity experiment.
MIN_SEGMENT_DURATION = 1.5

# Prototype construction.
#
# Every human-confirmed sample is used, but longer samples receive
# slightly more weight. This prevents a very short sample from
# dominating a prototype.
MIN_ANCHOR_DURATION = 1.5

# Classification thresholds.
#
# We deliberately keep these conservative. We do NOT want to force
# every segment into A/B/C.
STRONG_SIMILARITY = 0.72
SUPPORTING_SIMILARITY = 0.62

STRONG_MARGIN = 0.08
SUPPORTING_MARGIN = 0.05

# At least this many human anchor samples should support a strong
# identity assignment.
MIN_STRONG_SUPPORT = 2

# ============================================================
# UTILITY FUNCTIONS
# ============================================================


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)

    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)

    if a_norm == 0 or b_norm == 0:
        return 0.0

    return float(np.dot(a, b) / (a_norm * b_norm))


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32)
    norm = np.linalg.norm(vector)

    if norm == 0:
        return vector

    return vector / norm


def weighted_centroid(
    embeddings: List[np.ndarray],
    weights: List[float],
) -> np.ndarray:

    matrix = np.vstack(embeddings).astype(np.float32)
    weights_array = np.asarray(weights, dtype=np.float32)

    weights_array = weights_array / weights_array.sum()

    centroid = np.sum(
        matrix * weights_array[:, None],
        axis=0,
    )

    return l2_normalize(centroid)


# ============================================================
# LOAD CACHED DIARIZATION SEGMENTS
# ============================================================


def load_diarization_segments() -> List[dict]:

    if not DIARIZATION_CACHE.exists():
        raise FileNotFoundError(
            f"Diarization cache not found:\n{DIARIZATION_CACHE}"
        )

    with DIARIZATION_CACHE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    experiments = data.get("experiments", [])

    selected = None

    for experiment in experiments:
        name = experiment.get("experiment", {}).get("name")

        if name == "threshold_060_default":
            selected = experiment
            break

    if selected is None:
        raise RuntimeError(
            "Could not find threshold_060_default in diarization cache."
        )

    segments = selected["exclusive"]["segments"]

    result = []

    for segment in segments:

        duration = float(segment["duration"])

        if duration < MIN_SEGMENT_DURATION:
            continue

        result.append(
            {
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "duration": duration,
                "speaker": segment["speaker"],
            }
        )

    return result


# ============================================================
# LOAD IDENTITY SEGMENT INDEXES
# ============================================================


def load_identity_segments() -> List[dict]:

    if not IDENTITY_DIAGNOSTIC.exists():
        raise FileNotFoundError(
            f"Identity diagnostic not found:\n{IDENTITY_DIAGNOSTIC}"
        )

    with IDENTITY_DIAGNOSTIC.open("r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])

    if not segments:
        raise RuntimeError(
            "No segments found in speaker_identity_results.json"
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
# MATCH IDENTITY SEGMENTS TO DIARIZATION LABELS
# ============================================================


def match_speaker_labels(
    identity_segments: List[dict],
    diarization_segments: List[dict],
) -> List[dict]:

    result = []

    for segment in identity_segments:

        best_match = None
        best_overlap = 0.0

        start = segment["start"]
        end = segment["end"]

        for diar in diarization_segments:

            overlap_start = max(start, diar["start"])
            overlap_end = min(end, diar["end"])

            overlap = max(
                0.0,
                overlap_end - overlap_start,
            )

            if overlap > best_overlap:
                best_overlap = overlap
                best_match = diar

        if best_match is None:
            continue

        result.append(
            {
                **segment,
                "speaker": best_match["speaker"],
                "overlap": best_overlap,
            }
        )

    return result


# ============================================================
# LOAD COMMUNITY-1
# ============================================================


def load_pipeline():

    print()
    print("=" * 70)
    print("LOADING COMMUNITY-1")
    print("=" * 70)

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1",
        token=HF_TOKEN,
    )

    if pipeline is None:
        raise RuntimeError(
            "Could not load pyannote Community-1."
        )

    pipeline.to(torch.device("cpu"))

    embedding_model = pipeline._embedding

    print("Community-1 loaded.")
    print(f"Embedding dimension: {embedding_model.dimension}")
    print(f"Embedding sample rate: {embedding_model.sample_rate}")

    return pipeline, embedding_model


# ============================================================
# LOAD AUDIO
# ============================================================


def load_audio():

    if not RECORDING_PATH.exists():
        raise FileNotFoundError(
            f"Recording not found:\n{RECORDING_PATH}"
        )

    print()
    print("=" * 70)
    print("LOADING AUDIO")
    print("=" * 70)

    waveform, sample_rate = torchaudio.load(
        str(RECORDING_PATH)
    )

    print(f"Original sample rate: {sample_rate}")
    print(f"Original channels: {waveform.shape[0]}")

    # Convert stereo/multi-channel to mono.
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Resample if necessary.
    if sample_rate != EMBEDDING_SAMPLE_RATE:

        print(
            f"Resampling {sample_rate} Hz -> "
            f"{EMBEDDING_SAMPLE_RATE} Hz"
        )

        resampler = torchaudio.transforms.Resample(
            orig_freq=sample_rate,
            new_freq=EMBEDDING_SAMPLE_RATE,
        )

        waveform = resampler(waveform)

        sample_rate = EMBEDDING_SAMPLE_RATE

    print(f"Final sample rate: {sample_rate}")
    print(f"Final channels: {waveform.shape[0]}")

    return waveform, sample_rate


# ============================================================
# EMBEDDING EXTRACTION
# ============================================================


def extract_embedding(
    embedding_model,
    waveform: torch.Tensor,
    sample_rate: int,
    start: float,
    end: float,
) -> np.ndarray:

    start_sample = int(start * sample_rate)
    end_sample = int(end * sample_rate)

    start_sample = max(0, start_sample)
    end_sample = min(
        waveform.shape[-1],
        end_sample,
    )

    audio = waveform[
        :,
        start_sample:end_sample,
    ]

    if audio.shape[-1] < 400:
        raise ValueError(
            f"Segment too short for embedding: "
            f"{start:.2f}-{end:.2f}"
        )

    # Community-1's embedding API expects:
    #
    # [batch, channels, samples]
    #
    batch = audio.unsqueeze(0)

    with torch.no_grad():
        embedding = embedding_model(batch)

    embedding = np.asarray(
        embedding[0],
        dtype=np.float32,
    )

    return l2_normalize(embedding)


# ============================================================
# BUILD HUMAN ANCHORS
# ============================================================


def build_human_anchors(
    segments: List[dict],
    embeddings: List[np.ndarray],
):

    print()
    print("=" * 70)
    print("BUILDING HUMAN VOICE ANCHORS")
    print("=" * 70)

    anchors = defaultdict(list)

    for original_speaker, labeled_segments in HUMAN_LABELS.items():

        for segment_index, human_label in labeled_segments.items():

            matching = [
                s
                for s in segments
                if s["segment_index"] == segment_index
                and s["speaker"] == original_speaker
            ]

            if not matching:
                print(
                    f"WARNING: Could not find "
                    f"{original_speaker} [{segment_index}]"
                )
                continue

            segment = matching[0]

            embedding = embeddings[
                segments.index(segment)
            ]

            anchors[human_label].append(
                {
                    "segment_index": segment_index,
                    "original_speaker": original_speaker,
                    "start": segment["start"],
                    "end": segment["end"],
                    "duration": segment["duration"],
                    "embedding": embedding,
                }
            )

    for label in sorted(anchors):

        samples = anchors[label]

        print(
            f"{label}: {len(samples)} confirmed samples"
        )

        for sample in samples:

            print(
                f"  [{sample['segment_index']:03d}] "
                f"{sample['original_speaker']} "
                f"{sample['start']:.2f}-"
                f"{sample['end']:.2f} "
                f"({sample['duration']:.2f}s)"
            )

    return anchors


# ============================================================
# BUILD PROTOTYPES
# ============================================================


def build_prototypes(anchors):

    print()
    print("=" * 70)
    print("VOICE PROTOTYPES")
    print("=" * 70)

    prototypes = {}

    for label, samples in sorted(anchors.items()):

        embeddings = [
            sample["embedding"]
            for sample in samples
        ]

        weights = [
            math.sqrt(
                max(
                    sample["duration"],
                    MIN_ANCHOR_DURATION,
                )
            )
            for sample in samples
        ]

        prototype = weighted_centroid(
            embeddings,
            weights,
        )

        similarities = [
            cosine_similarity(
                embedding,
                prototype,
            )
            for embedding in embeddings
        ]

        prototypes[label] = {
            "embedding": prototype,
            "sample_count": len(samples),
            "coherence_mean": float(
                np.mean(similarities)
            ),
            "coherence_median": float(
                np.median(similarities)
            ),
            "coherence_min": float(
                np.min(similarities)
            ),
            "coherence_max": float(
                np.max(similarities)
            ),
            "samples": [
                {
                    "segment_index": sample["segment_index"],
                    "original_speaker": sample[
                        "original_speaker"
                    ],
                    "start": sample["start"],
                    "end": sample["end"],
                    "duration": sample["duration"],
                }
                for sample in samples
            ],
        }

        print(
            f"VOICE {label}: "
            f"{len(samples)} samples | "
            f"coherence mean="
            f"{prototypes[label]['coherence_mean']:.4f} | "
            f"median="
            f"{prototypes[label]['coherence_median']:.4f} | "
            f"min="
            f"{prototypes[label]['coherence_min']:.4f} | "
            f"max="
            f"{prototypes[label]['coherence_max']:.4f}"
        )

    return prototypes


# ============================================================
# CLASSIFY ONE SEGMENT
# ============================================================


def classify_segment(
    embedding: np.ndarray,
    anchors,
    prototypes,
):

    # --------------------------------------------------------
    # Prototype similarity
    # --------------------------------------------------------

    prototype_scores = []

    for label, prototype_data in prototypes.items():

        score = cosine_similarity(
            embedding,
            prototype_data["embedding"],
        )

        prototype_scores.append(
            (
                label,
                score,
            )
        )

    prototype_scores.sort(
        key=lambda x: x[1],
        reverse=True,
    )

    best_label, best_score = prototype_scores[0]

    if len(prototype_scores) > 1:
        second_score = prototype_scores[1][1]
    else:
        second_score = -1.0

    margin = best_score - second_score

    # --------------------------------------------------------
    # Individual anchor support
    # --------------------------------------------------------

    anchor_scores = []

    for label, samples in anchors.items():

        scores = [
            cosine_similarity(
                embedding,
                sample["embedding"],
            )
            for sample in samples
        ]

        strong_count = sum(
            score >= STRONG_SIMILARITY
            for score in scores
        )

        supporting_count = sum(
            score >= SUPPORTING_SIMILARITY
            for score in scores
        )

        max_score = max(scores) if scores else -1.0

        anchor_scores.append(
            {
                "label": label,
                "max_score": max_score,
                "strong_count": strong_count,
                "supporting_count": supporting_count,
            }
        )

    best_anchor = max(
        anchor_scores,
        key=lambda x: x["max_score"],
    )

    # --------------------------------------------------------
    # Classification
    # --------------------------------------------------------

    if (
        best_score >= STRONG_SIMILARITY
        and margin >= STRONG_MARGIN
        and best_anchor["strong_count"]
        >= MIN_STRONG_SUPPORT
        and best_anchor["label"] == best_label
    ):

        status = "strong"

    elif (
        best_score >= SUPPORTING_SIMILARITY
        and margin >= SUPPORTING_MARGIN
        and best_anchor["supporting_count"] >= 1
        and best_anchor["label"] == best_label
    ):

        status = "supporting"

    else:

        status = "unknown"

    return {
        "identity": (
            best_label
            if status != "unknown"
            else None
        ),
        "status": status,
        "best_score": float(best_score),
        "second_score": float(second_score),
        "margin": float(margin),
        "prototype_scores": {
            label: float(score)
            for label, score in prototype_scores
        },
        "best_anchor_label": best_anchor["label"],
        "best_anchor_score": float(
            best_anchor["max_score"]
        ),
        "strong_anchor_support": int(
            best_anchor["strong_count"]
        ),
        "supporting_anchor_support": int(
            best_anchor["supporting_count"]
        ),
    }


# ============================================================
# RUN
# ============================================================


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 70)
    print("MANUAL VOICE IDENTITY EXPERIMENT")
    print("=" * 70)

    print(f"Recording ID: {RECORDING_ID}")

    # --------------------------------------------------------
    # Load segments
    # --------------------------------------------------------

    diarization_segments = load_diarization_segments()

    identity_segments = load_identity_segments()

    segments = match_speaker_labels(
        identity_segments,
        diarization_segments,
    )

    print(
        f"Usable segments: {len(segments)}"
    )

    # --------------------------------------------------------
    # Load audio
    # --------------------------------------------------------

    waveform, sample_rate = load_audio()

    # --------------------------------------------------------
    # Load Community-1
    # --------------------------------------------------------

    pipeline, embedding_model = load_pipeline()

    # --------------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("GENERATING EMBEDDINGS")
    print("=" * 70)

    embeddings = []

    for index, segment in enumerate(segments):

        embedding = extract_embedding(
            embedding_model,
            waveform,
            sample_rate,
            segment["start"],
            segment["end"],
        )

        embeddings.append(embedding)

        print(
            f"\rEmbedded "
            f"{index + 1}/{len(segments)}",
            end="",
            flush=True,
        )

    print()
    print("Embedding generation complete.")

    # --------------------------------------------------------
    # Human anchors
    # --------------------------------------------------------

    anchors = build_human_anchors(
        segments,
        embeddings,
    )

    # --------------------------------------------------------
    # Prototypes
    # --------------------------------------------------------

    prototypes = build_prototypes(
        anchors
    )

    # --------------------------------------------------------
    # Classify all segments
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CLASSIFYING ALL SEGMENTS")
    print("=" * 70)

    assignments = []

    status_counts = defaultdict(int)

    original_to_identity = defaultdict(
        lambda: defaultdict(int)
    )

    for index, segment in enumerate(segments):

        result = classify_segment(
            embeddings[index],
            anchors,
            prototypes,
        )

        status_counts[result["status"]] += 1

        identity = result["identity"]

        if identity is None:
            identity_name = "UNKNOWN"
        else:
            identity_name = identity

        original_to_identity[
            segment["speaker"]
        ][identity_name] += 1

        assignment = {
            "segment_index": segment[
                "segment_index"
            ],
            "start": segment["start"],
            "end": segment["end"],
            "duration": segment["duration"],
            "original_speaker": segment[
                "speaker"
            ],
            **result,
        }

        assignments.append(
            assignment
        )

        print(
            f"[{segment['segment_index']:03d}] "
            f"{segment['start']:8.2f}-"
            f"{segment['end']:8.2f} | "
            f"{segment['speaker']:12s} | "
            f"{identity_name:7s} | "
            f"{result['status']:10s} | "
            f"score="
            f"{result['best_score']:.4f} | "
            f"margin="
            f"{result['margin']:.4f}"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("ASSIGNMENT SUMMARY")
    print("=" * 70)

    print(
        f"Strong:    {status_counts['strong']}"
    )

    print(
        f"Supporting: {status_counts['supporting']}"
    )

    print(
        f"Unknown:   {status_counts['unknown']}"
    )

    print()
    print("=" * 70)
    print("ORIGINAL LABEL → HUMAN IDENTITY")
    print("=" * 70)

    for speaker in sorted(
        original_to_identity
    ):

        counts = original_to_identity[
            speaker
        ]

        total = sum(counts.values())

        formatted = ", ".join(
            f"{identity}={count}/{total}"
            for identity, count
            in sorted(counts.items())
        )

        print(
            f"{speaker}: {formatted}"
        )

    # --------------------------------------------------------
    # Save JSON
    # --------------------------------------------------------

    output = {
        "recording_id": RECORDING_ID,
        "recording_path": str(
            RECORDING_PATH
        ),
        "diarization_cache": str(
            DIARIZATION_CACHE
        ),
        "identity_diagnostic": str(
            IDENTITY_DIAGNOSTIC
        ),
        "configuration": {
            "min_segment_duration":
                MIN_SEGMENT_DURATION,
            "strong_similarity":
                STRONG_SIMILARITY,
            "supporting_similarity":
                SUPPORTING_SIMILARITY,
            "strong_margin":
                STRONG_MARGIN,
            "supporting_margin":
                SUPPORTING_MARGIN,
            "min_strong_support":
                MIN_STRONG_SUPPORT,
        },
        "human_labels": HUMAN_LABELS,
        "prototype_statistics": {
            label: {
                key: value
                for key, value
                in prototype.items()
                if key != "embedding"
            }
            for label, prototype
            in prototypes.items()
        },
        "summary": {
            "total_segments": len(
                assignments
            ),
            "strong": status_counts[
                "strong"
            ],
            "supporting": status_counts[
                "supporting"
            ],
            "unknown": status_counts[
                "unknown"
            ],
        },
        "original_label_summary": {
            speaker: dict(counts)
            for speaker, counts
            in original_to_identity.items()
        },
        "assignments": assignments,
    }

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
        )

    print()
    print("=" * 70)
    print("RESULT SAVED")
    print("=" * 70)

    print(OUTPUT_JSON)


if __name__ == "__main__":
    main()