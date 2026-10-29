"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Navbar } from "../components/Navbar";
import { Footer } from "../components/Footer";
import { KpiRibbon } from "../components/KpiRibbon";
import { ForecastChart } from "../components/ForecastChart";
import { TransactionTable } from "../components/TransactionTable";
import { UploadModal } from "../components/UploadModal";
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
} from "lucide-react";

const CATEGORY_COLORS = [
  "#3B82F6", // Royal blue
  "#10B981", // Emerald
  "#06B6D4", // Cyan
  "#8B5CF6", // Purple
  "#F59E0B", // Amber
  "#EC4899", // Pink
  "#64748B", // Slate
  "#E11D48", // Crimson
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

  return (
    <div className="min-h-screen flex flex-col bg-canvas selection:bg-blue-600/30 selection:text-white">
      {/* Top Navigation */}
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Header Breadcrumb / Welcome Title */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
          <div>
            <div className="flex items-center space-x-2 text-xs text-muted-foreground font-mono mb-1">
              <span>FINWISE SYSTEMS</span>
              <span>/</span>
              <span className="text-blue-400">EXECUTIVE OVERVIEW</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white font-sans">
              Financial Intelligence & Forecaster
            </h1>
          </div>

          <div className="flex items-center space-x-3 text-xs">
            <Link
              href="/forecast"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-border transition font-medium"
            >
              <LineChart className="w-3.5 h-3.5 text-blue-400" />
              <span>Forecast Studio</span>
              <ArrowRight className="w-3 h-3 ml-0.5" />
            </Link>
            <Link
              href="/statements"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-border transition font-medium"
            >
              <FileCheck2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Statements Pipeline</span>
            </Link>
          </div>
        </div>

        {/* 1. Top 4 KPI Metrics */}
        <section aria-label="Key Performance Indicators">
          <KpiRibbon summary={summary} loading={loadingSummary} />
        </section>

        {/* 2. Middle Grid: Forecast Fan Ribbon + Spending Distribution */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Forecast Visualization Card */}
          <div className="lg:col-span-2">
            <ForecastChart
              forecastData={forecast}
              loading={loadingForecast}
              granularity={granularity}
              horizon={horizon}
              onGranularityChange={(g) => setGranularity(g)}
              onHorizonChange={(h) => setHorizon(h)}
              onRefresh={() => loadForecast(true)}
              height={360}
            />
          </div>

          {/* Right Column: Spending by Category & Cashflow Dynamics */}
          <div className="space-y-6">
            {/* Category Breakdown Card */}
            <div className="bg-card border border-border/80 rounded-xl p-5 shadow-subtle flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-tight">Spending by Category</h3>
                    <p className="text-[11px] text-muted-foreground mt-0.5">Top expenditure shares (30-day window)</p>
                  </div>
                  <Link
                    href="/analytics"
                    className="text-xs text-blue-400 hover:text-blue-300 flex items-center font-medium"
                  >
                    <span>Details</span>
                    <ArrowRight className="w-3 h-3 ml-0.5" />
                  </Link>
                </div>

                {loadingSummary || !isClient ? (
                  <div className="h-44 flex items-center justify-center text-xs text-muted-foreground">
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
                              stroke="#0B0F19"
                              strokeWidth={2}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(val: any) => [`$${parseFloat(val).toFixed(2)}`, "Spent"]}
                          contentStyle={{
                            backgroundColor: "#0F172A",
                            borderColor: "#1E293B",
                            borderRadius: "8px",
                            fontSize: "12px",
                            fontFamily: "JetBrains Mono, monospace",
                          }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="h-40 flex items-center justify-center text-xs text-muted-foreground border border-dashed border-border/60 rounded-lg mt-3">
                    No expenditure recorded
                  </div>
                )}
              </div>

              {/* Category Legend */}
              <div className="space-y-1.5 mt-3 max-h-36 overflow-y-auto pr-1">
                {summary?.top_categories?.slice(0, 4).map((cat, idx) => (
                  <div key={cat.category} className="flex items-center justify-between text-xs py-0.5">
                    <div className="flex items-center space-x-2 truncate">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length] }}
                      />
                      <span className="text-slate-300 truncate font-medium">{cat.category}</span>
                    </div>
                    <div className="flex items-center space-x-2 font-mono text-[11px]">
                      <span className="text-white font-semibold">
                        ${(cat.total_amount ?? 0).toFixed(2)}
                      </span>
                      <span className="text-muted-foreground">({cat.percentage}%)</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Inflow / Outflow Ratio Card */}
            <div className="bg-card border border-border/80 rounded-xl p-5 shadow-subtle">
              <h3 className="text-sm font-bold text-white tracking-tight mb-3">Cashflow Velocity</h3>
              <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <div className="text-[11px] text-muted-foreground flex items-center mb-1">
                    <ArrowDownLeft className="w-3 h-3 text-emerald-400 mr-1" />
                    <span>Inflow</span>
                  </div>
                  <div className="text-base font-bold text-emerald-400">
                    +${(summary?.total_credit_30d ?? 0).toFixed(2)}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-rose-500/5 border border-rose-500/20">
                  <div className="text-[11px] text-muted-foreground flex items-center mb-1">
                    <ArrowUpRight className="w-3 h-3 text-rose-400 mr-1" />
                    <span>Outflow</span>
                  </div>
                  <div className="text-base font-bold text-rose-400">
                    -${(summary?.total_debit_30d ?? 0).toFixed(2)}
                  </div>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-border/60 flex items-center justify-between text-[11px] text-muted-foreground font-mono">
                <span>Net Burn</span>
                <span
                  className={
                    (summary?.total_credit_30d ?? 0) - (summary?.total_debit_30d ?? 0) >= 0
                      ? "text-emerald-400 font-bold"
                      : "text-rose-400 font-bold"
                  }
                >
                  {(summary?.total_credit_30d ?? 0) - (summary?.total_debit_30d ?? 0) >= 0 ? "+" : ""}
                  ${((summary?.total_credit_30d ?? 0) - (summary?.total_debit_30d ?? 0)).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Bottom Section: Transaction Ledger with link to full view */}
        <section aria-label="Transaction Ledger">
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
        </section>
      </main>

      {/* Global Ingestion Modal */}
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
