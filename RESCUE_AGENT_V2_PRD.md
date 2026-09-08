# Rescue Snag Bookings — V2 PRD: Rescue Agent Ops Copilot

## 0. Purpose
This document modifies the existing Rescue Snag Bookings application. Do not rebuild V1. Preserve the existing Next.js + TypeScript frontend, FastAPI + Python backend, randomized 90-second simulation, deterministic rescue scoring, Autopilot, simulated SMS, activity ledger, GMV metrics, Vercel deployment, and Render deployment unless this V2 PRD explicitly changes behavior.

V2 goal: turn Rescue Agent into a constrained marketplace operations copilot that can inspect the full simulated marketplace, select from approved rescue interventions, generate/send SMS, summarize operations, surface high-value cases, escalate exceptions, and take approved actions from an operations-only chat.

Core principle:

**Rules define authority. Rescue Agent operates inside those rules.**

---

## 1. Product behavior

Rescue Agent may:
- inspect whole-marketplace state;
- review rescue-eligible bookings;
- select among backend-approved intervention types;
- generate concise SMS;
- request approved backend actions;
- summarize marketplace activity and prior interventions;
- identify high-value cases;
- escalate exceptions;
- draft follow-up responses;
- answer marketplace-operations questions;
- take approved actions through tool calls.

Rescue Agent may not:
- change rescue scores or scoring thresholds;
- change booking value;
- mark bookings rescued/completed/lost;
- bypass Autopilot or backend policy;
- invent availability, dates, pricing, discounts, or other marketplace facts;
- directly mutate state outside registered backend tools.

Backend remains source of truth.

Execution pattern:

Marketplace state → deterministic rescue score/policy → allowed action set → Rescue Agent → backend tool request → server-side revalidation → execute/deny → audit log.

---

## 2. Branding and navigation

Visible branding: **Rescue Agent**. Do not expose provider branding in prominent product UI.

Primary routes:
- `/dashboard` — Live Console
- `/activity` — Activity Ledger
- `/ops` — Rescue Agent Ops Brief

Add an **Ops Brief** button beside the existing Activity button on the dashboard.

---

## 3. High-value policy

High-value means **booking value >= $4,000**.

### First outbound message
For all eligible bookings, including high-value:
- Rescue Agent may auto-send the first rescue SMS if Autopilot is ON and all backend guardrails pass.

### Normal-value bookings (< $4,000)
- Rescue Agent may continue approved follow-up messaging autonomously.
- Every send must pass backend guardrails.
- Safety cap for V2 MVP: maximum 2 AI-authored outbound rescue messages per booking unless the operator explicitly acts from the Ops interface.

### High-value bookings (>= $4,000)
- first outbound rescue SMS may auto-send;
- every subsequent outbound response/action requires human approval;
- Rescue Agent must pre-draft the next response;
- case appears in **Needs Immediate Attention**;
- Rescue Agent cannot send the follow-up until the human chooses **Approve AI**;
- choosing **Human Rescue** transfers ownership to the operator and stops autonomous Rescue Agent messaging for that case.

No Close/Ignore action exists. Attention issues remain active until resolved by marketplace state or human/Rescue Agent action.

---

## 4. Exception escalation

Rescue Agent may escalate before the first SMS if:
- required context is missing;
- marketplace data conflicts;
- case does not fit an approved intervention type;
- action would violate messaging policy;
- booking state is ambiguous;
- recipient explicitly asks for a human;
- Rescue Agent cannot determine a safe approved action;
- repeated model/tool failure prevents safe automation.

These cases also appear in **Needs Immediate Attention**.

---

## 5. Rescue Agent Ops Brief page

Route: `/ops`

Page hierarchy:

1. **Needs Immediate Attention**
2. **Rescue Agent Ops Brief**
3. **What Rescue Agent Handled**
4. **High-Value Watch**
5. **Ask Rescue Agent**

This page must feel like an operations command center, not a generic chatbot.

### 5.1 Needs Immediate Attention
Each card shows:
- booking value;
- HIGH VALUE badge when applicable;
- renter;
- lister;
- listing;
- booking status;
- rescue score;
- escalation reason;
- first automated SMS;
- latest reply if present;
- Rescue Agent’s drafted next response/action;
- concise AI recommendation.

Buttons:
- **Approve AI**
- **Human Rescue**

Approve AI:
- server re-validates policy;
- sends the drafted response;
- logs human approval.

Human Rescue:
- marks case human-owned;
- blocks further autonomous Rescue Agent sends;
- keeps case active;
- optionally provides a human message field.

### 5.2 Rescue Agent Ops Brief
At the end of each 90-second run, generate one structured summary containing:
- journeys monitored;
- interventions sent;
- bookings rescued;
- GMV rescued this run;
- high-value cases;
- unresolved cases;
- needs-attention count;
- concise natural-language summary.

During a run, do not continuously regenerate the full summary. Mid-run brief updates are only for high-value/urgent events.

Example:
- `$4,650 high-value booking entered critical risk`
- `First automated outreach sent`
- `High-value recipient replied — approval required`

### 5.3 What Rescue Agent Handled
Operator-friendly list of meaningful Rescue Agent actions, e.g.:
- Reviewed 3 booking journeys
- Sent first rescue SMS to Sarah
- Sent payment assistance to Jordan
- Flagged Maya’s $4,650 booking
- Drafted high-value follow-up
- Escalated case for human review
- Paused Autopilot from operator request

### 5.4 High-Value Watch
Show current/recent bookings >= $4,000 with:
- booking;
- value;
- score;
- status;
- intervention state;
- human-review state.

### 5.5 Ask Rescue Agent
Operations-only chat. Supported examples:
- “What needs my attention right now?”
- “What did you do during this run?”
- “Show me all high-value cases.”
- “Which booking is most at risk?”
- “Why did you contact Sarah?”
- “Which lister caused the most rescue activity?”
- “What messages did you send?”
- “Pause Autopilot.”
- “Resume Autopilot.”
- “Handle anything you safely can.”

Out-of-domain response:
> I can help with Rescue Agent marketplace operations, booking risk, interventions, and current simulation activity.

---

## 6. Rescue Agent tool interface

Approved tools:
- `get_marketplace_summary()`
- `get_active_bookings()`
- `get_at_risk_bookings()`
- `get_booking_details(booking_id)`
- `get_recent_rescue_actions()`
- `get_high_value_cases()`
- `get_lister_performance()`
- `get_renter_history(renter_id)`
- `get_lister_history(lister_id)`
- `get_attention_cases()`
- `send_rescue_sms(booking_id, intervention_type, message)`
- `escalate_to_operator(booking_id, reason)`
- `set_autopilot(enabled)`

Rescue Agent must not have tools such as:
- `change_rescue_score`
- `change_booking_value`
- `mark_booking_completed`
- `mark_booking_rescued`
- `mark_booking_lost`
- `delete_booking`
- `edit_marketplace_event`

All write tools re-check policy server-side. A Rescue Agent tool request is never itself authorization.

---

## 7. Intervention policy

Existing deterministic rescue rules provide an allowed action set.

Example:
```json
{
  "booking_id": "booking_123",
  "score": 87,
  "risk_level": "critical",
  "allowed_interventions": [
    "LISTER_REMINDER",
    "ESCALATE_TO_OPERATOR"
  ]
}
```

Rescue Agent may choose only from allowed interventions.

Supported interventions:
- `LISTER_REMINDER`
- `REQUEST_AVAILABILITY`
- `CHECKOUT_ASSISTANCE`
- `PAYMENT_ASSISTANCE`
- `RENTER_FOLLOW_UP`
- `ESCALATE_TO_OPERATOR`

---

## 8. Score and outcome rules

### Rescue score
Rescue Agent may read, interpret, summarize, and prioritize using the score.

Rescue Agent may not:
- change the score;
- add/remove points;
- alter thresholds;
- change the scoring function.

### Booking outcome
Rescue Agent may summarize outcomes but may not set them.

Backend/simulation owns:
- booking transitions;
- rescued/completed/lost status;
- failure;
- GMV attribution.

Rescue Agent must never grade its own intervention as successful.

---

## 9. Rescue Agent provider implementation

Use OpenAI as the current server-side LLM provider behind a provider-neutral
Rescue Agent interface. Product logic must not depend directly on a provider so
another implementation can be substituted later without changing rescue policy.

Backend environment variables:
```text
OPENAI_API_KEY=<secret>
OPENAI_MODEL=<model id>
OPENAI_TIMEOUT_SECONDS=<positive seconds; optional, defaults to 20>
FRONTEND_ORIGIN=<existing production frontend>
```

Do not expose OpenAI credentials to frontend.

Keep `OPENAI_MODEL` configurable, with a safe backend default. The active V2
runtime requires `OPENAI_API_KEY`; it does not require alternate-provider credentials.

### SMS prompt constraints
AI-generated SMS must:
- be concise;
- be natural;
- have a clear next action;
- ideally remain under 240 characters;
- use only supplied facts;
- never invent availability;
- never invent pricing/discounts;
- avoid false urgency;
- avoid manipulative language.

### Failure behavior
If Rescue Agent is unavailable:
- first-message rescue uses deterministic fallback templates;
- simulation does not crash;
- fallback is logged;
- high-value follow-up drafting failure escalates to Needs Immediate Attention instead of auto-sending a fallback follow-up.

---

## 10. High-value follow-up flow

High-value booking ($4,000+) → rescue eligible → Rescue Agent reviews case → backend validates → first SMS auto-sends → recipient replies OR remains unresolved → Rescue Agent drafts next action → Needs Immediate Attention → human chooses:

- **Approve AI** → revalidate → send draft
- **Human Rescue** → operator takes ownership; Rescue Agent stops autonomous messaging for that case

---

## 11. Activity Ledger V2

Keep the existing **Rescue Actions** section.

Add a second box below it:

## AI Agent Log

Columns:
- Time
- Booking
- AI Action
- Reason
- Tool
- Result

Example actions:
- `CASE_REVIEWED`
- `INTERVENTION_SELECTED`
- `SMS_REQUESTED`
- `SMS_SENT`
- `ACTION_DENIED`
- `HIGH_VALUE_FLAGGED`
- `ESCALATED_TO_OPERATOR`
- `FOLLOWUP_DRAFTED`
- `HUMAN_APPROVED`
- `HUMAN_TAKEOVER`
- `OPS_BRIEF_GENERATED`
- `CHAT_TOOL_CALLED`
- `AUTOPILOT_CHANGED`

Only log concise operational reasons. Never expose hidden chain-of-thought.

---

## 12. Historical context

Rescue Agent does not learn/train from interventions in V2.

Rescue Agent may read:
- prior rescue actions;
- prior recipient responses;
- lister historical response behavior;
- current simulated-month counts;
- prior outcomes.

Rescue Agent may summarize patterns, e.g.:
> Andre has required 4 rescue interventions this simulated month.

No fine-tuning, adaptive scoring, or policy self-modification.

---

## 13. Suggested new backend models

### AIAgentLog
```text
id
timestamp
booking_id optional
action_type
reason_summary
tool_name optional
tool_arguments_summary optional
result
metadata
```

### AttentionCase
```text
id
booking_id
reason
priority
high_value
status
created_at
first_sms_action_id optional
latest_reply optional
drafted_response optional
ai_recommendation
human_decision optional
resolved_at optional
```

Statuses:
- `needs_attention`
- `awaiting_approval`
- `human_handling`
- `resolved`

### OpsBrief
```text
run_id
generated_at
journeys_monitored
interventions_sent
bookings_rescued
gmv_rescued
high_value_cases
unresolved_cases
attention_case_ids
summary
```

### OpsChatMessage
```text
id
timestamp
role
content
tool_calls optional
```

In-memory persistence is acceptable for this demo if consistent with V1.

---

## 14. Suggested backend modules

```text
backend/app/services/
  llm_client.py
  rescue_agent.py
  ai_tools.py
  attention.py
  ops_brief.py
  ops_chat.py
```

Responsibilities:
- `llm_client`: OpenAI client/config/error handling
- `rescue_agent`: case review, intervention selection, SMS, escalation
- `ai_tools`: registered tools and dispatch
- `attention`: high-value policy/human approval/takeover
- `ops_brief`: run summary and urgent brief updates
- `ops_chat`: operations-only tool-using chat

Do not move deterministic scoring into Rescue Agent services.

---

## 15. Suggested V2 API

```text
GET  /ops/brief
GET  /ops/attention
GET  /ops/high-value
GET  /ops/ai-log
POST /ops/attention/{id}/approve
POST /ops/attention/{id}/human-rescue
POST /ops/chat
```

Optional:
```text
POST /bookings/{id}/human-message
```

Existing V1 endpoints must continue working.

---

## 16. Simulation changes

Keep the randomized 90-second simulation.

V2 must demonstrate:
- at least one Rescue Agent-reviewed eligible rescue;
- at least one first SMS sent by Rescue Agent;
- AI Agent Log entries;
- end-of-run Ops Brief;
- mixed outcomes.

Simulation must be capable of generating >= $4,000 bookings.

For reliable QA, add a deterministic test seed/fixture for high-value flow. Random public demo may still vary.

---

## 17. Security and reliability

- OpenAI API key server-side only.
- Never put `OPENAI_API_KEY` in `NEXT_PUBLIC_*`.
- No secrets in logs.
- Validate tool arguments.
- Rescue Agent cannot call unregistered tools.
- Simulated user text cannot grant Rescue Agent extra permissions.
- High-value human gate enforced server-side.
- Human ownership enforced server-side.
- Existing deterministic fallback templates retained.
- Rescue Agent outage must not crash the demo.

---

## 18. V2 acceptance criteria

V2 is complete when:
1. OpenAI is the current provider implementation for Rescue Agent AI behavior.
2. Existing deterministic rescue scoring remains unchanged.
3. Rescue Agent can inspect whole-marketplace state via approved tools.
4. Rescue Agent can select only allowed interventions.
5. First eligible rescue SMS can auto-send.
6. Backend revalidates every Rescue Agent write action.
7. Normal-value cases can follow approved autonomous follow-up rules.
8. High-value = >= $4,000.
9. High-value first SMS is autonomous.
10. High-value subsequent communication is human-gated.
11. Rescue Agent pre-drafts high-value follow-up.
12. Needs Immediate Attention shows high-value/exception cases.
13. Approve AI validates and sends.
14. Human Rescue transfers control.
15. No Close/Ignore action exists.
16. Rescue Agent can escalate before first outreach.
17. `/ops` exists.
18. End-of-run Rescue Agent Ops Brief is generated.
19. Mid-run brief only updates for high-value/urgent events.
20. What Rescue Agent Handled is visible.
21. High-Value Watch is visible.
22. Ask Rescue Agent is operations-only.
23. Ask Rescue Agent can call approved tools.
24. Out-of-domain chat is restricted.
25. Activity Ledger retains Rescue Actions.
26. Activity Ledger adds AI Agent Log.
27. Rescue Agent never changes scores.
28. Rescue Agent never sets booking outcomes.
29. Rescue Agent shows only concise operational reasons.
30. Rescue Agent can read prior interventions but does not self-learn.
31. 90-second simulation still works.
32. GMV metrics remain coherent.
33. Rescue Agent outage degrades safely.
34. Backend tests pass.
35. Frontend lint/build pass.
36. Render/Vercel deployment still works.

---

## 19. Codex rules

This V2 PRD modifies the existing working codebase. Do not rebuild from scratch.

Branch policy:
- V1 stable branch: `main`;
- V2 development branch: `claude-v2`;
- all Phase 10–16 commits and pushes go only to `claude-v2`;
- never merge V2 into `main` automatically;
- final merge into `main` requires explicit approval after Phase 16 and final
  end-to-end QA pass.

Before coding:
1. read `PRD.md`;
2. read `SIMULATION_PROFILES.md`;
3. read this V2 PRD;
4. inspect current architecture;
5. preserve V1 unless V2 explicitly changes it.

At the end of every phase:
1. run relevant tests;
2. fix current-phase regressions;
3. summarize implementation;
4. give manual verification steps;
5. check `git status`;
6. commit with specified message;
7. push to `origin/claude-v2`;
8. report commit hash and push result;
9. STOP;
10. wait for explicit user approval.

Never continue automatically.

---

# 20. V2 implementation phases

## Phase 10 — Provider foundation and rescue messaging
Build:
- provider-neutral LLM boundary and provider client
- `OPENAI_API_KEY`
- configurable `OPENAI_MODEL`
- Rescue Agent SMS generation
- preserve fallback templates
- update env examples/docs
- keep provider secrets backend-only

Acceptance:
- existing simulation works;
- SMS generated by Rescue Agent;
- fallback works;
- scoring/rules unchanged;
- tests pass.

Commit:
`phase-10: migrate rescue messaging to claude`

The Phase 10 commit message is retained as immutable project history. The active
provider strategy was revised during the uncommitted Phase 11 work; OpenAI is now
the current provider implementation.

Push and stop.

---

## Phase 11 — Rescue Agent tool layer + agent audit log
Build:
- approved read/write tools;
- dispatcher;
- server-side validation;
- AIAgentLog;
- `/ops/ai-log`;
- AI Agent Log UI below Rescue Actions.

Acceptance:
- Rescue Agent can inspect marketplace through tools;
- unregistered actions fail;
- write tools revalidate;
- tool actions log correctly;
- existing Rescue Actions unchanged.

Commit:
`phase-11: add rescue agent tools and ai audit log`

Push and stop.

---

## Phase 12 — High-value policy + Needs Immediate Attention
Build:
- >=$4,000 classifier;
- AttentionCase;
- first-message autonomy;
- high-value follow-up gate;
- exception escalation;
- drafted follow-up;
- Approve AI;
- Human Rescue;
- server-side human ownership.

Acceptance:
- $3,999 normal;
- $4,000 high-value;
- first high-value message auto-sends;
- second high-value message cannot send without approval;
- reply/no-response follow-up creates attention case when applicable;
- Rescue Agent draft exists;
- Approve AI sends after validation;
- Human Rescue blocks Rescue Agent sends;
- exceptions can escalate before first outreach.

Commit:
`phase-12: add high-value human escalation workflow`

Push and stop.

---

## Phase 13 — Rescue Agent Ops Brief console
Build `/ops` with:
1. Needs Immediate Attention
2. Rescue Agent Ops Brief
3. What Rescue Agent Handled
4. High-Value Watch
5. Ask Rescue Agent placeholder

Add dashboard navigation.

Acceptance:
- `/ops` loads;
- attention cases appear first;
- cards show context/draft/buttons;
- brief data renders;
- handled actions render;
- high-value watch renders;
- styling matches app.

Commit:
`phase-13: build rescue agent ops brief console`

Push and stop.

---

## Phase 14 — End-of-run brief + urgent live alerts
Build:
- structured OpsBrief;
- one full summary at run completion;
- high-value/urgent mid-run alerts;
- What Rescue Agent Handled from real logs.

Acceptance:
- completed run generates one brief;
- metrics match backend;
- Rescue Agent does not invent outcomes;
- urgent high-value events surface;
- normal events do not spam summaries;
- Rescue Agent outage degrades safely.

Commit:
`phase-14: add rescue agent marketplace briefs and priority alerts`

Push and stop.

---

## Phase 15 — Ask Rescue Agent + tool actions
Build:
- operations-only chat UI;
- Rescue Agent tool-use loop;
- read actions;
- approved write actions;
- Autopilot control;
- action result display;
- out-of-domain restriction;
- chat tool calls logged.

Acceptance examples:
- what needs attention;
- show high-value cases;
- what did you do;
- why contact Sarah;
- most at-risk booking;
- pause/resume Autopilot;
- handle anything safely allowed.

Rescue Agent cannot:
- change scores;
- set outcomes;
- bypass high-value gate;
- perform arbitrary actions;
- act as a general assistant.

Commit:
`phase-15: add tool-enabled rescue agent ops chat`

Push and stop.

---

## Phase 16 — V2 integration + production QA
Verify/polish:
- randomized 90-second run;
- deterministic high-value QA seed/fixture;
- normal-value follow-up;
- high-value first-message autonomy;
- high-value human gate;
- Needs Immediate Attention;
- Approve AI;
- Human Rescue;
- Rescue Agent logs;
- Ops Brief;
- Ask Rescue Agent;
- error/loading states;
- README V2 architecture;
- Render/Vercel env docs;
- remove dead OpenAI config if unused.

Manual reviewer path:
1. open public dashboard;
2. start simulation;
3. see deterministic scores;
4. see Rescue Agent select/send rescue;
5. see Rescue Agent logs;
6. encounter/load high-value case;
7. see first SMS auto-send;
8. see follow-up require human attention;
9. open Ops Brief;
10. review draft;
11. Approve AI or Human Rescue;
12. view end-of-run summary;
13. ask operations question;
14. use approved chat action;
15. verify both activity logs.

Automated:
- backend tests;
- frontend lint;
- frontend production build;
- no secret exposure;
- hosted backend health;
- hosted frontend/backend integration.

Commit:
`phase-16: polish ai powered rescue ops demo`

Push and stop.

---

## 21. Final V2 demo story

Start Live Simulation → marketplace events → deterministic rescue score → eligible case → Rescue Agent reviews allowed actions → Rescue Agent chooses intervention → backend validates → first SMS auto-sends → Rescue Agent logs action → high-value reply/unresolved follow-up → Rescue Agent drafts next response → Needs Immediate Attention → operator chooses Approve AI or Human Rescue → backend/simulation resolves state → Rescue Agent produces end-of-run Ops Brief → operator can ask “What needs my attention?”

Final product story:

> **The rescue engine provides deterministic policy and risk scoring. Rescue Agent operates inside those rules: it handles routine outreach, monitors the whole marketplace, summarizes what happened, and escalates high-value or exceptional cases when human judgment matters.**
