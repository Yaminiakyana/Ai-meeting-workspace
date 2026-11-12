from pathlib import Path
import json
import subprocess
import traceback

import whisper
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.recording import Recording
from app.models.transcript import Transcript

from app.services.diarization import diarize_audio

from app.services.speaker_alignment import (
    align_whisper_segments,
    correct_isolated_segment_switches,
    correct_segment_continuity,
    correct_transcript_continuations,
    merge_same_speaker_segments,
    resolve_unassigned_segments,
)

from app.services.speaker_stabilization import (
    stabilize_speaker_segments,
)

from app.services.meeting_summary import generate_meeting_insights
from app.services.rag_service import index_meeting_chunks
from app.worker.celery_app import celery_app


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STORAGE_ROOT = PROJECT_ROOT / "storage"

RECORDINGS_ROOT = (
    STORAGE_ROOT / "recordings"
)

PROCESSED_ROOT = (
    STORAGE_ROOT / "processed"
)


# ============================================================
# Whisper model
# ============================================================

_whisper_model = None


def resolve_recording_path(storage_key: str) -> Path:
    """
    Resolve a recording storage key to an existing file.

    Supports storage keys relative to the storage directory,
    the recordings directory, or absolute paths.
    """
    if not storage_key or not str(storage_key).strip():
        raise ValueError("Recording has an empty storage_key.")

    key_path = Path(storage_key).expanduser()

    candidates = []

    if key_path.is_absolute():
        candidates.append(key_path)
    else:
        candidates.extend(
            [
                STORAGE_ROOT / key_path,
                RECORDINGS_ROOT / key_path,
                PROJECT_ROOT / key_path,
            ]
        )

    checked = []

    for candidate in candidates:
        resolved = candidate.resolve()

        if resolved in checked:
            continue

        checked.append(resolved)

        if resolved.is_file():
            return resolved

    checked_paths = "\n".join(str(path) for path in checked)

    raise FileNotFoundError(
        "Could not locate the uploaded recording.\n"
        f"Storage key: {storage_key}\n"
        f"Checked paths:\n{checked_paths}"
    )



def get_whisper_model():

    global _whisper_model

    if _whisper_model is None:

        print("=" * 70)
        print(
            "Loading Whisper base model on CPU..."
        )
        print("=" * 70)

        _whisper_model = whisper.load_model(
            "base",
            device="cpu",
        )

        print(
            "Whisper base model loaded."
        )

    return _whisper_model


# ============================================================
# Processed directory
# ============================================================

def get_processed_dir(
    recording_id: int,
) -> Path:

    directory = (
        PROCESSED_ROOT
        / f"recording_{recording_id}"
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


# ============================================================
# JSON helpers
# ============================================================

def save_json(
    path: Path,
    data,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def load_json(
    path: Path,
):
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# ============================================================
# Audio Preparation (FFmpeg PCM standardizer)
# ============================================================

def prepare_processing_audio(audio_path: Path, processed_dir: Path) -> Path:
    """
    Ensure the audio file is converted to a 16kHz mono PCM WAV file
    for maximal accuracy and zero codec issues across Whisper and Pyannote.
    """
    audio_path = Path(audio_path).resolve()
    if audio_path.suffix.lower() == ".wav":
        return audio_path

    converted_wav = processed_dir / "audio_16k.wav"
    if converted_wav.is_file() and converted_wav.stat().st_size > 0:
        return converted_wav

    print(f"Converting {audio_path.name} to 16kHz mono WAV for Whisper & Diarization...")
    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(converted_wav)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0 and converted_wav.is_file() and converted_wav.stat().st_size > 0:
        print(f"Audio extraction successful: {converted_wav}")
        return converted_wav
    else:
        print(f"FFmpeg conversion notice: {res.stderr.decode('utf-8', errors='ignore')[:150]}")
        return audio_path


# ============================================================
# Whisper
# ============================================================


def transcribe_with_whisper(
    audio_path: Path,
    recording_id: int,
    force_reprocess: bool = False,
):
    audio_path = Path(audio_path).resolve()

    if not audio_path.is_file():
        raise FileNotFoundError(
            f"Recording audio file does not exist: {audio_path}"
        )

    processed_dir = get_processed_dir(recording_id)

    whisper_words_cache = processed_dir / "whisper_words.json"
    whisper_segments_cache = processed_dir / "whisper_segments.json"
    whisper_manifest = processed_dir / "whisper_cache_manifest.json"

    stat = audio_path.stat()

    current_manifest = {
        "recording_id": recording_id,
        "audio_path": str(audio_path),
        "file_size": stat.st_size,
        "modified_time_ns": stat.st_mtime_ns,
        "language": "en",
        "task": "transcribe",
        "model": "base",
    }

    if (
        not force_reprocess
        and whisper_words_cache.is_file()
        and whisper_segments_cache.is_file()
        and whisper_manifest.is_file()
    ):
        try:
            cached_manifest = load_json(whisper_manifest)

            if cached_manifest == current_manifest:
                words = load_json(whisper_words_cache)
                segments = load_json(whisper_segments_cache)

                print(
                    f"Using matching Whisper cache for recording "
                    f"{recording_id}: {len(segments)} segments."
                )

                return {
                    "words": words,
                    "segments": segments,
                    "language": "en",
                }

            print(
                "Whisper cache does not match the current audio file. "
                "Regenerating transcription."
            )

        except (OSError, ValueError, TypeError) as exc:
            print(f"Could not validate Whisper cache: {exc}")

    print("=" * 70)
    print("RUNNING WHISPER TRANSCRIPTION")
    print(f"Recording ID: {recording_id}")
    print(f"Audio file: {audio_path}")
    print("Language: English (en)")
    print("=" * 70)

    model = get_whisper_model()

    result = model.transcribe(
        str(audio_path),
        language="en",
        task="transcribe",
        fp16=False,
        verbose=True,
        word_timestamps=True,
    )

    words = []
    segments = []

    for index, segment in enumerate(result.get("segments", [])):
        text = str(segment.get("text") or "").strip()

        segment_words = []

        for word in segment.get("words") or []:
            word_text = str(word.get("word") or "").strip()

            if not word_text:
                continue

            start = float(word["start"])
            end = float(word["end"])

            if end <= start:
                continue

            item = {
                "word": word_text,
                "start": start,
                "end": end,
            }

            segment_words.append(item)
            words.append(item.copy())

        if not text:
            continue

        start = float(segment["start"])
        end = float(segment["end"])

        if end <= start:
            continue

        segments.append(
            {
                "segment_index": index,
                "start": start,
                "end": end,
                "text": text,
                "words": segment_words,
            }
        )

    save_json(whisper_words_cache, words)
    save_json(whisper_segments_cache, segments)
    save_json(whisper_manifest, current_manifest)

    print(
        f"Whisper finished: {len(words)} words, "
        f"{len(segments)} segments."
    )

    return {
        "words": words,
        "segments": segments,
        "language": "en",
    }


# ============================================================
# Diarization
# ============================================================

def run_diarization(
    audio_path: Path,
    recording_id: int,
):

    processed_dir = (
        get_processed_dir(
            recording_id
        )
    )

    diarization_cache = (
        processed_dir
        / "diarization.json"
    )

    # --------------------------------------------------------
    # Cached
    # --------------------------------------------------------

    if diarization_cache.exists():

        print("=" * 70)
        print(
            "LOADING CACHED DIARIZATION"
        )
        print("=" * 70)

        diarization_segments = (
            load_json(
                diarization_cache
            )
        )

        print(
            f"Loaded "
            f"{len(diarization_segments)} "
            "cached diarization segments."
        )

        return diarization_segments

    # --------------------------------------------------------
    # Run pyannote
    # --------------------------------------------------------

    print("=" * 70)
    print(
        "RUNNING SPEAKER DIARIZATION"
    )
    print("=" * 70)

    diarization_segments = (
        diarize_audio(
            audio_path
        )
    )

    save_json(
        diarization_cache,
        diarization_segments,
    )

    print(
        f"Saved "
        f"{len(diarization_segments)} "
        "diarization segments."
    )

    return diarization_segments


# ============================================================
# Database
# ============================================================

def delete_existing_transcript(
    db: Session,
    recording_id: int,
):

    db.query(
        Transcript
    ).filter(
        Transcript.recording_id
        == recording_id
    ).delete(
        synchronize_session=False
    )

    db.commit()


def save_transcript_segments(
    db: Session,
    recording: Recording,
    transcript_segments,
):

    saved_count = 0

    for index, segment in enumerate(
        transcript_segments
    ):

        text = (
            segment.get(
                "text",
                "",
            )
            .strip()
        )

        if not text:
            continue

        transcript = Transcript(
            meeting_id=recording.meeting_id,
            recording_id=recording.id,
            speaker_label=segment.get(
                "speaker_label"
            ),
            speaker_name=None,
            text=text,
            start_time=float(
                segment["start_time"]
            ),
            end_time=float(
                segment["end_time"]
            ),
            sequence_number=index,
            language=None,
        )

        db.add(transcript)

        saved_count += 1

    db.commit()

    print(
        f"Saved {saved_count} "
        "transcript rows."
    )


# ============================================================
# Celery task
# ============================================================


@celery_app.task(
    bind=True,
    name="app.worker.tasks.process_recording",
)
def process_recording(self, recording_id: int = None):
    """
    Process one recording:
      1. Load the recording from the database.
      2. Resolve and validate its audio path.
      3. Load or generate Whisper transcription.
      4. Load or generate diarization.
      5. Align and stabilize speaker segments.
      6. Save transcript JSON and database records.

    Uses cached Whisper and diarization results when available.
    """
    # Support both Celery execution (self=Task, recording_id=int)
    # and direct Python calls (process_recording(recording_id))
    if recording_id is None and isinstance(self, int):
        recording_id = self


    db = SessionLocal()

    try:
        # ----------------------------------------------------
        # 1. Load recording
        # ----------------------------------------------------
        recording = (
            db.query(Recording)
            .filter(Recording.id == recording_id)
            .first()
        )

        if recording is None:
            raise ValueError(
                f"Recording ID {recording_id} was not found."
            )

        print("=" * 70)
        print("PROCESSING RECORDING")
        print("=" * 70)

        # ----------------------------------------------------
        # 2. Resolve audio path
        # ----------------------------------------------------
        audio_path = resolve_recording_path(
            recording.storage_key
        )

        print(f"Processing recording ID: {recording.id}")
        print(f"Original filename: {recording.file_name}")
        print(f"Storage key: {recording.storage_key}")
        print(f"Resolved audio file: {audio_path}")
        print(
            f"File size: {audio_path.stat().st_size:,} bytes"
        )

        if audio_path.stat().st_size == 0:
            raise ValueError(
                f"Recording file is empty: {audio_path}"
            )

        processed_dir = get_processed_dir(recording.id)

        # Standardize audio for Whisper & Pyannote (e.g. webm/mp4 to 16kHz mono wav)
        processing_audio_path = prepare_processing_audio(
            audio_path=audio_path,
            processed_dir=processed_dir,
        )

        # ----------------------------------------------------
        # 3. Whisper transcription
        # ----------------------------------------------------
        whisper_result = transcribe_with_whisper(
            audio_path=processing_audio_path,
            recording_id=recording.id,
        )

        whisper_segments = whisper_result.get("segments", [])

        if not whisper_segments:
            print("Whisper detected no verbal speech in recording; checking for live transcripts or marking completed.")
            # Check if there are live transcripts in the DB
            existing_transcripts = db.scalars(
                select(Transcript).where(Transcript.meeting_id == recording.meeting_id)
            ).all()

            if existing_transcripts:
                print(f"Preserving {len(existing_transcripts)} live transcripts.")
            else:
                # Add a placeholder notice segment so the user sees the audio was processed
                placeholder = Transcript(
                    meeting_id=recording.meeting_id,
                    recording_id=recording.id,
                    speaker_label="Speaker 1",
                    speaker_name="Speaker 1",
                    text="(No verbal speech detected in the audio recording)",
                    start_time=0.0,
                    end_time=recording.duration_seconds or 2.0,
                    sequence_number=1,
                )
                db.add(placeholder)
                db.commit()

            try:
                generate_meeting_insights(db, recording.meeting_id, force_regenerate=True)
                index_meeting_chunks(db, recording.meeting_id)
            except Exception as ins_err:
                print(f"Insights note: {ins_err}")

            recording.processing_status = "completed"
            recording.processing_error = None
            db.commit()
            return {
                "recording_id": recording.id,
                "status": "completed",
                "transcript_segments": len(existing_transcripts) or 1,
            }

        # ----------------------------------------------------
        # 4. Speaker diarization
        # ----------------------------------------------------
        try:
            diarization_segments = run_diarization(
                audio_path=processing_audio_path,
                recording_id=recording.id,
            )
        except Exception as diar_err:
            print(f"Diarization notice ({diar_err}); falling back to default speaker.")
            diarization_segments = []

        if not diarization_segments:
            print("Diarization produced no speaker segments; assigning Speaker 1 to all segments.")
            diarization_segments = [
                {
                    "speaker": "Speaker 1",
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                }
                for seg in whisper_segments
            ]

        # ----------------------------------------------------
        # 5. Align transcript and speakers
        # ----------------------------------------------------
        aligned_segments = align_whisper_segments(
            whisper_segments,
            diarization_segments,
        )

        # Normalize timestamp fields and order.
        stabilized_segments = stabilize_speaker_segments(
            aligned_segments
        )

        # Apply existing alignment correction functions.
        stabilized_segments = correct_segment_continuity(
            stabilized_segments
        )

        stabilized_segments = correct_transcript_continuations(
            stabilized_segments
        )

        stabilized_segments = correct_isolated_segment_switches(
            stabilized_segments
        )

        stabilized_segments = resolve_unassigned_segments(
            stabilized_segments
        )

        stabilized_segments = merge_same_speaker_segments(
            stabilized_segments
        )

        stabilized_segments = stabilize_speaker_segments(
            stabilized_segments
        )

        # ----------------------------------------------------
        # 6. Save JSON output
        # ----------------------------------------------------
        final_transcript_path = (
            processed_dir / "final_speaker_transcript.json"
        )

        save_json(
            final_transcript_path,
            stabilized_segments,
        )

        print(
            f"Saved {len(stabilized_segments)} transcript segments."
        )
        print(f"Transcript JSON: {final_transcript_path}")

        # ----------------------------------------------------
        # 7. Save transcript to database
        # ----------------------------------------------------
        delete_existing_transcript(
            db,
            recording.id,
        )

        save_transcript_segments(
            db,
            recording,
            stabilized_segments,
        )

        # ----------------------------------------------------
        # 7.5. Generate meeting summary & RAG index
        # ----------------------------------------------------
        try:
            print("=" * 70)
            print("GENERATING SUMMARY & EXTRACTING ACTION ITEMS/DECISIONS")
            print("=" * 70)
            generate_meeting_insights(db, recording.meeting_id, force_regenerate=True)
            index_meeting_chunks(db, recording.meeting_id)
            print("Summary, insights, and vector chunks generated successfully.")
        except Exception as insight_err:
            print(f"Warning: Could not generate automatic summary: {insight_err}")

        # ----------------------------------------------------
        # 8. Update processing status
        # ----------------------------------------------------
        # Keep these values consistent with your existing API.
        recording.processing_status = "completed"
        recording.processing_error = None

        db.commit()

        return {
            "recording_id": recording.id,
            "status": "completed",
            "transcript_segments": len(stabilized_segments),
            "transcript_path": str(final_transcript_path),
        }

    except Exception as exc:
        db.rollback()

        print(
            f"Failed to process recording {recording_id}: {exc}"
        )
        traceback.print_exc()

        # Update status in a separate transaction.
        try:
            recording = (
                db.query(Recording)
                .filter(Recording.id == recording_id)
                .first()
            )

            if recording is not None:
                recording.processing_status = "failed"
                recording.processing_error = str(exc)[:2000]
                db.commit()

        except Exception:
            db.rollback()
            traceback.print_exc()

        raise

    finally:
        db.close()
