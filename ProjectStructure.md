# WorkSpot — Project Structure & UI Customization Guide

## 1. Project Overview

**WorkSpot** is an AI-powered, multilingual voice assistant and livelihood platform designed for informal economy workers. It provides multilingual conversational onboarding, voice-driven skills profiling, and smart matching with government schemes (e.g., PM-AJAY, NSFDC) and skill training courses (e.g., Skill India Digital Hub).

The repository is built as a polyglot monorepo featuring:
- **Frontend (Web/Kiosk UI)**: React + TypeScript + Vite (`apps/web`)
- **Node.js Gateway / Server**: Fastify + WebSocket + Zod + MongoDB adapter (`apps/server`)
- **Shared TS Package**: Types, schemas, state machine logic (`packages/shared`)
- **Python Telephony & AI Engine**: FastAPI, FreeSWITCH/Kamailio integration, Whisper ASR, Indic TTS, vLLM / LLM orchestrator, MongoDB vector embeddings (`api/`, `services/`, `schemas/`, `config/`)

---

## 2. Directory Tree Structure

```text
WorkSpot/
├── Dockerfile.app                  # Production Dockerfile for Node/Web services
├── Dockerfile.asr                  # Dockerfile for Whisper ASR container
├── Dockerfile.tts                  # Dockerfile for Indic TTS container
├── docker-compose.yml              # Multi-container orchestration (Mongo, Redis, FreeSWITCH, Services)
├── package.json                    # Root package.json (pnpm workspace)
├── pnpm-lock.yaml                  # Workspace lockfile
├── pnpm-workspace.yaml             # pnpm workspace definition (apps/*, packages/*)
├── requirements.txt                # Python backend dependencies
├── tsconfig.json                   # Root TypeScript configuration
├── README.md                       # High-level architecture and quickstart guide
├── ProjectStructure.md             # This comprehensive architecture and UI guide
│
├── apps/
│   ├── web/                        # React Frontend (Kiosk & Web UI)
│   │   ├── index.html              # HTML entry point (title, viewport, meta tags)
│   │   ├── package.json            # Web app dependencies (React, Lucide icons, Vite)
│   │   ├── tsconfig.json           # Frontend TypeScript configuration
│   │   ├── vite.config.ts          # Vite build, server, and dev configuration
│   │   └── src/
│   │       ├── main.tsx            # Main React application, screen router, state & components
│   │       ├── styles.css          # Core CSS stylesheet (fonts, variables, layouts, themes)
│   │       ├── languageConfig.ts   # Supported languages, ASR/TTS language codes, speech synthesis
│   │       ├── localeRuntime.ts    # Runtime localization resolver and UI labels
│   │       ├── locales/            # Translation JSON dictionaries (15 Indian languages)
│   │       │   ├── en.json         # English
│   │       │   ├── hi.json         # Hindi
│   │       │   ├── bn.json         # Bengali
│   │       │   ├── mr.json         # Marathi
│   │       │   ├── ta.json         # Tamil
│   │       │   ├── te.json         # Telugu
│   │       │   ├── kn.json         # Kannada
│   │       │   ├── ml.json         # Malayalam
│   │       │   ├── gu.json         # Gujarati
│   │       │   ├── pa.json         # Punjabi
│   │       │   ├── or.json         # Odia
│   │       │   ├── as.json         # Assamese
│   │       │   ├── bho.json        # Bhojpuri
│   │       │   ├── mai.json        # Maithili
│   │       │   └── ur.json         # Urdu
│   │       └── api/
│   │           └── client.ts       # Frontend REST & WebSocket API communication client
│   │
│   └── server/                     # Node.js API Gateway (Fastify)
│       ├── package.json            # Server dependencies (Fastify, ws, mongodb, zod)
│       ├── tsconfig.json           # Server TypeScript config
│       └── src/
│           ├── index.ts            # Fastify server entry point, REST routes & WS handlers
│           ├── store.ts            # Data store abstraction (MongoDB & In-memory fallback)
│           └── index.test.ts       # Server unit tests
│
├── packages/
│   └── shared/                     # Shared TypeScript Library
│       ├── package.json
│       ├── tsconfig.json
│       └── src/
│           ├── index.ts            # Profile models, Recommendation schemas, State Machine
│           └── index.test.ts       # State machine and validation tests
│
├── api/                            # Python FastAPI Telephony & AI Endpoints
│   ├── __init__.py
│   ├── server.py                   # FastAPI app setup, CORS, lifespan handlers
│   ├── routes_client.py            # Client-facing REST endpoints (profile, recommendations)
│   ├── routes_telephony_ws.py      # Telephony WebSocket streaming (audio in/out)
│   └── routes_mock.py              # Mock routes for development and simulation
│
├── services/                       # Python AI & Processing Microservices
│   ├── asr/                        # Automatic Speech Recognition (ASR)
│   │   ├── __init__.py
│   │   └── whisper_worker.py       # Whisper / IndicConformer speech-to-text pipeline
│   ├── audio/                      # Audio Processing
│   │   ├── __init__.py
│   │   ├── resampler.py            # Audio rate conversions (e.g. 8kHz telephony <-> 16kHz ASR)
│   │   └── vad_filter.py           # Voice Activity Detection (Silero VAD)
│   ├── db/                         # MongoDB database layer
│   │   ├── __init__.py
│   │   ├── mongo_client.py         # Motor async MongoDB client connection
│   │   ├── indexes.py              # MongoDB index management (geospatial, vector, compound)
│   │   └── repositories/           # Repository pattern data access
│   │       ├── base_repository.py
│   │       ├── beneficiary_repo.py
│   │       ├── course_repo.py
│   │       ├── district_repo.py
│   │       ├── dpiu_repo.py
│   │       └── session_repo.py
│   ├── llm/                        # Large Language Model Services
│   │   ├── __init__.py
│   │   ├── prompt_templates.py     # System prompts for extraction, dialog, recommendations
│   │   └── vllm_client.py          # vLLM / OpenAI-compatible client integration
│   ├── orchestrator/               # Conversational State Orchestration
│   │   ├── __init__.py
│   │   ├── state_machine.py        # Dialogue state transitions and logic
│   │   ├── dialogue_synthesizer.py # Dynamic response generator
│   │   └── session_cache.py        # Redis / in-memory conversational session cache
│   ├── recommendation/             # Vector Embeddings & Opportunity Matching
│   │   ├── __init__.py
│   │   ├── embedder.py             # SentenceTransformer embeddings generator
│   │   └── mongo_service.py        # MongoDB Atlas Vector Search queries
│   └── tts/                        # Text-to-Speech (TTS)
│       ├── __init__.py
│       ├── chunker.py              # Sentence segmenter for streaming TTS
│       └── indic_tts_worker.py     # Indic TTS synthesis worker
│
├── schemas/                        # Pydantic Schemas (Python)
│   ├── __init__.py
│   ├── beneficiary.py              # Beneficiary model & demographics
│   ├── beneficiary_profile.py      # Skills, craft, aspirations schema
│   ├── call_session.py             # Telephony call record schema
│   ├── course.py                   # Skill courses & NSQF training schema
│   ├── dpiu_application.py         # PM-AJAY capital grants & DPIU application schema
│   ├── lgd_district.py             # Local Government Directory (LGD) district data
│   ├── session.py                  # Web/Kiosk interactive session schema
│   └── websocket_events.py         # Telephony & client WS event contracts
│
├── config/                         # Infrastructure & Telephony Configurations
│   ├── config.py                   # Pydantic settings & environment variables
│   ├── freeswitch_dialplan.xml     # FreeSWITCH SIP dialplan
│   ├── freeswitch_vars.xml         # FreeSWITCH parameters
│   └── kamailio.cfg                # Kamailio SIP proxy configuration
│
├── scripts/                        # Database & Seeding Scripts
│   ├── init-mongo.js               # MongoDB initial database creation & indexing
│   ├── requirements.txt            # Script dependencies
│   └── seed_mock_data.py           # Seed sample beneficiaries, courses, and opportunities
│
├── static/                         # Static Assets
│   └── audio/
│       └── mock_greeting.wav       # Sample audio prompt for testing telephony
│
└── tests/                          # Backend Unit & Integration Tests
    ├── test_audio_pipeline.py
    ├── test_client_endpoints.py
    ├── test_enterprise_aspirations.py
    ├── test_mongo_vector_search.py
    └── test_state_machine.py
```

---

## 3. UI Customization Guide: CSS, Fonts, Themes & Features

All frontend user interface elements, styling, fonts, and interactive features are located under **[`apps/web/`](file:///home/aritra/Code/Github/WorkSpot/apps/web)**. Below is a detailed breakdown of where each aspect can be modified:

### 3.1. Fonts & Typography

| What to Change | File Location | How to Change |
|---|---|---|
| **Google Fonts Imports** | [`apps/web/src/styles.css`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/styles.css) (Line 1) | Modify the `@import url('https://fonts.googleapis.com/...');` rule. Currently loaded: `DM Sans`, `DM Mono`, and `Fraunces`. |
| **Primary Font Family** | [`apps/web/src/styles.css`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/styles.css) (Line 4) | Update `font-family: 'DM Sans', sans-serif;` inside the `:root` selector. |
| **Monospace / Label Font** | [`apps/web/src/styles.css`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/styles.css) (Lines 69–71, 74–80) | Update `font-family: 'DM Mono';` on `.logo small`, `.eyebrow`, `.type-label`, badges, and code tags. |
| **Headings & Display Typography** | [`apps/web/src/styles.css`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/styles.css) (Lines 82–93) | Customize `h1`, `h2`, `h3`, `p`, letter-spacing, and line-heights. |
| **HTML Head & External Font Links** | [`apps/web/index.html`](file:///home/aritra/Code/Github/WorkSpot/apps/web/index.html) (Lines 3–8) | Add `<link rel="preconnect">` or `<link rel="stylesheet">` tags for external web fonts or local font files. |

---

### 3.2. Color Palette, Themes & Design Tokens

Theme colors and global tokens are defined in `:root` in [`apps/web/src/styles.css`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/styles.css) (Lines 3–17):

```css
:root {
  font-family: 'DM Sans', sans-serif;
  color: #e9f0f5;             /* Primary text color */
  background: #07131f;        /* Global background color */
  font-synthesis: none;

  /* Color Tokens */
  --ink: #07131f;             /* Dark contrast background / deep brand color */
  --muted: #7f94a4;           /* Subdued text and border tint */
  --soft: #f5f5f1;            /* Off-white light surface */
  --surface: #fffefa;         /* Pure card/container light surface */
  --mint: #9be5ca;            /* Primary brand accent (mint green) */
  --blue: #63b2f1;            /* Secondary action / link accent (soft blue) */
  --line: #dfe4e2;            /* Light divider line color */
  --navy-line: #1d3547;       /* Dark theme border and container outline */
  --purple: #ab9df6;          /* Tertiary highlight / badge accent */
}
```

*To create a light mode or change the color branding:*
1. Adjust the CSS variables in [`apps/web/src/styles.css`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/styles.css).
2. Change the browser theme bar color in [`apps/web/index.html`](file:///home/aritra/Code/Github/WorkSpot/apps/web/index.html) (Line 6: `<meta name="theme-color" content="#0d1b2a" />`).

---

### 3.3. UI Component Styles

All component classes are in [`apps/web/src/styles.css`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/styles.css):

- **Buttons & Action Controls** (Lines 95–180): `.primary-button`, `.secondary-button`, `.ghost-button`, `.listen-button`, `.mic-button`. Controls padding, border-radius, shadows, hover, and disabled states.
- **Header & Navigation Bar** (Lines 41–73, 200–260): `.logo`, `.top-nav`, `.nav-tab`, active indicator styling.
- **Cards & Banners**: `.kiosk-card`, `.opportunity-card`, `.metric-card`, `.profile-pill`, `.hero-banner`.
- **Audio & Voice Recording UI**: `.recording-panel`, `.pulsing-indicator`, `.audio-player`, waveform styling.
- **Advisor / AI Chat Interface**: Chat bubbles (`.chat-bubble-ai`, `.chat-bubble-user`), input bar, and suggestion chips.
- **Responsive Layout & Breakpoints**: Media queries located at the bottom of [`styles.css`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/styles.css) for mobile, tablet, and kiosk displays.

---

### 3.4. Features & Logic Customization

| Feature | Primary File | Description |
|---|---|---|
| **Screens & Navigation Flow** | [`apps/web/src/main.tsx`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/main.tsx) | Screen router enum (`Screen`: `welcome`, `login`, `language`, `workIntro`, `recording`, `preview`, `interview`, `home`, `profile`, `opportunities`, `advisor`, etc.) and render logic. |
| **Voice Recording & Web Speech** | [`apps/web/src/main.tsx`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/main.tsx) | `mediaRecorderRef`, `MediaRecorder` audio capture, fallback Web Speech API (`SpeechRecognition`). |
| **Text-to-Speech (TTS) Engine** | [`apps/web/src/languageConfig.ts`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/languageConfig.ts) | `speakText()` using the browser's `SpeechSynthesisUtterance`. Voice locale mapping (`asrCode`, `ttsCode`). |
| **Languages Supported** | [`apps/web/src/languageConfig.ts`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/languageConfig.ts) | `supportedLanguages` list: add or modify language codes (e.g. Hindi, Bengali, Tamil, Telugu, Bhojpuri, etc.). |
| **Localized UI Text & Translations** | [`apps/web/src/locales/*.json`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/locales/) & [`localeRuntime.ts`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/localeRuntime.ts) | JSON dictionaries for all 15 supported languages. Edit these to change text labels, button copies, and prompts. |
| **Interview Questions** | [`apps/web/src/main.tsx`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/main.tsx) | `questions` object defines the questions asked during onboarding. |
| **Opportunities & Matching** | [`apps/web/src/main.tsx`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/main.tsx) & [`packages/shared/src/index.ts`](file:///home/aritra/Code/Github/WorkSpot/packages/shared/src/index.ts) | Default cards (`initialOpportunities`) and `Recommendation` type definitions. |
| **API Backend Client** | [`apps/web/src/api/client.ts`](file:///home/aritra/Code/Github/WorkSpot/apps/web/src/api/client.ts) | REST endpoints for audio upload, profile fetching, dynamic advice, and telephony sessions. Configure `VITE_API_URL` in `.env` or Vite config. |
| **Vite Dev Server & Proxy** | [`apps/web/vite.config.ts`](file:///home/aritra/Code/Github/WorkSpot/apps/web/vite.config.ts) | Vite port configuration, plugins, and proxy rules for backend routing. |
