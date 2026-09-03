"use client";

import { useEffect, useState } from "react";
import styles from "./page.module.css";

type ConnectionState = "checking" | "connected" | "unavailable";

export default function Home() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("checking");

  useEffect(() => {
    const apiBaseUrl =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

    fetch(`${apiBaseUrl}/health`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Health check failed with ${response.status}`);
        }

        return response.json() as Promise<{ status: string }>;
      })
      .then((health) => {
        setConnectionState(health.status === "ok" ? "connected" : "unavailable");
      })
      .catch(() => setConnectionState("unavailable"));
  }, []);

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <p className={styles.eyebrow}>RESCUE SNAG BOOKINGS</p>
        <h1>Rescue Agent</h1>
        <p className={styles.description}>
          Full-stack foundation ready for the live marketplace rescue workflow.
        </p>
        <div className={styles.status} data-state={connectionState}>
          <span className={styles.statusDot} aria-hidden="true" />
          <span>
            {connectionState === "checking" && "Checking backend connection…"}
            {connectionState === "connected" && "Backend connected"}
            {connectionState === "unavailable" && "Backend unavailable"}
          </span>
        </div>
      </main>
    </div>
  );
}
