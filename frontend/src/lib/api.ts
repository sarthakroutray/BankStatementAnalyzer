import {
  AnalyticsSummary,
  DeleteResponse,
  ForecastResponse,
  PaginatedTransactions,
  Statement,
  Transaction,
  UploadResponse,
} from "./types";

const getApiBase = () => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "");
  }
  return "http://localhost:8000";
};

export const API_BASE = getApiBase();

export async function uploadStatement(
  file: File,
  onProgress?: (stage: string) => void
): Promise<UploadResponse> {
  if (onProgress) onProgress("Uploading PDF statement to backend...");

  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/v1/statements/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with HTTP ${res.status}`);
  }

  return res.json();
}

export async function fetchTransactions(params: {
  category?: string;
  txn_type?: string;
  search?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedTransactions> {
  const url = new URL(`${API_BASE}/api/v1/transactions`);
  if (params.category && params.category !== "All") url.searchParams.append("category", params.category);
  if (params.txn_type && params.txn_type !== "ALL") url.searchParams.append("txn_type", params.txn_type);
  if (params.search) url.searchParams.append("search", params.search);
  if (params.start_date) url.searchParams.append("start_date", params.start_date);
  if (params.end_date) url.searchParams.append("end_date", params.end_date);
  if (params.limit) url.searchParams.append("limit", params.limit.toString());
  if (params.offset !== undefined) url.searchParams.append("offset", params.offset.toString());

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch transactions (${res.status})`);
  }
  return res.json();
}

export async function updateCategory(txnId: string, category: string): Promise<Transaction> {
  const res = await fetch(`${API_BASE}/api/v1/transactions/${txnId}/category`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to update category");
  }
  return res.json();
}

export async function deleteTransaction(txnId: string): Promise<DeleteResponse> {
  const res = await fetch(`${API_BASE}/api/v1/transactions/${txnId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to delete transaction");
  }
  return res.json();
}

export async function deleteAllTransactions(): Promise<DeleteResponse> {
  const res = await fetch(`${API_BASE}/api/v1/transactions`, {
    method: "DELETE",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to delete all transactions");
  }
  return res.json();
}


export async function generateForecast(
  granularity: "DAILY" | "WEEKLY" = "DAILY",
  horizon: number = 30
): Promise<ForecastResponse> {
  const res = await fetch(`${API_BASE}/api/v1/forecasts/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ granularity, horizon }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Forecast generation failed");
  }
  return res.json();
}

export async function fetchLatestForecast(
  granularity: "DAILY" | "WEEKLY" = "DAILY",
  horizon: number = 30
): Promise<ForecastResponse | null> {
  const res = await fetch(
    `${API_BASE}/api/v1/forecasts/latest?granularity=${granularity}&horizon=${horizon}`,
    { cache: "no-store" }
  );

  if (res.status === 400 || res.status === 404) {
    const errorData = await res.json().catch(() => ({}));
    if (
      errorData.detail?.includes("No DEBIT transactions") ||
      errorData.detail?.includes("No forecast") ||
      errorData.detail?.includes("Insufficient")
    ) {
      return null;
    }
    throw new Error(errorData.detail || "Failed to retrieve forecast");
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to retrieve forecast");
  }
  return res.json();
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const res = await fetch(`${API_BASE}/api/v1/analytics/summary`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch analytics summary (${res.status})`);
  }
  return res.json();
}

export async function fetchStatements(limit = 50, offset = 0): Promise<Statement[]> {
  const res = await fetch(`${API_BASE}/api/v1/statements?limit=${limit}&offset=${offset}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch statements (${res.status})`);
  }
  return res.json();
}

