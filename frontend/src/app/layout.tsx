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
  title: "Fluxo | Bank Statement Intelligence & SARIMA Forecaster",
  description:
    "Fluxo: Know your future spend. Deterministic PDF bank statement table extraction, PostgreSQL ledger normalization, and SARIMA time-series models with 90% confidence bands.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-onyx text-white antialiased min-h-screen selection:bg-cyber-yellow selection:text-black font-sans">
        {children}
      </body>
    </html>
  );
}
