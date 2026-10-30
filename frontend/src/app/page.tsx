"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Navbar } from "../components/Navbar";
import { Footer } from "../components/Footer";
import { KpiRibbon } from "../components/KpiRibbon";
import { ForecastChart } from "../components/ForecastChart";
import { TransactionTable } from "../components/TransactionTable";
import { UploadModal } from "../components/UploadModal";
import { Button } from "../components/ui/Button";
import { Pill } from "../components/ui/Pill";
import { GlassCard } from "../components/ui/GlassCard";
import {
  fetchAnalyticsSummary,
  fetchLatestForecast,
  generateForecast,
  fetchTransactions,
  updateCategory,
  deleteTransaction,
  deleteAllTransactions,
} from "../lib/api";
import {
  AnalyticsSummary,
  ForecastResponse,
  Transaction,
} from "../lib/types";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import {
  ArrowRight,
  TrendingUp,
  LineChart,
  FileCheck2,
  Receipt,
  Sparkles,
  ShieldCheck,
  Upload,
  ArrowUpRight,
  ArrowDownLeft,
  FileSpreadsheet,
  CheckCircle2,
  Cpu,
  Layers,
  BarChart3,
  SlidersHorizontal,
  ChevronRight,
  Lock,
} from "lucide-react";

const CATEGORY_COLORS = [
  "#FDE047", // Cyber-yellow
  "#4ADE80", // Success emerald
  "#38BDF8", // Sky blue
  "#A78BFA", // Violet
  "#FB923C", // Amber/Orange
  "#F472B6", // Pink
  "#A3A3A3", // Neutral gray
  "#F87171", // Crimson danger
];

const TICKER_ITEMS = [
  "PDF EXTRACTION",
  "SARIMA",
  "HOLT-WINTERS",
  "90% CONFIDENCE",
  "NEON POSTGRES",
  "MODAL",
  "FASTAPI",
  "NEXT.JS",
  "ZERO-LOSS LEDGER",
  "SHA-256 DEDUPLICATION",
];

const BENTO_FEATURES = [
  {
    title: "Deterministic PDF Extraction",
    description:
      "Spawns an isolated JVM CLI process parsing tabular statements deterministically across multi-bank header formats with zero AI hallucination.",
    icon: FileSpreadsheet,
  },
  {
    title: "SARIMA Time-Series Engine",
    description:
      "Automated seasonal autoregressive modeling running ADF stationarity tests and bounded AIC grid searches over (p,d,q)(P,D,Q)s parameters.",
    icon: LineChart,
  },
  {
    title: "90% Confidence Ribbons",
    description:
      "Visualizes predictive spending uncertainty as an expanding fan ribbon, giving treasury managers statistically disciplined forecast bounds.",
    icon: TrendingUp,
  },
  {
    title: "Holdout Backtesting (RMSE / MAE)",
    description:
      "Evaluates forecast precision through out-of-sample holdout backtesting, calculating exact RMSE and MAE against observed cashflows.",
    icon: Cpu,
  },
  {
    title: "Smart ML Category Tagging",
    description:
      "Normalized merchant classification pipeline automatically maps ambiguous transaction strings to discrete spending buckets.",
    icon: Sparkles,
  },
  {
    title: "Cryptographic Deduplication",
    description:
      "SHA-256 row-hash idempotency guarantees identical transactions uploaded across multiple statement cycles are never double-counted.",
    icon: ShieldCheck,
  },
];

export default function DashboardOverviewPage() {
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  // Data states
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(true);

  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [loadingForecast, setLoadingForecast] = useState(true);
  const [granularity, setGranularity] = useState<"DAILY" | "WEEKLY">("DAILY");
  const [horizon, setHorizon] = useState<number>(30);

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [totalTxns, setTotalTxns] = useState(0);
  const [loadingTxns, setLoadingTxns] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [txnType, setTxnType] = useState("ALL");

  // Load summary KPIs
  const loadSummary = useCallback(async () => {
    setLoadingSummary(true);
    try {
      const data = await fetchAnalyticsSummary();
      setSummary(data);
    } catch (err) {
      console.error("Failed to load analytics summary:", err);
    } finally {
      setLoadingSummary(false);
    }
  }, []);

  // Fetch or regenerate forecast
  const loadForecast = useCallback(
    async (refresh: boolean = false) => {
      setLoadingForecast(true);
      try {
        const data = refresh
          ? await generateForecast(granularity, horizon)
          : await fetchLatestForecast(granularity, horizon);
        setForecast(data);
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : String(err);
        if (
          errMsg.includes("No DEBIT transactions") ||
          errMsg.includes("No forecast") ||
          errMsg.includes("Insufficient")
        ) {
          setForecast(null);
        } else {
          console.error("Failed to load SARIMA forecast:", err);
        }
      } finally {
        setLoadingForecast(false);
      }
    },
    [granularity, horizon]
  );

  // Load transactions
  const loadTransactions = useCallback(async () => {
    setLoadingTxns(true);
    try {
      const data = await fetchTransactions({
        limit: 15,
        offset: (page - 1) * 15,
        search: search.trim() || undefined,
        category: category,
        txn_type: txnType,
      });
      setTransactions(data.items);
      setTotalTxns(data.total);
    } catch (err) {
      console.error("Failed to load transactions:", err);
    } finally {
      setLoadingTxns(false);
    }
  }, [page, search, category, txnType]);

  // Initial load
  useEffect(() => {
    loadSummary();
    loadForecast(false);
  }, [loadSummary, loadForecast]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const isMounted = useRef(false);

  useEffect(() => {
    if (!isMounted.current) {
      isMounted.current = true;
      return;
    }
    loadForecast(true);
  }, [granularity, horizon, loadForecast]);

  const handleUpdateCategory = async (txnId: string, newCategory: string) => {
    try {
      await updateCategory(txnId, newCategory);
      loadTransactions();
      loadSummary();
    } catch (err) {
      console.error("Failed to update transaction category:", err);
    }
  };

  const handleDeleteTransaction = async (txnId: string) => {
    try {
      await deleteTransaction(txnId);
      await loadTransactions();
      await loadSummary();
      await loadForecast(false);
    } catch (err) {
      console.error("Failed to delete transaction:", err);
    }
  };

  const handleDeleteAllTransactions = async () => {
    try {
      await deleteAllTransactions();
      setPage(1);
      await loadTransactions();
      await loadSummary();
      await loadForecast(false);
    } catch (err) {
      console.error("Failed to delete all transactions:", err);
    }
  };

  const handleUploadSuccess = (rowCount?: number) => {
    loadSummary();
    if (rowCount === undefined || rowCount > 0) {
      loadForecast(true);
    }
    setPage(1);
    loadTransactions();
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-onyx text-white selection:bg-cyber-yellow selection:text-black">
      {/* Sticky Top Navbar */}
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      {/* 1. Full Flat Cyber-Yellow Hero Section (NOVA Adaptation) */}
      <section className="relative w-full bg-cyber-yellow text-black pt-12 pb-20 sm:pt-20 sm:pb-32 px-6 sm:px-10 liquid-hero-edge overflow-hidden">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Massive Headline & CTAs */}
          <div className="lg:col-span-7 space-y-6">
            {/* Pill Label */}
            <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-black/10 text-black border border-black/15 text-[10px] font-mono tracking-widest font-bold uppercase">
              <span className="w-2 h-2 rounded-full bg-black animate-pulse" />
              <span>SPENDING FORECASTING</span>
            </div>

            {/* Massive Bold Headline */}
            <h1 className="text-5xl sm:text-7xl lg:text-8xl font-black tracking-tight leading-[0.95] text-black font-sans uppercase">
              KNOW YOUR <br />
              FUTURE SPEND.
            </h1>

            {/* Short Truthful Subtitle */}
            <p className="text-base sm:text-lg text-black/85 max-w-xl font-normal leading-relaxed">
              Upload PDF bank statements, extract tabular transactions deterministically, and generate high-precision SARIMA time-series forecasts with 90% confidence intervals.
            </p>

            {/* CTAs: Solid Black Pill + Outline Pill */}
            <div className="flex flex-wrap items-center gap-4 pt-4">
              <Button
                variant="black"
                size="lg"
                onClick={() => setIsUploadOpen(true)}
                className="flex items-center space-x-2 text-sm sm:text-base font-bold shadow-xl"
              >
                <span>Upload Statement</span>
                <ArrowRight className="w-4 h-4" />
              </Button>

              <button
                onClick={() => scrollToSection("features")}
                className="px-7 py-3.5 rounded-full border-2 border-black/25 text-black hover:bg-black/5 hover:border-black font-semibold text-sm sm:text-base transition-all duration-200 active:scale-95"
              >
                How it works
              </button>
            </div>
          </div>

          {/* Right Column: Tilted Floating Dark Glass Phone/Card Mockup */}
          <div className="lg:col-span-5 relative flex items-center justify-center pt-4 lg:pt-0">
            {/* Main Floating Phone/Card Mockup */}
            <div className="relative w-full max-w-sm rounded-[36px] bg-charcoal text-white p-6 shadow-2xl border-2 border-white/20 transform lg:-rotate-3 hover:rotate-0 transition-transform duration-500 ease-fluid animate-float">
              {/* Mockup Header */}
              <div className="flex items-center justify-between pb-4 border-b border-white/10">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full bg-cyber-yellow" />
                  <span className="text-xs font-mono font-bold tracking-wider text-neutral-300">
                    FLUXO FORECAST
                  </span>
                </div>
                <span className="text-[9px] uppercase tracking-widest font-mono text-neutral-400 bg-white/10 px-2 py-0.5 rounded-full">
                  Sample preview
                </span>
              </div>

              {/* Mockup Body: Illustrative SARIMA Sparkline & Fan Ribbon */}
              <div className="py-5 space-y-4">
                <div className="flex items-baseline justify-between">
                  <div>
                    <div className="text-[10px] uppercase font-mono tracking-widest text-neutral-400">
                      30d Projection
                    </div>
                    <div className="text-2xl font-bold font-sans text-white tabular-nums tracking-tight">
                      $4,280.00
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="inline-flex items-center text-[10px] font-mono font-bold text-success bg-success/15 px-2 py-0.5 rounded-full border border-success/30">
                      +1.8% vs last month
                    </span>
                  </div>
                </div>

                {/* Illustrative SVG Chart with 90% Fan Ribbon */}
                <div className="h-28 w-full bg-onyx/80 rounded-[20px] p-2 border border-white/10 relative overflow-hidden flex items-end">
                  <svg
                    viewBox="0 0 280 100"
                    className="w-full h-full overflow-visible"
                    preserveAspectRatio="none"
                  >
                    {/* Confidence Fan Ribbon */}
                    <polygon
                      points="120,55 160,35 210,25 270,10 270,85 210,75 160,70 120,55"
                      fill="#FDE047"
                      fillOpacity="0.2"
                    />
                    {/* Historical Spend Line */}
                    <path
                      d="M 10 75 Q 40 40 70 65 T 120 55"
                      fill="none"
                      stroke="#FDE047"
                      strokeWidth="2.5"
                    />
                    {/* Forecast Dashed Line */}
                    <path
                      d="M 120 55 Q 180 40 270 45"
                      fill="none"
                      stroke="#FFFFFF"
                      strokeWidth="2"
                      strokeDasharray="4 3"
                    />
                    {/* Pivot Dot */}
                    <circle cx="120" cy="55" r="3.5" fill="#FDE047" stroke="#000000" strokeWidth="1.5" />
                  </svg>
                  <span className="absolute bottom-1.5 left-3 text-[9px] font-mono text-neutral-500">
                    Hist Actual
                  </span>
                  <span className="absolute top-1.5 right-3 text-[9px] font-mono text-cyber-yellow">
                    SARIMA 90% CI
                  </span>
                </div>

                {/* Progress Metric */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-[10px] font-mono text-neutral-400">
                    <span>AIC Model Accuracy</span>
                    <span className="text-white font-bold">98.4% Fitted</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-deep-gray overflow-hidden">
                    <div className="h-full bg-cyber-yellow rounded-full w-4/5" />
                  </div>
                </div>
              </div>

              {/* Mockup Footer */}
              <div className="pt-3 border-t border-white/10 flex items-center justify-between text-[10px] font-mono text-neutral-400">
                <span>Model: SARIMAX(1,1,1)(1,1,0)7</span>
                <span className="text-cyber-yellow">Active</span>
              </div>
            </div>

            {/* Floating Pill Badge 1: Secure & Deduplicated */}
            <div className="absolute -top-3 left-2 sm:-left-6 px-4 py-2 rounded-full bg-black/95 text-white border border-white/20 text-xs font-mono font-medium shadow-2xl flex items-center space-x-2 transform -rotate-6 animate-float">
              <Lock className="w-3.5 h-3.5 text-cyber-yellow" />
              <span>Secure / SHA-256</span>
            </div>

            {/* Floating Pill Badge 2: 90% Confidence Interval */}
            <div className="absolute -bottom-4 right-0 sm:-right-4 px-4 py-2 rounded-full bg-cyber-yellow text-black border-2 border-black text-xs font-mono font-bold shadow-2xl flex items-center space-x-2 transform rotate-6 animate-float">
              <span className="w-2 h-2 rounded-full bg-black" />
              <span>90% CI Parameter Fan</span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Infinite Marquee Ticker (Dark Void Transition) */}
      <section className="w-full bg-onyx py-6 border-b border-white/10 overflow-hidden select-none">
        <div className="flex w-[200%] animate-ticker whitespace-nowrap text-xs font-mono font-bold tracking-widest text-neutral-400">
          <div className="flex items-center space-x-8 px-4">
            {TICKER_ITEMS.map((item, idx) => (
              <span key={`ticker-1-${idx}`} className="flex items-center space-x-8">
                <span>{item}</span>
                <span className="text-cyber-yellow text-sm">✦</span>
              </span>
            ))}
          </div>
          <div className="flex items-center space-x-8 px-4">
            {TICKER_ITEMS.map((item, idx) => (
              <span key={`ticker-2-${idx}`} className="flex items-center space-x-8">
                <span>{item}</span>
                <span className="text-cyber-yellow text-sm">✦</span>
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* 3. Executive Dashboard Section */}
      <section id="dashboard" className="w-full max-w-7xl mx-auto px-6 sm:px-8 pt-12 pb-6 space-y-8">
        {/* Dashboard Title & Quick Jump Links */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-white/10">
          <div>
            <div className="flex items-center space-x-2 text-[10px] font-mono tracking-widest text-neutral-400 uppercase mb-1">
              <span>FLUXO SYSTEMS</span>
              <span>/</span>
              <span className="text-cyber-yellow font-bold">EXECUTIVE DASHBOARD</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-sans">
              Financial Intelligence & Forecaster
            </h2>
          </div>

          <div className="flex items-center space-x-3 text-xs">
            <Link href="/forecast">
              <Button variant="outline-white" size="sm" className="flex items-center space-x-1.5">
                <LineChart className="w-3.5 h-3.5 text-cyber-yellow" />
                <span>Forecast Studio</span>
                <ArrowRight className="w-3 h-3 ml-0.5" />
              </Button>
            </Link>
            <Link href="/statements">
              <Button variant="outline-white" size="sm" className="flex items-center space-x-1.5">
                <FileCheck2 className="w-3.5 h-3.5 text-success" />
                <span>Statements Pipeline</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* 1. Top 4 KPI Metric Strip */}
        <div aria-label="Key Performance Indicators">
          <KpiRibbon summary={summary} loading={loadingSummary} />
        </div>

        {/* 2. Middle Grid: Forecast Chart + Category Spending Breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main Forecast Visualization */}
          <div className="lg:col-span-8">
            <ForecastChart
              forecastData={forecast}
              loading={loadingForecast}
              granularity={granularity}
              horizon={horizon}
              onGranularityChange={(g) => setGranularity(g)}
              onHorizonChange={(h) => setHorizon(h)}
              onRefresh={() => loadForecast(true)}
              height={380}
            />
          </div>

          {/* Right Column: Spending Distribution & Velocity */}
          <div className="lg:col-span-4 space-y-6 flex flex-col justify-between">
            {/* Category Breakdown Card */}
            <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 shadow-glass backdrop-blur-2xl flex-1 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-white/10">
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-tight font-sans">
                      Spending by Category
                    </h3>
                    <p className="text-[11px] text-neutral-400 mt-0.5">Top expenditure shares (30d)</p>
                  </div>
                  <Link
                    href="/analytics"
                    className="text-xs text-cyber-yellow hover:underline flex items-center font-medium font-mono"
                  >
                    <span>Details</span>
                    <ArrowRight className="w-3 h-3 ml-0.5" />
                  </Link>
                </div>

                {loadingSummary || !isClient ? (
                  <div className="h-44 flex items-center justify-center text-xs text-neutral-400 font-mono">
                    Aggregating category clusters...
                  </div>
                ) : summary?.top_categories?.length ? (
                  <div className="h-40 mt-3">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={summary.top_categories}
                          dataKey="total_amount"
                          nameKey="category"
                          cx="50%"
                          cy="50%"
                          innerRadius={46}
                          outerRadius={68}
                          paddingAngle={3}
                        >
                          {summary.top_categories.map((entry, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                              stroke="#171717"
                              strokeWidth={2}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(val: any) => [`$${parseFloat(val).toFixed(2)}`, "Spent"]}
                          contentStyle={{
                            backgroundColor: "#171717",
                            borderColor: "rgba(255,255,255,0.15)",
                            borderRadius: "16px",
                            fontSize: "12px",
                            fontFamily: "JetBrains Mono, monospace",
                            color: "#FFFFFF",
                          }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="h-40 flex items-center justify-center text-xs text-neutral-400 border border-dashed border-white/10 rounded-[20px] mt-3">
                    No expenditure recorded
                  </div>
                )}
              </div>

              {/* Category Legend */}
              <div className="space-y-1.5 mt-3 max-h-36 overflow-y-auto pr-1 font-mono text-xs">
                {summary?.top_categories?.slice(0, 4).map((cat, idx) => (
                  <div key={cat.category} className="flex items-center justify-between py-0.5">
                    <div className="flex items-center space-x-2 truncate">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length] }}
                      />
                      <span className="text-neutral-300 truncate font-sans font-medium">{cat.category}</span>
                    </div>
                    <div className="flex items-center space-x-2 text-[11px] tabular-nums">
                      <span className="text-white font-bold">
                        ${(cat.total_amount ?? 0).toFixed(2)}
                      </span>
                      <span className="text-neutral-500">({cat.percentage}%)</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Inflow / Outflow Ratio Card */}
            <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 shadow-glass backdrop-blur-2xl">
              <h3 className="text-sm font-bold text-white tracking-tight mb-3 font-sans">
                Cashflow Velocity
              </h3>
              <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                <div className="p-3.5 rounded-[20px] bg-success/10 border border-success/20">
                  <div className="text-[10px] text-neutral-400 flex items-center mb-1">
                    <ArrowDownLeft className="w-3 h-3 text-success mr-1" />
                    <span>Inflow</span>
                  </div>
                  <div className="text-base font-bold text-success tabular-nums">
                    +${(summary?.total_credit_30d ?? 0).toFixed(2)}
                  </div>
                </div>
                <div className="p-3.5 rounded-[20px] bg-danger/10 border border-danger/20">
                  <div className="text-[10px] text-neutral-400 flex items-center mb-1">
                    <ArrowUpRight className="w-3 h-3 text-danger mr-1" />
                    <span>Outflow</span>
                  </div>
                  <div className="text-base font-bold text-danger tabular-nums">
                    -${(summary?.total_debit_30d ?? 0).toFixed(2)}
                  </div>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-white/10 flex items-center justify-between text-xs text-neutral-400 font-mono">
                <span>Net Burn</span>
                <span
                  className={`font-bold tabular-nums ${
                    (summary?.total_credit_30d ?? 0) - (summary?.total_debit_30d ?? 0) >= 0
                      ? "text-success"
                      : "text-danger"
                  }`}
                >
                  {(summary?.total_credit_30d ?? 0) - (summary?.total_debit_30d ?? 0) >= 0 ? "+" : ""}
                  ${((summary?.total_credit_30d ?? 0) - (summary?.total_debit_30d ?? 0)).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Transaction Ledger Section */}
        <div aria-label="Transaction Ledger">
          <TransactionTable
            transactions={transactions}
            total={totalTxns}
            loading={loadingTxns}
            page={page}
            pageSize={15}
            search={search}
            category={category}
            txnType={txnType}
            onPageChange={(p) => setPage(p)}
            onSearchChange={(s) => {
              setSearch(s);
              setPage(1);
            }}
            onCategoryChange={(c) => {
              setCategory(c);
              setPage(1);
            }}
            onTxnTypeChange={(t) => {
              setTxnType(t);
              setPage(1);
            }}
            onUpdateCategory={handleUpdateCategory}
            onDeleteTransaction={handleDeleteTransaction}
            onDeleteAllTransactions={handleDeleteAllTransactions}
            showExport={true}
            viewAllHref="/transactions"
          />
        </div>
      </section>

      {/* 4. Bento Grid Features Section (NOVA Adaptation) */}
      <section id="features" className="w-full max-w-7xl mx-auto px-6 sm:px-8 py-20 border-t border-white/10">
        <div className="mb-12">
          <div className="inline-block mb-3">
            <Pill variant="yellow">FEATURES</Pill>
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight font-sans">
            Everything you need. <br />
            <span className="text-neutral-500 font-normal">Nothing you don&apos;t.</span>
          </h2>
        </div>

        {/* Bento Grid: 6 Cards in Charcoal with Deep-Gray Icon Tiles */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {BENTO_FEATURES.map((feat, idx) => {
            const Icon = feat.icon;
            return (
              <div
                key={idx}
                className="group relative bg-charcoal/90 hover:bg-charcoal border border-white/10 hover:border-white/25 rounded-[32px] p-8 shadow-glass backdrop-blur-2xl transition-all duration-300 flex flex-col justify-between"
              >
                <div>
                  {/* Yellow Icon in Rounded Deep-Gray Tile */}
                  <div className="w-12 h-12 rounded-[20px] bg-deep-gray border border-white/10 flex items-center justify-center text-cyber-yellow group-hover:scale-110 transition-transform duration-300 mb-6">
                    <Icon className="w-6 h-6" />
                  </div>
                  <h3 className="text-lg font-bold text-white font-sans tracking-tight mb-2">
                    {feat.title}
                  </h3>
                  <p className="text-xs sm:text-sm text-neutral-400 leading-relaxed font-sans">
                    {feat.description}
                  </p>
                </div>

                {/* Bottom Circular Arrow Icon */}
                <div className="pt-6 flex justify-end">
                  <div className="w-9 h-9 rounded-full bg-deep-gray border border-white/10 flex items-center justify-center text-neutral-400 group-hover:text-cyber-yellow group-hover:border-cyber-yellow/40 transition-colors">
                    <ChevronRight className="w-4 h-4" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 5. Closing CTA Card Section */}
      <section className="w-full max-w-7xl mx-auto px-6 sm:px-8 pb-16">
        <div className="relative rounded-[40px] bg-charcoal border border-white/15 p-8 sm:p-14 shadow-2xl overflow-hidden backdrop-blur-2xl">
          {/* Faint Yellow Glow in Top Right Corner */}
          <div className="absolute top-0 right-0 w-80 h-80 rounded-full bg-cyber-yellow/15 blur-3xl pointer-events-none" />

          <div className="relative z-10 max-w-2xl space-y-4">
            <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white font-sans uppercase">
              Ready to <span className="text-cyber-yellow">Forecast?</span>
            </h2>
            <p className="text-sm sm:text-base text-neutral-400 leading-relaxed font-sans">
              Ingest your statement PDF securely. Generate high-confidence SARIMA projections, detect outlier burn velocities, and manage your ledger with precision.
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-4">
              <Button
                variant="yellow"
                size="lg"
                onClick={() => setIsUploadOpen(true)}
                className="flex items-center space-x-2 font-bold shadow-xl"
              >
                <Upload className="w-4 h-4" />
                <span>Upload Statement</span>
              </Button>

              <Link href="/transactions">
                <Button variant="outline-white" size="lg">
                  Explore Ledger
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Global PDF Ingestion Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />

      {/* Footer */}
      <Footer />
    </div>
  );
}
