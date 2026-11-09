from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
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

IDENTITY_RESULTS_FILE = (
    PROCESSED_DIR
    / "speaker_identity_diagnostic"
    / "speaker_identity_results.json"
)

OUTPUT_DIR = (
    PROCESSED_DIR
    / "speaker_identity_validation_diagnostic"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "speaker_identity_validation_results.json"
)

# Known physical file for Recording 7.
AUDIO_FILE = (
    STORAGE_DIR
    / "recordings"
    / "5"
    / "344d63fd75074ab3a4a19e745f7aa090.mp4"
)


# ------------------------------------------------------------
# Segment quality
# ------------------------------------------------------------

MIN_ANCHOR_DURATION = 3.0

MIN_EVALUATION_DURATION = 1.5

MAX_ANCHORS_PER_LABEL = 10


# ------------------------------------------------------------
# Nearest-neighbor graph
# ------------------------------------------------------------

TOP_K = 8

STRONG_SIMILARITY = 0.78

SUPPORTING_SIMILARITY = 0.68


# ------------------------------------------------------------
# Identity seed requirements
# ------------------------------------------------------------

MIN_SEED_SIZE = 3

MIN_SEED_COHERENCE = 0.78

MAX_SEED_CROSS_SIMILARITY = 0.72


# ------------------------------------------------------------
# Assignment requirements
# ------------------------------------------------------------

STRONG_ASSIGNMENT = 0.80

SUPPORTING_ASSIGNMENT = 0.72

MIN_ASSIGNMENT_MARGIN = 0.08

MIN_STRONG_SUPPORT_COUNT = 2


# ============================================================
# UNION FIND
# ============================================================

class UnionFind:

    def __init__(self, n: int):

        self.parent = list(
            range(n)
        )

        self.rank = [
            0
        ] * n

    def find(self, x: int) -> int:

        while self.parent[x] != x:

            self.parent[x] = (
                self.parent[
                    self.parent[x]
                ]
            )

            x = self.parent[x]

        return x

    def union(self, a: int, b: int):

        ra = self.find(a)
        rb = self.find(b)

        if ra == rb:
            return

        if self.rank[ra] < self.rank[rb]:

            self.parent[ra] = rb

        elif self.rank[ra] > self.rank[rb]:

            self.parent[rb] = ra

        else:

            self.parent[rb] = ra
            self.rank[ra] += 1


# ============================================================
# VECTOR FUNCTIONS
# ============================================================

def normalize(
    vector: np.ndarray,
) -> np.ndarray:

    norm = np.linalg.norm(vector)

    if norm == 0:
        return vector

    return vector / norm


def cosine(
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


def weighted_centroid(
    embeddings,
    durations,
):

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
# LOAD SEGMENTS
# ============================================================

def load_segments():

    if not IDENTITY_RESULTS_FILE.exists():

        raise FileNotFoundError(
            f"Missing identity diagnostic:\n"
            f"{IDENTITY_RESULTS_FILE}"
        )

    with IDENTITY_RESULTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    raw_segments = data.get(
        "segments",
        [],
    )

    if not raw_segments:

        raise RuntimeError(
            "No segments found in identity diagnostic."
        )

    segments = []

    for source_index, item in enumerate(
        raw_segments
    ):

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

        if duration < MIN_EVALUATION_DURATION:

            continue

        segments.append(
            {
                "source_index":
                    source_index,

                "start":
                    start,

                "end":
                    end,

                "duration":
                    duration,

                # The previous diagnostic's speaker label
                # is not assumed here. It will be recovered
                # from the original diarization cache.
            }
        )

    return segments


# ============================================================
# LOAD ORIGINAL DIARIZATION LABELS
# ============================================================

def find_cache():

    candidates = list(
        PROCESSED_DIR.rglob(
            "*.json"
        )
    )

    for candidate in candidates:

        try:

            with candidate.open(
                "r",
                encoding="utf-8",
            ) as f:

                data = json.load(f)

            if "experiments" not in data:
                continue

            for experiment in data[
                "experiments"
            ]:

                metadata = experiment.get(
                    "experiment",
                    {},
                )

                if metadata.get(
                    "name"
                ) == "threshold_060_default":

                    return candidate

        except Exception:
            continue

    raise FileNotFoundError(
        "Could not locate threshold_060_default cache."
    )


def load_original_diarization():

    cache_file = find_cache()

    with cache_file.open(
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    target = None

    for experiment in data[
        "experiments"
    ]:

        metadata = experiment.get(
            "experiment",
            {},
        )

        if metadata.get(
            "name"
        ) == "threshold_060_default":

            target = experiment
            break

    if target is None:

        raise RuntimeError(
            "threshold_060_default not found."
        )

    segments = target[
        "exclusive"
    ][
        "segments"
    ]

    return cache_file, segments


def attach_original_labels(
    identity_segments,
    diarization_segments,
):

    output = []

    for segment in identity_segments:

        best = None
        best_overlap = 0.0

        for diar in diarization_segments:

            overlap_start = max(
                segment["start"],
                float(
                    diar["start"]
                ),
            )

            overlap_end = min(
                segment["end"],
                float(
                    diar["end"]
                ),
            )

            overlap = max(
                0.0,
                overlap_end
                - overlap_start,
            )

            if overlap > best_overlap:

                best_overlap = overlap
                best = diar

        if best is None:

            raise RuntimeError(
                "Could not match segment "
                f"{segment['source_index']}"
            )

        item = dict(segment)

        item[
            "original_speaker"
        ] = best["speaker"]

        item[
            "overlap"
        ] = best_overlap

        output.append(item)

    return output


# ============================================================
# AUDIO
# ============================================================

def load_audio():

    if not AUDIO_FILE.exists():

        raise FileNotFoundError(
            f"Recording 7 audio not found:\n"
            f"{AUDIO_FILE}"
        )

    waveform, sample_rate = (
        torchaudio.load(
            str(AUDIO_FILE)
        )
    )

    if waveform.shape[0] > 1:

        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    if sample_rate != 16000:

        resampler = (
            torchaudio.transforms.Resample(
                sample_rate,
                16000,
            )
        )

        waveform = resampler(
            waveform
        )

        sample_rate = 16000

    return waveform, sample_rate


# ============================================================
# COMMUNITY-1 EMBEDDING
# ============================================================

def load_pipeline():

    token = os.getenv(
        "HF_TOKEN"
    )

    if not token:

        raise RuntimeError(
            "HF_TOKEN is not available."
        )

    print()
    print(
        "Loading Community-1..."
    )

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1",
        token=token,
    )

    pipeline.to(
        torch.device("cpu")
    )

    print(
        "Community-1 loaded."
    )

    return pipeline


def extract_embeddings(
    pipeline,
    waveform,
    sample_rate,
    segments,
):

    embedding_model = getattr(
        pipeline,
        "_embedding",
        None,
    )

    if embedding_model is None:

        raise RuntimeError(
            "Community-1 bundled embedding model "
            "is unavailable."
        )

    print()
    print(
        "Embedding dimension:",
        embedding_model.dimension,
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
                f"Segment too short: {segment}"
            )

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

        embeddings.append(
            normalize(
                embedding
            )
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
# HIGH QUALITY ANCHOR SELECTION
# ============================================================

def select_anchor_candidates(
    segments,
    embeddings,
):

    candidates = []

    for index, segment in enumerate(
        segments
    ):

        if (
            segment["duration"]
            >= MIN_ANCHOR_DURATION
        ):

            candidates.append(
                index
            )

    print()
    print(
        f"Anchor candidates: "
        f"{len(candidates)}"
    )

    return candidates


# ============================================================
# BUILD ANCHOR GRAPH
# ============================================================

def build_anchor_similarity(
    embeddings,
    candidates,
):

    matrix = np.vstack(
        [
            embeddings[i]
            for i in candidates
        ]
    )

    matrix = matrix / np.maximum(
        np.linalg.norm(
            matrix,
            axis=1,
            keepdims=True,
        ),
        1e-12,
    )

    return (
        matrix @ matrix.T
    )


def build_mutual_anchor_graph(
    candidates,
    similarity,
):

    n = len(candidates)

    nearest = []

    for i in range(n):

        choices = [
            j
            for j in range(n)
            if j != i
        ]

        choices.sort(
            key=lambda j:
            similarity[i, j],
            reverse=True,
        )

        nearest.append(
            choices[:TOP_K]
        )

    pairs = []

    for i in range(n):

        for j in nearest[i]:

            if i >= j:
                continue

            if i in nearest[j]:

                score = float(
                    similarity[i, j]
                )

                if (
                    score
                    >= STRONG_SIMILARITY
                ):

                    pairs.append(
                        (
                            i,
                            j,
                            score,
                        )
                    )

    return pairs


# ============================================================
# BUILD CANDIDATE IDENTITIES
# ============================================================

def build_identity_candidates(
    segments,
    embeddings,
    candidates,
    mutual_pairs,
):

    uf = UnionFind(
        len(candidates)
    )

    for i, j, score in mutual_pairs:

        uf.union(
            i,
            j,
        )

    components = defaultdict(
        list
    )

    for local_index in range(
        len(candidates)
    ):

        root = uf.find(
            local_index
        )

        components[root].append(
            local_index
        )

    identities = []

    identity_number = 1

    for local_members in sorted(
        components.values(),
        key=len,
        reverse=True,
    ):

        if len(local_members) < MIN_SEED_SIZE:

            continue

        global_members = [
            candidates[i]
            for i in local_members
        ]

        centroid = weighted_centroid(
            [
                embeddings[i]
                for i in global_members
            ],
            [
                segments[i]["duration"]
                for i in global_members
            ],
        )

        coherence = [
            cosine(
                embeddings[i],
                centroid,
            )
            for i in global_members
        ]

        mean = float(
            np.mean(
                coherence
            )
        )

        minimum = float(
            np.min(
                coherence
            )
        )

        if mean < MIN_SEED_COHERENCE:

            continue

        labels = Counter(
            segments[i][
                "original_speaker"
            ]
            for i in global_members
        )

        identities.append(
            {
                "identity_id":
                    f"VOICE_{identity_number:02d}",

                "members":
                    global_members,

                "labels":
                    dict(labels),

                "dominant_label":
                    labels.most_common(
                        1
                    )[0][0],

                "size":
                    len(global_members),

                "coherence_mean":
                    mean,

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

        identity_number += 1

    return identities


# ============================================================
# CHECK BETWEEN-IDENTITY SEPARATION
# ============================================================

def validate_identity_separation(
    identities,
):

    results = []

    for i in range(
        len(identities)
    ):

        for j in range(
            i + 1,
            len(identities),
        ):

            a = identities[i]
            b = identities[j]

            score = cosine(
                a["centroid"],
                b["centroid"],
            )

            results.append(
                {
                    "identity_a":
                        a["identity_id"],

                    "identity_b":
                        b["identity_id"],

                    "prototype_similarity":
                        score,

                    "well_separated":
                        score
                        <= MAX_SEED_CROSS_SIMILARITY,
                }
            )

    return results


# ============================================================
# ASSIGNMENT
# ============================================================

def assign_segments(
    segments,
    embeddings,
    identities,
):

    assignments = []

    for index, segment in enumerate(
        segments
    ):

        scores = []

        for identity in identities:

            score = cosine(
                embeddings[index],
                identity["centroid"],
            )

            scores.append(
                {
                    "identity":
                        identity[
                            "identity_id"
                        ],

                    "score":
                        score,
                }
            )

        scores.sort(
            key=lambda x:
            x["score"],
            reverse=True,
        )

        if not scores:

            assignments.append(
                {
                    "segment_index":
                        index,

                    "original_speaker":
                        segment[
                            "original_speaker"
                        ],

                    "status":
                        "unresolved",

                    "resolved_identity":
                        None,
                }
            )

            continue

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

        # ----------------------------------------------------
        # Count how many seed members strongly support this
        # particular segment.
        # ----------------------------------------------------

        support_count = 0

        best_identity = next(
            identity
            for identity in identities
            if identity[
                "identity_id"
            ]
            == best["identity"]
        )

        for member in best_identity[
            "members"
        ]:

            member_score = cosine(
                embeddings[index],
                embeddings[member],
            )

            if (
                member_score
                >= STRONG_SIMILARITY
            ):

                support_count += 1

        # ----------------------------------------------------
        # Conservative decision.
        # ----------------------------------------------------

        if (
            best["score"]
            >= STRONG_ASSIGNMENT
            and margin
            >= MIN_ASSIGNMENT_MARGIN
            and support_count
            >= MIN_STRONG_SUPPORT_COUNT
        ):

            status = "strong"

        elif (
            best["score"]
            >= SUPPORTING_ASSIGNMENT
            and margin
            >= MIN_ASSIGNMENT_MARGIN
            and support_count
            >= 1
        ):

            status = "supporting"

        else:

            status = "unresolved"

        assignments.append(
            {
                "segment_index":
                    index,

                "source_index":
                    segment[
                        "source_index"
                    ],

                "start":
                    segment["start"],

                "end":
                    segment["end"],

                "duration":
                    segment["duration"],

                "original_speaker":
                    segment[
                        "original_speaker"
                    ],

                "resolved_identity":
                    (
                        best["identity"]
                        if status
                        in {
                            "strong",
                            "supporting",
                        }
                        else None
                    ),

                "best_candidate":
                    best["identity"],

                "best_score":
                    best["score"],

                "second_candidate":
                    second["identity"],

                "second_score":
                    second["score"],

                "margin":
                    margin,

                "strong_support_count":
                    support_count,

                "status":
                    status,

                "all_scores":
                    scores,
            }
        )

    return assignments


# ============================================================
# DISTRIBUTION
# ============================================================

def build_distribution(
    segments,
    assignments,
):

    output = defaultdict(
        Counter
    )

    for segment, assignment in zip(
        segments,
        assignments,
    ):

        identity = (
            assignment[
                "resolved_identity"
            ]
            or "UNRESOLVED"
        )

        output[
            segment[
                "original_speaker"
            ]
        ][identity] += 1

    return {
        label:
        dict(counter)
        for label, counter
        in output.items()
    }


# ============================================================
# PRINT
# ============================================================

def print_report(
    identities,
    separation,
    assignments,
    distribution,
):

    print()
    print("=" * 80)
    print("CANDIDATE VOICE IDENTITIES")
    print("=" * 80)

    for identity in identities:

        print()

        print(
            identity[
                "identity_id"
            ]
        )

        print(
            f"  Size: "
            f"{identity['size']}"
        )

        print(
            f"  Labels: "
            f"{identity['labels']}"
        )

        print(
            f"  Dominant label: "
            f"{identity['dominant_label']}"
        )

        print(
            f"  Coherence mean: "
            f"{identity['coherence_mean']:.4f}"
        )

        print(
            f"  Coherence min: "
            f"{identity['coherence_min']:.4f}"
        )

        print(
            f"  Coherence max: "
            f"{identity['coherence_max']:.4f}"
        )

    print()
    print("=" * 80)
    print("IDENTITY SEPARATION")
    print("=" * 80)

    for item in separation:

        print(
            f"{item['identity_a']} <-> "
            f"{item['identity_b']}: "
            f"{item['prototype_similarity']:.4f} "
            f"separated="
            f"{item['well_separated']}"
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
        f"Strong:      "
        f"{counts['strong']}"
    )

    print(
        f"Supporting:  "
        f"{counts['supporting']}"
    )

    print(
        f"Unresolved:  "
        f"{counts['unresolved']}"
    )

    print()
    print("=" * 80)
    print("ORIGINAL LABEL -> VALIDATED IDENTITY")
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
    print("UNRESOLVED SPEAKER_02 / SPEAKER_04")
    print("=" * 80)

    for assignment in assignments:

        if (
            assignment[
                "original_speaker"
            ]
            not in {
                "SPEAKER_02",
                "SPEAKER_04",
            }
        ):
            continue

        if (
            assignment[
                "status"
            ]
            != "unresolved"
        ):
            continue

        print()

        print(
            f"[{assignment['segment_index']:03d}] "
            f"{assignment['original_speaker']} "
            f"{assignment['start']:.2f} -> "
            f"{assignment['end']:.2f}"
        )

        print(
            f"  best: "
            f"{assignment['best_candidate']} "
            f"{assignment['best_score']:.4f}"
        )

        print(
            f"  second: "
            f"{assignment['second_candidate']} "
            f"{assignment['second_score']:.4f}"
        )

        print(
            f"  margin: "
            f"{assignment['margin']:.4f}"
        )

        print(
            f"  strong support: "
            f"{assignment['strong_support_count']}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("SPEAKER IDENTITY VALIDATION")
    print("=" * 80)

    print()
    print(
        "Whisper: NOT RUN"
    )

    print(
        "Diarization: NOT RUN"
    )

    print(
        "Recording: 7"
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    identity_segments = (
        load_segments()
    )

    cache_file, diarization_segments = (
        load_original_diarization()
    )

    segments = attach_original_labels(
        identity_segments,
        diarization_segments,
    )

    print()
    print(
        f"Segments: "
        f"{len(segments)}"
    )

    print(
        f"Diarization cache:\n"
        f"{cache_file}"
    )

    # --------------------------------------------------------
    # Audio
    # --------------------------------------------------------

    waveform, sample_rate = (
        load_audio()
    )

    print()
    print(
        f"Audio sample rate: "
        f"{sample_rate}"
    )

    print(
        f"Audio channels: "
        f"{waveform.shape[0]}"
    )

    # --------------------------------------------------------
    # Community-1
    # --------------------------------------------------------

    pipeline = (
        load_pipeline()
    )

    # --------------------------------------------------------
    # Embeddings
    # --------------------------------------------------------

    embeddings = extract_embeddings(
        pipeline,
        waveform,
        sample_rate,
        segments,
    )

    print()
    print(
        f"Embeddings: "
        f"{len(embeddings)}"
    )

    print(
        f"Dimension: "
        f"{len(embeddings[0])}"
    )

    # --------------------------------------------------------
    # Anchor candidates
    # --------------------------------------------------------

    anchor_candidates = (
        select_anchor_candidates(
            segments,
            embeddings,
        )
    )

    # --------------------------------------------------------
    # Anchor graph
    # --------------------------------------------------------

    anchor_similarity = (
        build_anchor_similarity(
            embeddings,
            anchor_candidates,
        )
    )

    mutual_pairs = (
        build_mutual_anchor_graph(
            anchor_candidates,
            anchor_similarity,
        )
    )

    print()
    print(
        f"Strong mutual anchor pairs: "
        f"{len(mutual_pairs)}"
    )

    # --------------------------------------------------------
    # Candidate identities
    # --------------------------------------------------------

    identities = (
        build_identity_candidates(
            segments,
            embeddings,
            anchor_candidates,
            mutual_pairs,
        )
    )

    print()
    print(
        f"Candidate identities: "
        f"{len(identities)}"
    )

    # --------------------------------------------------------
    # Identity separation
    # --------------------------------------------------------

    separation = (
        validate_identity_separation(
            identities
        )
    )

    # --------------------------------------------------------
    # Assign all segments
    # --------------------------------------------------------

    assignments = assign_segments(
        segments,
        embeddings,
        identities,
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
    # Print
    # --------------------------------------------------------

    print_report(
        identities,
        separation,
        assignments,
        distribution,
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    serializable_identities = []

    for identity in identities:

        serializable_identities.append(
            {
                key: value
                for key, value
                in identity.items()
                if key != "centroid"
            }
        )

    output = {
        "recording_id":
            RECORDING_ID,

        "configuration": {
            "min_anchor_duration":
                MIN_ANCHOR_DURATION,

            "min_evaluation_duration":
                MIN_EVALUATION_DURATION,

            "top_k":
                TOP_K,

            "strong_similarity":
                STRONG_SIMILARITY,

            "supporting_similarity":
                SUPPORTING_SIMILARITY,

            "min_seed_size":
                MIN_SEED_SIZE,

            "min_seed_coherence":
                MIN_SEED_COHERENCE,

            "max_seed_cross_similarity":
                MAX_SEED_CROSS_SIMILARITY,

            "strong_assignment":
                STRONG_ASSIGNMENT,

            "supporting_assignment":
                SUPPORTING_ASSIGNMENT,

            "min_assignment_margin":
                MIN_ASSIGNMENT_MARGIN,

            "min_strong_support_count":
                MIN_STRONG_SUPPORT_COUNT,
        },

        "audio_file":
            str(AUDIO_FILE),

        "identity_diagnostic":
            str(IDENTITY_RESULTS_FILE),

        "diarization_cache":
            str(cache_file),

        "segment_count":
            len(segments),

        "anchor_candidate_count":
            len(anchor_candidates),

        "mutual_anchor_pair_count":
            len(mutual_pairs),

        "candidate_identity_count":
            len(identities),

        "identities":
            serializable_identities,

        "identity_separation":
            separation,

        "assignments":
            assignments,

        "label_distribution":
            distribution,
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