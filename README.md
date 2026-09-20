# WorkSpot

WorkSpot is an AI-powered, multilingual voice assistant for livelihood mapping and skill recommendations.

This repository is a working MVP foundation based on the architecture brief:

- `apps/web` — React + Vite kiosk experience with a deterministic interview flow, multilingual entry point, consent gate, tap/text fallback, recommendations, and offline-mode indicator.
- `apps/server` — Node.js + Fastify API with REST, WebSocket, Zod validation, a MongoDB repository adapter, and an in-memory fallback for local development.
- `packages/shared` — shared profile/session types, schemas, language definitions, and the interview state machine.

## Run locally

```bash
pnpm install
pnpm dev
```

Open `http://localhost:5173`. The API runs at `http://localhost:4000`.

To use MongoDB instead of the in-memory store:

```bash
MONGODB_URI=mongodb://127.0.0.1:27017 MONGODB_DB=workspot pnpm --filter @workspot/server dev
```

## Next production integrations

The seams are ready for Bhashini/IndicConformer ASR, Indic-capable LLM extraction, Indic TTS, Redis/BullMQ workers, Atlas Vector Search, and authenticated external ingestion from PM-AJAY, SIDH, NSFDC, and district demand data. Exact DPDP requirements must be validated before deployment.
