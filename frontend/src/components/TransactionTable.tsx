"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import {
  Search,
  ArrowUpRight,
  ArrowDownLeft,
  ChevronLeft,
  ChevronRight,
  Tag,
  Check,
  Download,
  Calendar,
  X,
  ArrowRight,
  Trash2,
  AlertTriangle,
  Loader2,
  Receipt,
  ArrowUpDown,
} from "lucide-react";
import { Transaction } from "../lib/types";
import { Pill } from "./ui/Pill";
import { Button } from "./ui/Button";

interface TransactionTableProps {
  transactions: Transaction[];
  total: number;
  loading: boolean;
  page: number;
  pageSize: number;
  search: string;
  category: string;
  txnType: string;
  startDate?: string;
  endDate?: string;
  onPageChange: (p: number) => void;
  onSearchChange: (s: string) => void;
  onCategoryChange: (c: string) => void;
  onTxnTypeChange: (t: string) => void;
  onStartDateChange?: (d: string) => void;
  onEndDateChange?: (d: string) => void;
  onUpdateCategory: (txnId: string, newCategory: string) => Promise<void>;
  onDeleteTransaction?: (txnId: string) => Promise<void>;
  onDeleteAllTransactions?: () => Promise<void>;
  showExport?: boolean;
  viewAllHref?: string;
}

const CATEGORIES = [
  "All",
  "Food & Dining",
  "Groceries",
  "Utilities",
  "Travel",
  "Subscriptions",
  "Transfers",
  "Shopping",
  "Other",
];

const CATEGORY_STYLES: Record<string, string> = {
  "Food & Dining": "bg-amber-400/10 text-amber-300 border-amber-400/20",
  Groceries: "bg-emerald-400/10 text-emerald-300 border-emerald-400/20",
  Utilities: "bg-cyan-400/10 text-cyan-300 border-cyan-400/20",
  Travel: "bg-blue-400/10 text-blue-300 border-blue-400/20",
  Subscriptions: "bg-purple-400/10 text-purple-300 border-purple-400/20",
  Transfers: "bg-white/10 text-neutral-300 border-white/15",
  Shopping: "bg-pink-400/10 text-pink-300 border-pink-400/20",
  Other: "bg-deep-gray text-neutral-400 border-white/10",
};

export const TransactionTable: React.FC<TransactionTableProps> = ({
  transactions,
  total,
  loading,
  page,
  pageSize,
  search,
  category,
  txnType,
  startDate = "",
  endDate = "",
  onPageChange,
  onSearchChange,
  onCategoryChange,
  onTxnTypeChange,
  onStartDateChange,
  onEndDateChange,
  onUpdateCategory,
  onDeleteTransaction,
  onDeleteAllTransactions,
  showExport = true,
  viewAllHref,
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState<string>("");
  const [isUpdating, setIsUpdating] = useState<boolean>(false);

  // Sorting state for client-side sorting of loaded data
  const [sortField, setSortField] = useState<"date" | "amount" | "description">("date");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

  // Deletion States
  const [singleDeleteTarget, setSingleDeleteTarget] = useState<Transaction | null>(null);
  const [isDeletingSingle, setIsDeletingSingle] = useState<boolean>(false);

  const [isBulkDeleteModalOpen, setIsBulkDeleteModalOpen] = useState<boolean>(false);
  const [isDeletingBulk, setIsDeletingBulk] = useState<boolean>(false);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Client-side sorted transactions
  const sortedTransactions = useMemo(() => {
    return [...transactions].sort((a, b) => {
      let comparison = 0;
      if (sortField === "date") {
        comparison = new Date(a.txn_date).getTime() - new Date(b.txn_date).getTime();
      } else if (sortField === "amount") {
        comparison = Number(a.amount) - Number(b.amount);
      } else if (sortField === "description") {
        comparison = (a.description || "").localeCompare(b.description || "");
      }
      return sortDirection === "desc" ? -comparison : comparison;
    });
  }, [transactions, sortField, sortDirection]);

  const handleSort = (field: "date" | "amount" | "description") => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const handleStartEdit = (txn: Transaction) => {
    setEditingId(txn.id);
    setEditCategory(txn.category || "Other");
  };

  const handleSaveEdit = async (txnId: string) => {
    if (!editCategory) return;
    setIsUpdating(true);
    try {
      await onUpdateCategory(txnId, editCategory);
      setEditingId(null);
    } finally {
      setIsUpdating(false);
    }
  };

  const confirmSingleDelete = async () => {
    if (!singleDeleteTarget || !onDeleteTransaction) return;
    setIsDeletingSingle(true);
    try {
      await onDeleteTransaction(singleDeleteTarget.id);
      setSingleDeleteTarget(null);
    } finally {
      setIsDeletingSingle(false);
    }
  };

  const confirmBulkDelete = async () => {
    if (!onDeleteAllTransactions) return;
    setIsDeletingBulk(true);
    try {
      await onDeleteAllTransactions();
      setIsBulkDeleteModalOpen(false);
    } finally {
      setIsDeletingBulk(false);
    }
  };

  const exportCSV = () => {
    if (!transactions.length) return;
    const headers = ["Date", "Description", "Type", "Amount", "Category"];
    const rows = transactions.map((t) => [
      t.txn_date,
      `"${(t.description || "").replace(/"/g, '""')}"`,
      t.txn_type,
      Number(t.amount).toFixed(2),
      t.category || "Other",
    ]);
    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Fluxo_Ledger_Export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="bg-charcoal/90 border border-white/10 rounded-[32px] p-6 sm:p-8 shadow-glass backdrop-blur-2xl">
      {/* Table Header & Search Filter Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5 pb-6 border-b border-white/10">
        <div>
          <div className="flex items-center space-x-3">
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight font-sans">
              Normalized Transaction Ledger
            </h2>
            <Pill variant="neutral" className="tabular-nums">
              {total.toLocaleString()} RECORDS
            </Pill>
          </div>
          <p className="text-xs sm:text-sm text-neutral-400 mt-1">
            Deterministic SHA-256 deduplicated records with ML merchant categorization
          </p>
        </div>

        {/* Global Table Actions */}
        <div className="flex flex-wrap items-center gap-2.5">
          {showExport && (
            <Button
              variant="outline-white"
              size="sm"
              onClick={exportCSV}
              disabled={loading || transactions.length === 0}
              className="flex items-center space-x-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </Button>
          )}

          {onDeleteAllTransactions && total > 0 && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setIsBulkDeleteModalOpen(true)}
              className="flex items-center space-x-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear Ledger</span>
            </Button>
          )}

          {viewAllHref && (
            <Link href={viewAllHref}>
              <Button variant="yellow" size="sm" className="flex items-center space-x-1.5">
                <span>View Full Studio</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Filter Ribbon: Search, Type, Category & Date Ranges */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 py-5 border-b border-white/10 text-xs">
        {/* Search Input */}
        <div className="md:col-span-5 relative">
          <Search className="w-4 h-4 text-neutral-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search merchant, memo or description..."
            className="w-full pl-9 pr-8 py-2.5 rounded-full bg-deep-gray border border-white/10 text-white placeholder-neutral-500 focus:outline-none focus:border-cyber-yellow transition text-xs font-sans"
          />
          {search && (
            <button
              onClick={() => onSearchChange("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Transaction Type Filter */}
        <div className="md:col-span-3">
          <div className="flex items-center p-1 rounded-full bg-deep-gray border border-white/10">
            {(["ALL", "DEBIT", "CREDIT"] as const).map((type) => (
              <button
                key={type}
                onClick={() => onTxnTypeChange(type)}
                className={`flex-1 py-1.5 rounded-full text-xs font-mono font-semibold transition-all duration-200 ${
                  txnType === type
                    ? "bg-white text-black shadow-sm"
                    : "text-neutral-400 hover:text-white"
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Category Dropdown */}
        <div className="md:col-span-4">
          <select
            value={category}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="w-full px-4 py-2.5 rounded-full bg-deep-gray border border-white/10 text-white focus:outline-none focus:border-cyber-yellow transition text-xs font-sans appearance-none cursor-pointer"
          >
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat} className="bg-charcoal text-white">
                Category: {cat}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table Container */}
      <div className="mt-4 overflow-x-auto rounded-[24px] border border-white/10">
        <table className="w-full text-left text-xs whitespace-nowrap">
          <thead className="sticky top-0 bg-deep-gray/95 backdrop-blur-md text-[10px] uppercase tracking-widest text-neutral-400 font-mono border-b border-white/10">
            <tr>
              <th
                onClick={() => handleSort("date")}
                className="py-3.5 px-4 font-bold cursor-pointer hover:text-white transition"
              >
                <div className="flex items-center space-x-1.5">
                  <span>Date</span>
                  <ArrowUpDown className="w-3 h-3 text-neutral-500" />
                </div>
              </th>
              <th
                onClick={() => handleSort("description")}
                className="py-3.5 px-4 font-bold cursor-pointer hover:text-white transition"
              >
                <div className="flex items-center space-x-1.5">
                  <span>Description</span>
                  <ArrowUpDown className="w-3 h-3 text-neutral-500" />
                </div>
              </th>
              <th className="py-3.5 px-4 font-bold">Category</th>
              <th className="py-3.5 px-4 font-bold text-center">Type</th>
              <th
                onClick={() => handleSort("amount")}
                className="py-3.5 px-4 font-bold text-right cursor-pointer hover:text-white transition"
              >
                <div className="flex items-center justify-end space-x-1.5">
                  <span>Amount</span>
                  <ArrowUpDown className="w-3 h-3 text-neutral-500" />
                </div>
              </th>
              {onDeleteTransaction && (
                <th className="py-3.5 px-4 font-bold text-center">Actions</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 font-sans">
            {loading ? (
              <tr>
                <td colSpan={6} className="py-16 text-center text-neutral-400 font-mono">
                  <div className="flex flex-col items-center justify-center space-y-3">
                    <Loader2 className="w-6 h-6 text-cyber-yellow animate-spin" />
                    <span>Loading ledger records...</span>
                  </div>
                </td>
              </tr>
            ) : sortedTransactions.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-16 text-center">
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <Receipt className="w-8 h-8 text-neutral-600 mb-1" />
                    <p className="text-sm font-semibold text-white">No transactions match your query</p>
                    <p className="text-xs text-neutral-400 max-w-sm">
                      Upload bank statements to ingest records or adjust your active search filters.
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              sortedTransactions.map((txn) => {
                const isDebit = txn.txn_type === "DEBIT";
                const isEditing = editingId === txn.id;
                const numericAmount = Number(txn.amount) || 0;

                return (
                  <tr
                    key={txn.id}
                    className="hover:bg-white/[0.03] transition-colors group"
                  >
                    {/* Date */}
                    <td className="py-3.5 px-4 font-mono text-neutral-300 tabular-nums">
                      {txn.txn_date}
                    </td>

                    {/* Description */}
                    <td className="py-3.5 px-4 text-white font-medium max-w-xs sm:max-w-md truncate">
                      {txn.description}
                    </td>

                    {/* Category Pill / Inline Editor */}
                    <td className="py-3.5 px-4">
                      {isEditing ? (
                        <div className="flex items-center space-x-1.5">
                          <select
                            value={editCategory}
                            onChange={(e) => setEditCategory(e.target.value)}
                            className="bg-deep-gray border border-cyber-yellow text-white text-xs rounded-full px-3 py-1 font-sans focus:outline-none"
                          >
                            {CATEGORIES.filter((c) => c !== "All").map((c) => (
                              <option key={c} value={c} className="bg-charcoal text-white">
                                {c}
                              </option>
                            ))}
                          </select>
                          <button
                            onClick={() => handleSaveEdit(txn.id)}
                            disabled={isUpdating}
                            className="p-1 rounded-full bg-cyber-yellow text-black hover:bg-yellow-300 transition"
                            title="Save"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setEditingId(null)}
                            className="p-1 rounded-full bg-deep-gray text-neutral-400 hover:text-white transition"
                            title="Cancel"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleStartEdit(txn)}
                          className={`inline-flex items-center space-x-1.5 px-3 py-0.5 rounded-full text-[11px] font-medium border transition-transform hover:scale-105 ${
                            CATEGORY_STYLES[txn.category || "Other"] ||
                            CATEGORY_STYLES["Other"]
                          }`}
                          title="Click to override category"
                        >
                          <span>{txn.category || "Other"}</span>
                          <Tag className="w-2.5 h-2.5 opacity-60" />
                        </button>
                      )}
                    </td>

                    {/* Type Badge */}
                    <td className="py-3.5 px-4 text-center font-mono">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider ${
                          isDebit
                            ? "bg-danger/10 text-danger border border-danger/20"
                            : "bg-success/10 text-success border border-success/20"
                        }`}
                      >
                        {isDebit ? (
                          <ArrowUpRight className="w-2.5 h-2.5 mr-0.5" />
                        ) : (
                          <ArrowDownLeft className="w-2.5 h-2.5 mr-0.5" />
                        )}
                        {txn.txn_type}
                      </span>
                    </td>

                    {/* Amount */}
                    <td className="py-3.5 px-4 text-right font-mono font-bold tabular-nums">
                      <span
                        className={
                          isDebit ? "text-danger" : "text-success"
                        }
                      >
                        {isDebit ? "-" : "+"}
                        ${numericAmount.toLocaleString("en-US", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </span>
                    </td>

                    {/* Actions */}
                    {onDeleteTransaction && (
                      <td className="py-3.5 px-4 text-center">
                        <button
                          onClick={() => setSingleDeleteTarget(txn)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded-full text-neutral-500 hover:text-danger hover:bg-danger/10 transition"
                          title="Delete transaction"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="mt-5 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-neutral-400 font-mono">
        <div>
          Showing page <span className="text-white font-bold tabular-nums">{page}</span> of{" "}
          <span className="text-white font-bold tabular-nums">{totalPages}</span> (
          <span className="tabular-nums">{total}</span> total entries)
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || loading}
            className="px-3.5 py-1.5 rounded-full bg-deep-gray border border-white/10 hover:border-white/30 text-white disabled:opacity-30 disabled:pointer-events-none transition flex items-center space-x-1"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            <span>Prev</span>
          </button>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || loading}
            className="px-3.5 py-1.5 rounded-full bg-deep-gray border border-white/10 hover:border-white/30 text-white disabled:opacity-30 disabled:pointer-events-none transition flex items-center space-x-1"
          >
            <span>Next</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Single Delete Confirmation Modal */}
      {singleDeleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-md bg-charcoal border border-white/20 rounded-[32px] p-6 shadow-2xl backdrop-blur-2xl">
            <div className="flex items-center space-x-3 text-danger mb-4">
              <div className="w-10 h-10 rounded-full bg-danger/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-white font-sans">Delete Transaction?</h3>
            </div>
            <p className="text-xs text-neutral-300 mb-4 leading-relaxed font-sans">
              This will permanently purge this record from your database ledger and recalibrate the time-series model.
            </p>
            <div className="p-3 rounded-2xl bg-deep-gray border border-white/10 font-mono text-xs mb-5">
              <div className="text-white truncate font-semibold">{singleDeleteTarget.description}</div>
              <div className="flex justify-between text-neutral-400 mt-1">
                <span>{singleDeleteTarget.txn_date}</span>
                <span className="text-white font-bold">${Number(singleDeleteTarget.amount).toFixed(2)}</span>
              </div>
            </div>
            <div className="flex items-center justify-end space-x-3">
              <Button
                variant="outline-white"
                size="sm"
                onClick={() => setSingleDeleteTarget(null)}
                disabled={isDeletingSingle}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={confirmSingleDelete}
                disabled={isDeletingSingle}
              >
                {isDeletingSingle ? "Deleting..." : "Confirm Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Delete All Modal */}
      {isBulkDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-md bg-charcoal border border-white/20 rounded-[32px] p-6 shadow-2xl backdrop-blur-2xl">
            <div className="flex items-center space-x-3 text-danger mb-4">
              <div className="w-10 h-10 rounded-full bg-danger/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-white font-sans">Clear Entire Ledger?</h3>
            </div>
            <p className="text-xs text-neutral-300 mb-6 leading-relaxed font-sans">
              Are you sure you want to delete all <strong className="text-white">{total}</strong> transactions? This cannot be undone.
            </p>
            <div className="flex items-center justify-end space-x-3">
              <Button
                variant="outline-white"
                size="sm"
                onClick={() => setIsBulkDeleteModalOpen(false)}
                disabled={isDeletingBulk}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={confirmBulkDelete}
                disabled={isDeletingBulk}
              >
                {isDeletingBulk ? "Purging..." : "Purge All Data"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
