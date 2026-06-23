import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RepoMind RAG Matcher",
  description: "Advanced RAG-powered job recommendation platform and semantic resume analyzer.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {/* Global Navigation Bar */}
        <nav className="navbar">
          <a href="#" className="nav-brand">
            <span>🧠</span> <span className="nav-brand-glow">RepoMind Matcher</span>
          </a>
          <ul className="nav-links">
            <li><a href="#" className="nav-link active">Dashboard</a></li>
            <li><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="nav-link">API Docs</a></li>
            <li><a href="https://weworkremotely.com" target="_blank" rel="noreferrer" className="nav-link">Jobs Feed</a></li>
          </ul>
          <div className="nav-actions">
            <a 
              href="https://github.com/ShailiSrivastava/RepoMind-RAG-Matcher" 
              target="_blank" 
              rel="noreferrer" 
              className="nav-git-btn"
            >
              <span>🐙</span> GitHub
            </a>
          </div>
        </nav>

        {/* Content Children */}
        <div style={{ flex: 1 }}>
          {children}
        </div>
      </body>
    </html>
  );
}
