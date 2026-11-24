# AI Meeting Workspace

<p align="center">
  <strong>End-to-End AI-Powered Meeting Intelligence, Live WebRTC Video Conferencing, Speaker Diarization, Real-Time Speech-to-Text & Cross-Meeting RAG Assistant</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/WebRTC-Native%20Mesh-333333?logo=webrtc&logoColor=white" alt="WebRTC" />
  <img src="https://img.shields.io/badge/WebSockets-FastAPI-009688?logo=fastapi&logoColor=white" alt="WebSockets" />
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

**AI Meeting Workspace** is a modern, end-to-end meeting intelligence and live collaboration platform. It offers both a **full-featured Google Meet-style live video conferencing room** and an **asynchronous recording intelligence pipeline**. 

With AI Meeting Workspace, you can launch instant live meetings, collaborate with video, audio, and screen sharing, read live floating speech subtitles, and automatically capture mixed master recordings. Once a meeting ends or an audio/video recording is uploaded, the platform transcribes speech, attributes voices with diarization, extracts executive summaries, action items, and strategic decisions, and organizes everything into an interactive meeting cockpit.

Users can also query their entire meeting history with a **Conversational RAG Meeting Assistant**, where every cited answer links to exact `[MM:SS]` timestamps that jump audio/video playback and highlight transcripts in real time.

### 🌟 Core Experience Modes:
* **🎥 Google Meet-Style Live Meeting Rooms**: Launch an instant live room with camera, microphone, and screen share. Invite team members with a 1-click link. View real-time floating captions as words are spoken, track live action items, and record the entire call in the browser. When the meeting ends, hardware turns off automatically, and the workspace opens with complete transcripts, AI summaries, action items, and decisions already organized!
* **📁 Audio/Video Upload & Deep AI Analysis**: Upload pre-recorded files (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.webm`, `.mov`). Asynchronous Celery workers transcribe with OpenAI Whisper and cluster voices with Pyannote speaker diarization.
* **🛡️ Secure Per-User Meeting Isolation**: Robust multi-user authentication ensures individuals only access meetings they launched or attended via invite link.
* **🔥 Ephemeral Guest Mode (Try Without Account)**: 1-click zero-setup trial session that runs in complete isolation and wipes upon session exit.

---

## ⚡ Architecture Pipeline

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                LIVE COLLABORATION STAGE                                │
│                                                                                        │
│  Host & Participants (React 19 / WebRTC Mesh)                                          │
│   ├── Video / Audio Tracks + Screen Share                                              │
│   ├── WebSocket Signaling Server (FastAPI /api/ws/meetings/{id})                       │
│   ├── Continuous Browser Speech Recognition & Multi-Peer Floating Subtitles Broadcast  │
│   ├── Synchronized Canonical Meeting Clock (Zero-Skew Timestamps)                      │
│   ├── Web Audio API Master Audio Mixer (Host Combines Local + Remote Voice Feeds)       │
│   └── In-Browser MediaRecorder (Single Canonical Whole-Meeting Master Recording)         │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                           Meeting Ended / Upload Initiated
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND INGESTION & WORKERS                               │
│                                                                                        │
│  FastAPI API Server (/api/meetings/{id}/recordings, /api/meetings/{id}/transcripts)    │
│   ├── Live Transcripts Batch Ingestion & Chronological Deduplication                   │
│   ├── HTTP 206 Partial Content Audio Streaming Range Server                            │
│   └── Multi-Tenant Database Storage (PostgreSQL 16)                                    │
│                                           │                                            │
│                                           ▼                                            │
│  Asynchronous Celery Worker (Redis Broker / Solo Worker Pool)                          │
│   ├── Speech-to-Text Transcription (Whisper Base / Word-Level Timestamps)              │
│   ├── Speaker Diarization & Voice Clustering (Pyannote Community-1)                    │
│   └── Timestamp Alignment & Speaker Stabilization                                      │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         MEETING INTELLIGENCE & RAG ENGINE                              │
│                                                                                        │
│  Structured Intelligence (Gemini / OpenAI / Heuristic NLP Engine)                      │
│   ├── Executive Brief & Thematic Key Discussion Points                                 │
│   ├── Action Item Extraction (Tasks, Owners, Priorities, Deadlines)                    │
│   ├── Strategic Decision Log (Agreements & Consensus)                                  │
│   └── AI Follow-Up Email Generator                                                     │
│                                           │                                            │
│  Vector Search & Conversational RAG Assistant                                          │
│   ├── Semantic Chunking & Vector Space Indexing                                        │
│   └── Cross-Meeting Natural Language Q&A with Clickable [MM:SS] Audio Jump Citations   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Features

### 🎥 1. Google Meet-Style Live Meeting Rooms (`/meetings/{id}/room`)
* **Instant 1-Click Launch**: Launch a live video room directly with one click from the dashboard or meeting list—no complex pre-scheduling required.
* **1-Click Shareable Invite Links**: Click **"Copy Link"** to invite guests or coworkers. Guests who open the link in their own account are automatically enrolled as meeting participants.
* **Camera, Microphone & Screen Share**: Toggle video feeds and audio inputs, or share full-screen displays, application windows, or browser tabs with picture-in-picture previews.
* **Active Speaker Ripple & Grid Layout**: Adaptive video grid layout dynamically accommodates 1, 2, or multiple participants with live pulsing green rings indicating active speakers.
* **Echo Guard (Same-Machine Testing)**: Top-right "Mute Speaker" control on remote participant video tiles allows multi-tab testing on the same laptop without screeching feedback loops.
* **Guaranteed Hardware LED Shutdown**: When leaving or ending a meeting, all camera, microphone, screen tracks, Web Speech instances, and AudioContext nodes are forcefully released—turning off hardware indicator lights immediately.

### 🗣️ 2. Real-Time Live Floating Captions & Multi-Peer Subtitles
* **Multi-Peer Live Subtitle Broadcasting**: Continuous speech recognition runs in the browser. As **any** participant speaks (Host or Candidate), live interim words and final subtitles float across **everyone's** screen in real time with the speaker's name (`[Yamini]: ...`, `[Munni]: ...`).
* **Browser Autoplay & User Gesture Auto-Activation**: Overcomes Chrome's autoplay gesture policy with automatic activation upon first user interaction and a 1-click floating "Turn On Captions" banner.
* **Synchronized Canonical Meeting Clock**: All participants share a unified meeting epoch clock. When a guest joins at `01:10`, their clock automatically begins at `01:10` instead of `00:00`, ensuring timestamps remain strictly chronological across the board without timezone skews.
* **Live Drawer with Captions, Actions & Decisions**: An expandable right-hand sidebar displays the scrolling transcript feed, live-detected action items, strategic decisions, and quick meeting notes in real time.

### 🔴 3. Single Canonical Master Recording
* **Unified Whole-Meeting Audio/Video Capture**: The host's browser automatically mixes local microphone input and incoming WebRTC remote audio streams into a single canonical WebM/MP4 recording using the Web Audio API and `MediaRecorder`.
* **Zero Duplicate Recordings**: Only one unified master recording is created and uploaded when the host ends the call—preventing redundant or conflicting files.
* **Instant Automatic Transition**: Ending the meeting automatically finalizes the recording, saves live transcripts, kicks off background AI summarization, and redirects all participants directly to the meeting cockpit.

### 🎙️ 4. Audio Processing & Deep Diarization Pipeline
* **Multi-Format Ingestion**: Supports `.mp3`, `.wav`, `.m4a`, `.mp4`, `.webm`, and `.mov` recording uploads.
* **OpenAI Whisper Speech-to-Text**: High-accuracy word-level transcription with precise millisecond boundaries.
* **Pyannote Speaker Diarization**: Disentangles and clusters multiple voices with heuristic stabilization to maintain consistent speaker labels across long conversations.
* **HTTP 206 Partial Content Streaming**: Fast, buffer-free audio and video seeking with byte-range requests.

### 🧠 5. Structured Meeting Intelligence & RAG Assistant
* **Executive Summary**: Comprehensive overviews and structured discussion themes powered by Google Gemini, OpenAI, or the built-in heuristic NLP fallback.
* **Action Items**: Identifies tasks, assigns owners, classifies priority (`High`, `Medium`, `Low`), and extracts target deadlines with interactive status checkboxes.
* **Decision Tracking**: Dedicated log capturing key architectural choices, consensus agreements, and next steps.
* **Synchronized Audio-Transcript Player**: Built-in audio bar with variable playback speeds (`1x`, `1.25x`, `1.5x`, `2x`), waveform scrubber, and real-time active transcript auto-scrolling and highlighting.
* **Conversational Cross-Meeting RAG Assistant**: Ask questions across single meetings or the entire organization's meeting history. Responses cite exact `[MM:SS]` timestamps—clicking any citation instantly seeks the audio player to that exact moment.
* **Follow-Up Email Drafter**: 1-click generation of formatted recap emails including action checklists and support for custom prompt instructions.

### 🛡️ 6. Multi-Tenant Security & Theme Customization
* **Strict Per-User Data Isolation**: PostgreSQL foreign key isolation ensures users only see meetings they launched or attended.
* **Modern Dynamic Color Themes**: Switch between Light, Dark, and Cyber Emerald AI palettes with persistent local storage.

---

## 📁 Repository Structure

```text
Ai-meeting-workspace/
├── backend/
│   ├── alembic/                       # Database schema migrations
│   │   └── versions/                  # Migration scripts (meetings, transcripts, participants, etc.)
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── assistant.py           # RAG chat & semantic search endpoints
│   │   │   ├── auth.py                # Registration, login, guest session & cleanup
│   │   │   ├── health.py              # Health check endpoint
│   │   │   ├── meetings.py            # Meetings CRUD, join endpoint & live transcript batch save
│   │   │   ├── recordings.py          # Recording upload & HTTP 206 audio streaming
│   │   │   ├── signaling.py           # Multi-user WebRTC & live caption WebSocket signaling
│   │   │   ├── summaries.py           # Summaries, action items, decisions & email draft
│   │   │   └── transcripts.py         # Chronological transcript segment retrieval
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic environment configuration
│   │   │   └── security.py            # JWT tokens & password hashing
│   │   ├── db/
│   │   │   └── database.py            # SQLAlchemy database engine & session maker
│   │   ├── models/                    # SQLAlchemy database models
│   │   │   ├── action_item.py
│   │   │   ├── decision.py
│   │   │   ├── meeting.py             # Meeting & MeetingParticipant models
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
│   │   │   └── ThemeToggle.tsx        # Dynamic palette & dark/light mode toggle
│   │   ├── pages/
│   │   │   ├── ActionItems.tsx        # Centralized task repository
│   │   │   ├── LandingPage.tsx        # Public landing & feature showcase
│   │   │   ├── LiveMeetingRoom.tsx    # Google Meet-style collaborative video room
│   │   │   ├── Login.tsx              # Sign In, Create Account & Guest Mode
│   │   │   ├── MeetingDetails.tsx     # Full meeting cockpit & audio sync
│   │   │   ├── Meetings.tsx           # Meeting list, launch & creation
│   │   │   └── WorkspaceDashboard.tsx # Authenticated workspace dashboard
│   │   ├── store/
│   │   │   ├── authStore.ts           # Zustand auth store (guest + permanent)
│   │   │   └── themeStore.ts          # Zustand dark/light theme store
│   │   ├── App.tsx                    # Routing & protected routes
│   │   ├── index.css                  # Tailwind CSS v4 & custom theme rules
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
celery -A app.worker.celery_app worker -l info -P solo
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

## 🧪 Testing the Application Flows

### Flow A: Live Meeting Room (Google Meet Style)
1. **Launch a Live Meeting**: From the dashboard or **"Meetings"** page, click **"Launch Instant Meeting"** (or open `/meetings/new/room`). Allow browser camera and microphone access.
2. **Invite Other Participants**:
   - In the live room, click **"Copy Link"** in the top bar or invite card.
   - Open another browser window or incognito tab signed into a different account, paste the link, and enter.
   - Both users will immediately appear in the balanced video grid via WebRTC.
3. **Real-Time Floating Subtitles**:
   - Speak into either microphone. Live floating subtitles immediately display on **both** users' screens with speaker attribution (`[User Name]: ...`).
   - Notice the speaking ripple visualizer and real-time feed in the right-hand **"Captions"** drawer.
4. **End & Auto-Analyze**:
   - The host clicks **"End & Save Meeting"**.
   - Camera and microphone indicators turn off immediately.
   - The master video/audio recording is uploaded, live transcripts are synchronized starting cleanly at `00:00`, and the meeting workspace opens with auto-generated summaries, action items, and decisions ready for review.

### Flow B: Recording Upload & RAG Assistant
1. **Upload Recording**: Click **"New Meeting"** or open an existing meeting card and upload an audio or video file (`.mp3`, `.wav`, `.m4a`, `.mp4`).
2. **Background Processing**: The Celery worker transcribes speech with Whisper, diarizes speakers with Pyannote, aligns segments, and extracts action items and vector chunks.
3. **Playback & Sync**: Click **"Play"** on the recording bar. As audio advances, corresponding transcript cards highlight automatically. Click any timestamp to jump to that moment.
4. **Conversational Assistant**: Open the **"Ask AI"** drawer and ask natural language questions (e.g., *"What did the team decide about deployment?"*). Click citation pills to jump directly to the relevant audio segment.
5. **Theme Selection**: Toggle the Sun/Moon/Palette button in the header to switch between light, dark, and cyber emerald themes.

---

## 📡 API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Register a new permanent user account |
| `POST` | `/api/auth/login` | Authenticate and obtain JWT access token |
| `POST` | `/api/auth/guest` | Launch an ephemeral guest session |
| `DELETE` | `/api/auth/guest/cleanup` | Wipe guest meetings, recordings, and files |
| `GET` | `/api/meetings` | List isolated meetings owned or attended by the current user |
| `POST` | `/api/meetings` | Create a new scheduled meeting |
| `GET` | `/api/meetings/{id}` | Retrieve meeting details and participant metadata |
| `POST` | `/api/meetings/{id}/join` | Register current authenticated user as an attendee of an existing meeting |
| `POST` | `/api/meetings/{id}/recordings` | Upload meeting audio/video file |
| `GET` | `/api/meetings/{id}/recordings/{rec_id}/stream` | HTTP 206 Partial Content audio streaming range request |
| `POST` | `/api/meetings/{id}/transcripts` | Save streaming/live transcript segments generated during live calls |
| `GET` | `/api/meetings/{id}/transcripts` | Retrieve timestamped, deduplicated transcript segments starting at `00:00` |
| `GET` | `/api/meetings/{id}/summary` | Retrieve meeting summary, action items, and decisions |
| `POST` | `/api/meetings/{id}/summary/generate` | Generate or regenerate AI summary & insights |
| `GET` | `/api/action-items` | Centralized repository of all user action items |
| `PATCH` | `/api/meetings/{id}/action-items/{item_id}` | Update action item status or assignee |
| `POST` | `/api/meetings/{id}/followup-email` | Draft recap email with custom instructions |
| `POST` | `/api/assistant/chat` | Cross-meeting or single-meeting RAG conversational Q&A |
| `GET` | `/api/assistant/search` | Semantic chunk search across transcripts |
| `WS` | `/api/ws/meetings/{id}` | Real-time WebRTC mesh signaling, media state & live caption broadcast |

---

## 💡 Troubleshooting

* **Celery `ValueError: not enough values to unpack` on macOS**:  
  Ensure Celery is run with `--pool=solo` (e.g. `celery -A app.worker.celery_app worker -l info -P solo`).
* **Audio playback doesn't play**:  
  Verify that the recording processing status is `completed` and that Docker containers (`ai-meeting-postgres`, `ai-meeting-redis`) are running.
* **Camera or Microphone blocked**:  
  Ensure browser permissions are granted for `http://localhost:5173`. If testing between two tabs on the same computer, use the **"Mute Speaker"** button on the remote participant tile to prevent acoustic audio feedback.
* **Live Captions not appearing**:  
  Click anywhere in the meeting window or click the floating **"Turn On Captions"** button to allow browser speech recognition activation under Chromium autoplay guidelines.
* **Port Conflicts (5432 or 6379)**:  
  If local Postgres or Redis is already running on your machine, stop them (`brew services stop postgresql` / `brew services stop redis`) or change the mapped port in `docker-compose.yml`.

---

## 📄 License

This project is licensed under the MIT License.
