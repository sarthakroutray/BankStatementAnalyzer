"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { Footer } from "../../components/Footer";
import { UploadModal } from "../../components/UploadModal";
import { Button } from "../../components/ui/Button";
import { Pill } from "../../components/ui/Pill";
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
  "#FDE047", // Cyber-yellow
  "#4ADE80", // Success
  "#38BDF8", // Sky blue
  "#A78BFA", // Violet
  "#FB923C", // Orange
  "#F472B6", // Pink
  "#A3A3A3", // Gray
  "#F87171", // Danger
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
    <div className="min-h-screen flex flex-col bg-onyx text-white selection:bg-cyber-yellow selection:text-black">
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 sm:px-8 py-10 space-y-8">
        {/* Breadcrumb Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
          <div>
            <div className="flex items-center space-x-2 text-[10px] font-mono tracking-widest text-neutral-400 mb-1">
              <Link href="/" className="hover:text-white transition">
                OVERVIEW
              </Link>
              <span>/</span>
              <span className="text-cyber-yellow font-bold">SPENDING ANALYTICS</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-sans">
              Expenditure Intelligence & Cashflow Distribution
            </h1>
            <p className="text-xs sm:text-sm text-neutral-400 mt-1">
              Portfolio cashflow velocity, cluster spending breakdown, and historical burn rate analysis
            </p>
          </div>

          <div className="flex items-center space-x-3 text-xs">
            <Link href="/forecast">
              <Button variant="outline-white" size="sm" className="flex items-center space-x-1.5">
                <span>View Forward Projections</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </Link>
          </div>
        </div>

        {/* 1. Cashflow Dynamics Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
              30d Total Debit
            </span>
            <div className="mt-4">
              <span className="text-3xl font-extrabold text-danger font-sans tabular-nums">
                -${totalDebit.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-xs text-neutral-400 mt-1">Total account debits</p>
            </div>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
              30d Total Inflow
            </span>
            <div className="mt-4">
              <span className="text-3xl font-extrabold text-success font-sans tabular-nums">
                +${totalCredit.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-xs text-neutral-400 mt-1">Total credits & deposits</p>
            </div>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
              Net Cashflow
            </span>
            <div className="mt-4">
              <span
                className={`text-3xl font-extrabold font-sans tabular-nums ${
                  netSavings >= 0 ? "text-success" : "text-danger"
                }`}
              >
                {netSavings >= 0 ? "+" : ""}${netSavings.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-xs text-neutral-400 mt-1">
                {savingsRate >= 0 ? `${savingsRate.toFixed(1)}% savings retention` : "Deficit spend"}
              </p>
            </div>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
              Daily Burn Rate
            </span>
            <div className="mt-4">
              <span className="text-3xl font-extrabold text-cyber-yellow font-sans tabular-nums">
                ${(summary?.daily_avg_burn_rate ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                <span className="text-xs text-neutral-400 font-normal ml-1 font-mono">/ day</span>
              </span>
              <p className="text-xs text-neutral-400 mt-1">Average daily debit velocity</p>
            </div>
          </div>
        </div>

        {/* 2. Visual Charts: Donut + Bar Comparison */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Donut Share */}
          <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-8 shadow-glass backdrop-blur-2xl">
            <h3 className="text-lg font-bold text-white tracking-tight mb-1 font-sans">
              Category Spending Share
            </h3>
            <p className="text-xs text-neutral-400 mb-6">
              Relative proportion of total expenditure across categories
            </p>

            {loading || !isClient ? (
              <div className="h-64 flex items-center justify-center text-xs text-neutral-400 font-mono">
                Analyzing category distributions...
              </div>
            ) : topCategories.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-xs text-neutral-400 border border-dashed border-white/10 rounded-[28px]">
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
                      paddingAngle={4}
                    >
                      {topCategories.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                          stroke="#171717"
                          strokeWidth={3}
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
            )}

            {/* Legend */}
            <div className="grid grid-cols-2 gap-2 mt-6 max-h-48 overflow-y-auto pr-1 text-xs font-mono">
              {topCategories.map((cat, idx) => (
                <div key={cat.category} className="flex items-center justify-between p-2 rounded-xl bg-deep-gray border border-white/5">
                  <div className="flex items-center space-x-2 truncate">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length] }}
                    />
                    <span className="text-white truncate font-sans font-medium">{cat.category}</span>
                  </div>
                  <span className="text-neutral-400 tabular-nums">
                    ${(cat.total_amount ?? 0).toFixed(0)} ({cat.percentage}%)
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Bar Chart Breakdown */}
          <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-8 shadow-glass backdrop-blur-2xl">
            <h3 className="text-lg font-bold text-white tracking-tight mb-1 font-sans">
              Expenditure by Magnitude
            </h3>
            <p className="text-xs text-neutral-400 mb-6">
              Total expenditure ranking in absolute dollar terms
            </p>

            {loading || !isClient ? (
              <div className="h-64 flex items-center justify-center text-xs text-neutral-400 font-mono">
                Computing expenditure rank...
              </div>
            ) : topCategories.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-xs text-neutral-400 border border-dashed border-white/10 rounded-[28px]">
                No category data available
              </div>
            ) : (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topCategories}
                    layout="vertical"
                    margin={{ top: 10, right: 30, left: 40, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="2 4" stroke="#262626" horizontal={false} />
                    <XAxis
                      type="number"
                      stroke="#737373"
                      fontSize={11}
                      tickLine={false}
                      axisLine={{ stroke: "#262626" }}
                      tickFormatter={(val) => `$${val}`}
                    />
                    <YAxis
                      dataKey="category"
                      type="category"
                      stroke="#A3A3A3"
                      fontSize={11}
                      tickLine={false}
                      axisLine={{ stroke: "#262626" }}
                      width={90}
                    />
                    <Tooltip
                      formatter={(val: any) => [`$${parseFloat(val).toFixed(2)}`, "Total Spend"]}
                      contentStyle={{
                        backgroundColor: "#171717",
                        borderColor: "rgba(255,255,255,0.15)",
                        borderRadius: "16px",
                        fontSize: "12px",
                        fontFamily: "JetBrains Mono, monospace",
                        color: "#FFFFFF",
                      }}
                    />
                    <Bar dataKey="total_amount" fill="#FDE047" radius={[0, 9999, 9999, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      </main>

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={loadData}
      />

      <Footer />
    </div>
  );
}
