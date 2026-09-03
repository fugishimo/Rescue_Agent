# Rescue Snag Bookings — Simulation Profiles

**Purpose:** Source of truth for the 11 unique marketplace profiles used by the randomized 90-second demo.

The profiles are intentionally designed to produce different booking behaviors, risk patterns, rescue triggers, and outcomes.

The simulation must contain exactly:

- **6 renters**
- **5 listers**

These profiles are fictional and must not be represented as real Snag users.

---

# 1. Simulation Design Principles

The profiles should make the Rescue Agent look intelligent because the same marketplace event can mean different things for different people.

Example:

- A 12-minute lister delay is unusual for a lister who normally responds in 3 minutes.
- The same delay is normal for a lister who usually responds in 25 minutes.

The simulation engine should use profile characteristics to influence:

- event probability,
- event timing,
- rescue score context,
- likelihood of SMS response,
- likelihood of rescue success.

Randomness should be bounded by the profile behavior rather than completely arbitrary.

---

# 2. Renter Profiles

## R1 — Maya Rodriguez

**Archetype:** High-intent, urgent mover

### Core attributes

- Intent level: Very high
- Responsiveness: High
- Listing views: High
- Checkout abandonment tendency: Low
- Payment failure tendency: Low
- Price sensitivity: Medium
- Move-in urgency: Very high
- SMS response rate: High

### Typical behavior

Maya is actively trying to secure a place soon.

She often:

- views the same listing several times,
- sends an inquiry quickly,
- starts booking when she finds a good fit,
- responds quickly to messages,
- becomes vulnerable to churn when a lister is slow.

### Simulation ranges

- views before action: 4–7
- delay between actions: short
- move-in: 2–7 days
- booking value: $1,800–$3,200
- probability of checkout abandonment: 10%
- probability of payment failure: 5%
- probability of responding to rescue SMS: 90%

### Best rescue scenario

**Lister unresponsive**

Maya creates a high-value rescue opportunity because her intent is strong but the supply side risks losing her.

### Likely successful SMS response

> Yes, I'm still interested. Can they confirm the dates?

### Likely failed outcome

If the lister remains unresponsive for too long, Maya may move to another listing.

---

## R2 — Alex Kim

**Archetype:** Interested but checkout-hesitant

### Core attributes

- Intent level: High
- Responsiveness: Medium-high
- Listing views: High
- Checkout abandonment tendency: High
- Payment failure tendency: Low
- Price sensitivity: Medium-high
- Move-in urgency: Medium
- SMS response rate: High

### Typical behavior

Alex explores deeply and often starts checkout, but may leave before finishing.

Possible reasons are intentionally abstract; the system should not invent a cause.

### Simulation ranges

- views before action: 5–9
- move-in: 7–21 days
- booking value: $2,000–$3,800
- probability of checkout abandonment: 65%
- probability of payment failure: 5%
- probability of responding to rescue SMS: 80%

### Best rescue scenario

**Checkout abandonment**

### Likely successful SMS response

> Yeah, I had a question before finishing.

### Likely failed outcome

Alex may ignore the outreach and continue browsing.

---

## R3 — Jordan Patel

**Archetype:** Strong intent with occasional payment friction

### Core attributes

- Intent level: High
- Responsiveness: High
- Listing views: Medium
- Checkout abandonment tendency: Low
- Payment failure tendency: High
- Price sensitivity: Low-medium
- Move-in urgency: High
- SMS response rate: High

### Typical behavior

Jordan moves decisively through the funnel but is the profile most likely to produce a payment failure event.

### Simulation ranges

- views before action: 2–5
- move-in: 3–12 days
- booking value: $2,300–$4,500
- probability of checkout abandonment: 10%
- probability of payment failure: 55%
- probability of responding to rescue SMS: 85%

### Best rescue scenario

**Payment assistance**

### Likely successful SMS response

> Got it — I'll try again now.

### Likely failed outcome

Payment issue remains unresolved and booking is lost.

---

## R4 — Emily Nguyen

**Archetype:** Careful researcher, healthy booking

### Core attributes

- Intent level: Medium
- Responsiveness: Medium
- Listing views: Medium-high
- Checkout abandonment tendency: Low
- Payment failure tendency: Very low
- Price sensitivity: Medium
- Move-in urgency: Low-medium
- SMS response rate: Medium

### Typical behavior

Emily researches carefully but generally progresses normally once she commits.

She should frequently create a **healthy control case** so the Rescue Agent demonstrates restraint.

### Simulation ranges

- views before action: 3–6
- move-in: 14–35 days
- booking value: $1,500–$2,900
- probability of checkout abandonment: 10%
- probability of payment failure: 2%
- probability of responding to rescue SMS: 60%

### Best simulation use

**Healthy / no rescue required**

The system should often monitor Emily without contacting her.

### Important behavior

Do not force a rescue message simply because she views a listing multiple times.

---

## R5 — Marcus Lee

**Archetype:** Price-sensitive browser with moderate intent

### Core attributes

- Intent level: Medium-low
- Responsiveness: Medium-low
- Listing views: Very high
- Checkout abandonment tendency: Medium
- Payment failure tendency: Low
- Price sensitivity: Very high
- Move-in urgency: Low
- SMS response rate: Low-medium

### Typical behavior

Marcus views many listings and may revisit them repeatedly without strong immediate purchase intent.

This profile exists to prevent the scoring model from treating raw view count as sufficient reason to intervene.

### Simulation ranges

- views before action: 6–12
- move-in: 20–45 days
- booking value: $1,200–$2,400
- probability of checkout abandonment: 35%
- probability of payment failure: 3%
- probability of responding to rescue SMS: 40%

### Best rescue scenario

Occasional **checkout assistance**, but only after stronger booking signals exist.

### Likely failed outcome

No response; continues browsing.

---

## R6 — Sofia Martinez

**Archetype:** Responsive renter who goes quiet after lister confirmation

### Core attributes

- Intent level: High
- Responsiveness: High initially, variable later
- Listing views: Medium
- Checkout abandonment tendency: Medium
- Payment failure tendency: Low
- Price sensitivity: Medium
- Move-in urgency: High
- SMS response rate: Medium-high

### Typical behavior

Sofia often moves quickly until availability is confirmed, then may become inactive before completing checkout.

### Simulation ranges

- views before action: 2–5
- move-in: 4–14 days
- booking value: $1,900–$3,400
- probability of post-confirmation inactivity: 55%
- probability of checkout abandonment: 30%
- probability of payment failure: 4%
- probability of responding to rescue SMS: 75%

### Best rescue scenario

**Renter follow-up after availability confirmed**

### Likely successful SMS response

> Yes — I'm still interested. I'll finish it now.

### Likely failed outcome

No response and booking eventually moves to lost.

---

# 3. Lister Profiles

## L1 — Sarah Chen

**Archetype:** Normally fast, highly reliable lister

### Core attributes

- Average response time: 3–5 minutes
- Acceptance rate: 90%
- Availability reliability: Very high
- App engagement: Very high
- SMS responsiveness: Very high
- Delayed-response frequency: Low

### Typical behavior

Sarah usually responds almost immediately.

Therefore, a 10–15 minute delay is a strong anomaly and should contribute materially to rescue risk.

### Simulation ranges

- average response: 4 min
- delayed response event probability: 15%
- acceptance probability: 90%
- availability confirmation probability: 95%
- response after rescue SMS: 92%

### Best rescue scenario

**Unusual lister delay**

### Successful simulated reply

> Yes, those dates are available.

### Design purpose

Demonstrates why historical behavior matters.

---

## L2 — David Brooks

**Archetype:** Slow but dependable operator

### Core attributes

- Average response time: 20–30 minutes
- Acceptance rate: 82%
- Availability reliability: High
- App engagement: Medium
- SMS responsiveness: High
- Delayed-response frequency: Medium

### Typical behavior

David responds slowly even when everything is healthy.

The Rescue Agent should **not overreact** to a short delay.

### Simulation ranges

- average response: 25 min
- delayed response event probability: 35%
- acceptance probability: 82%
- availability confirmation probability: 88%
- response after rescue SMS: 80%

### Best rescue scenario

Only trigger after the delay becomes meaningful relative to David's own baseline or when other risk factors are strong.

### Design purpose

Prevents a naive universal response-time threshold from looking intelligent.

---

## L3 — Priya Shah

**Archetype:** Strong operator with stale availability/calendar risk

### Core attributes

- Average response time: 8–12 minutes
- Acceptance rate: 86%
- Availability reliability: Medium-low
- App engagement: High
- SMS responsiveness: High
- Delayed-response frequency: Low-medium

### Typical behavior

Priya communicates reasonably quickly but sometimes does not keep availability fully current.

### Simulation ranges

- average response: 10 min
- delayed response event probability: 25%
- acceptance probability: 86%
- availability confirmation probability without reminder: 55%
- response after availability rescue SMS: 88%

### Best rescue scenario

**Request availability**

### Successful simulated reply

> Those dates are open — they can book.

### Design purpose

Creates a lister rescue that is not purely about response speed.

---

## L4 — Andre Williams

**Archetype:** High-volume lister who misses app notifications

### Core attributes

- Average response time: 12–18 minutes
- Acceptance rate: 76%
- Availability reliability: Medium-high
- App engagement: Low-medium
- SMS responsiveness: Very high
- Delayed-response frequency: High

### Typical behavior

Andre manages several listings and is more likely to miss in-app activity, but responds well to SMS.

### Simulation ranges

- average response: 15 min
- missed-app-notification probability: 50%
- delayed response probability: 45%
- acceptance probability: 76%
- response after rescue SMS: 90%

### Best rescue scenario

**Lister reminder because request is unseen / app not opened**

### Successful simulated reply

> Just saw this — yes, I'll check it now.

### Design purpose

Maps directly to "lister needs a reminder to check the app."

---

## L5 — Olivia Park

**Archetype:** Selective, low-conversion lister

### Core attributes

- Average response time: 10–15 minutes
- Acceptance rate: 55%
- Availability reliability: Medium
- App engagement: Medium-high
- SMS responsiveness: Medium
- Delayed-response frequency: Medium

### Typical behavior

Olivia is responsive enough, but frequently does not accept a request.

The Rescue Agent cannot force a successful booking.

### Simulation ranges

- average response: 12 min
- delayed response probability: 30%
- acceptance probability: 55%
- availability confirmation probability: 65%
- response after rescue SMS: 55%

### Best rescue scenario

Can receive a valid reminder, but outcomes should frequently remain unresolved or fail.

### Likely response

> Sorry, those dates won't work.

### Design purpose

Makes the system's rescue rate realistically imperfect.

---

# 4. Suggested Listing Seed Data

Each lister should own at least one listing.

These names are fictional.

## Sarah Chen

**Williamsburg Loft**
- market: Brooklyn
- monthly price: ~$2,400

**Greenpoint Studio**
- market: Brooklyn
- monthly price: ~$2,150

## David Brooks

**SoHo Studio**
- market: Manhattan
- monthly price: ~$3,300

**Lower East Side Room**
- market: Manhattan
- monthly price: ~$2,100

## Priya Shah

**Chelsea Furnished Room**
- market: Manhattan
- monthly price: ~$2,750

**East Village Studio**
- market: Manhattan
- monthly price: ~$3,050

## Andre Williams

**Bushwick Creative Loft**
- market: Brooklyn
- monthly price: ~$2,000

**Bed-Stuy Brownstone Room**
- market: Brooklyn
- monthly price: ~$1,850

**Crown Heights Studio**
- market: Brooklyn
- monthly price: ~$2,250

## Olivia Park

**Astoria Apartment**
- market: Queens
- monthly price: ~$2,300

**Long Island City Studio**
- market: Queens
- monthly price: ~$2,900

---

# 5. Profile Pairing Guidance

The randomized simulation should not hardcode only one renter/lister pair.

However, certain pairings are useful for demonstrating different rescue behavior.

## Strong hero combinations

### Maya + Sarah

Why:

- Maya has very high intent.
- Sarah normally responds very quickly.
- An unusual delay creates a clear critical rescue case.

Good trigger:

`LISTER_REMINDER`

### Alex + David

Why:

- Alex is prone to checkout abandonment.
- David is slow, but the rescue target can still be the renter when checkout behavior dominates.

Good trigger:

`CHECKOUT_ASSISTANCE`

### Jordan + Priya

Why:

- Jordan can produce payment failure.
- Priya may produce availability uncertainty.

Either side can become the rescue target depending on the randomized event sequence.

### Sofia + Andre

Why:

- Andre may miss the app notification.
- Sofia may later go quiet after confirmation.

This pair can demonstrate both lister and renter rescue at different points.

### Marcus + Olivia

Why:

- Marcus is lower intent.
- Olivia is selective.
- This pairing should frequently **not** be rescued.

Good negative/control outcome.

---

# 6. Simulation Probability Guidance

These values are guidance, not a requirement for a sophisticated probabilistic model.

Keep the engine simple and understandable.

## Renter event tendencies

High-intent renters should be more likely to:

- start booking
- send inquiry
- respond to rescue SMS

Low-intent renters should be more likely to:

- browse
- abandon
- ignore rescue outreach

## Lister event tendencies

Fast listers should usually respond quickly.

If a fast lister is delayed, the historical anomaly score should rise strongly.

Slow listers should not trigger only because they passed a generic short threshold.

High SMS-responsive listers should be more likely to recover after intervention.

Selective listers should create legitimate failed rescue outcomes.

---

# 7. Rescue Outcome Guidance

The overall demo should not have a 100% success rate.

A reasonable randomized behavior target is approximately:

- 50–75% of automated rescue interventions result in a successful progression
- 15–30% receive no useful response
- 10–25% end in a legitimate failure/rejection

These are demo-design targets, not claims about real marketplace performance.

Do not display these as real Snag statistics.

---

# 8. SMS Response Templates

The system may use short simulated recipient replies.

These replies do not need an LLM for MVP.

## Lister positive

- "Yes, those dates are available."
- "Just saw this — I'll check the request now."
- "Yep, they can move forward."
- "Those dates work."

## Lister negative

- "Sorry, those dates won't work."
- "The space isn't available anymore."
- "I can't accommodate that move-in date."

## Renter positive

- "Yes, I'm still interested."
- "Got it — I'll finish the booking now."
- "I had a question, but I'm ready to continue."
- "I'll try the payment again."

## Renter no-response

No incoming message after the defined response window.

---

# 9. Profile Data Shape

Codex should encode profile data in a structured format.

Example renter:

```python
{
    "id": "renter_maya",
    "name": "Maya Rodriguez",
    "intent_level": "very_high",
    "responsiveness": 0.90,
    "checkout_abandonment_rate": 0.10,
    "payment_failure_rate": 0.05,
    "sms_response_rate": 0.90,
    "move_in_days_range": [2, 7],
    "booking_value_range": [1800, 3200]
}
```

Example lister:

```python
{
    "id": "lister_sarah",
    "name": "Sarah Chen",
    "average_response_minutes": 4,
    "acceptance_rate": 0.90,
    "availability_reliability": 0.95,
    "app_engagement": 0.95,
    "sms_response_rate": 0.92,
    "delay_probability": 0.15
}
```

Exact representation can change if the backend model is cleaner, but the behavior meaning must remain.

---

# 10. Simulation Run Constraints

Every 90-second run should randomly select from the 11 profiles, while satisfying these constraints:

1. At least 3 active booking journeys should occur.
2. At least 1 booking must become meaningfully at risk.
3. At least 1 Autopilot rescue should be eligible when Autopilot is ON.
4. At least 1 outgoing SMS must be shown.
5. At least 1 score must visibly change at least twice.
6. At least 1 case should not be perfectly rescued.
7. Avoid making the same exact pair/story happen every run.
8. Prefer runs that include both renter and lister rescue opportunities.
9. Do not send outreach to healthy control cases merely to force activity.
10. Profile baselines must influence score interpretation.

---

# 11. Important Realism Rules

- High listing views alone do not equal high booking intent.
- A slow response is relative to the lister's baseline.
- A rescue SMS does not guarantee a successful booking.
- The Rescue Agent cannot invent availability.
- A lister may legitimately reject dates.
- A renter may legitimately stop responding.
- Payment failure may remain unresolved.
- A healthy booking should sometimes complete without AI intervention.
- The system should show restraint as well as action.

---

# 12. What Each Profile Demonstrates

| Profile | Demonstrates |
|---|---|
| Maya Rodriguez | High-intent renter endangered by supply-side delay |
| Alex Kim | Checkout abandonment rescue |
| Jordan Patel | Payment failure rescue |
| Emily Nguyen | Healthy control case / AI restraint |
| Marcus Lee | Why browsing alone should not trigger outreach |
| Sofia Martinez | Post-confirmation renter follow-up |
| Sarah Chen | Historical response-time anomaly |
| David Brooks | Why universal response thresholds are weak |
| Priya Shah | Availability confirmation rescue |
| Andre Williams | Missed app notification + SMS leverage |
| Olivia Park | Legitimate failed rescue / imperfect conversion |

This diversity is intentional and should be preserved.
