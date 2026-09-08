"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  approveAIFollowUp,
  getAIAgentLog,
  getAttentionCases,
  getDashboard,
  getHighValueBookings,
  getMarketplaceSeed,
  selectHumanRescue,
} from "@/lib/api";
import type {
  AIAgentLog,
  AttentionCase,
  Booking,
  MarketplaceSeed,
  RescueAction,
  SimulationSnapshot,
} from "@/lib/types";

import styles from "./rescue-ops.module.css";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function words(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortTime(timestamp: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(timestamp));
}

function latestAction(actions: RescueAction[], bookingId: string) {
  return [...actions].reverse().find((action) => action.booking_id === bookingId);
}

export function RescueOps() {
  const [seed, setSeed] = useState<MarketplaceSeed | null>(null);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [attention, setAttention] = useState<AttentionCase[]>([]);
  const [agentLog, setAgentLog] = useState<AIAgentLog[]>([]);
  const [highValue, setHighValue] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingCaseId, setPendingCaseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [marketplace, dashboard, cases, logs, highValueBookings] = await Promise.all([
        getMarketplaceSeed(),
        getDashboard(),
        getAttentionCases(),
        getAIAgentLog(),
        getHighValueBookings(),
      ]);
      setSeed(marketplace);
      setSnapshot(dashboard);
      setAttention(cases);
      setAgentLog(logs);
      setHighValue(highValueBookings);
      setError(null);
    } catch {
      setError("The Rescue Agent operations API is unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void load(), 0);
    const poll = window.setInterval(() => void load(), 1000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(poll);
    };
  }, [load]);

  const bookings = useMemo(() => {
    const source = snapshot?.bookings.length ? snapshot.bookings : seed?.bookings ?? [];
    return new Map(source.map((booking) => [booking.id, booking]));
  }, [seed, snapshot]);
  const renters = useMemo(
    () => new Map(seed?.renters.map((renter) => [renter.id, renter]) ?? []),
    [seed],
  );
  const listers = useMemo(
    () => new Map(seed?.listers.map((lister) => [lister.id, lister]) ?? []),
    [seed],
  );
  const listings = useMemo(
    () => new Map(seed?.listings.map((listing) => [listing.id, listing]) ?? []),
    [seed],
  );
  const actions = snapshot?.rescue_actions ?? [];

  async function decide(caseId: string, decision: "approve" | "human") {
    setPendingCaseId(caseId);
    try {
      if (decision === "approve") await approveAIFollowUp(caseId);
      else await selectHumanRescue(caseId);
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The attention-case action could not be completed.",
      );
    } finally {
      setPendingCaseId(null);
    }
  }

  const sentCount = actions.filter((action) => action.status === "sent").length;
  const rescuedCount = snapshot?.analytics.run_bookings_rescued ?? 0;
  const runGmv = snapshot?.analytics.run_gmv_rescued ?? 0;
  const journeys = snapshot?.selected_journeys.length ?? 0;
  const unresolved = (snapshot?.bookings ?? []).filter((booking) =>
    ["at_risk", "payment_issue", "awaiting_lister", "awaiting_availability"].includes(
      booking.status,
    )
  ).length;
  const runSummary = snapshot?.status === "completed"
    ? `Run complete. ${sentCount} interventions were sent; ${attention.length} cases still need operator attention.`
    : snapshot?.status === "running"
      ? `Monitoring ${journeys} live booking journeys with ${attention.length} cases requiring attention.`
      : "The operations console is ready. Start a live simulation to generate a marketplace brief.";

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p>RESCUE AGENT · OPERATIONS</p>
          <h1>Ops brief</h1>
          <span>Human judgment where it matters. Guardrailed automation everywhere else.</span>
        </div>
        <nav aria-label="Operations navigation">
          <Link href="/dashboard">Live console</Link>
          <Link href="/activity">Activity log</Link>
        </nav>
      </header>

      {error && <div className={styles.error} role="alert">{error}</div>}

      <section className={styles.section} aria-labelledby="attention-title">
        <SectionHeading
          id="attention-title"
          eyebrow="OPERATOR QUEUE"
          title="Needs immediate attention"
          detail={`${attention.length} active`}
          urgent={attention.length > 0}
        />
        {attention.length ? (
          <div className={styles.attentionGrid}>
            {attention.map((attentionCase) => {
              const booking = bookings.get(attentionCase.booking_id);
              const renter = booking ? renters.get(booking.renter_id) : undefined;
              const lister = booking ? listers.get(booking.lister_id) : undefined;
              const listing = booking ? listings.get(booking.listing_id) : undefined;
              const score = snapshot?.scores[attentionCase.booking_id];
              const firstAction = actions.find(
                (action) => action.id === attentionCase.first_sms_action_id,
              );
              const isHumanOwned = attentionCase.status === "human_handling";
              return (
                <article className={styles.attentionCard} key={attentionCase.id}>
                  <div className={styles.cardTop}>
                    <div>
                      <span className={styles.priority}>{words(attentionCase.priority)}</span>
                      {attentionCase.high_value && <span className={styles.highBadge}>HIGH VALUE</span>}
                    </div>
                    <strong>{money.format(booking?.booking_value ?? 0)}</strong>
                  </div>
                  <div className={styles.caseIdentity}>
                    <div>
                      <p>{renter?.name ?? booking?.renter_id ?? "Renter"}</p>
                      <span>Renter</span>
                    </div>
                    <b aria-hidden="true">→</b>
                    <div>
                      <p>{lister?.name ?? booking?.lister_id ?? "Lister"}</p>
                      <span>{listing?.name ?? booking?.listing_id ?? "Listing"}</span>
                    </div>
                  </div>
                  <dl className={styles.caseFacts}>
                    <div><dt>Booking status</dt><dd>{words(booking?.status ?? "unknown")}</dd></div>
                    <div><dt>Rescue score</dt><dd>{score?.score ?? booking?.rescue_score ?? 0}</dd></div>
                    <div><dt>Review state</dt><dd>{words(attentionCase.status)}</dd></div>
                  </dl>
                  <div className={styles.reason}>
                    <span>Why this needs you</span>
                    <p>{attentionCase.reason}</p>
                  </div>
                  <div className={styles.messageStack}>
                    <Message
                      label="First automated SMS"
                      text={firstAction?.message_text}
                    />
                    <Message label="Latest reply" text={attentionCase.latest_reply} incoming />
                    {attentionCase.drafted_response && (
                      <Message label="Drafted next response" text={attentionCase.drafted_response} />
                    )}
                  </div>
                  <div className={styles.recommendation}>
                    <span>AI recommendation</span>
                    <p>{attentionCase.ai_recommendation}</p>
                  </div>
                  {!attentionCase.drafted_response && (
                    <p className={styles.approvalNote}>
                      Approve AI unavailable — no AI draft exists.
                    </p>
                  )}
                  <div className={styles.actions}>
                    <button
                      type="button"
                      disabled={
                        pendingCaseId === attentionCase.id
                        || !attentionCase.drafted_response
                        || attentionCase.status !== "awaiting_approval"
                      }
                      onClick={() => void decide(attentionCase.id, "approve")}
                    >
                      Approve AI
                    </button>
                    <button
                      type="button"
                      disabled={pendingCaseId === attentionCase.id || isHumanOwned}
                      onClick={() => void decide(attentionCase.id, "human")}
                    >
                      {isHumanOwned ? "Human-owned" : "Human Rescue"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title={loading ? "Loading operator queue…" : "No cases need intervention"}
            detail="High-value follow-ups and exceptions will surface here automatically."
          />
        )}
      </section>

      <section className={styles.section} aria-labelledby="brief-title">
        <SectionHeading id="brief-title" eyebrow="CURRENT RUN" title="Rescue Agent Ops Brief" detail={words(snapshot?.status ?? "idle")} />
        <div className={styles.briefPanel}>
          <div className={styles.briefMetrics}>
            <BriefMetric label="Journeys monitored" value={String(journeys)} />
            <BriefMetric label="Interventions sent" value={String(sentCount)} />
            <BriefMetric label="Bookings rescued" value={String(rescuedCount)} />
            <BriefMetric label="GMV rescued" value={money.format(runGmv)} />
            <BriefMetric label="High-value cases" value={String(highValue.length)} />
            <BriefMetric label="Unresolved" value={String(unresolved)} />
          </div>
          <p className={styles.summary}>{runSummary}</p>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="handled-title">
        <SectionHeading id="handled-title" eyebrow="AUTOMATION TRAIL" title="What Rescue Agent Handled" detail={`${agentLog.length} logged`} />
        {agentLog.length ? (
          <div className={styles.handledList}>
            {agentLog.slice(0, 8).map((entry) => (
              <article key={entry.id}>
                <time dateTime={entry.timestamp}>{shortTime(entry.timestamp)}</time>
                <div><strong>{words(entry.action_type)}</strong><p>{entry.reason_summary}</p></div>
                <span data-result={entry.result}>{words(entry.result)}</span>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="No handled actions yet" detail="Rescue Agent actions will appear when a simulation begins." />
        )}
      </section>

      <section className={styles.section} aria-labelledby="high-value-title">
        <SectionHeading id="high-value-title" eyebrow="POLICY WATCH" title="High-Value Watch" detail="≥ $4,000" />
        {highValue.length ? (
          <div className={styles.watchGrid}>
            {highValue.map((booking) => {
              const renter = renters.get(booking.renter_id);
              const listing = listings.get(booking.listing_id);
              const action = latestAction(actions, booking.id);
              const review = attention.find((item) => item.booking_id === booking.id);
              return (
                <article className={styles.watchRow} key={booking.id}>
                  <div className={styles.watchPrimary}>
                    <span className={styles.highBadge}>HIGH VALUE</span>
                    <strong className={styles.watchIdentity}>
                      {renter?.name ?? booking.renter_id}
                      <i aria-hidden="true">·</i>
                      {listing?.name ?? booking.listing_id}
                    </strong>
                    <b>{money.format(booking.booking_value)}</b>
                  </div>
                  <div className={styles.watchMeta}>
                    <span>Score <strong>{snapshot?.scores[booking.id]?.score ?? booking.rescue_score}</strong></span>
                    <span>{words(booking.status)}</span>
                    <span>{action ? words(action.status) : "Monitoring"}</span>
                    <span>Human review {review ? words(review.status) : "not required"}</span>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState title="No high-value bookings this run" detail="Bookings at or above $4,000 will be tracked here." />
        )}
      </section>

      <section className={styles.section} aria-labelledby="ask-title">
        <SectionHeading id="ask-title" eyebrow="OPERATIONS ASSISTANT" title="Ask Rescue Agent" detail="Coming online soon" />
        <div className={styles.askPanel}>
          <div>
            <strong>Operations-only assistance</strong>
            <p>Ask about booking risk, interventions, marketplace activity, and cases that need attention.</p>
          </div>
          <form onSubmit={(event) => event.preventDefault()}>
            <input disabled aria-label="Ask Rescue Agent" placeholder="What needs my attention right now?" />
            <button disabled type="submit">Ask Rescue Agent</button>
          </form>
          <div className={styles.prompts}>
            <span>Show me high-value cases</span>
            <span>What did you handle?</span>
            <span>Which booking is most at risk?</span>
          </div>
        </div>
      </section>
    </main>
  );
}

function SectionHeading({
  id,
  eyebrow,
  title,
  detail,
  urgent = false,
}: {
  id: string;
  eyebrow: string;
  title: string;
  detail: string;
  urgent?: boolean;
}) {
  return (
    <div className={styles.sectionHeading}>
      <div><p>{eyebrow}</p><h2 id={id}>{title}</h2></div>
      <span data-urgent={urgent}>{detail}</span>
    </div>
  );
}

function BriefMetric({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function Message({
  label,
  text,
  incoming = false,
}: {
  label: string;
  text?: string | null;
  incoming?: boolean;
}) {
  return (
    <div className={styles.message} data-incoming={incoming}>
      <span>{label}</span>
      <p>{text ?? "No message recorded."}</p>
    </div>
  );
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className={styles.empty}><strong>{title}</strong><p>{detail}</p></div>;
}
