"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { Footer } from "../../components/Footer";
import { ForecastChart } from "../../components/ForecastChart";
import { UploadModal } from "../../components/UploadModal";
import { fetchLatestForecast, generateForecast } from "../../lib/api";
import { ForecastResponse } from "../../lib/types";
import {
  LineChart,
  Cpu,
  Sliders,
  TrendingDown,
  TrendingUp,
  Download,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  HelpCircle,
  Layers,
  ArrowRight,
} from "lucide-react";

export default function ForecastStudioPage() {
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [granularity, setGranularity] = useState<"DAILY" | "WEEKLY">("DAILY");
  const [horizon, setHorizon] = useState<number>(30);

  // Scenario Simulator: Percentage adjustment (-30% to +30%)
  const [scenarioAdjustment, setScenarioAdjustment] = useState<number>(0);

  const isMounted = useRef(false);

  const loadForecast = useCallback(
    async (refresh: boolean = false, g = granularity, h = horizon) => {
      setLoading(true);
      try {
        const data = refresh
          ? await generateForecast(g, h)
          : await fetchLatestForecast(g, h);
        setForecast(data);
      } catch (err: unknown) {
        console.error("Forecast error:", err);
        setForecast(null);
      } finally {
        setLoading(false);
      }
    },
    [granularity, horizon]
  );

  useEffect(() => {
    if (!isMounted.current) {
      isMounted.current = true;
      loadForecast(false);
      return;
    }
    loadForecast(true);
  }, [granularity, horizon]);

  // Aggregate forecast totals
  const totalProjected = useMemo(() => {
    if (!forecast?.forecast_payload) return 0;
    return forecast.forecast_payload.reduce((acc, pt) => acc + (pt.predicted || 0), 0);
  }, [forecast]);

  const simulatedProjected = useMemo(() => {
    return totalProjected * (1 + scenarioAdjustment / 100);
  }, [totalProjected, scenarioAdjustment]);

  // Export forecast projection points to CSV
  const handleExportForecast = () => {
    if (!forecast?.forecast_payload?.length) return;
    const headers = ["Date", "Predicted Spend", "Lower 90% CI", "Upper 90% CI"];
    const rows = forecast.forecast_payload.map((pt) => [
      pt.date,
      pt.predicted.toFixed(2),
      pt.lower_ci.toFixed(2),
      pt.upper_ci.toFixed(2),
    ]);
    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `sarima_forecast_${granularity.toLowerCase()}_${horizon}d.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen flex flex-col bg-canvas selection:bg-blue-600/30 selection:text-white">
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Header Breadcrumbs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
          <div>
            <div className="flex items-center space-x-2 text-xs text-muted-foreground font-mono mb-1">
              <Link href="/" className="hover:text-white transition">
                OVERVIEW
              </Link>
              <span>/</span>
              <span className="text-blue-400">SARIMA FORECAST STUDIO</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white font-sans">
              Predictive Spending Engine & Diagnostics
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Seasonal Autoregressive Integrated Moving Average (SARIMA) forecasting with 90% parameter confidence bands
            </p>
          </div>

          <div className="flex items-center space-x-2.5">
            <button
              onClick={() => loadForecast(true)}
              disabled={loading}
              className="flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-border text-xs font-medium transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-blue-400" : ""}`} />
              <span>Refit Model</span>
            </button>
            <button
              onClick={handleExportForecast}
              disabled={!forecast?.forecast_payload?.length}
              className="flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition disabled:opacity-40"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export Projections</span>
            </button>
          </div>
        </div>

        {/* 1. Main Forecast Fan Chart */}
        <section aria-label="SARIMA Forecast Canvas">
          <ForecastChart
            forecastData={forecast}
            loading={loading}
            granularity={granularity}
            horizon={horizon}
            onGranularityChange={(g) => setGranularity(g)}
            onHorizonChange={(h) => setHorizon(h)}
            onRefresh={() => loadForecast(true)}
            height={440}
            scenarioAdjustment={scenarioAdjustment}
          />
        </section>

        {/* 2. Statistical Diagnostics & Scenario Simulation Grid */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Model Diagnostics Card */}
          <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle flex flex-col justify-between">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <Cpu className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-bold text-white tracking-tight">Model Diagnostics</h3>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Statistical fit parameters and loss metrics
              </p>

              <div className="mt-4 space-y-3 font-mono text-xs">
                <div className="p-3 rounded-lg bg-slate-900 border border-border/80 flex items-center justify-between">
                  <span className="text-slate-400 text-[11px] font-sans">SARIMA Order</span>
                  <span className="text-blue-400 font-bold">
                    {forecast?.sarima_order || "None"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-slate-900 border border-border/80">
                    <span className="text-slate-400 text-[11px] font-sans block mb-1">RMSE Error</span>
                    <span className="text-white font-bold text-sm">
                      {forecast?.rmse !== null && forecast?.rmse !== undefined
                        ? `±$${forecast.rmse.toFixed(2)}`
                        : "N/A"}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-border/80">
                    <span className="text-slate-400 text-[11px] font-sans block mb-1">Akaike IC (AIC)</span>
                    <span className="text-white font-bold text-sm">
                      {forecast?.aic !== null && forecast?.aic !== undefined
                        ? forecast.aic.toFixed(1)
                        : "N/A"}
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-900 border border-border/80 space-y-1.5 text-[11px]">
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="font-sans">Seasonality (s):</span>
                    <span className="font-bold text-white">
                      {granularity === "DAILY" ? "s = 7 (Weekly)" : "s = 4 (Monthly)"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="font-sans">Confidence Band:</span>
                    <span className="font-bold text-emerald-400">90% Parametric</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="font-sans">Fallback Applied:</span>
                    <span className={forecast?.fallback_used ? "text-amber-400" : "text-slate-400"}>
                      {forecast?.fallback_used ? "Yes (Cold Start)" : "No (Auto-ARIMA)"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-border/60 text-[11px] text-muted-foreground leading-relaxed">
              Model parameters are tuned via Stepwise AIC optimization across non-seasonal (p,d,q) and seasonal (P,D,Q)s orders.
            </div>
          </div>

          {/* Interactive Scenario Stress-Tester */}
          <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle flex flex-col justify-between">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <Sliders className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-bold text-white tracking-tight">Scenario Simulator</h3>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Simulate spending adjustments & test budget sensitivity
              </p>

              <div className="mt-4 space-y-4">
                <div>
                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="text-slate-300 font-medium">Spending Delta:</span>
                    <span
                      className={`font-mono font-bold px-2 py-0.5 rounded text-xs ${
                        scenarioAdjustment > 0
                          ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                          : scenarioAdjustment < 0
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-slate-800 text-slate-300"
                      }`}
                    >
                      {scenarioAdjustment > 0 ? "+" : ""}
                      {scenarioAdjustment}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="-30"
                    max="30"
                    step="5"
                    value={scenarioAdjustment}
                    onChange={(e) => setScenarioAdjustment(parseInt(e.target.value, 10))}
                    className="w-full accent-blue-600 bg-slate-800 rounded-lg h-2 cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
                    <span>-30% Cut</span>
                    <span>Baseline (0%)</span>
                    <span>+30% Surge</span>
                  </div>
                </div>

                <div className="p-3.5 rounded-lg bg-slate-900 border border-border/80 space-y-2 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 font-sans text-[11px]">Baseline Projected:</span>
                    <span className="text-white font-semibold">
                      ${totalProjected.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-1 border-t border-slate-800">
                    <span className="text-slate-300 font-sans text-[11px]">Simulated Total:</span>
                    <span className="text-base font-bold text-blue-400">
                      ${simulatedProjected.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-1 border-t border-slate-800 text-[11px]">
                    <span className="text-slate-400 font-sans">Variance Impact:</span>
                    <span
                      className={
                        simulatedProjected - totalProjected > 0
                          ? "text-rose-400 font-bold"
                          : simulatedProjected - totalProjected < 0
                          ? "text-emerald-400 font-bold"
                          : "text-slate-400"
                      }
                    >
                      {simulatedProjected - totalProjected > 0 ? "+" : ""}
                      ${(simulatedProjected - totalProjected).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <button
              onClick={() => setScenarioAdjustment(0)}
              className="mt-4 w-full py-1.5 text-xs text-slate-400 hover:text-white bg-slate-900 hover:bg-slate-800 rounded-lg border border-border transition"
            >
              Reset Simulation to Baseline
            </button>
          </div>

          {/* Quick Guidance / Methodology Card */}
          <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle flex flex-col justify-between">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <HelpCircle className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-bold text-white tracking-tight">Methodology</h3>
              </div>
              <p className="text-[11px] text-muted-foreground">
                How FinWise models debit expenditure
              </p>

              <div className="mt-4 space-y-3 text-xs text-slate-300 leading-relaxed">
                <p>
                  <strong className="text-white">1. Stationarity Differentiation:</strong> Ingested daily debit series are tested for unit roots and differenced (d=1, D=1) to eliminate trends.
                </p>
                <p>
                  <strong className="text-white">2. Seasonality Fitting:</strong> Calendar recurrence (e.g. rent, payroll, weekend spending spikes) is captured via 7-day or monthly cyclic orders.
                </p>
                <p>
                  <strong className="text-white">3. Confidence Intervals:</strong> Error variances propagate through the forecast horizon to generate institutional 90% confidence ribbons.
                </p>
              </div>
            </div>

            <Link
              href="/statements"
              className="mt-4 inline-flex items-center justify-center space-x-1.5 w-full py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-blue-400 hover:text-blue-300 border border-border text-xs font-medium transition"
            >
              <span>Add Statements for Calibration</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </section>

        {/* 3. Forecast Projections Table */}
        <section aria-label="Forecast Data Points">
          <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle">
            <div className="flex items-center justify-between pb-4 border-b border-border/60">
              <div>
                <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                  Forward Forecast Steps ({forecast?.forecast_payload?.length || 0} intervals)
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Point estimates and 90% confidence bounds generated by the fitted model
                </p>
              </div>
              <button
                onClick={handleExportForecast}
                disabled={!forecast?.forecast_payload?.length}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-border text-xs font-medium transition disabled:opacity-40"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export CSV</span>
              </button>
            </div>

            <div className="overflow-x-auto mt-4 max-h-96">
              <table className="w-full text-left text-xs font-mono">
                <thead className="sticky top-0 bg-card border-b border-border/80 text-muted-foreground uppercase tracking-wider text-[11px] font-sans">
                  <tr>
                    <th className="py-2.5 px-3">Date</th>
                    <th className="py-2.5 px-3 text-right">Predicted Spend</th>
                    <th className="py-2.5 px-3 text-right">Lower Bound (90% CI)</th>
                    <th className="py-2.5 px-3 text-right">Upper Bound (90% CI)</th>
                    <th className="py-2.5 px-3 text-right">Spread</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {!forecast?.forecast_payload?.length ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-muted-foreground font-sans">
                        No forecast intervals generated. Upload statement records to compute projections.
                      </td>
                    </tr>
                  ) : (
                    forecast.forecast_payload.map((pt) => {
                      const spread = Math.max(0, pt.upper_ci - pt.lower_ci);
                      return (
                        <tr key={pt.date} className="hover:bg-slate-900/50 transition">
                          <td className="py-2.5 px-3 text-slate-300 font-sans font-medium">{pt.date}</td>
                          <td className="py-2.5 px-3 text-right text-blue-400 font-bold">
                            ${pt.predicted.toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 text-right text-slate-400">
                            ${Math.max(0, pt.lower_ci).toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 text-right text-slate-400">
                            ${pt.upper_ci.toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 text-right text-slate-500">
                            ±${(spread / 2).toFixed(2)}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </main>

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => loadForecast(true)}
      />

      <Footer />
    </div>
  );
}
