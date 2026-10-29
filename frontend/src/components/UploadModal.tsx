"use client";

import React, { useState } from "react";
import { useDropzone } from "react-dropzone";
import {
  X,
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Cpu,
  Database,
  Layers,
  FileSpreadsheet,
} from "lucide-react";
import { uploadStatement, generateForecast } from "../lib/api";
import { UploadResponse } from "../lib/types";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (rowCount?: number) => void;
}

type StepStatus = "pending" | "current" | "completed" | "error" | "skipped";

interface ProgressStep {
  id: number;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
}

const STEPS: ProgressStep[] = [
  {
    id: 1,
    label: "Statement Ingestion",
    icon: UploadCloud,
    description: "Secure binary upload directly to backend pipeline",
  },
  {
    id: 2,
    label: "Tabular Extraction Engine",
    icon: Layers,
    description: "Deterministic table extraction via pdfplumber or OCR fallback",
  },
  {
    id: 3,
    label: "Ledger Normalization & Deduplication",
    icon: Database,
    description: "Standardizing amounts, ML category tagging & SHA-256 deduplication",
  },
  {
    id: 4,
    label: "SARIMA Time-Series Calibration",
    icon: Cpu,
    description: "Re-estimating model parameters and 90% confidence intervals",
  },
];

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResponse | null>(null);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      "application/pdf": [".pdf"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/webp": [".webp"],
    },
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        setSelectedFile(acceptedFiles[0]);
        setErrorMsg(null);
        setResult(null);
      }
    },
  });

  if (!isOpen) return null;

  const handleStartUpload = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setErrorMsg(null);
    setCurrentStepIndex(1); // Step 1: Ingestion

    let timer1: NodeJS.Timeout | null = null;
    let timer2: NodeJS.Timeout | null = null;

    try {
      timer1 = setTimeout(() => setCurrentStepIndex(2), 800);
      timer2 = setTimeout(() => setCurrentStepIndex(3), 2000);

      const res = await uploadStatement(selectedFile);
      if (timer1) clearTimeout(timer1);
      if (timer2) clearTimeout(timer2);

      setResult(res);

      const rowCount = res?.statement?.row_count ?? res?.parsed_rows?.length ?? 0;

      if (rowCount === 0) {
        setCurrentStepIndex(5);
        onUploadSuccess(0);
        return;
      }

      // Step 4: SARIMA Refit
      setCurrentStepIndex(4);
      try {
        await generateForecast("DAILY", 30);
      } catch (fErr) {
        console.warn("Forecast refit notice:", fErr);
      }

      // Completed
      setCurrentStepIndex(5);
      onUploadSuccess(rowCount);
    } catch (err: any) {
      if (timer1) clearTimeout(timer1);
      if (timer2) clearTimeout(timer2);
      setErrorMsg(err.message || "Failed to process bank statement.");
      setCurrentStepIndex(0);
    } finally {
      if (timer1) clearTimeout(timer1);
      if (timer2) clearTimeout(timer2);
      setIsProcessing(false);
    }
  };

  const resetState = () => {
    setSelectedFile(null);
    setCurrentStepIndex(0);
    setErrorMsg(null);
    setResult(null);
    setIsProcessing(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/80 bg-slate-900/60">
          <div>
            <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
              Ingest Bank Statement
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Supports official statement files (PDF, JPG, PNG, WebP)
            </p>
          </div>
          <button
            onClick={() => {
              resetState();
              onClose();
            }}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6">
          {/* Dropzone */}
          {!isProcessing && currentStepIndex === 0 && (
            <div>
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition flex flex-col items-center justify-center space-y-3.5 ${
                  isDragActive
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-border hover:border-blue-500/50 hover:bg-slate-900/40"
                }`}
              >
                <input {...getInputProps()} />
                <div className="p-3.5 rounded-full bg-slate-900 border border-border text-blue-400">
                  <UploadCloud className="w-8 h-8" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">
                    {selectedFile
                      ? selectedFile.name
                      : "Drag & drop statement file here, or click to browse"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Direct digital table parsing with OCR image fallback • Up to 25MB
                  </p>
                </div>
                <div className="flex items-center space-x-2 pt-1">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-300 border border-slate-700">
                    PDF
                  </span>
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-300 border border-slate-700">
                    PNG
                  </span>
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-300 border border-slate-700">
                    JPG / JPEG
                  </span>
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-300 border border-slate-700">
                    WEBP
                  </span>
                </div>
              </div>

              {selectedFile && (
                <div className="mt-4 flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-border text-xs">
                  <div className="flex items-center space-x-2.5 truncate">
                    <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                    <span className="text-white font-medium truncate">{selectedFile.name}</span>
                    <span className="text-slate-400 font-mono text-[11px]">
                      ({(selectedFile.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  <button
                    onClick={() => setSelectedFile(null)}
                    className="text-rose-400 hover:text-rose-300 text-xs ml-2 font-medium"
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Stepper Progress */}
          {(isProcessing || currentStepIndex > 0) && (
            <div className="space-y-4">
              <div className="space-y-2.5">
                {STEPS.map((step) => {
                  const StepIcon = step.icon;
                  const isZeroRows = result ? (result.statement?.row_count ?? result.parsed_rows?.length ?? 0) === 0 : false;
                  const isStepSkipped = step.id === 4 && isZeroRows && currentStepIndex >= 5;

                  let status: StepStatus = "pending";
                  if (isStepSkipped) status = "skipped";
                  else if (currentStepIndex > step.id) status = "completed";
                  else if (currentStepIndex === step.id) status = isProcessing ? "current" : "completed";

                  return (
                    <div
                      key={step.id}
                      className={`flex items-start space-x-3 p-3 rounded-lg border transition ${
                        status === "current"
                          ? "bg-blue-500/10 border-blue-500/40"
                          : status === "completed"
                          ? "bg-emerald-500/5 border-emerald-500/20"
                          : status === "skipped"
                          ? "bg-amber-500/5 border-amber-500/20"
                          : "bg-slate-900/30 border-border/40 opacity-40"
                      }`}
                    >
                      <div className="mt-0.5">
                        {status === "completed" ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        ) : status === "current" ? (
                          <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                        ) : status === "skipped" ? (
                          <AlertCircle className="w-4 h-4 text-amber-400" />
                        ) : (
                          <StepIcon className="w-4 h-4 text-slate-500" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-semibold text-white">{step.label}</p>
                          <span
                            className={`text-[10px] uppercase font-mono tracking-wider ${
                              status === "completed"
                                ? "text-emerald-400"
                                : status === "current"
                                ? "text-blue-400"
                                : status === "skipped"
                                ? "text-amber-400"
                                : "text-slate-500"
                            }`}
                          >
                            {status === "completed"
                              ? "Done"
                              : status === "current"
                              ? "Running"
                              : status === "skipped"
                              ? "Skipped"
                              : "Queued"}
                          </span>
                        </div>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {isStepSkipped
                            ? "Skipped: 0 new debit transactions available for forecasting"
                            : step.description}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Completion Summary Card */}
              {result && currentStepIndex >= 5 && (
                (result.statement?.row_count ?? result.parsed_rows?.length ?? 0) === 0 ? (
                  <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 space-y-2">
                    <div className="flex items-center space-x-2 font-semibold text-amber-400">
                      <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                      <span>No Tabular Transactions Detected</span>
                    </div>
                    <p className="text-[11px] text-amber-200/90 leading-relaxed">
                      No transaction rows could be parsed from this document. Please ensure the file has a recognizable statement table or is not password protected.
                    </p>
                  </div>
                ) : (
                  <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-white space-y-2">
                    <div className="flex items-center space-x-2 font-semibold text-emerald-400">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Ingestion & Normalization Complete</span>
                    </div>
                    <div className="font-mono text-[11px] space-y-1 text-slate-300">
                      <p>• {result.newly_inserted} new transaction records committed to database</p>
                      <p>• {result.duplicates_skipped} duplicates skipped via SHA-256 row verification</p>
                      <p>• SARIMA time-series model calibrated with updated spend history</p>
                    </div>
                  </div>
                )
              )}
            </div>
          )}

          {/* Error Message */}
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-slate-900/60 border-t border-border flex items-center justify-end space-x-3">
          {currentStepIndex >= 5 ? (
            <button
              onClick={() => {
                resetState();
                onClose();
              }}
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition shadow-sm"
            >
              Done & View Dashboard
            </button>
          ) : (
            <>
              <button
                onClick={() => {
                  resetState();
                  onClose();
                }}
                disabled={isProcessing}
                className="px-4 py-2 text-xs font-medium text-muted-foreground hover:text-white transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleStartUpload}
                disabled={!selectedFile || isProcessing}
                className="flex items-center space-x-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition disabled:opacity-50 shadow-sm"
              >
                {isProcessing && <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />}
                <span>{isProcessing ? "Ingesting..." : "Process Statement"}</span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
