"use client";

import React from "react";
import {
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Receipt,
  Flame,
  Cpu,
  Wallet,
} from "lucide-react";
import { AnalyticsSummary } from "../lib/types";

interface KpiRibbonProps {
  summary: AnalyticsSummary | null;
  loading: boolean;
}

export const KpiRibbon: React.FC<KpiRibbonProps> = ({ summary, loading }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-32 rounded-xl bg-card border border-border/80 animate-pulse p-5 flex flex-col justify-between"
          >
            <div className="h-3 bg-slate-800 rounded w-1/3"></div>
            <div className="h-7 bg-slate-800 rounded w-2/3"></div>
            <div className="h-3 bg-slate-800 rounded w-1/2"></div>
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
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Historical 30d Spend */}
      <div className="bg-card border border-border/80 rounded-xl p-5 hover:border-slate-700 transition shadow-subtle flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            30-Day Historical Spend
          </span>
          <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Wallet className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl font-bold tracking-tight text-white font-mono">
            ${histSpend.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-2.5 flex items-center text-[11px] text-muted-foreground space-x-2">
            <span className="text-rose-400 font-mono">
              -${(summary?.total_debit_30d ?? 0).toFixed(2)} out
            </span>
            <span>•</span>
            <span className="text-emerald-400 font-mono">
              +${(summary?.total_credit_30d ?? 0).toFixed(2)} in
            </span>
          </div>
        </div>
      </div>

      {/* 2. SARIMA Projected Next 30d Spend */}
      <div className="bg-card border border-border/80 rounded-xl p-5 hover:border-slate-700 transition shadow-subtle flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            SARIMA Projected Spend
          </span>
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <TrendingUp className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl font-bold tracking-tight text-white font-mono">
            ${projSpend.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-2.5 flex items-center space-x-2">
            <span
              className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono font-medium ${
                isSpendIncreasing
                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                  : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
              }`}
            >
              {isSpendIncreasing ? (
                <ArrowUpRight className="w-3 h-3 mr-0.5" />
              ) : (
                <ArrowDownRight className="w-3 h-3 mr-0.5" />
              )}
              {Math.abs(momDelta).toFixed(1)}% MoM
            </span>
            <span className="text-[11px] text-muted-foreground">vs historical 30d</span>
          </div>
        </div>
      </div>

      {/* 3. Daily Average Burn Rate */}
      <div className="bg-card border border-border/80 rounded-xl p-5 hover:border-slate-700 transition shadow-subtle flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            Daily Average Burn
          </span>
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Flame className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl font-bold tracking-tight text-white font-mono">
            ${dailyBurn.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            <span className="text-xs font-normal text-muted-foreground ml-1">/ day</span>
          </div>
          <div className="mt-2.5 flex items-center text-[11px] text-muted-foreground">
            <Receipt className="w-3.5 h-3.5 mr-1 text-slate-400" />
            <span>{summary?.recent_transactions_count ?? 0} transactions (30d window)</span>
          </div>
        </div>
      </div>

      {/* 4. Model Accuracy & Order */}
      <div className="bg-card border border-border/80 rounded-xl p-5 hover:border-slate-700 transition shadow-subtle flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            SARIMA Model Quality
          </span>
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Cpu className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold tracking-tight text-white font-mono">
              {rmse !== null && rmse !== undefined
                ? `±$${rmse.toFixed(2)}`
                : txnCount === 0
                ? "N/A"
                : "Evaluating"}
            </span>
            <span className="text-[11px] text-muted-foreground font-mono">RMSE</span>
          </div>
          <div className="mt-2.5 flex items-center space-x-2 text-[11px] font-mono">
            <span
              className="px-1.5 py-0.5 rounded bg-slate-800 text-blue-300 border border-slate-700 truncate max-w-[140px]"
              title={sarimaOrder}
            >
              {sarimaOrder}
            </span>
            {aic !== null && aic !== undefined && (
              <span className="text-muted-foreground">AIC: {aic.toFixed(0)}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
