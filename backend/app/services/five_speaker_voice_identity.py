
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torchaudio
import torch.nn.functional as F
from pyannote.audio import Pipeline


# ============================================================
# PATHS AND CONFIGURATION
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[2]

RECORDING_PATH = (
    BACKEND_DIR
    / "storage"
    / "recordings"
    / "5"
    / "344d63fd75074ab3a4a19e745f7aa090.mp4"
)

PROCESSED_DIR = (
    BACKEND_DIR
    / "storage"
    / "processed"
    / "recording_7"
)

# This is the output of the previous successful 91-segment
# experiment. We reuse its timestamps and do not rerun diarization.
BASELINE_RESULTS_PATH = (
    PROCESSED_DIR
    / "five_speaker_voice_identity_diagnostic"
    / "five_speaker_voice_identity_results.json"
)

# Save to a NEW file so the previous diagnostic remains intact.
OUTPUT_DIR = (
    PROCESSED_DIR
    / "five_speaker_voice_identity_validation_v2"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "five_speaker_voice_identity_validation_v2_results.json"
)

MODEL_ID = "pyannote/speaker-diarization-community-1"
TARGET_SAMPLE_RATE = 16000

# Retain the previous experiment's confidence thresholds.
STRONG_THRESHOLD = 0.72
SUPPORT_THRESHOLD = 0.62

STRONG_MARGIN = 0.08
SUPPORT_MARGIN = 0.05

IDENTITIES = ["A", "B", "C", "D", "E"]


# ============================================================
# HUMAN-VERIFIED ANCHORS
#
# These are indexes in the CACHED 91-SEGMENT diagnostic,
# NOT indexes in the 210-segment diarization.json file.
#
# The four new unique labels are:
#   011 = A
#   023 = C
#   035 = B
#   080 = A
#
# 030 = C and 043 = B were already among the original anchors.
# Segment 000 is intentionally excluded.
# ============================================================

ORIGINAL_ANCHORS = {
    "A": [3, 32, 40, 52, 53, 61, 62, 24, 49, 65],
    "B": [4, 10, 19, 43, 48, 66, 16, 34, 42, 45, 60, 67, 68],
    "C": [25, 27, 30, 31, 51, 22, 26, 21],
    "D": [88, 70, 90],
    "E": [76, 74, 78, 84],
}

NEWLY_VERIFIED = {
    11: "A",
    23: "C",
    30: "C",
    35: "B",
    43: "B",
    80: "A",
}

# The four genuinely new unique samples are 011, 023, 035, 080.
INDEPENDENTLY_ADDED_INDICES = {11, 23, 35, 80}


# ============================================================
# HELPERS
# ============================================================

def first_present(
    item: dict[str, Any],
    names: tuple[str, ...],
    description: str,
) -> Any:
    """Return the first available field from a list of alternatives."""
    for name in names:
        if name in item and item[name] is not None:
            return item[name]

    raise KeyError(
        f"Could not find {description}. "
        f"Tried fields: {names}. "
        f"Available fields: {list(item.keys())}"
    )



def load_cached_segments() -> list[dict[str, Any]]:
    """Load the 91 cached segments from the existing assignments list."""

    if not BASELINE_RESULTS_PATH.exists():
        raise FileNotFoundError(
            "Cached diagnostic not found:\n"
            f"{BASELINE_RESULTS_PATH}\n"
            "Do not rerun Whisper or diarization."
        )

    with BASELINE_RESULTS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise TypeError(
            f"Expected a JSON object, got {type(data).__name__}."
        )

    # The actual diagnostic stores the 91 segments in "assignments".
    records = data.get("assignments")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'assignments' to be a list. "
            f"Available keys: {list(data.keys())}"
        )

    normalized = []

    for position, item in enumerate(records):
        if not isinstance(item, dict):
            raise TypeError(
                f"Assignment at position {position} is not an object."
            )

        required_fields = (
            "segment_index",
            "start",
            "end",
            "original_speaker",
        )

        missing = [
            field for field in required_fields
            if field not in item
        ]

        if missing:
            raise ValueError(
                f"Assignment {position} is missing fields: {missing}. "
                f"Available fields: {list(item.keys())}"
            )

        normalized.append(
            {
                "segment_index": int(item["segment_index"]),
                "start_time": float(item["start"]),
                "end_time": float(item["end"]),
                "original_speaker": str(item["original_speaker"]),
            }
        )

    normalized.sort(key=lambda item: item["segment_index"])

    if len(normalized) != 91:
        raise ValueError(
            f"Expected 91 cached segments, found {len(normalized)}."
        )

    indexes = [item["segment_index"] for item in normalized]

    if indexes != list(range(91)):
        raise ValueError(
            "Expected segment indexes 0–90. "
            f"Received: {indexes[:10]}..."
        )

    print(f"Loaded {len(normalized)} cached diagnostic segments.")
    print(
        "First segment:",
        normalized[0],
    )
    print(
        "Last segment:",
        normalized[-1],
    )

    return normalized


def build_anchor_map() -> dict[int, str]:
    """Build a unique segment-index-to-human-identity mapping."""

    anchors: dict[int, str] = {}

    for identity, indexes in ORIGINAL_ANCHORS.items():
        for index in indexes:
            if index in anchors and anchors[index] != identity:
                raise ValueError(
                    f"Conflicting anchor labels for segment {index}."
                )
            anchors[index] = identity

    for index, identity in NEWLY_VERIFIED.items():
        if index in anchors and anchors[index] != identity:
            raise ValueError(
                f"Conflicting newly verified label for segment {index}."
            )
        anchors[index] = identity

    if 0 in anchors:
        raise ValueError(
            "Segment 000 must be excluded because it belongs to "
            "the previous recording part."
        )

    counts = {
        identity: sum(
            label == identity for label in anchors.values()
        )
        for identity in IDENTITIES
    }

    expected_counts = {
        "A": 12,
        "B": 14,
        "C": 9,
        "D": 3,
        "E": 4,
    }

    if counts != expected_counts:
        raise ValueError(
            f"Unexpected anchor counts: {counts}; "
            f"expected {expected_counts}."
        )

    if len(anchors) != 42:
        raise ValueError(
            f"Expected 42 unique verified anchors, got {len(anchors)}."
        )

    print("\nHuman-verified anchor counts:")
    for identity in IDENTITIES:
        print(f"  Voice {identity}: {counts[identity]}")

    print(f"  Total unique anchors: {len(anchors)}")

    return anchors


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)

    norm = float(np.linalg.norm(vector))

    if norm < 1e-12:
        raise ValueError("The embedding model returned a zero vector.")

    return vector / norm


def extract_embedding(
    embedding_model: Any,
    waveform: torch.Tensor,
    sample_rate: int,
    start_time: float,
    end_time: float,
    segment_index: int,
) -> np.ndarray:
    """Extract one embedding using the model's tensor-based API."""

    start_sample = max(0, int(round(start_time * sample_rate)))
    end_sample = min(
        waveform.shape[-1],
        int(round(end_time * sample_rate)),
    )

    if end_sample <= start_sample:
        raise ValueError(
            f"Invalid audio interval for segment {segment_index}: "
            f"{start_time:.3f}-{end_time:.3f}s"
        )

    audio = waveform[:, start_sample:end_sample]

    # Community-1's bundled embedding model expects
    # [batch, channels, samples], not a dictionary.
    if audio.ndim != 2:
        raise ValueError(
            f"Expected [channels, samples] for segment {segment_index}; "
            f"received shape {tuple(audio.shape)}."
        )

    batch = audio.unsqueeze(0).to(torch.device("cpu"))

    with torch.inference_mode():
        embedding = embedding_model(batch)

    if isinstance(embedding, (tuple, list)):
        embedding = embedding[0]

    if not isinstance(embedding, torch.Tensor):
        embedding = torch.as_tensor(embedding)

    embedding = embedding.detach().cpu().numpy()

    if embedding.ndim == 2 and embedding.shape[0] == 1:
        embedding = embedding[0]

    if embedding.ndim != 1:
        raise ValueError(
            f"Unexpected embedding shape for segment {segment_index}: "
            f"{embedding.shape}"
        )

    return normalize_vector(embedding)


def make_prototypes(
    embeddings: dict[int, np.ndarray],
    anchor_map: dict[int, str],
    excluded_index: int | None = None,
) -> dict[str, np.ndarray]:
    """
    Make normalized speaker prototypes.

    When excluded_index is supplied, that sample is omitted from
    its own speaker prototype for honest leave-one-out evaluation.
    """

    prototypes: dict[str, np.ndarray] = {}

    for identity in IDENTITIES:
        vectors = [
            embeddings[index]
            for index, label in anchor_map.items()
            if label == identity and index != excluded_index
        ]

        if not vectors:
            raise ValueError(
                f"No prototype samples remain for voice {identity} "
                f"after excluding segment {excluded_index}."
            )

        mean_vector = np.mean(
            np.stack(vectors, axis=0),
            axis=0,
        )

        prototypes[identity] = normalize_vector(mean_vector)

    return prototypes


def score_identity(
    embedding: np.ndarray,
    prototypes: dict[str, np.ndarray],
) -> dict[str, Any]:
    """Rank identities and assign a conservative confidence class."""

    scores = {
        identity: float(np.dot(embedding, prototypes[identity]))
        for identity in IDENTITIES
    }

    ranked = sorted(
        scores.items(),
        key=lambda pair: pair[1],
        reverse=True,
    )

    best_identity, best_score = ranked[0]
    second_identity, second_score = ranked[1]
    margin = best_score - second_score

    if (
        best_score >= STRONG_THRESHOLD
        and margin >= STRONG_MARGIN
    ):
        confidence = "STRONG"
        predicted_identity = best_identity

    elif (
        best_score >= SUPPORT_THRESHOLD
        and margin >= SUPPORT_MARGIN
    ):
        confidence = "SUPPORTING"
        predicted_identity = best_identity

    else:
        confidence = "UNKNOWN"
        predicted_identity = "UNKNOWN"

    return {
        "predicted_identity": predicted_identity,
        "top_identity": best_identity,
        "top_score": round(best_score, 6),
        "second_identity": second_identity,
        "second_score": round(second_score, 6),
        "margin": round(margin, 6),
        "confidence": confidence,
        "scores": {
            identity: round(score, 6)
            for identity, score in ranked
        },
    }


def evaluate_predictions(
    predictions: list[dict[str, Any]],
    anchor_map: dict[int, str],
    selected_indexes: set[int] | None = None,
) -> dict[str, Any]:
    """Calculate top-1 and confidence-qualified accuracy."""

    if selected_indexes is None:
        selected_indexes = set(anchor_map.keys())

    evaluated = [
        item
        for item in predictions
        if item["segment_index"] in selected_indexes
    ]

    if not evaluated:
        return {
            "sample_count": 0,
            "top1_correct": 0,
            "top1_accuracy": None,
            "resolved_count": 0,
            "resolved_correct": 0,
            "resolved_accuracy": None,
            "unknown_count": 0,
        }

    top1_correct = sum(
        item["top_identity"] == anchor_map[item["segment_index"]]
        for item in evaluated
    )

    resolved = [
        item for item in evaluated
        if item["predicted_identity"] != "UNKNOWN"
    ]

    resolved_correct = sum(
        item["predicted_identity"] == anchor_map[item["segment_index"]]
        for item in resolved
    )

    return {
        "sample_count": len(evaluated),
        "top1_correct": int(top1_correct),
        "top1_accuracy": round(
            top1_correct / len(evaluated), 4
        ),
        "resolved_count": len(resolved),
        "resolved_correct": int(resolved_correct),
        "resolved_accuracy": (
            round(resolved_correct / len(resolved), 4)
            if resolved else None
        ),
        "unknown_count": sum(
            item["predicted_identity"] == "UNKNOWN"
            for item in evaluated
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 72)
    print("FIVE-SPEAKER VOICE IDENTITY VALIDATION — VERSION 2")
    print("=" * 72)

    if not RECORDING_PATH.exists():
        raise FileNotFoundError(
            f"Recording not found:\n{RECORDING_PATH}\n"
            "Update RECORDING_PATH to the actual recording file."
        )

    segments = load_cached_segments()
    anchor_map = build_anchor_map()

    print(f"\nLoaded cached segments: {len(segments)}")
    print(f"Recording: {RECORDING_PATH}")
    print("Whisper rerun: NO")
    print("Community-1 diarization rerun: NO")

    # Load the audio once.
    print("\nLoading audio...")
    waveform, sample_rate = torchaudio.load(str(RECORDING_PATH))

    if waveform.ndim != 2:
        raise ValueError(
            f"Expected [channels, samples], got {tuple(waveform.shape)}."
        )

    # Convert multichannel audio to mono if necessary.
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    if sample_rate != TARGET_SAMPLE_RATE:
        print(
            f"Resampling audio from {sample_rate} Hz "
            f"to {TARGET_SAMPLE_RATE} Hz..."
        )

        waveform = torchaudio.functional.resample(
            waveform,
            orig_freq=sample_rate,
            new_freq=TARGET_SAMPLE_RATE,
        )
        sample_rate = TARGET_SAMPLE_RATE

    waveform = waveform.to(torch.float32)

    print(f"Audio sample rate: {sample_rate} Hz")
    print(f"Audio duration: {waveform.shape[-1] / sample_rate:.2f}s")

    # Load Community-1 only to access its bundled embedding model.
    # This does NOT call the diarization pipeline on the recording.
    print("\nLoading Community-1 embedding model on CPU...")

    hf_token = os.environ.get("HF_TOKEN")

    pipeline = Pipeline.from_pretrained(
        MODEL_ID,
        token=hf_token,
    )

    if pipeline is None:
        raise RuntimeError(
            "Could not load Community-1. Check model access and HF_TOKEN."
        )

    pipeline.to(torch.device("cpu"))

    embedding_model = getattr(pipeline, "_embedding", None)

    if embedding_model is None:
        raise RuntimeError(
            "Community-1 did not expose its bundled _embedding model. "
            "No diarization was run."
        )

    pipeline.to(torch.device("cpu"))
    embedding_model = getattr(pipeline, "_embedding", None)

    if embedding_model is None:
        raise RuntimeError(
        "Community-1 did not expose its bundled _embedding model."
    )
    # Cache one embedding per segment so all evaluations reuse
    # the exact same audio and embedding representation.
    embeddings: dict[int, np.ndarray] = {}

    print(f"\nExtracting embeddings for {len(segments)} segments...")

    for position, segment in enumerate(segments, start=1):
        index = segment["segment_index"]

        embeddings[index] = extract_embedding(
            embedding_model=embedding_model,
            waveform=waveform,
            sample_rate=sample_rate,
            start_time=segment["start_time"],
            end_time=segment["end_time"],
            segment_index=index,
        )

        if position % 10 == 0 or position == len(segments):
            print(f"  Embedded {position}/{len(segments)}")

    dimensions = {vector.shape[0] for vector in embeddings.values()}

    if len(dimensions) != 1:
        raise ValueError(
            f"Inconsistent embedding dimensions: {dimensions}"
        )

    embedding_dimension = dimensions.pop()

    print(f"Embedding dimension: {embedding_dimension}")

    # --------------------------------------------------------
    # 1. LEAVE-ONE-OUT VALIDATION
    #
    # For each of the 42 verified clips, exclude that clip from
    # its own identity prototype before predicting its identity.
    # --------------------------------------------------------

    print("\nRunning leave-one-out validation on 42 verified clips...")

    loo_results = []

    for index, true_identity in sorted(anchor_map.items()):
        prototypes = make_prototypes(
            embeddings=embeddings,
            anchor_map=anchor_map,
            excluded_index=index,
        )

        result = score_identity(
            embedding=embeddings[index],
            prototypes=prototypes,
        )

        loo_results.append(
            {
                "segment_index": index,
                "start_time": next(
                    s["start_time"] for s in segments
                    if s["segment_index"] == index
                ),
                "end_time": next(
                    s["end_time"] for s in segments
                    if s["segment_index"] == index
                ),
                "original_speaker": next(
                    s["original_speaker"] for s in segments
                    if s["segment_index"] == index
                ),
                "true_identity": true_identity,
                **result,
                "top1_correct": (
                    result["top_identity"] == true_identity
                ),
                "resolved_correct": (
                    result["predicted_identity"] == true_identity
                ),
                "is_newly_added_anchor": (
                    index in INDEPENDENTLY_ADDED_INDICES
                ),
            }
        )

    all_loo_metrics = evaluate_predictions(
        predictions=[
            {
                "segment_index": item["segment_index"],
                "top_identity": item["top_identity"],
                "predicted_identity": item["predicted_identity"],
            }
            for item in loo_results
        ],
        anchor_map=anchor_map,
    )

    new_anchor_metrics = evaluate_predictions(
        predictions=[
            {
                "segment_index": item["segment_index"],
                "top_identity": item["top_identity"],
                "predicted_identity": item["predicted_identity"],
            }
            for item in loo_results
        ],
        anchor_map=anchor_map,
        selected_indexes=INDEPENDENTLY_ADDED_INDICES,
    )

    # --------------------------------------------------------
    # 2. BUILD FINAL PROTOTYPES USING ALL 42 ANCHORS
    # --------------------------------------------------------

    print("\nBuilding final A-E speaker prototypes...")

    final_prototypes = make_prototypes(
        embeddings=embeddings,
        anchor_map=anchor_map,
    )

    # --------------------------------------------------------
    # 3. CLASSIFY ALL 91 CACHED SEGMENTS
    # --------------------------------------------------------

    print("\nClassifying all 91 cached segments...")

    final_classifications = []

    for segment in segments:
        index = segment["segment_index"]

        result = score_identity(
            embedding=embeddings[index],
            prototypes=final_prototypes,
        )

        final_classifications.append(
            {
                **segment,
                **result,
                "human_verified_identity": anchor_map.get(index),
                "is_human_verified_anchor": index in anchor_map,
            }
        )

    confidence_counts = {
        label: sum(
            item["confidence"] == label
            for item in final_classifications
        )
        for label in ("STRONG", "SUPPORTING", "UNKNOWN")
    }

    identity_counts = {
        identity: sum(
            item["predicted_identity"] == identity
            for item in final_classifications
        )
        for identity in IDENTITIES
    }

    # Show results for the six user-verified clips.
    newly_checked_indices = {11, 23, 30, 35, 43, 80}

    new_clip_results = [
        {
            **item,
            "validation_type": (
                "leave_one_out_anchor"
                if item["segment_index"] in anchor_map
                else "independent"
            ),
        }
        for item in loo_results
        if item["segment_index"] in newly_checked_indices
    ]

    # --------------------------------------------------------
    # 4. SAVE RESULTS TO A NEW FILE
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "experiment": "five_speaker_voice_identity_validation_v2",
        "model": MODEL_ID,
        "device": "cpu",
        "recording_path": str(RECORDING_PATH),
        "baseline_results_path": str(BASELINE_RESULTS_PATH),
        "whisper_rerun": False,
        "community1_diarization_rerun": False,
        "segment_count": len(segments),
        "embedding_dimension": embedding_dimension,
        "verified_anchor_count": len(anchor_map),
        "verified_anchor_counts_by_identity": {
            identity: sum(
                label == identity for label in anchor_map.values()
            )
            for identity in IDENTITIES
        },
        "thresholds": {
            "strong_similarity": STRONG_THRESHOLD,
            "support_similarity": SUPPORT_THRESHOLD,
            "strong_margin": STRONG_MARGIN,
            "support_margin": SUPPORT_MARGIN,
        },
        "leave_one_out_validation": {
            "all_42_verified_samples": all_loo_metrics,
            "four_new_unique_samples": new_anchor_metrics,
            "per_sample_results": loo_results,
        },
        "six_user_verified_clips": new_clip_results,
        "final_prototype_classification": {
            "confidence_counts": confidence_counts,
            "predicted_identity_counts": identity_counts,
            "segments": final_classifications,
        },
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    # --------------------------------------------------------
    # 5. PRINT SUMMARY
    # --------------------------------------------------------

    print("\n" + "=" * 72)
    print("LEAVE-ONE-OUT VALIDATION")
    print("=" * 72)

    print(
        f"All verified anchors: "
        f"{all_loo_metrics['top1_correct']}/"
        f"{all_loo_metrics['sample_count']} top-1 correct "
        f"({all_loo_metrics['top1_accuracy']:.1%})"
    )

    if all_loo_metrics["resolved_accuracy"] is not None:
        print(
            f"Resolved anchors: "
            f"{all_loo_metrics['resolved_correct']}/"
            f"{all_loo_metrics['resolved_count']} correct "
            f"({all_loo_metrics['resolved_accuracy']:.1%})"
        )
    else:
        print("Resolved anchors: none")

    print(
        "\nFour newly added unique samples "
        "(011, 023, 035, 080):"
    )
    print(
        f"  Top-1 correct: "
        f"{new_anchor_metrics['top1_correct']}/"
        f"{new_anchor_metrics['sample_count']}"
    )
    print(
        f"  Resolved correctly: "
        f"{new_anchor_metrics['resolved_correct']}/"
        f"{new_anchor_metrics['resolved_count']}"
    )
    print(
        f"  Unknown: {new_anchor_metrics['unknown_count']}"
    )

    print("\nSix manually verified clips — leave-one-out results:")

    for item in new_clip_results:
        print(
            f"  {item['segment_index']:03d} "
            f"true={item['true_identity']} "
            f"top1={item['top_identity']} "
            f"score={item['top_score']:.3f} "
            f"margin={item['margin']:.3f} "
            f"confidence={item['confidence']} "
            f"correct={item['top1_correct']} "
            f"type={item['validation_type']}"
        )

    print("\nFinal classification of 91 segments:")
    print(f"  STRONG:    {confidence_counts['STRONG']}")
    print(f"  SUPPORTING:{confidence_counts['SUPPORTING']}")
    print(f"  UNKNOWN:   {confidence_counts['UNKNOWN']}")

    print("\nPredicted identity counts:")
    for identity in IDENTITIES:
        print(f"  Voice {identity}: {identity_counts[identity]}")

    print(f"\nResults saved to:\n{OUTPUT_PATH}")
    print("\nNo Whisper transcription or diarization was rerun.")
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
