# Rescue Snag Bookings

Rescue Snag Bookings is an AI-native marketplace operations dashboard. The
project contains a Next.js frontend and a FastAPI backend with a basic health
connection between them.

## Prerequisites

- Node.js 20.9 or newer
- npm
- Python 3.12

## Start the backend

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Verify it directly at
`http://localhost:8000/health`.

## Inspect backend APIs

With the backend running, seeded data and live engine state are available from:

- `GET /profiles` — six renters and five listers
- `GET /listings` — seeded inventory tied to listers
- `GET /bookings` — valid seeded booking journeys
- `GET /events` — booking event history
- `GET /marketplace/seed` — the complete seed payload
- `GET /simulation` — current live run state
- `POST /simulation/start` — start a randomized 90-second run
- `POST /simulation/reset` — stop and clear the current run
- `GET /dashboard` — polling-friendly simulation snapshot
- `POST /autopilot` — enable or disable automatic rescue actions

Phase 4 rescue actions remain `pending`; message generation and SMS delivery are
implemented in later gated phases.

Interactive API documentation is available at `http://localhost:8000/docs`.

## Start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000/dashboard` to use the live Rescue Agent operations
console. Start a simulation to watch booking events, scores, rescue targets, and
autopilot decisions update without refreshing the page. Select any booking row
to inspect its score breakdown and agent explanation.

## Run checks

Backend:

```bash
cd backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Repository structure

```text
backend/   FastAPI application and backend tests
frontend/  Next.js App Router application
```

Product requirements and simulation behavior are defined in `PRD.md` and
`SIMULATION_PROFILES.md`.
