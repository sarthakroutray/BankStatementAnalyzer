import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FinWise | Bank Statement Intelligence & SARIMA Forecaster",
  description:
    "Institutional financial analytics platform: Deterministic bank statement table extraction, PostgreSQL ledger normalization, and SARIMA time-series predictive spending modeling.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-background text-foreground antialiased min-h-screen selection:bg-blue-600/30 selection:text-white font-sans">
        {children}
      </body>
    </html>
  );
}

