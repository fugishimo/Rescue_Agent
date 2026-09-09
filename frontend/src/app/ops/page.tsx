import type { Metadata } from "next";

import { RescueOps } from "@/components/rescue-ops";

export const metadata: Metadata = {
  title: "Ops Brief",
  description: "Review priority rescue cases and current marketplace operations.",
};

export default function OpsPage() {
  return <RescueOps />;
}
