# Rescue Snag Bookings — V2 PRD: Claude Ops Copilot

## 0. Purpose
This document modifies the existing Rescue Snag Bookings application. Do not rebuild V1. Preserve the existing Next.js + TypeScript frontend, FastAPI + Python backend, randomized 90-second simulation, deterministic rescue scoring, Autopilot, simulated SMS, activity ledger, GMV metrics, Vercel deployment, and Render deployment unless this V2 PRD explicitly changes behavior.

V2 goal: turn Claude into a constrained marketplace operations copilot that can inspect the full simulated marketplace, select from approved rescue interventions, generate/send SMS, summarize operations, surface high-value cases, escalate exceptions, and take approved actions from an operations-only chat.

Core principle:

**Rules define authority. Claude operates inside those rules.**

---

## 1. Product behavior

Claude may:
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

Claude may not:
- change rescue scores or scoring thresholds;
- change booking value;
- mark bookings rescued/completed/lost;
- bypass Autopilot or backend policy;
- invent availability, dates, pricing, discounts, or other marketplace facts;
- directly mutate state outside registered backend tools.

Backend remains source of truth.

Execution pattern:

Marketplace state → deterministic rescue score/policy → allowed action set → Claude → backend tool request → server-side revalidation → execute/deny → audit log.

---

## 2. Branding and navigation

Visible branding: **Rescue Agent · Powered by Claude**.

Primary routes:
- `/dashboard` — Live Console
- `/activity` — Activity Ledger
- `/ops` — Claude Ops Brief

Add an **Ops Brief** button beside the existing Activity button on the dashboard.

---

## 3. High-value policy

High-value means **booking value >= $4,000**.

### First outbound message
For all eligible bookings, including high-value:
- Claude may auto-send the first rescue SMS if Autopilot is ON and all backend guardrails pass.

### Normal-value bookings (< $4,000)
- Claude may continue approved follow-up messaging autonomously.
- Every send must pass backend guardrails.
- Safety cap for V2 MVP: maximum 2 Claude-authored outbound rescue messages per booking unless the operator explicitly acts from the Ops interface.

### High-value bookings (>= $4,000)
- first outbound rescue SMS may auto-send;
- every subsequent outbound response/action requires human approval;
- Claude must pre-draft the next response;
- case appears in **Needs Immediate Attention**;
- Claude cannot send the follow-up until the human chooses **Approve Claude**;
- choosing **Human Rescue** transfers ownership to the operator and stops autonomous Claude messaging for that case.

No Close/Ignore action exists. Attention issues remain active until resolved by marketplace state or human/Claude action.

---

## 4. Exception escalation

Claude may escalate before the first SMS if:
- required context is missing;
- marketplace data conflicts;
- case does not fit an approved intervention type;
- action would violate messaging policy;
- booking state is ambiguous;
- recipient explicitly asks for a human;
- Claude cannot determine a safe approved action;
- repeated model/tool failure prevents safe automation.

These cases also appear in **Needs Immediate Attention**.

---

## 5. Claude Ops Brief page

Route: `/ops`

Page hierarchy:

1. **Needs Immediate Attention**
2. **Claude Ops Brief**
3. **What Claude Handled**
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
- Claude’s drafted next response/action;
- concise Claude recommendation.

Buttons:
- **Approve Claude**
- **Human Rescue**

Approve Claude:
- server re-validates policy;
- sends the drafted response;
- logs human approval.

Human Rescue:
- marks case human-owned;
- blocks further autonomous Claude sends;
- keeps case active;
- optionally provides a human message field.

### 5.2 Claude Ops Brief
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

### 5.3 What Claude Handled
Operator-friendly list of meaningful Claude actions, e.g.:
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

## 6. Claude tool interface

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

Claude must not have tools such as:
- `change_rescue_score`
- `change_booking_value`
- `mark_booking_completed`
- `mark_booking_rescued`
- `mark_booking_lost`
- `delete_booking`
- `edit_marketplace_event`

All write tools re-check policy server-side. A Claude tool request is never itself authorization.

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

Claude may choose only from allowed interventions.

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
Claude may read, interpret, summarize, and prioritize using the score.

Claude may not:
- change the score;
- add/remove points;
- alter thresholds;
- change the scoring function.

### Booking outcome
Claude may summarize outcomes but may not set them.

Backend/simulation owns:
- booking transitions;
- rescued/completed/lost status;
- failure;
- GMV attribution.

Claude must never grade its own intervention as successful.

---

## 9. Claude provider migration

Replace the current OpenAI AI-message layer with Anthropic Claude.

Backend environment variables:
```text
ANTHROPIC_API_KEY=<secret>
ANTHROPIC_MODEL=<model id>
FRONTEND_ORIGIN=<existing production frontend>
```

Do not expose Anthropic credentials to frontend.

Keep `ANTHROPIC_MODEL` configurable rather than hardcoding a model if possible.

After migration, `OPENAI_API_KEY` should no longer be required unless some unrelated feature still uses it.

### SMS prompt constraints
Claude-generated SMS must:
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
If Claude is unavailable:
- first-message rescue uses deterministic fallback templates;
- simulation does not crash;
- fallback is logged;
- high-value follow-up drafting failure escalates to Needs Immediate Attention instead of auto-sending a fallback follow-up.

---

## 10. High-value follow-up flow

High-value booking ($4,000+) → rescue eligible → Claude reviews case → backend validates → first SMS auto-sends → recipient replies OR remains unresolved → Claude drafts next action → Needs Immediate Attention → human chooses:

- **Approve Claude** → revalidate → send draft
- **Human Rescue** → operator takes ownership; Claude stops autonomous messaging for that case

---

## 11. Activity Ledger V2

Keep the existing **Rescue Actions** section.

Add a second box below it:

## Claude Agent Log

Columns:
- Time
- Booking
- Claude Action
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

Claude does not learn/train from interventions in V2.

Claude may read:
- prior rescue actions;
- prior recipient responses;
- lister historical response behavior;
- current simulated-month counts;
- prior outcomes.

Claude may summarize patterns, e.g.:
> Andre has required 4 rescue interventions this simulated month.

No fine-tuning, adaptive scoring, or policy self-modification.

---

## 13. Suggested new backend models

### ClaudeAgentLog
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
claude_recommendation
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
  claude_client.py
  claude_agent.py
  claude_tools.py
  attention.py
  ops_brief.py
  ops_chat.py
```

Responsibilities:
- `claude_client`: Anthropic client/config/error handling
- `claude_agent`: case review, intervention selection, SMS, escalation
- `claude_tools`: registered tools and dispatch
- `attention`: high-value policy/human approval/takeover
- `ops_brief`: run summary and urgent brief updates
- `ops_chat`: operations-only tool-using chat

Do not move deterministic scoring into Claude services.

---

## 15. Suggested V2 API

```text
GET  /ops/brief
GET  /ops/attention
GET  /ops/high-value
GET  /ops/claude-log
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
- at least one Claude-reviewed eligible rescue;
- at least one first SMS sent by Claude;
- Claude Agent Log entries;
- end-of-run Ops Brief;
- mixed outcomes.

Simulation must be capable of generating >= $4,000 bookings.

For reliable QA, add a deterministic test seed/fixture for high-value flow. Random public demo may still vary.

---

## 17. Security and reliability

- Anthropic API key server-side only.
- Never put `ANTHROPIC_API_KEY` in `NEXT_PUBLIC_*`.
- No secrets in logs.
- Validate tool arguments.
- Claude cannot call unregistered tools.
- Simulated user text cannot grant Claude extra permissions.
- High-value human gate enforced server-side.
- Human ownership enforced server-side.
- Existing deterministic fallback templates retained.
- Claude outage must not crash the demo.

---

## 18. V2 acceptance criteria

V2 is complete when:
1. Claude replaces OpenAI for Rescue Agent AI behavior.
2. Existing deterministic rescue scoring remains unchanged.
3. Claude can inspect whole-marketplace state via approved tools.
4. Claude can select only allowed interventions.
5. First eligible rescue SMS can auto-send.
6. Backend revalidates every Claude write action.
7. Normal-value cases can follow approved autonomous follow-up rules.
8. High-value = >= $4,000.
9. High-value first SMS is autonomous.
10. High-value subsequent communication is human-gated.
11. Claude pre-drafts high-value follow-up.
12. Needs Immediate Attention shows high-value/exception cases.
13. Approve Claude validates and sends.
14. Human Rescue transfers control.
15. No Close/Ignore action exists.
16. Claude can escalate before first outreach.
17. `/ops` exists.
18. End-of-run Claude Ops Brief is generated.
19. Mid-run brief only updates for high-value/urgent events.
20. What Claude Handled is visible.
21. High-Value Watch is visible.
22. Ask Rescue Agent is operations-only.
23. Ask Rescue Agent can call approved tools.
24. Out-of-domain chat is restricted.
25. Activity Ledger retains Rescue Actions.
26. Activity Ledger adds Claude Agent Log.
27. Claude never changes scores.
28. Claude never sets booking outcomes.
29. Claude shows only concise operational reasons.
30. Claude can read prior interventions but does not self-learn.
31. 90-second simulation still works.
32. GMV metrics remain coherent.
33. Claude outage degrades safely.
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
7. push to `origin/main`;
8. report commit hash and push result;
9. STOP;
10. wait for explicit user approval.

Never continue automatically.

---

# 20. V2 implementation phases

## Phase 10 — Anthropic foundation + OpenAI migration
Build:
- Anthropic dependency/client
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- replace OpenAI SMS generation with Claude
- preserve fallback templates
- update env examples/docs
- remove unused OpenAI dependency if safe

Acceptance:
- existing simulation works;
- SMS generated by Claude;
- fallback works;
- scoring/rules unchanged;
- tests pass.

Commit:
`phase-10: migrate rescue messaging to claude`

Push and stop.

---

## Phase 11 — Claude tool layer + agent audit log
Build:
- approved read/write tools;
- dispatcher;
- server-side validation;
- ClaudeAgentLog;
- `/ops/claude-log`;
- Claude Agent Log UI below Rescue Actions.

Acceptance:
- Claude can inspect marketplace through tools;
- unregistered actions fail;
- write tools revalidate;
- tool actions log correctly;
- existing Rescue Actions unchanged.

Commit:
`phase-11: add claude ops tools and agent audit log`

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
- Approve Claude;
- Human Rescue;
- server-side human ownership.

Acceptance:
- $3,999 normal;
- $4,000 high-value;
- first high-value message auto-sends;
- second high-value message cannot send without approval;
- reply/no-response follow-up creates attention case when applicable;
- Claude draft exists;
- Approve Claude sends after validation;
- Human Rescue blocks Claude sends;
- exceptions can escalate before first outreach.

Commit:
`phase-12: add high-value human escalation workflow`

Push and stop.

---

## Phase 13 — Claude Ops Brief console
Build `/ops` with:
1. Needs Immediate Attention
2. Claude Ops Brief
3. What Claude Handled
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
`phase-13: build claude ops brief console`

Push and stop.

---

## Phase 14 — End-of-run brief + urgent live alerts
Build:
- structured OpsBrief;
- one full summary at run completion;
- high-value/urgent mid-run alerts;
- What Claude Handled from real logs.

Acceptance:
- completed run generates one brief;
- metrics match backend;
- Claude does not invent outcomes;
- urgent high-value events surface;
- normal events do not spam summaries;
- Claude outage degrades safely.

Commit:
`phase-14: add claude marketplace briefs and priority alerts`

Push and stop.

---

## Phase 15 — Ask Rescue Agent + tool actions
Build:
- operations-only chat UI;
- Claude tool-use loop;
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

Claude cannot:
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
- Approve Claude;
- Human Rescue;
- Claude logs;
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
4. see Claude select/send rescue;
5. see Claude logs;
6. encounter/load high-value case;
7. see first SMS auto-send;
8. see follow-up require human attention;
9. open Ops Brief;
10. review draft;
11. Approve Claude or Human Rescue;
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
`phase-16: polish claude powered rescue ops demo`

Push and stop.

---

## 21. Final V2 demo story

Start Live Simulation → marketplace events → deterministic rescue score → eligible case → Claude reviews allowed actions → Claude chooses intervention → backend validates → first SMS auto-sends → Claude logs action → high-value reply/unresolved follow-up → Claude drafts next response → Needs Immediate Attention → operator chooses Approve Claude or Human Rescue → backend/simulation resolves state → Claude produces end-of-run Ops Brief → operator can ask “What needs my attention?”

Final product story:

> **The rescue engine provides deterministic policy and risk scoring. Claude operates inside those rules: it handles routine outreach, monitors the whole marketplace, summarizes what happened, and escalates high-value or exceptional cases when human judgment matters.**
