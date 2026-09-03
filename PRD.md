# Rescue Snag Bookings — Product Requirements Document

**Document purpose:** Source of truth for Codex while building the MVP.  
**Product type:** AI-native marketplace operations dashboard  
**Frontend:** Next.js + TypeScript  
**Backend:** FastAPI + Python  
**Primary demo:** 90-second randomized live marketplace simulation  
**Core behavior:** Detect at-risk bookings → calculate rescue score → apply deterministic rescue rules → generate an SMS with an LLM → auto-send it in demo mode → simulate recipient response → update booking outcome and rescued GMV.

---

## 1. Product Summary

**Rescue Snag Bookings** is an autonomous marketplace operations system inspired by the responsibility:

> Rescue bookings in real time.

The system continuously monitors simulated renter and lister activity, identifies bookings that are likely to fail, calculates a transparent rescue score, and automatically intervenes when predefined rules are met.

The product is intentionally designed around one operating principle:

> **Rules decide when and why to act. The LLM decides how to communicate.**

The dashboard is not the brain. It is the operator's window into the rescue system.

### Core demo story

A user opens the dashboard and clicks:

**Start Live Marketplace Simulation**

During the next ~90 seconds:

1. Simulated renters and listers begin generating marketplace activity.
2. Active bookings appear and change state.
3. Rescue scores rise and fall visibly.
4. The Rescue Agent detects a qualifying risk condition.
5. Autopilot applies deterministic rescue rules.
6. The LLM generates a concise SMS.
7. The SMS is automatically "sent" in demo mode.
8. The recipient's simulated phone/inbox receives the message.
9. A simulated response may arrive.
10. The booking may be rescued, remain at risk, or fail.
11. Rescued GMV and other dashboard metrics update in real time.

The demo must feel alive, but it must not falsely imply access to Snag's real production data.

---

## 2. Product Goals

### Primary goals

1. Demonstrate how one operations specialist could monitor more marketplace activity with AI.
2. Show that rescue decisions are governed by explicit operational rules rather than unrestricted LLM judgment.
3. Make real-time booking risk understandable through a visible rescue score and score breakdown.
4. Automatically generate and send context-aware SMS outreach when rescue rules permit.
5. Show measurable business impact through rescued bookings and rescued GMV.
6. Create a polished, reliable 90-second demo that can be shared as part of a job application.

### Secondary goals

- Show renter-side and lister-side rescue workflows.
- Demonstrate auditability through Rescue Agent logs.
- Demonstrate autonomous operation while preserving guardrails.
- Make the system easy to extend later with real SMS, real data, more channels, or smarter models.

---

## 3. Non-Goals for MVP

Do **not** spend MVP time building:

- Authentication
- Real renter/lister accounts
- Real marketplace inventory
- Real payment processing
- Full two-way conversational AI
- Email or voice calling
- Machine-learning-based risk prediction
- A production-grade queueing system
- A large admin panel
- Mobile applications
- Complex role permissions
- Real Snag data integrations
- Real Twilio delivery for the default demo
- A fully persistent production database unless needed for the implementation

The MVP must prioritize the live rescue loop.

---

## 4. Core Product Principles

### 4.1 Deterministic rules own intervention

The rescue engine determines:

- whether a booking is at risk,
- the risk score,
- the reasons for the score,
- whether an outreach action is allowed,
- who should receive the outreach,
- the intervention type.

The LLM must **not** independently decide whether to contact someone.

### 4.2 The LLM owns wording

The LLM receives structured, pre-approved context and generates a concise SMS.

The LLM may choose:

- phrasing,
- tone,
- ordering of facts,
- how to make the next action clear.

The LLM may not:

- invent dates,
- invent pricing,
- invent availability,
- offer discounts unless explicitly permitted,
- change booking status,
- make policy promises,
- make unsupported claims.

### 4.3 The system must be explainable

Every rescue score must expose the factors that produced it.

Every automated action must have a short operational explanation, for example:

> High-intent renter + lister response delay is 3.2× the lister's normal response time. Autopilot triggered a lister reminder.

Do not expose hidden chain-of-thought. Only expose concise, user-facing decision summaries based on explicit rule inputs.

### 4.4 The demo must be credible, not perfect

Not every intervention should succeed.

Possible outcomes:

- Rescued
- No response
- Still at risk
- Lost / failed to rescue

The simulation must produce mixed outcomes.

---

## 5. Primary User

The primary user is an internal marketplace operations specialist.

Their questions are:

- What is happening right now?
- Which bookings are most at risk?
- Why are they at risk?
- What has the Rescue Agent already done?
- Which side of the marketplace was contacted?
- Did the intervention work?
- How much GMV has the Rescue Agent helped recover?

---

## 6. App Information Architecture

MVP should contain **two primary pages**.

### Page A — Dashboard

Recommended route:

`/dashboard`

This is the live operations command center.

### Page B — Rescue Agent Activity

Recommended route:

`/activity`

This is the audit/log view for rescue decisions, generated messages, actions, and outcomes.

Optional detail UI may be implemented as a drawer/modal from the dashboard rather than a third page.

---

# 7. Dashboard Requirements

## 7.1 Hero / centerpiece

The top of the dashboard must immediately communicate the product.

Display:

**Rescue Agent**  
**LIVE** status indicator when simulation is running

Supporting copy such as:

> Monitoring active bookings and rescuing conversion risk automatically.

Primary controls:

- **Start Live Marketplace Simulation**
- **Autopilot ON/OFF**

When simulation is running:

- Start button should become disabled, "Simulation Running", or offer an intentional reset/restart behavior.
- LIVE status should visibly change.
- The interface should begin updating without a page refresh.

### Hero metrics

At minimum:

- Active bookings
- GMV rescued this month
- Bookings rescued this month
- Rescue success rate

Example:

- `14 Active Bookings`
- `$52,840 GMV Rescued`
- `31 Bookings Rescued`
- `68% Rescue Success Rate`

Seeded monthly historical metrics may exist before the demo begins so the dashboard looks like an established operations environment.

The current demo run should increment those values when rescue outcomes occur.

---

## 7.2 Active bookings table

The main table must include:

- Rescue score
- Renter
- Listing
- Booking value
- Current status
- Rescue target tag
- Current/most recent AI action

Example:

| Score | Renter | Listing | Value | Status | Tag | AI Action |
|---|---|---|---:|---|---|---|
| 94 | Maya | Williamsburg Loft | $2,400 | Lister unresponsive | LISTER RESCUE | SMS sent |
| 78 | Alex | SoHo Studio | $3,100 | Checkout abandoned | RENTER RESCUE | SMS sent |
| 55 | Jordan | Chelsea Room | $1,850 | At risk | LISTER RESCUE | Monitoring |
| 22 | Emily | Brooklyn Studio | $2,700 | Healthy | — | None |

### Required behaviors

- Rows update during the simulation.
- Rescue score changes must be visible.
- High-risk bookings should be visually distinguishable from healthy bookings.
- Clicking a row opens booking details.
- Table should be sorted by rescue score descending by default while the simulation is active.

---

## 7.3 Booking detail view

A booking detail view must show:

### Booking details

- Renter
- Lister
- Listing
- Move-in
- Move-out
- Booking value
- Current booking status
- Current rescue score
- Risk level
- Rescue target: renter or lister

### Rescue score breakdown

Show each active factor and point contribution.

Example:

- `+20` Lister unresponsive for >10 simulated minutes
- `+15` Current delay is >2× historical average
- `+15` Renter started checkout
- `+10` Renter viewed listing 5+ times
- `+10` Move-in is within 7 days
- `+10` Booking value exceeds $2,500

Show total and cap at 100.

### Rescue Agent explanation

Example:

> High-intent renter + unusually delayed lister response. Immediate lister reminder triggered.

### SMS section

Show:

- intended recipient
- intervention type
- generated SMS
- send status
- sent timestamp
- simulated response if one exists
- outcome

---

## 7.4 Live Operations feed

A right-side or otherwise prominent live activity feed must update throughout the simulation.

Example events:

- New listing view
- Booking started
- Booking request submitted
- Lister notified
- Rescue score increased
- Booking entered at-risk state
- Rescue Agent triggered
- SMS generated
- SMS sent
- Simulated SMS response
- Availability confirmed
- Booking rescued
- Booking lost

Example:

`6:42:31 PM — Rescue score increased 74 → 89`  
`6:42:32 PM — Rescue Agent triggered LISTER_REMINDER`  
`6:42:33 PM — SMS sent to Sarah`  
`6:42:46 PM — Sarah responded`  
`6:42:52 PM — Booking rescued — +$2,400 GMV`

The feed must be chronological and clearly readable.

---

# 8. Simulated SMS Experience

The default MVP uses **demo SMS mode**.

No external SMS provider is required for the default demo.

## 8.1 SMS behavior

When Autopilot triggers an outreach:

1. Backend creates a rescue action.
2. LLM generates the SMS.
3. Backend records the SMS as sent.
4. Frontend displays the outgoing SMS in the dashboard.
5. A simulated phone/inbox panel shows the message arriving.
6. Based on simulation behavior, the recipient may respond after a delay.
7. Response produces a new event.
8. Booking state is updated.

## 8.2 Phone / inbox panel

The UI should include a simulated SMS experience so viewers can see the intervention.

It should clearly indicate this is a demo/simulation.

Example:

**SMS Demo — Sarah Chen**

Outgoing:

> Hey Sarah — Maya is interested in your Williamsburg loft for Sept 8–Oct 6. Can you confirm those dates are still available?

Incoming after a delay:

> Yes, those dates work.

The phone panel does not need to imitate iOS exactly. It only needs to make the send/receive loop obvious and polished.

## 8.3 Single-outreach MVP

Do not implement open-ended conversational AI.

For the MVP:

- one automated rescue outreach may be sent per rescue trigger,
- a simulated reply may or may not arrive,
- the reply is generated/selected by the simulation engine,
- the booking outcome is then updated.

A second follow-up may be represented as a future extension but is not required.

---

# 9. Rescue Score

## 9.1 Purpose

The rescue score represents how urgently a booking may need intervention.

Range:

`0–100`

Suggested labels:

- 0–49: Healthy / Monitoring
- 50–69: At Risk
- 70–84: High Risk
- 85–100: Critical

The score should change during the simulation as events occur.

## 9.2 Initial scoring factors

Implement simple deterministic scoring.

### Lister response delay

- >5 simulated minutes: `+10`
- >10 simulated minutes: `+20`
- >20 simulated minutes: `+35`
- >30 simulated minutes: `+50`

Only apply the highest matching delay tier, not all tiers cumulatively.

### Historical response anomaly

- current wait >2× lister average response time: `+15`
- current wait >4× lister average response time: `+25`

Only apply the highest matching anomaly tier.

### Renter intent

- 3+ listing views: `+5`
- 5+ listing views: `+10`
- inquiry sent: `+10`
- booking started: `+15`

Viewing tiers should not double-count; use highest matching tier.

### Move-in urgency

- move-in within 14 days: `+5`
- within 7 days: `+10`
- within 3 days: `+15`

Use highest matching tier.

### Booking value

- >$1,500: `+5`
- >$2,500: `+10`
- >$4,000: `+15`

Use highest matching tier.

### Checkout abandonment

If booking has been started but not completed after the defined simulated timeout:

`+30`

### Payment failure

If payment failed:

`+35`

### Availability uncertainty

If renter requested dates but lister availability is unconfirmed after threshold:

`+20`

## 9.3 Score output shape

Backend score calculation should return structured output similar to:

```json
{
  "score": 89,
  "risk_level": "critical",
  "target": "lister",
  "reasons": [
    {
      "code": "LISTER_RESPONSE_DELAY",
      "points": 20,
      "label": "Lister has not responded for more than 10 simulated minutes"
    },
    {
      "code": "RESPONSE_ANOMALY",
      "points": 15,
      "label": "Current delay is more than 2x historical average"
    }
  ],
  "recommended_intervention": "LISTER_REMINDER"
}
```

Cap score at 100.

The same score result powers:

- dashboard display,
- score explanation,
- rescue rules,
- activity logs,
- LLM context.

There must not be separate conflicting scoring logic in frontend and backend.

---

# 10. Rescue Intervention Types

The rules engine must map detected conditions to a known intervention.

Initial intervention types:

### `LISTER_REMINDER`

Used when:

- booking/request exists,
- lister has not responded,
- risk threshold is satisfied.

### `REQUEST_AVAILABILITY`

Used when:

- renter has requested dates,
- availability has not been confirmed,
- risk threshold is satisfied.

### `CHECKOUT_ASSISTANCE`

Used when:

- renter has started checkout,
- checkout is abandoned,
- risk threshold is satisfied.

### `PAYMENT_ASSISTANCE`

Used when:

- a payment failure event occurs,
- outreach is allowed.

### `RENTER_FOLLOW_UP`

Used when:

- lister has confirmed availability,
- renter becomes inactive before completing the booking,
- risk threshold is satisfied.

---

# 11. Autopilot Rules

## 11.1 Toggle behavior

Dashboard contains:

**Autopilot ON/OFF**

When ON:

- Rescue Agent may automatically generate and send demo SMS messages when deterministic rules permit.

When OFF:

- scores continue to update,
- rescue cases continue to be detected,
- no SMS is sent,
- activity feed should indicate that action was held because Autopilot is off.

## 11.2 Threshold behavior

Suggested initial rules:

- score < 50: monitor only
- score 50–69: mark at risk, no message
- score 70–84: send applicable rescue SMS if guardrails pass
- score 85+: urgent rescue SMS if guardrails pass

Certain explicit events may immediately qualify when appropriate, especially payment failure, if total score reaches threshold.

## 11.3 Guardrails

Do not send an automated message when:

- booking is canceled,
- booking is already completed,
- user has opted out,
- a rescue SMS was already sent for the same trigger,
- required context is missing,
- recipient phone contact is unavailable in the simulated data,
- Autopilot is OFF.

For MVP, limit to one automated outreach per rescue trigger.

LLM-generated output must be validated before marking as sent.

---

# 12. LLM Messaging

## 12.1 Inputs

Send only structured context needed for the message.

Example:

```json
{
  "recipient_type": "lister",
  "recipient_name": "Sarah",
  "renter_name": "Maya",
  "listing_name": "Williamsburg Loft",
  "move_in": "September 8",
  "move_out": "October 6",
  "booking_value": 2400,
  "problem": "lister_unresponsive",
  "intervention_type": "LISTER_REMINDER",
  "minutes_waiting": 14,
  "rescue_score": 94
}
```

## 12.2 System constraints

The generation prompt should require:

- concise SMS
- natural tone
- clear next action
- ideally under 240 characters
- no invented information
- no discounts unless supplied
- no promise that a space is available
- no false urgency
- no manipulative language

## 12.3 Failure handling

If the LLM call fails:

- do not crash the simulation,
- log the failure,
- use a safe deterministic fallback template for that intervention type,
- clearly mark the action source as fallback template if shown in logs.

This ensures the demo still works if the API is unavailable.

---

# 13. Rescue Agent Activity Page

Recommended route:

`/activity`

Purpose:

Provide an audit trail of Rescue Agent behavior.

## 13.1 Activity table

Columns:

- Timestamp
- Booking
- Rescue target
- Trigger
- Rescue score
- Intervention
- Message status
- Outcome

Example:

| Time | Booking | Target | Trigger | Score | Action | Outcome |
|---|---|---|---|---:|---|---|
| 6:41:22 | Maya → Williamsburg | Lister | Response delay | 91 | SMS | Rescued |
| 6:41:47 | Alex → SoHo | Renter | Checkout abandoned | 78 | SMS | No response |
| 6:42:03 | Jordan → Chelsea | Renter | Payment failed | 86 | SMS | Pending |

## 13.2 Detail view

Selecting an activity record should show:

- triggering events
- rescue score breakdown
- concise agent explanation
- intervention type
- SMS text
- simulated reply
- resulting booking state
- GMV attribution, if rescued

---

# 14. GMV Rescue Analytics

## 14.1 Definition

For the MVP, a booking is counted as **rescued** when:

1. it entered an at-risk state,
2. Rescue Agent sent an intervention,
3. booking later reaches `completed` within the simulation's rescue window.

The metric should be described as:

**GMV associated with rescued bookings**

or

**GMV rescued**

The product should avoid implying rigorous causal inference.

## 14.2 Required metrics

Dashboard:

- GMV rescued this month
- Bookings rescued this month
- Rescue success rate
- Active rescue cases

Optional if time permits:

- total rescue SMS sent
- renter rescues vs lister rescues
- average rescued booking value

## 14.3 Seeded monthly data

The app may begin with seeded historical monthly totals.

Current demo events add to those totals.

Example:

Before run:

`$48,250 GMV rescued this month`

After $2,400 rescue:

`$50,650 GMV rescued this month`

---

# 15. Simulation Engine

## 15.1 Duration

Target runtime:

**approximately 90 seconds**

The simulation uses compressed marketplace time.

UI should indicate something like:

**Simulation speed: 30×**

Exact multiplier may be adjusted to make the score rules and timing coherent.

## 15.2 Randomized simulation

The simulation should be randomized.

Each run can vary:

- participating renters/listers,
- listings,
- event timing,
- booking values within profile ranges,
- rescue triggers,
- response behavior,
- outcome.

However, pure randomness must not make the demo boring.

### Minimum demo guarantees

Every run should guarantee:

- at least 1 meaningful at-risk booking,
- at least 1 Rescue Agent intervention while Autopilot is ON,
- at least 1 visible outgoing SMS,
- at least 1 score visibly changing over time,
- at least 1 lister-side or renter-side rescue,
- mixed outcomes across the run when enough cases are created.

Preferably, most runs should include both renter and lister rescue types.

## 15.3 Event cadence

Generate meaningful UI events roughly every 4–10 seconds.

Do not flood the feed.

## 15.4 Example event types

- `listing_viewed`
- `inquiry_sent`
- `booking_started`
- `booking_requested`
- `lister_notified`
- `availability_requested`
- `availability_confirmed`
- `checkout_abandoned`
- `payment_failed`
- `renter_inactive`
- `rescue_score_changed`
- `rescue_triggered`
- `sms_generated`
- `sms_sent`
- `sms_received`
- `booking_completed`
- `booking_canceled`
- `rescue_failed`

---

# 16. Simulated Profiles

The simulation must use exactly **11 unique primary profiles**:

- 6 renters
- 5 listers

Their full behavior specification lives in:

`SIMULATION_PROFILES.md`

The PRD should treat that file as the source of truth for profile attributes and behavior probabilities.

Important profile fields include:

### Renter

- id
- name
- typical intent
- responsiveness
- listing view behavior
- checkout abandonment tendency
- payment failure tendency
- move-in urgency tendency
- price sensitivity
- likely SMS response behavior

### Lister

- id
- name
- average response time
- acceptance rate
- calendar/availability reliability
- app engagement
- SMS responsiveness
- likelihood of delayed response
- likelihood of confirming after SMS

---

# 17. Backend Architecture

Use **FastAPI + Python**.

The backend owns all business logic.

## 17.1 Backend responsibilities

- simulation lifecycle
- seeded marketplace state
- randomized events
- booking state transitions
- rescue score calculation
- rescue rule evaluation
- Autopilot state
- intervention creation
- LLM generation
- deterministic SMS fallback
- demo SMS send/receive state
- outcome calculation
- GMV attribution
- activity logs

## 17.2 Suggested modules

Exact file names may vary, but responsibilities should be separated.

Example:

```text
backend/
  app/
    main.py
    models/
      renter.py
      lister.py
      listing.py
      booking.py
      event.py
      rescue_action.py
    services/
      simulation.py
      rescue_scoring.py
      rescue_rules.py
      messaging.py
      sms_demo.py
      analytics.py
    data/
      profiles.py
      seed_data.py
```

Do not over-engineer the module structure if a simpler layout remains readable.

## 17.3 API expectations

Likely endpoints:

- `GET /health`
- `GET /dashboard`
- `GET /bookings`
- `GET /bookings/{id}`
- `GET /activity`
- `POST /simulation/start`
- `POST /simulation/reset`
- `POST /autopilot`
- optional event stream endpoint

Codex may adjust endpoint structure if it remains simple and satisfies requirements.

---

# 18. Frontend Architecture

Use **Next.js + TypeScript**.

Frontend owns presentation and user interaction, not rescue logic.

## 18.1 Frontend responsibilities

- dashboard layout
- start simulation control
- Autopilot control
- metric cards
- active bookings table
- booking detail UI
- live operations feed
- score animation/update
- simulated SMS panel
- activity page
- loading/error/empty states

## 18.2 Live updates

For one-evening MVP, prefer the simplest reliable implementation.

Acceptable:

- client polling every 1–2 seconds

Optional improvement:

- Server-Sent Events

Do not spend significant time on WebSockets unless already trivial.

---

# 19. Core Data Model

## 19.1 Renter

Suggested fields:

```text
id
name
phone_demo_id
intent_level
responsiveness
checkout_abandonment_rate
payment_failure_rate
price_sensitivity
sms_response_rate
```

## 19.2 Lister

Suggested fields:

```text
id
name
phone_demo_id
average_response_minutes
acceptance_rate
availability_reliability
app_engagement
sms_response_rate
```

## 19.3 Listing

Suggested fields:

```text
id
lister_id
name
market
monthly_price
availability_status
```

## 19.4 Booking

Suggested fields:

```text
id
renter_id
lister_id
listing_id
move_in
move_out
booking_value
status
rescue_score
risk_level
rescue_target
created_at
last_activity_at
at_risk_at
rescued_at
completed_at
```

## 19.5 Event

Suggested fields:

```text
id
booking_id
event_type
timestamp
metadata
```

## 19.6 RescueAction

Suggested fields:

```text
id
booking_id
score_at_trigger
intervention_type
target_type
target_id
reason_summary
message_text
message_source
status
sent_at
response_text
response_at
outcome
```

---

# 20. Booking State Model

Suggested statuses:

- `browsing`
- `inquiry`
- `checkout_started`
- `booking_requested`
- `awaiting_lister`
- `awaiting_availability`
- `payment_issue`
- `at_risk`
- `rescued`
- `completed`
- `canceled`
- `lost`

The exact state machine can remain lightweight.

Avoid impossible transitions.

Examples:

`checkout_started → payment_issue → rescued → completed`

`booking_requested → awaiting_lister → at_risk → rescued → completed`

`booking_requested → awaiting_lister → at_risk → lost`

---

# 21. Visual / UX Direction

The product should feel like an internal startup operations tool:

- clean
- dense enough to feel operational
- easy to scan
- not over-designed
- clear status hierarchy
- high-quality dashboard spacing
- strong emphasis on live state

Important UI elements:

- LIVE indicator
- Autopilot status
- dynamic rescue score
- renter/lister rescue tags
- clear timestamps
- visible GMV changes
- polished SMS panel
- activity feed

Avoid unnecessary marketing landing-page sections inside the application.

---

# 22. Demo Behavior / Hero Sequence

The application should support a memorable sequence even though the simulation is randomized.

A representative run:

1. User clicks **Start Live Marketplace Simulation**.
2. LIVE indicator turns on.
3. Existing bookings begin updating.
4. A renter repeatedly views a listing.
5. Booking begins.
6. Request reaches lister.
7. Lister does not respond in expected time.
8. Rescue score moves visibly, e.g. `41 → 57 → 74 → 91`.
9. Feed logs why the score changed.
10. Autopilot sees score above threshold.
11. Rescue Agent creates `LISTER_REMINDER`.
12. LLM generates SMS.
13. Demo SMS panel displays outgoing message.
14. Simulated recipient may reply.
15. If successful, booking becomes rescued/completed.
16. UI displays something like:
    - `BOOKING RESCUED`
    - `+$2,400 GMV`
17. Monthly GMV metric increments.
18. Other concurrent cases may fail or remain at risk.

The experience must remain understandable without narration.

---

# 23. Error Handling

The demo must not collapse because of one service failure.

Required behavior:

### LLM unavailable

Use deterministic fallback SMS template.

### Backend unavailable

Frontend shows clear connection state/error.

### Simulation already running

Do not start duplicate simulation loops.

### User restarts

Reset ephemeral run state cleanly.

### Missing score context

Do not send SMS.

### Invalid LLM message

Reject it and use fallback template.

---

# 24. Acceptance Criteria for MVP

The MVP is complete when all are true:

1. Next.js frontend communicates successfully with FastAPI backend.
2. Dashboard renders seeded marketplace state.
3. Exactly 11 simulation profiles are available from the profile spec.
4. User can start a randomized ~90-second simulation.
5. Marketplace events occur without manual interaction.
6. Active bookings update in real time.
7. Rescue scores visibly change.
8. Score breakdown can be inspected.
9. Renter and lister rescue cases both exist.
10. Autopilot can be toggled.
11. When Autopilot is ON, qualifying rescue rules automatically trigger.
12. Rule engine determines intervention type.
13. LLM generates SMS from structured context.
14. LLM failure falls back safely.
15. Simulated SMS visibly appears in the app.
16. Simulated response may arrive.
17. Booking outcome updates based on simulation.
18. Some rescues fail or receive no response.
19. Successful rescue updates monthly GMV.
20. Activity page logs decisions, actions, explanation, score, and outcome.
21. Application can be run locally from README instructions.
22. No real Snag data is claimed or used.
23. Demo remains functional without Twilio.

---

# 25. Development Rules for Codex

This section is mandatory.

## 25.1 Source of truth

Before writing code, Codex must read:

1. `PRD.md`
2. `SIMULATION_PROFILES.md`

If implementation conflicts with these files, these files win unless the user explicitly approves a change.

## 25.2 Do not build all phases at once

Implementation is divided into gated phases.

At the beginning of each phase:

1. State the phase number and objective.
2. Re-read the relevant PRD sections.
3. Inspect the existing repository before changing code.
4. Make only changes required for the current phase.

At the end of each phase:

1. Run relevant tests/checks.
2. Fix failures caused by the phase.
3. Summarize what was implemented.
4. Show how the user can verify it.
5. Check `git status`.
6. Commit the completed phase with the specified commit style.
7. Push the commit to the configured GitHub remote.
8. Report the commit hash and push result.
9. **STOP.**
10. Ask the user to confirm before beginning the next phase.

**Codex must never automatically begin the next phase.**

If GitHub push cannot be completed because authentication, remote configuration, permissions, or another external dependency is missing:

- do not fake success,
- report the exact blocker,
- keep the local commit intact,
- provide the minimal command/action needed from the user,
- stop and wait.

## 25.3 Commit style

Use:

`phase-N: concise description`

Examples:

- `phase-1: scaffold nextjs and fastapi apps`
- `phase-2: add marketplace models and seed profiles`
- `phase-3: implement randomized simulation engine`
- `phase-4: add rescue scoring and autopilot rules`

Avoid bundling unrelated work into a phase commit.

---

# 26. Gated Implementation Plan

## Phase 1 — Project Scaffold

### Objective

Create the working full-stack foundation.

### Build

- Next.js + TypeScript frontend
- FastAPI + Python backend
- repository structure
- environment variable examples
- backend `/health`
- frontend confirms backend connectivity
- basic README run instructions

### Do not build yet

- profile logic
- simulation
- scoring
- AI
- SMS
- polished dashboard

### Acceptance criteria

- frontend starts locally
- backend starts locally
- frontend can successfully call backend health endpoint
- README contains exact local start commands
- no obvious console/server errors

### Git checkpoint

Commit:

`phase-1: scaffold nextjs and fastapi apps`

Push to GitHub.

Stop and require user confirmation.

---

## Phase 2 — Core Models + 11 Simulation Profiles

### Objective

Represent the marketplace domain and load the exact profiles from `SIMULATION_PROFILES.md`.

### Build

Backend models for:

- renter
- lister
- listing
- booking
- event
- rescue action

Add:

- exactly 6 renter profiles
- exactly 5 lister profiles
- listings tied to listers
- seed booking/history data required for later simulation
- API endpoint(s) to inspect seeded data

### Acceptance criteria

- exactly 11 primary profiles load successfully
- profile fields match the profile document
- listings reference valid listers
- seeded booking references are valid
- API returns structured data
- basic tests validate relationships

### Git checkpoint

Commit:

`phase-2: add marketplace models and simulation profiles`

Push to GitHub.

Stop and require user confirmation.

---

## Phase 3 — Randomized 90-Second Simulation Engine

### Objective

Create the live marketplace behavior.

### Build

- start simulation endpoint
- reset behavior
- run state
- compressed time
- randomized profile selection
- randomized event generation
- valid booking state changes
- representative event types
- guaranteed meaningful rescue opportunity
- mixed outcome setup
- dashboard-accessible current state

Do not implement LLM messaging yet.

### Acceptance criteria

- one user action starts the simulation
- run lasts approximately 90 seconds
- events occur automatically
- every run varies in meaningful ways
- at least one booking becomes at risk
- no duplicate simulation loop can start accidentally
- reset allows a clean second run

### Git checkpoint

Commit:

`phase-3: implement randomized live simulation`

Push to GitHub.

Stop and require user confirmation.

---

## Phase 4 — Rescue Scoring + Autopilot Rules

### Objective

Build the deterministic decision engine.

### Build

- `calculate_rescue_score(...)`
- factorized score reasons
- risk levels
- renter/lister target
- intervention mapping
- thresholds
- Autopilot state
- guardrails
- concise operational explanation

No LLM required yet; actions can be represented as pending rescue actions.

### Acceptance criteria

- one backend source of truth for scores
- scores capped at 100
- score reasons sum correctly
- score changes as events occur
- interventions trigger only when rules allow
- Autopilot OFF prevents sends/actions
- both renter and lister rescue types are testable
- guardrails block invalid actions

### Git checkpoint

Commit:

`phase-4: add rescue scoring and autopilot rules`

Push to GitHub.

Stop and require user confirmation.

---

## Phase 5 — Live Dashboard

### Objective

Make the system visually understandable.

### Build

- Rescue Agent hero
- LIVE indicator
- Start Live Marketplace Simulation button
- Autopilot toggle
- monthly GMV card
- bookings rescued card
- rescue success rate
- active bookings
- active bookings table
- dynamic scores
- renter/lister tags
- live operations feed
- booking detail UI
- rescue score breakdown
- agent explanation

### Acceptance criteria

- user can start demo from dashboard
- dashboard updates without refresh
- scores visibly change
- events appear chronologically
- user can inspect score reasons
- high-risk cases are easy to identify
- renter/lister targets are clearly tagged
- layout works at common desktop widths

### Git checkpoint

Commit:

`phase-5: build live rescue operations dashboard`

Push to GitHub.

Stop and require user confirmation.

---

## Phase 6 — LLM SMS Generation

### Objective

Use an LLM only for message wording.

### Build

- structured rescue context
- prompt constraints
- LLM service
- intervention-specific messaging
- response validation
- deterministic fallback templates
- activity logging of generated message source

### Acceptance criteria

- rules, not LLM, decide whether to act
- LLM receives structured context
- generated SMS is concise
- no unsupported details appear
- failure uses fallback message
- simulation continues if LLM is unavailable

### Git checkpoint

Commit:

`phase-6: add guarded llm rescue messaging`

Push to GitHub.

Stop and require user confirmation.

---

## Phase 7 — Demo SMS Inbox + Simulated Responses

### Objective

Make autonomous intervention visible.

### Build

- simulated SMS phone/inbox panel
- outgoing SMS animation/state
- timestamps
- recipient name
- simulated reply logic based on profiles
- reply event
- resulting booking state update
- one-outreach behavior

### Acceptance criteria

- qualifying rescue visibly sends an SMS
- viewer can see which recipient received it
- simulated reply may arrive
- responses vary based on profile behavior
- not every intervention succeeds
- booking state updates after reply/no reply
- UI clearly indicates SMS is simulated/demo mode

### Git checkpoint

Commit:

`phase-7: add simulated sms rescue loop`

Push to GitHub.

Stop and require user confirmation.

---

## Phase 8 — Rescue Activity + GMV Analytics

### Objective

Show auditability and business impact.

### Build

- `/activity`
- activity table
- action detail
- trigger
- score
- score reasons
- agent explanation
- intervention
- SMS text
- response
- outcome
- rescued GMV updates
- seeded monthly baseline metrics
- success rate calculations

### Acceptance criteria

- all rescue actions are logged
- user can understand why each action occurred
- rescued booking increments GMV once
- failed rescue does not increment GMV
- success rate updates correctly
- activity data stays coherent with dashboard

### Git checkpoint

Commit:

`phase-8: add rescue audit logs and gmv analytics`

Push to GitHub.

Stop and require user confirmation.

---

## Phase 9 — Demo Polish + Final QA

### Objective

Turn the working prototype into a shareable application.

### Build

- polish 90-second pacing
- improve loading/empty/error states
- remove obvious debug UI
- animation restraint
- responsive desktop layout
- realistic seeded monthly data
- clean reset/replay
- README project explanation
- architecture summary
- screenshots/GIF instructions if useful
- final code cleanup
- final automated/manual checks

### Acceptance criteria

A reviewer should be able to:

1. clone repository,
2. follow README,
3. start frontend/backend,
4. open dashboard,
5. click Start Live Marketplace Simulation,
6. understand the product without explanation,
7. see at least one rescue score evolve,
8. see Autopilot trigger,
9. see an SMS send,
10. see mixed rescue outcomes,
11. see GMV update,
12. inspect Rescue Agent logs.

### Git checkpoint

Commit:

`phase-9: polish live booking rescue demo`

Push to GitHub.

Stop and report final commit.

Do not create additional phases without user approval.

---

# 27. Future Extensions — Not MVP

Possible later iterations:

- real Twilio SMS
- inbound Twilio webhooks
- multi-message AI conversations
- email and phone channels
- real-time WebSockets
- Supabase/Postgres persistence
- rescue A/B testing
- learned rescue score model
- intervention effectiveness by profile/segment
- GMV attribution windows
- operator override
- human approval mode
- escalation queues
- real marketplace event integrations
- Slack alerts
- experimentation dashboard

These should not delay the initial MVP.
