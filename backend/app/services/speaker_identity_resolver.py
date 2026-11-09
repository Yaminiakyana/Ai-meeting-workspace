from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

import numpy as np


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    BASE_DIR
    / "storage"
    / "processed"
    / "recording_7"
    / "speaker_identity_results.json"
)

# The actual file is inside speaker_identity_diagnostic.
INPUT_FILE = (
    BASE_DIR
    / "storage"
    / "processed"
    / "recording_7"
    / "speaker_identity_diagnostic"
    / "speaker_identity_results.json"
)

OUTPUT_DIR = (
    BASE_DIR
    / "storage"
    / "processed"
    / "recording_7"
    / "speaker_identity_resolver_diagnostic"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "speaker_identity_resolver_results.json"
)


# ============================================================
# CONFIGURATION
# ============================================================

# Segment must have enough speech to produce a useful
# speaker embedding.
MIN_SEGMENT_DURATION = 1.5


# A segment must have at least this many seconds before
# it can become a high-confidence identity anchor.
MIN_ANCHOR_DURATION = 2.5


# Maximum number of anchor segments per original
# diarization label.
MAX_ANCHORS_PER_LABEL = 8


# Minimum similarity to an identity prototype.
STRONG_SIMILARITY = 0.78


# Similarity below this is treated as weak evidence.
WEAK_SIMILARITY = 0.68


# Minimum number of independent anchor matches.
MIN_STRONG_ANCHORS = 2


# Minimum number of independent original diarization
# labels represented in the identity evidence before
# considering cross-label confirmation.
MIN_SUPPORTING_LABELS = 1


# A segment must have a reasonable margin over its
# second-best identity before automatic assignment.
MIN_MARGIN = 0.06


# ============================================================
# HELPERS
# ============================================================

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two vectors.
    """

    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)

    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0

    return float(
        np.dot(a, b)
        / (a_norm * b_norm)
    )


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)

    if norm == 0.0:
        return vector

    return vector / norm


def load_data():
    """
    Load the cached segment embeddings.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find:\n{INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    segments = data.get("segments")
    embeddings = data.get("embeddings")

    if not segments:
        raise ValueError(
            "No segments found in input JSON."
        )

    if not embeddings:
        raise ValueError(
            "No embeddings found in input JSON."
        )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )

    if len(segments) != len(embeddings):
        raise ValueError(
            "Segment/embedding count mismatch: "
            f"{len(segments)} vs "
            f"{len(embeddings)}"
        )

    return data, segments, embeddings


def speaker_label(segment: dict) -> str:
    return (
        segment.get("speaker_label")
        or segment.get("speaker")
        or "UNKNOWN"
    )


def duration(segment: dict) -> float:
    return float(
        segment["end"]
        - segment["start"]
    )


def segment_text(
    index: int,
    segment: dict,
) -> str:

    return (
        f"[{index:03d}] "
        f"{speaker_label(segment)} "
        f"{segment['start']:.2f}-"
        f"{segment['end']:.2f} "
        f"({duration(segment):.2f}s)"
    )


# ============================================================
# SELECT HIGH-CONFIDENCE ANCHORS
# ============================================================

def select_anchor_segments(
    segments: list[dict],
    embeddings: np.ndarray,
):
    """
    Select long segments as candidate identity anchors.

    We do NOT assume every Community-1 label is pure.

    Anchors are initially selected within each original
    diarization label, then internally compared.
    """

    by_label = defaultdict(list)

    for index, segment in enumerate(segments):

        if duration(segment) < MIN_ANCHOR_DURATION:
            continue

        by_label[
            speaker_label(segment)
        ].append(index)

    anchors = {}

    print()
    print("=" * 80)
    print("ANCHOR SELECTION")
    print("=" * 80)

    for label, indices in sorted(
        by_label.items()
    ):

        # Longest segments first.
        indices = sorted(
            indices,
            key=lambda i: duration(
                segments[i]
            ),
            reverse=True,
        )

        selected = indices[
            :MAX_ANCHORS_PER_LABEL
        ]

        anchors[label] = selected

        print()
        print(
            f"{label}: "
            f"{len(indices)} candidates -> "
            f"{len(selected)} anchors"
        )

        for index in selected:

            print(
                "    "
                + segment_text(
                    index,
                    segments[index],
                )
            )

    return anchors


# ============================================================
# CREATE INITIAL PROTOTYPES
# ============================================================

def build_initial_prototypes(
    segments: list[dict],
    embeddings: np.ndarray,
    anchors: dict[str, list[int]],
):
    """
    Build a duration-weighted prototype for each original
    diarization label.

    These are diagnostic prototypes only.
    """

    prototypes = {}

    for label, indices in anchors.items():

        if not indices:
            continue

        vectors = []

        weights = []

        for index in indices:

            vector = normalize(
                embeddings[index]
            )

            weight = max(
                duration(
                    segments[index]
                ),
                0.1,
            )

            vectors.append(vector)
            weights.append(weight)

        vectors = np.asarray(
            vectors,
            dtype=np.float32,
        )

        weights = np.asarray(
            weights,
            dtype=np.float32,
        )

        prototype = np.average(
            vectors,
            axis=0,
            weights=weights,
        )

        prototype = normalize(
            prototype
        )

        prototypes[label] = prototype

    return prototypes


# ============================================================
# LABEL COHERENCE
# ============================================================

def calculate_label_coherence(
    segments: list[dict],
    embeddings: np.ndarray,
    anchors: dict[str, list[int]],
    prototypes: dict[str, np.ndarray],
):
    """
    Measure how consistently each original diarization
    label matches its own prototype.
    """

    result = {}

    for label, indices in anchors.items():

        prototype = prototypes.get(label)

        if prototype is None:
            continue

        scores = []

        for index in indices:

            score = cosine_similarity(
                embeddings[index],
                prototype,
            )

            scores.append(score)

        result[label] = {
            "count": len(scores),
            "mean": float(np.mean(scores)),
            "median": float(np.median(scores)),
            "minimum": float(np.min(scores)),
            "maximum": float(np.max(scores)),
        }

    return result


# ============================================================
# SEGMENT → PROTOTYPE MATCHING
# ============================================================

def match_segments_to_prototypes(
    segments: list[dict],
    embeddings: np.ndarray,
    prototypes: dict[str, np.ndarray],
):
    """
    Compare every segment against every identity prototype.

    This does NOT automatically assign every segment.

    It returns:
        best identity
        second-best identity
        margin
        all scores
    """

    labels = list(
        prototypes.keys()
    )

    results = []

    for index, segment in enumerate(
        segments
    ):

        vector = embeddings[index]

        scores = []

        for label in labels:

            score = cosine_similarity(
                vector,
                prototypes[label],
            )

            scores.append(
                {
                    "identity": label,
                    "similarity": score,
                }
            )

        scores.sort(
            key=lambda item: item["similarity"],
            reverse=True,
        )

        best = scores[0] if scores else None
        second = (
            scores[1]
            if len(scores) > 1
            else None
        )

        if best is None:

            results.append(
                {
                    "segment_index": index,
                    "original_label": speaker_label(
                        segment
                    ),
                    "status": "unresolved",
                    "scores": [],
                }
            )

            continue

        margin = (
            best["similarity"]
            - second["similarity"]
            if second
            else best["similarity"]
        )

        if (
            best["similarity"]
            >= STRONG_SIMILARITY
            and margin >= MIN_MARGIN
        ):

            status = "strong"

        elif (
            best["similarity"]
            >= WEAK_SIMILARITY
            and margin >= MIN_MARGIN
        ):

            status = "supporting"

        else:

            status = "uncertain"

        results.append(
            {
                "segment_index": index,
                "original_label": speaker_label(
                    segment
                ),
                "duration": duration(
                    segment
                ),
                "best_identity": best["identity"],
                "best_similarity": best["similarity"],
                "second_identity": (
                    second["identity"]
                    if second
                    else None
                ),
                "second_similarity": (
                    second["similarity"]
                    if second
                    else None
                ),
                "margin": margin,
                "status": status,
                "scores": scores,
            }
        )

    return results


# ============================================================
# CROSS-LABEL IDENTITY EVIDENCE
# ============================================================

def analyze_cross_label_matches(
    segments: list[dict],
    matches: list[dict],
):
    """
    Determine whether an identity prototype attracts
    segments from multiple Community-1 labels.
    """

    identity_support = defaultdict(
        lambda: defaultdict(list)
    )

    for match in matches:

        if match["status"] == "uncertain":
            continue

        identity = match.get(
            "best_identity"
        )

        if not identity:
            continue

        original = match[
            "original_label"
        ]

        identity_support[
            identity
        ][original].append(match)

    return identity_support


def print_identity_support(
    identity_support,
):
    print()
    print("=" * 80)
    print("IDENTITY PROTOTYPE SUPPORT")
    print("=" * 80)

    for identity in sorted(
        identity_support
    ):

        label_map = identity_support[
            identity
        ]

        print()
        print(
            f"IDENTITY PROTOTYPE: {identity}"
        )

        for original_label, matches in sorted(
            label_map.items()
        ):

            strong = sum(
                match["status"] == "strong"
                for match in matches
            )

            print(
                f"    {original_label}: "
                f"{len(matches)} matches "
                f"({strong} strong)"
            )


# ============================================================
# ORIGINAL LABEL → IDENTITY DISTRIBUTION
# ============================================================

def analyze_original_labels(
    matches: list[dict],
):
    distribution = defaultdict(
        lambda: defaultdict(list)
    )

    for match in matches:

        label = match[
            "original_label"
        ]

        identity = match.get(
            "best_identity"
        )

        if identity:

            distribution[
                label
            ][identity].append(match)

    return distribution


def print_original_label_distribution(
    distribution,
):
    print()
    print("=" * 80)
    print("ORIGINAL DIARIZATION LABEL → RESOLVED IDENTITY")
    print("=" * 80)

    for original_label in sorted(
        distribution
    ):

        print()
        print(
            original_label
        )

        identity_map = distribution[
            original_label
        ]

        total = sum(
            len(values)
            for values in identity_map.values()
        )

        for identity, values in sorted(
            identity_map.items(),
            key=lambda item: len(
                item[1]
            ),
            reverse=True,
        ):

            print(
                f"    {identity}: "
                f"{len(values)}/{total}"
            )


# ============================================================
# IMPORTANT: DON'T FORCE IDENTITY
# ============================================================

def create_conservative_resolution(
    segments: list[dict],
    matches: list[dict],
):
    """
    Create a conservative result.

    Strong:
        confidently assigned to an identity prototype.

    Supporting:
        useful evidence but not enough for final confidence.

    Uncertain:
        preserve original diarization label.

    This is diagnostic only.
    """

    resolved = []

    for match in matches:

        index = match[
            "segment_index"
        ]

        segment = segments[index]

        if match["status"] == "strong":

            resolved_identity = (
                match["best_identity"]
            )

            resolution_reason = (
                "strong_prototype_match"
            )

        else:

            resolved_identity = (
                speaker_label(segment)
            )

            resolution_reason = (
                "preserved_original_label"
            )

        resolved.append(
            {
                "segment_index": index,
                "start": segment["start"],
                "end": segment["end"],
                "original_label": speaker_label(
                    segment
                ),
                "resolved_identity": (
                    resolved_identity
                ),
                "confidence_status": (
                    match["status"]
                ),
                "best_similarity": (
                    match.get(
                        "best_similarity"
                    )
                ),
                "second_similarity": (
                    match.get(
                        "second_similarity"
                    )
                ),
                "margin": (
                    match.get(
                        "margin"
                    )
                ),
                "resolution_reason": (
                    resolution_reason
                ),
            }
        )

    return resolved


# ============================================================
# PRINT RESOLUTION
# ============================================================

def print_resolution_summary(
    segments,
    resolved,
):

    print()
    print("=" * 80)
    print("CONSERVATIVE RESOLUTION SUMMARY")
    print("=" * 80)

    counts = defaultdict(int)

    for item in resolved:

        counts[
            item["confidence_status"]
        ] += 1

    print()

    for status in [
        "strong",
        "supporting",
        "uncertain",
    ]:

        print(
            f"{status}: "
            f"{counts[status]}"
        )

    print()
    print(
        "Strong assignments:"
    )

    for item in resolved:

        if item[
            "confidence_status"
        ] != "strong":
            continue

        index = item[
            "segment_index"
        ]

        print(
            f"    [{index:03d}] "
            f"{item['original_label']} "
            f"-> "
            f"{item['resolved_identity']} "
            f"score="
            f"{item['best_similarity']:.4f} "
            f"margin="
            f"{item['margin']:.4f}"
        )


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(
    source_data,
    segments,
    embeddings,
    anchors,
    prototypes,
    coherence,
    matches,
    resolved,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    serializable_prototypes = {
        label: vector.tolist()
        for label, vector
        in prototypes.items()
    }

    data = {
        "source": str(
            INPUT_FILE
        ),

        "configuration": {
            "min_segment_duration": (
                MIN_SEGMENT_DURATION
            ),
            "min_anchor_duration": (
                MIN_ANCHOR_DURATION
            ),
            "max_anchors_per_label": (
                MAX_ANCHORS_PER_LABEL
            ),
            "strong_similarity": (
                STRONG_SIMILARITY
            ),
            "weak_similarity": (
                WEAK_SIMILARITY
            ),
            "min_strong_anchors": (
                MIN_STRONG_ANCHORS
            ),
            "min_margin": (
                MIN_MARGIN
            ),
        },

        "segment_count": len(
            segments
        ),

        "segments": segments,

        "embeddings": embeddings.tolist(),

        "anchors": anchors,

        "prototypes": (
            serializable_prototypes
        ),

        "prototype_coherence": coherence,

        "matches": matches,

        "resolved": resolved,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
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
        OUTPUT_FILE
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("SPEAKER IDENTITY RESOLVER DIAGNOSTIC")
    print("=" * 80)

    print()
    print(
        "This is a diagnostic only."
    )

    print(
        "It does not rerun diarization."
    )

    print(
        "It does not rerun Whisper."
    )

    print(
        "It does not modify production."
    )

    print()

    source_data, segments, embeddings = (
        load_data()
    )

    print(
        f"Segments loaded: "
        f"{len(segments)}"
    )

    print(
        f"Embedding matrix: "
        f"{embeddings.shape}"
    )

    # --------------------------------------------------------
    # 1. SELECT ANCHORS
    # --------------------------------------------------------

    anchors = select_anchor_segments(
        segments,
        embeddings,
    )

    # --------------------------------------------------------
    # 2. BUILD INITIAL PROTOTYPES
    # --------------------------------------------------------

    prototypes = (
        build_initial_prototypes(
            segments,
            embeddings,
            anchors,
        )
    )

    print()
    print("=" * 80)
    print("INITIAL IDENTITY PROTOTYPES")
    print("=" * 80)

    for label in sorted(
        prototypes
    ):

        print(
            f"    {label}"
        )

    # --------------------------------------------------------
    # 3. CHECK COHERENCE
    # --------------------------------------------------------

    coherence = (
        calculate_label_coherence(
            segments,
            embeddings,
            anchors,
            prototypes,
        )
    )

    print()
    print("=" * 80)
    print("PROTOTYPE COHERENCE")
    print("=" * 80)

    for label, stats in sorted(
        coherence.items()
    ):

        print(
            f"{label}: "
            f"mean={stats['mean']:.4f} "
            f"median={stats['median']:.4f} "
            f"min={stats['minimum']:.4f} "
            f"max={stats['maximum']:.4f}"
        )

    # --------------------------------------------------------
    # 4. MATCH EVERY SEGMENT
    # --------------------------------------------------------

    matches = (
        match_segments_to_prototypes(
            segments,
            embeddings,
            prototypes,
        )
    )

    # --------------------------------------------------------
    # 5. CROSS-LABEL ANALYSIS
    # --------------------------------------------------------

    identity_support = (
        analyze_cross_label_matches(
            segments,
            matches,
        )
    )

    print_identity_support(
        identity_support
    )

    # --------------------------------------------------------
    # 6. ORIGINAL LABEL DISTRIBUTION
    # --------------------------------------------------------

    distribution = (
        analyze_original_labels(
            matches
        )
    )

    print_original_label_distribution(
        distribution
    )

    # --------------------------------------------------------
    # 7. CONSERVATIVE RESOLUTION
    # --------------------------------------------------------

    resolved = (
        create_conservative_resolution(
            segments,
            matches,
        )
    )

    print_resolution_summary(
        segments,
        resolved,
    )

    # --------------------------------------------------------
    # 8. SAVE
    # --------------------------------------------------------

    save_results(
        source_data,
        segments,
        embeddings,
        anchors,
        prototypes,
        coherence,
        matches,
        resolved,
    )

    print()
    print(
        "Speaker identity resolver diagnostic completed."
    )


if __name__ == "__main__":
    main()