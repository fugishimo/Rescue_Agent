"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  getDashboard,
  getMarketplaceSeed,
  resetSimulation,
  startSimulation,
  updateAutopilot,
} from "@/lib/api";
import type {
  Booking,
  MarketplaceEvent,
  MarketplaceSeed,
  RescueAction,
  RescueScore,
  SimulationSnapshot,
} from "@/lib/types";

import styles from "./rescue-dashboard.module.css";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function words(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function eventLabel(event: MarketplaceEvent) {
  const labels: Record<string, string> = {
    listing_viewed: "Listing viewed",
    inquiry_sent: "Renter sent an inquiry",
    booking_started: "Checkout started",
    booking_requested: "Booking requested",
    lister_notified: "Lister notified",
    lister_response_delayed: "Lister response delayed",
    availability_requested: "Availability requested",
    availability_confirmed: "Availability confirmed",
    checkout_abandoned: "Checkout abandoned",
    payment_failed: "Payment failed",
    renter_inactive: "Renter became inactive",
    rescue_score_changed: "Rescue score changed",
    rescue_triggered: "Rescue action triggered",
    autopilot_action_held: "Action held by operator",
    sms_generated: "SMS wording generated",
    sms_sent: "Demo SMS sent",
    sms_received: "Simulated reply received",
    booking_rescued: "Booking rescued",
    rescue_failed: "Rescue unsuccessful",
    booking_completed: "Booking completed",
  };
  return labels[event.event_type] ?? words(event.event_type);
}

function shortTime(timestamp: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(timestamp));
}

function ScoreDial({ score, risk }: { score: number; risk: string }) {
  return (
    <span
      className={styles.scoreDial}
      data-risk={risk}
      style={{ "--score": score } as React.CSSProperties}
      aria-label={`Rescue score ${score} out of 100`}
    >
      <span>{score}</span>
    </span>
  );
}

function MetricCard({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note: string;
  tone?: "cyan" | "amber";
}) {
  return (
    <article className={styles.metricCard} data-tone={tone}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{note}</span>
    </article>
  );
}

function SmsDemoPanel({
  action,
  recipientName,
  listingName,
}: {
  action: RescueAction | null;
  recipientName: string;
  listingName: string;
}) {
  const outcomeLabel = action?.outcome === "pending"
    ? action.status === "sent" ? "Awaiting simulated reply" : "Preparing demo message"
    : action?.outcome === "rescued" ? "Booking rescued"
      : action?.outcome === "no_response" ? "No response"
        : action?.outcome === "lost" ? "Booking lost" : "Still at risk";

  return (
    <aside className={styles.smsPanel} aria-live="polite">
      <div className={styles.smsHeader}>
        <div>
          <p>SIMULATED SMS</p>
          <h2>Rescue inbox</h2>
        </div>
        <span>DEMO · NO REAL SEND</span>
      </div>
      {action ? (
        <div className={styles.phoneFrame}>
          <div className={styles.phoneTop}>
            <span aria-hidden="true" />
            <div>
              <strong>{recipientName}</strong>
              <small>{words(action.target_type)} · {listingName}</small>
            </div>
          </div>
          <div className={styles.messageThread}>
            <div className={styles.outgoingMessage}>
              <p>{action.message_text ?? "Generating outreach…"}</p>
              <time dateTime={action.sent_at ?? undefined}>
                {action.sent_at ? `Demo sent ${shortTime(action.sent_at)}` : words(action.status)}
              </time>
            </div>
            {action.response_text && (
              <div className={styles.incomingMessage}>
                <p>{action.response_text}</p>
                {action.response_at && (
                  <time dateTime={action.response_at}>Simulated reply {shortTime(action.response_at)}</time>
                )}
              </div>
            )}
            {action.outcome === "no_response" && (
              <p className={styles.noResponse}>No simulated reply received.</p>
            )}
          </div>
          <div className={styles.smsOutcome} data-outcome={action.outcome}>
            <span>{outcomeLabel}</span>
            <small>{action.message_source === "openai" ? "AI-generated copy" : "Guardrailed fallback copy"}</small>
          </div>
        </div>
      ) : (
        <div className={styles.smsEmpty}>
          <span aria-hidden="true">•••</span>
          <strong>Demo inbox ready</strong>
          <p>A qualifying rescue will appear here as a simulated text conversation.</p>
        </div>
      )}
    </aside>
  );
}

export function RescueDashboard() {
  const [seed, setSeed] = useState<MarketplaceSeed | null>(null);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [mutating, setMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [marketplace, dashboard] = await Promise.all([
        getMarketplaceSeed(),
        getDashboard(),
      ]);
      setSeed(marketplace);
      setSnapshot(dashboard);
      setError(null);
    } catch {
      setError("The live operations API is unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(async () => {
      try {
        const dashboard = await getDashboard();
        setSnapshot(dashboard);
        setError(null);
      } catch {
        setError("Live updates paused. Reconnecting…");
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    function closeDetail(event: KeyboardEvent) {
      if (event.key === "Escape") setSelectedId(null);
    }
    window.addEventListener("keydown", closeDetail);
    return () => window.removeEventListener("keydown", closeDetail);
  }, []);

  const bookings = useMemo(() => {
    const source = snapshot?.bookings.length ? snapshot.bookings : seed?.bookings ?? [];
    return [...source].sort((a, b) => b.rescue_score - a.rescue_score);
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
  const actions = useMemo(
    () =>
      new Map(
        snapshot?.rescue_actions.map((action) => [action.booking_id, action]) ?? [],
      ),
    [snapshot],
  );

  const selectedBooking =
    bookings.find((booking) => booking.id === selectedId) ?? null;
  const selectedScore = selectedBooking
    ? snapshot?.scores[selectedBooking.id] ?? null
    : null;
  const selectedAction = selectedBooking
    ? actions.get(selectedBooking.id) ?? null
    : null;
  const latestAction = snapshot?.rescue_actions.at(-1) ?? null;
  const latestBooking = latestAction
    ? bookings.find((booking) => booking.id === latestAction.booking_id) ?? null
    : null;
  const latestRecipientName = latestAction?.target_type === "renter"
    ? renters.get(latestAction.target_id)?.name ?? "Demo renter"
    : listers.get(latestAction?.target_id ?? "")?.name ?? "Demo lister";
  const latestListingName = listings.get(latestBooking?.listing_id ?? "")?.name
    ?? "Marketplace listing";

  const status = snapshot?.status ?? "idle";
  const isRunning = status === "running";
  const highRiskCount = bookings.filter((booking) => booking.rescue_score >= 50).length;

  async function runMutation(operation: () => Promise<SimulationSnapshot>) {
    setMutating(true);
    try {
      setSnapshot(await operation());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The operation failed.");
    } finally {
      setMutating(false);
    }
  }

  async function handleStart() {
    await runMutation(async () => {
      if (status === "completed") await resetSimulation();
      return startSimulation();
    });
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <div className={styles.brandLine}>
            <span className={styles.brandMark}>RA</span>
            <span>RESCUE SNAG BOOKINGS</span>
          </div>
          <h1>Rescue Agent</h1>
          <p>Live marketplace intervention console</p>
        </div>
        <div className={styles.headerControls}>
          <Link className={styles.navLink} href="/activity">Activity log</Link>
          <div className={styles.liveState} data-live={isRunning}>
            <span aria-hidden="true" />
            {isRunning ? "LIVE" : status === "completed" ? "RUN COMPLETE" : "STANDBY"}
          </div>
          <label className={styles.toggleLabel}>
            <span>
              <strong>Autopilot</strong>
              <small>{snapshot?.autopilot_enabled === false ? "Observe only" : "Intervene automatically"}</small>
            </span>
            <button
              className={styles.toggle}
              type="button"
              role="switch"
              aria-checked={snapshot?.autopilot_enabled ?? true}
              disabled={!snapshot || mutating}
              onClick={() =>
                void runMutation(() =>
                  updateAutopilot(!(snapshot?.autopilot_enabled ?? true)),
                )
              }
            >
              <span />
            </button>
          </label>
          <button
            className={styles.primaryButton}
            type="button"
            disabled={isRunning || mutating || loading}
            onClick={() => void handleStart()}
          >
            {isRunning ? "Simulation running" : status === "completed" ? "Run again" : "Start simulation"}
          </button>
          <button
            className={styles.secondaryButton}
            type="button"
            disabled={status === "idle" || mutating}
            onClick={() => void runMutation(resetSimulation)}
          >
            Reset
          </button>
        </div>
      </header>

      {isRunning && (
        <div className={styles.progressTrack} aria-label="Simulation progress">
          <span style={{ width: `${snapshot?.progress_percent ?? 0}%` }} />
        </div>
      )}

      {error && (
        <div className={styles.errorBanner} role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void load()}>Retry</button>
        </div>
      )}

      <section className={styles.metrics} aria-label="Marketplace performance">
        <MetricCard
          label="GMV rescued"
          value={money.format(snapshot?.analytics.monthly_gmv_rescued ?? 48_250)}
          note={`Baseline + ${money.format(snapshot?.analytics.run_gmv_rescued ?? 0)} this run`}
          tone="cyan"
        />
        <MetricCard
          label="Bookings rescued"
          value={String(snapshot?.analytics.monthly_bookings_rescued ?? 30)}
          note={`${snapshot?.analytics.run_bookings_rescued ?? 0} added this run`}
          tone="cyan"
        />
        <MetricCard
          label="Rescue success rate"
          value={`${snapshot?.analytics.rescue_success_rate ?? 68.2}%`}
          note="Resolved monthly interventions"
          tone="cyan"
        />
        <MetricCard
          label="Active rescue cases"
          value={String(snapshot?.analytics.active_rescue_cases ?? 0)}
          note={`${bookings.length} live bookings · ${highRiskCount} elevated`}
          tone={highRiskCount ? "amber" : undefined}
        />
      </section>

      <div className={styles.workspace}>
        <section className={styles.bookingsPanel}>
          <div className={styles.panelHeading}>
            <div>
              <p>RISK QUEUE</p>
              <h2>Active bookings</h2>
            </div>
            <span>{bookings.length} monitored</span>
          </div>
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th>Score</th>
                  <th>Renter / listing</th>
                  <th>Value</th>
                  <th>Status</th>
                  <th>Rescue target</th>
                  <th>AI action</th>
                </tr>
              </thead>
              <tbody>
                {bookings.map((booking) => {
                  const listing = listings.get(booking.listing_id);
                  const action = actions.get(booking.id);
                  return (
                    <tr
                      key={booking.id}
                      data-risk={booking.risk_level}
                      className={selectedId === booking.id ? styles.selectedRow : undefined}
                      tabIndex={0}
                      onClick={() => setSelectedId(booking.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId(booking.id);
                        }
                      }}
                    >
                      <td><ScoreDial score={booking.rescue_score} risk={booking.risk_level} /></td>
                      <td>
                        <strong>{renters.get(booking.renter_id)?.name ?? "Unknown renter"}</strong>
                        <span>{listing?.name ?? booking.listing_id}</span>
                      </td>
                      <td className={styles.money}>{money.format(booking.booking_value)}</td>
                      <td><span className={styles.statusTag} data-status={booking.status}>{words(booking.status)}</span></td>
                      <td>
                        {booking.rescue_target ? (
                          <span className={styles.targetTag} data-target={booking.rescue_target}>{words(booking.rescue_target)}</span>
                        ) : <span className={styles.muted}>None</span>}
                      </td>
                      <td>
                        {action ? (
                          <span className={styles.actionCell}>
                            <strong>{words(action.intervention_type)}</strong>
                            <small>{words(action.status)}</small>
                          </span>
                        ) : <span className={styles.monitoring}>Monitoring</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <div className={styles.rightRail}>
          <SmsDemoPanel
            action={latestAction}
            recipientName={latestRecipientName}
            listingName={latestListingName}
          />
          <aside className={styles.feedPanel}>
            <div className={styles.panelHeading}>
              <div><p>EVENT STREAM</p><h2>Live operations</h2></div>
              <span>{snapshot?.processed_planned_events ?? 0}/{snapshot?.total_planned_events ?? 0}</span>
            </div>
            <ol className={styles.feed} aria-live="polite">
              {(snapshot?.events ?? []).slice(-12).reverse().map((event) => {
                const booking = bookings.find((item) => item.id === event.booking_id);
                return (
                  <li key={event.id} data-event={event.event_type}>
                    <span className={styles.feedDot} aria-hidden="true" />
                    <div>
                      <strong>{eventLabel(event)}</strong>
                      <p>{renters.get(booking?.renter_id ?? "")?.name ?? "Marketplace activity"}</p>
                      <time dateTime={event.timestamp}>{shortTime(event.timestamp)}</time>
                    </div>
                  </li>
                );
              })}
              {!snapshot?.events.length && (
                <li className={styles.emptyFeed}>
                  <strong>Operations feed ready</strong>
                  <p>Start the simulation to stream marketplace events.</p>
                </li>
              )}
            </ol>
          </aside>
        </div>
      </div>

      {selectedBooking && (
        <BookingDetail
          booking={selectedBooking}
          score={selectedScore}
          action={selectedAction}
          renterName={renters.get(selectedBooking.renter_id)?.name ?? "Unknown renter"}
          listerName={listers.get(selectedBooking.lister_id)?.name ?? "Unknown lister"}
          listingName={listings.get(selectedBooking.listing_id)?.name ?? "Unknown listing"}
          onClose={() => setSelectedId(null)}
        />
      )}
    </main>
  );
}

function BookingDetail({
  booking,
  score,
  action,
  renterName,
  listerName,
  listingName,
  onClose,
}: {
  booking: Booking;
  score: RescueScore | null;
  action: RescueAction | null;
  renterName: string;
  listerName: string;
  listingName: string;
  onClose: () => void;
}) {
  return (
    <div className={styles.detailBackdrop} role="presentation" onMouseDown={onClose}>
      <aside
        className={styles.detailPanel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="booking-detail-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className={styles.detailHeader}>
          <div><p>BOOKING INSPECTOR</p><h2 id="booking-detail-title">{renterName}</h2><span>{listingName}</span></div>
          <button type="button" aria-label="Close booking details" onClick={onClose}>×</button>
        </div>
        <div className={styles.detailScore}>
          <ScoreDial score={booking.rescue_score} risk={booking.risk_level} />
          <div><span>Current risk</span><strong>{words(booking.risk_level)}</strong><small>{score?.raw_score !== undefined ? `Raw signal total: ${score.raw_score}` : "Awaiting live signals"}</small></div>
        </div>
        <dl className={styles.detailFacts}>
          <div><dt>Lister</dt><dd>{listerName}</dd></div>
          <div><dt>Booking value</dt><dd>{money.format(booking.booking_value)}</dd></div>
          <div><dt>Move-in</dt><dd>{new Date(`${booking.move_in}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</dd></div>
          <div><dt>Move-out</dt><dd>{new Date(`${booking.move_out}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</dd></div>
          <div><dt>Status</dt><dd>{words(booking.status)}</dd></div>
          <div><dt>Rescue target</dt><dd>{booking.rescue_target ? words(booking.rescue_target) : "Not assigned"}</dd></div>
        </dl>
        <section className={styles.explanation}>
          <p>WHY THIS SCORE</p>
          <h3>{score?.explanation ?? "No elevated risk signals have been detected yet."}</h3>
          <ul>
            {score?.reasons.map((reason) => (
              <li key={reason.code}><span>{reason.label}</span><strong>+{reason.points}</strong></li>
            ))}
            {!score?.reasons.length && <li><span>Baseline monitoring</span><strong>+0</strong></li>}
          </ul>
        </section>
        <section className={styles.detailAction}>
          <p>AUTOPILOT DECISION</p>
          {action ? (
            <><strong>{words(action.intervention_type)}</strong><span>{action.reason_summary}</span><small>Status: {words(action.status)}</small></>
          ) : (
            <><strong>Monitoring only</strong><span>No intervention has passed the rescue guardrails.</span></>
          )}
        </section>
        {action?.message_text && (
          <section className={styles.detailSms}>
            <div>
              <p>SIMULATED SMS THREAD</p>
              <span>DEMO · NO REAL SEND</span>
            </div>
            <strong>To {action.target_type === "renter" ? renterName : listerName}</strong>
            <blockquote>{action.message_text}</blockquote>
            <small>{action.sent_at ? `Demo sent ${shortTime(action.sent_at)}` : `Status: ${words(action.status)}`}</small>
            {action.response_text && (
              <blockquote className={styles.detailReply}>{action.response_text}</blockquote>
            )}
            <b>Outcome: {words(action.outcome)}</b>
          </section>
        )}
      </aside>
    </div>
  );
}
