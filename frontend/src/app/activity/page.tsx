import type { Metadata } from "next";

import { RescueActivity } from "@/components/rescue-activity";

export const metadata: Metadata = {
  title: "Activity Ledger",
  description: "Inspect Rescue Agent decisions, messages, outcomes, and GMV impact.",
};

export default function ActivityPage() {
  return <RescueActivity />;
}
