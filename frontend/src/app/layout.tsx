import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Rescue Agent | Live Operations",
    template: "%s | Rescue Agent",
  },
  description: "Monitor and rescue at-risk marketplace bookings in real time.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
