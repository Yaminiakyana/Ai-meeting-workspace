from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    Citation,
    SearchResponse,
    SearchResultItem,
)
from app.services.rag_service import (
    ask_meeting_assistant,
    search_meeting_chunks,
)

router = APIRouter(
    prefix="/assistant",
    tags=["AI Assistant & Search"],
)


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
)
def assistant_chat_endpoint(
    request: AssistantChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    RAG-powered conversational assistant to ask natural language questions
    across a single meeting or the user's entire meeting history.
    """
    result = ask_meeting_assistant(
        db=db,
        user_id=current_user.id,
        question=request.question,
        meeting_id=request.meeting_id,
        history=[msg.model_dump() for msg in request.history] if request.history else None,
    )

    return {
        "answer": result["answer"],
        "citations": [Citation(**c) for c in result["citations"]],
        "sources_count": result["sources_count"],
    }


@router.get(
    "/search",
    response_model=SearchResponse,
)
def assistant_search_endpoint(
    q: str = Query(..., min_length=1, description="Natural language search query"),
    meeting_id: int | None = Query(None, description="Optional meeting ID filter"),
    limit: int = Query(8, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Semantic search across transcript segments.
    """
    matches = search_meeting_chunks(
        db=db,
        user_id=current_user.id,
        query=q,
        meeting_id=meeting_id,
        limit=limit,
    )

    return {
        "query": q,
        "results": [SearchResultItem(**m) for m in matches],
        "total": len(matches),
    }
