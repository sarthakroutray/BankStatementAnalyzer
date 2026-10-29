import React from "react";
import Link from "next/link";
import { ShieldCheck, Cpu, Database, FileSpreadsheet } from "lucide-react";

export const Footer: React.FC = () => {
  return (
    <footer className="w-full border-t border-border/80 bg-slate-950/70 text-xs text-muted-foreground mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          <div className="md:col-span-2 space-y-3">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-white tracking-tight text-sm font-sans">
                FinWise Statement Intelligence
              </span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
                SARIMA v1.2
              </span>
            </div>
            <p className="text-xs text-slate-400 max-w-md leading-relaxed">
              Deterministic tabular extraction from unstructured bank statements, robust SHA-256 ledger deduplication, and automated seasonal autoregressive time-series spend forecasting.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-slate-400">
              <span className="inline-flex items-center">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 mr-1" />
                Zero-Loss Ledger
              </span>
              <span>•</span>
              <span className="inline-flex items-center">
                <Database className="w-3.5 h-3.5 text-blue-400 mr-1" />
                PostgreSQL Storage
              </span>
              <span>•</span>
              <span className="inline-flex items-center">
                <Cpu className="w-3.5 h-3.5 text-purple-400 mr-1" />
                SARIMA Grid Search
              </span>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-3">
              Feature Pages
            </h4>
            <ul className="space-y-2">
              <li>
                <Link href="/" className="hover:text-white transition">
                  Executive Overview
                </Link>
              </li>
              <li>
                <Link href="/forecast" className="hover:text-white transition">
                  Forecast Studio & Scenarios
                </Link>
              </li>
              <li>
                <Link href="/transactions" className="hover:text-white transition">
                  Transaction Ledger
                </Link>
              </li>
              <li>
                <Link href="/analytics" className="hover:text-white transition">
                  Spending Analytics
                </Link>
              </li>
              <li>
                <Link href="/statements" className="hover:text-white transition">
                  Statement Ingestion Pipeline
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-3">
              Engine Specifications
            </h4>
            <ul className="space-y-1.5 font-mono text-[11px] text-slate-400">
              <li>Extractor: Digital table + OCR</li>
              <li>Model: SARIMA (p,d,q)(P,D,Q)s</li>
              <li>Loss Metric: AIC & RMSE</li>
              <li>Deduplication: SHA-256 row hash</li>
              <li>Confidence: 90% parameter ribbon</li>
            </ul>
          </div>
        </div>

        <div className="pt-6 border-t border-border/40 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px]">
          <p>© {new Date().getFullYear()} FinWise Systems. Institutional Bank Statement Intelligence.</p>
          <div className="flex items-center space-x-4">
            <span className="inline-flex items-center text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5"></span>
              All systems operational
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
};
