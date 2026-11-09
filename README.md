# AI Meeting Workspace

<p align="center">
  <strong>End-to-End AI-Powered Meeting Intelligence, Speaker Diarization, Summarization & Cross-Meeting RAG Assistant</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Celery-5.6-37814A?logo=celery&logoColor=white" alt="Celery" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React 19" />
  <img src="https://img.shields.io/badge/TailwindCSS-v4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind CSS v4" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/Whisper-OpenAI-00A67E?logo=openai&logoColor=white" alt="Whisper" />
  <img src="https://img.shields.io/badge/Pyannote-Audio-FF6F00" alt="Pyannote" />
</p>

---

## 📖 Overview

**AI Meeting Workspace** is an end-to-end meeting intelligence platform that transforms raw audio and video recordings into searchable, actionable knowledge. The system transcribes audio using OpenAI Whisper, separates different voices using Pyannote speaker diarization, generates structured AI summaries and action items, and organizes everything into an interactive meeting workspace.

Users can interact with a **RAG-based AI Meeting Assistant** to ask natural-language questions across individual meetings or hundreds of past meetings. Every response cites exact `[MM:SS]` timestamps, and clicking any citation immediately jumps playback to that exact second in the recording with synchronized transcript auto-highlighting.

### Dual User Experience:
* **🔥 Try Without Account (Guest Mode)**: Instant zero-setup ephemeral trial. All meeting uploads, transcripts, summaries, and chat occur in an isolated session that vanishes upon exit.
* **🛡️ Permanent Account**: Secure user registration and authentication where recordings, transcripts, summaries, action items, and vector embeddings are stored permanently in PostgreSQL.

---

## ⚡ Architecture Pipeline

```text
Meeting Recording (MP3 / WAV / M4A / MP4 / MOV)
       │
       ▼
Audio Validation & Storage (FastAPI)
       │
       ▼
Asynchronous Celery Worker (Redis Broker)
 ├── Speech-to-Text Transcription (Whisper Base / Word-Level Timestamps)
 ├── Speaker Diarization & Voice Clustering (Pyannote Community-1)
 └── Timestamp Alignment & Speaker Stabilization
       │
       ▼
Structured Meeting Intelligence Engine
 ├── Executive Summary & Thematic Discussion Points (Gemini / OpenAI / NLP Fallback)
 ├── Action Item Extraction (Tasks, Owners, Priorities, Deadlines)
 ├── Decision Tracking (Key Architectural Choices & Agreements)
 └── Personalized Follow-Up Email Generation
       │
       ▼
Vector Indexing & RAG Retrieval
 ├── Semantic Text Chunking & Embeddings (Gemini / OpenAI / TF-IDF Vector Space)
 └── Cross-Meeting Conversational RAG Assistant with Timestamp Citations
       │
       ▼
Interactive Frontend (React 19, Vite, Tailwind CSS v4)
 ├── Synchronized Audio Player Bar (Range Requests / Partial Content HTTP 206)
 ├── Real-Time Transcript Highlighting & Jump-to-Time Navigation
 └── Light & Dark Mode Theming
```

---

## 🚀 Key Features

* **🎙️ Audio & Video Processing**: Upload MP3, WAV, M4A, MP4, WebM, and MOV recordings. Stream seamlessly with HTTP 206 Partial Content range requests.
* **📝 Accurate Speech-to-Text**: Whisper model transcription with word-level start and end timestamps.
* **👥 Speaker Diarization**: Disentangles multiple speakers using Pyannote Community-1 clustering and stabilization algorithms.
* **🧠 Structured AI Summaries**: Executive briefs, discussion topics, and consensus points powered by Google Gemini, OpenAI, or smart local heuristic NLP fallback.
* **✅ Action Item Extraction**: Automatically identifies tasks, assigns owners, classifies priority (`High`, `Medium`, `Low`), and extracts deadlines with interactive completion toggles.
* **📌 Decision Log**: Dedicated repository of team agreements and strategic decisions with timestamp links.
* **⏱️ Audio-Transcript Synchronization**: Built-in audio player with speed controls (`1x`, `1.25x`, `1.5x`, `2x`), scrubbing, and instant jump-to-time navigation from any citation or transcript line.
* **🤖 RAG-Based AI Meeting Assistant**: Natural-language conversational Q&A over single meetings or the entire meeting history with `[MM:SS]` references.
* **📧 AI Follow-Up Email Generator**: Automatically crafts email recaps with action item checklists and custom instruction support.
* **🌓 Dark & Light Mode**: Complete theme system with automatic system preference detection, persistent switching, and high-contrast typing.
* **⚡ Asynchronous Background Execution**: Celery worker integration with automatic FastAPI `BackgroundTasks` fallback.

---

## 📁 Repository Structure

```text
Ai-meeting-workspace/
├── backend/
│   ├── alembic/                       # Database schema migrations
│   │   └── versions/                  # Migration scripts (tables, chunks, etc.)
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── assistant.py           # RAG chat & semantic search endpoints
│   │   │   ├── auth.py                # Registration, login, guest session & cleanup
│   │   │   ├── health.py              # Health check endpoint
│   │   │   ├── meetings.py            # Meetings CRUD operations
│   │   │   ├── recordings.py          # Recording upload & HTTP 206 audio streaming
│   │   │   ├── summaries.py           # Summaries, action items, decisions & email draft
│   │   │   └── transcripts.py         # Transcript segment retrieval
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic environment configuration
│   │   │   └── security.py            # JWT tokens & password hashing
│   │   ├── db/
│   │   │   └── database.py            # SQLAlchemy database engine & session maker
│   │   ├── models/                    # SQLAlchemy database models
│   │   │   ├── action_item.py
│   │   │   ├── decision.py
│   │   │   ├── meeting.py
│   │   │   ├── meeting_summary.py
│   │   │   ├── recording.py
│   │   │   ├── transcript.py
│   │   │   ├── transcript_chunk.py    # Vector RAG chunks
│   │   │   └── user.py
│   │   ├── schemas/                   # Pydantic request & response schemas
│   │   ├── services/
│   │   │   ├── diarization.py         # Pyannote pipeline & local cache loader
│   │   │   ├── meeting_summary.py     # LLM summarization & NLP engine
│   │   │   ├── rag_service.py         # Chunking, vector embeddings & RAG Q&A
│   │   │   ├── speaker_alignment.py   # Whisper segment & diarization alignment
│   │   │   └── speaker_stabilization.py
│   │   ├── worker/
│   │   │   ├── celery_app.py          # Celery configuration (macOS solo pool ready)
│   │   │   └── tasks.py               # Asynchronous process_recording worker task
│   │   └── main.py                    # FastAPI application initialization & CORS
│   ├── storage/                       # Local audio storage & processed caches (.gitkeep)
│   │   ├── recordings/
│   │   └── processed/
│   ├── .env.example                   # Environment template
│   ├── alembic.ini                    # Alembic configuration
│   └── requirements.txt               # Backend Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts              # Axios instance with auth interceptor
│   │   │   └── meetings.ts            # Type-safe API calls
│   │   ├── components/
│   │   │   ├── meetings/
│   │   │   │   ├── ActionItemsList.tsx
│   │   │   │   ├── AudioPlayerBar.tsx # Synchronized player & scrub bar
│   │   │   │   ├── DecisionsList.tsx
│   │   │   │   ├── FollowupEmailModal.tsx
│   │   │   │   ├── MeetingAssistantDrawer.tsx # Conversational RAG drawer
│   │   │   │   └── SummaryView.tsx
│   │   │   └── ThemeToggle.tsx        # Sun/Moon light & dark mode toggle
│   │   ├── pages/
│   │   │   ├── ActionItems.tsx        # Centralized task repository
│   │   │   ├── LandingPage.tsx        # Public landing & feature showcase
│   │   │   ├── Login.tsx              # Sign In, Create Account & Guest Mode
│   │   │   ├── MeetingDetails.tsx     # Full meeting cockpit & audio sync
│   │   │   ├── Meetings.tsx           # Meeting list & creation
│   │   │   └── WorkspaceDashboard.tsx # Authenticated workspace dashboard
│   │   ├── store/
│   │   │   ├── authStore.ts           # Zustand auth store (guest + permanent)
│   │   │   └── themeStore.ts          # Zustand dark/light theme store
│   │   ├── App.tsx                    # Routing & protected routes
│   │   ├── index.css                  # Tailwind CSS v4 & custom dark mode rules
│   │   └── main.tsx                   # React root entry
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docker-compose.yml                 # PostgreSQL 16 & Redis 7 services
├── .gitignore
└── README.md
```

---

## 🛠️ Prerequisites

Before running the application, ensure you have the following installed:

* **Docker & Docker Compose** (for PostgreSQL and Redis)
* **Python 3.11** (recommended via [Conda](https://docs.conda.io/) or `venv`)
* **Node.js 18+** & **npm**
* **FFmpeg** (required by Whisper for audio decoding):
  ```bash
  # macOS
  brew install ffmpeg

  # Ubuntu/Debian
  sudo apt-get update && sudo apt-get install -y ffmpeg
  ```

---

## ⚙️ Configuration & Environment Variables

Copy the example environment configuration into `backend/.env`:

```bash
cp backend/.env.example backend/.env
```

Configure your parameters in `backend/.env`:

```env
APP_NAME=AI Meeting Workspace
APP_VERSION=0.1.0

# Database & Cache (matches docker-compose.yml)
DATABASE_URL=postgresql+psycopg://meeting_user:meeting_password@localhost:5432/meeting_workspace
REDIS_URL=redis://localhost:6379/0

# JWT Security
JWT_SECRET_KEY=replace-with-a-secure-random-secret-key-32-chars-minimum
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# LLM Providers (Configure your preferred API key)
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
LLM_PROVIDER=auto   # Options: "auto", "gemini", or "openai"

# Hugging Face Token (Optional)
# If Pyannote Community-1 is already cached locally, this can remain blank.
HF_TOKEN=
```

> **Note**: Even if external LLM API keys are left blank, the application automatically falls back to its built-in heuristic NLP engine for summaries, action items, and semantic retrieval.

---

## 🚀 Running the Project

Follow these steps to launch all services locally:

### 1. Start Infrastructure (PostgreSQL & Redis)

Start the database and queue services with Docker Compose:

```bash
docker compose up -d
```

Verify that both containers are running healthy:
```bash
docker compose ps
```

---

### 2. Backend Setup & Database Migrations

In a new terminal, activate your Python 3.11 environment:

```bash
cd backend

# If using Conda:
conda activate meeting_ai

# Or if using venv:
# python -m venv venv && source venv/bin/activate

# Install Python dependencies:
pip install -r requirements.txt

# Apply database migrations:
alembic upgrade head

# Start the FastAPI backend:
uvicorn app.main:app --reload --port 8000
```

The backend API will be available at **`http://localhost:8000`**.  
Interactive Swagger API docs can be viewed at **`http://localhost:8000/docs`**.

---

### 3. Start the Celery Worker (Audio & AI Pipeline)

In another terminal, start the Celery worker to process uploaded recordings:

```bash
cd backend
conda activate meeting_ai  # or source venv/bin/activate

# Start Celery worker with solo pool (recommended for macOS & deep learning models):
celery -A app.worker.celery_app.celery_app worker --pool=solo --loglevel=info
```

> **macOS Note**: Celery defaults to `worker_pool="solo"` in `celery_app.py` to prevent Python 3.8+ `spawn` multiprocess unpack issues and Metal/MPS memory duplication when running PyTorch, Whisper, and Pyannote.

---

### 4. Frontend Setup

In another terminal, install and run the React frontend:

```bash
cd frontend
npm install
npm run dev
```

Open your browser and navigate to **`http://localhost:5173`**.

---

## 🧪 Testing the Application Flow

1. **Landing Page (`/`)**: Explore the project presentation or click **"Try Without Account"** to immediately launch Guest Mode.
2. **Create a Meeting**: Click **"New Meeting"**, add a title, description, and scheduled date.
3. **Upload Recording**: Upload an audio or video file (`.mp3`, `.wav`, `.m4a`, `.mp4`). The Celery worker will asynchronously transcribe with Whisper, perform speaker diarization, align transcript segments, extract action items, and build vector chunks.
4. **Playback & Sync**: Click **"Play"** on the recording. Notice how transcript cards highlight as audio advances, and clicking any line jumps playback directly to that moment.
5. **AI Summary & Follow-Up Email**: Inspect generated discussion points, toggle action item statuses, and draft a recap email.
6. **Chat with AI Assistant**: Open the **"Ask AI"** drawer to ask questions across meetings (e.g., *"What did Daniel mention about the landing page?"*). Click timestamp pills in the citations to verify against the source audio.
7. **Toggle Dark/Light Mode**: Click the Sun/Moon icon in the top header. Test typing in any input field to enjoy high-contrast black text on clean white inputs.

---

## 📡 API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Register a new permanent user account |
| `POST` | `/api/auth/login` | Authenticate and obtain JWT access token |
| `POST` | `/api/auth/guest` | Launch an ephemeral guest session |
| `DELETE` | `/api/auth/guest/cleanup` | Wipe guest meetings, recordings, and files |
| `GET` | `/api/meetings` | List all meetings for the current user |
| `POST` | `/api/meetings` | Create a new meeting |
| `GET` | `/api/meetings/{id}` | Retrieve meeting details and metadata |
| `POST` | `/api/meetings/{id}/recordings` | Upload meeting audio/video file |
| `GET` | `/api/meetings/{id}/recordings/{rec_id}/stream` | HTTP 206 Partial Content audio stream |
| `GET` | `/api/meetings/{id}/transcripts` | Retrieve timestamped, diarized transcript segments |
| `GET` | `/api/meetings/{id}/summary` | Retrieve meeting summary |
| `POST` | `/api/meetings/{id}/summary/generate` | Generate or regenerate AI summary & insights |
| `GET` | `/api/action-items` | Centralized repository of all user action items |
| `PATCH` | `/api/meetings/{id}/action-items/{item_id}` | Update action item status or assignee |
| `POST` | `/api/meetings/{id}/followup-email` | Draft recap email with custom instructions |
| `POST` | `/api/assistant/chat` | Cross-meeting or single-meeting RAG conversational Q&A |
| `GET` | `/api/assistant/search` | Semantic chunk search across transcripts |

---

## 💡 Troubleshooting

* **Celery `ValueError: not enough values to unpack` on macOS**:  
  Ensure Celery is run with `--pool=solo`. This is configured by default in `backend/app/worker/celery_app.py`.
* **Audio playback doesn't play**:  
  Verify that the recording processing status is `completed` and that Docker containers (`ai-meeting-postgres`, `ai-meeting-redis`) are running.
* **Port Conflicts (5432 or 6379)**:  
  If local Postgres or Redis is already running on your machine, stop them (`brew services stop postgresql` / `brew services stop redis`) or change the mapped port in `docker-compose.yml`.

---

## 📄 License

This project is licensed under the MIT License.
