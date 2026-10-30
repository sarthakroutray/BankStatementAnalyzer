"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { Footer } from "../../components/Footer";
import { ForecastChart } from "../../components/ForecastChart";
import { UploadModal } from "../../components/UploadModal";
import { Button } from "../../components/ui/Button";
import { Pill } from "../../components/ui/Pill";
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
  Sparkles,
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
    <div className="min-h-screen flex flex-col bg-onyx text-white selection:bg-cyber-yellow selection:text-black">
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 sm:px-8 py-10 space-y-8">
        {/* Header Breadcrumbs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
          <div>
            <div className="flex items-center space-x-2 text-[10px] font-mono tracking-widest text-neutral-400 mb-1">
              <Link href="/" className="hover:text-white transition">
                OVERVIEW
              </Link>
              <span>/</span>
              <span className="text-cyber-yellow font-bold">SARIMA FORECAST STUDIO</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-sans">
              Predictive Spending Engine & Diagnostics
            </h1>
            <p className="text-xs sm:text-sm text-neutral-400 mt-1">
              Seasonal Autoregressive Integrated Moving Average (SARIMA) forecasting with 90% parameter confidence bands
            </p>
          </div>

          <div className="flex items-center space-x-2.5">
            <Button
              variant="outline-white"
              size="sm"
              onClick={() => loadForecast(true)}
              disabled={loading}
              className="flex items-center space-x-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-cyber-yellow" : ""}`} />
              <span>Refit Model</span>
            </Button>
            <Button
              variant="yellow"
              size="sm"
              onClick={handleExportForecast}
              disabled={!forecast?.forecast_payload?.length}
              className="flex items-center space-x-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export Projections</span>
            </Button>
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
          <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-7 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <Cpu className="w-4 h-4 text-cyber-yellow" />
                <h3 className="text-base font-bold text-white tracking-tight font-sans">Model Diagnostics</h3>
              </div>
              <p className="text-xs text-neutral-400">
                Statistical fit parameters and loss metrics
              </p>

              <div className="mt-5 space-y-3 font-mono text-xs">
                <div className="p-3.5 rounded-[20px] bg-deep-gray border border-white/10 flex items-center justify-between">
                  <span className="text-neutral-400 text-xs font-sans">SARIMA Order</span>
                  <span className="text-cyber-yellow font-bold">
                    {forecast?.sarima_order || "None"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3.5 rounded-[20px] bg-deep-gray border border-white/10">
                    <span className="text-neutral-400 text-[10px] font-sans block mb-1">RMSE Error</span>
                    <span className="text-white font-bold text-sm tabular-nums">
                      {forecast?.rmse !== null && forecast?.rmse !== undefined
                        ? `±$${forecast.rmse.toFixed(2)}`
                        : "N/A"}
                    </span>
                  </div>
                  <div className="p-3.5 rounded-[20px] bg-deep-gray border border-white/10">
                    <span className="text-neutral-400 text-[10px] font-sans block mb-1">Akaike IC (AIC)</span>
                    <span className="text-white font-bold text-sm tabular-nums">
                      {forecast?.aic !== null && forecast?.aic !== undefined
                        ? forecast.aic.toFixed(1)
                        : "N/A"}
                    </span>
                  </div>
                </div>

                <div className="p-3.5 rounded-[20px] bg-deep-gray border border-white/10 space-y-2 text-xs">
                  <div className="flex items-center justify-between text-neutral-300">
                    <span className="font-sans">Seasonality (s):</span>
                    <span className="font-bold text-white">
                      {granularity === "DAILY" ? "s = 7 (Weekly)" : "s = 4 (Monthly)"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-neutral-300">
                    <span className="font-sans">Confidence Band:</span>
                    <span className="font-bold text-cyber-yellow">90% Parametric</span>
                  </div>
                  <div className="flex items-center justify-between text-neutral-300">
                    <span className="font-sans">Fallback Applied:</span>
                    <span className={forecast?.fallback_used ? "text-amber-400" : "text-neutral-400"}>
                      {forecast?.fallback_used ? "Yes (Cold Start)" : "No (Auto-ARIMA)"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-5 pt-3 border-t border-white/10 text-xs text-neutral-400 leading-relaxed font-sans">
              Model parameters are tuned via Stepwise AIC optimization across non-seasonal (p,d,q) and seasonal (P,D,Q)s orders.
            </div>
          </div>

          {/* Interactive Scenario Stress-Tester */}
          <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-7 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <Sliders className="w-4 h-4 text-cyber-yellow" />
                <h3 className="text-base font-bold text-white tracking-tight font-sans">Scenario Simulator</h3>
              </div>
              <p className="text-xs text-neutral-400">
                Simulate spending adjustments & test budget sensitivity
              </p>

              <div className="mt-5 space-y-4">
                <div>
                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="text-neutral-300 font-medium font-sans">Spending Delta:</span>
                    <span
                      className={`font-mono font-bold px-2.5 py-0.5 rounded-full text-xs ${
                        scenarioAdjustment > 0
                          ? "bg-danger/15 text-danger border border-danger/30"
                          : scenarioAdjustment < 0
                          ? "bg-success/15 text-success border border-success/30"
                          : "bg-deep-gray text-neutral-300 border border-white/10"
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
                    className="w-full accent-cyber-yellow bg-deep-gray rounded-lg h-2 cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-neutral-500 font-mono mt-1">
                    <span>-30% Cut</span>
                    <span>Baseline (0%)</span>
                    <span>+30% Surge</span>
                  </div>
                </div>

                <div className="p-4 rounded-[20px] bg-deep-gray border border-white/10 space-y-2.5 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-neutral-400 font-sans text-xs">Baseline Projected:</span>
                    <span className="text-white font-semibold tabular-nums">
                      ${totalProjected.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-white/10">
                    <span className="text-neutral-300 font-sans text-xs">Simulated Total:</span>
                    <span className="text-base font-bold text-cyber-yellow tabular-nums">
                      ${simulatedProjected.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-white/10 text-xs">
                    <span className="text-neutral-400 font-sans">Variance Impact:</span>
                    <span
                      className={`tabular-nums ${
                        simulatedProjected - totalProjected > 0
                          ? "text-danger font-bold"
                          : simulatedProjected - totalProjected < 0
                          ? "text-success font-bold"
                          : "text-neutral-400"
                      }`}
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
              className="mt-5 w-full py-2.5 text-xs text-neutral-400 hover:text-white bg-deep-gray hover:bg-neutral-800 rounded-full border border-white/10 transition active:scale-95"
            >
              Reset Simulation to Baseline
            </button>
          </div>

          {/* Quick Guidance / Methodology Card */}
          <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-7 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <HelpCircle className="w-4 h-4 text-cyber-yellow" />
                <h3 className="text-base font-bold text-white tracking-tight font-sans">Methodology</h3>
              </div>
              <p className="text-xs text-neutral-400">
                How Fluxo models debit expenditure
              </p>

              <div className="mt-5 space-y-3.5 text-xs text-neutral-300 leading-relaxed font-sans">
                <p>
                  <strong className="text-white">Deterministic Ingestion:</strong> Statements are parsed via JVM table boundary detectors, preserving exact cents and posting dates.
                </p>
                <p>
                  <strong className="text-white">Stationarity & Differencing:</strong> The ADF test assesses non-stationarity, applying seasonal and first differencing where necessary.
                </p>
                <p>
                  <strong className="text-white">90% Parametric Envelope:</strong> The forecast ribbon widens over the forward horizon, representing model uncertainty intervals.
                </p>
              </div>
            </div>

            <div className="mt-5 pt-3 border-t border-white/10">
              <Link href="/analytics" className="inline-flex items-center space-x-1.5 text-xs text-cyber-yellow hover:underline font-mono">
                <span>View categorical spending distribution</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
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
