from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

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
    / "speaker_identity_mutual_diagnostic"
)

OUTPUT_FILE = OUTPUT_DIR / "speaker_identity_mutual_results.json"

TOP_K = 8

# Strong mutual identity evidence.
STRONG_THRESHOLD = 0.78

# Lower threshold used only for supporting evidence.
SUPPORTING_THRESHOLD = 0.68

# A segment must have this many mutual strong relationships
# before we consider it a reliable identity anchor.
MIN_MUTUAL_STRONG = 2


# ============================================================
# HELPERS
# ============================================================

def cosine_matrix(embeddings: np.ndarray) -> np.ndarray:
    """
    Calculate complete cosine-similarity matrix.
    """
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)

    safe_norms = np.where(norms == 0.0, 1.0, norms)

    normalized = embeddings / safe_norms

    return normalized @ normalized.T


def load_results() -> tuple[list[dict], np.ndarray]:
    """
    Load the previous speaker identity diagnostic.
    """
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file does not exist:\n{INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments")
    embeddings = data.get("embeddings")

    if not segments:
        raise ValueError(
            "No 'segments' found in speaker_identity_results.json"
        )

    if not embeddings:
        raise ValueError(
            "No 'embeddings' found in speaker_identity_results.json"
        )

    matrix = np.asarray(embeddings, dtype=np.float32)

    if matrix.ndim != 2:
        raise ValueError(
            f"Expected 2-D embedding matrix, got {matrix.shape}"
        )

    if len(segments) != len(matrix):
        raise ValueError(
            f"Segment/embedding mismatch: "
            f"{len(segments)} segments vs {len(matrix)} embeddings"
        )

    return segments, matrix


def segment_label(segment: dict) -> str:
    return (
        segment.get("speaker_label")
        or segment.get("speaker")
        or "UNKNOWN"
    )


def segment_description(index: int, segment: dict) -> str:
    speaker = segment_label(segment)

    start = float(segment["start"])
    end = float(segment["end"])

    return (
        f"[{index:03d}] "
        f"{speaker} "
        f"{start:.2f}-{end:.2f} "
        f"({end - start:.2f}s)"
    )


# ============================================================
# MUTUAL NEAREST NEIGHBORS
# ============================================================

def build_top_neighbors(
    similarity: np.ndarray,
    top_k: int,
) -> list[list[dict]]:
    """
    For every segment, calculate its top-K nearest neighbors.

    Self similarity is excluded.
    """
    n = similarity.shape[0]

    all_neighbors: list[list[dict]] = []

    for i in range(n):
        scores = similarity[i].copy()

        # Never consider the segment itself.
        scores[i] = -np.inf

        k = min(top_k, n - 1)

        indices = np.argpartition(
            -scores,
            kth=k - 1,
        )[:k]

        indices = indices[
            np.argsort(-scores[indices])
        ]

        neighbors = []

        for j in indices:
            neighbors.append(
                {
                    "index": int(j),
                    "similarity": float(scores[j]),
                }
            )

        all_neighbors.append(neighbors)

    return all_neighbors


def build_mutual_pairs(
    similarity: np.ndarray,
    top_neighbors: list[list[dict]],
) -> list[dict]:
    """
    A mutual-nearest-neighbor relationship exists when:

        A has B in its top-K
        AND
        B has A in its top-K

    This is much stronger than a one-way nearest-neighbor match.
    """
    n = similarity.shape[0]

    neighbor_sets = []

    for neighbors in top_neighbors:
        neighbor_sets.append(
            {
                item["index"]
                for item in neighbors
            }
        )

    pairs = []

    for i in range(n):
        for j in neighbor_sets[i]:

            if j <= i:
                continue

            if i not in neighbor_sets[j]:
                continue

            score = float(similarity[i, j])

            pairs.append(
                {
                    "a": i,
                    "b": j,
                    "similarity": score,
                }
            )

    pairs.sort(
        key=lambda item: item["similarity"],
        reverse=True,
    )

    return pairs


# ============================================================
# MUTUAL STRONG ANCHORS
# ============================================================

def build_mutual_anchor_map(
    segments: list[dict],
    mutual_pairs: list[dict],
) -> dict[int, list[dict]]:
    """
    Build strong mutual relationships for every segment.
    """
    anchors: dict[int, list[dict]] = defaultdict(list)

    for pair in mutual_pairs:

        if pair["similarity"] < STRONG_THRESHOLD:
            continue

        a = pair["a"]
        b = pair["b"]

        anchors[a].append(
            {
                "index": b,
                "similarity": pair["similarity"],
            }
        )

        anchors[b].append(
            {
                "index": a,
                "similarity": pair["similarity"],
            }
        )

    for values in anchors.values():
        values.sort(
            key=lambda item: item["similarity"],
            reverse=True,
        )

    return anchors


# ============================================================
# PRINT STRONG ANCHORS
# ============================================================

def print_strong_anchors(
    segments: list[dict],
    anchors: dict[int, list[dict]],
) -> None:

    print()
    print("=" * 80)
    print("MUTUAL STRONG IDENTITY ANCHORS")
    print("=" * 80)

    reliable = [
        (index, neighbors)
        for index, neighbors in anchors.items()
        if len(neighbors) >= MIN_MUTUAL_STRONG
    ]

    reliable.sort(
        key=lambda item: len(item[1]),
        reverse=True,
    )

    print(
        f"Segments with >= "
        f"{MIN_MUTUAL_STRONG} mutual strong neighbors: "
        f"{len(reliable)}"
    )

    print()

    for index, neighbors in reliable:

        print(
            segment_description(
                index,
                segments[index],
            )
        )

        print(
            f"Mutual strong neighbors: "
            f"{len(neighbors)}"
        )

        for item in neighbors[:TOP_K]:

            other = item["index"]

            print(
                "    "
                + segment_description(
                    other,
                    segments[other],
                )
                + f" = {item['similarity']:.4f}"
            )

        print()


# ============================================================
# CROSS-LABEL MUTUAL EVIDENCE
# ============================================================

def cross_label_mutual_pairs(
    segments: list[dict],
    mutual_pairs: list[dict],
) -> dict[tuple[str, str], list[dict]]:

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for pair in mutual_pairs:

        score = pair["similarity"]

        if score < SUPPORTING_THRESHOLD:
            continue

        a = pair["a"]
        b = pair["b"]

        label_a = segment_label(segments[a])
        label_b = segment_label(segments[b])

        if label_a == label_b:
            continue

        key = tuple(
            sorted(
                [label_a, label_b]
            )
        )

        grouped[key].append(
            {
                "a": a,
                "b": b,
                "similarity": score,
            }
        )

    for values in grouped.values():
        values.sort(
            key=lambda item: item["similarity"],
            reverse=True,
        )

    return grouped


def print_cross_label_mutual(
    segments: list[dict],
    grouped: dict[tuple[str, str], list[dict]],
) -> None:

    print()
    print("=" * 80)
    print("MUTUAL CROSS-LABEL IDENTITY EVIDENCE")
    print("=" * 80)

    ordered = sorted(
        grouped.items(),
        key=lambda item: (
            -sum(
                x["similarity"] >= STRONG_THRESHOLD
                for x in item[1]
            ),
            -len(item[1]),
        ),
    )

    for (label_a, label_b), pairs in ordered:

        strong = [
            p
            for p in pairs
            if p["similarity"] >= STRONG_THRESHOLD
        ]

        print()
        print(
            f"{label_a} <-> {label_b}"
        )

        print(
            f"    mutual strong matches: {len(strong)}"
        )

        print(
            f"    mutual supporting matches: {len(pairs)}"
        )

        if pairs:
            print(
                f"    best similarity: "
                f"{pairs[0]['similarity']:.4f}"
            )

        for pair in pairs[:8]:

            print(
                "    "
                + segment_description(
                    pair["a"],
                    segments[pair["a"]],
                )
            )

            print(
                "        <-> "
                + segment_description(
                    pair["b"],
                    segments[pair["b"]],
                )
                + f" = {pair['similarity']:.4f}"
            )


# ============================================================
# MUTUAL IDENTITY GRAPH
# ============================================================

class UnionFind:

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[
                self.parent[x]
            ]
            x = self.parent[x]

        return x

    def union(self, a: int, b: int) -> None:

        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        if self.rank[root_a] < self.rank[root_b]:
            self.parent[root_a] = root_b

        elif self.rank[root_a] > self.rank[root_b]:
            self.parent[root_b] = root_a

        else:
            self.parent[root_b] = root_a
            self.rank[root_a] += 1


def build_identity_components(
    segments: list[dict],
    mutual_pairs: list[dict],
) -> list[list[int]]:

    uf = UnionFind(len(segments))

    # Only use VERY strong mutual relationships.
    for pair in mutual_pairs:

        if pair["similarity"] < STRONG_THRESHOLD:
            continue

        uf.union(
            pair["a"],
            pair["b"],
        )

    components: dict[int, list[int]] = defaultdict(list)

    for i in range(len(segments)):
        root = uf.find(i)
        components[root].append(i)

    result = [
        values
        for values in components.values()
        if len(values) >= 2
    ]

    result.sort(
        key=len,
        reverse=True,
    )

    return result


def print_identity_components(
    segments: list[dict],
    components: list[list[int]],
) -> None:

    print()
    print("=" * 80)
    print("MUTUAL STRONG IDENTITY COMPONENTS")
    print("=" * 80)

    print(
        f"Components with at least 2 segments: "
        f"{len(components)}"
    )

    for component_index, component in enumerate(
        components,
        start=1,
    ):

        labels = defaultdict(int)

        for index in component:
            labels[
                segment_label(
                    segments[index]
                )
            ] += 1

        print()
        print(
            f"IDENTITY COMPONENT {component_index}"
        )

        print(
            f"Segments: {len(component)}"
        )

        print(
            "Diarization labels: "
            + ", ".join(
                f"{label}={count}"
                for label, count in sorted(
                    labels.items()
                )
            )
        )

        ordered = sorted(
            component,
            key=lambda i: segments[i]["start"],
        )

        for index in ordered:
            print(
                "    "
                + segment_description(
                    index,
                    segments[index],
                )
            )


# ============================================================
# CONSISTENCY ANALYSIS
# ============================================================

def analyze_label_purity(
    segments: list[dict],
    components: list[list[int]],
) -> list[dict]:

    results = []

    for component_index, component in enumerate(
        components,
        start=1,
    ):

        labels = defaultdict(int)

        for index in component:
            labels[
                segment_label(
                    segments[index]
                )
            ] += 1

        total = len(component)

        dominant_label = max(
            labels,
            key=labels.get,
        )

        dominant_count = labels[
            dominant_label
        ]

        purity = dominant_count / total

        results.append(
            {
                "component": component_index,
                "size": total,
                "labels": dict(labels),
                "dominant_label": dominant_label,
                "dominant_count": dominant_count,
                "purity": purity,
            }
        )

    return results


# ============================================================
# SAVE
# ============================================================

def save_results(
    segments: list[dict],
    similarity: np.ndarray,
    top_neighbors: list[list[dict]],
    mutual_pairs: list[dict],
    components: list[list[int]],
    purity: list[dict],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    serializable_neighbors = []

    for index, neighbors in enumerate(
        top_neighbors
    ):

        serializable_neighbors.append(
            {
                "segment_index": index,
                "neighbors": neighbors,
            }
        )

    data = {
        "configuration": {
            "top_k": TOP_K,
            "strong_threshold": STRONG_THRESHOLD,
            "supporting_threshold": SUPPORTING_THRESHOLD,
            "min_mutual_strong": MIN_MUTUAL_STRONG,
        },

        "segment_count": len(segments),

        "segments": segments,

        "similarity_matrix_shape": list(
            similarity.shape
        ),

        "top_neighbors": serializable_neighbors,

        "mutual_pairs": mutual_pairs,

        "identity_components": components,

        "component_purity": purity,
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
    print("Saved:")
    print(OUTPUT_FILE)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("MUTUAL NEAREST-NEIGHBOR SPEAKER IDENTITY DIAGNOSTIC")
    print("=" * 80)

    print()
    print(
        "This diagnostic does not rerun diarization."
    )

    print(
        "This diagnostic does not modify production."
    )

    print()

    segments, embeddings = load_results()

    print(
        f"Segments: {len(segments)}"
    )

    print(
        f"Embedding matrix: {embeddings.shape}"
    )

    similarity = cosine_matrix(
        embeddings
    )

    top_neighbors = build_top_neighbors(
        similarity,
        TOP_K,
    )

    mutual_pairs = build_mutual_pairs(
        similarity,
        top_neighbors,
    )

    print()
    print(
        f"Mutual nearest-neighbor pairs: "
        f"{len(mutual_pairs)}"
    )

    anchors = build_mutual_anchor_map(
        segments,
        mutual_pairs,
    )

    print_strong_anchors(
        segments,
        anchors,
    )

    cross_label = cross_label_mutual_pairs(
        segments,
        mutual_pairs,
    )

    print_cross_label_mutual(
        segments,
        cross_label,
    )

    components = build_identity_components(
        segments,
        mutual_pairs,
    )

    print_identity_components(
        segments,
        components,
    )

    purity = analyze_label_purity(
        segments,
        components,
    )

    print()
    print("=" * 80)
    print("COMPONENT PURITY")
    print("=" * 80)

    for item in purity:

        print(
            f"Component {item['component']}: "
            f"size={item['size']} "
            f"dominant={item['dominant_label']} "
            f"purity={item['purity']:.3f} "
            f"labels={item['labels']}"
        )

    save_results(
        segments,
        similarity,
        top_neighbors,
        mutual_pairs,
        components,
        purity,
    )

    print()
    print(
        "Mutual nearest-neighbor diagnostic completed."
    )


if __name__ == "__main__":
    main()