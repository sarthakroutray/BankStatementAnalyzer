"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Search,
  Filter,
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
} from "lucide-react";
import { Transaction } from "../lib/types";

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
  "Food & Dining": "bg-amber-500/10 text-amber-400 border-amber-500/20",
  Groceries: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  Utilities: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  Travel: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  Subscriptions: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  Transfers: "bg-slate-700/40 text-slate-300 border-slate-600/40",
  Shopping: "bg-pink-500/10 text-pink-400 border-pink-500/20",
  Other: "bg-slate-800 text-slate-400 border-slate-700/60",
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

  // Deletion States
  const [singleDeleteTarget, setSingleDeleteTarget] = useState<Transaction | null>(null);
  const [isDeletingSingle, setIsDeletingSingle] = useState<boolean>(false);
  const [showDeleteAllModal, setShowDeleteAllModal] = useState<boolean>(false);
  const [isDeletingAll, setIsDeletingAll] = useState<boolean>(false);

  const totalPages = Math.ceil(total / pageSize) || 1;

  const handleStartEdit = (txn: Transaction) => {
    setEditingId(txn.id);
    setEditCategory(txn.category);
  };

  const handleSaveEdit = async (txnId: string) => {
    if (!editCategory) return;
    setIsUpdating(true);
    try {
      await onUpdateCategory(txnId, editCategory);
      setEditingId(null);
    } catch (err) {
      console.error("Failed to update transaction category:", err);
    } finally {
      setIsUpdating(false);
    }
  };

  // CSV Export utility
  const handleExportCSV = () => {
    if (!transactions.length) return;
    const headers = ["ID", "Date", "Description", "Category", "Type", "Amount", "Balance", "Hash"];
    const rows = transactions.map((t) => [
      t.id,
      t.txn_date,
      `"${(t.description || "").replace(/"/g, '""')}"`,
      t.category,
      t.txn_type,
      typeof t.amount === "number" ? t.amount.toFixed(2) : t.amount,
      t.balance !== null && t.balance !== undefined ? t.balance : "",
      t.row_hash,
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `finwise_ledger_${new Date().toISOString().split("T")[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="bg-card border border-border/80 rounded-xl p-5 sm:p-6 shadow-subtle flex flex-col justify-between">
      {/* Header & Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-5 border-b border-border/60">
        <div className="flex items-center justify-between w-full lg:w-auto">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                Normalized Transaction Ledger
              </h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700">
                {total.toLocaleString()} records
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Deduplicated transactions extracted deterministically with AI categorization overrides
            </p>
          </div>
          {viewAllHref && (
            <Link
              href={viewAllHref}
              className="lg:hidden text-xs text-blue-400 hover:text-blue-300 flex items-center font-medium"
            >
              <span>Full Ledger</span>
              <ArrowRight className="w-3 h-3 ml-0.5" />
            </Link>
          )}
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Search Input */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search description..."
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              className="pl-9 pr-7 py-1.5 rounded-lg bg-slate-900 border border-border text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 w-40 sm:w-52 transition"
            />
            {search && (
              <button
                onClick={() => onSearchChange("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                title="Clear search"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Category Filter */}
          <div className="relative flex items-center">
            <Filter className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
            <select
              value={category}
              onChange={(e) => onCategoryChange(e.target.value)}
              className="pl-7 pr-3 py-1.5 rounded-lg bg-slate-900 border border-border text-xs text-white appearance-none focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c === "All" ? "All Categories" : c}
                </option>
              ))}
            </select>
          </div>

          {/* Type Filter */}
          <div className="flex items-center bg-slate-900 p-0.5 rounded-lg border border-border text-xs">
            {["ALL", "DEBIT", "CREDIT"].map((t) => (
              <button
                key={t}
                onClick={() => onTxnTypeChange(t)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                  txnType === t
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-muted-foreground hover:text-white"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Date Pickers (if handlers provided) */}
          {onStartDateChange && (
            <div className="flex items-center space-x-1 bg-slate-900 px-2 py-1 rounded-lg border border-border text-xs">
              <Calendar className="w-3 h-3 text-slate-400" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => onStartDateChange(e.target.value)}
                className="bg-transparent text-white text-[11px] focus:outline-none"
                title="Start Date"
              />
              <span className="text-slate-500">-</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => onEndDateChange?.(e.target.value)}
                className="bg-transparent text-white text-[11px] focus:outline-none"
                title="End Date"
              />
              {(startDate || endDate) && (
                <button
                  onClick={() => {
                    onStartDateChange("");
                    onEndDateChange?.("");
                  }}
                  className="text-slate-400 hover:text-white pl-1"
                  title="Clear date filter"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          )}

          {/* CSV Export Button */}
          {showExport && (
            <button
              onClick={handleExportCSV}
              disabled={transactions.length === 0}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-border text-xs font-medium transition disabled:opacity-40"
              title="Download CSV of current table records"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Export CSV</span>
            </button>
          )}

          {/* Delete All Button */}
          {onDeleteAllTransactions && (
            <button
              onClick={() => setShowDeleteAllModal(true)}
              disabled={total === 0 || loading || isDeletingAll}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 border border-rose-500/20 text-xs font-medium transition disabled:opacity-40 disabled:cursor-not-allowed"
              title={total === 0 ? "No transactions to delete" : "Delete all transactions from database"}
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete All</span>
            </button>
          )}

          {viewAllHref && (
            <Link
              href={viewAllHref}
              className="hidden lg:flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-blue-600/10 text-blue-400 border border-blue-500/20 hover:bg-blue-600/20 text-xs font-medium transition ml-1"
            >
              <span>Full Ledger</span>
              <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
            </Link>
          )}
        </div>
      </div>

      {/* Table view */}
      <div className="overflow-x-auto mt-4">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border/80 text-muted-foreground uppercase tracking-wider font-semibold text-[11px]">
              <th className="py-2.5 px-3">Date</th>
              <th className="py-2.5 px-3">Description</th>
              <th className="py-2.5 px-3">Category</th>
              <th className="py-2.5 px-3">Type</th>
              <th className="py-2.5 px-3 text-right">Amount</th>
              <th className="py-2.5 px-3 text-right">Balance</th>
              {onDeleteTransaction && <th className="py-2.5 px-3 text-right">Action</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40 font-mono">
            {loading ? (
              <tr>
                <td colSpan={onDeleteTransaction ? 7 : 6} className="py-12 text-center text-muted-foreground font-sans">
                  Querying transactions from PostgreSQL...
                </td>
              </tr>
            ) : transactions.length === 0 ? (
              <tr>
                <td colSpan={onDeleteTransaction ? 7 : 6} className="py-12 text-center text-muted-foreground font-sans">
                  No matching transactions found. Try adjusting filters or search query.
                </td>
              </tr>
            ) : (
              transactions.map((txn) => {
                const isDebit = txn.txn_type === "DEBIT";
                const isEditing = editingId === txn.id;
                const amt = typeof txn.amount === "number" ? txn.amount : (parseFloat(String(txn.amount)) || 0);
                const bal = txn.balance !== null && txn.balance !== undefined
                  ? typeof txn.balance === "number" ? txn.balance : parseFloat(String(txn.balance))
                  : null;

                return (
                  <tr key={txn.id} className="hover:bg-slate-900/60 transition group">
                    <td className="py-3 px-3 text-slate-400 whitespace-nowrap">{txn.txn_date}</td>
                    <td className="py-3 px-3 text-slate-200 font-sans max-w-sm truncate" title={txn.description}>
                      {txn.description}
                    </td>

                    {/* Category with inline override */}
                    <td className="py-3 px-3 whitespace-nowrap font-sans">
                      {isEditing ? (
                        <div className="flex items-center space-x-1.5">
                          <select
                            value={editCategory}
                            onChange={(e) => setEditCategory(e.target.value)}
                            className="py-1 px-2 text-xs rounded bg-slate-900 border border-blue-500 text-white focus:outline-none"
                          >
                            {CATEGORIES.filter((c) => c !== "All").map((cat) => (
                              <option key={cat} value={cat}>
                                {cat}
                              </option>
                            ))}
                          </select>
                          <button
                            onClick={() => handleSaveEdit(txn.id)}
                            disabled={isUpdating}
                            className="p-1 rounded bg-blue-600 text-white hover:bg-blue-500"
                            title="Save"
                          >
                            <Check className="w-3 h-3" />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleStartEdit(txn)}
                          className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-[11px] font-medium border transition ${
                            CATEGORY_STYLES[txn.category] || CATEGORY_STYLES["Other"]
                          } hover:brightness-125`}
                          title="Click to override category"
                        >
                          <Tag className="w-2.5 h-2.5 mr-0.5 opacity-70" />
                          <span>{txn.category}</span>
                        </button>
                      )}
                    </td>

                    {/* Type Badge */}
                    <td className="py-3 px-3 whitespace-nowrap font-sans">
                      <span
                        className={`inline-flex items-center text-[11px] font-semibold px-2 py-0.5 rounded ${
                          isDebit
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        }`}
                      >
                        {isDebit ? (
                          <ArrowUpRight className="w-3 h-3 mr-0.5" />
                        ) : (
                          <ArrowDownLeft className="w-3 h-3 mr-0.5" />
                        )}
                        {txn.txn_type}
                      </span>
                    </td>

                    {/* Amount */}
                    <td
                      className={`py-3 px-3 text-right font-bold whitespace-nowrap ${
                        isDebit ? "text-rose-400" : "text-emerald-400"
                      }`}
                    >
                      {isDebit ? "-" : "+"}${amt.toFixed(2)}
                    </td>

                    {/* Running Balance */}
                    <td className="py-3 px-3 text-right text-slate-400 whitespace-nowrap">
                      {bal !== null && !isNaN(bal) ? `$${bal.toFixed(2)}` : "—"}
                    </td>

                    {/* Delete Action */}
                    {onDeleteTransaction && (
                      <td className="py-3 px-3 text-right whitespace-nowrap">
                        <button
                          onClick={() => setSingleDeleteTarget(txn)}
                          disabled={isDeletingSingle}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition disabled:opacity-40"
                          title="Delete this transaction"
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-4 mt-3 border-t border-border/60 text-xs text-muted-foreground">
        <div>
          Showing {transactions.length > 0 ? (page - 1) * pageSize + 1 : 0} to{" "}
          {Math.min(page * pageSize, total)} of {total.toLocaleString()} records
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || loading}
            className="p-1.5 rounded-lg border border-border bg-slate-900 hover:bg-slate-800 disabled:opacity-30 transition"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="font-mono px-2 text-slate-300">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || loading}
            className="p-1.5 rounded-lg border border-border bg-slate-900 hover:bg-slate-800 disabled:opacity-30 transition"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Single Delete Confirmation Modal */}
      {singleDeleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-card border border-border rounded-xl w-full max-w-md overflow-hidden shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border/80 bg-slate-900/60">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                  <Trash2 className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white tracking-tight">Delete Transaction</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Confirm permanent record removal</p>
                </div>
              </div>
              <button
                onClick={() => !isDeletingSingle && setSingleDeleteTarget(null)}
                className="text-slate-400 hover:text-white transition"
                disabled={isDeletingSingle}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-xs text-slate-300 leading-relaxed">
                Are you sure you want to delete this transaction from the ledger? This action cannot be reversed.
              </p>

              <div className="p-3.5 rounded-lg bg-slate-900/80 border border-border/60 text-xs space-y-2 font-mono">
                <div className="flex justify-between text-slate-400">
                  <span className="font-sans">Date:</span>
                  <span className="text-slate-200">{singleDeleteTarget.txn_date}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span className="font-sans">Description:</span>
                  <span className="text-slate-200 truncate max-w-[200px]" title={singleDeleteTarget.description}>
                    {singleDeleteTarget.description}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span className="font-sans">Amount:</span>
                  <span className={`font-bold ${singleDeleteTarget.txn_type === "DEBIT" ? "text-rose-400" : "text-emerald-400"}`}>
                    {singleDeleteTarget.txn_type === "DEBIT" ? "-" : "+"}${Number(singleDeleteTarget.amount).toFixed(2)}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSingleDeleteTarget(null)}
                  disabled={isDeletingSingle}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    if (!singleDeleteTarget || !onDeleteTransaction) return;
                    setIsDeletingSingle(true);
                    try {
                      await onDeleteTransaction(singleDeleteTarget.id);
                      setSingleDeleteTarget(null);
                    } catch (err) {
                      console.error("Failed to delete transaction:", err);
                    } finally {
                      setIsDeletingSingle(false);
                    }
                  }}
                  disabled={isDeletingSingle}
                  className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition flex items-center space-x-1.5 disabled:opacity-50"
                >
                  {isDeletingSingle ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Deleting...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Confirm Delete</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete All Confirmation Modal */}
      {showDeleteAllModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-card border border-border rounded-xl w-full max-w-md overflow-hidden shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border/80 bg-slate-900/60">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white tracking-tight">Delete All Transactions</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Destructive ledger reset</p>
                </div>
              </div>
              <button
                onClick={() => !isDeletingAll && setShowDeleteAllModal(false)}
                className="text-slate-400 hover:text-white transition"
                disabled={isDeletingAll}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs leading-relaxed flex items-start space-x-2.5">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span>
                  This action will permanently delete all <strong>{total.toLocaleString()}</strong> transaction records and clear past forecasts. This action cannot be undone.
                </span>
              </div>

              <p className="text-xs text-slate-400">
                Are you sure you want to clear the entire transaction ledger?
              </p>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowDeleteAllModal(false)}
                  disabled={isDeletingAll}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    if (!onDeleteAllTransactions) return;
                    setIsDeletingAll(true);
                    try {
                      await onDeleteAllTransactions();
                      setShowDeleteAllModal(false);
                    } catch (err) {
                      console.error("Failed to delete all transactions:", err);
                    } finally {
                      setIsDeletingAll(false);
                    }
                  }}
                  disabled={isDeletingAll}
                  className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition flex items-center space-x-1.5 disabled:opacity-50"
                >
                  {isDeletingAll ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Deleting All...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Yes, Delete All ({total.toLocaleString()})</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
