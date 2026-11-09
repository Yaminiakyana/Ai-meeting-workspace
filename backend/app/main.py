from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.assistant import router as assistant_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.meetings import router as meetings_router
from app.api.routes.recordings import router as recordings_router
from app.api.routes.signaling import router as signaling_router
from app.api.routes.summaries import router as summaries_router
from app.api.routes.transcripts import router as transcripts_router

app = FastAPI(
    title="AI Meeting Workspace API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    health_router,
    prefix="/api",
)

app.include_router(
    auth_router,
    prefix="/api",
)

app.include_router(
    meetings_router,
    prefix="/api",
)

app.include_router(
    recordings_router,
    prefix="/api",
)

app.include_router(
    transcripts_router,
    prefix="/api",
)

app.include_router(
    summaries_router,
    prefix="/api",
)

app.include_router(
    assistant_router,
    prefix="/api",
)

app.include_router(
    signaling_router,
    prefix="/api",
)


@app.get("/")
def root():
    return {
        "message": "AI Meeting Workspace API",
        "version": "0.1.0",
        "features": [
            "Audio/Video Processing",
            "Speech-to-Text with Speaker Diarization",
            "AI Summarization",
            "Action Item & Decision Extraction",
            "RAG AI Meeting Assistant",
            "Synchronized Transcript Playback",
        ],
    }
