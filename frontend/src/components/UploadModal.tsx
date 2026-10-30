"use client";

import React, { useState, useEffect, useRef } from "react";
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
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { uploadStatement, generateForecast } from "../lib/api";
import { UploadResponse } from "../lib/types";
import { Button } from "./ui/Button";
import { Pill } from "./ui/Pill";

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
    description: "Deterministic table extraction via JVM CLI or OCR fallback",
  },
  {
    id: 3,
    label: "Ledger Normalization & Deduplication",
    icon: Database,
    description: "Amount formatting, ML category tagging & SHA-256 deduplication",
  },
  {
    id: 4,
    label: "SARIMA Time-Series Calibration",
    icon: Cpu,
    description: "Re-estimating model parameters and 90% confidence ribbons",
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

  const modalRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isProcessing) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isProcessing, onClose]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      "application/pdf": [".pdf"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/webp": [".webp"],
    },
    maxFiles: 1,
    disabled: isProcessing,
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
      timer1 = setTimeout(() => {
        setCurrentStepIndex(2); // Step 2: Tabular Extraction
      }, 1200);

      timer2 = setTimeout(() => {
        setCurrentStepIndex(3); // Step 3: Normalization & Deduplication
      }, 3500);

      // Upload file directly
      const uploadRes = await uploadStatement(selectedFile);

      if (timer1) clearTimeout(timer1);
      if (timer2) clearTimeout(timer2);

      setResult(uploadRes);
      setCurrentStepIndex(4); // Step 4: SARIMA Calibration

      // Calibrate SARIMA parameters
      try {
        await generateForecast("DAILY", 30);
      } catch (fErr) {
        console.warn("Forecast re-calibration skipped or deferred:", fErr);
      }

      setCurrentStepIndex(5); // Complete

      // Notify parent of newly ingested records
      setTimeout(() => {
        onUploadSuccess(uploadRes.newly_inserted ?? 0);
        handleClose();
      }, 1400);
    } catch (err: unknown) {
      if (timer1) clearTimeout(timer1);
      if (timer2) clearTimeout(timer2);
      const message =
        err instanceof Error
          ? err.message
          : "An unexpected error occurred during statement processing.";
      setErrorMsg(message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleClose = () => {
    if (isProcessing) return;
    setSelectedFile(null);
    setCurrentStepIndex(0);
    setErrorMsg(null);
    setResult(null);
    onClose();
  };

  const getStepStatus = (stepId: number): StepStatus => {
    if (errorMsg && currentStepIndex === stepId) return "error";
    if (currentStepIndex > stepId) return "completed";
    if (currentStepIndex === stepId) return "current";
    return "pending";
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-xl"
    >
      <div
        ref={modalRef}
        className="w-full max-w-xl bg-charcoal/95 border border-white/20 rounded-[32px] p-6 sm:p-8 shadow-2xl backdrop-blur-2xl relative overflow-hidden transition-all ease-fluid"
      >
        {/* Top Header */}
        <div className="flex items-center justify-between pb-5 border-b border-white/10">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-full bg-black border border-white/20 flex items-center justify-center text-cyber-yellow">
              <UploadCloud className="w-4 h-4" />
            </div>
            <div>
              <h2 id="upload-modal-title" className="text-lg sm:text-xl font-bold text-white font-sans">
                Upload Bank Statement
              </h2>
              <p className="text-xs text-neutral-400">
                Deterministic extraction with SHA-256 deduplication
              </p>
            </div>
          </div>

          <button
            onClick={handleClose}
            disabled={isProcessing}
            aria-label="Close dialog"
            className="w-8 h-8 rounded-full bg-deep-gray border border-white/10 flex items-center justify-center text-neutral-400 hover:text-white transition disabled:opacity-40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="py-6 space-y-6">
          {/* Dropzone Area */}
          {!isProcessing && currentStepIndex === 0 && (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-[28px] p-8 text-center cursor-pointer transition-all duration-300 select-none ${
                isDragActive
                  ? "border-cyber-yellow bg-cyber-yellow/10 ring-4 ring-cyber-yellow/30 scale-[1.01]"
                  : "border-white/15 bg-white/[0.02] hover:border-white/30 hover:bg-white/[0.04]"
              }`}
            >
              <input {...getInputProps()} aria-label="Drop statement PDF file here" />
              <div className="flex flex-col items-center justify-center space-y-3">
                <div className="w-14 h-14 rounded-full bg-deep-gray border border-white/10 flex items-center justify-center text-cyber-yellow transition-transform group-hover:scale-110">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white font-sans">
                    {isDragActive
                      ? "Drop statement here..."
                      : "Drag & drop PDF bank statement here"}
                  </p>
                  <p className="text-xs text-neutral-400 mt-1">
                    or click to browse from device (PDF, PNG, JPG)
                  </p>
                </div>
                <div className="flex items-center space-x-2 text-[10px] font-mono text-neutral-500 pt-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-cyber-yellow" />
                  <span>Encrypted client-to-server TLS transfer</span>
                </div>
              </div>
            </div>
          )}

          {/* Selected File Chip */}
          {selectedFile && currentStepIndex === 0 && (
            <div className="flex items-center justify-between p-4 rounded-[20px] bg-deep-gray border border-white/10">
              <div className="flex items-center space-x-3 truncate">
                <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-cyber-yellow shrink-0">
                  <FileText className="w-4 h-4" />
                </div>
                <div className="truncate">
                  <p className="text-xs font-semibold text-white truncate font-sans">
                    {selectedFile.name}
                  </p>
                  <p className="text-[10px] font-mono text-neutral-400">
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedFile(null);
                }}
                className="p-1 rounded-full text-neutral-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Processing Stepper */}
          {isProcessing || currentStepIndex > 0 ? (
            <div className="space-y-4 py-2">
              <div className="space-y-3">
                {STEPS.map((step) => {
                  const status = getStepStatus(step.id);
                  const Icon = step.icon;

                  return (
                    <div
                      key={step.id}
                      className={`flex items-start space-x-3.5 p-3.5 rounded-[20px] border transition-all duration-300 ${
                        status === "completed"
                          ? "bg-white/[0.03] border-white/15"
                          : status === "current"
                          ? "bg-cyber-yellow/5 border-cyber-yellow/40 shadow-sm"
                          : status === "error"
                          ? "bg-danger/10 border-danger/30"
                          : "bg-transparent border-transparent opacity-40"
                      }`}
                    >
                      <div className="mt-0.5 shrink-0">
                        {status === "completed" ? (
                          <div className="w-6 h-6 rounded-full bg-success/20 text-success flex items-center justify-center">
                            <CheckCircle2 className="w-4 h-4" />
                          </div>
                        ) : status === "current" ? (
                          <div className="w-6 h-6 rounded-full bg-cyber-yellow text-black flex items-center justify-center animate-pulse">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          </div>
                        ) : status === "error" ? (
                          <div className="w-6 h-6 rounded-full bg-danger text-white flex items-center justify-center">
                            <AlertCircle className="w-3.5 h-3.5" />
                          </div>
                        ) : (
                          <div className="w-6 h-6 rounded-full bg-deep-gray text-neutral-500 flex items-center justify-center">
                            <Icon className="w-3.5 h-3.5" />
                          </div>
                        )}
                      </div>

                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <p
                            className={`text-xs font-semibold font-sans ${
                              status === "current"
                                ? "text-cyber-yellow"
                                : status === "completed"
                                ? "text-white"
                                : status === "error"
                                ? "text-danger"
                                : "text-neutral-500"
                            }`}
                          >
                            {step.label}
                          </p>
                          {status === "completed" && (
                            <span className="text-[10px] font-mono text-success font-bold">
                              DONE
                            </span>
                          )}
                          {status === "current" && (
                            <span className="text-[10px] font-mono text-cyber-yellow animate-pulse">
                              RUNNING
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-neutral-400 mt-0.5 leading-snug">
                          {step.description}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Success Result Summary */}
              {currentStepIndex === 5 && result && (
                <div className="p-4 rounded-[20px] bg-cyber-yellow/10 border border-cyber-yellow/30 text-xs text-white">
                  <div className="flex items-center justify-between font-mono">
                    <span className="text-cyber-yellow font-bold">Extraction Complete</span>
                    <span className="text-white font-bold tabular-nums">
                      +{result.newly_inserted ?? 0} rows parsed
                    </span>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {/* Error Message Box */}
          {errorMsg && (
            <div className="p-4 rounded-[20px] bg-danger/10 border border-danger/30 text-xs text-danger space-y-1">
              <div className="flex items-center space-x-1.5 font-bold">
                <AlertCircle className="w-4 h-4" />
                <span>Processing Error</span>
              </div>
              <p className="text-neutral-300 text-[11px] leading-relaxed">{errorMsg}</p>
            </div>
          )}
        </div>

        {/* Modal Actions */}
        <div className="pt-4 border-t border-white/10 flex items-center justify-end space-x-3">
          <Button
            variant="outline-white"
            size="sm"
            onClick={handleClose}
            disabled={isProcessing}
          >
            {currentStepIndex === 5 ? "Close" : "Cancel"}
          </Button>

          {currentStepIndex === 0 && (
            <Button
              variant="yellow"
              size="sm"
              onClick={handleStartUpload}
              disabled={!selectedFile || isProcessing}
              className="flex items-center space-x-1.5"
            >
              <span>Process Statement</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          )}

          {errorMsg && (
            <Button
              variant="yellow"
              size="sm"
              onClick={handleStartUpload}
              className="flex items-center space-x-1.5"
            >
              <span>Retry</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
