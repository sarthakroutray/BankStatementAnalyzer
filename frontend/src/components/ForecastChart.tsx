"use client";

import React, { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { AlertCircle, RefreshCw, BarChart3, SlidersHorizontal } from "lucide-react";
import { ForecastResponse } from "../lib/types";
import { Pill } from "./ui/Pill";
import { Button } from "./ui/Button";

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
  height = 420,
  scenarioAdjustment = 0,
}) => {
  const [isMounted, setIsMounted] = useState(false);
  const [timeRange, setTimeRange] = useState<"3M" | "6M" | "12M" | "ALL">("ALL");

  React.useEffect(() => {
    setIsMounted(true);
  }, []);

  // Chronological merge of actuals + forward predictions
  const { chartData, forecastStartDate } = useMemo(() => {
    if (!forecastData || forecastData.status === "EMPTY") {
      return { chartData: [], forecastStartDate: null };
    }

    const rawData: Array<{
      date: string;
      actual?: number | null;
      predicted?: number | null;
      simulated?: number | null;
      ci_lower?: number | null;
      ci_spread?: number | null;
      lower_ci?: number | null;
      upper_ci?: number | null;
      isForecast?: boolean;
    }> = [];

    // Historical actuals
    (forecastData.historical_series || []).forEach((item) => {
      rawData.push({
        date: item.date,
        actual: item.actual,
        predicted: null,
        simulated: null,
        ci_lower: 0,
        ci_spread: 0,
        isForecast: false,
      });
    });

    let startDate: string | null = null;

    // Bridge the final historical point with forecast if present
    const lastHist = forecastData.historical_series?.[forecastData.historical_series.length - 1];
    if (lastHist && forecastData.forecast_payload?.length > 0) {
      const firstF = forecastData.forecast_payload[0];
      startDate = firstF.date;
      const simVal =
        scenarioAdjustment !== 0
          ? Math.max(0, firstF.predicted * (1 + scenarioAdjustment / 100))
          : null;
      rawData.push({
        date: firstF.date,
        actual: null,
        predicted: firstF.predicted,
        simulated: simVal,
        ci_lower: Math.max(0, firstF.lower_ci),
        ci_spread: Math.max(0, firstF.upper_ci - firstF.lower_ci),
        lower_ci: firstF.lower_ci,
        upper_ci: firstF.upper_ci,
        isForecast: true,
      });
    }

    // Remaining forecast points
    (forecastData.forecast_payload || []).slice(1).forEach((item) => {
      const lower = Math.max(0, item.lower_ci);
      const upper = Math.max(lower, item.upper_ci);
      const simVal =
        scenarioAdjustment !== 0
          ? Math.max(0, item.predicted * (1 + scenarioAdjustment / 100))
          : null;
      rawData.push({
        date: item.date,
        actual: null,
        predicted: item.predicted,
        simulated: simVal,
        ci_lower: lower,
        ci_spread: Math.max(0, upper - lower),
        lower_ci: item.lower_ci,
        upper_ci: item.upper_ci,
        isForecast: true,
      });
    });

    // Client-side slice based on range selector
    if (timeRange === "ALL" || rawData.length === 0) {
      return { chartData: rawData, forecastStartDate: startDate };
    }

    const daysCount = timeRange === "3M" ? 90 : timeRange === "6M" ? 180 : 365;
    const histItems = rawData.filter((d) => !d.isForecast);
    const forecastItems = rawData.filter((d) => d.isForecast);

    const slicedHist = histItems.slice(-daysCount);
    return {
      chartData: [...slicedHist, ...forecastItems],
      forecastStartDate: startDate,
    };
  }, [forecastData, scenarioAdjustment, timeRange]);

  // Clean financial glass tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null;

    const actualVal = payload.find((p: any) => p.dataKey === "actual")?.value;
    const predVal = payload.find((p: any) => p.dataKey === "predicted")?.value;
    const simVal = payload.find((p: any) => p.dataKey === "simulated")?.value;
    const point = payload[0]?.payload;

    return (
      <div className="bg-charcoal/95 border border-white/20 rounded-[20px] p-4 text-xs shadow-2xl backdrop-blur-2xl font-mono text-white min-w-[200px]">
        <div className="text-neutral-400 mb-2 font-sans font-medium text-[11px] pb-1.5 border-b border-white/10 flex items-center justify-between">
          <span>{label}</span>
          <span className="text-[9px] uppercase tracking-wider text-cyber-yellow font-bold">
            {point?.isForecast ? "Projected" : "Historical"}
          </span>
        </div>

        {actualVal !== null && actualVal !== undefined && (
          <div className="flex items-center justify-between space-x-4 text-cyber-yellow py-0.5">
            <span className="text-neutral-300 font-sans">Historical Actual:</span>
            <span className="font-bold tabular-nums">${(Number(actualVal) || 0).toFixed(2)}</span>
          </div>
        )}

        {predVal !== null && predVal !== undefined && (
          <div className="flex items-center justify-between space-x-4 text-white py-0.5">
            <span className="text-neutral-300 font-sans">SARIMA Forecast:</span>
            <span className="font-bold tabular-nums">${(Number(predVal) || 0).toFixed(2)}</span>
          </div>
        )}

        {simVal !== null && simVal !== undefined && (
          <div className="flex items-center justify-between space-x-4 text-amber-400 py-0.5">
            <span className="text-neutral-300 font-sans">
              Simulated ({scenarioAdjustment > 0 ? `+${scenarioAdjustment}` : scenarioAdjustment}%):
            </span>
            <span className="font-bold tabular-nums">${(Number(simVal) || 0).toFixed(2)}</span>
          </div>
        )}

        {point?.lower_ci !== undefined && point?.upper_ci !== undefined && (
          <div className="mt-2 pt-2 border-t border-white/10 text-[10px] text-neutral-400 flex items-center justify-between space-x-2">
            <span className="font-sans">90% CI:</span>
            <span className="text-neutral-200 tabular-nums font-semibold">
              [${(Number(point.lower_ci) || 0).toFixed(2)}, ${(Number(point.upper_ci) || 0).toFixed(2)}]
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-8 shadow-glass flex flex-col justify-between backdrop-blur-2xl">
      {/* Top Header & Interactive Controls Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5 pb-6 border-b border-white/10">
        <div>
          <div className="flex items-center space-x-3 flex-wrap gap-y-2">
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight font-sans">
              Spending Forecast & Confidence Ribbon
            </h2>
            <Pill variant="yellow">90% CI</Pill>
            {scenarioAdjustment !== 0 && (
              <Pill variant="glass">
                Simulated: {scenarioAdjustment > 0 ? `+${scenarioAdjustment}` : scenarioAdjustment}%
              </Pill>
            )}
            {forecastData?.fallback_used && (
              <Pill variant="neutral" className="text-amber-400 border-amber-400/30">
                Fallback Used
              </Pill>
            )}
          </div>
          <p className="text-xs sm:text-sm text-neutral-400 mt-1">
            Deterministic daily ledger series projected forward with bounded SARIMA time-series ribbons
          </p>
        </div>

        {/* Filter Controls: Granularity, Horizon, Range & Refresh */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Time Range Slicer */}
          <div className="flex items-center p-1 rounded-full bg-deep-gray border border-white/10 text-xs">
            {(["3M", "6M", "12M", "ALL"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-3 py-1 rounded-full text-xs font-mono font-semibold transition-all duration-200 ${
                  timeRange === r
                    ? "bg-white text-black shadow-sm"
                    : "text-neutral-400 hover:text-white"
                }`}
              >
                {r}
              </button>
            ))}
          </div>

          {/* Granularity Toggle */}
          <div className="flex items-center p-1 rounded-full bg-deep-gray border border-white/10 text-xs">
            <button
              onClick={() => onGranularityChange("DAILY")}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-200 ${
                granularity === "DAILY"
                  ? "bg-cyber-yellow text-black font-bold shadow-sm"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              Daily (s=7)
            </button>
            <button
              onClick={() => onGranularityChange("WEEKLY")}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-200 ${
                granularity === "WEEKLY"
                  ? "bg-cyber-yellow text-black font-bold shadow-sm"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              Weekly (s=4)
            </button>
          </div>

          {/* Horizon Selector */}
          <div className="flex items-center p-1 rounded-full bg-deep-gray border border-white/10 text-xs">
            {[14, 30, 60, 90].map((h) => (
              <button
                key={h}
                onClick={() => onHorizonChange(h)}
                className={`px-2.5 py-1 rounded-full text-xs font-mono font-semibold transition-all duration-200 ${
                  horizon === h
                    ? "bg-white/20 text-white font-bold"
                    : "text-neutral-400 hover:text-white"
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
            className="w-8 h-8 rounded-full bg-deep-gray border border-white/10 hover:border-white/30 flex items-center justify-center text-neutral-300 hover:text-white transition-all duration-200 disabled:opacity-50 active:scale-95"
            title="Refit SARIMA parameters"
            aria-label="Refit model"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-cyber-yellow" : ""}`} />
          </button>
        </div>
      </div>

      {/* Legend Chips */}
      <div className="flex flex-wrap items-center gap-3 pt-4 text-xs font-mono">
        <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-deep-gray border border-white/10">
          <span className="w-2.5 h-2.5 rounded-full bg-cyber-yellow" />
          <span className="text-white font-medium">Historical Spend</span>
        </div>
        <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-deep-gray border border-white/10">
          <span className="w-3.5 h-0.5 border-b-2 border-dashed border-white" />
          <span className="text-white font-medium">SARIMA Forecast</span>
        </div>
        <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-deep-gray border border-white/10">
          <span className="w-3.5 h-2 rounded bg-cyber-yellow/20 border border-cyber-yellow/40" />
          <span className="text-white font-medium">90% Confidence Ribbon</span>
        </div>
        {scenarioAdjustment !== 0 && (
          <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-deep-gray border border-white/10">
            <span className="w-3.5 h-0.5 border-b-2 border-dotted border-amber-400" />
            <span className="text-amber-400 font-medium">Simulated</span>
          </div>
        )}
      </div>

      {/* Chart Canvas */}
      <div style={{ height: `${height}px` }} className="mt-4 w-full">
        {loading || !isMounted ? (
          <div className="h-full flex flex-col items-center justify-center space-y-3">
            <RefreshCw className="w-8 h-8 text-cyber-yellow animate-spin" />
            <p className="text-xs text-neutral-400 font-mono tracking-widest uppercase">
              {!isMounted ? "Initializing visualization engine..." : "Fitting SARIMA Parameters & AIC Grid..."}
            </p>
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center space-y-3 border-2 border-dashed border-white/10 rounded-[28px] p-8 text-center bg-white/[0.02]">
            <div className="w-12 h-12 rounded-full bg-deep-gray flex items-center justify-center text-neutral-400">
              <BarChart3 className="w-6 h-6" />
            </div>
            <p className="text-base font-semibold text-white">
              {forecastData?.status === "EMPTY" && forecastData?.model_notes
                ? forecastData.model_notes
                : "No historical transaction series to plot"}
            </p>
            <p className="text-xs text-neutral-400 max-w-md leading-relaxed">
              Upload a bank statement PDF to extract transaction tables and calibrate the forward SARIMA time-series forecast.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 15, right: 20, left: 10, bottom: 0 }}>
              <defs>
                {/* 90% Confidence Ribbon Gradient */}
                <linearGradient id="fanRibbonGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#FDE047" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#FFFFFF" stopOpacity={0.06} />
                </linearGradient>
                {/* Historical Area Fill Gradient */}
                <linearGradient id="historicalSpendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#FDE047" stopOpacity={0.20} />
                  <stop offset="100%" stopColor="#FDE047" stopOpacity={0.0} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="2 4" stroke="#262626" vertical={false} />

              <XAxis
                dataKey="date"
                stroke="#737373"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#262626" }}
                tickFormatter={(val) => {
                  const parts = val.split("-");
                  return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : val;
                }}
              />
              <YAxis
                stroke="#737373"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#262626" }}
                tickFormatter={(v) => `$${v}`}
              />

              <Tooltip content={<CustomTooltip />} />

              {/* Vertical line where forecast begins */}
              {forecastStartDate && (
                <ReferenceLine
                  x={forecastStartDate}
                  stroke="#737373"
                  strokeDasharray="3 3"
                  label={{
                    value: "Forecast starts",
                    fill: "#A3A3A3",
                    fontSize: 10,
                    position: "top",
                  }}
                />
              )}

              {/* 1. Stacked Confidence Interval Ribbon: Invisible base + translucent fan fill */}
              <Area
                type="monotone"
                dataKey="ci_lower"
                stackId="ci"
                stroke="none"
                fill="transparent"
                isAnimationActive={false}
              />
              <Area
                name="ci_spread"
                type="monotone"
                dataKey="ci_spread"
                stackId="ci"
                stroke="none"
                fill="url(#fanRibbonGradient)"
                isAnimationActive={false}
              />

              {/* 2. Soft Area under Historical Spend */}
              <Area
                type="monotone"
                dataKey="actual"
                stroke="none"
                fill="url(#historicalSpendFill)"
                isAnimationActive={false}
              />

              {/* 3. Historical Spend Actuals: Solid Flat Cyber-Yellow */}
              <Line
                name="actual"
                type="monotone"
                dataKey="actual"
                stroke="#FDE047"
                strokeWidth={2.5}
                dot={{ r: 2.5, fill: "#FDE047" }}
                activeDot={{ r: 5, fill: "#FDE047" }}
                connectNulls={false}
              />

              {/* 4. SARIMA Forecast: Dashed White Line */}
              <Line
                name="predicted"
                type="monotone"
                dataKey="predicted"
                stroke="#FFFFFF"
                strokeWidth={2.2}
                strokeDasharray="4 4"
                dot={{ r: 3, fill: "#FFFFFF" }}
                activeDot={{ r: 5, fill: "#FFFFFF" }}
                connectNulls={true}
              />

              {/* 5. Optional Simulated Scenario Line */}
              {scenarioAdjustment !== 0 && (
                <Line
                  name="simulated"
                  type="monotone"
                  dataKey="simulated"
                  stroke="#F59E0B"
                  strokeWidth={2}
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
        <div className="mt-6 pt-4 border-t border-white/10 text-xs text-neutral-400 font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <span>{forecastData.model_notes}</span>
          <span className="text-white">
            SARIMA Order:{" "}
            <span className="text-cyber-yellow font-bold">{forecastData.sarima_order || "None"}</span>
          </span>
        </div>
      )}
    </div>
  );
};
