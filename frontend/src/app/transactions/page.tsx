"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { Footer } from "../../components/Footer";
import { TransactionTable } from "../../components/TransactionTable";
import { UploadModal } from "../../components/UploadModal";
import { Button } from "../../components/ui/Button";
import { Pill } from "../../components/ui/Pill";
import { fetchTransactions, updateCategory, deleteTransaction, deleteAllTransactions } from "../../lib/api";
import { Transaction } from "../../lib/types";
import {
  Receipt,
  Download,
  Filter,
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
    <div className="min-h-screen flex flex-col bg-onyx text-white selection:bg-cyber-yellow selection:text-black">
      <Navbar onOpenUpload={() => setIsUploadOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 sm:px-8 py-10 space-y-8">
        {/* Breadcrumb Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
          <div>
            <div className="flex items-center space-x-2 text-[10px] font-mono tracking-widest text-neutral-400 mb-1">
              <Link href="/" className="hover:text-white transition">
                OVERVIEW
              </Link>
              <span>/</span>
              <span className="text-cyber-yellow font-bold">TRANSACTION LEDGER</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-sans">
              Normalized Bank Statement Ledger
            </h1>
            <p className="text-xs sm:text-sm text-neutral-400 mt-1">
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
              className="py-2 px-4 rounded-full bg-deep-gray border border-white/10 text-xs text-white focus:outline-none focus:border-cyber-yellow cursor-pointer font-mono"
            >
              <option value={15} className="bg-charcoal text-white">15 per page</option>
              <option value={25} className="bg-charcoal text-white">25 per page</option>
              <option value={50} className="bg-charcoal text-white">50 per page</option>
              <option value={100} className="bg-charcoal text-white">100 per page</option>
            </select>
          </div>
        </div>

        {/* Aggregate Filtered Ribbon */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex items-center justify-between font-mono">
            <div>
              <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest block mb-1">
                Total Matches
              </span>
              <span className="text-2xl font-bold text-white tabular-nums">
                {total.toLocaleString()} records
              </span>
            </div>
            <div className="w-10 h-10 rounded-full bg-deep-gray border border-white/10 flex items-center justify-center text-cyber-yellow">
              <Receipt className="w-5 h-5" />
            </div>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex items-center justify-between font-mono">
            <div>
              <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest block mb-1">
                Visible Debit Outflow
              </span>
              <span className="text-2xl font-bold text-danger tabular-nums">
                -${pageDebitSum.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="w-10 h-10 rounded-full bg-danger/10 border border-danger/20 flex items-center justify-center text-danger">
              <ArrowUpRight className="w-5 h-5" />
            </div>
          </div>

          <div className="p-6 rounded-[32px] bg-charcoal/90 border border-white/10 shadow-glass backdrop-blur-2xl flex items-center justify-between font-mono">
            <div>
              <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest block mb-1">
                Visible Credit Inflow
              </span>
              <span className="text-2xl font-bold text-success tabular-nums">
                +${pageCreditSum.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="w-10 h-10 rounded-full bg-success/10 border border-success/20 flex items-center justify-center text-success">
              <ArrowDownLeft className="w-5 h-5" />
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
