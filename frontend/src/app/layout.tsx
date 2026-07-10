import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistPixelSquare } from "geist/font/pixel";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export const metadata: Metadata = {
  title: "VoiceScope — Operator Dashboard",
  description: "Voice AI observability platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistPixelSquare.variable} ${GeistMono.variable} dark h-full`}
      suppressHydrationWarning
    >
      <body className="h-full bg-background text-foreground" suppressHydrationWarning>
        <a href="#main-content" className="skip-link">Skip to content</a>
        <div className="app">
          <Sidebar />
          <div className="main">
            <Topbar />
            <div className="content">
              <div className="content-scroll" id="main-content" tabIndex={-1}>{children}</div>
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
