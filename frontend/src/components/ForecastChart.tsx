"use client";

import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { Calendar, AlertCircle, RefreshCw, BarChart3 } from "lucide-react";
import { ForecastResponse } from "../lib/types";

interface ForecastChartProps {
  forecastData: ForecastResponse | null;
  loading: boolean;
  granularity: "DAILY" | "WEEKLY";
  horizon: number;
  onGranularityChange: (g: "DAILY" | "WEEKLY") => void;
  onHorizonChange: (h: number) => void;
  onRefresh: () => void;
  height?: number;
  scenarioAdjustment?: number;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({
  forecastData,
  loading,
  granularity,
  horizon,
  onGranularityChange,
  onHorizonChange,
  onRefresh,
  height = 380,
  scenarioAdjustment = 0,
}) => {
  const [isMounted, setIsMounted] = React.useState(false);
  React.useEffect(() => {
    setIsMounted(true);
  }, []);

  // Chronological merge of actuals + forward predictions
  const chartData = useMemo(() => {
    if (!forecastData || forecastData.status === "EMPTY") return [];

    const data: Array<{
      date: string;
      actual?: number | null;
      predicted?: number | null;
      simulated?: number | null;
      ci_lower?: number | null;
      ci_spread?: number | null;
      lower_ci?: number | null;
      upper_ci?: number | null;
    }> = [];

    // Historical actuals
    (forecastData.historical_series || []).forEach((item) => {
      data.push({
        date: item.date,
        actual: item.actual,
        predicted: null,
        simulated: null,
        ci_lower: 0,
        ci_spread: 0,
      });
    });

    // Bridge the final historical point with forecast if present
    const lastHist = forecastData.historical_series?.[forecastData.historical_series.length - 1];
    if (lastHist && forecastData.forecast_payload?.length > 0) {
      const firstF = forecastData.forecast_payload[0];
      const simVal = scenarioAdjustment !== 0
        ? Math.max(0, firstF.predicted * (1 + scenarioAdjustment / 100))
        : null;
      data.push({
        date: firstF.date,
        actual: null,
        predicted: firstF.predicted,
        simulated: simVal,
        ci_lower: Math.max(0, firstF.lower_ci),
        ci_spread: Math.max(0, firstF.upper_ci - firstF.lower_ci),
        lower_ci: firstF.lower_ci,
        upper_ci: firstF.upper_ci,
      });
    }

    // Remaining forecast points
    (forecastData.forecast_payload || []).slice(1).forEach((item) => {
      const lower = Math.max(0, item.lower_ci);
      const upper = Math.max(lower, item.upper_ci);
      const simVal = scenarioAdjustment !== 0
        ? Math.max(0, item.predicted * (1 + scenarioAdjustment / 100))
        : null;
      data.push({
        date: item.date,
        actual: null,
        predicted: item.predicted,
        simulated: simVal,
        ci_lower: lower,
        ci_spread: Math.max(0, upper - lower),
        lower_ci: item.lower_ci,
        upper_ci: item.upper_ci,
      });
    });

    return data;
  }, [forecastData, scenarioAdjustment]);

  // Clean financial tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null;

    const actualVal = payload.find((p: any) => p.dataKey === "actual")?.value;
    const predVal = payload.find((p: any) => p.dataKey === "predicted")?.value;
    const simVal = payload.find((p: any) => p.dataKey === "simulated")?.value;
    const point = payload[0]?.payload;

    return (
      <div className="bg-slate-900 border border-slate-700/80 rounded-lg p-3 text-xs shadow-xl font-mono">
        <div className="text-slate-400 mb-2 font-sans font-medium text-[11px] pb-1 border-b border-slate-800">
          {label}
        </div>
        {actualVal !== null && actualVal !== undefined && (
          <div className="flex items-center justify-between space-x-4 text-emerald-400 py-0.5">
            <span>Historical Actual:</span>
            <span className="font-bold">${(Number(actualVal) || 0).toFixed(2)}</span>
          </div>
        )}
        {predVal !== null && predVal !== undefined && (
          <div className="flex items-center justify-between space-x-4 text-blue-400 py-0.5">
            <span>SARIMA Forecast:</span>
            <span className="font-bold">${(Number(predVal) || 0).toFixed(2)}</span>
          </div>
        )}
        {simVal !== null && simVal !== undefined && (
          <div className="flex items-center justify-between space-x-4 text-amber-400 py-0.5">
            <span>Simulated ({scenarioAdjustment > 0 ? `+${scenarioAdjustment}` : scenarioAdjustment}%):</span>
            <span className="font-bold">${(Number(simVal) || 0).toFixed(2)}</span>
          </div>
        )}
        {point?.lower_ci !== undefined && point?.upper_ci !== undefined && (
          <div className="mt-1 pt-1.5 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between space-x-2">
            <span>90% Confidence Interval:</span>
            <span className="text-slate-200">
              [${(Number(point.lower_ci) || 0).toFixed(2)}, ${(Number(point.upper_ci) || 0).toFixed(2)}]
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle flex flex-col justify-between">
      {/* Top Controls Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-border/60">
        <div>
          <div className="flex items-center space-x-2.5 flex-wrap gap-y-1">
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Spending Forecast & Confidence Ribbon
            </h2>
            {scenarioAdjustment !== 0 && (
              <span
                className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-mono border font-semibold ${
                  scenarioAdjustment > 0
                    ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                    : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                }`}
              >
                <span>Simulated: {scenarioAdjustment > 0 ? `+${scenarioAdjustment}` : scenarioAdjustment}%</span>
              </span>
            )}
            {forecastData?.fallback_used && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <AlertCircle className="w-3 h-3" />
                <span>Cold Start Fallback</span>
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Historical daily debit series vs. forward SARIMA projection with 90% confidence bands
          </p>
        </div>

        {/* Granularity & Horizon Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Granularity Toggle */}
          <div className="flex items-center bg-slate-900 p-0.5 rounded-lg border border-border text-xs">
            <button
              onClick={() => onGranularityChange("DAILY")}
              className={`px-3 py-1 text-xs rounded-md font-medium transition ${
                granularity === "DAILY"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              Daily (s=7)
            </button>
            <button
              onClick={() => onGranularityChange("WEEKLY")}
              className={`px-3 py-1 text-xs rounded-md font-medium transition ${
                granularity === "WEEKLY"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              Weekly (s=4)
            </button>
          </div>

          {/* Horizon Selector */}
          <div className="flex items-center bg-slate-900 p-0.5 rounded-lg border border-border text-xs">
            {[14, 30, 60, 90].map((h) => (
              <button
                key={h}
                onClick={() => onHorizonChange(h)}
                className={`px-2.5 py-1 text-xs rounded-md font-medium transition ${
                  horizon === h
                    ? "bg-slate-700 text-white shadow-sm font-semibold"
                    : "text-muted-foreground hover:text-white"
                }`}
              >
                {h}d
              </button>
            ))}
          </div>

          {/* Refit Model Button */}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-1.5 rounded-lg bg-slate-900 border border-border hover:bg-slate-800 text-muted-foreground hover:text-white transition disabled:opacity-50"
            title="Refit SARIMA parameters"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div style={{ height: `${height}px` }} className="mt-5 w-full">
        {loading || !isMounted ? (
          <div className="h-full flex flex-col items-center justify-center space-y-3">
            <RefreshCw className="w-7 h-7 text-blue-500 animate-spin" />
            <p className="text-xs text-muted-foreground font-mono">
              {!isMounted ? "Initializing visualization engine..." : "Running AIC Grid Search & Stationarity Tests..."}
            </p>
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center space-y-2 border border-dashed border-border/80 rounded-xl p-6 text-center">
            <BarChart3 className="w-10 h-10 text-slate-600" />
            <p className="text-sm font-medium text-slate-300">
              {forecastData?.status === "EMPTY" && forecastData?.model_notes
                ? forecastData.model_notes
                : "No historical transaction series to plot"}
            </p>
            <p className="text-xs text-muted-foreground max-w-sm">
              Upload a bank statement (PDF or image) to extract transaction records and fit the time-series model.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="ciGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.22} />
                  <stop offset="100%" stopColor="#3B82F6" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
              <XAxis
                dataKey="date"
                stroke="#64748B"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#1E293B" }}
                tickFormatter={(val) => {
                  const parts = val.split("-");
                  return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : val;
                }}
              />
              <YAxis
                stroke="#64748B"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#1E293B" }}
                tickFormatter={(v) => `$${v}`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                verticalAlign="top"
                height={32}
                formatter={(value) => {
                  if (value === "actual") return <span className="text-xs text-emerald-400 font-medium">Historical Spend</span>;
                  if (value === "predicted") return <span className="text-xs text-blue-400 font-medium">SARIMA Baseline</span>;
                  if (value === "simulated") return <span className="text-xs text-amber-400 font-medium">Simulated Scenario</span>;
                  if (value === "ci_spread") return <span className="text-xs text-blue-300/80 font-medium">90% Confidence Interval</span>;
                  return value;
                }}
              />

              {/* Stacked Confidence Interval Ribbon: Invisible base + translucent fill */}
              <Area
                type="monotone"
                dataKey="ci_lower"
                stackId="ci"
                stroke="none"
                fill="transparent"
                isAnimationActive={false}
                legendType="none"
              />
              <Area
                name="ci_spread"
                type="monotone"
                dataKey="ci_spread"
                stackId="ci"
                stroke="none"
                fill="url(#ciGradient)"
                isAnimationActive={false}
              />

              {/* Historical Spend Actuals */}
              <Line
                name="actual"
                type="monotone"
                dataKey="actual"
                stroke="#10B981"
                strokeWidth={2}
                dot={{ r: 2, fill: "#10B981" }}
                activeDot={{ r: 4, fill: "#10B981" }}
                connectNulls={false}
              />

              {/* SARIMA Forecast Line */}
              <Line
                name="predicted"
                type="monotone"
                dataKey="predicted"
                stroke="#3B82F6"
                strokeWidth={2.2}
                strokeDasharray="4 4"
                dot={{ r: 3, fill: "#3B82F6" }}
                activeDot={{ r: 5, fill: "#60A5FA" }}
                connectNulls={true}
              />

              {/* Optional Simulated Scenario Line */}
              {scenarioAdjustment !== 0 && (
                <Line
                  name="simulated"
                  type="monotone"
                  dataKey="simulated"
                  stroke="#F59E0B"
                  strokeWidth={2.2}
                  strokeDasharray="2 2"
                  dot={{ r: 3, fill: "#F59E0B" }}
                  activeDot={{ r: 5, fill: "#FBBF24" }}
                  connectNulls={true}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Model Diagnostics Footnote */}
      {forecastData?.model_notes && (
        <div className="mt-4 pt-3 border-t border-border/60 text-[11px] text-muted-foreground font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <span>{forecastData.model_notes}</span>
          <span className="text-slate-300">
            SARIMA Order: <span className="text-blue-400 font-semibold">{forecastData.sarima_order || "None"}</span>
          </span>
        </div>
      )}
    </div>
  );
};
