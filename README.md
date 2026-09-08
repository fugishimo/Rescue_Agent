# Rescue Snag Bookings

Rescue Snag Bookings is an AI-native marketplace operations demo for detecting
and recovering at-risk bookings. A randomized 90-second run streams renter and
lister activity, calculates transparent rescue scores, applies deterministic
guardrails, generates intervention-specific SMS copy, and simulates replies and
booking outcomes. Successful interventions update rescued GMV and every action
remains inspectable in an audit ledger.

This repository uses simulated marketplace profiles and demo SMS state only. It
does not contain or claim access to real Snag data, and it never sends a real
text message.

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
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Verify it directly at
`http://localhost:8000/health`.

The demo works without credentials by using intervention-specific fallback
messages. To enable model-generated rescue wording, create a private
`backend/.env` and add `OPENAI_API_KEY`; `OPENAI_MODEL` and
`OPENAI_TIMEOUT_SECONDS` are optional. The backend
loads that file automatically at startup; it never loads `.env.example`.
Existing environment variables take precedence, preserving Render deployment
behavior. Both settings stay on the backend, and the environment file is
ignored by Git. The current provider implementation is OpenAI, isolated behind
a provider-neutral LLM interface. The default model is `gpt-4o-mini`.

```dotenv
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=20
```

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
- `GET /activity` — rescue audit records and coherent monthly impact metrics
- `GET /ops/ai-log` — newest-first AI tool and operational audit entries
- `GET /ops/attention` — active human-review cases
- `POST /ops/attention/{id}/approve` — validate and send an approved AI follow-up
- `POST /ops/attention/{id}/human-rescue` — transfer a case to human ownership
- `POST /autopilot` — enable or disable automatic rescue actions

Qualifying rescue actions contain validated SMS wording and record whether it
came from the configured AI provider or a fallback template. The demo then records a simulated send,
uses the selected profile to produce a reply or no-response outcome, and updates
the booking. No real SMS provider is connected and no message leaves the app.

Interactive API documentation is available at `http://localhost:8000/docs`.

## Start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/dashboard` to use the live Rescue Agent operations
console. Start a simulation to watch booking events, scores, rescue targets, and
autopilot decisions update without refreshing the page. The simulated SMS inbox
shows the latest outreach, recipient, reply, and outcome. Select any booking row
to inspect its score breakdown, agent explanation, and full demo message thread.

Open `http://localhost:3000/activity` to inspect every intervention in the
current run. Each record retains its trigger, score evidence, explanation,
message, simulated response, resulting booking state, and any rescued GMV. The
dashboard and activity page use the same duplicate-safe monthly analytics. A
second AI Agent Log on the page records approved tool calls, denied requests,
and concise operational reasons without exposing hidden reasoning.

Bookings valued at $4,000 or more use a server-enforced review gate. Their first
eligible rescue SMS can still send automatically, but any follow-up is drafted
for review and cannot send until an operator selects **Approve AI**. Selecting
**Human Rescue** blocks all further AI sends for that booking. When follow-up
generation is unavailable, the case is escalated without sending a fallback
follow-up.

## Demo walkthrough

1. Open `http://localhost:3000/dashboard`.
2. Leave Autopilot on and select **Start live simulation**.
3. Watch three booking journeys evolve for approximately 90 seconds.
4. Inspect a booking row as its score and risk reasons change.
5. Follow the simulated rescue SMS, recipient reply, and mixed outcomes.
6. Confirm that a completed rescue increments monthly GMV.
7. Open **Activity log** and select an intervention to inspect its evidence.

Use **Reset** at any point to cancel the current run and restore a clean demo.
After completion, **Run simulation again** starts a newly randomized run.

## Architecture

```text
Next.js dashboard + activity ledger
                 │ polls JSON
                 ▼
FastAPI simulation engine
  ├─ seeded renter/lister profiles
  ├─ deterministic rescue scoring and guardrails
  ├─ provider-neutral AI message generation with safe fallback
  ├─ allowlisted AI tools with server-side write revalidation
  ├─ simulated SMS delivery and profile-driven response outcomes
  └─ shared audit and duplicate-safe GMV analytics
```

FastAPI owns all scoring, intervention, outcome, and analytics logic. The
Next.js client is an operator view over that canonical state, so the dashboard
and activity ledger cannot calculate conflicting results.

## Production environment

Set these deployment variables without committing their values to the repository:

- Render backend: `FRONTEND_ORIGIN` set to the deployed Vercel origin
- Render backend: `OPENAI_API_KEY` for model-generated wording
- Render backend: optional `OPENAI_MODEL` override (defaults to `gpt-4o-mini`)
- Render backend: optional `OPENAI_TIMEOUT_SECONDS` override (defaults to `20`)
- Vercel frontend: `NEXT_PUBLIC_API_URL` set to the deployed Render API origin

The backend always permits `http://localhost:3000` for local development and
adds `FRONTEND_ORIGIN` to its CORS allowlist when configured. The frontend falls
back to `http://localhost:8000` when `NEXT_PUBLIC_API_URL` is absent.

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

Product requirements and simulation behavior are defined in `PRD.md`,
`SIMULATION_PROFILES.md`, and `RESCUE_AGENT_V2_PRD.md`.
