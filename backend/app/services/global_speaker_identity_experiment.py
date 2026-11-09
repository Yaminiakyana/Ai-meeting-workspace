from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torchaudio
from pyannote.audio import Pipeline
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity


# =============================================================================
# CONFIGURATION
# =============================================================================

RECORDING_ID = 7

PIPELINE_NAME = "pyannote/speaker-diarization-community-1"

EXPERIMENT_NAME = "threshold_060_default"

MIN_SEGMENT_DURATION = 1.5

MAX_SEGMENTS_PER_DIARIZATION_LABEL = None

# We are deliberately NOT deciding the number of real speakers.
#
# This value is only an exploratory clustering distance threshold.
# We will inspect the results rather than treating it as truth.
#
# cosine distance = 1 - cosine similarity
#
# 0.35 distance = 0.65 cosine similarity
EXPLORATORY_DISTANCE_THRESHOLD = 0.35


# =============================================================================
# PATHS
# =============================================================================

BACKEND_ROOT = Path(__file__).resolve().parents[2]

RECORDINGS_ROOT = (
    BACKEND_ROOT / "storage" / "recordings"
)

PROCESSED_ROOT = (
    BACKEND_ROOT / "storage" / "processed"
)

DIARIZATION_JSON = (
    PROCESSED_ROOT
    / f"recording_{RECORDING_ID}"
    / "diarization_clustering_experiments.json"
)

OUTPUT_DIR = (
    PROCESSED_ROOT
    / f"recording_{RECORDING_ID}"
    / "global_speaker_identity_diagnostic"
)

OUTPUT_JSON = (
    OUTPUT_DIR
    / "global_speaker_identity_results.json"
)

KNOWN_RECORDING_FILE = (
    RECORDINGS_ROOT
    / "5"
    / "344d63fd75074ab3a4a19e745f7aa090.mp4"
)


# =============================================================================
# HELPERS
# =============================================================================

def find_recording_file() -> Path:

    if KNOWN_RECORDING_FILE.exists():
        return KNOWN_RECORDING_FILE

    candidates = []

    for path in RECORDINGS_ROOT.rglob("*"):

        if not path.is_file():
            continue

        if path.suffix.lower() not in {
            ".mp4",
            ".wav",
            ".m4a",
            ".mp3",
            ".mov",
            ".webm",
        }:
            continue

        candidates.append(path)

    if len(candidates) == 1:
        return candidates[0]

    raise FileNotFoundError(
        "Could not uniquely locate recording.\n"
        f"Recordings root: {RECORDINGS_ROOT}\n"
        f"Candidates: {candidates}"
    )


def cosine(a: np.ndarray, b: np.ndarray) -> float:

    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)

    denominator = (
        np.linalg.norm(a)
        * np.linalg.norm(b)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.dot(a, b) / denominator
    )


def normalize(
    embedding: np.ndarray,
) -> np.ndarray:

    embedding = np.asarray(
        embedding,
        dtype=np.float32,
    )

    norm = np.linalg.norm(
        embedding
    )

    if norm == 0:
        raise ValueError(
            "Cannot normalize zero embedding."
        )

    return (
        embedding / norm
    ).astype(np.float32)


# =============================================================================
# LOAD CACHED DIARIZATION
# =============================================================================

def load_cached_segments() -> list[dict[str, Any]]:

    print()
    print("=" * 80)
    print("LOADING CACHED DIARIZATION")
    print("=" * 80)

    print()
    print(DIARIZATION_JSON)

    if not DIARIZATION_JSON.exists():
        raise FileNotFoundError(
            f"Missing diarization cache:\n{DIARIZATION_JSON}"
        )

    with DIARIZATION_JSON.open(
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    experiments = data.get(
        "experiments"
    )

    if not isinstance(
        experiments,
        list,
    ):
        raise RuntimeError(
            "Unexpected JSON structure: "
            "'experiments' is not a list."
        )

    selected = None

    for item in experiments:

        if not isinstance(
            item,
            dict,
        ):
            continue

        experiment = item.get(
            "experiment"
        )

        if not isinstance(
            experiment,
            dict,
        ):
            continue

        if (
            experiment.get("name")
            == EXPERIMENT_NAME
        ):
            selected = item
            break

    if selected is None:

        names = []

        for item in experiments:

            experiment = (
                item.get("experiment")
                if isinstance(item, dict)
                else None
            )

            if isinstance(
                experiment,
                dict,
            ):
                names.append(
                    experiment.get("name")
                )

        raise RuntimeError(
            f"Experiment '{EXPERIMENT_NAME}' "
            f"not found.\n"
            f"Available: {names}"
        )

    exclusive = selected.get(
        "exclusive"
    )

    if not isinstance(
        exclusive,
        dict,
    ):
        raise RuntimeError(
            "Missing exclusive diarization data."
        )

    raw_segments = exclusive.get(
        "segments"
    )

    if not isinstance(
        raw_segments,
        list,
    ):
        raise RuntimeError(
            "exclusive.segments is not a list."
        )

    segments = []

    for item in raw_segments:

        if not isinstance(
            item,
            dict,
        ):
            continue

        speaker = item.get(
            "speaker"
        )

        if speaker is None:
            speaker = item.get(
                "speaker_label"
            )

        start = item.get(
            "start"
        )

        end = item.get(
            "end"
        )

        if (
            speaker is None
            or start is None
            or end is None
        ):
            continue

        start = float(start)
        end = float(end)

        duration = end - start

        if duration < MIN_SEGMENT_DURATION:
            continue

        segments.append(
            {
                "speaker": str(speaker),
                "start": start,
                "end": end,
                "duration": duration,
            }
        )

    if not segments:
        raise RuntimeError(
            "No segments survived the duration filter."
        )

    # -------------------------------------------------------------------------
    # Optional per-label cap.
    # -------------------------------------------------------------------------

    if (
        MAX_SEGMENTS_PER_DIARIZATION_LABEL
        is not None
    ):

        grouped = defaultdict(list)

        for segment in segments:

            grouped[
                segment["speaker"]
            ].append(segment)

        limited = []

        for speaker, speaker_segments in (
            grouped.items()
        ):

            speaker_segments.sort(
                key=lambda x: x["duration"],
                reverse=True,
            )

            limited.extend(
                speaker_segments[
                    :MAX_SEGMENTS_PER_DIARIZATION_LABEL
                ]
            )

        segments = limited

    # -------------------------------------------------------------------------
    # Sort chronologically.
    # -------------------------------------------------------------------------

    segments.sort(
        key=lambda x: x["start"]
    )

    print()
    print(
        f"Segments >= {MIN_SEGMENT_DURATION}s:"
    )
    print(len(segments))

    speakers = sorted(
        {
            segment["speaker"]
            for segment in segments
        }
    )

    print()
    print(
        "Diarization labels:"
    )

    for speaker in speakers:

        count = sum(
            1
            for segment in segments
            if segment["speaker"] == speaker
        )

        duration = sum(
            segment["duration"]
            for segment in segments
            if segment["speaker"] == speaker
        )

        print(
            f"  {speaker}: "
            f"{count} segments, "
            f"{duration:.2f}s"
        )

    return segments


# =============================================================================
# AUDIO
# =============================================================================

def load_audio(
    audio_path: Path,
) -> tuple[torch.Tensor, int]:

    print()
    print("=" * 80)
    print("LOADING AUDIO")
    print("=" * 80)

    waveform, sample_rate = (
        torchaudio.load(
            str(audio_path)
        )
    )

    print(
        f"Original sample rate: "
        f"{sample_rate}"
    )

    print(
        f"Original shape: "
        f"{tuple(waveform.shape)}"
    )

    # Mono.
    if waveform.shape[0] > 1:

        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    # Resample.
    if sample_rate != 16000:

        waveform = (
            torchaudio.functional.resample(
                waveform,
                sample_rate,
                16000,
            )
        )

        sample_rate = 16000

    print(
        f"Final sample rate: "
        f"{sample_rate}"
    )

    print(
        f"Final shape: "
        f"{tuple(waveform.shape)}"
    )

    return waveform, sample_rate


# =============================================================================
# SEGMENT EXTRACTION
# =============================================================================

def extract_segment(
    waveform: torch.Tensor,
    sample_rate: int,
    start: float,
    end: float,
) -> torch.Tensor:

    start_sample = max(
        0,
        int(
            round(
                start * sample_rate
            )
        ),
    )

    end_sample = min(
        waveform.shape[-1],
        int(
            round(
                end * sample_rate
            )
        ),
    )

    if end_sample <= start_sample:

        raise ValueError(
            f"Invalid segment: "
            f"{start} -> {end}"
        )

    return waveform[
        :,
        start_sample:end_sample,
    ]


# =============================================================================
# EMBEDDING
# =============================================================================

def generate_embedding(
    embedding_model: Any,
    waveform: torch.Tensor,
) -> np.ndarray:

    waveform = waveform.float()

    # [samples]
    if waveform.ndim == 1:

        waveform = waveform.unsqueeze(0)

    # [channels, samples]
    if waveform.ndim != 2:

        raise ValueError(
            "Expected [channels, samples], "
            f"got {tuple(waveform.shape)}"
        )

    # Ensure mono.
    if waveform.shape[0] != 1:

        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    # -------------------------------------------------------------------------
    # IMPORTANT:
    #
    # Community-1 bundled embedding requires:
    #
    # [batch, channels, samples]
    #
    # => [1, 1, samples]
    # -------------------------------------------------------------------------

    waveforms = waveform.unsqueeze(0)

    if waveforms.ndim != 3:

        raise ValueError(
            f"Expected 3-D input, "
            f"got {tuple(waveforms.shape)}"
        )

    with torch.inference_mode():

        embeddings = embedding_model(
            waveforms
        )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )

    if embeddings.ndim != 2:

        raise ValueError(
            "Unexpected embedding shape: "
            f"{embeddings.shape}"
        )

    if embeddings.shape[0] != 1:

        raise ValueError(
            f"Expected one embedding, "
            f"got shape {embeddings.shape}"
        )

    embedding = embeddings[0]

    return normalize(
        embedding
    )


# =============================================================================
# EXTRACT ALL EMBEDDINGS
# =============================================================================

def extract_all_embeddings(
    pipeline: Pipeline,
    waveform: torch.Tensor,
    sample_rate: int,
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    print()
    print("=" * 80)
    print("EXTRACTING GLOBAL SEGMENT EMBEDDINGS")
    print("=" * 80)

    embedding_model = pipeline._embedding

    print()
    print(
        "Embedding model:"
    )

    print(
        type(embedding_model)
    )

    print()
    print(
        "Embedding dimension:"
    )

    print(
        embedding_model.dimension
    )

    results = []

    total = len(segments)

    for index, segment in enumerate(
        segments,
        start=1,
    ):

        try:

            audio_segment = (
                extract_segment(
                    waveform,
                    sample_rate,
                    segment["start"],
                    segment["end"],
                )
            )

            embedding = (
                generate_embedding(
                    embedding_model,
                    audio_segment,
                )
            )

            result = {
                "index": index,
                "speaker": segment["speaker"],
                "start": segment["start"],
                "end": segment["end"],
                "duration": segment["duration"],
                "embedding": embedding.tolist(),
            }

            results.append(
                result
            )

            print(
                f"[{index:03d}/{total:03d}] "
                f"{segment['speaker']:>10} "
                f"{segment['start']:8.2f} -> "
                f"{segment['end']:8.2f} "
                f"({segment['duration']:5.2f}s)"
            )

        except Exception as exc:

            print(
                f"[{index:03d}/{total:03d}] "
                f"FAILED "
                f"{segment['speaker']} "
                f"{type(exc).__name__}: {exc}"
            )

    if not results:

        raise RuntimeError(
            "No embeddings were generated."
        )

    return results


# =============================================================================
# DIARIZATION-LABEL SIMILARITY
# =============================================================================

def calculate_label_similarity(
    records: list[dict[str, Any]],
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print("DIARIZATION LABEL SIMILARITY")
    print("=" * 80)

    grouped = defaultdict(list)

    for record in records:

        grouped[
            record["speaker"]
        ].append(
            np.asarray(
                record["embedding"],
                dtype=np.float32,
            )
        )

    speakers = sorted(
        grouped.keys()
    )

    # -------------------------------------------------------------------------
    # Create robust prototype using normalized mean.
    # -------------------------------------------------------------------------

    prototypes = {}

    for speaker in speakers:

        matrix = np.vstack(
            grouped[speaker]
        )

        centroid = matrix.mean(
            axis=0
        )

        centroid = normalize(
            centroid
        )

        prototypes[speaker] = centroid

    similarity_matrix = {}

    for speaker_a in speakers:

        similarity_matrix[speaker_a] = {}

        for speaker_b in speakers:

            similarity_matrix[
                speaker_a
            ][speaker_b] = cosine(
                prototypes[speaker_a],
                prototypes[speaker_b],
            )

    print()
    print(
        "Prototype cosine similarity:"
    )

    print()

    header = (
        " " * 12
        + "".join(
            f"{speaker:>12}"
            for speaker in speakers
        )
    )

    print(header)

    for speaker_a in speakers:

        row = f"{speaker_a:>12}"

        for speaker_b in speakers:

            row += (
                f"{similarity_matrix[speaker_a][speaker_b]:12.3f}"
            )

        print(row)

    return {
        "speakers": speakers,
        "prototypes": {
            speaker: prototype.tolist()
            for speaker, prototype in prototypes.items()
        },
        "similarity_matrix": similarity_matrix,
    }


# =============================================================================
# GLOBAL CLUSTERING
# =============================================================================

def perform_global_clustering(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    print()
    print("=" * 80)
    print("GLOBAL VOICE CLUSTERING")
    print("=" * 80)

    embeddings = np.vstack(
        [
            np.asarray(
                record["embedding"],
                dtype=np.float32,
            )
            for record in records
        ]
    )

    # -------------------------------------------------------------------------
    # Cosine distance.
    # -------------------------------------------------------------------------

    distance_matrix = (
        1.0
        - cosine_similarity(
            embeddings
        )
    )

    np.fill_diagonal(
        distance_matrix,
        0.0,
    )

    print()
    print(
        "Embedding matrix:"
    )

    print(
        embeddings.shape
    )

    print()
    print(
        "Exploratory distance threshold:"
    )

    print(
        EXPLORATORY_DISTANCE_THRESHOLD
    )

    # -------------------------------------------------------------------------
    # Agglomerative clustering.
    #
    # IMPORTANT:
    # This is diagnostic only.
    # It does NOT define the final speaker count.
    # -------------------------------------------------------------------------

    clustering = AgglomerativeClustering(
        metric="precomputed",
        linkage="average",
        distance_threshold=(
            EXPLORATORY_DISTANCE_THRESHOLD
        ),
        n_clusters=None,
    )

    labels = clustering.fit_predict(
        distance_matrix
    )

    cluster_count = (
        len(
            set(
                labels.tolist()
            )
        )
    )

    print()
    print(
        f"Exploratory clusters: "
        f"{cluster_count}"
    )

    # -------------------------------------------------------------------------
    # Attach cluster labels.
    # -------------------------------------------------------------------------

    clustered_records = []

    for record, cluster_id in zip(
        records,
        labels,
    ):

        item = dict(record)

        item[
            "voice_cluster"
        ] = int(cluster_id)

        clustered_records.append(
            item
        )

    # -------------------------------------------------------------------------
    # Print clusters.
    # -------------------------------------------------------------------------

    clusters = defaultdict(list)

    for record in clustered_records:

        clusters[
            record["voice_cluster"]
        ].append(
            record
        )

    print()
    print(
        "Clusters:"
    )

    for cluster_id in sorted(
        clusters
    ):

        cluster_records = clusters[
            cluster_id
        ]

        label_counts = defaultdict(int)

        for record in cluster_records:

            label_counts[
                record["speaker"]
            ] += 1

        print()
        print(
            f"VOICE CLUSTER {cluster_id}"
        )

        print(
            f"  Segments: "
            f"{len(cluster_records)}"
        )

        print(
            "  Diarization labels:"
        )

        for speaker, count in sorted(
            label_counts.items()
        ):

            print(
                f"    {speaker}: {count}"
            )

        print(
            "  Segments:"
        )

        for record in cluster_records:

            print(
                f"    "
                f"{record['speaker']} "
                f"{record['start']:.2f}"
                f" -> "
                f"{record['end']:.2f}"
                f" "
                f"({record['duration']:.2f}s)"
            )

    return clustered_records


# =============================================================================
# CROSS-LABEL HIGH-SIMILARITY PAIRS
# =============================================================================

def find_cross_label_pairs(
    records: list[dict[str, Any]],
    top_n: int = 50,
) -> list[dict[str, Any]]:

    pairs = []

    for i in range(
        len(records)
    ):

        a = records[i]

        embedding_a = np.asarray(
            a["embedding"],
            dtype=np.float32,
        )

        for j in range(
            i + 1,
            len(records),
        ):

            b = records[j]

            if (
                a["speaker"]
                == b["speaker"]
            ):
                continue

            embedding_b = np.asarray(
                b["embedding"],
                dtype=np.float32,
            )

            similarity = cosine(
                embedding_a,
                embedding_b,
            )

            pairs.append(
                {
                    "similarity": similarity,
                    "speaker_a": a["speaker"],
                    "index_a": a["index"],
                    "start_a": a["start"],
                    "end_a": a["end"],
                    "speaker_b": b["speaker"],
                    "index_b": b["index"],
                    "start_b": b["start"],
                    "end_b": b["end"],
                }
            )

    pairs.sort(
        key=lambda x: x["similarity"],
        reverse=True,
    )

    print()
    print("=" * 80)
    print("TOP CROSS-DIARIZATION-LABEL VOICE MATCHES")
    print("=" * 80)

    for pair in pairs[:top_n]:

        print(
            f"{pair['speaker_a']}#{pair['index_a']}"
            f" "
            f"({pair['start_a']:.2f}-{pair['end_a']:.2f})"
            f" <-> "
            f"{pair['speaker_b']}#{pair['index_b']}"
            f" "
            f"({pair['start_b']:.2f}-{pair['end_b']:.2f})"
            f" = "
            f"{pair['similarity']:.4f}"
        )

    return pairs[:top_n]


# =============================================================================
# CLUSTER PURITY / LABEL MIXING
# =============================================================================

def calculate_cluster_mixing(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    clusters = defaultdict(list)

    for record in records:

        clusters[
            record["voice_cluster"]
        ].append(
            record
        )

    results = []

    print()
    print("=" * 80)
    print("VOICE CLUSTER / DIARIZATION-LABEL MIXING")
    print("=" * 80)

    for cluster_id in sorted(
        clusters
    ):

        cluster_records = clusters[
            cluster_id
        ]

        counts = defaultdict(int)

        for record in cluster_records:

            counts[
                record["speaker"]
            ] += 1

        total = len(
            cluster_records
        )

        distribution = {
            speaker: count / total
            for speaker, count
            in counts.items()
        }

        result = {
            "voice_cluster": cluster_id,
            "segment_count": total,
            "label_counts": dict(
                counts
            ),
            "label_distribution": distribution,
        }

        results.append(
            result
        )

        print()
        print(
            f"Cluster {cluster_id}: "
            f"{total} segments"
        )

        for speaker, fraction in sorted(
            distribution.items(),
            key=lambda x: x[1],
            reverse=True,
        ):

            print(
                f"  {speaker}: "
                f"{counts[speaker]} "
                f"({fraction:.1%})"
            )

    return results


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    print()
    print("=" * 80)
    print("GLOBAL SPEAKER IDENTITY DIAGNOSTIC")
    print("=" * 80)

    print()
    print(
        "This experiment uses cached diarization only."
    )

    print(
        "No Community-1 diarization rerun is performed."
    )

    print(
        "No speaker count is forced."
    )

    print()

    # -------------------------------------------------------------------------
    # Recording
    # -------------------------------------------------------------------------

    audio_path = (
        find_recording_file()
    )

    print(
        "Recording:"
    )

    print(
        audio_path
    )

    # -------------------------------------------------------------------------
    # Cached segments
    # -------------------------------------------------------------------------

    segments = (
        load_cached_segments()
    )

    # -------------------------------------------------------------------------
    # Load Community-1
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("LOADING COMMUNITY-1")
    print("=" * 80)

    hf_token = os.getenv(
        "HF_TOKEN"
    )

    if not hf_token:

        raise RuntimeError(
            "HF_TOKEN environment variable is not set."
        )

    pipeline = (
        Pipeline.from_pretrained(
            PIPELINE_NAME,
            token=hf_token,
        )
    )

    if pipeline is None:

        raise RuntimeError(
            "Could not load Community-1."
        )

    print(
        "Community-1 loaded."
    )

    print()
    print(
        "Bundled embedding:"
    )

    print(
        type(
            pipeline._embedding
        )
    )

    print(
        "Dimension:",
        pipeline._embedding.dimension,
    )

    # -------------------------------------------------------------------------
    # Audio
    # -------------------------------------------------------------------------

    waveform, sample_rate = (
        load_audio(
            audio_path
        )
    )

    # -------------------------------------------------------------------------
    # Embeddings
    # -------------------------------------------------------------------------

    records = (
        extract_all_embeddings(
            pipeline=pipeline,
            waveform=waveform,
            sample_rate=sample_rate,
            segments=segments,
        )
    )

    print()
    print(
        f"Successfully generated "
        f"{len(records)} embeddings."
    )

    # -------------------------------------------------------------------------
    # Label similarity
    # -------------------------------------------------------------------------

    label_similarity = (
        calculate_label_similarity(
            records
        )
    )

    # -------------------------------------------------------------------------
    # Global clustering
    # -------------------------------------------------------------------------

    clustered_records = (
        perform_global_clustering(
            records
        )
    )

    # -------------------------------------------------------------------------
    # Mixing
    # -------------------------------------------------------------------------

    cluster_mixing = (
        calculate_cluster_mixing(
            clustered_records
        )
    )

    # -------------------------------------------------------------------------
    # Cross-label pairs
    # -------------------------------------------------------------------------

    cross_label_pairs = (
        find_cross_label_pairs(
            records
        )
    )

    # -------------------------------------------------------------------------
    # Save
    # -------------------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = {
        "recording_id": RECORDING_ID,
        "audio": str(audio_path),
        "pipeline": PIPELINE_NAME,
        "experiment": EXPERIMENT_NAME,
        "min_segment_duration": MIN_SEGMENT_DURATION,
        "exploratory_distance_threshold": (
            EXPLORATORY_DISTANCE_THRESHOLD
        ),
        "embedding_dimension": (
            pipeline._embedding.dimension
        ),
        "segment_count": len(records),
        "records": clustered_records,
        "label_similarity": label_similarity,
        "cluster_mixing": cluster_mixing,
        "top_cross_label_pairs": cross_label_pairs,
    }

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
        )

    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)

    print()
    print(
        "Saved:"
    )

    print(
        OUTPUT_JSON
    )

    print()
    print(
        "Global speaker identity diagnostic completed."
    )


if __name__ == "__main__":
    main()