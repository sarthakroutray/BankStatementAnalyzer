"use client";

import React from "react";
import {
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Flame,
  Cpu,
  Wallet,
  Activity,
} from "lucide-react";
import { AnalyticsSummary } from "../lib/types";
import { Skeleton } from "./ui/Skeleton";
import { Pill } from "./ui/Pill";

interface KpiRibbonProps {
  summary: AnalyticsSummary | null;
  loading: boolean;
}

const formatCurrency = (val: number) => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);
};

export const KpiRibbon: React.FC<KpiRibbonProps> = ({ summary, loading }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-44 rounded-[32px] bg-charcoal/90 border border-white/10 p-6 flex flex-col justify-between"
          >
            <div className="flex justify-between items-center">
              <Skeleton rounded="pill" className="h-3 w-28" />
              <Skeleton rounded="pill" className="h-6 w-16" />
            </div>
            <Skeleton rounded="pill" className="h-10 w-36 my-2" />
            <Skeleton rounded="pill" className="h-4 w-44" />
          </div>
        ))}
      </div>
    );
  }

  const txnCount = summary?.recent_transactions_count ?? 0;
  const histSpend = summary?.total_spend_historical_30d ?? 0;
  const projSpend = summary?.sarima_projected_spend_next_30d ?? 0;
  const momDelta = summary?.mom_spend_delta_percent ?? 0;
  const dailyBurn = summary?.daily_avg_burn_rate ?? 0;
  const rmse = summary?.model_accuracy?.rmse;
  const aic = summary?.model_accuracy?.aic;
  const sarimaOrder =
    txnCount === 0
      ? "No Data"
      : summary?.model_accuracy?.sarima_order || "Not fitted";

  const isSpendIncreasing = momDelta > 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      {/* 1. Historical 30d Spend */}
      <div className="relative group bg-charcoal/90 hover:bg-charcoal border border-white/10 hover:border-white/20 rounded-[32px] p-6 backdrop-blur-2xl transition-all duration-300 shadow-glass flex flex-col justify-between overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
            30d Historical Spend
          </span>
          <Pill variant="yellow" className="text-[9px] px-2.5 py-0.5">
            ACTUAL
          </Pill>
        </div>

        <div className="mt-4">
          <div className="text-3xl font-extrabold tracking-tight text-white font-sans tabular-nums">
            {formatCurrency(histSpend)}
          </div>
          <div className="mt-3 flex items-center text-xs text-neutral-400 font-mono space-x-2">
            <span className="text-danger font-medium tabular-nums">
              -{formatCurrency(summary?.total_debit_30d ?? 0)} out
            </span>
            <span>•</span>
            <span className="text-success font-medium tabular-nums">
              +{formatCurrency(summary?.total_credit_30d ?? 0)} in
            </span>
          </div>
        </div>
      </div>

      {/* 2. SARIMA Projected Next 30d Spend */}
      <div className="relative group bg-charcoal/90 hover:bg-charcoal border border-white/10 hover:border-cyber-yellow/40 rounded-[32px] p-6 backdrop-blur-2xl transition-all duration-300 shadow-glass flex flex-col justify-between overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
            SARIMA Projected Spend
          </span>
          <Pill variant="yellow" className="text-[9px] px-2.5 py-0.5">
            90% CI
          </Pill>
        </div>

        <div className="mt-4">
          <div className="text-3xl font-extrabold tracking-tight text-cyber-yellow font-sans tabular-nums">
            {formatCurrency(projSpend)}
          </div>
          <div className="mt-3 flex items-center space-x-2">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider ${
                isSpendIncreasing
                  ? "bg-danger/15 text-danger border border-danger/30"
                  : "bg-success/15 text-success border border-success/30"
              }`}
            >
              {isSpendIncreasing ? (
                <ArrowUpRight className="w-3 h-3 mr-0.5" />
              ) : (
                <ArrowDownRight className="w-3 h-3 mr-0.5" />
              )}
              {Math.abs(momDelta).toFixed(1)}% MoM
            </span>
            <span className="text-[11px] text-neutral-400">vs historical</span>
          </div>
        </div>
      </div>

      {/* 3. Daily Average Burn Rate */}
      <div className="relative group bg-charcoal/90 hover:bg-charcoal border border-white/10 hover:border-white/20 rounded-[32px] p-6 backdrop-blur-2xl transition-all duration-300 shadow-glass flex flex-col justify-between overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
            Daily Burn Velocity
          </span>
          <div className="w-7 h-7 rounded-full bg-deep-gray border border-white/10 flex items-center justify-center text-cyber-yellow">
            <Flame className="w-3.5 h-3.5" />
          </div>
        </div>

        <div className="mt-4">
          <div className="text-3xl font-extrabold tracking-tight text-white font-sans tabular-nums">
            {formatCurrency(dailyBurn)}
            <span className="text-xs font-normal text-neutral-400 ml-1 font-mono">/ day</span>
          </div>
          <div className="mt-3 flex items-center text-xs text-neutral-400 font-mono">
            <Activity className="w-3.5 h-3.5 mr-1.5 text-neutral-500" />
            <span className="tabular-nums">{summary?.recent_transactions_count ?? 0} txns recorded</span>
          </div>
        </div>
      </div>

      {/* 4. Model Accuracy & Order */}
      <div className="relative group bg-charcoal/90 hover:bg-charcoal border border-white/10 hover:border-white/20 rounded-[32px] p-6 backdrop-blur-2xl transition-all duration-300 shadow-glass flex flex-col justify-between overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
            SARIMA Model Quality
          </span>
          <div className="w-7 h-7 rounded-full bg-deep-gray border border-white/10 flex items-center justify-center text-white">
            <Cpu className="w-3.5 h-3.5" />
          </div>
        </div>

        <div className="mt-4">
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold tracking-tight text-white font-sans tabular-nums">
              {rmse !== null && rmse !== undefined
                ? `±$${rmse.toFixed(2)}`
                : txnCount === 0
                ? "N/A"
                : "Evaluating"}
            </span>
            <span className="text-[10px] text-neutral-400 font-mono tracking-widest">RMSE</span>
          </div>
          <div className="mt-3 flex items-center space-x-2 text-[10px] font-mono">
            <span
              className="px-2.5 py-0.5 rounded-full bg-deep-gray text-neutral-200 border border-white/10 truncate max-w-[130px]"
              title={sarimaOrder}
            >
              {sarimaOrder}
            </span>
            {aic !== null && aic !== undefined && (
              <span className="text-neutral-400 tabular-nums">AIC: {aic.toFixed(0)}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
