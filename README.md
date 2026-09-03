# Rescue Snag Bookings

Rescue Snag Bookings is an AI-native marketplace operations dashboard. This
Phase 1 scaffold contains a Next.js frontend and a FastAPI backend with a basic
health connection between them.

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

## Start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. The page reports **Backend connected** when the
FastAPI health endpoint is available.

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
