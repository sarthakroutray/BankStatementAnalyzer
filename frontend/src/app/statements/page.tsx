"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { Footer } from "../../components/Footer";
import { UploadModal } from "../../components/UploadModal";
import { Button } from "../../components/ui/Button";
import { Pill } from "../../components/ui/Pill";
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
      const rowCount =
        res.statement?.row_count ??
        res.parsed_rows?.length ??
        res.newly_inserted + res.duplicates_skipped;

      if (rowCount === 0) {
        setUploadStatus(null);
        setUploadError(
          "No tabular transactions detected in this statement document. Please ensure the file has a recognizable statement table or is not password protected."
        );
      } else {
        setUploadStatus(
          `Extracted ${res.newly_inserted} new rows (${res.duplicates_skipped} duplicates skipped).`
        );
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
    <div className="min-h-screen flex flex-col bg-onyx text-white selection:bg-cyber-yellow selection:text-black">
      <Navbar onOpenUpload={() => setIsModalOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 sm:px-8 py-10 space-y-8">
        {/* Breadcrumb Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
          <div>
            <div className="flex items-center space-x-2 text-[10px] font-mono tracking-widest text-neutral-400 mb-1">
              <Link href="/" className="hover:text-white transition">
                OVERVIEW
              </Link>
              <span>/</span>
              <span className="text-cyber-yellow font-bold">INGESTION PIPELINE</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-sans">
              Statement Pipeline & Ingestion Audit
            </h1>
            <p className="text-xs sm:text-sm text-neutral-400 mt-1">
              Deterministic document parser logs, cryptographic deduplication receipts, and database sync status
            </p>
          </div>

          <div className="flex items-center space-x-2.5">
            <Button
              variant="outline-white"
              size="sm"
              onClick={loadStatements}
              disabled={loading}
              className="flex items-center space-x-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-cyber-yellow" : ""}`} />
              <span>Refresh Pipeline</span>
            </Button>
          </div>
        </div>

        {/* 1. Ingestion Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
              Statements Ingested
            </span>
            <div className="mt-4">
              <span className="text-3xl font-extrabold text-white font-sans tabular-nums">
                {statements.length}
              </span>
              <p className="text-xs text-neutral-400 mt-1 font-mono">Processed documents</p>
            </div>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
              Extracted Transactions
            </span>
            <div className="mt-4">
              <span className="text-3xl font-extrabold text-cyber-yellow font-sans tabular-nums">
                {totalRows.toLocaleString()}
              </span>
              <p className="text-xs text-neutral-400 mt-1 font-mono">Deduplicated ledger entries</p>
            </div>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
              Cumulative Debit Value
            </span>
            <div className="mt-4">
              <span className="text-3xl font-extrabold text-danger font-sans tabular-nums">
                -${totalDebits.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-xs text-neutral-400 mt-1 font-mono">Total debit volume</p>
            </div>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex flex-col justify-between">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest font-mono">
              Cumulative Credit Value
            </span>
            <div className="mt-4">
              <span className="text-3xl font-extrabold text-success font-sans tabular-nums">
                +${totalCredits.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <p className="text-xs text-neutral-400 mt-1 font-mono">Total credit volume</p>
            </div>
          </div>
        </div>

        {/* 2. Direct Ingestion Dropzone Card */}
        <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-8 shadow-glass backdrop-blur-2xl">
          <div className="mb-5">
            <h3 className="text-lg font-bold text-white tracking-tight font-sans">
              Ingest Bank Document
            </h3>
            <p className="text-xs sm:text-sm text-neutral-400 mt-0.5">
              Drop statements to trigger automatic tabular extraction, SHA-256 deduplication, and SARIMA refit
            </p>
          </div>

          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-[28px] p-8 sm:p-10 text-center cursor-pointer transition-all duration-300 flex flex-col items-center justify-center space-y-3 select-none ${
              isDragActive
                ? "border-cyber-yellow bg-cyber-yellow/10 ring-4 ring-cyber-yellow/30 scale-[1.01]"
                : "border-white/15 bg-white/[0.02] hover:border-white/30 hover:bg-white/[0.04]"
            }`}
          >
            <input {...getInputProps()} />
            <div className="w-14 h-14 rounded-full bg-deep-gray border border-white/10 flex items-center justify-center text-cyber-yellow">
              {uploading ? (
                <Loader2 className="w-7 h-7 animate-spin" />
              ) : (
                <UploadCloud className="w-7 h-7" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-white font-sans">
                {uploading
                  ? "Processing statement document..."
                  : "Drag and drop bank statement (PDF, PNG, JPG, WebP), or click to browse"}
              </p>
              <p className="text-xs text-neutral-400 mt-1">
                Deterministic digital table parsing with OCR image fallback • Maximum file size 25MB
              </p>
            </div>
          </div>

          {uploadStatus && (
            <div className="mt-4 p-4 rounded-[20px] bg-cyber-yellow/10 border border-cyber-yellow/30 text-xs text-white flex items-center space-x-2 font-mono">
              <CheckCircle2 className="w-4 h-4 text-cyber-yellow shrink-0" />
              <span>{uploadStatus}</span>
            </div>
          )}

          {uploadError && (
            <div className="mt-4 p-4 rounded-[20px] bg-danger/10 border border-danger/30 text-xs text-danger flex items-center space-x-2 font-mono">
              <AlertCircle className="w-4 h-4 text-danger shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}
        </div>

        {/* 3. Ingested Statements Table */}
        <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-8 shadow-glass backdrop-blur-2xl">
          <div className="flex items-center justify-between pb-5 border-b border-white/10">
            <div>
              <h3 className="text-lg font-bold text-white tracking-tight font-sans">
                Ingested Statement Documents
              </h3>
              <p className="text-xs text-neutral-400 mt-0.5">
                Audit trail of uploaded statement files and tabular parsing receipts
              </p>
            </div>
            <Link href="/transactions">
              <Button variant="outline-white" size="sm" className="flex items-center space-x-1.5">
                <span>View Full Ledger</span>
                <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </Link>
          </div>

          <div className="overflow-x-auto mt-4 rounded-[24px] border border-white/10">
            <table className="w-full text-left text-xs whitespace-nowrap">
              <thead className="sticky top-0 bg-deep-gray/95 backdrop-blur-md text-[10px] uppercase tracking-widest text-neutral-400 font-mono border-b border-white/10">
                <tr>
                  <th className="py-3.5 px-4 font-bold">Filename</th>
                  <th className="py-3.5 px-4 font-bold">Uploaded At</th>
                  <th className="py-3.5 px-4 font-bold">Status</th>
                  <th className="py-3.5 px-4 font-bold text-right">Extracted Rows</th>
                  <th className="py-3.5 px-4 font-bold text-right">Total Debit</th>
                  <th className="py-3.5 px-4 font-bold text-right">Total Credit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-sans">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-neutral-400 font-mono">
                      <div className="flex flex-col items-center justify-center space-y-2">
                        <Loader2 className="w-6 h-6 text-cyber-yellow animate-spin" />
                        <span>Loading statement history...</span>
                      </div>
                    </td>
                  </tr>
                ) : statements.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-neutral-400">
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
                      <tr key={stmt.id} className="hover:bg-white/[0.03] transition-colors">
                        <td className="py-3.5 px-4 font-medium text-white flex items-center space-x-2">
                          <FileText className="w-4 h-4 text-cyber-yellow shrink-0" />
                          <span className="truncate max-w-xs">{stmt.filename}</span>
                        </td>
                        <td className="py-3.5 px-4 text-neutral-400 font-mono">{formattedDate}</td>
                        <td className="py-3.5 px-4 font-mono">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              isSuccess
                                ? "bg-success/15 text-success border border-success/30"
                                : stmt.status === "PROCESSING"
                                ? "bg-cyber-yellow/15 text-cyber-yellow border border-cyber-yellow/30"
                                : "bg-danger/15 text-danger border border-danger/30"
                            }`}
                          >
                            {stmt.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-bold text-white tabular-nums">
                          {stmt.row_count}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-danger font-bold tabular-nums">
                          -${Number(stmt.total_debit || 0).toFixed(2)}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-success font-bold tabular-nums">
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-xs">
          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl space-y-2">
            <div className="flex items-center space-x-2 text-white font-semibold font-sans">
              <Layers className="w-4 h-4 text-cyber-yellow" />
              <span>Deterministic Table Parsing</span>
            </div>
            <p className="text-neutral-400 leading-relaxed text-xs">
              Extracts bounding coordinate tables directly from vector PDF streams with zero LLM hallucination or row dropping.
            </p>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl space-y-2">
            <div className="flex items-center space-x-2 text-white font-semibold font-sans">
              <ShieldCheck className="w-4 h-4 text-success" />
              <span>SHA-256 Deduplication</span>
            </div>
            <p className="text-neutral-400 leading-relaxed text-xs">
              Every transaction hash digests date, amount, description, and balance to prevent duplicate entries across overlapping statements.
            </p>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl space-y-2">
            <div className="flex items-center space-x-2 text-white font-semibold font-sans">
              <Cpu className="w-4 h-4 text-cyber-yellow" />
              <span>Dynamic SARIMA Fit</span>
            </div>
            <p className="text-neutral-400 leading-relaxed text-xs">
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
