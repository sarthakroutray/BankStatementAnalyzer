"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { Footer } from "../../components/Footer";
import { UploadModal } from "../../components/UploadModal";
import { fetchStatements, uploadStatement, generateForecast } from "../../lib/api";
import { Statement } from "../../lib/types";
import { useDropzone } from "react-dropzone";
import {
  FileCheck2,
  UploadCloud,
  FileText,
  Database,
  ShieldCheck,
  Cpu,
  Layers,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  ArrowRight,
  FileSpreadsheet,
} from "lucide-react";

export default function StatementsPage() {
  const [statements, setStatements] = useState<Statement[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // In-page direct uploader state
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const loadStatements = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchStatements(50, 0);
      setStatements(data);
    } catch (err) {
      console.error("Failed to load statements:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatements();
  }, [loadStatements]);

  const onDrop = async (acceptedFiles: File[]) => {
    if (!acceptedFiles.length) return;
    const file = acceptedFiles[0];

    setUploading(true);
    setUploadStatus("Uploading & extracting statement tables...");
    setUploadError(null);

    try {
      const res = await uploadStatement(file);
      const rowCount = res.statement?.row_count ?? res.parsed_rows?.length ?? (res.newly_inserted + res.duplicates_skipped);
      
      if (rowCount === 0) {
        setUploadStatus(null);
        setUploadError("No tabular transactions detected in this statement document. Please ensure the file has a recognizable statement table or is not password protected.");
      } else {
        setUploadStatus(`Extracted ${res.newly_inserted} new rows (${res.duplicates_skipped} duplicates skipped).`);
        // Trigger forecast refit
        try {
          await generateForecast("DAILY", 30);
        } catch (fErr) {
          console.warn("Forecast refit notice:", fErr);
        }
      }

      await loadStatements();
    } catch (err: any) {
      setUploadError(err.message || "Failed to process statement.");
    } finally {
      setUploading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/webp": [".webp"],
    },
    maxFiles: 1,
    disabled: uploading,
  });

  const totalRows = statements.reduce((acc, s) => acc + (s.row_count || 0), 0);
  const totalDebits = statements.reduce((acc, s) => acc + Number(s.total_debit || 0), 0);
  const totalCredits = statements.reduce((acc, s) => acc + Number(s.total_credit || 0), 0);

  return (
    <div className="min-h-screen flex flex-col bg-canvas selection:bg-blue-600/30 selection:text-white">
      <Navbar onOpenUpload={() => setIsModalOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Breadcrumb Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
          <div>
            <div className="flex items-center space-x-2 text-xs text-muted-foreground font-mono mb-1">
              <Link href="/" className="hover:text-white transition">
                OVERVIEW
              </Link>
              <span>/</span>
              <span className="text-blue-400">INGESTION PIPELINE</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white font-sans">
              Statement Pipeline & Ingestion Audit
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Deterministic document parser logs, cryptographic deduplication receipts, and database sync status
            </p>
          </div>

          <div className="flex items-center space-x-2.5">
            <button
              onClick={loadStatements}
              disabled={loading}
              className="flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-border text-xs font-medium transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-blue-400" : ""}`} />
              <span>Refresh Pipeline</span>
            </button>
          </div>
        </div>

        {/* 1. Ingestion Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl bg-card border border-border/80 shadow-subtle flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              Statements Ingested
            </span>
            <div className="mt-3">
              <span className="text-2xl font-bold text-white font-mono">
                {statements.length} documents
              </span>
              <p className="text-[11px] text-muted-foreground mt-1">Processed statements</p>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-card border border-border/80 shadow-subtle flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              Extracted Transactions
            </span>
            <div className="mt-3">
              <span className="text-2xl font-bold text-blue-400 font-mono">
                {totalRows.toLocaleString()} rows
              </span>
              <p className="text-[11px] text-muted-foreground mt-1">Deduplicated ledger entries</p>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-card border border-border/80 shadow-subtle flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              Cumulative Debit Value
            </span>
            <div className="mt-3">
              <span className="text-2xl font-bold text-rose-400 font-mono">
                -${totalDebits.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-[11px] text-muted-foreground mt-1">Total debit volume</p>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-card border border-border/80 shadow-subtle flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              Cumulative Credit Value
            </span>
            <div className="mt-3">
              <span className="text-2xl font-bold text-emerald-400 font-mono">
                +${totalCredits.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-[11px] text-muted-foreground mt-1">Total credit volume</p>
            </div>
          </div>
        </div>

        {/* 2. Direct Ingestion Dropzone Card */}
        <div className="bg-card border border-border/80 rounded-xl p-6 shadow-subtle">
          <div className="mb-4">
            <h3 className="text-base font-bold text-white tracking-tight">Ingest Bank Document</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Drop statements to trigger automatic tabular extraction, SHA-256 deduplication, and SARIMA refit
            </p>
          </div>

          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition flex flex-col items-center justify-center space-y-3 ${
              isDragActive
                ? "border-blue-500 bg-blue-500/10"
                : "border-border hover:border-blue-500/50 hover:bg-slate-900/40"
            }`}
          >
            <input {...getInputProps()} />
            <div className="p-3.5 rounded-full bg-slate-900 border border-border text-blue-400">
              {uploading ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                <UploadCloud className="w-8 h-8" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-white">
                {uploading
                  ? "Processing statement document..."
                  : "Drag and drop bank statement (PDF, PNG, JPG, WebP), or click to browse"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Deterministic digital table parsing with OCR image fallback • Maximum file size 25MB
              </p>
            </div>
          </div>

          {uploadStatus && (
            <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{uploadStatus}</span>
            </div>
          )}

          {uploadError && (
            <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}
        </div>

        {/* 3. Ingested Statements Table */}
        <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle">
          <div className="flex items-center justify-between pb-4 border-b border-border/60">
            <div>
              <h3 className="text-base font-bold text-white tracking-tight">Ingested Statement Documents</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Audit trail of uploaded statement files and tabular parsing receipts
              </p>
            </div>
            <Link
              href="/transactions"
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center font-medium"
            >
              <span>View Full Ledger</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Link>
          </div>

          <div className="overflow-x-auto mt-4">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/80 text-muted-foreground uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-2.5 px-3">Filename</th>
                  <th className="py-2.5 px-3">Uploaded At</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Extracted Rows</th>
                  <th className="py-2.5 px-3 text-right">Total Debit</th>
                  <th className="py-2.5 px-3 text-right">Total Credit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-muted-foreground font-sans">
                      Loading statement history...
                    </td>
                  </tr>
                ) : statements.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-muted-foreground font-sans">
                      No statements uploaded yet. Drop a PDF or image statement above to begin.
                    </td>
                  </tr>
                ) : (
                  statements.map((stmt) => {
                    const isSuccess = stmt.status === "COMPLETED";
                    const formattedDate = stmt.uploaded_at
                      ? new Date(stmt.uploaded_at).toLocaleString("en-US", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })
                      : "—";

                    return (
                      <tr key={stmt.id} className="hover:bg-slate-900/50 transition">
                        <td className="py-3 px-3 font-sans font-medium text-white flex items-center space-x-2">
                          <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                          <span className="truncate max-w-xs">{stmt.filename}</span>
                        </td>
                        <td className="py-3 px-3 text-slate-400 whitespace-nowrap">{formattedDate}</td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${
                              isSuccess
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : stmt.status === "PROCESSING"
                                ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            }`}
                          >
                            {stmt.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right font-bold text-white">
                          {stmt.row_count}
                        </td>
                        <td className="py-3 px-3 text-right text-rose-400 font-bold">
                          -${Number(stmt.total_debit || 0).toFixed(2)}
                        </td>
                        <td className="py-3 px-3 text-right text-emerald-400 font-bold">
                          +${Number(stmt.total_credit || 0).toFixed(2)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 4. Engine Architecture Information */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-card border border-border/80 shadow-subtle space-y-2">
            <div className="flex items-center space-x-2 text-white font-semibold">
              <Layers className="w-4 h-4 text-blue-400" />
              <span>Deterministic Table Parsing</span>
            </div>
            <p className="text-muted-foreground leading-relaxed text-[11px]">
              Extracts bounding coordinate tables directly from vector PDF streams with zero LLM hallucination or row dropping.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-card border border-border/80 shadow-subtle space-y-2">
            <div className="flex items-center space-x-2 text-white font-semibold">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>SHA-256 Deduplication</span>
            </div>
            <p className="text-muted-foreground leading-relaxed text-[11px]">
              Every transaction hash digests date, amount, description, and balance to prevent duplicate entries across overlapping statements.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-card border border-border/80 shadow-subtle space-y-2">
            <div className="flex items-center space-x-2 text-white font-semibold">
              <Cpu className="w-4 h-4 text-purple-400" />
              <span>Dynamic SARIMA Fit</span>
            </div>
            <p className="text-muted-foreground leading-relaxed text-[11px]">
              Automated stepwise AIC minimization recalculates seasonal and trend orders each time new statements are committed.
            </p>
          </div>
        </div>
      </main>

      <UploadModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onUploadSuccess={() => loadStatements()}
      />

      <Footer />
    </div>
  );
}
