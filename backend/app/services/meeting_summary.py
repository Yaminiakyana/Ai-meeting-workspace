from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.action_item import ActionItem
from app.models.decision import Decision
from app.models.meeting import Meeting
from app.models.meeting_summary import MeetingSummary
from app.models.transcript import Transcript

logger = logging.getLogger(__name__)


# ============================================================
# Helper: Format Transcripts for Prompting
# ============================================================

def format_transcript_for_prompt(transcripts: list[Transcript]) -> str:
    """
    Format transcript segments into a clean chronological text block
    with timestamps and speaker labels.
    """
    lines: list[str] = []
    for t in sorted(transcripts, key=lambda x: x.start_time):
        speaker = t.speaker_name or t.speaker_label or "Speaker"
        # Convert seconds to MM:SS
        start_m, start_s = divmod(int(t.start_time), 60)
        end_m, end_s = divmod(int(t.end_time), 60)
        time_tag = f"[{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}]"
        lines.append(f"{time_tag} {speaker}: {t.text.strip()}")
    return "\n".join(lines)


# ============================================================
# LLM Client Extraction (Gemini / OpenAI / Fallback)
# ============================================================

SUMMARY_PROMPT_SYSTEM = """You are an expert AI meeting intelligence assistant.
Analyze the provided meeting transcript with speaker tags and timestamps.
You must extract:
1. "summary": A rich, well-formatted Markdown summary covering:
   - ## Overview: A concise 2-3 sentence executive synopsis.
   - ## Key Discussion Points: Bulleted breakdown of major topics, points made, and context.
   - ## Outcomes: Main takeaways and consensus achieved.
2. "action_items": A list of all commitments, tasks, and to-dos extracted. Each item must have:
   - "description": Clear, actionable description of the task.
   - "assignee_name": Name or speaker label of the person responsible (or null if unassigned).
   - "priority": One of "high", "medium", "low".
   - "due_date": Target date or timeframe if mentioned (e.g. "2026-11-15" or "Friday"), else null.
   - "source_start_time": Floating point second timestamp where the task was discussed.
   - "source_end_time": Floating point second timestamp ending the discussion.
3. "decisions": A list of all definitive conclusions, agreements, or choices made. Each item must have:
   - "description": What was agreed upon.
   - "decision_type": Category such as "strategic", "technical", "timeline", "architecture", or "process".
   - "source_start_time": Floating point second timestamp where the decision occurred.
   - "source_end_time": Floating point second timestamp.

Return ONLY a valid JSON object with the keys "summary", "action_items", and "decisions".
Ensure timestamps reflect the exact seconds in the transcript."""


def _call_gemini(transcript_text: str, meeting_title: str) -> dict[str, Any] | None:
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = f"Meeting Title: {meeting_title}\n\nTranscript:\n{transcript_text}"

        response = client.models.generate_content(
            model=settings.llm_model or "gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SUMMARY_PROMPT_SYSTEM,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        if response.text:
            return json.loads(response.text)
    except Exception as exc:
        logger.warning("Gemini generation failed: %s", exc)
    return None


def _call_openai(transcript_text: str, meeting_title: str) -> dict[str, Any] | None:
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        prompt = f"Meeting Title: {meeting_title}\n\nTranscript:\n{transcript_text}"

        response = client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if content:
            return json.loads(content)
    except Exception as exc:
        logger.warning("OpenAI generation failed: %s", exc)
    return None


import os

def _heuristic_summary_fallback(transcripts: list[Transcript], meeting_title: str) -> dict[str, Any]:
    """
    Intelligent heuristic fallback when no LLM API key is configured or API is unreachable.
    Extracts high-signal sentences, detects commitments, and identifies decisions with timestamps.
    """
    action_keywords = [
        "will", "need to", "action item", "todo", "follow up", "deadline",
        "by next", "assigned to", "please ensure", "i will", "we should",
        "responsible for", "send", "review", "schedule", "create", "fix", "implement"
    ]
    decision_keywords = [
        "decided", "agreed", "decision", "let's go with", "approved", "finalized",
        "resolved", "conclusion", "opted for", "settled on", "confirmed"
    ]

    action_items = []
    decisions = []
    discussion_points = []

    for t in sorted(transcripts, key=lambda x: x.start_time):
        text_lower = t.text.lower()
        speaker = t.speaker_name or t.speaker_label or "Participant"

        # Check for decisions
        for dk in decision_keywords:
            if dk in text_lower and len(t.text.strip()) > 15:
                decisions.append({
                    "description": t.text.strip(),
                    "decision_type": "agreement",
                    "source_start_time": float(t.start_time),
                    "source_end_time": float(t.end_time),
                })
                break

        # Check for action items
        for ak in action_keywords:
            if re.search(rf"\b{ak}\b", text_lower) and len(t.text.strip()) > 15:
                # Deduce priority
                priority = "medium"
                if any(w in text_lower for w in ["urgent", "asap", "immediately", "critical"]):
                    priority = "high"
                elif any(w in text_lower for w in ["later", "low priority", "eventually"]):
                    priority = "low"

                action_items.append({
                    "description": t.text.strip(),
                    "assignee_name": speaker,
                    "priority": priority,
                    "due_date": None,
                    "source_start_time": float(t.start_time),
                    "source_end_time": float(t.end_time),
                })
                break

        if len(discussion_points) < 8 and len(t.text.strip()) > 25:
            start_m, start_s = divmod(int(t.start_time), 60)
            discussion_points.append(f"- **{speaker}** ({start_m:02d}:{start_s:02d}): {t.text.strip()}")

    # Synthesize Markdown Summary
    speakers_list = sorted({t.speaker_name or t.speaker_label for t in transcripts if t.speaker_label})
    speakers_str = ", ".join(speakers_list) if speakers_list else "Meeting attendees"
    total_duration = max((t.end_time for t in transcripts), default=0.0)
    dur_m, dur_s = divmod(int(total_duration), 60)

    summary_md = f"""## Overview
Meeting focused on **{meeting_title}** with participants: {speakers_str}. Total recorded discussion span is approximately {dur_m}m {dur_s}s covering key project milestones, coordination, and next steps.

## Key Discussion Points
{chr(10).join(discussion_points) if discussion_points else "- Productive review and coordination across the team."}

## Outcomes & Next Steps
- Team aligned on core objectives and discussed action items.
- Identified {len(action_items)} key action item(s) and {len(decisions)} decision(s) across the session.
"""

    return {
        "summary": summary_md,
        "action_items": action_items[:15],
        "decisions": decisions[:10],
    }


# ============================================================
# Main Extraction & Persistence Service
# ============================================================

def generate_meeting_insights(
    db: Session,
    meeting_id: int,
    force_regenerate: bool = False,
) -> dict[str, Any]:
    """
    Generate or load meeting summary, action items, and decisions.
    """
    meeting = db.scalar(select(Meeting).where(Meeting.id == meeting_id))
    if meeting is None:
        raise ValueError(f"Meeting {meeting_id} not found.")

    # Check if summary already exists and regeneration not requested
    existing_summary = db.scalar(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
    )
    existing_actions = db.scalars(
        select(ActionItem).where(ActionItem.meeting_id == meeting_id)
    ).all()
    existing_decisions = db.scalars(
        select(Decision).where(Decision.meeting_id == meeting_id)
    ).all()

    if existing_summary and not force_regenerate:
        return {
            "summary": existing_summary,
            "action_items": existing_actions,
            "decisions": existing_decisions,
            "cached": True,
        }

    # Fetch transcripts
    transcripts = db.scalars(
        select(Transcript)
        .where(Transcript.meeting_id == meeting_id)
        .order_by(Transcript.sequence_number.asc())
    ).all()

    if not transcripts:
        raise ValueError(f"No transcripts found for meeting {meeting_id}.")

    formatted_transcript = format_transcript_for_prompt(transcripts)

    # Attempt LLM generation
    result_data = None
    model_used = "heuristic-nlp"

    # 1. Try Gemini
    if settings.llm_provider in ("gemini", "auto"):
        gemini_result = _call_gemini(formatted_transcript, meeting.title)
        if gemini_result and "summary" in gemini_result:
            result_data = gemini_result
            model_used = f"gemini:{settings.llm_model}"

    # 2. Try OpenAI
    if not result_data and settings.llm_provider in ("openai", "auto"):
        openai_result = _call_openai(formatted_transcript, meeting.title)
        if openai_result and "summary" in openai_result:
            result_data = openai_result
            model_used = f"openai:{settings.openai_model}"

    # 3. Fallback heuristic
    if not result_data:
        result_data = _heuristic_summary_fallback(transcripts, meeting.title)
        model_used = "extractive-nlp-v1"

    # Persist Summary
    summary_text = str(result_data.get("summary", "")).strip()
    if not summary_text:
        summary_text = f"## Summary for {meeting.title}\n\nTranscript processed successfully."

    if existing_summary:
        existing_summary.summary = summary_text
        existing_summary.model_name = model_used
        existing_summary.updated_at = datetime.utcnow()
        summary_obj = existing_summary
    else:
        summary_obj = MeetingSummary(
            meeting_id=meeting_id,
            summary=summary_text,
            model_name=model_used,
        )
        db.add(summary_obj)

    # Replace / Re-populate Action Items
    if force_regenerate or not existing_actions:
        db.execute(delete(ActionItem).where(ActionItem.meeting_id == meeting_id))
        raw_actions = result_data.get("action_items", [])
        saved_actions = []
        for item in raw_actions:
            desc = str(item.get("description", "")).strip()
            if not desc:
                continue
            action = ActionItem(
                meeting_id=meeting_id,
                owner_id=None,
                description=desc,
                due_date=None,
                status="pending",
                priority=str(item.get("priority", "medium")).lower(),
                source_start_time=float(item["source_start_time"]) if item.get("source_start_time") is not None else None,
                source_end_time=float(item["source_end_time"]) if item.get("source_end_time") is not None else None,
            )
            db.add(action)
            saved_actions.append(action)
    else:
        saved_actions = existing_actions

    # Replace / Re-populate Decisions
    if force_regenerate or not existing_decisions:
        db.execute(delete(Decision).where(Decision.meeting_id == meeting_id))
        raw_decisions = result_data.get("decisions", [])
        saved_decisions = []
        for item in raw_decisions:
            desc = str(item.get("description", "")).strip()
            if not desc:
                continue
            decision = Decision(
                meeting_id=meeting_id,
                description=desc,
                decision_type=str(item.get("decision_type", "strategic")),
                source_start_time=float(item["source_start_time"]) if item.get("source_start_time") is not None else None,
                source_end_time=float(item["source_end_time"]) if item.get("source_end_time") is not None else None,
            )
            db.add(decision)
            saved_decisions.append(decision)
    else:
        saved_decisions = existing_decisions

    meeting.status = "summarized"
    db.commit()
    db.refresh(summary_obj)

    return {
        "summary": summary_obj,
        "action_items": saved_actions,
        "decisions": saved_decisions,
        "cached": False,
    }


# ============================================================
# Follow-up Email Generator
# ============================================================

def generate_followup_email(
    meeting_title: str,
    summary_text: str,
    action_items: list[ActionItem],
    decisions: list[Decision],
    custom_instructions: str | None = None,
) -> dict[str, str]:
    """
    Generate a clean, structured follow-up email.
    """
    actions_formatted = "\n".join(
        f"- [ ] {ai.description} ({ai.priority.capitalize()} priority)"
        for ai in action_items
    ) or "None recorded."

    decisions_formatted = "\n".join(
        f"- {d.description} ({d.decision_type or 'General'})"
        for d in decisions
    ) or "None recorded."

    subject = f"Meeting Summary & Action Items: {meeting_title}"

    body = f"""Hi Team,

Thank you for your time today in the "{meeting_title}" meeting. Below is a recap of our discussion, key decisions made, and assigned action items.

--------------------------------------------------
MEETING SUMMARY
--------------------------------------------------
{summary_text}

--------------------------------------------------
KEY DECISIONS
--------------------------------------------------
{decisions_formatted}

--------------------------------------------------
ACTION ITEMS & NEXT STEPS
--------------------------------------------------
{actions_formatted}

Please let me know if there are any additions or adjustments.

Best regards,
Meeting Intelligence Workspace
"""

    return {
        "subject": subject,
        "body": body,
    }
