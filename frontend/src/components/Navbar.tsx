"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Upload,
  Activity,
  Layers,
  LineChart,
  Receipt,
  PieChart,
  FileCheck2,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";
import { API_BASE } from "../lib/api";

interface NavbarProps {
  onOpenUpload: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenUpload }) => {
  const pathname = usePathname();
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  const [latency, setLatency] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      const t0 = performance.now();
      try {
        const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        const t1 = performance.now();
        if (isMounted) {
          setIsBackendConnected(res.ok);
          setLatency(Math.round(t1 - t0));
        }
      } catch {
        if (isMounted) {
          setIsBackendConnected(false);
          setLatency(null);
        }
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 20000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const navLinks = [
    { href: "/", label: "Overview", icon: Layers },
    { href: "/forecast", label: "Forecast Studio", icon: LineChart },
    { href: "/transactions", label: "Ledger", icon: Receipt },
    { href: "/analytics", label: "Analytics", icon: PieChart },
    { href: "/statements", label: "Statements", icon: FileCheck2 },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/80 bg-canvas/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand Identification */}
        <div className="flex items-center space-x-6">
          <Link href="/" className="flex items-center space-x-3 group">
            <div className="h-9 w-9 rounded-lg bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400 group-hover:border-blue-400 transition">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-semibold text-white tracking-tight text-base font-sans">
                  FinWise
                </span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-semibold tracking-wider">
                  Enterprise
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground hidden sm:block">
                Statement Intelligence & Forecasting
              </p>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1 pl-4 border-l border-border/60">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive =
                link.href === "/"
                  ? pathname === "/"
                  : pathname?.startsWith(link.href);

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
                    isActive
                      ? "bg-slate-800 text-white border border-slate-700/80 shadow-sm"
                      : "text-muted-foreground hover:text-slate-200 hover:bg-slate-800/50"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? "text-blue-400" : "text-muted-foreground"}`} />
                  <span>{link.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right side controls */}
        <div className="flex items-center space-x-3">
          {/* Status Indicator */}
          <div
            className="hidden sm:flex items-center space-x-2 px-2.5 py-1 rounded-md bg-slate-900 border border-border/80 text-xs font-mono"
            title={
              isBackendConnected === null
                ? "Checking API connectivity..."
                : isBackendConnected
                ? `FastAPI Engine online (${latency ?? 0}ms)`
                : "FastAPI Engine unreachable"
            }
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendConnected === null
                  ? "bg-amber-400 animate-pulse"
                  : isBackendConnected
                  ? "bg-emerald-400 ring-2 ring-emerald-400/20"
                  : "bg-rose-500 ring-2 ring-rose-500/20"
              }`}
            />
            <span className="text-[11px] text-slate-300">
              {isBackendConnected === null
                ? "Connecting"
                : isBackendConnected
                ? `Operational • ${latency ?? 0}ms`
                : "Offline"}
            </span>
          </div>

          {/* Upload Button */}
          <button
            onClick={onOpenUpload}
            className="flex items-center space-x-1.5 sm:space-x-2 px-3 sm:px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 active:scale-95 text-white text-xs font-medium transition border border-blue-500/40 shadow-sm shadow-blue-600/20 shrink-0"
          >
            <Upload className="w-3.5 h-3.5 shrink-0" />
            <span>Upload<span className="hidden sm:inline"> Statement</span></span>
          </button>
        </div>
      </div>

      {/* Mobile Navigation bar */}
      <div className="md:hidden flex items-center overflow-x-auto px-4 py-2 border-t border-border/60 bg-slate-900/60 gap-1.5">
        {navLinks.map((link) => {
          const Icon = link.icon;
          const isActive =
            link.href === "/"
              ? pathname === "/"
              : pathname?.startsWith(link.href);

          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs font-medium whitespace-nowrap shrink-0 transition ${
                isActive
                  ? "bg-slate-800 text-white border border-slate-700"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{link.label}</span>
            </Link>
          );
        })}
      </div>
    </header>
  );
};
