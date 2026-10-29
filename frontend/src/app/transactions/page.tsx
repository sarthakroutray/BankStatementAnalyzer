"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { Footer } from "../../components/Footer";
import { TransactionTable } from "../../components/TransactionTable";
import { UploadModal } from "../../components/UploadModal";
import { fetchTransactions, updateCategory, deleteTransaction, deleteAllTransactions } from "../../lib/api";
import { Transaction } from "../../lib/types";
import {
  Receipt,
  Download,
  Filter,
  DollarSign,
  ArrowUpRight,
  ArrowDownLeft,
  Calendar,
} from "lucide-react";

export default function TransactionsLedgerPage() {
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [txnType, setTxnType] = useState("ALL");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchTransactions({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        search: search.trim() || undefined,
        category: category,
        txn_type: txnType,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      setTransactions(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error("Failed to fetch transactions:", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, category, txnType, startDate, endDate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleUpdateCategory = async (txnId: string, newCategory: string) => {
    try {
      await updateCategory(txnId, newCategory);
      loadData();
    } catch (err) {
      console.error("Failed to update transaction category:", err);
    }
  };

  const handleDeleteTransaction = async (txnId: string) => {
    try {
      await deleteTransaction(txnId);
      await loadData();
    } catch (err) {
      console.error("Failed to delete transaction:", err);
    }
  };

  const handleDeleteAllTransactions = async () => {
    try {
      await deleteAllTransactions();
      setPage(1);
      await loadData();
    } catch (err) {
      console.error("Failed to delete all transactions:", err);
    }
  };

  // Compute stats on the loaded page
  const pageDebitSum = transactions
    .filter((t) => t.txn_type === "DEBIT")
    .reduce((acc, t) => acc + (typeof t.amount === "number" ? t.amount : parseFloat(String(t.amount)) || 0), 0);

  const pageCreditSum = transactions
    .filter((t) => t.txn_type === "CREDIT")
    .reduce((acc, t) => acc + (typeof t.amount === "number" ? t.amount : parseFloat(String(t.amount)) || 0), 0);

  return (
    <div className="min-h-screen flex flex-col bg-canvas selection:bg-blue-600/30 selection:text-white">
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Breadcrumb Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
          <div>
            <div className="flex items-center space-x-2 text-xs text-muted-foreground font-mono mb-1">
              <Link href="/" className="hover:text-white transition">
                OVERVIEW
              </Link>
              <span>/</span>
              <span className="text-blue-400">TRANSACTION LEDGER</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white font-sans">
              Normalized Bank Statement Ledger
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Auditable transaction records extracted deterministically with cryptographic SHA-256 deduplication
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="py-1.5 px-3 rounded-lg bg-slate-900 border border-border text-xs text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer font-mono"
            >
              <option value={15}>15 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
            </select>
          </div>
        </div>

        {/* Aggregate Filtered Ribbon */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-card border border-border/80 shadow-subtle flex items-center justify-between font-mono">
            <div>
              <span className="text-[11px] font-sans text-muted-foreground block mb-1">
                Total Matches
              </span>
              <span className="text-xl font-bold text-white">
                {total.toLocaleString()} records
              </span>
            </div>
            <div className="p-2 rounded-lg bg-slate-800 text-slate-300">
              <Receipt className="w-4 h-4" />
            </div>
          </div>

          <div className="p-4 rounded-xl bg-card border border-border/80 shadow-subtle flex items-center justify-between font-mono">
            <div>
              <span className="text-[11px] font-sans text-muted-foreground block mb-1">
                Visible Debit Outflow
              </span>
              <span className="text-xl font-bold text-rose-400">
                -${pageDebitSum.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <ArrowUpRight className="w-4 h-4" />
            </div>
          </div>

          <div className="p-4 rounded-xl bg-card border border-border/80 shadow-subtle flex items-center justify-between font-mono">
            <div>
              <span className="text-[11px] font-sans text-muted-foreground block mb-1">
                Visible Credit Inflow
              </span>
              <span className="text-xl font-bold text-emerald-400">
                +${pageCreditSum.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <ArrowDownLeft className="w-4 h-4" />
            </div>
          </div>
        </div>

        {/* Main Table */}
        <section aria-label="Transaction Ledger Table">
          <TransactionTable
            transactions={transactions}
            total={total}
            loading={loading}
            page={page}
            pageSize={pageSize}
            search={search}
            category={category}
            txnType={txnType}
            startDate={startDate}
            endDate={endDate}
            onPageChange={(p) => setPage(p)}
            onSearchChange={(s) => {
              setSearch(s);
              setPage(1);
            }}
            onCategoryChange={(c) => {
              setCategory(c);
              setPage(1);
            }}
            onTxnTypeChange={(t) => {
              setTxnType(t);
              setPage(1);
            }}
            onStartDateChange={(d) => {
              setStartDate(d);
              setPage(1);
            }}
            onEndDateChange={(d) => {
              setEndDate(d);
              setPage(1);
            }}
            onUpdateCategory={handleUpdateCategory}
            onDeleteTransaction={handleDeleteTransaction}
            onDeleteAllTransactions={handleDeleteAllTransactions}
            showExport={true}
          />
        </section>
      </main>

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => {
          setPage(1);
          loadData();
        }}
      />

      <Footer />
    </div>
  );
}
