"""
Robust Speaker Identity Layer

Purpose:
    Convert noisy Community-1 diarization labels into more stable
    voice identities using multiple speech segments and the bundled
    Community-1 speaker embedding model.

IMPORTANT:
    This module is diagnostic/experimental for now.

    It does NOT:
        - rerun diarization
        - force a speaker count
        - use transcript grammar
        - use sentence continuity
        - modify the existing production diarization pipeline

Architecture:

    Community-1 diarization
            |
            v
    candidate speech segments
            |
            v
    quality filtering
            |
            v
    multiple voice embeddings
            |
            v
    robust label prototypes
            |
            v
    pairwise identity evidence
            |
            v
    stable identity groups
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torchaudio
from pyannote.audio import Pipeline
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================================
# CONFIGURATION
# ============================================================================

RECORDING_ID = 7

PIPELINE_NAME = "pyannote/speaker-diarization-community-1"

EXPERIMENT_NAME = "threshold_060_default"

MIN_SEGMENT_DURATION = 1.5

# Prefer longer speech for identity modeling.
PROTOTYPE_MIN_DURATION = 2.5

# Maximum number of strongest segments used to construct a label prototype.
MAX_PROTOTYPE_SEGMENTS = 8

# Minimum number of useful segments needed before a label becomes
# a strong identity candidate.
MIN_IDENTITY_SEGMENTS = 2

# Similarity values are diagnostic, NOT universal truth.
#
# We deliberately use two levels:
#
#   STRONG_SIMILARITY
#       Strong evidence that two observations may represent the same voice.
#
#   SUPPORTING_SIMILARITY
#       Useful supporting evidence but insufficient by itself.
#
STRONG_SIMILARITY = 0.78
SUPPORTING_SIMILARITY = 0.68

# A pair needs multiple supporting observations before we consider
# the relationship strong enough to form an identity edge.
MIN_STRONG_PAIRS = 2

# Weight longer segments slightly more heavily.
DURATION_WEIGHT_POWER = 0.5


# ============================================================================
# PATHS
# ============================================================================

BACKEND_DIR = Path(__file__).resolve().parents[2]

RECORDING_PATH = (
    BACKEND_DIR
    / "storage"
    / "recordings"
    / "5"
    / "344d63fd75074ab3a4a19e745f7aa090.mp4"
)

CACHE_PATH = (
    BACKEND_DIR
    / "storage"
    / "processed"
    / f"recording_{RECORDING_ID}"
    / "diarization_clustering_experiments.json"
)

OUTPUT_DIR = (
    BACKEND_DIR
    / "storage"
    / "processed"
    / f"recording_{RECORDING_ID}"
    / "speaker_identity_diagnostic"
)

OUTPUT_PATH = OUTPUT_DIR / "speaker_identity_results.json"


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class SegmentEmbedding:
    index: int
    speaker_label: str
    start: float
    end: float
    duration: float
    embedding: np.ndarray

    @property
    def key(self) -> str:
        return f"{self.speaker_label}#{self.index}"


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def normalize_embedding(vector: np.ndarray) -> np.ndarray:
    """
    L2-normalize an embedding.
    """
    vector = np.asarray(vector, dtype=np.float32)

    norm = np.linalg.norm(vector)

    if norm <= 1e-12:
        return vector

    return vector / norm


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two vectors.
    """
    a = normalize_embedding(a)
    b = normalize_embedding(b)

    return float(np.dot(a, b))


def weighted_centroid(
    embeddings: list[np.ndarray],
    weights: list[float],
) -> np.ndarray:
    """
    Calculate a weighted normalized centroid.
    """
    if not embeddings:
        raise ValueError("Cannot calculate centroid from zero embeddings.")

    matrix = np.vstack(embeddings)

    weight_array = np.asarray(weights, dtype=np.float32)

    if np.sum(weight_array) <= 0:
        weight_array = np.ones(len(embeddings), dtype=np.float32)

    centroid = np.average(
        matrix,
        axis=0,
        weights=weight_array,
    )

    return normalize_embedding(centroid)


# ============================================================================
# LOAD CACHE
# ============================================================================


def load_cached_segments() -> list[dict[str, Any]]:
    """
    Load exclusive diarization segments from the cached
    threshold_060_default experiment.

    No diarization is performed here.
    """

    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            f"Cached diarization file not found:\n{CACHE_PATH}"
        )

    with CACHE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            "Unexpected cache format: top-level JSON "
            "value is not an object."
        )

    experiments = data.get("experiments")

    if not isinstance(experiments, list):
        raise ValueError(
            "Unexpected cache format: 'experiments' "
            "is not a list."
        )

    selected_experiment = None

    for item in experiments:

        if not isinstance(item, dict):
            continue

        experiment_info = item.get("experiment")

        if not isinstance(
            experiment_info,
            dict,
        ):
            continue

        if experiment_info.get("name") == EXPERIMENT_NAME:
            selected_experiment = item
            break

    if selected_experiment is None:

        available_experiments = []

        for item in experiments:

            if not isinstance(item, dict):
                continue

            experiment_info = item.get("experiment")

            if isinstance(
                experiment_info,
                dict,
            ):
                name = experiment_info.get("name")

                if name:
                    available_experiments.append(name)

        raise ValueError(
            f"Experiment '{EXPERIMENT_NAME}' was not found.\n"
            f"Available experiments:\n"
            f"{available_experiments}"
        )

    experiment_info = selected_experiment["experiment"]

    print(
        f"Found cached experiment: "
        f"{experiment_info.get('name')}"
    )

    print(
        f"Threshold: "
        f"{experiment_info.get('threshold')}"
    )

    print(
        f"Fa: "
        f"{experiment_info.get('Fa')}"
    )

    print(
        f"Fb: "
        f"{experiment_info.get('Fb')}"
    )

    exclusive = selected_experiment.get("exclusive")

    if not isinstance(
        exclusive,
        dict,
    ):
        raise ValueError(
            "Selected experiment does not contain "
            "an 'exclusive' object."
        )

    segments = exclusive.get("segments")

    if not isinstance(
        segments,
        list,
    ):
        raise ValueError(
            "Selected experiment does not contain "
            "an exclusive 'segments' list."
        )

    print(
        f"Cached exclusive segments: "
        f"{len(segments)}"
    )

    filtered = []

    for segment in segments:

        if not isinstance(
            segment,
            dict,
        ):
            continue

        speaker = segment.get("speaker")

        if not speaker:
            continue

        try:
            start = float(segment["start"])
            end = float(segment["end"])
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        duration = end - start

        if duration < MIN_SEGMENT_DURATION:
            continue

        filtered.append(
            {
                "speaker": speaker,
                "start": start,
                "end": end,
                "duration": duration,
            }
        )

    filtered.sort(
        key=lambda item: item["start"]
    )

    if not filtered:
        raise ValueError(
            f"No exclusive segments >= "
            f"{MIN_SEGMENT_DURATION}s were found."
        )

    return filtered

# ============================================================================
# LOAD AUDIO
# ============================================================================


def load_audio() -> tuple[torch.Tensor, int]:
    """
    Load the complete meeting audio.
    """
    if not RECORDING_PATH.exists():
        raise FileNotFoundError(
            f"Recording file not found:\n{RECORDING_PATH}"
        )

    waveform, sample_rate = torchaudio.load(str(RECORDING_PATH))

    print(f"Original sample rate: {sample_rate}")
    print(f"Original shape: {tuple(waveform.shape)}")

    # Community-1 embedding expects mono 16 kHz.
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    if sample_rate != 16000:
        waveform = torchaudio.functional.resample(
            waveform,
            sample_rate,
            16000,
        )
        sample_rate = 16000

    print(f"Final sample rate: {sample_rate}")
    print(f"Final shape: {tuple(waveform.shape)}")

    return waveform, sample_rate


# ============================================================================
# LOAD COMMUNITY-1 EMBEDDING
# ============================================================================


def load_pipeline() -> Pipeline:
    """
    Load Community-1.

    We use its bundled embedding model rather than pyannote/embedding,
    because the latter is a separate gated model and is not required here.
    """
    print()
    print("=" * 80)
    print("LOADING COMMUNITY-1")
    print("=" * 80)

    pipeline = Pipeline.from_pretrained(PIPELINE_NAME)

    if pipeline is None:
        raise RuntimeError("Failed to load Community-1.")

    print("Community-1 loaded.")

    embedding_model = getattr(pipeline, "_embedding", None)

    if embedding_model is None:
        raise RuntimeError(
            "Community-1 does not expose its bundled embedding model."
        )

    print()
    print("Bundled embedding:")
    print(type(embedding_model))

    dimension = getattr(embedding_model, "dimension", None)

    print("Embedding dimension:")
    print(dimension)

    return pipeline


# ============================================================================
# EMBEDDING EXTRACTION
# ============================================================================


def extract_embedding(
    embedding_model: Any,
    waveform: torch.Tensor,
    start: float,
    end: float,
    sample_rate: int,
) -> np.ndarray:
    """
    Extract one embedding.

    Required input shape:

        [batch, channels, samples]

    For one mono segment:

        [1, 1, samples]
    """
    start_sample = max(
        0,
        int(round(start * sample_rate)),
    )

    end_sample = min(
        waveform.shape[-1],
        int(round(end * sample_rate)),
    )

    segment = waveform[:, start_sample:end_sample]

    if segment.shape[-1] <= 0:
        raise ValueError(
            f"Invalid segment: {start:.2f} -> {end:.2f}"
        )

    # [channels, samples] -> [batch, channels, samples]
    segment = segment.unsqueeze(0)

    with torch.inference_mode():
        embedding = embedding_model(segment)

    embedding = np.asarray(embedding)

    if embedding.ndim != 2 or embedding.shape[0] != 1:
        raise RuntimeError(
            f"Unexpected embedding shape: {embedding.shape}"
        )

    return normalize_embedding(embedding[0])


# ============================================================================
# EXTRACT ALL EMBEDDINGS
# ============================================================================


def extract_all_embeddings(
    segments: list[dict[str, Any]],
    waveform: torch.Tensor,
    sample_rate: int,
    pipeline: Pipeline,
) -> list[SegmentEmbedding]:

    embedding_model = pipeline._embedding

    results: list[SegmentEmbedding] = []

    print()
    print("=" * 80)
    print("EXTRACTING SPEAKER EMBEDDINGS")
    print("=" * 80)

    total = len(segments)

    for number, segment in enumerate(segments, start=1):

        speaker = segment["speaker"]
        start = segment["start"]
        end = segment["end"]
        duration = segment["duration"]

        embedding = extract_embedding(
            embedding_model=embedding_model,
            waveform=waveform,
            start=start,
            end=end,
            sample_rate=sample_rate,
        )

        item = SegmentEmbedding(
            index=number,
            speaker_label=speaker,
            start=start,
            end=end,
            duration=duration,
            embedding=embedding,
        )

        results.append(item)

        print(
            f"[{number:03d}/{total:03d}] "
            f"{speaker:<12} "
            f"{start:8.2f} -> {end:8.2f} "
            f"({duration:5.2f}s)"
        )

    print()
    print(f"Generated embeddings: {len(results)}")

    return results


# ============================================================================
# GROUP BY DIARIZATION LABEL
# ============================================================================


def group_by_label(
    embeddings: list[SegmentEmbedding],
) -> dict[str, list[SegmentEmbedding]]:

    grouped: dict[str, list[SegmentEmbedding]] = defaultdict(list)

    for item in embeddings:
        grouped[item.speaker_label].append(item)

    return dict(grouped)


# ============================================================================
# SELECT PROTOTYPE SEGMENTS
# ============================================================================


def select_prototype_segments(
    items: list[SegmentEmbedding],
) -> list[SegmentEmbedding]:
    """
    Select the strongest observations for a diarization label.

    Longer segments are preferred because they generally provide
    more stable speaker evidence.
    """
    eligible = [
        item
        for item in items
        if item.duration >= PROTOTYPE_MIN_DURATION
    ]

    eligible.sort(
        key=lambda item: item.duration,
        reverse=True,
    )

    return eligible[:MAX_PROTOTYPE_SEGMENTS]


# ============================================================================
# BUILD ROBUST LABEL PROTOTYPE
# ============================================================================


def build_label_prototypes(
    grouped: dict[str, list[SegmentEmbedding]],
) -> tuple[
    dict[str, np.ndarray],
    dict[str, list[SegmentEmbedding]],
]:
    """
    Build one robust prototype per Community-1 diarization label.
    """
    prototypes: dict[str, np.ndarray] = {}

    selected_segments: dict[str, list[SegmentEmbedding]] = {}

    print()
    print("=" * 80)
    print("BUILDING ROBUST DIARIZATION-LABEL PROTOTYPES")
    print("=" * 80)

    for speaker in sorted(grouped.keys()):

        items = grouped[speaker]

        selected = select_prototype_segments(items)

        selected_segments[speaker] = selected

        if not selected:
            print(
                f"{speaker}: NO eligible prototype segments"
            )
            continue

        embeddings = [
            item.embedding
            for item in selected
        ]

        weights = [
            math.pow(
                max(item.duration, 1.0),
                DURATION_WEIGHT_POWER,
            )
            for item in selected
        ]

        prototype = weighted_centroid(
            embeddings,
            weights,
        )

        prototypes[speaker] = prototype

        print(
            f"{speaker}: "
            f"{len(items)} total segments, "
            f"{len(selected)} prototype segments"
        )

        for item in selected:
            print(
                f"    {item.start:8.2f} -> "
                f"{item.end:8.2f} "
                f"({item.duration:5.2f}s)"
            )

    return prototypes, selected_segments


# ============================================================================
# PROTOTYPE SIMILARITY
# ============================================================================


def calculate_prototype_similarity(
    prototypes: dict[str, np.ndarray],
) -> dict[str, dict[str, float]]:

    labels = sorted(prototypes.keys())

    matrix = np.vstack(
        [
            prototypes[label]
            for label in labels
        ]
    )

    similarities = cosine_similarity(matrix)

    result: dict[str, dict[str, float]] = {}

    for i, label_a in enumerate(labels):

        result[label_a] = {}

        for j, label_b in enumerate(labels):

            result[label_a][label_b] = float(
                similarities[i, j]
            )

    return result


def print_prototype_similarity(
    similarity: dict[str, dict[str, float]],
) -> None:

    labels = sorted(similarity.keys())

    print()
    print("=" * 80)
    print("ROBUST PROTOTYPE SIMILARITY")
    print("=" * 80)

    header = " " * 14

    for label in labels:
        header += f"{label:>13}"

    print(header)

    for label_a in labels:

        row = f"{label_a:<14}"

        for label_b in labels:
            row += f"{similarity[label_a][label_b]:13.3f}"

        print(row)


# ============================================================================
# CROSS-LABEL OBSERVATION EVIDENCE
# ============================================================================


def calculate_cross_label_evidence(
    embeddings: list[SegmentEmbedding],
) -> list[dict[str, Any]]:

    results: list[dict[str, Any]] = []

    for i in range(len(embeddings)):

        a = embeddings[i]

        for j in range(i + 1, len(embeddings)):

            b = embeddings[j]

            if a.speaker_label == b.speaker_label:
                continue

            similarity = cosine(
                a.embedding,
                b.embedding,
            )

            results.append(
                {
                    "a": a,
                    "b": b,
                    "similarity": similarity,
                }
            )

    results.sort(
        key=lambda item: item["similarity"],
        reverse=True,
    )

    return results


# ============================================================================
# BUILD IDENTITY GRAPH
# ============================================================================


class UnionFind:
    """
    Small disjoint-set implementation.

    Used only for the experimental identity graph.
    """

    def __init__(self, items: list[str]):
        self.parent = {
            item: item
            for item in items
        }

    def find(self, item: str) -> str:

        if self.parent[item] != item:
            self.parent[item] = self.find(
                self.parent[item]
            )

        return self.parent[item]

    def union(self, a: str, b: str) -> None:

        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        self.parent[root_b] = root_a


def build_identity_graph(
    embeddings: list[SegmentEmbedding],
) -> tuple[
    UnionFind,
    dict[tuple[str, str], dict[str, Any]],
]:

    labels = sorted(
        {
            item.speaker_label
            for item in embeddings
        }
    )

    union_find = UnionFind(labels)

    pair_evidence: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    observations = calculate_cross_label_evidence(
        embeddings
    )

    for observation in observations:

        a: SegmentEmbedding = observation["a"]
        b: SegmentEmbedding = observation["b"]

        similarity = observation["similarity"]

        labels_pair = tuple(
            sorted(
                [
                    a.speaker_label,
                    b.speaker_label,
                ]
            )
        )

        if labels_pair not in pair_evidence:

            pair_evidence[labels_pair] = {
                "strong_pairs": 0,
                "supporting_pairs": 0,
                "best_similarity": -1.0,
                "top_matches": [],
            }

        evidence = pair_evidence[labels_pair]

        if similarity >= STRONG_SIMILARITY:
            evidence["strong_pairs"] += 1

        if similarity >= SUPPORTING_SIMILARITY:
            evidence["supporting_pairs"] += 1

        evidence["best_similarity"] = max(
            evidence["best_similarity"],
            similarity,
        )

        if len(evidence["top_matches"]) < 5:
            evidence["top_matches"].append(
                {
                    "speaker_a": a.speaker_label,
                    "speaker_b": b.speaker_label,
                    "start_a": a.start,
                    "end_a": a.end,
                    "start_b": b.start,
                    "end_b": b.end,
                    "similarity": similarity,
                }
            )

    # Only create an identity edge when we have repeated evidence.
    #
    # This is intentionally conservative.
    for pair, evidence in pair_evidence.items():

        if (
            evidence["strong_pairs"]
            >= MIN_STRONG_PAIRS
        ):
            union_find.union(
                pair[0],
                pair[1],
            )

    return union_find, pair_evidence


# ============================================================================
# IDENTITY GROUPS
# ============================================================================


def build_identity_groups(
    union_find: UnionFind,
    labels: list[str],
) -> dict[str, list[str]]:

    groups: dict[str, list[str]] = defaultdict(list)

    for label in labels:

        root = union_find.find(label)

        groups[root].append(label)

    return {
        root: sorted(members)
        for root, members in groups.items()
    }


# ============================================================================
# DIAGNOSTIC REPORT
# ============================================================================


def print_identity_groups(
    groups: dict[str, list[str]],
) -> None:

    print()
    print("=" * 80)
    print("EXPERIMENTAL IDENTITY GROUPS")
    print("=" * 80)

    for number, members in enumerate(
        sorted(groups.values()),
        start=1,
    ):

        print()
        print(
            f"IDENTITY GROUP {number}"
        )

        for member in members:
            print(
                f"    {member}"
            )


def print_top_cross_label_matches(
    pair_evidence: dict[
        tuple[str, str],
        dict[str, Any],
    ],
) -> None:

    matches = []

    for pair, evidence in pair_evidence.items():

        for match in evidence["top_matches"]:

            matches.append(match)

    matches.sort(
        key=lambda item: item["similarity"],
        reverse=True,
    )

    print()
    print("=" * 80)
    print("TOP CROSS-LABEL VOICE EVIDENCE")
    print("=" * 80)

    for match in matches[:30]:

        print(
            f"{match['speaker_a']} "
            f"{match['start_a']:.2f}-{match['end_a']:.2f}"
            f" <-> "
            f"{match['speaker_b']} "
            f"{match['start_b']:.2f}-{match['end_b']:.2f}"
            f" = "
            f"{match['similarity']:.4f}"
        )


# ============================================================================
# SAVE RESULTS
# ============================================================================


def serialize_embedding_item(
    item: SegmentEmbedding,
) -> dict[str, Any]:

    return {
        "index": item.index,
        "speaker_label": item.speaker_label,
        "start": item.start,
        "end": item.end,
        "duration": item.duration,
    }


def save_results(
    segments: list[SegmentEmbedding],
    prototypes: dict[str, np.ndarray],
    selected_segments: dict[str, list[SegmentEmbedding]],
    prototype_similarity: dict[str, dict[str, float]],
    identity_groups: dict[str, list[str]],
    pair_evidence: dict[
        tuple[str, str],
        dict[str, Any],
    ],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    labels = sorted(
        {
            item.speaker_label
            for item in segments
        }
    )

    serialized_pairs = {}

    for pair, evidence in pair_evidence.items():

        serialized_pairs[
            f"{pair[0]}__{pair[1]}"
        ] = {
            "strong_pairs": evidence["strong_pairs"],
            "supporting_pairs": evidence["supporting_pairs"],
            "best_similarity": evidence["best_similarity"],
            "top_matches": evidence["top_matches"],
        }

    data = {
        "recording_id": RECORDING_ID,
        "recording_path": str(RECORDING_PATH),
        "pipeline": PIPELINE_NAME,
        "experiment": EXPERIMENT_NAME,
        "configuration": {
            "min_segment_duration": MIN_SEGMENT_DURATION,
            "prototype_min_duration": PROTOTYPE_MIN_DURATION,
            "max_prototype_segments": MAX_PROTOTYPE_SEGMENTS,
            "min_identity_segments": MIN_IDENTITY_SEGMENTS,
            "strong_similarity": STRONG_SIMILARITY,
            "supporting_similarity": SUPPORTING_SIMILARITY,
            "min_strong_pairs": MIN_STRONG_PAIRS,
            "duration_weight_power": DURATION_WEIGHT_POWER,
        },
        "labels": labels,
        "segment_count": len(segments),
        "prototype_count": len(prototypes),
        "prototype_similarity": prototype_similarity,
        "prototype_segments": {
            label: [
                serialize_embedding_item(item)
                for item in selected_segments.get(
                    label,
                    [],
                )
            ]
            for label in labels
        },
        "identity_groups": list(
            identity_groups.values()
        ),
        "pair_evidence": serialized_pairs,
        "segments": [
            serialize_embedding_item(item)
            for item in segments
        ],
        "embeddings": [
            item.embedding.tolist()
            for item in segments
    ],
    }

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
        )

    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)
    print()
    print(f"Saved:")
    print(OUTPUT_PATH)


# ============================================================================
# MAIN
# ============================================================================


def main() -> None:

    print()
    print("=" * 80)
    print("ROBUST SPEAKER IDENTITY DIAGNOSTIC")
    print("=" * 80)
    print()
    print("Cached diarization only.")
    print("No Community-1 diarization rerun.")
    print("No speaker count forced.")
    print("No transcript heuristics.")
    print()

    print(f"Recording:")
    print(RECORDING_PATH)

    # ----------------------------------------------------------------------
    # Load cached diarization
    # ----------------------------------------------------------------------

    print()
    print("=" * 80)
    print("LOADING CACHED DIARIZATION")
    print("=" * 80)

    segments = load_cached_segments()

    print()
    print(f"Segments >= {MIN_SEGMENT_DURATION}s:")
    print(len(segments))

    grouped_preview = defaultdict(list)

    for segment in segments:
        grouped_preview[
            segment["speaker"]
        ].append(segment)

    print()
    print("Diarization labels:")

    for speaker in sorted(grouped_preview.keys()):

        items = grouped_preview[speaker]

        duration = sum(
            item["duration"]
            for item in items
        )

        print(
            f"  {speaker}: "
            f"{len(items)} segments, "
            f"{duration:.2f}s"
        )

    # ----------------------------------------------------------------------
    # Load pipeline
    # ----------------------------------------------------------------------

    pipeline = load_pipeline()

    # ----------------------------------------------------------------------
    # Load audio
    # ----------------------------------------------------------------------

    print()
    print("=" * 80)
    print("LOADING AUDIO")
    print("=" * 80)

    waveform, sample_rate = load_audio()

    # ----------------------------------------------------------------------
    # Embeddings
    # ----------------------------------------------------------------------

    embeddings = extract_all_embeddings(
        segments=segments,
        waveform=waveform,
        sample_rate=sample_rate,
        pipeline=pipeline,
    )

    # ----------------------------------------------------------------------
    # Group labels
    # ----------------------------------------------------------------------

    grouped = group_by_label(
        embeddings
    )

    # ----------------------------------------------------------------------
    # Robust prototypes
    # ----------------------------------------------------------------------

    prototypes, selected_segments = (
        build_label_prototypes(
            grouped
        )
    )

    # ----------------------------------------------------------------------
    # Prototype similarity
    # ----------------------------------------------------------------------

    prototype_similarity = (
        calculate_prototype_similarity(
            prototypes
        )
    )

    print_prototype_similarity(
        prototype_similarity
    )

    # ----------------------------------------------------------------------
    # Identity graph
    # ----------------------------------------------------------------------

    union_find, pair_evidence = (
        build_identity_graph(
            embeddings
        )
    )

    labels = sorted(grouped.keys())

    identity_groups = build_identity_groups(
        union_find,
        labels,
    )

    print_identity_groups(
        identity_groups
    )

    # ----------------------------------------------------------------------
    # Cross-label evidence
    # ----------------------------------------------------------------------

    print_top_cross_label_matches(
        pair_evidence
    )

    # ----------------------------------------------------------------------
    # Save
    # ----------------------------------------------------------------------

    save_results(
        segments=embeddings,
        prototypes=prototypes,
        selected_segments=selected_segments,
        prototype_similarity=prototype_similarity,
        identity_groups=identity_groups,
        pair_evidence=pair_evidence,
    )

    print()
    print("Robust speaker identity diagnostic completed.")


if __name__ == "__main__":
    main()