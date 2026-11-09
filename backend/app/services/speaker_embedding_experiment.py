from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torchaudio
from pyannote.audio import Pipeline


# =============================================================================
# PATHS
# =============================================================================

BACKEND_ROOT = Path(__file__).resolve().parents[2]

RECORDINGS_ROOT = BACKEND_ROOT / "storage" / "recordings"
PROCESSED_ROOT = BACKEND_ROOT / "storage" / "processed"

RECORDING_ID = 7

DIARIZATION_JSON = (
    PROCESSED_ROOT
    / f"recording_{RECORDING_ID}"
    / "diarization_clustering_experiments.json"
)

OUTPUT_DIR = (
    PROCESSED_ROOT
    / f"recording_{RECORDING_ID}"
    / "speaker_embedding_diagnostic"
)

OUTPUT_JSON = OUTPUT_DIR / "speaker_embedding_results.json"

EXPERIMENT_NAME = "threshold_060_default"

SPEAKERS_TO_ANALYZE = [
    "SPEAKER_02",
    "SPEAKER_04",
]

MIN_SEGMENT_DURATION = 1.5
MAX_SEGMENTS_PER_SPEAKER = 12


# =============================================================================
# MODEL
# =============================================================================

PIPELINE_NAME = "pyannote/speaker-diarization-community-1"


# =============================================================================
# RECORDING
# =============================================================================

KNOWN_RECORDING_7_FILE = (
    RECORDINGS_ROOT
    / "5"
    / "344d63fd75074ab3a4a19e745f7aa090.mp4"
)


# =============================================================================
# HELPERS
# =============================================================================

def cosine_similarity(
    a: np.ndarray,
    b: np.ndarray,
) -> float:
    """
    Calculate cosine similarity between two embedding vectors.
    """

    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)

    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)

    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0

    return float(np.dot(a, b) / (a_norm * b_norm))


def normalize_embedding(
    embedding: np.ndarray,
) -> np.ndarray:
    """
    L2-normalize an embedding.
    """

    embedding = np.asarray(embedding, dtype=np.float32)

    norm = np.linalg.norm(embedding)

    if norm == 0.0:
        return embedding

    return embedding / norm


def find_recording_file() -> Path:
    """
    Find the physical recording file.

    Recording database ID and storage directory are not assumed
    to be identical.
    """

    if KNOWN_RECORDING_7_FILE.exists():
        return KNOWN_RECORDING_7_FILE

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
        "Could not uniquely locate recording 7.\n"
        f"Searched: {RECORDINGS_ROOT}\n"
        f"Candidates: {candidates}"
    )


# =============================================================================
# DIARIZATION CACHE
# =============================================================================

def load_cached_segments() -> list[dict[str, Any]]:
    """
    Load the threshold_060_default experiment from the cached
    clustering experiment JSON.
    """

    if not DIARIZATION_JSON.exists():
        raise FileNotFoundError(
            f"Diarization cache not found:\n{DIARIZATION_JSON}"
        )

    with DIARIZATION_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    experiments = data.get("experiments")

    if not isinstance(experiments, list):
        raise RuntimeError(
            "Unexpected diarization JSON structure: "
            "'experiments' is not a list."
        )

    selected = None

    for item in experiments:
        if not isinstance(item, dict):
            continue

        experiment = item.get("experiment")

        if not isinstance(experiment, dict):
            continue

        if experiment.get("name") == EXPERIMENT_NAME:
            selected = item
            break

    if selected is None:
        available = []

        for item in experiments:
            if isinstance(item, dict):
                experiment = item.get("experiment")

                if isinstance(experiment, dict):
                    available.append(experiment.get("name"))

        raise ValueError(
            f"{EXPERIMENT_NAME} was not found in the diarization experiment JSON.\n"
            f"Available experiments: {available}"
        )

    exclusive = selected.get("exclusive")

    if not isinstance(exclusive, dict):
        raise RuntimeError(
            "The selected experiment does not contain an 'exclusive' dictionary."
        )

    print("Exclusive keys:")
    print(list(exclusive.keys()))

    raw_segments = exclusive.get("segments")

    if not isinstance(raw_segments, list):
        raise RuntimeError(
            "The selected experiment does not contain "
            "'exclusive.segments' as a list."
        )

    segments: list[dict[str, Any]] = []

    for item in raw_segments:

        if not isinstance(item, dict):
            continue

        speaker = item.get("speaker")

        start = item.get("start")
        end = item.get("end")

        if speaker is None:
            speaker = item.get("speaker_label")

        if start is None or end is None:
            continue

        start = float(start)
        end = float(end)

        if end <= start:
            continue

        segments.append(
            {
                "speaker": str(speaker),
                "start": start,
                "end": end,
                "duration": end - start,
            }
        )

    if not segments:
        raise RuntimeError(
            "No usable exclusive diarization segments were found."
        )

    print(
        f"Loaded {len(segments)} cached exclusive segments "
        f"from {EXPERIMENT_NAME}."
    )

    return segments


# =============================================================================
# AUDIO
# =============================================================================

def load_audio(
    audio_path: Path,
) -> tuple[torch.Tensor, int]:
    """
    Load the entire recording.

    Returns:
        waveform: [channels, samples]
        sample_rate
    """

    waveform, sample_rate = torchaudio.load(str(audio_path))

    print(f"Original sample rate: {sample_rate}")
    print(f"Original shape: {tuple(waveform.shape)}")

    # Convert stereo/multi-channel audio to mono.
    if waveform.ndim == 2 and waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Community-1 expects 16 kHz audio.
    target_sample_rate = 16000

    if sample_rate != target_sample_rate:

        waveform = torchaudio.functional.resample(
            waveform,
            sample_rate,
            target_sample_rate,
        )

        sample_rate = target_sample_rate

    print(f"Final sample rate: {sample_rate}")
    print(f"Final shape: {tuple(waveform.shape)}")

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
    """
    Extract a [1, samples] waveform segment.
    """

    start_sample = max(
        0,
        int(round(start * sample_rate)),
    )

    end_sample = min(
        waveform.shape[-1],
        int(round(end * sample_rate)),
    )

    if end_sample <= start_sample:
        raise ValueError(
            f"Invalid segment: {start} -> {end}"
        )

    segment = waveform[
        :,
        start_sample:end_sample,
    ]

    return segment


# =============================================================================
# SEGMENT SELECTION
# =============================================================================

def select_segments(
    segments: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Select the longest useful segments for each target speaker.
    """

    result: dict[str, list[dict[str, Any]]] = {}

    for speaker in SPEAKERS_TO_ANALYZE:

        speaker_segments = [
            segment
            for segment in segments
            if segment["speaker"] == speaker
            and segment["duration"] >= MIN_SEGMENT_DURATION
        ]

        speaker_segments.sort(
            key=lambda x: x["duration"],
            reverse=True,
        )

        selected = speaker_segments[
            :MAX_SEGMENTS_PER_SPEAKER
        ]

        result[speaker] = selected

        print()
        print("=" * 80)
        print(speaker)
        print("=" * 80)

        print(
            f"Selected {len(selected)} segments "
            f"(minimum duration {MIN_SEGMENT_DURATION}s)"
        )

        for index, segment in enumerate(selected, start=1):

            print(
                f"{index:02d}. "
                f"{segment['start']:.2f} -> "
                f"{segment['end']:.2f} "
                f"({segment['duration']:.2f}s)"
            )

    return result


# =============================================================================
# EMBEDDING
# =============================================================================

def generate_embedding(
    embedding_model: Any,
    waveform: torch.Tensor,
    sample_rate: int,
    device: torch.device,
) -> np.ndarray:
    """
    Generate one 256-D speaker embedding using the embedding model
    bundled inside Community-1.

    pyannote.audio 4.x expects:

        [batch, channels, samples]

    For one mono audio segment:

        [1, 1, samples]
    """

    del sample_rate  # The bundled model already knows its sample rate.

    waveform = waveform.float()

    # -------------------------------------------------------------------------
    # Normalize waveform shape to [channels, samples]
    # -------------------------------------------------------------------------

    if waveform.ndim == 1:
        # [samples] -> [1, samples]
        waveform = waveform.unsqueeze(0)

    elif waveform.ndim == 2:
        # Already [channels, samples]
        pass

    else:
        raise ValueError(
            "Unexpected waveform shape before batching: "
            f"{tuple(waveform.shape)}"
        )

    # -------------------------------------------------------------------------
    # Community-1 bundled embedding expects mono audio.
    # -------------------------------------------------------------------------

    if waveform.shape[0] != 1:
        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    # -------------------------------------------------------------------------
    # Add batch dimension.
    #
    # [1, samples]
    #       ↓
    # [1, 1, samples]
    # -------------------------------------------------------------------------

    waveforms = waveform.unsqueeze(0)

    if waveforms.ndim != 3:
        raise ValueError(
            "Embedding input must have 3 dimensions "
            "[batch, channels, samples]. "
            f"Got: {tuple(waveforms.shape)}"
        )

    if waveforms.shape[0] != 1:
        raise ValueError(
            "Expected batch size 1."
        )

    if waveforms.shape[1] != 1:
        raise ValueError(
            "Expected mono audio with one channel."
        )

    if waveforms.shape[2] < 400:
        raise ValueError(
            "Audio segment is too short for the bundled speaker "
            f"embedding model: {waveforms.shape[2]} samples."
        )

    # -------------------------------------------------------------------------
    # Run the exact __call__ interface exposed by
    # PyannoteAudioPretrainedSpeakerEmbedding.
    # -------------------------------------------------------------------------

    with torch.inference_mode():

        embeddings = embedding_model(
            waveforms.to(device)
        )

    # The wrapper returns numpy.ndarray.
    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )

    # Expected shape:
    #
    # [batch, dimension]
    #
    # For one segment:
    #
    # [1, 256]
    # -------------------------------------------------------------------------

    if embeddings.ndim != 2:
        raise ValueError(
            "Unexpected embedding output shape: "
            f"{embeddings.shape}"
        )

    if embeddings.shape[0] != 1:
        raise ValueError(
            "Expected exactly one embedding."
        )

    embedding = embeddings[0]

    if embedding.size == 0:
        raise RuntimeError(
            "Embedding model returned an empty embedding."
        )

    # -------------------------------------------------------------------------
    # Normalize for cosine similarity.
    # -------------------------------------------------------------------------

    norm = np.linalg.norm(
        embedding
    )

    if not np.isfinite(norm) or norm == 0.0:
        raise RuntimeError(
            f"Invalid embedding norm: {norm}"
        )

    embedding = embedding / norm

    return embedding.astype(
        np.float32
    )
    


# =============================================================================
# EMBEDDING MATRIX STATISTICS
# =============================================================================

def calculate_within_speaker_statistics(
    embeddings: list[np.ndarray],
) -> dict[str, Any]:
    """
    Calculate pairwise similarity statistics within one diarization label.
    """

    similarities: list[float] = []

    for i in range(len(embeddings)):

        for j in range(i + 1, len(embeddings)):

            similarities.append(
                cosine_similarity(
                    embeddings[i],
                    embeddings[j],
                )
            )

    if not similarities:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
        }

    values = np.asarray(
        similarities,
        dtype=np.float32,
    )

    return {
        "count": int(len(values)),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
    }


def calculate_cross_speaker_statistics(
    speaker_a: list[np.ndarray],
    speaker_b: list[np.ndarray],
) -> dict[str, Any]:
    """
    Calculate pairwise similarity between two diarization labels.
    """

    similarities: list[float] = []

    for a in speaker_a:

        for b in speaker_b:

            similarities.append(
                cosine_similarity(a, b)
            )

    if not similarities:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
        }

    values = np.asarray(
        similarities,
        dtype=np.float32,
    )

    return {
        "count": int(len(values)),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
    }


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    print()
    print("=" * 80)
    print("COMMUNITY-1 BUNDLED SPEAKER EMBEDDING DIAGNOSTIC")
    print("=" * 80)
    print()

    # -------------------------------------------------------------------------
    # Recording
    # -------------------------------------------------------------------------

    audio_path = find_recording_file()

    print("Recording:")
    print(audio_path)
    print()

    # -------------------------------------------------------------------------
    # Cached diarization
    # -------------------------------------------------------------------------

    print("Loading cached diarization:")
    print(DIARIZATION_JSON)
    print()

    segments = load_cached_segments()

    print(
        f"Total cached segments: {len(segments)}"
    )

    # -------------------------------------------------------------------------
    # Load Community-1
    # -------------------------------------------------------------------------

    print()
    print("Loading Community-1...")

    hf_token = os.getenv("HF_TOKEN")

    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN environment variable is not set."
        )

    pipeline = Pipeline.from_pretrained(
        PIPELINE_NAME,
        token=hf_token,
    )

    if pipeline is None:
        raise RuntimeError(
            "Failed to load Community-1."
        )

    print("Community-1 loaded.")

    # -------------------------------------------------------------------------
    # Bundled embedding
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("BUNDLED EMBEDDING MODEL")
    print("=" * 80)

    embedding_model = getattr(
        pipeline,
        "_embedding",
        None,
    )

    if embedding_model is None:
        raise RuntimeError(
            "Community-1 does not expose the expected "
            "'_embedding' object."
        )

    print("Type:")
    print(type(embedding_model))

    print()
    print("Dimension:")

    dimension = getattr(
        embedding_model,
        "dimension",
        None,
    )

    print(dimension)

    print()
    print("Embedding object:")
    print(embedding_model)

    # -------------------------------------------------------------------------
    # Audio
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("LOADING AUDIO")
    print("=" * 80)

    waveform, sample_rate = load_audio(
        audio_path
    )

    # -------------------------------------------------------------------------
    # Select segments
    # -------------------------------------------------------------------------

    selected_segments = select_segments(
        segments
    )

    # -------------------------------------------------------------------------
    # Device
    # -------------------------------------------------------------------------

    device = torch.device("cpu")

    print()
    print("=" * 80)
    print("EXTRACTING SEGMENT-LEVEL EMBEDDINGS")
    print("=" * 80)
    print()

    print(
        f"Using device: {device}"
    )

    speaker_embeddings: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    errors: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    # -------------------------------------------------------------------------
    # Extract embeddings
    # -------------------------------------------------------------------------

    for speaker, speaker_segments in selected_segments.items():

        print()
        print(
            f"Processing {speaker}..."
        )

        speaker_embeddings[speaker] = []
        errors[speaker] = []

        for index, segment in enumerate(
            speaker_segments,
            start=1,
        ):

            try:

                segment_waveform = extract_segment(
                    waveform=waveform,
                    sample_rate=sample_rate,
                    start=segment["start"],
                    end=segment["end"],
                )

                embedding = generate_embedding(
                    embedding_model=embedding_model,
                    waveform=segment_waveform,
                    sample_rate=sample_rate,
                    device=device,
                )

                speaker_embeddings[speaker].append(
                    {
                        "index": index,
                        "start": segment["start"],
                        "end": segment["end"],
                        "duration": segment["duration"],
                        "embedding": embedding.tolist(),
                    }
                )

                print(
                    f"  {index:02d}: OK "
                    f"dimension={embedding.shape[0]} "
                    f"norm={np.linalg.norm(embedding):.4f}"
                )

            except Exception as exc:

                print(
                    f"  {index:02d}: FAILED"
                )

                print(
                    f"      {type(exc).__name__}: {exc}"
                )

                errors[speaker].append(
                    {
                        "index": index,
                        "start": segment["start"],
                        "end": segment["end"],
                        "duration": segment["duration"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

    # -------------------------------------------------------------------------
    # Validate
    # -------------------------------------------------------------------------

    for speaker in SPEAKERS_TO_ANALYZE:

        if not speaker_embeddings.get(speaker):

            raise RuntimeError(
                f"No embeddings were generated for {speaker}."
            )

    # -------------------------------------------------------------------------
    # Convert to numpy
    # -------------------------------------------------------------------------

    matrices: dict[str, list[np.ndarray]] = {}

    for speaker, records in speaker_embeddings.items():

        matrices[speaker] = [
            np.asarray(
                record["embedding"],
                dtype=np.float32,
            )
            for record in records
        ]

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("WITHIN-SPEAKER SIMILARITY")
    print("=" * 80)

    within_statistics = {}

    for speaker, embeddings in matrices.items():

        stats = calculate_within_speaker_statistics(
            embeddings
        )

        within_statistics[speaker] = stats

        print()
        print(speaker)

        for key, value in stats.items():
            print(
                f"  {key}: {value}"
            )

    # -------------------------------------------------------------------------
    # Cross-speaker comparison
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("CROSS-SPEAKER SIMILARITY")
    print("=" * 80)

    cross_statistics = {}

    for i, speaker_a in enumerate(
        SPEAKERS_TO_ANALYZE
    ):

        for speaker_b in SPEAKERS_TO_ANALYZE[
            i + 1:
        ]:

            stats = calculate_cross_speaker_statistics(
                matrices[speaker_a],
                matrices[speaker_b],
            )

            key = f"{speaker_a}__{speaker_b}"

            cross_statistics[key] = stats

            print()
            print(
                f"{speaker_a} vs {speaker_b}"
            )

            for name, value in stats.items():
                print(
                    f"  {name}: {value}"
                )

    # -------------------------------------------------------------------------
    # Full pairwise matrix
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("ALL EMBEDDING PAIR SIMILARITIES")
    print("=" * 80)

    all_records = []

    for speaker, records in speaker_embeddings.items():

        for record in records:

            all_records.append(
                {
                    "speaker": speaker,
                    "index": record["index"],
                    "embedding": np.asarray(
                        record["embedding"],
                        dtype=np.float32,
                    ),
                }
            )

    pairwise = []

    for i in range(len(all_records)):

        for j in range(i + 1, len(all_records)):

            a = all_records[i]
            b = all_records[j]

            similarity = cosine_similarity(
                a["embedding"],
                b["embedding"],
            )

            pairwise.append(
                {
                    "speaker_a": a["speaker"],
                    "index_a": a["index"],
                    "speaker_b": b["speaker"],
                    "index_b": b["index"],
                    "cosine_similarity": similarity,
                    "same_diarization_label": (
                        a["speaker"] == b["speaker"]
                    ),
                }
            )

    pairwise_sorted = sorted(
        pairwise,
        key=lambda x: x["cosine_similarity"],
        reverse=True,
    )

    print()
    print("Top 20 most similar pairs:")

    for pair in pairwise_sorted[:20]:

        print(
            f"  "
            f"{pair['speaker_a']}#{pair['index_a']:02d}"
            f" <-> "
            f"{pair['speaker_b']}#{pair['index_b']:02d}"
            f" = "
            f"{pair['cosine_similarity']:.4f}"
        )

    print()
    print("Top 20 most dissimilar pairs:")

    for pair in pairwise_sorted[-20:][::-1]:

        print(
            f"  "
            f"{pair['speaker_a']}#{pair['index_a']:02d}"
            f" <-> "
            f"{pair['speaker_b']}#{pair['index_b']:02d}"
            f" = "
            f"{pair['cosine_similarity']:.4f}"
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
        "embedding_model": {
            "type": str(
                type(embedding_model)
            ),
            "dimension": dimension,
        },
        "audio": {
            "sample_rate": sample_rate,
            "channels": int(
                waveform.shape[0]
            ),
            "samples": int(
                waveform.shape[-1]
            ),
        },
        "selection": {
            "minimum_duration": MIN_SEGMENT_DURATION,
            "max_segments_per_speaker": MAX_SEGMENTS_PER_SPEAKER,
        },
        "speaker_embeddings": speaker_embeddings,
        "errors": errors,
        "within_speaker_statistics": within_statistics,
        "cross_speaker_statistics": cross_statistics,
        "top_similar_pairs": pairwise_sorted[:20],
        "top_dissimilar_pairs": pairwise_sorted[-20:][::-1],
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
        f"Saved diagnostic results to:"
    )
    print(OUTPUT_JSON)

    print()
    print(
        "Embedding diagnostic completed successfully."
    )


if __name__ == "__main__":
    main()