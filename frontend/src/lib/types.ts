export interface Transaction {
  id: string;
  statement_id?: string;
  txn_date: string;
  description: string;
  amount: number | string;
  txn_type: "DEBIT" | "CREDIT";
  category: string;
  balance?: number | string | null;
  row_hash: string;
}

export interface Statement {
  id: string;
  filename: string;
  uploaded_at: string;
  status: "PROCESSING" | "COMPLETED" | "FAILED";
  total_debit: number | string;
  total_credit: number | string;
  row_count: number;
}

export interface UploadResponse {
  status: string;
  statement: Statement;
  message: string;
  newly_inserted: number;
  duplicates_skipped: number;
  parsed_rows?: Transaction[];
}

export interface HistoricalPoint {
  date: string;
  actual: number;
}

export interface ForecastPoint {
  date: string;
  predicted: number;
  lower_ci: number;
  upper_ci: number;
  actual?: number | null;
}

export interface CombinedChartPoint {
  date: string;
  actual?: number;
  predicted?: number;
  lower_ci?: number;
  upper_ci?: number;
  confidence_band?: [number, number];
}

export interface ForecastResponse {
  forecast_id?: string | number | null;
  created_at?: string;
  granularity: "DAILY" | "WEEKLY";
  horizon_steps: number;
  sarima_order?: string | null;
  aic?: number | null;
  rmse?: number | null;
  mae?: number | null;
  historical_series: HistoricalPoint[];
  forecast_payload: ForecastPoint[];
  fallback_used: boolean;
  model_notes?: string | null;
  status?: "EMPTY" | "PENDING" | "COMPLETED" | string;
  error?: string | null;
  warning?: string | null;
}

export interface TopCategory {
  category: string;
  total_amount: number;
  percentage: number;
}

export interface ModelAccuracy {
  rmse?: number | null;
  aic?: number | null;
  sarima_order?: string | null;
}

export interface AnalyticsSummary {
  total_spend_historical_30d: number;
  sarima_projected_spend_next_30d: number;
  mom_spend_delta_percent: number;
  daily_avg_burn_rate: number;
  model_accuracy: ModelAccuracy;
  top_categories: TopCategory[];
  recent_transactions_count: number;
  total_credit_30d: number;
  total_debit_30d: number;
}

export interface PaginatedTransactions {
  total: number;
  limit: number;
  offset: number;
  items: Transaction[];
}

export interface DeleteResponse {
  success: boolean;
  deleted_count: number;
  message: string;
}

