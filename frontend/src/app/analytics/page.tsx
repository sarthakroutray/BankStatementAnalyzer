"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { Footer } from "../../components/Footer";
import { UploadModal } from "../../components/UploadModal";
import { fetchAnalyticsSummary } from "../../lib/api";
import { AnalyticsSummary } from "../../lib/types";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import {
  PieChart as PieIcon,
  TrendingUp,
  Flame,
  ArrowUpRight,
  ArrowDownLeft,
  DollarSign,
  BarChart3,
  Layers,
  ArrowRight,
} from "lucide-react";

const CATEGORY_COLORS = [
  "#3B82F6",
  "#10B981",
  "#06B6D4",
  "#8B5CF6",
  "#F59E0B",
  "#EC4899",
  "#64748B",
  "#E11D48",
];

export default function AnalyticsPage() {
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isClient, setIsClient] = useState(false);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAnalyticsSummary();
      setSummary(data);
    } catch (err) {
      console.error("Failed to load analytics summary:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const topCategories = summary?.top_categories || [];
  const histSpend = summary?.total_spend_historical_30d ?? 0;
  const totalCredit = summary?.total_credit_30d ?? 0;
  const totalDebit = summary?.total_debit_30d ?? 0;
  const netSavings = totalCredit - totalDebit;
  const savingsRate = totalCredit > 0 ? (netSavings / totalCredit) * 100 : 0;

  return (
    <div className="min-h-screen flex flex-col bg-canvas selection:bg-blue-600/30 selection:text-white">
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Breadcrumb Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
          <div>
            <div className="flex items-center space-x-2 text-xs text-muted-foreground font-mono mb-1">
              <Link href="/" className="hover:text-white transition">
                OVERVIEW
              </Link>
              <span>/</span>
              <span className="text-blue-400">SPENDING ANALYTICS</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white font-sans">
              Expenditure Intelligence & Cashflow Distribution
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Portfolio cashflow velocity, cluster spending breakdown, and historical burn rate analysis
            </p>
          </div>

          <div className="flex items-center space-x-3 text-xs">
            <Link
              href="/forecast"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-border transition font-medium"
            >
              <span>View Forward Projections</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>

        {/* 1. Cashflow Dynamics Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl bg-card border border-border/80 shadow-subtle flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              30-Day Total Debit
            </span>
            <div className="mt-3">
              <span className="text-2xl font-bold text-rose-400 font-mono">
                -${totalDebit.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-[11px] text-muted-foreground mt-1">Total account debits</p>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-card border border-border/80 shadow-subtle flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              30-Day Total Inflow
            </span>
            <div className="mt-3">
              <span className="text-2xl font-bold text-emerald-400 font-mono">
                +${totalCredit.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-[11px] text-muted-foreground mt-1">Total credits & deposits</p>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-card border border-border/80 shadow-subtle flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              Net Cashflow
            </span>
            <div className="mt-3">
              <span
                className={`text-2xl font-bold font-mono ${
                  netSavings >= 0 ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {netSavings >= 0 ? "+" : ""}${netSavings.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-[11px] text-muted-foreground mt-1">
                {savingsRate >= 0 ? `${savingsRate.toFixed(1)}% savings retention` : "Deficit spend"}
              </p>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-card border border-border/80 shadow-subtle flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              Daily Burn Rate
            </span>
            <div className="mt-3">
              <span className="text-2xl font-bold text-amber-400 font-mono">
                ${(summary?.daily_avg_burn_rate ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                <span className="text-xs text-muted-foreground font-normal ml-1">/ day</span>
              </span>
              <p className="text-[11px] text-muted-foreground mt-1">Average daily debit velocity</p>
            </div>
          </div>
        </div>

        {/* 2. Visual Charts: Donut + Bar Comparison */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Donut Share */}
          <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle">
            <h3 className="text-base font-bold text-white tracking-tight mb-1">
              Category Spending Share
            </h3>
            <p className="text-xs text-muted-foreground mb-4">
              Relative proportion of total expenditure across categories
            </p>

            {loading || !isClient ? (
              <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
                Analyzing category distributions...
              </div>
            ) : topCategories.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-xs text-muted-foreground border border-dashed border-border/60 rounded-xl">
                No expense category data found
              </div>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={topCategories}
                      dataKey="total_amount"
                      nameKey="category"
                      cx="50%"
                      cy="50%"
                      innerRadius={65}
                      outerRadius={95}
                      paddingAngle={3}
                    >
                      {topCategories.map((entry, index) => (
                        <Cell
                          key={`cat-cell-${index}`}
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
            )}
          </div>

          {/* Ranked Category Bar Chart */}
          <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle">
            <h3 className="text-base font-bold text-white tracking-tight mb-1">
              Top Categories by Expenditure
            </h3>
            <p className="text-xs text-muted-foreground mb-4">
              Ranked total spent per category in USD
            </p>

            {loading || !isClient ? (
              <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
                Calculating totals...
              </div>
            ) : topCategories.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-xs text-muted-foreground border border-dashed border-border/60 rounded-xl">
                No expense category data found
              </div>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topCategories.slice(0, 6)}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
                    <XAxis type="number" stroke="#64748B" fontSize={11} tickFormatter={(v) => `$${v}`} />
                    <YAxis dataKey="category" type="category" stroke="#94A3B8" fontSize={11} width={80} />
                    <Tooltip
                      formatter={(val: any) => [`$${parseFloat(val).toFixed(2)}`, "Total Spent"]}
                      contentStyle={{
                        backgroundColor: "#0F172A",
                        borderColor: "#1E293B",
                        borderRadius: "8px",
                        fontSize: "12px",
                        fontFamily: "JetBrains Mono, monospace",
                      }}
                    />
                    <Bar dataKey="total_amount" radius={[0, 4, 4, 0]}>
                      {topCategories.slice(0, 6).map((entry, index) => (
                        <Cell
                          key={`barchart-cell-${index}`}
                          fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>

        {/* 3. Detailed Category Ledger Table */}
        <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle">
          <div className="flex items-center justify-between pb-4 border-b border-border/60">
            <div>
              <h3 className="text-base font-bold text-white tracking-tight">Category Breakdown Matrix</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Detailed view of category expenditure, share percentages, and normalized spend
              </p>
            </div>
            <Link
              href="/transactions"
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center font-medium"
            >
              <span>View Individual Transactions</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Link>
          </div>

          <div className="overflow-x-auto mt-4">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/80 text-muted-foreground uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-2.5 px-3">Category Name</th>
                  <th className="py-2.5 px-3 text-right">Total Amount</th>
                  <th className="py-2.5 px-3 text-right">Share of Total</th>
                  <th className="py-2.5 px-3">Distribution Meter</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {loading ? (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-muted-foreground font-sans">
                      Loading category matrix...
                    </td>
                  </tr>
                ) : topCategories.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-muted-foreground font-sans">
                      No category metrics available.
                    </td>
                  </tr>
                ) : (
                  topCategories.map((cat, idx) => (
                    <tr key={cat.category} className="hover:bg-slate-900/50 transition">
                      <td className="py-3 px-3 font-sans font-medium text-white flex items-center space-x-2">
                        <span
                          className="w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length] }}
                        />
                        <span>{cat.category}</span>
                      </td>
                      <td className="py-3 px-3 text-right font-bold text-white">
                        ${cat.total_amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-300 font-semibold">
                        {cat.percentage.toFixed(1)}%
                      </td>
                      <td className="py-3 px-3 w-48">
                        <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                          <div
                            className="h-2 rounded-full"
                            style={{
                              width: `${Math.min(100, Math.max(2, cat.percentage))}%`,
                              backgroundColor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length],
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => loadData()}
      />

      <Footer />
    </div>
  );
}
