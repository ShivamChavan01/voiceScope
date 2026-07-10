import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

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
      className={`${inter.variable} ${jetbrainsMono.variable} dark h-full antialiased`}
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
