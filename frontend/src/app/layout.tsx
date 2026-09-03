import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rescue Agent",
  description: "Rescue bookings in real time.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
