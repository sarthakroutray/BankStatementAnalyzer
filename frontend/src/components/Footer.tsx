"use client";

import React from "react";
import Link from "next/link";
import { ShieldCheck, Cpu, Database, Activity, ArrowUpRight } from "lucide-react";
import { Pill } from "./ui/Pill";

export const Footer: React.FC = () => {
  return (
    <footer className="w-full bg-charcoal/80 border-t border-white/10 rounded-t-[48px] text-xs text-neutral-400 mt-20 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-6 sm:px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 mb-12">
          {/* Brand & Mission Column */}
          <div className="md:col-span-5 space-y-4">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-full bg-black border border-white/20 flex items-center justify-center">
                <span className="w-2.5 h-2.5 rounded-full bg-cyber-yellow" />
              </div>
              <span className="font-bold text-white text-lg tracking-tight font-sans">
                Fluxo
              </span>
              <Pill variant="yellow" className="text-[9px] px-2 py-0.5">
                SARIMA v1.2
              </Pill>
            </div>
            <p className="text-xs text-neutral-400 max-w-sm leading-relaxed">
              Deterministic tabular extraction from bank statements, cryptographically deduplicated PostgreSQL ledger normalization, and automated SARIMA spending forecasts with 90% confidence ribbons.
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px] font-mono">
              <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-deep-gray border border-white/10 text-neutral-300">
                <ShieldCheck className="w-3 h-3 text-cyber-yellow mr-1.5" />
                Zero-Loss Ledger
              </span>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-deep-gray border border-white/10 text-neutral-300">
                <Database className="w-3 h-3 text-white mr-1.5" />
                PostgreSQL
              </span>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-deep-gray border border-white/10 text-neutral-300">
                <Cpu className="w-3 h-3 text-cyber-yellow mr-1.5" />
                SARIMAX Engine
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <div className="md:col-span-3">
            <h4 className="text-[10px] font-bold text-white uppercase tracking-widest font-mono mb-4">
              Dashboard Navigation
            </h4>
            <ul className="space-y-2.5 text-xs font-sans">
              <li>
                <Link href="/" className="hover:text-white transition flex items-center group">
                  <span>Executive Overview</span>
                  <ArrowUpRight className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              </li>
              <li>
                <Link href="/forecast" className="hover:text-white transition flex items-center group">
                  <span>Forecast Studio & Scenarios</span>
                  <ArrowUpRight className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              </li>
              <li>
                <Link href="/transactions" className="hover:text-white transition flex items-center group">
                  <span>Transaction Ledger</span>
                  <ArrowUpRight className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              </li>
              <li>
                <Link href="/analytics" className="hover:text-white transition flex items-center group">
                  <span>Spending Distribution</span>
                  <ArrowUpRight className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              </li>
              <li>
                <Link href="/statements" className="hover:text-white transition flex items-center group">
                  <span>Statement Ingestion Pipeline</span>
                  <ArrowUpRight className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              </li>
            </ul>
          </div>

          {/* Architecture Specifications */}
          <div className="md:col-span-4">
            <h4 className="text-[10px] font-bold text-white uppercase tracking-widest font-mono mb-4">
              System Architecture
            </h4>
            <ul className="space-y-2 font-mono text-[11px] text-neutral-400">
              <li className="flex justify-between py-1 border-b border-white/5">
                <span>Tabular Extractor</span>
                <span className="text-white">JVM CLI + OCR</span>
              </li>
              <li className="flex justify-between py-1 border-b border-white/5">
                <span>Time-Series Model</span>
                <span className="text-cyber-yellow">SARIMA (p,d,q)(P,D,Q)s</span>
              </li>
              <li className="flex justify-between py-1 border-b border-white/5">
                <span>Model Optimization</span>
                <span className="text-white">Bounded AIC Grid</span>
              </li>
              <li className="flex justify-between py-1 border-b border-white/5">
                <span>Ledger Deduplication</span>
                <span className="text-white">SHA-256 Row Hash</span>
              </li>
              <li className="flex justify-between py-1">
                <span>Confidence Envelope</span>
                <span className="text-cyber-yellow font-bold">90% Parametric Ribbon</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] font-mono">
          <p>© {new Date().getFullYear()} Fluxo Systems. Bank Statement Intelligence.</p>
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-neutral-300">All analytics systems operational</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
