# WorkSpot

> **Voice-first livelihood discovery kiosk for low-literacy and rural users.**

WorkSpot is a voice-first, multilingual livelihood assistance kiosk designed to help users discover suitable livelihood opportunities through a simple, guided conversation.

The system is designed around **voice interaction, minimal UI, deterministic interview flows, and privacy-first data handling**, with support for **Bengali, Hindi, and Santali**.

---

## ✨ Overview

WorkSpot guides a user through a short conversational interview to understand:

* Current trade or work experience
* Education and literacy
* Mobility and travel limitations
* Livelihood aspirations
* Available resources and constraints

The collected information is converted into a structured user profile that can be used for livelihood matching and recommendation workflows.

The interface is intentionally designed for environments where users may have:

* Limited digital literacy
* Limited reading ability
* Limited experience with smartphones or computers
* Difficulty using conventional forms
* Noisy surroundings
* Intermittent internet connectivity

### Core principle

> **The server controls the conversation. AI understands and speaks, but does not control the flow.**

This keeps the system predictable, testable, and easier to operate in real-world kiosk environments.

---

# 🎯 Goals

* Build a **voice-first** interaction model
* Minimize text and complex navigation
* Support **Bengali, Hindi, and Santali**
* Provide a tap-based fallback for every important interaction
* Handle noisy environments gracefully
* Avoid storing raw voice recordings
* Work reliably in kiosk environments
* Support intermittent network connectivity
* Produce structured livelihood profiles
* Keep AI interaction deterministic and controlled

---

# 🏗️ System Architecture

```text
┌──────────────────────────── KIOSK BROWSER ────────────────────────────┐
│                                                                      │
│  React + Vite + TypeScript                                           │
│                                                                      │
│  XState Flow Machine ─ Zustand Store ─ i18next                      │
│                                                                      │
│  Microphone → AudioWorklet → VAD → PCM Audio                        │
│                                                                      │
│  Web Audio API ← Cached TTS / Dynamic TTS                            │
│                                                                      │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                    WebSocket + REST
                            │
                            ▼
┌──────────────────────────── NODE SERVER ──────────────────────────────┐
│                                                                      │
│  Fastify + WebSocket                                                 │
│                                                                      │
│  Session Service                                                     │
│          │                                                           │
│          ▼                                                           │
│  Interview Controller ──────────────── Deterministic Flow            │
│          │                                                           │
│          ├── Gemini Service                                           │
│          │      ├── Speech Understanding                              │
│          │      ├── Slot Extraction                                  │
│          │      └── TTS                                               │
│          │                                                           │
│          ├── Zod Slot Validator                                       │
│          │                                                           │
│          ├── TTS Cache                                                │
│          │                                                           │
│          └── SQLite Profile Store                                     │
│                                                                      │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
                       Gemini API
```

---

# 🧰 Tech Stack

## Frontend

* React 18
* Vite
* TypeScript
* Tailwind CSS
* Framer Motion
* XState
* Zustand
* i18next
* Web Audio API
* AudioWorklet

## Backend

* Node.js 20
* Fastify
* WebSocket (`ws`)
* Zod
* better-sqlite3
* Pino

## AI

* Google Gemini
* Gemini TTS
* Gemini multimodal audio understanding
* Structured JSON output
* Server-side API integration

## Development

* pnpm
* TypeScript
* ESLint
* Prettier

---

# 🌐 Supported Languages

| Language | Code  | Script  |
| -------- | ----- | ------- |
| Bengali  | `bn`  | বাংলা   |
| Hindi    | `hi`  | हिन्दी  |
| Santali  | `sat` | ᱥᱟᱱᱛᱟᱲᱤ |

> Santali speech recognition and TTS capabilities should be validated with real speakers during early development.

A fallback based on pre-recorded human audio and tap-based interaction is provided for situations where speech support is unreliable.

---

# 🗂️ Repository Structure

```text
WorkSpot/
│
├── apps/
│   ├── web/
│   │   ├── components/
│   │   ├── screens/
│   │   ├── audio/
│   │   ├── i18n/
│   │   └── ...
│   │
│   └── server/
│       ├── routes/
│       ├── ws/
│       ├── services/
│       │   └── gemini/
│       ├── controller/
│       ├── cache/
│       └── ...
│
├── packages/
│   └── shared/
│       ├── schemas/
│       ├── types/
│       ├── events/
│       ├── enums/
│       └── i18n/
│
├── prompts/
│   ├── bn/
│   ├── hi/
│   └── sat/
│
├── scripts/
│   └── tts/
│
├── SPEC.md
├── DESIGN_TOKENS.md
├── package.json
├── pnpm-workspace.yaml
└── README.md
```

---

# 🧭 User Flow

```text
                 ┌───────────┐
                 │   IDLE    │
                 └─────┬─────┘
                       │
                       ▼
                 ┌───────────┐
                 │ LANGUAGE  │
                 └─────┬─────┘
                       │
                       ▼
              ┌─────────────────┐
              │    INTERVIEW    │
              │                 │
              │ Turn 1          │
              │ Turn 2          │
              │ Turn 3          │
              │ Turn 4          │
              │ Turn 5          │
              └────────┬────────┘
                       │
                       ▼
                 ┌───────────┐
                 │  CONFIRM  │
                 └─────┬─────┘
                       │
                 ┌─────┴─────┐
                 │           │
                 ▼           ▼
             Correct      Confirm
                 │           │
                 ▼           ▼
            Re-ask Slot     DONE
```

---

# 🎙️ Voice Interaction

The voice pipeline is designed around short conversational turns.

```text
Microphone
    ↓
AudioWorklet
    ↓
Voice Activity Detection
    ↓
16 kHz PCM
    ↓
WebSocket
    ↓
Gemini
    ↓
Transcript + Slot Extraction
    ↓
Validation
    ↓
Interview Controller
    ↓
Next Question
```

### Voice fallback strategy

When speech recognition or extraction confidence is low:

1. Ask a simpler follow-up question
2. Retry once
3. Switch to visual/tap-based interaction

This prevents users from becoming trapped in a failed voice interaction loop.

---

# 🔊 Text-to-Speech

WorkSpot uses two TTS strategies.

### Fixed prompts

Questions, confirmations, errors, and other predictable messages are pre-generated and cached.

Benefits:

* Lower latency
* Lower API usage
* Predictable playback
* Better offline resilience

### Dynamic speech

Dynamic content such as the final profile summary is generated at runtime.

The generated speech is optimized for:

* Slow delivery
* Clear pronunciation
* Simple language
* Conversational tone

---

# 🧠 Interview State Machine

The interview flow is deterministic and controlled by the server.

```text
idle
  ↓
language
  ↓
interview
  ├── turn1
  ├── turn2
  ├── turn3
  ├── turn4
  └── turn5
  ↓
confirm
  ↓
correcting
  ↓
done
  ↓
idle
```

Every state supports an inactivity timeout.

When a session expires:

```text
Session
   ↓
Clear temporary state
   ↓
Remove user interaction data
   ↓
Return to idle
```

---

# 👤 Profile Schema

The interview produces a structured livelihood profile.

```text
Profile
│
├── language
│
├── trade
│   ├── category
│   └── detail
│
├── education
│   ├── level
│   └── literate
│
├── mobility
│   ├── mode
│   └── maxKm
│
├── aspiration
│   └── type
│
└── resources
    ├── tools
    ├── land
    └── savings
```

### Supported education levels

* None
* Primary
* Secondary
* Higher Secondary
* Graduate

### Mobility

* Village only
* Block
* District

### Livelihood aspiration

* Wage employment
* Self-employment
* Either

---

# 🔌 API

## Session

### `POST /session`

Creates a new interview session.

---

## TTS

### `GET /tts/:lang/:promptId`

Serves cached audio for a fixed prompt.

### `POST /tts/dynamic`

Generates speech for dynamic content.

---

## WebSocket

### `WS /interview`

### Client → Server

```text
audio_chunk
turn_end
tap_answer
correct_slot
```

### Server → Client

```text
partial_transcript
slot_update
next_prompt
error_fallback
```

---

## Profile

### `POST /profile/confirm`

Finalizes and stores the user's structured profile.

---

# 🎨 UX Principles

WorkSpot follows a deliberately minimal interface philosophy.

### One action per screen

Every screen has a single obvious primary interaction.

### Large touch targets

Minimum target size:

```text
72px
```

### Minimal text

Icons and illustrations communicate meaning wherever possible.

### No unnecessary navigation

The kiosk does not use:

* Complex menus
* Conventional headers
* Long forms
* Dense information layouts
* Unnecessary scrolling

### Motion

Animations are limited to:

* Voice orb states
* Card highlighting
* Screen transitions

Target transition duration:

```text
200–300ms
```

---

# 🖥️ Screens

## Idle

* Ambient animation
* "Touch to begin"
* Rotating language prompts
* Minimal visual elements

---

## Language Selection

Three large language cards:

```text
বাংলা

हिन्दी

ᱥᱟᱱᱛᱟᱲᱤ
```

Selecting a language:

* Changes the interface language
* Loads the appropriate font
* Warms the audio pipeline

---

## Interview

The interview screen contains:

* Voice orb
* Listening state
* Thinking state
* Speaking state
* Live caption
* Visual slot cards
* Tap-to-answer fallback

---

## Confirmation

The final profile is presented using large visual cards.

Each slot can be:

* Confirmed
* Corrected
* Re-asked through voice
* Corrected through tap-based options

---

## Done

The session ends with a simple success state before returning to the idle screen.

---

# 🔐 Privacy

Privacy is a core design requirement.

### Audio

Raw user audio is **not stored**.

Audio is processed for the current interaction and discarded.

### Session data

Temporary session state is cleared after:

* Completion
* Timeout
* Reset

### Stored data

Only the anonymized final structured profile is retained.

### Consent

The microphone is activated only after explicit voice consent.

---

# 📡 Offline Resilience

A service worker caches:

* Application shell
* Fonts
* Static assets
* Fixed TTS clips
* Required UI resources

If the network becomes unavailable, the kiosk can fall back to:

```text
Tap-based interaction
        +
Cached audio
        +
Cached application
```

---

# 🔊 Noisy Environment Handling

The system is designed for environments where background noise may affect speech recognition.

Mitigation strategies include:

* Directional microphone
* Voice Activity Detection
* Noise-level estimation
* Short questions
* Longer silence threshold
* Tap-based fallback

The system can recommend switching to tap mode when the environment is too noisy.

---

# ⚡ Performance Targets

| Metric                  |      Target |
| ----------------------- | ----------: |
| Speech response latency | < 2 seconds |
| Minimum touch target    |        72px |
| UI transition           |   200–300ms |
| Raw audio retention     |           0 |
| Idle session reset      |   Automatic |
| Fixed TTS               |      Cached |

---

# 🛠️ Development Roadmap

## Phase 0 — Foundation

* Monorepo scaffold
* Shared types
* Linting
* Development environment

**Done when:**

```text
pnpm dev
```

runs both web and server.

---

## Phase 1 — Design System

* Design tokens
* Layout shell
* Three locales
* Local fonts
* Language switching

**Done when:**

Changing the language updates the entire interface.

---

## Phase 2 — Mock Interview

* XState flow
* Mock voice interaction
* Tap-based answers
* Complete interview flow

**Done when:**

```text
Idle → Language → Interview → Confirm → Done
```

works entirely without AI.

---

## Phase 3 — TTS

* TTS service
* TTS cache generation
* Audio player
* Voice orb states

**Done when:**

Every fixed prompt can be played in all supported languages.

---

## Phase 4 — Voice Input

* Microphone capture
* AudioWorklet
* VAD
* WebSocket audio streaming
* Gemini integration
* Transcription
* Slot extraction
* Live captions

**Done when:**

A spoken answer successfully fills the corresponding profile slot.

---

## Phase 5 — Confirmation

* Profile summary
* Dynamic TTS
* Per-slot correction
* Voice correction
* Tap correction

**Done when:**

Users can change any incorrect answer through voice or touch.

---

## Phase 6 — Kiosk Hardening

* Kiosk mode
* Idle reset
* Offline cache
* Voice consent
* Crash recovery
* Session cleanup

**Done when:**

The application completes 100 reset cycles without a memory leak or crash.

---

## Phase 7 — Field Testing

* Real-user testing
* Prompt tuning
* Accent testing
* VAD tuning
* Noise testing
* Santali validation

**Target:**

> Task completion above 90% without assistance.

---

# ⚠️ Risks & Mitigations

| Risk                   | Mitigation                                     |
| ---------------------- | ---------------------------------------------- |
| Santali speech quality | Early validation with native speakers          |
| Dialect variation      | Real-world speech samples and prompt iteration |
| Noisy environment      | Directional microphone + VAD + tap fallback    |
| API latency            | Cached TTS + efficient voice pipeline          |
| API cost               | Pre-generated fixed prompts                    |
| Network failure        | Service worker + cached assets                 |
| User trust             | Explicit microphone consent                    |
| Privacy                | No raw audio storage                           |
| Low literacy           | Voice-first + visual interaction               |
| Recognition failure    | Simplified retry + tap fallback                |

---

# 🧪 Testing Strategy

Testing should cover four major layers.

### Unit Testing

* Slot validation
* State transitions
* Event validation
* Profile transformations
* Session expiration

### Integration Testing

* WebSocket communication
* Gemini service
* TTS service
* SQLite persistence
* Session lifecycle

### UI Testing

* Language selection
* Interview flow
* Confirmation
* Slot correction
* Reset behaviour

### Field Testing

* Background noise
* Different accents
* Different speaking speeds
* Low-literacy users
* Touch-only interaction
* Intermittent connectivity
* Real kiosk hardware

---

# 🚀 Development Philosophy

WorkSpot follows a **mock-first, AI-last** development strategy.

The complete user experience should work without AI before integrating speech recognition or generative services.

```text
UI
 ↓
State Machine
 ↓
Mock Voice
 ↓
TTS
 ↓
Microphone
 ↓
AI Extraction
 ↓
Field Testing
```

This prevents AI availability or model behaviour from becoming a dependency during early development.

---

# 📋 Project Principles

1. **Voice first**
2. **Touch always available**
3. **AI does not control the flow**
4. **Minimal text**
5. **Large visual affordances**
6. **No raw audio storage**
7. **Offline where possible**
8. **Fail gracefully**
9. **Test with real users**
10. **Design for the kiosk, not the desktop**

---

# 📄 Project Documentation

Additional project specifications are maintained in:

```text
SPEC.md
DESIGN_TOKENS.md
```

These documents define the functional requirements and visual system used throughout development.

---

# 🤝 Contributing

Contributions should follow the project's architectural and UX principles.

Before implementing a feature:

1. Check the existing specification.
2. Keep the interview flow deterministic.
3. Keep AI responsibilities isolated.
4. Provide a tap-based fallback where applicable.
5. Validate user-facing changes against kiosk constraints.
6. Add or update tests for behavioural changes.

---

# 📜 License

License information will be added to this repository.

---

<p align="center">
  <strong>WorkSpot</strong><br>
  Voice-first livelihood assistance for everyone.
</p>
