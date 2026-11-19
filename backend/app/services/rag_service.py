from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import numpy as np
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.meeting import Meeting
from app.models.meeting_participant import MeetingParticipant
from app.models.transcript import Transcript
from app.models.transcript_chunk import TranscriptChunk

logger = logging.getLogger(__name__)


# ============================================================
# Chunking Logic
# ============================================================

def chunk_transcripts(
    transcripts: list[Transcript],
    target_duration: float = 40.0,
    max_duration: float = 60.0,
) -> list[dict[str, Any]]:
    """
    Split chronological transcript segments into semantic chunks
    bounded by time (~40-60 seconds) or speaker shifts.
    """
    sorted_transcripts = sorted(transcripts, key=lambda x: x.start_time)
    if not sorted_transcripts:
        return []

    chunks: list[dict[str, Any]] = []
    current_texts: list[str] = []
    current_start = sorted_transcripts[0].start_time
    current_end = sorted_transcripts[0].end_time
    current_speakers: set[str] = set()
    recording_id = sorted_transcripts[0].recording_id

    for t in sorted_transcripts:
        speaker = t.speaker_name or t.speaker_label or "Speaker"
        duration = t.end_time - current_start

        if duration > target_duration and current_texts and (duration >= max_duration or len(current_speakers) > 2):
            chunks.append({
                "chunk_text": " ".join(current_texts),
                "speaker_label": ", ".join(sorted(current_speakers)),
                "start_time": current_start,
                "end_time": current_end,
                "recording_id": recording_id,
            })
            current_texts = []
            current_start = t.start_time
            current_speakers = set()

        start_m, start_s = divmod(int(t.start_time), 60)
        current_texts.append(f"[{start_m:02d}:{start_s:02d}] {speaker}: {t.text.strip()}")
        current_speakers.add(speaker)
        current_end = t.end_time

    if current_texts:
        chunks.append({
            "chunk_text": " ".join(current_texts),
            "speaker_label": ", ".join(sorted(current_speakers)),
            "start_time": current_start,
            "end_time": current_end,
            "recording_id": recording_id,
        })

    return chunks


# ============================================================
# Embeddings Helpers (Gemini, OpenAI, or Fallback)
# ============================================================

def _compute_embeddings_gemini(texts: list[str]) -> list[list[float]] | None:
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        embeddings = []
        for text in texts:
            res = client.models.embed_content(
                model=settings.embedding_model or "text-embedding-004",
                contents=text,
            )
            embeddings.append(res.embedding.values)
        return embeddings
    except Exception as exc:
        logger.warning("Gemini embeddings failed: %s", exc)
        return None


def _compute_embeddings_openai(texts: list[str]) -> list[list[float]] | None:
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        res = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in res.data]
    except Exception as exc:
        logger.warning("OpenAI embeddings failed: %s", exc)
        return None


# ============================================================
# Indexing Service
# ============================================================

def index_meeting_chunks(db: Session, meeting_id: int) -> int:
    """
    Chunk transcripts for a meeting and index them in the database.
    """
    transcripts = db.scalars(
        select(Transcript)
        .where(Transcript.meeting_id == meeting_id)
        .order_by(Transcript.sequence_number.asc())
    ).all()

    if not transcripts:
        return 0

    # Delete existing chunks for this meeting
    db.execute(delete(TranscriptChunk).where(TranscriptChunk.meeting_id == meeting_id))

    raw_chunks = chunk_transcripts(transcripts)
    if not raw_chunks:
        return 0

    chunk_texts = [c["chunk_text"] for c in raw_chunks]
    embeddings = None

    if settings.llm_provider in ("gemini", "auto"):
        embeddings = _compute_embeddings_gemini(chunk_texts)
    if embeddings is None and settings.llm_provider in ("openai", "auto"):
        embeddings = _compute_embeddings_openai(chunk_texts)

    for i, c in enumerate(raw_chunks):
        emb_json = json.dumps(embeddings[i]) if (embeddings and i < len(embeddings)) else None
        db_chunk = TranscriptChunk(
            meeting_id=meeting_id,
            recording_id=c.get("recording_id"),
            chunk_text=c["chunk_text"],
            speaker_label=c.get("speaker_label"),
            start_time=c["start_time"],
            end_time=c["end_time"],
            sequence_number=i,
            embedding=emb_json,
        )
        db.add(db_chunk)

    db.commit()
    return len(raw_chunks)


# ============================================================
# Search & Retrieval Service
# ============================================================

def search_meeting_chunks(
    db: Session,
    user_id: int,
    query: str,
    meeting_id: int | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """
    Perform hybrid vector/lexical search across transcript chunks.
    Filters strictly to meetings owned by user_id (and optionally meeting_id).
    """
    stmt = (
        select(TranscriptChunk, Meeting)
        .join(Meeting, TranscriptChunk.meeting_id == Meeting.id)
    )
    user_participated_meeting_ids = select(MeetingParticipant.meeting_id).where(
        MeetingParticipant.user_id == user_id
    )
    if meeting_id is not None:
        stmt = stmt.where(
            TranscriptChunk.meeting_id == meeting_id,
            or_(
                Meeting.owner_id == user_id,
                Meeting.id.in_(user_participated_meeting_ids),
            ),
        )
    else:
        stmt = stmt.where(
            or_(
                Meeting.owner_id == user_id,
                Meeting.id.in_(user_participated_meeting_ids),
            )
        )

    records = db.execute(stmt).all()
    if not records:
        # If no chunks yet, let's index on-demand if meeting_id provided
        if meeting_id:
            count = index_meeting_chunks(db, meeting_id)
            if count > 0:
                records = db.execute(stmt).all()
        if not records:
            return []

    chunks = [row[0] for row in records]
    meetings = {row[1].id: row[1] for row in records}

    # Vector search if query embedding is available
    query_emb = None
    if settings.llm_provider in ("gemini", "auto"):
        emb_list = _compute_embeddings_gemini([query])
        if emb_list:
            query_emb = emb_list[0]
    if query_emb is None and settings.llm_provider in ("openai", "auto"):
        emb_list = _compute_embeddings_openai([query])
        if emb_list:
            query_emb = emb_list[0]

    results = []

    if query_emb is not None:
        # Cosine similarity against stored embeddings
        q_vec = np.array(query_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        for chunk in chunks:
            sim = 0.0
            if chunk.embedding:
                try:
                    c_vec = np.array(json.loads(chunk.embedding), dtype=np.float32)
                    c_norm = np.linalg.norm(c_vec)
                    if q_norm > 0 and c_norm > 0:
                        sim = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
                except Exception:
                    sim = 0.0
            results.append((sim, chunk))
        results.sort(key=lambda x: x[0], reverse=True)
    else:
        # Fallback to TF-IDF + keyword matching
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            corpus = [c.chunk_text for c in chunks]
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            tfidf_mat = vectorizer.fit_transform(corpus)
            q_mat = vectorizer.transform([query])
            sim_scores = cosine_similarity(q_mat, tfidf_mat).flatten()

            for i, chunk in enumerate(chunks):
                results.append((float(sim_scores[i]), chunk))
            results.sort(key=lambda x: x[0], reverse=True)
        except Exception:
            # Simple keyword overlap fallback
            q_words = set(re.findall(r"\w+", query.lower()))
            for chunk in chunks:
                c_words = set(re.findall(r"\w+", chunk.chunk_text.lower()))
                overlap = len(q_words & c_words) / max(1, len(q_words))
                results.append((overlap, chunk))
            results.sort(key=lambda x: x[0], reverse=True)

    top_matches = []
    for score, chunk in results[:limit]:
        mt = meetings.get(chunk.meeting_id)
        top_matches.append({
            "meeting_id": chunk.meeting_id,
            "meeting_title": mt.title if mt else f"Meeting #{chunk.meeting_id}",
            "speaker": chunk.speaker_label,
            "start_time": chunk.start_time,
            "end_time": chunk.end_time,
            "text": chunk.chunk_text,
            "similarity_score": round(score, 4),
        })

    return top_matches


# ============================================================
# RAG AI Assistant Service
# ============================================================

ASSISTANT_SYSTEM_PROMPT = """You are an intelligent AI Meeting Assistant in the AI Meeting Workspace platform.
Your job is to answer the user's question accurately using ONLY the provided meeting transcript excerpts.
Rules:
1. Cite timestamps accurately using [MM:SS] format corresponding to the excerpts.
2. If multiple speakers or meetings are involved, name the speaker and meeting title.
3. Be clear, professional, concise, and direct.
4. If the retrieved excerpts do not contain sufficient information, state what is known and clarify what was not found."""


def ask_meeting_assistant(
    db: Session,
    user_id: int,
    question: str,
    meeting_id: int | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    RAG Assistant: retrieves relevant transcript context and generates an answer with citations.
    """
    matches = search_meeting_chunks(
        db=db,
        user_id=user_id,
        query=question,
        meeting_id=meeting_id,
        limit=5,
    )

    if not matches:
        return {
            "answer": "No relevant meeting transcripts were found matching your query. Please ensure meetings have completed recordings and transcripts.",
            "citations": [],
            "sources_count": 0,
        }

    # Build context string
    context_blocks = []
    for i, m in enumerate(matches, 1):
        m_start, s_start = divmod(int(m["start_time"]), 60)
        m_end, s_end = divmod(int(m["end_time"]), 60)
        time_str = f"[{m_start:02d}:{m_start:02d} - {m_end:02d}:{s_end:02d}]"
        context_blocks.append(
            f"--- Source #{i}: Meeting '{m['meeting_title']}' {time_str} ---\n{m['text']}"
        )
    context_text = "\n\n".join(context_blocks)

    user_prompt = f"""Context from recorded meetings:
{context_text}

User Question: {question}

Please answer the question based on the excerpts above, citing timestamps in [MM:SS] format:"""

    answer_text = None

    # Try Gemini
    if settings.llm_provider in ("gemini", "auto"):
        api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                res = client.models.generate_content(
                    model=settings.llm_model or "gemini-1.5-flash",
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=ASSISTANT_SYSTEM_PROMPT,
                        temperature=0.3,
                    ),
                )
                if res.text:
                    answer_text = res.text
            except Exception as e:
                logger.warning("Gemini assistant call failed: %s", e)

    # Try OpenAI
    if not answer_text and settings.llm_provider in ("openai", "auto"):
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                msgs = [{"role": "system", "content": ASSISTANT_SYSTEM_PROMPT}]
                if history:
                    for h in history[-4:]:
                        msgs.append({"role": h.get("role", "user"), "content": h.get("content", "")})
                msgs.append({"role": "user", "content": user_prompt})
                res = client.chat.completions.create(
                    model=settings.openai_model or "gpt-4o-mini",
                    messages=msgs,
                    temperature=0.3,
                )
                if res.choices[0].message.content:
                    answer_text = res.choices[0].message.content
            except Exception as e:
                logger.warning("OpenAI assistant call failed: %s", e)

    # Fallback answer synthesis
    if not answer_text:
        top_match = matches[0]
        start_m, start_s = divmod(int(top_match["start_time"]), 60)
        answer_text = (
            f"Based on **{top_match['meeting_title']}** at [{start_m:02d}:{start_s:02d}], "
            f"the relevant discussion states:\n\n> \"{top_match['text'][:350]}...\"\n\n"
            f"*(Generated via local semantic retrieval. Configure GEMINI_API_KEY or OPENAI_API_KEY for conversational synthesis.)*"
        )

    return {
        "answer": answer_text,
        "citations": [
            {
                "meeting_id": m["meeting_id"],
                "meeting_title": m["meeting_title"],
                "speaker": m["speaker"],
                "start_time": m["start_time"],
                "end_time": m["end_time"],
                "text": m["text"][:200],
            }
            for m in matches
        ],
        "sources_count": len(matches),
    }
