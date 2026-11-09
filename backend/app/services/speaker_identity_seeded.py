from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torchaudio

from pyannote.audio import Pipeline


# ============================================================
# CONFIGURATION
# ============================================================

RECORDING_ID = 7

BACKEND_DIR = Path(__file__).resolve().parents[2]

STORAGE_DIR = (
    BACKEND_DIR
    / "storage"
)

PROCESSED_DIR = (
    STORAGE_DIR
    / "processed"
    / f"recording_{RECORDING_ID}"
)

CACHE_FILE = (
    PROCESSED_DIR
    / "diarization_diagnostic"
    / "diarization_experiments.json"
)

# If your existing cache has a different filename, the fallback
# search below will locate the JSON automatically.

IDENTITY_DIAGNOSTIC_DIR = (
    PROCESSED_DIR
    / "speaker_identity_diagnostic"
)

IDENTITY_RESULTS_FILE = (
    IDENTITY_DIAGNOSTIC_DIR
    / "speaker_identity_results.json"
)

OUTPUT_DIR = (
    PROCESSED_DIR
    / "speaker_identity_seeded_diagnostic"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "speaker_identity_seeded_results.json"
)

MIN_SEGMENT_DURATION = 1.5

TOP_K = 8

STRONG_SIMILARITY = 0.78

SUPPORTING_SIMILARITY = 0.68

ASSIGN_STRONG_THRESHOLD = 0.78

ASSIGN_SUPPORT_THRESHOLD = 0.68

ASSIGN_MARGIN = 0.06


# ============================================================
# CACHE DISCOVERY
# ============================================================

def find_diarization_cache() -> Path:

    candidates = [
        PROCESSED_DIR / "diarization_experiments.json",
        PROCESSED_DIR / "diarization_diagnostic.json",
        PROCESSED_DIR / "diarization_results.json",
    ]

    for candidate in candidates:

        if candidate.exists():
            return candidate

    json_files = list(
        PROCESSED_DIR.rglob("*.json")
    )

    for file in json_files:

        try:

            with file.open(
                "r",
                encoding="utf-8",
            ) as f:

                data = json.load(f)

            if (
                isinstance(data, dict)
                and "experiments" in data
            ):
                return file

        except Exception:
            continue

    raise FileNotFoundError(
        "Could not find the existing diarization "
        "experiment cache under:\n"
        f"{PROCESSED_DIR}"
    )


# ============================================================
# FIND RECORDING AUDIO
# ============================================================

def find_recording_file() -> Path:

    recordings_dir = (
        STORAGE_DIR
        / "recordings"
    )

    if not recordings_dir.exists():

        raise FileNotFoundError(
            f"Recordings directory does not exist:\n"
            f"{recordings_dir}"
        )

    # --------------------------------------------------------
    # Known physical file for Recording 7.
    #
    # The directory name is NOT the database recording ID.
    # --------------------------------------------------------

    known_file = (
        recordings_dir
        / "5"
        / "344d63fd75074ab3a4a19e745f7aa090.mp4"
    )

    if known_file.exists():

        return known_file

    # --------------------------------------------------------
    # Fallback: search for video/audio files.
    # --------------------------------------------------------

    audio_extensions = {
        ".wav",
        ".mp3",
        ".m4a",
        ".mp4",
        ".mov",
        ".webm",
        ".flac",
        ".ogg",
    }

    candidates = [
        p
        for p in recordings_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower()
        in audio_extensions
    ]

    if not candidates:

        raise FileNotFoundError(
            "No recording audio/video file found under:\n"
            f"{recordings_dir}"
        )

    # For this diagnostic there should be only one
    # relevant Recording 7 source. Select the known file
    # if it exists; otherwise fail rather than silently
    # processing the wrong recording.
    if len(candidates) == 1:

        return candidates[0]

    raise RuntimeError(
        "Multiple recording files were found and the "
        "Recording 7 source could not be uniquely determined.\n\n"
        + "\n".join(
            str(p)
            for p in candidates
        )
    )


# ============================================================
# LOAD EXISTING IDENTITY DIAGNOSTIC
# ============================================================

def load_identity_segments() -> List[dict]:
    """
    Load the 91 long segments from the existing speaker identity
    diagnostic.

    IMPORTANT:
    speaker_identity_results.json contains the segment timestamps,
    but does not necessarily contain the original diarization
    speaker label in each segment.

    Therefore this function intentionally loads only:
        - source index
        - start
        - end
        - duration

    The actual Community-1 speaker label is recovered later from
    threshold_060_default.
    """

    if not IDENTITY_RESULTS_FILE.exists():

        raise FileNotFoundError(
            f"Identity diagnostic not found:\n"
            f"{IDENTITY_RESULTS_FILE}"
        )

    with IDENTITY_RESULTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    raw_segments = data.get(
        "segments",
        []
    )

    if not raw_segments:

        raise RuntimeError(
            "No segments were found in "
            "speaker_identity_results.json"
        )

    segments = []

    for index, item in enumerate(
        raw_segments
    ):

        # ----------------------------------------------------
        # The identity diagnostic may use either:
        #
        #   duration
        #
        # or derive duration from:
        #
        #   end - start
        #
        # We support both without changing the source data.
        # ----------------------------------------------------

        start = float(
            item["start"]
        )

        end = float(
            item["end"]
        )

        duration = float(
            item.get(
                "duration",
                end - start,
            )
        )

        if duration < MIN_SEGMENT_DURATION:
            continue

        segments.append(
            {
                "index": index,

                "start": start,

                "end": end,

                "duration": duration,
            }
        )

    return segments

# ============================================================
# LOAD THRESHOLD 0.60 SEGMENTS
# ============================================================

def load_cached_diarization_segments(
    cache_file: Path,
) -> List[dict]:

    with cache_file.open(
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    experiments = data.get(
        "experiments",
        []
    )

    target = None

    for experiment in experiments:

        metadata = experiment.get(
            "experiment",
            {}
        )

        if metadata.get("name") == (
            "threshold_060_default"
        ):
            target = experiment
            break

    if target is None:

        raise RuntimeError(
            "threshold_060_default was not found "
            "in the diarization cache."
        )

    exclusive = target.get(
        "exclusive",
        {}
    )

    segments = exclusive.get(
        "segments",
        []
    )

    if not segments:

        raise RuntimeError(
            "No exclusive diarization segments "
            "were found in threshold_060_default."
        )

    return segments


# ============================================================
# MATCH IDENTITY SEGMENTS TO DIARIZATION SEGMENTS
# ============================================================

def match_segments(
    identity_segments: List[dict],
    diarization_segments: List[dict],
) -> List[dict]:

    output = []

    for identity_segment in identity_segments:

        best = None
        best_overlap = -1.0

        for diar_segment in diarization_segments:

            identity_start = (
                identity_segment["start"]
            )

            identity_end = (
                identity_segment["end"]
            )

            diar_start = float(
                diar_segment["start"]
            )

            diar_end = float(
                diar_segment["end"]
            )

            overlap_start = max(
                identity_start,
                diar_start,
            )

            overlap_end = min(
                identity_end,
                diar_end,
            )

            overlap = max(
                0.0,
                overlap_end - overlap_start,
            )

            if overlap > best_overlap:

                best_overlap = overlap

                best = diar_segment

        if best is None:

            raise RuntimeError(
                "Could not match identity segment "
                f"{identity_segment['index']}"
            )

        output.append(
            {
                **identity_segment,

                "speaker":
                    best["speaker"],

                "matched_diarization_speaker":
                    best["speaker"],

                "matched_overlap":
                    best_overlap,
            }
        )

    return output

# ============================================================
# LOAD COMMUNITY-1
# ============================================================

def load_pipeline():

    hf_token = None

    import os

    hf_token = os.getenv(
        "HF_TOKEN"
    )

    if not hf_token:

        raise RuntimeError(
            "HF_TOKEN is not available in the environment."
        )

    print()
    print(
        "Loading Community-1 pipeline..."
    )

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1",
        token=hf_token,
    )

    if pipeline is None:

        raise RuntimeError(
            "Failed to load Community-1."
        )

    pipeline.to(
        torch.device("cpu")
    )

    print(
        "Community-1 loaded."
    )

    return pipeline


# ============================================================
# LOAD AUDIO
# ============================================================

def load_audio(
    audio_file: Path,
) -> Tuple[torch.Tensor, int]:

    print()
    print(
        f"Loading audio:\n{audio_file}"
    )

    waveform, sample_rate = (
        torchaudio.load(
            str(audio_file)
        )
    )

    # Convert to mono.
    if waveform.shape[0] > 1:

        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    # Community-1 embedding expects 16 kHz.
    if sample_rate != 16000:

        resampler = (
            torchaudio.transforms.Resample(
                orig_freq=sample_rate,
                new_freq=16000,
            )
        )

        waveform = resampler(
            waveform
        )

        sample_rate = 16000

    return waveform, sample_rate


# ============================================================
# EXTRACT COMMUNITY-1 EMBEDDINGS
# ============================================================

def extract_embeddings(
    pipeline,
    waveform: torch.Tensor,
    sample_rate: int,
    segments: List[dict],
) -> List[np.ndarray]:

    embedding_model = getattr(
        pipeline,
        "_embedding",
        None,
    )

    if embedding_model is None:

        raise RuntimeError(
            "Community-1 internal embedding model "
            "could not be accessed."
        )

    print()
    print(
        "Embedding dimension:",
        embedding_model.dimension,
    )

    print(
        "Embedding sample rate:",
        embedding_model.sample_rate,
    )

    embeddings = []

    total = len(segments)

    for position, segment in enumerate(
        segments,
        start=1,
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

        if audio.shape[-1] < 400:

            raise RuntimeError(
                "Audio segment is too short "
                "for Community-1 embedding: "
                f"{segment}"
            )

        # Expected shape:
        #
        # [batch, channels, samples]
        #
        # Here:
        # [1, 1, samples]
        batch = audio.unsqueeze(0)

        with torch.no_grad():

            embedding = (
                embedding_model(
                    batch
                )
            )

        if isinstance(
            embedding,
            torch.Tensor,
        ):

            embedding = (
                embedding
                .detach()
                .cpu()
                .numpy()
            )

        embedding = np.asarray(
            embedding,
            dtype=np.float32,
        )

        if embedding.ndim == 2:

            embedding = embedding[0]

        embedding = normalize(
            embedding
        )

        embeddings.append(
            embedding
        )

        if (
            position % 10 == 0
            or position == total
        ):

            print(
                f"Embedded "
                f"{position}/{total}"
            )

    return embeddings


# ============================================================
# VECTOR HELPERS
# ============================================================

def normalize(
    vector: np.ndarray,
) -> np.ndarray:

    norm = np.linalg.norm(
        vector
    )

    if norm == 0:
        return vector

    return vector / norm


def cosine_similarity(
    a: np.ndarray,
    b: np.ndarray,
) -> float:

    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)

    if (
        a_norm == 0
        or b_norm == 0
    ):
        return 0.0

    return float(
        np.dot(a, b)
        / (a_norm * b_norm)
    )


def duration_weighted_centroid(
    embeddings: List[np.ndarray],
    durations: List[float],
) -> np.ndarray:

    matrix = np.vstack(
        embeddings
    )

    weights = np.asarray(
        durations,
        dtype=np.float32,
    )

    if np.sum(weights) <= 0:

        weights = np.ones(
            len(embeddings),
            dtype=np.float32,
        )

    centroid = np.average(
        matrix,
        axis=0,
        weights=weights,
    )

    return normalize(
        centroid
    )


# ============================================================
# MUTUAL NEAREST NEIGHBORS
# ============================================================

def build_similarity_matrix(
    embeddings: List[np.ndarray],
) -> np.ndarray:

    matrix = np.vstack(
        embeddings
    )

    matrix = matrix / np.maximum(
        np.linalg.norm(
            matrix,
            axis=1,
            keepdims=True,
        ),
        1e-12,
    )

    return matrix @ matrix.T


def build_mutual_pairs(
    similarity: np.ndarray,
) -> List[Tuple[int, int, float]]:

    n = similarity.shape[0]

    nearest = []

    for i in range(n):

        candidates = [
            j
            for j in range(n)
            if j != i
        ]

        candidates.sort(
            key=lambda j:
            similarity[i, j],
            reverse=True,
        )

        nearest.append(
            candidates[:TOP_K]
        )

    pairs = []

    for i in range(n):

        for j in nearest[i]:

            if i >= j:
                continue

            if i in nearest[j]:

                pairs.append(
                    (
                        i,
                        j,
                        float(
                            similarity[i, j]
                        ),
                    )
                )

    return pairs


# ============================================================
# UNION FIND
# ============================================================

class UnionFind:

    def __init__(
        self,
        n: int,
    ):

        self.parent = list(
            range(n)
        )

        self.rank = [
            0
        ] * n

    def find(
        self,
        x: int,
    ) -> int:

        while (
            self.parent[x]
            != x
        ):

            self.parent[x] = (
                self.parent[
                    self.parent[x]
                ]
            )

            x = self.parent[x]

        return x

    def union(
        self,
        a: int,
        b: int,
    ):

        ra = self.find(a)
        rb = self.find(b)

        if ra == rb:
            return

        if (
            self.rank[ra]
            < self.rank[rb]
        ):

            self.parent[ra] = rb

        elif (
            self.rank[ra]
            > self.rank[rb]
        ):

            self.parent[rb] = ra

        else:

            self.parent[rb] = ra

            self.rank[ra] += 1


# ============================================================
# BUILD SEED COMPONENTS
# ============================================================

def build_strong_components(
    segments: List[dict],
    embeddings: List[np.ndarray],
    similarity: np.ndarray,
    mutual_pairs: List[Tuple[int, int, float]],
):

    uf = UnionFind(
        len(segments)
    )

    strong_pairs = []

    for i, j, score in mutual_pairs:

        if score >= STRONG_SIMILARITY:

            uf.union(
                i,
                j,
            )

            strong_pairs.append(
                (
                    i,
                    j,
                    score,
                )
            )

    components = defaultdict(
        list
    )

    for i in range(
        len(segments)
    ):

        root = uf.find(i)

        components[root].append(
            i
        )

    useful = [
        members
        for members in components.values()
        if len(members) >= 2
    ]

    useful.sort(
        key=len,
        reverse=True,
    )

    return useful, strong_pairs


# ============================================================
# CREATE IDENTITY SEEDS
# ============================================================

def create_seeds(
    segments: List[dict],
    embeddings: List[np.ndarray],
    components: List[List[int]],
):

    seeds = []

    used = set()

    seed_number = 1

    # --------------------------------------------------------
    # Strong mutual components
    # --------------------------------------------------------

    for members in components:

        labels = Counter(
            segments[i]["speaker"]
            for i in members
        )

        dominant_label = (
            labels.most_common(1)[0][0]
        )

        purity = (
            labels[dominant_label]
            / len(members)
        )

        centroid = (
            duration_weighted_centroid(
                [
                    embeddings[i]
                    for i in members
                ],
                [
                    segments[i]["duration"]
                    for i in members
                ],
            )
        )

        coherence = [
            cosine_similarity(
                embeddings[i],
                centroid,
            )
            for i in members
        ]

        seeds.append(
            {
                "seed_id":
                    f"IDENTITY_{seed_number:02d}",

                "type":
                    "mutual_strong_component",

                "members":
                    members,

                "labels":
                    dict(labels),

                "dominant_label":
                    dominant_label,

                "purity":
                    purity,

                "size":
                    len(members),

                "coherence_mean":
                    float(
                        np.mean(
                            coherence
                        )
                    ),

                "coherence_median":
                    float(
                        np.median(
                            coherence
                        )
                    ),

                "coherence_min":
                    float(
                        np.min(
                            coherence
                        )
                    ),

                "coherence_max":
                    float(
                        np.max(
                            coherence
                        )
                    ),

                "centroid":
                    centroid,
            }
        )

        used.update(
            members
        )

        seed_number += 1

    # --------------------------------------------------------
    # Stable labels not represented by a strong component
    # --------------------------------------------------------

    by_label = defaultdict(
        list
    )

    for i, segment in enumerate(
        segments
    ):

        by_label[
            segment["speaker"]
        ].append(i)

    for label, indices in sorted(
        by_label.items()
    ):

        remaining = [
            i
            for i in indices
            if i not in used
        ]

        if len(remaining) < 2:
            continue

        centroid = (
            duration_weighted_centroid(
                [
                    embeddings[i]
                    for i in remaining
                ],
                [
                    segments[i]["duration"]
                    for i in remaining
                ],
            )
        )

        coherence = [
            cosine_similarity(
                embeddings[i],
                centroid,
            )
            for i in remaining
        ]

        mean = float(
            np.mean(
                coherence
            )
        )

        median = float(
            np.median(
                coherence
            )
        )

        minimum = float(
            np.min(
                coherence
            )
        )

        # Conservative criterion.
        stable = (
            mean >= 0.82
            and median >= 0.82
            and minimum >= 0.70
        )

        if not stable:
            continue

        seeds.append(
            {
                "seed_id":
                    f"IDENTITY_{seed_number:02d}",

                "type":
                    "stable_original_label",

                "members":
                    remaining,

                "labels":
                    {
                        label:
                        len(remaining)
                    },

                "dominant_label":
                    label,

                "purity":
                    1.0,

                "size":
                    len(remaining),

                "coherence_mean":
                    mean,

                "coherence_median":
                    median,

                "coherence_min":
                    minimum,

                "coherence_max":
                    float(
                        np.max(
                            coherence
                        )
                    ),

                "centroid":
                    centroid,
            }
        )

        used.update(
            remaining
        )

        seed_number += 1

    return seeds


# ============================================================
# ASSIGN SEGMENTS TO SEEDS
# ============================================================

def assign_segments(
    segments: List[dict],
    embeddings: List[np.ndarray],
    seeds: List[dict],
):

    assignments = []

    for i, segment in enumerate(
        segments
    ):

        scores = []

        for seed in seeds:

            score = cosine_similarity(
                embeddings[i],
                seed["centroid"],
            )

            scores.append(
                {
                    "identity":
                        seed["seed_id"],

                    "score":
                        score,
                }
            )

        scores.sort(
            key=lambda x:
            x["score"],
            reverse=True,
        )

        best = scores[0]

        second = (
            scores[1]
            if len(scores) > 1
            else {
                "identity": None,
                "score": -1.0,
            }
        )

        margin = (
            best["score"]
            - second["score"]
        )

        if (
            best["score"]
            >= ASSIGN_STRONG_THRESHOLD
            and margin
            >= ASSIGN_MARGIN
        ):

            status = "strong"

        elif (
            best["score"]
            >= ASSIGN_SUPPORT_THRESHOLD
            and margin
            >= ASSIGN_MARGIN
        ):

            status = "supporting"

        else:

            status = "uncertain"

        assignments.append(
            {
                "segment_index":
                    i,

                "source_index":
                    segment["index"],

                "start":
                    segment["start"],

                "end":
                    segment["end"],

                "duration":
                    segment["duration"],

                "original_speaker":
                    segment["speaker"],

                "resolved_identity":
                    best["identity"],

                "best_score":
                    best["score"],

                "second_identity":
                    second["identity"],

                "second_score":
                    second["score"],

                "margin":
                    margin,

                "status":
                    status,

                "all_scores":
                    scores,
            }
        )

    return assignments


# ============================================================
# ORIGINAL LABEL DISTRIBUTION
# ============================================================

def build_distribution(
    segments: List[dict],
    assignments: List[dict],
):

    distribution = defaultdict(
        Counter
    )

    for segment, assignment in zip(
        segments,
        assignments,
    ):

        distribution[
            segment["speaker"]
        ][
            assignment[
                "resolved_identity"
            ]
        ] += 1

    return {
        label:
        dict(counter)
        for label, counter
        in distribution.items()
    }


# ============================================================
# AMBIGUOUS 02 / 04 REPORT
# ============================================================

def ambiguous_02_04(
    segments: List[dict],
    assignments: List[dict],
):

    output = []

    for segment, assignment in zip(
        segments,
        assignments,
    ):

        if segment["speaker"] not in {
            "SPEAKER_02",
            "SPEAKER_04",
        }:
            continue

        output.append(
            {
                "segment_index":
                    assignment[
                        "segment_index"
                    ],

                "source_index":
                    assignment[
                        "source_index"
                    ],

                "speaker":
                    segment["speaker"],

                "start":
                    segment["start"],

                "end":
                    segment["end"],

                "duration":
                    segment["duration"],

                "resolved_identity":
                    assignment[
                        "resolved_identity"
                    ],

                "best_score":
                    assignment[
                        "best_score"
                    ],

                "second_identity":
                    assignment[
                        "second_identity"
                    ],

                "second_score":
                    assignment[
                        "second_score"
                    ],

                "margin":
                    assignment[
                        "margin"
                    ],

                "status":
                    assignment[
                        "status"
                    ],
            }
        )

    return output


# ============================================================
# SERIALIZATION
# ============================================================

def serialize_seed(
    seed: dict,
):

    output = {
        key: value
        for key, value
        in seed.items()
        if key != "centroid"
    }

    output[
        "centroid_dimension"
    ] = len(
        seed["centroid"]
    )

    return output


# ============================================================
# PRINT REPORT
# ============================================================

def print_report(
    seeds,
    assignments,
    distribution,
    ambiguous,
):

    print()
    print("=" * 80)
    print("IDENTITY SEEDS")
    print("=" * 80)

    for seed in seeds:

        print()

        print(
            seed["seed_id"]
        )

        print(
            f"  Type: "
            f"{seed['type']}"
        )

        print(
            f"  Size: "
            f"{seed['size']}"
        )

        print(
            f"  Labels: "
            f"{seed['labels']}"
        )

        print(
            f"  Dominant label: "
            f"{seed['dominant_label']}"
        )

        print(
            f"  Purity: "
            f"{seed['purity']:.3f}"
        )

        print(
            f"  Coherence mean: "
            f"{seed['coherence_mean']:.4f}"
        )

        print(
            f"  Coherence median: "
            f"{seed['coherence_median']:.4f}"
        )

        print(
            f"  Coherence min: "
            f"{seed['coherence_min']:.4f}"
        )

        print(
            f"  Coherence max: "
            f"{seed['coherence_max']:.4f}"
        )

    counts = Counter(
        assignment["status"]
        for assignment in assignments
    )

    print()
    print("=" * 80)
    print("ASSIGNMENT SUMMARY")
    print("=" * 80)

    print(
        f"Strong:     "
        f"{counts['strong']}"
    )

    print(
        f"Supporting: "
        f"{counts['supporting']}"
    )

    print(
        f"Uncertain:  "
        f"{counts['uncertain']}"
    )

    print()
    print("=" * 80)
    print("ORIGINAL LABEL -> RESOLVED IDENTITY")
    print("=" * 80)

    for label in sorted(
        distribution
    ):

        print()
        print(label)

        total = sum(
            distribution[
                label
            ].values()
        )

        for identity, count in sorted(
            distribution[
                label
            ].items(),
            key=lambda x:
            x[1],
            reverse=True,
        ):

            percentage = (
                count
                / total
                * 100
            )

            print(
                f"  {identity}: "
                f"{count}/{total} "
                f"({percentage:.1f}%)"
            )

    print()
    print("=" * 80)
    print("SPEAKER_02 / SPEAKER_04 ANALYSIS")
    print("=" * 80)

    for item in ambiguous:

        print()

        print(
            f"[{item['segment_index']:03d}] "
            f"{item['speaker']} "
            f"{item['start']:.2f} -> "
            f"{item['end']:.2f}"
        )

        print(
            f"  -> "
            f"{item['resolved_identity']} "
            f"{item['best_score']:.4f}"
        )

        print(
            f"  second: "
            f"{item['second_identity']} "
            f"{item['second_score']:.4f}"
        )

        print(
            f"  margin: "
            f"{item['margin']:.4f}"
        )

        print(
            f"  status: "
            f"{item['status']}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("SEEDED SPEAKER IDENTITY RESOLVER")
    print("=" * 80)

    print()
    print(
        "IMPORTANT: "
        "This reuses existing diarization results."
    )

    print(
        "Whisper will NOT be run."
    )

    print(
        "Community-1 diarization will NOT be run."
    )

    # --------------------------------------------------------
    # Load identity diagnostic
    # --------------------------------------------------------

    identity_segments = (
        load_identity_segments()
    )

    print()
    print(
        f"Identity segments: "
        f"{len(identity_segments)}"
    )

    # --------------------------------------------------------
    # Locate existing diarization cache
    # --------------------------------------------------------

    cache_file = (
        find_diarization_cache()
    )

    print()
    print(
        f"Diarization cache:\n"
        f"{cache_file}"
    )

    diarization_segments = (
        load_cached_diarization_segments(
            cache_file
        )
    )

    print(
        f"Cached diarization segments: "
        f"{len(diarization_segments)}"
    )

    # --------------------------------------------------------
    # Match segments
    # --------------------------------------------------------

    segments = match_segments(
        identity_segments,
        diarization_segments,
    )

    # --------------------------------------------------------
    # Locate audio
    # --------------------------------------------------------

    audio_file = (
        find_recording_file()
    )

    print()
    print(
        f"Recording:\n"
        f"{audio_file}"
    )

    # --------------------------------------------------------
    # Load audio
    # --------------------------------------------------------

    waveform, sample_rate = (
        load_audio(
            audio_file
        )
    )

    print(
        f"Sample rate: "
        f"{sample_rate}"
    )

    print(
        f"Channels: "
        f"{waveform.shape[0]}"
    )

    # --------------------------------------------------------
    # Load Community-1
    # --------------------------------------------------------

    pipeline = (
        load_pipeline()
    )

    # --------------------------------------------------------
    # Extract embeddings
    # --------------------------------------------------------

    embeddings = extract_embeddings(
        pipeline,
        waveform,
        sample_rate,
        segments,
    )

    print()
    print(
        f"Generated embeddings: "
        f"{len(embeddings)}"
    )

    print(
        f"Embedding dimension: "
        f"{len(embeddings[0])}"
    )

    # --------------------------------------------------------
    # Similarity
    # --------------------------------------------------------

    similarity = (
        build_similarity_matrix(
            embeddings
        )
    )

    # --------------------------------------------------------
    # Mutual nearest neighbors
    # --------------------------------------------------------

    mutual_pairs = (
        build_mutual_pairs(
            similarity
        )
    )

    print()
    print(
        f"Mutual nearest-neighbor pairs: "
        f"{len(mutual_pairs)}"
    )

    # --------------------------------------------------------
    # Strong components
    # --------------------------------------------------------

    components, strong_pairs = (
        build_strong_components(
            segments,
            embeddings,
            similarity,
            mutual_pairs,
        )
    )

    print(
        f"Strong mutual components: "
        f"{len(components)}"
    )

    # --------------------------------------------------------
    # Seeds
    # --------------------------------------------------------

    seeds = create_seeds(
        segments,
        embeddings,
        components,
    )

    if not seeds:

        raise RuntimeError(
            "No identity seeds could be created."
        )

    # --------------------------------------------------------
    # Assignment
    # --------------------------------------------------------

    assignments = assign_segments(
        segments,
        embeddings,
        seeds,
    )

    # --------------------------------------------------------
    # Distribution
    # --------------------------------------------------------

    distribution = (
        build_distribution(
            segments,
            assignments,
        )
    )

    # --------------------------------------------------------
    # Ambiguous report
    # --------------------------------------------------------

    ambiguous = (
        ambiguous_02_04(
            segments,
            assignments,
        )
    )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print_report(
        seeds,
        assignments,
        distribution,
        ambiguous,
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "recording_id":
            RECORDING_ID,

        "configuration": {
            "min_segment_duration":
                MIN_SEGMENT_DURATION,

            "top_k":
                TOP_K,

            "strong_similarity":
                STRONG_SIMILARITY,

            "supporting_similarity":
                SUPPORTING_SIMILARITY,

            "assign_strong_threshold":
                ASSIGN_STRONG_THRESHOLD,

            "assign_support_threshold":
                ASSIGN_SUPPORT_THRESHOLD,

            "assign_margin":
                ASSIGN_MARGIN,
        },

        "cache_file":
            str(cache_file),

        "audio_file":
            str(audio_file),

        "segment_count":
            len(segments),

        "mutual_pair_count":
            len(mutual_pairs),

        "strong_pair_count":
            len(strong_pairs),

        "seeds": [
            serialize_seed(seed)
            for seed in seeds
        ],

        "assignments":
            assignments,

        "label_distribution":
            distribution,

        "ambiguous_speaker_02_04":
            ambiguous,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
        )

    print()
    print("=" * 80)
    print("RESULT SAVED")
    print("=" * 80)

    print(
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()