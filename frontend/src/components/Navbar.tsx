"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Layers,
  LineChart,
  Receipt,
  PieChart,
  FileCheck2,
  Upload,
  ArrowUpRight,
} from "lucide-react";
import { API_BASE } from "../lib/api";
import { Button } from "./ui/Button";

interface NavbarProps {
  onOpenUpload: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenUpload }) => {
  const pathname = usePathname();
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        if (isMounted) setIsBackendConnected(res.ok);
      } catch {
        if (isMounted) setIsBackendConnected(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 25000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const navLinks = [
    { href: "/", label: "Overview" },
    { href: "/forecast", label: "Forecast Studio" },
    { href: "/transactions", label: "Ledger" },
    { href: "/analytics", label: "Analytics" },
    { href: "/statements", label: "Statements" },
  ];

  return (
    <header className="sticky top-0 z-50 w-full bg-onyx/80 backdrop-blur-2xl border-b border-white/10 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-20 flex items-center justify-between gap-4">
        {/* Brand Mark & Title */}
        <Link href="/" className="flex items-center space-x-3 group select-none">
          {/* Logo Mark: Black ring with cyber-yellow center dot */}
          <div className="w-9 h-9 rounded-full bg-black border-2 border-white/20 group-hover:border-cyber-yellow flex items-center justify-center transition-all duration-300 shadow-subtle group-hover:scale-105">
            <span className="w-3 h-3 rounded-full bg-cyber-yellow animate-pulse-glow" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg sm:text-xl tracking-tight text-white font-sans">
                Fluxo
              </span>
              <span className="hidden sm:inline-block px-2 py-0.5 rounded-full text-[9px] font-mono tracking-widest font-bold bg-white/10 text-neutral-300 border border-white/10">
                SARIMA
              </span>
            </div>
          </div>
        </Link>

        {/* Center Nav Pills */}
        <nav
          aria-label="Primary Navigation"
          className="hidden md:flex items-center p-1 rounded-full bg-white/5 border border-white/10 backdrop-blur-xl"
        >
          {navLinks.map((link) => {
            const isActive =
              link.href === "/"
                ? pathname === "/"
                : pathname?.startsWith(link.href);

            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 select-none ${
                  isActive
                    ? "bg-white text-black font-semibold shadow-sm"
                    : "text-neutral-400 hover:text-white hover:bg-white/5"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Right Actions: Status + Pill CTA */}
        <div className="flex items-center space-x-3">
          {/* Server Connection Indicator */}
          <div
            className="hidden sm:flex items-center space-x-1.5 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] font-mono"
            title={
              isBackendConnected === true
                ? "FastAPI & SQLite/Postgres connected"
                : isBackendConnected === false
                ? "Backend offline"
                : "Connecting..."
            }
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isBackendConnected === true
                  ? "bg-success"
                  : isBackendConnected === false
                  ? "bg-danger"
                  : "bg-cyber-yellow animate-ping"
              }`}
            />
            <span className="text-neutral-400">
              {isBackendConnected === true ? "API LIVE" : "CONNECTING"}
            </span>
          </div>

          {/* Upload Pill Button */}
          <Button
            variant="yellow"
            size="sm"
            onClick={onOpenUpload}
            className="flex items-center space-x-1.5"
            aria-label="Upload Statement"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Statement</span>
          </Button>
        </div>
      </div>
    </header>
  );
};
