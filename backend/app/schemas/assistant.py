from pydantic import BaseModel


class AssistantMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class Citation(BaseModel):
    meeting_id: int
    meeting_title: str
    speaker: str | None = None
    start_time: float
    end_time: float
    text: str


class AssistantChatRequest(BaseModel):
    question: str
    meeting_id: int | None = None  # None = search across all user meetings
    history: list[AssistantMessage] = []


class AssistantChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    sources_count: int = 0


class SearchQueryRequest(BaseModel):
    query: str
    meeting_id: int | None = None
    limit: int = 10


class SearchResultItem(BaseModel):
    meeting_id: int
    meeting_title: str
    speaker: str | None = None
    start_time: float
    end_time: float
    text: str
    similarity_score: float = 0.0


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem] = []
    total: int = 0
