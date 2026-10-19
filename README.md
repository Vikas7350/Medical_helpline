# SwasSetu: Multilingual AI Medical Helpline for Rural Feature Phones

**SwasSetu** is a production-ready, clinician-reviewed, multilingual AI medical helpline backend built for rural communities in India where callers predominantly use basic button feature phones over cellular networks (GSM/PSTN).

Callers dial an IVR helpline number, navigate a simple keypad menu (**1 for English, 2 for Hindi, 3 for Marathi**), speak their health symptoms in their native language, and receive immediate audio health triage guidance.

The project integrates with **Exotel AgentStream / Voicebot** bi-directional WebSockets (8 kHz mono PCM) and includes an **Administrative Web Dashboard** with real-time health surveillance charts, privacy-preserving logs, and an **Interactive Rural Feature Phone Simulator**.

---

## 🌟 Key Features

1. **Feature Phone First (Zero Smartphone / Internet Requirement)**:
   - Works over standard cellular voice calls via Exotel telephony.
   - Dual-Tone Multi-Frequency (DTMF) keypad menu navigation:
     - `1`: English
     - `2`: Hindi (हिंदी)
     - `3`: Marathi (मराठी)
     - `0`: Repeat last guidance message
     - `9`: End call gracefully

2. **Clinician-Reviewable 3-Tier Medical Triage**:
   - **Emergency (Red)**: Immediate bypass! Red-flag symptoms (severe chest pain, breathing difficulty, stroke signs, severe hemorrhage) trigger immediate emergency referral instructions (`Call 108 / visit nearest emergency hospital immediately`) without delaying callers with unnecessary questions.
   - **Prompt Medical Assessment (Amber)**: Multi-day persistent fever (>3 days), prolonged diarrhea/vomiting with dehydration, animal bites (rabies protocol), or maternal complications; directs caller to the village ASHA/ANM worker or Primary Health Centre (PHC).
   - **General Guidance (Green)**: Mild, self-limiting seasonal cold/cough, mild tension headache, or exertion fatigue; provides supportive hydration, rest, and red-flag watch-outs.

3. **Strict Medical Guardrails**:
   - AI **never** diagnoses a medical condition.
   - AI **never** prescribes prescription drugs or exact dosages.
   - AI **never** declares a caller 100% safe.
   - Mandatory non-diagnostic clinical disclaimer spoken in all 3 languages.
   - Ambiguous symptoms safely default to recommending a clinical checkup.

4. **Zero-PII Privacy by Design**:
   - No caller phone numbers stored (hashed on receipt with HMAC/SHA-256 for rate-limiting only).
   - No caller names, addresses, voice recordings, or transcripts retained.
   - Timestamps rounded to the minute to prevent correlation attacks.
   - Configurable automated data-retention purging (default: 90 days).

5. **Independent AI & Speech Provider Architecture**:
   - **LLM Guidance**: Supported providers include `grok` (xAI Grok-2), `openai` (GPT-4o-mini), and `mock` (deterministic clinical rule engine).
   - **Speech-to-Text (STT)**: Independent STT via `speech_recognition` (Google Speech API) or `mock`.
   - **Text-to-Speech (TTS)**: Independent TTS via `deepgram` (Deepgram Aura), `openai` (TTS-1), or `mock` (telephony acoustic chime).
   - **Safe Error Handling**: When a real TTS provider fails (e.g. 401 invalid key), the system logs the error safely without leaking API keys and reports speech failure rather than silently falling back to a beep.

---

## 🏛️ System Architecture

```mermaid
graph TD
    User([Rural Caller with Button Phone]) -->|Cellular Call / DTMF| Exotel[Exotel Voicebot / AgentStream]
    Exotel -->|8 kHz Mono PCM / WebSocket| StreamWS[/api/v1/telephony/stream/]
    Exotel -->|Webhook Fallback / DTMF| Webhook[/api/v1/telephony/webhook]
    
    subgraph "FastAPI Helpline Backend (app/)"
        StreamWS --> AudioProc[Audio Pacing & Gating: 8kHz PCM]
        AudioProc --> STT[STT: SpeechRecognition / Mock]
        STT --> Engine[Helpline State Machine]
        Engine --> Triage[Medical Safety & Triage Engine]
        Triage --> LLM[LLM Guidance: Grok / OpenAI / Mock Engine]
        LLM --> Guardrails[Safety Guardrails Validation]
        Guardrails --> TTS[TTS: Deepgram / OpenAI / Mock]
        TTS --> Outbound[8kHz Resampler & Outbound Chunk Streamer]
    end

    subgraph "Storage & Administration"
        Engine --> Repo[Privacy-Preserving Repository]
        Repo --> DB[(SQLite / PostgreSQL)]
        DB --> Dashboard[Web Analytics Dashboard: :8000]
        Dashboard --> Simulator[Interactive Phone Simulator UI]
    end
```

---

## ⚙️ Environment Configuration Guide (.env)

The application reads its configuration from a `.env` file in the project root. A template is provided in `.env.example`.

### How to set up your `.env`:
1. In your project root, copy `.env.example` to create `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` in your editor and configure the variables according to your setup.

---

### Configuration Variables Breakdown

| Variable | Description | Recommended / Allowed Values | Default in .env.example |
| :--- | :--- | :--- | :--- |
| **`ENVIRONMENT`** | Application environment | `development` \| `production` \| `test` | `development` |
| **`DEBUG`** | Enable debug mode and hot-reloading | `true` \| `false` | `true` |
| **`HOST`** | Host interface to bind server | `0.0.0.0` or `127.0.0.1` | `0.0.0.0` |
| **`PORT`** | Server port | `8000` | `8000` |
| **`DATABASE_URL`** | Database connection string | `sqlite:///./helpline.db` or PostgreSQL URI | `sqlite:///./helpline.db` |
| **`ADMIN_API_KEY`** | API key to access admin analytics | Change in production! | `dev-hackathon-admin-key-2026` |
| **`ADMIN_SECRET_TOKEN`**| Admin secret token | Change in production! | `dev-secret-token-change-in-prod` |
| **`TELEPHONY_PROVIDER`**| Telephony integration mode | `mock` (local browser simulator) or `exotel` | `mock` |
| **`EXOTEL_ACCOUNT_SID`**| Your Exotel Account SID | Found in Exotel API Console | `your_exotel_account_sid_here` |
| **`EXOTEL_API_KEY`** | Your Exotel API Key | Found in Exotel API Console | `your_exotel_api_key_here` |
| **`EXOTEL_API_TOKEN`** | Your Exotel API Token | Found in Exotel API Console | `your_exotel_api_token_here` |
| **`EXOTEL_VIRTUAL_NUMBER`**| Your assigned Exotel Landline/Mobile Number | e.g. `+9180XXXXXXXX` | `+918000000000` |
| **`TELEPHONY_WEBHOOK_SECRET`**| HMAC secret for webhook signature verification | Your secret string | `your_webhook_hmac_secret_here` |
| **`EXOTEL_STREAM_SAMPLE_RATE`**| Telephony audio sample rate | `8000` (standard PSTN) or `16000` | `8000` |
| **`EXOTEL_STREAM_BASE_URL`**| Public WSS URL for Exotel Voicebot Applet | e.g. `wss://your-ngrok.ngrok-free.app/api/v1/telephony/stream` (leave blank to auto-infer) | *(blank)* |
| **`EXOTEL_STREAM_CHUNK_SIZE`**| Audio chunk size in bytes (must be multiple of 320) | `3200` (~200ms at 8kHz) | `3200` |
| **`EXOTEL_STREAM_REQUIRE_AUTH`**| Require Basic Auth on WebSocket stream | `false` (whitelisted IP mode) or `true` | `false` |
| **`STT_PROVIDER`** | Speech-to-Text provider | `mock` \| `speech_recognition` | `mock` |
| **`TTS_PROVIDER`** | Text-to-Speech provider | `edge_tts` (Recommended for multilingual calls) \| `deepgram` \| `openai` \| `mock` | `edge_tts` |
| **`LLM_PROVIDER`** | Clinical triage text generation provider | `mock` \| `grok` \| `xai` \| `openai` | `mock` |
| **`XAI_API_KEY`** | **xAI Grok API Key** (used when `LLM_PROVIDER=grok`) | `xai-...` | *(blank)* |
| **`OPENAI_API_KEY`** | OpenAI API Key (used when `TTS_PROVIDER=openai` or `LLM_PROVIDER=openai`) | `sk-proj-...` | *(blank)* |
| **`DEEPGRAM_API_KEY`**| Deepgram API Key (used when `TTS_PROVIDER=deepgram`) | `dg-...` | *(blank)* |
| **`DATA_RETENTION_DAYS`**| Number of days before auto-purging session records | `90` | `90` |
| **`MAX_CALL_DURATION_SECONDS`**| Call duration timeout | `480` (8 minutes) | `480` |
| **`TURN_TIMEOUT_SECONDS`**| Inactivity timeout per turn | `30` | `30` |

---

## 🧩 Provider Compatibility & Setup Profiles

### ⚠️ Multilingual TTS & xAI Grok Architecture
- **xAI Grok is a Large Language Model (LLM)**. It processes text and generates clinical triage guidance via `https://api.x.ai/v1/chat/completions` (model: `grok-2-latest`).
- **xAI does NOT offer a public standalone REST TTS endpoint** for converting text to telephony audio waveforms. Chat completion models do not output audio.
- Therefore, **do not set `TTS_PROVIDER=grok`**. Grok handles text generation (`LLM_PROVIDER=grok`), while speech synthesis is configured independently via `TTS_PROVIDER`.
- **Deepgram Aura Limitation**: Deepgram Aura models (e.g. `aura-asteria-en`) are acoustic models trained exclusively for English. Sending Hindi or Marathi Devanagari text to an English-only voice sounds like gibberish. If `TTS_PROVIDER=deepgram` is configured, SwasSetu automatically routes Hindi (`hi`) and Marathi (`mr`) calls to `EdgeTTSService` to guarantee clear, natural speech.
- **Recommended Multilingual TTS**: Setting **`TTS_PROVIDER=edge_tts`** uses Microsoft Azure Neural Voices:
  - **Hindi (`hi`)**: `hi-IN-SwaraNeural` (Natural Devanagari Hindi)
  - **Marathi (`mr`)**: `mr-IN-AarohiNeural` (Natural Devanagari Marathi)
  - **English (`en`)**: `en-IN-NeerjaNeural` (Indian English)
  - **Cost**: **$0 (100% Free)**, zero API key required, native Devanagari support.

---

### Profile 1: Complete Offline Testing (Zero Credentials / 100% Free)
Ideal for local feature phone simulator testing, hackathon demos, and running the test suite without any external API costs.

```ini
ENVIRONMENT=development
TELEPHONY_PROVIDER=mock
STT_PROVIDER=mock
TTS_PROVIDER=mock
LLM_PROVIDER=mock
```

---

### Profile 2: xAI Grok for LLM + Edge TTS for Multilingual Spoken Audio (Recommended Real Exotel Calls)
Uses your **xAI Grok API key** for intelligent clinical triage guidance, **Edge TTS** for native, understandable Hindi, Marathi, and Indian English 8 kHz voice output, and **SpeechRecognition** for transcribing caller speech.

```ini
ENVIRONMENT=development
TELEPHONY_PROVIDER=exotel

# Telephony credentials
EXOTEL_ACCOUNT_SID=your_exotel_account_sid
EXOTEL_API_KEY=your_exotel_api_key
EXOTEL_API_TOKEN=your_exotel_api_token
EXOTEL_VIRTUAL_NUMBER=+9180XXXXXXXX
EXOTEL_STREAM_REQUIRE_AUTH=false

# AI Services
STT_PROVIDER=speech_recognition
TTS_PROVIDER=edge_tts
LLM_PROVIDER=grok

# API Keys
XAI_API_KEY=xai-your-grok-api-key-here
```


---

### Profile 3: xAI Grok for LLM + OpenAI for TTS
Uses **xAI Grok** for medical text generation and a valid **OpenAI API key** for OpenAI voice synthesis (`tts-1`).

```ini
ENVIRONMENT=development
TELEPHONY_PROVIDER=exotel

# Telephony credentials
EXOTEL_ACCOUNT_SID=your_exotel_account_sid
EXOTEL_API_KEY=your_exotel_api_key
EXOTEL_API_TOKEN=your_exotel_api_token
EXOTEL_VIRTUAL_NUMBER=+9180XXXXXXXX

# AI Services
STT_PROVIDER=speech_recognition
TTS_PROVIDER=openai
LLM_PROVIDER=grok

# API Keys
XAI_API_KEY=xai-your-grok-api-key-here
OPENAI_API_KEY=sk-proj-your-valid-openai-key-here
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ installed
- Virtual environment (recommended):
  ```bash
  # Windows:
  python -m venv venv
  venv\Scripts\activate

  # Linux / macOS:
  python3 -m venv venv
  source venv/bin/activate
  ```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Configuration
```bash
# Copy example configuration
cp .env.example .env
```
Edit `.env` with your desired provider profile (see profiles above).

### 4. Launch the Server
```bash
python run.py
```
Or directly with Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Access the Web Application
- **Web Dashboard & Interactive Feature Phone Simulator**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 📞 Exotel AgentStream & Live Telephony Setup

To connect live phone calls from an Exotel virtual number to your local server:

### 1. Expose your Local Server with ngrok
Run ngrok in a separate terminal window:
```bash
ngrok http 8000
```
Note the generated public URL (e.g., `https://abc1234.ngrok-free.app`).

### 2. Configure Exotel Voicebot Applet
In the Exotel App Bazaar flow:
1. Drag the **Voicebot / Stream Applet** into your incoming call flow.
2. In the Voicebot Applet configuration:
   - Set Stream URL to: `wss://abc1234.ngrok-free.app/api/v1/telephony/stream`
   - Set Sample Rate to: `8000` (8 kHz 16-bit linear PCM).
   - Set Audio Format to: `audio/x-raw` (Linear PCM).
3. If using dynamic endpoint routing, point the URL endpoint to:
   `https://abc1234.ngrok-free.app/api/v1/telephony/voicebot`
4. Set `.env` variable:
   ```ini
   TELEPHONY_PROVIDER=exotel
   ```
5. When a call arrives, Exotel connects to the WebSocket stream, sends the caller's audio in 3200-byte PCM chunks, receives synthesized speech, and listens for barge-in DTMF digits!

---

## 🚀 Cloud Production Deployment Guide

SwasSetu is architected for cloud deployment on platforms supporting persistent HTTP/WebSocket connections (e.g. Render, Railway, Fly.io, AWS ECS, GCP Cloud Run, or custom VPS).

### Deployment Platform Recommendations

| Hosting Platform | Persistent WebSockets | Long Audio Streams | SSL / WSS Termination | Recommended Run Command |
| :--- | :---: | :---: | :---: | :--- |
| **Render** (Recommended) | Yes | Yes (No timeout) | Automatic SSL (`wss://`) | `python run.py` via `render.yaml` |
| **Railway** | Yes | Yes | Automatic SSL (`wss://`) | `python run.py` via `Procfile` |
| **Fly.io** | Yes | Yes | Automatic SSL (`wss://`) | `fly deploy` via `Dockerfile` |
| **GCP Cloud Run** | Yes | Up to 60 min session | Automatic SSL (`wss://`) | `Dockerfile` (Concurrency: 80) |
| **Docker / VPS** | Yes | Unlimited | Traefik / Nginx reverse proxy | `docker run -p 8000:8000` |

---

### Option A: Deploy to Render with Blueprint (One-Click)

1. Push this repository to GitHub or GitLab.
2. In the [Render Dashboard](https://dashboard.render.com/), click **New +** $\rightarrow$ **Blueprint**.
3. Select this repository. Render automatically reads [`render.yaml`](file:///c:/Users/vikas/Projects/helpLine_mit_india/render.yaml) and provisions:
   - A FastAPI Web Service with automated health checking at `/health`.
   - A managed PostgreSQL database (`swassetu-db`), wiring `DATABASE_URL` automatically.
4. Add your secrets in the Render Environment Dashboard:
   - `EXOTEL_ACCOUNT_SID`
   - `EXOTEL_API_KEY`
   - `EXOTEL_API_TOKEN`
   - `TELEPHONY_WEBHOOK_SECRET`
   - `XAI_API_KEY` (for Grok LLM)
5. Copy your Render service URL (e.g., `https://swassetu-helpline.onrender.com`).
6. In Exotel's Voicebot Applet, set:
   - Dynamic URL: `https://swassetu-helpline.onrender.com/api/v1/telephony/voicebot`
   - Direct Stream: `wss://swassetu-helpline.onrender.com/api/v1/telephony/stream`

---

### Option B: Deploy with Docker Container

1. **Build the container image**:
   ```bash
   docker build -t swassetu-helpline:latest .
   ```

2. **Run container locally or on a cloud VM**:
   ```bash
   docker run -d \
     --name swassetu \
     -p 8000:8000 \
     --env-file .env \
     swassetu-helpline:latest
   ```

3. **Verify container health**:
   ```bash
   curl -f http://localhost:8000/health
   # Returns: {"status":"healthy","service":"rural-medical-helpline",...}
   ```

---

### Option C: Manual Linux / Systemd VPS Deployment

1. **Clone repository and set up environment**:
   ```bash
   git clone https://github.com/your-org/helpLine_mit_india.git
   cd helpLine_mit_india
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Configure production `.env`**:
   ```ini
   ENVIRONMENT=production
   DEBUG=false
   HOST=0.0.0.0
   PORT=8000
   DATABASE_URL=postgresql://user:password@localhost:5432/helpline_db
   TELEPHONY_PROVIDER=exotel
   STT_PROVIDER=speech_recognition
   TTS_PROVIDER=edge_tts
   LLM_PROVIDER=grok
   XAI_API_KEY=your_xai_grok_key_here
   ```

3. **Run with production ASGI server**:
   ```bash
   python run.py
   # Or using gunicorn:
   gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
   ```

---

## 🧪 Automated Testing

SwasSetu includes a comprehensive 83-test automated suite covering:
- Provider selection for LLM (`grok`, `xai`, `openai`, `mock`), STT (`speech_recognition`, `mock`), and TTS (`edge_tts`, `deepgram`, `openai`, `mock`).
- Multilingual speech recognition with Indian locales (`hi-IN`, `mr-IN`, `en-IN`), non-blocking execution, and silence handling.
- Voice Activity Detection (VAD) and `UtteranceDetector` chunk accumulation, pre-roll retention, and trailing silence triggering.
- xAI Grok responses, medical safety guardrails against prescription/diagnostic claims, and Devanagari script enforcement.
- Feature phone DTMF language selection (1/2/3) and turn-by-turn conversation flow.
- Emergency red-flag triage bypass (`Call 108`).
- Exotel bidirectional WebSocket streaming protocol (media, mark, clear, and barge-in events).
- Disconnect handling, health checks (`/health` and `/api/v1/health`), and database persistence with privacy guarantees.

Run the full test suite:
```bash
python -m pytest
```

Run specific test modules:
```bash
# Test telephony & Exotel WebSocket streaming (27 tests)
python -m pytest tests/test_telephony.py -v

# Test AI providers, STT, TTS, and VAD (35 tests)
python -m pytest tests/test_ai_providers.py -v

# Test medical safety, guardrails, & triage (6 tests)
python -m pytest tests/test_medical_safety.py -v
```

---

## 📁 Repository Structure

```text
helpLine_mit_india/
├── app/
│   ├── main.py                     # FastAPI application factory, middleware, CORS
│   ├── core/
│   │   ├── config.py               # Pydantic settings & environment configuration
│   │   ├── logging.py              # Structured, credential-redacted logging
│   │   └── security.py             # Admin Bearer/API key validation, Webhook HMAC
│   ├── database/
│   │   ├── session.py              # SQLAlchemy engine & SQLite/PostgreSQL session maker
│   │   ├── models.py               # Privacy-first models (AnonymousSession)
│   │   └── repository.py           # Data access, analytics queries & retention cleanup
│   ├── triage/
│   │   ├── rules.py                # Clinician-reviewable rule definitions with rationale
│   │   └── engine.py               # Triage classifier, emergency bypass, safety filters
│   ├── services/
│   │   ├── base.py                 # Abstract Base Classes (BaseSTT, BaseTTS, BaseLLM)
│   │   ├── stt.py                  # MockSTT, SpeechRecognitionSTT (Google Speech)
│   │   ├── tts.py                  # OpenAITTSService, DeepgramTTSService, MockTTSService
│   │   └── llm.py                  # GrokLLMService (xAI), OpenAILLMService, MockLLMService
│   ├── engine/
│   │   ├── state_machine.py        # States: LANGUAGE_SELECT -> SYMPTOM -> DURATION -> GUIDANCE
│   │   ├── conversation.py         # Session coordinator, duration limit & DB sync
│   │   └── localization.py         # Voice scripts & disclaimers (English, Hindi, Marathi)
│   ├── telephony/
│   │   ├── adapter.py              # Exotel IVR webhook handler & response builder
│   │   ├── websocket_stream.py     # Live audio WebSocket streaming (8kHz mono PCM)
│   │   ├── audio.py                # PCM/WAV conversion, energy gating, acoustic tone detection
│   │   └── validator.py            # Caller ID anonymization & signature validation
│   ├── api/
│   │   ├── deps.py                 # FastAPI dependencies (get_db, verify_admin)
│   │   └── v1/
│   │       ├── router.py           # Combined v1 API router
│   │       ├── sessions.py         # Session lifecycle & turn endpoints
│   │       ├── telephony.py        # Telephony webhook & WebSocket streaming routes
│   │       └── admin.py            # Analytics, reports & CSV export
│   └── dashboard/
│       ├── static/
│       │   ├── css/style.css       # Retro feature phone keypad styles & analytics layout
│       │   ├── js/dashboard.js     # Analytics charts, report viewer, CSV exporter
│       │   └── js/simulator.js     # Tactile button-phone simulator with audio playback
│       └── templates/
│           └── index.html          # Web Dashboard & Feature Phone Simulator
├── tests/
│   ├── conftest.py                 # Test fixtures & isolated in-memory DB configuration
│   ├── test_ai_providers.py        # Tests for xAI Grok, OpenAI, Deepgram, and TTS error handling
│   ├── test_telephony.py           # Webhook validation, DTMF handling, Exotel AgentStream protocol
│   ├── test_medical_safety.py      # Emergency red flag bypass, disclaimers, prescription blocking
│   ├── test_conversation.py        # State transitions, repeat (0), end (9), silence
│   ├── test_admin_analytics.py     # Auth protection, metrics aggregation, CSV export
│   ├── test_repository.py          # Data persistence, retention cleanup, privacy validation
│   └── test_health.py              # Health check endpoint tests
├── scripts/
│   ├── seed_demo_data.py           # Generates labeled synthetic demo records
│   └── test_call_sim.py            # Interactive CLI feature phone terminal caller
├── .env.example                    # Sample environment configuration template
├── requirements.txt                # Python package dependencies
├── run.py                          # Application launcher
├── Dockerfile                      # Production container image specification
├── .dockerignore                   # Build context exclusions
├── Procfile                        # PaaS web process definition
├── render.yaml                     # Automated Render Blueprint for Web + PostgreSQL
└── README.md                       # Comprehensive documentation
```

---

## 🛡️ Medical Safety & Disclaimer

> **IMPORTANT CLINICAL NOTICE**  
> This software is a technology demonstration for rural healthcare access in India. It is **not** a certified medical device and does **not** provide clinical diagnosis or medication prescriptions. All triage rules are provided for clinician review and must be validated by licensed medical authorities before any production deployment.
