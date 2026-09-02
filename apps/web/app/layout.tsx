import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sift | AI-assisted support operations",
  description: "Sift prioritizes support conversations, prepares agent-approved replies, and keeps Gmail support workflows under human control.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}



