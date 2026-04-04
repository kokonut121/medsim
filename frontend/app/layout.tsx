import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedSentinel",
  description: "AI world model + agent orchestration network for hospital safety and operations intelligence"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

