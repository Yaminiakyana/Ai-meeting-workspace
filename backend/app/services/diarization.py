from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from pyannote.audio import Pipeline


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RECORDINGS_ROOT = PROJECT_ROOT / "storage" / "recordings"
PROCESSED_ROOT = PROJECT_ROOT / "storage" / "processed"


# ============================================================
# COMMUNITY-1 CONFIGURATION
# ============================================================

PIPELINE_NAME = "pyannote/speaker-diarization-community-1"

DEFAULT_CLUSTERING = {
    "threshold": 0.60,
    "Fa": 0.07,
    "Fb": 0.80,
}


# We deliberately test only a small neighborhood around the
# official default instead of randomly changing parameters.
CLUSTERING_EXPERIMENTS = [
    {
        "name": "threshold_055",
        "threshold": 0.55,
        "Fa": 0.07,
        "Fb": 0.80,
    },
    {
        "name": "threshold_060_default",
        "threshold": 0.60,
        "Fa": 0.07,
        "Fb": 0.80,
    },
    {
        "name": "threshold_065",
        "threshold": 0.65,
        "Fa": 0.07,
        "Fb": 0.80,
    },
    {
        "name": "threshold_070",
        "threshold": 0.70,
        "Fa": 0.07,
        "Fb": 0.80,
    },
]


# ============================================================
# PIPELINE LOADING
# ============================================================

def load_diarization_pipeline() -> Pipeline:
    """
    Load Community-1 pipeline.

    Checks:
      1. HF_TOKEN environment variable
      2. settings.hf_token from backend/.env
      3. Cached token from huggingface-cli
      4. Local Hugging Face model cache fallback
    """
    from app.core.config import settings

    token = os.getenv("HF_TOKEN") or getattr(settings, "hf_token", None)
    if not token:
        try:
            from huggingface_hub import get_token
            token = get_token()
        except Exception:
            token = None

    print()
    print("=" * 80)
    print("LOADING PYANNOTE COMMUNITY-1")
    print("=" * 80)
    print(f"Pipeline: {PIPELINE_NAME}")

    if token:
        print("Using provided Hugging Face token.")
        pipeline = Pipeline.from_pretrained(
            PIPELINE_NAME,
            token=token,
        )
    else:
        print("No HF_TOKEN found in environment or .env; checking local cache...")
        try:
            pipeline = Pipeline.from_pretrained(PIPELINE_NAME)
            print("Loaded pipeline successfully from local Hugging Face cache.")
        except Exception as exc:
            raise RuntimeError(
                "HF_TOKEN is not set and the model could not be loaded from local cache.\n"
                "Please add HF_TOKEN=hf_... to backend/.env or run 'export HF_TOKEN=your_token'."
            ) from exc

    print("Pipeline loaded successfully.")
    return pipeline


# ============================================================
# PARAMETER CONFIGURATION
# ============================================================

def configure_clustering(
    pipeline: Pipeline,
    threshold: float,
    Fa: float,
    Fb: float,
) -> None:
    """
    Configure Community-1's VBx clustering parameters.

    Community-1 uses VBx clustering by default.
    """

    clustering = pipeline.clustering

    clustering.threshold = threshold
    clustering.Fa = Fa
    clustering.Fb = Fb

    print()
    print("Clustering configuration:")
    print(f"  threshold = {threshold}")
    print(f"  Fa        = {Fa}")
    print(f"  Fb        = {Fb}")


# ============================================================
# ANNOTATION EXTRACTION
# ============================================================

def annotation_to_segments(annotation: Any) -> list[dict[str, Any]]:
    """
    Convert pyannote Annotation into plain dictionaries.
    """

    segments: list[dict[str, Any]] = []

    for turn, _, speaker in annotation.itertracks(yield_label=True):
        start = float(turn.start)
        end = float(turn.end)

        if end <= start:
            continue

        segments.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "speaker": str(speaker),
            }
        )

    segments.sort(
        key=lambda item: (
            item["start"],
            item["end"],
            item["speaker"],
        )
    )

    return segments


# ============================================================
# STATISTICS
# ============================================================

def calculate_statistics(
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Calculate fragmentation and speaker statistics.
    """

    speaker_segments: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for segment in segments:
        speaker_segments[segment["speaker"]].append(segment)

    speaker_stats: dict[str, Any] = {}

    total_speech = 0.0

    for speaker, items in sorted(speaker_segments.items()):
        durations = [
            float(item["duration"])
            for item in items
        ]

        total_duration = sum(durations)
        total_speech += total_duration

        speaker_stats[speaker] = {
            "speech_seconds": round(total_duration, 3),
            "segment_count": len(items),
            "average_segment_seconds": round(
                total_duration / len(items),
                3,
            )
            if items
            else 0.0,
            "median_segment_seconds": round(
                sorted(durations)[len(durations) // 2],
                3,
            )
            if durations
            else 0.0,
            "short_under_0_1s": sum(
                1 for d in durations if d < 0.1
            ),
            "short_under_0_5s": sum(
                1 for d in durations if d < 0.5
            ),
            "short_under_1s": sum(
                1 for d in durations if d < 1.0
            ),
            "long_over_2s": sum(
                1 for d in durations if d >= 2.0
            ),
            "long_over_5s": sum(
                1 for d in durations if d >= 5.0
            ),
        }

    durations_all = [
        float(segment["duration"])
        for segment in segments
    ]

    short_01 = [
        d for d in durations_all if d < 0.1
    ]

    short_05 = [
        d for d in durations_all if d < 0.5
    ]

    short_1 = [
        d for d in durations_all if d < 1.0
    ]

    statistics = {
        "detected_speakers": len(speaker_segments),
        "speaker_labels": sorted(speaker_segments.keys()),
        "total_segments": len(segments),
        "total_speech_seconds": round(total_speech, 3),
        "average_segment_seconds": round(
            sum(durations_all) / len(durations_all),
            3,
        )
        if durations_all
        else 0.0,
        "short_under_0_1s": len(short_01),
        "short_under_0_5s": len(short_05),
        "short_under_1s": len(short_1),
        "short_under_0_1s_percentage": round(
            100.0 * len(short_01) / len(segments),
            2,
        )
        if segments
        else 0.0,
        "short_under_0_5s_percentage": round(
            100.0 * len(short_05) / len(segments),
            2,
        )
        if segments
        else 0.0,
        "short_under_1s_percentage": round(
            100.0 * len(short_1) / len(segments),
            2,
        )
        if segments
        else 0.0,
        "speaker_statistics": speaker_stats,
    }

    return statistics


# ============================================================
# RAPID SPEAKER SWITCH DIAGNOSTICS
# ============================================================

def calculate_switch_statistics(
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Detect rapid A/B/A/B-style switching.

    This does NOT change the diarization.
    It is purely diagnostic.
    """

    if len(segments) < 3:
        return {
            "speaker_switches": 0,
            "rapid_switches_under_0_5s": 0,
            "rapid_switches_under_1s": 0,
            "alternating_triplets": 0,
        }

    speaker_switches = 0
    rapid_under_05 = 0
    rapid_under_1 = 0
    alternating_triplets = 0

    for i in range(1, len(segments)):
        previous = segments[i - 1]
        current = segments[i]

        if previous["speaker"] != current["speaker"]:
            speaker_switches += 1

            duration = float(current["duration"])

            if duration < 0.5:
                rapid_under_05 += 1

            if duration < 1.0:
                rapid_under_1 += 1

    for i in range(2, len(segments)):
        a = segments[i - 2]
        b = segments[i - 1]
        c = segments[i]

        if (
            a["speaker"] == c["speaker"]
            and a["speaker"] != b["speaker"]
        ):
            alternating_triplets += 1

    return {
        "speaker_switches": speaker_switches,
        "rapid_switches_under_0_5s": rapid_under_05,
        "rapid_switches_under_1s": rapid_under_1,
        "alternating_triplets": alternating_triplets,
    }


# ============================================================
# EMBEDDING DIAGNOSTICS
# ============================================================

def calculate_embedding_statistics(
    output: Any,
) -> dict[str, Any]:
    """
    Inspect speaker embeddings returned by Community-1.

    Community-1 returns one embedding per detected speaker.

    We do not perform a second clustering here.
    We only record dimensions and basic cosine similarity.
    """

    embeddings = getattr(
        output,
        "speaker_embeddings",
        None,
    )

    if embeddings is None:
        return {
            "available": False,
            "reason": "speaker_embeddings not available",
        }

    try:
        import numpy as np

        embeddings = np.asarray(embeddings)

        result: dict[str, Any] = {
            "available": True,
            "shape": list(embeddings.shape),
        }

        if embeddings.ndim != 2 or len(embeddings) < 2:
            result["pairwise_similarity"] = []

            return result

        norms = np.linalg.norm(
            embeddings,
            axis=1,
            keepdims=True,
        )

        normalized = embeddings / np.maximum(
            norms,
            1e-12,
        )

        similarity = normalized @ normalized.T

        pairwise = []

        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                pairwise.append(
                    {
                        "speaker_index_a": i,
                        "speaker_index_b": j,
                        "cosine_similarity": round(
                            float(similarity[i, j]),
                            4,
                        ),
                    }
                )

        pairwise.sort(
            key=lambda item: item["cosine_similarity"],
            reverse=True,
        )

        result["pairwise_similarity"] = pairwise

        return result

    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
        }


# ============================================================
# ONE EXPERIMENT
# ============================================================

def run_experiment(
    pipeline: Pipeline,
    audio_path: Path,
    experiment: dict[str, Any],
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print(f"EXPERIMENT: {experiment['name']}")
    print("=" * 80)

    configure_clustering(
        pipeline=pipeline,
        threshold=experiment["threshold"],
        Fa=experiment["Fa"],
        Fb=experiment["Fb"],
    )

    print()
    print("Running Community-1...")
    print(f"Audio: {audio_path}")

    # IMPORTANT:
    # No num_speakers
    # No min_speakers
    # No max_speakers
    #
    # Speaker count remains completely automatic.

    output = pipeline(
        str(audio_path)
    )

    regular_annotation = output.speaker_diarization
    exclusive_annotation = output.exclusive_speaker_diarization

    regular_segments = annotation_to_segments(
        regular_annotation
    )

    exclusive_segments = annotation_to_segments(
        exclusive_annotation
    )

    regular_statistics = calculate_statistics(
        regular_segments
    )

    exclusive_statistics = calculate_statistics(
        exclusive_segments
    )

    regular_switches = calculate_switch_statistics(
        regular_segments
    )

    exclusive_switches = calculate_switch_statistics(
        exclusive_segments
    )

    embedding_statistics = calculate_embedding_statistics(
        output
    )

    result = {
        "experiment": experiment,
        "regular": {
            "statistics": regular_statistics,
            "switch_statistics": regular_switches,
            "segments": regular_segments,
        },
        "exclusive": {
            "statistics": exclusive_statistics,
            "switch_statistics": exclusive_switches,
            "segments": exclusive_segments,
        },
        "embedding_statistics": embedding_statistics,
    }

    print()
    print("RESULT")
    print("-" * 80)

    print(
        f"Regular speakers: "
        f"{regular_statistics['detected_speakers']}"
    )

    print(
        f"Regular segments: "
        f"{regular_statistics['total_segments']}"
    )

    print(
        f"Regular <0.1s: "
        f"{regular_statistics['short_under_0_1s']}"
    )

    print(
        f"Regular <0.5s: "
        f"{regular_statistics['short_under_0_5s']}"
    )

    print(
        f"Regular <1s: "
        f"{regular_statistics['short_under_1s']}"
    )

    print(
        f"Regular A/B/A patterns: "
        f"{regular_switches['alternating_triplets']}"
    )

    print()

    print(
        f"Exclusive speakers: "
        f"{exclusive_statistics['detected_speakers']}"
    )

    print(
        f"Exclusive segments: "
        f"{exclusive_statistics['total_segments']}"
    )

    print(
        f"Exclusive <0.1s: "
        f"{exclusive_statistics['short_under_0_1s']}"
    )

    print(
        f"Exclusive <0.5s: "
        f"{exclusive_statistics['short_under_0_5s']}"
    )

    print(
        f"Exclusive <1s: "
        f"{exclusive_statistics['short_under_1s']}"
    )

    print(
        f"Exclusive A/B/A patterns: "
        f"{exclusive_switches['alternating_triplets']}"
    )

    return result


# ============================================================
# EXPERIMENT SUITE
# ============================================================

def run_clustering_experiments(
    audio_path: str | Path,
) -> dict[str, Any]:

    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file does not exist: {audio_path}"
        )

    pipeline = load_diarization_pipeline()

    results = []

    for experiment in CLUSTERING_EXPERIMENTS:

        result = run_experiment(
            pipeline=pipeline,
            audio_path=audio_path,
            experiment=experiment,
        )

        results.append(result)

    output_dir = (
        PROCESSED_ROOT
        / "recording_7"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir
        / "diarization_clustering_experiments.json"
    )

    payload = {
        "pipeline": PIPELINE_NAME,
        "audio": str(audio_path),
        "default_configuration": DEFAULT_CLUSTERING,
        "speaker_count_mode": "automatic",
        "experiments": results,
    }

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
            indent=2,
        )

    print()
    print("=" * 80)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 80)

    print()
    print(f"Results saved to:")
    print(output_file)

    print()
    print("SUMMARY")
    print("-" * 80)

    for result in results:

        name = result["experiment"]["name"]

        stats = result["exclusive"]["statistics"]
        switches = result["exclusive"]["switch_statistics"]

        print()
        print(name)
        print(
            f"  speakers       : "
            f"{stats['detected_speakers']}"
        )
        print(
            f"  segments       : "
            f"{stats['total_segments']}"
        )
        print(
            f"  <0.1 sec       : "
            f"{stats['short_under_0_1s']}"
        )
        print(
            f"  <0.5 sec       : "
            f"{stats['short_under_0_5s']}"
        )
        print(
            f"  <1 sec         : "
            f"{stats['short_under_1s']}"
        )
        print(
            f"  avg duration   : "
            f"{stats['average_segment_seconds']:.3f}s"
        )
        print(
            f"  A/B/A patterns : "
            f"{switches['alternating_triplets']}"
        )

    return payload

# ============================================================
# PRODUCTION DIARIZATION
# ============================================================

def diarize_audio(
    audio_path: Path,
) -> list[dict[str, Any]]:
    """
    Run production speaker diarization using pyannote Community-1.

    Important:
    - Speaker count is completely automatic.
    - No num_speakers is supplied.
    - No min_speakers is supplied.
    - No max_speakers is supplied.
    - We use Community-1's exclusive diarization output so that
      each moment of audio has at most one speaker label.
    - This function does NOT perform grammar-based speaker
      correction or transcript heuristics.
    """

    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file does not exist: {audio_path}"
        )

    print()
    print("=" * 80)
    print("RUNNING COMMUNITY-1 SPEAKER DIARIZATION")
    print("=" * 80)
    print()
    print(f"Audio: {audio_path}")
    print()

    # --------------------------------------------------------
    # Load Community-1
    # --------------------------------------------------------

    pipeline = load_diarization_pipeline()

    # --------------------------------------------------------
    # Automatic speaker count
    # --------------------------------------------------------

    print()
    print("Running Community-1 with automatic speaker count...")
    print("  num_speakers = automatic")
    print("  min_speakers = not specified")
    print("  max_speakers = not specified")
    print()

    output = pipeline(
        str(audio_path)
    )

    # --------------------------------------------------------
    # Use exclusive diarization
    # --------------------------------------------------------

    exclusive_annotation = getattr(
        output,
        "exclusive_speaker_diarization",
        None,
    )

    if exclusive_annotation is None:
        raise RuntimeError(
            "Community-1 did not return "
            "exclusive_speaker_diarization."
        )

    diarization_segments = annotation_to_segments(
        exclusive_annotation
    )

    if not diarization_segments:
        raise RuntimeError(
            "Community-1 returned no speaker segments."
        )

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    statistics = calculate_statistics(
        diarization_segments
    )

    switch_statistics = calculate_switch_statistics(
        diarization_segments
    )

    embedding_statistics = (
        calculate_embedding_statistics(output)
    )

    print()
    print("=" * 80)
    print("DIARIZATION RESULTS")
    print("=" * 80)

    print(
        f"Detected speakers: "
        f"{statistics['detected_speakers']}"
    )

    print(
        f"Total segments: "
        f"{statistics['total_segments']}"
    )

    print(
        f"Total speech: "
        f"{statistics['total_speech_seconds']:.2f}s"
    )

    print(
        f"Average segment: "
        f"{statistics['average_segment_seconds']:.2f}s"
    )

    print(
        f"Segments < 0.5s: "
        f"{statistics['short_under_0_5s']}"
    )

    print(
        f"Segments < 1.0s: "
        f"{statistics['short_under_1s']}"
    )

    print(
        f"Speaker switches: "
        f"{switch_statistics['speaker_switches']}"
    )

    print(
        f"A/B/A triplets: "
        f"{switch_statistics['alternating_triplets']}"
    )

    if embedding_statistics.get("available"):
        print(
            f"Speaker embedding shape: "
            f"{embedding_statistics.get('shape')}"
        )

    print()

    # --------------------------------------------------------
    # Return only the diarization segments.
    #
    # The worker expects this exact structure and will cache it
    # in:
    #
    # storage/processed/recording_<id>/diarization.json
    # --------------------------------------------------------

    return diarization_segments


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    # IMPORTANT:
    # This is Recording 7's ACTUAL physical file.
    #
    # Do not replace this with recordings/7 unless the physical
    # file really exists there.

    test_audio = (
        RECORDINGS_ROOT
        / "5"
        / "344d63fd75074ab3a4a19e745f7aa090.mp4"
    )

    run_clustering_experiments(
        test_audio
    )