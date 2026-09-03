"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { getActivity } from "@/lib/api";
import type { ActivityRecord, ActivityResponse } from "@/lib/types";

import styles from "./rescue-activity.module.css";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function words(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function time(timestamp: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(timestamp));
}

export function RescueActivity() {
  const [data, setData] = useState<ActivityResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await getActivity());
      setError(null);
    } catch {
      setError("The rescue audit API is unavailable.");
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

  useEffect(() => {
    function closeDetail(event: KeyboardEvent) {
      if (event.key === "Escape") setSelectedId(null);
    }
    window.addEventListener("keydown", closeDetail);
    return () => window.removeEventListener("keydown", closeDetail);
  }, []);

  const selected = data?.records.find((record) => record.id === selectedId) ?? null;

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p>RESCUE AGENT · AUDIT TRAIL</p>
          <h1>Activity ledger</h1>
          <span>Every automated intervention, from trigger to business outcome.</span>
        </div>
        <Link href="/dashboard">Back to live console</Link>
      </header>

      {error && <div className={styles.error} role="alert">{error}</div>}

      <section className={styles.metrics} aria-label="Monthly rescue impact">
        <article><span>GMV rescued this month</span><strong>{money.format(data?.analytics.monthly_gmv_rescued ?? 48_250)}</strong><small>Includes {money.format(data?.analytics.run_gmv_rescued ?? 0)} this run</small></article>
        <article><span>Bookings rescued</span><strong>{data?.analytics.monthly_bookings_rescued ?? 30}</strong><small>{data?.analytics.run_bookings_rescued ?? 0} this run</small></article>
        <article><span>Success rate</span><strong>{data?.analytics.rescue_success_rate ?? 68.2}%</strong><small>Resolved monthly interventions</small></article>
      </section>

      <section className={styles.ledger}>
        <div className={styles.ledgerHeading}>
          <div><p>INTERVENTION LOG</p><h2>Rescue actions</h2></div>
          <span>{data?.records.length ?? 0} this run</span>
        </div>
        <div className={styles.tableWrap}>
          <table>
            <thead><tr><th>Time</th><th>Booking</th><th>Target</th><th>Trigger</th><th>Score</th><th>Intervention</th><th>Message</th><th>Outcome</th></tr></thead>
            <tbody>
              {data?.records.map((record) => (
                <tr
                  key={record.id}
                  tabIndex={0}
                  className={selectedId === record.id ? styles.selectedRow : undefined}
                  onClick={() => setSelectedId(record.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedId(record.id);
                    }
                  }}
                >
                  <td><time dateTime={record.timestamp}>{time(record.timestamp)}</time></td>
                  <td><strong>{record.renter_name}</strong><span>{record.listing_name}</span></td>
                  <td>{words(record.target_type)}</td>
                  <td>{words(record.trigger)}</td>
                  <td><b>{record.score}</b></td>
                  <td>{words(record.intervention)}</td>
                  <td>{words(record.message_status)}</td>
                  <td><span className={styles.outcome} data-outcome={record.outcome}>{words(record.outcome)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loading && (
          <div className={styles.empty}>
            <strong>Loading rescue activity…</strong>
            <p>Reconstructing the current intervention trail.</p>
          </div>
        )}
        {!loading && !data?.records.length && (
          <div className={styles.empty}>
            <strong>No interventions logged yet</strong>
            <p>Start the live simulation to create an inspectable Rescue Agent record.</p>
            <Link href="/dashboard">Open live console</Link>
          </div>
        )}
      </section>
      {selected && (
        <ActivityDetail record={selected} onClose={() => setSelectedId(null)} />
      )}
    </main>
  );
}

function ActivityDetail({
  record,
  onClose,
}: {
  record: ActivityRecord;
  onClose: () => void;
}) {
  return (
    <div className={styles.detailBackdrop} role="presentation" onMouseDown={onClose}>
      <aside
        className={styles.detailPanel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="activity-detail-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className={styles.detailHeader}>
          <div>
            <p>RESCUE ACTION EVIDENCE</p>
            <h2 id="activity-detail-title">{record.renter_name}</h2>
            <span>{record.listing_name}</span>
          </div>
          <button type="button" aria-label="Close activity details" onClick={onClose}>×</button>
        </div>

        <div className={styles.detailOutcome} data-outcome={record.outcome}>
          <div><span>Outcome</span><strong>{words(record.outcome)}</strong></div>
          <div><span>GMV attributed</span><strong>{money.format(record.gmv_attributed)}</strong></div>
        </div>

        <section className={styles.evidenceSection}>
          <p>WHY THE AGENT ACTED</p>
          <h3>{record.agent_explanation}</h3>
          <dl className={styles.actionFacts}>
            <div><dt>Trigger</dt><dd>{words(record.trigger)}</dd></div>
            <div><dt>Score at trigger</dt><dd>{record.score}/100</dd></div>
            <div><dt>Target</dt><dd>{record.target_name} · {words(record.target_type)}</dd></div>
            <div><dt>Intervention</dt><dd>{words(record.intervention)}</dd></div>
          </dl>
          <ul className={styles.reasons}>
            {record.score_reasons.map((reason) => (
              <li key={reason.code}><span>{reason.label}</span><strong>+{reason.points}</strong></li>
            ))}
          </ul>
        </section>

        <section className={styles.evidenceSection}>
          <p>TRIGGERING EVENTS</p>
          <ol className={styles.triggerEvents}>
            {record.triggering_events.map((event, index) => <li key={`${event}-${index}`}>{event}</li>)}
          </ol>
        </section>

        <section className={styles.messageEvidence}>
          <div><p>SIMULATED SMS</p><span>DEMO · NO REAL SEND</span></div>
          <strong>To {record.target_name}</strong>
          <blockquote>{record.message_text ?? "Message generation pending."}</blockquote>
          <small>{record.sent_at ? `Demo sent ${time(record.sent_at)}` : `Status: ${words(record.message_status)}`} · {words(record.message_source ?? "pending")}</small>
          {record.response_text ? (
            <blockquote className={styles.reply}>{record.response_text}</blockquote>
          ) : record.outcome !== "pending" ? (
            <span className={styles.noReply}>No simulated reply received.</span>
          ) : null}
        </section>

        <div className={styles.resultState}>
          <span>Resulting booking state</span>
          <strong>{words(record.resulting_booking_state)}</strong>
        </div>
      </aside>
    </div>
  );
}
