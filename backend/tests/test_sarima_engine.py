from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np

from app.schemas import TransactionCreate
from app.services.sarima_engine import (
    determine_stationarity_orders,
    fit_and_forecast_spending,
    prepare_time_series,
    train_sarima_and_forecast,
    winsorize_series,
)


def test_winsorize_series():
    s = pd.Series([10.0, 12.0, 11.0, 13.0, 12.0, 1000.0])
    w = winsorize_series(s)
    assert w.max() < 1000.0


def test_prepare_time_series():
    base_date = date(2024, 1, 1)
    txns = [
        TransactionCreate(
            txn_date=base_date + timedelta(days=0),
            description="Chipotle",
            amount=Decimal("15.00"),
            txn_type="DEBIT",
            category="Food & Dining",
            row_hash="h1"
        ),
        TransactionCreate(
            txn_date=base_date + timedelta(days=0),
            description="Starbucks",
            amount=Decimal("5.00"),
            txn_type="DEBIT",
            category="Food & Dining",
            row_hash="h2"
        ),
        TransactionCreate(
            txn_date=base_date + timedelta(days=2),
            description="Lyft",
            amount=Decimal("20.00"),
            txn_type="DEBIT",
            category="Travel",
            row_hash="h3"
        ),
        TransactionCreate(
            txn_date=base_date + timedelta(days=1),
            description="Transfer Out",
            amount=Decimal("500.00"),
            txn_type="DEBIT",
            category="Transfers",
            row_hash="h4"
        ),
        TransactionCreate(
            txn_date=base_date + timedelta(days=1),
            description="Salary",
            amount=Decimal("3000.00"),
            txn_type="CREDIT",
            category="Transfers",
            row_hash="h5"
        ),
    ]

    series_daily = prepare_time_series(txns, granularity="DAILY", exclude_transfers=True)
    assert len(series_daily) == 3
    # Day 0: 15 + 5 = 20
    assert series_daily.iloc[0] == 20.0
    # Day 1: Transfers excluded, so 0.0 filled
    assert series_daily.iloc[1] == 0.0
    # Day 2: 20
    assert series_daily.iloc[2] == 20.0


def test_cold_start_fallback():
    # Only 7 daily points (< 2 * 7 = 14)
    dates = pd.date_range("2024-01-01", periods=7, freq="D")
    s = pd.Series([25.0, 30.0, 15.0, 40.0, 50.0, 35.0, 20.0], index=dates)

    res = train_sarima_and_forecast(s, granularity="DAILY", horizon=14)
    assert res["fallback_used"] is True
    assert len(res["forecast_payload"]) == 14
    for pt in res["forecast_payload"]:
        assert pt.predicted >= 0.0
        assert pt.lower_ci >= 0.0
        assert pt.upper_ci >= pt.predicted


def test_full_sarima_grid_search():
    # Generate 60 days of daily data with a weekly cyclic pattern
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    base_pattern = [30.0, 25.0, 35.0, 28.0, 80.0, 95.0, 45.0]  # higher weekend spending
    vals = [base_pattern[i % 7] + float(np.random.normal(0, 5)) for i in range(60)]
    s = pd.Series([max(5.0, v) for v in vals], index=dates)

    res = train_sarima_and_forecast(s, granularity="DAILY", horizon=30)
    assert res["fallback_used"] is False
    assert "x" in res["order"]
    assert len(res["forecast_payload"]) == 30
    assert res["aic"] is not None
    assert res["rmse"] is not None
    for pt in res["forecast_payload"]:
        assert pt.predicted >= 0.0
        assert pt.lower_ci >= 0.0
        assert pt.upper_ci >= pt.predicted


def test_prepare_time_series_weekly():
    # Transactions spread across various days of the week (Tue, Wed, Thu)
    txns = [
        {"txn_date": "2024-01-02", "amount": 100.0, "txn_type": "DEBIT", "category": "Food & Dining"},
        {"txn_date": "2024-01-03", "amount": 150.0, "txn_type": "DEBIT", "category": "Food & Dining"},
        {"txn_date": "2024-01-10", "amount": 200.0, "txn_type": "DEBIT", "category": "Utilities"},
        {"txn_date": "2024-01-17", "amount": 300.0, "txn_type": "DEBIT", "category": "Shopping"},
    ]
    series_weekly = prepare_time_series(txns, granularity="WEEKLY")
    assert not series_weekly.empty
    # Must have aggregated non-zero amounts into weekly bins
    assert series_weekly.sum() == 750.0
    assert series_weekly.iloc[0] == 250.0  # 100 + 150


def test_prepare_time_series_span_and_zero_fill():
    txns = [
        {"txn_date": "2024-01-01", "amount": 50.0, "txn_type": "DEBIT", "category": "Groceries"},
        {"txn_date": "2024-01-10", "amount": 100.0, "txn_type": "DEBIT", "category": "Shopping"},
    ]
    series = prepare_time_series(txns, granularity="DAILY")
    assert len(series) == 10
    assert series.attrs.get("date_span_days") == 10
    assert series.iloc[0] == 50.0
    assert series.iloc[9] == 100.0
    # Intermediate days must be 0.0
    for day_idx in range(1, 9):
        assert series.iloc[day_idx] == 0.0


def test_winsorize_extreme_spike_30d():
    # 29 regular spend days ($30 to $50) and 1 extreme tuition/deposit spike of $5000
    np.random.seed(42)
    regular = [float(np.random.uniform(30.0, 50.0)) for _ in range(29)]
    s = pd.Series(regular + [5000.0])
    w = winsorize_series(s)
    # The extreme outlier must be clipped drastically below $5000
    assert w.max() < 200.0
    assert w.max() >= s.median()


def test_fit_and_forecast_tier1_sarima_30d():
    # Single-month 30-day statement with weekly cyclic variation
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    base = [20.0, 25.0, 22.0, 30.0, 60.0, 75.0, 35.0]
    vals = [base[i % 7] for i in range(30)]
    s = pd.Series(vals, index=dates)

    res = fit_and_forecast_spending(s, horizon_days=30)
    assert res["model_used"] == "SARIMA"
    assert res["fallback_used"] is False
    assert "(1, 0, 1)x(1, 0, 0, 7)" in res["order"]
    assert len(res["forecast_payload"]) == 30
    assert len(res["predictions"]) == 30
    assert len(res["confidence_intervals"]) == 30
    for pt in res["forecast_payload"]:
        assert pt.predicted >= 0.0
        assert pt.lower_ci >= 0.0
        assert pt.upper_ci >= pt.predicted


def test_fit_and_forecast_tier1_sarima_60d():
    # 60-day statement uses higher order (1, 1, 1)x(1, 1, 0, 7)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    base = [30.0, 25.0, 35.0, 28.0, 80.0, 95.0, 45.0]
    vals = [base[i % 7] for i in range(60)]
    s = pd.Series(vals, index=dates)

    res = fit_and_forecast_spending(s, horizon_days=30)
    assert res["model_used"] == "SARIMA"
    assert "(1, 1, 1)x(1, 1, 0, 7)" in res["order"]
    assert len(res["forecast_payload"]) == 30


def test_fit_and_forecast_tier1_arima_fallback(monkeypatch):
    import statsmodels.tsa.statespace.sarimax as sm_sarimax
    orig_fit = sm_sarimax.SARIMAX.fit

    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    s = pd.Series([20.0 + (i % 7) * 5.0 for i in range(30)], index=dates)

    def broken_sarimax_fit(self, *args, **kwargs):
        # SARIMAX model has seasonal_order != (0, 0, 0, 0); ARIMA model has (0, 0, 0, 0)
        if getattr(self, "seasonal_order", (0, 0, 0, 0)) != (0, 0, 0, 0):
            raise RuntimeError("Simulated SARIMAX inversion failure")
        return orig_fit(self, *args, **kwargs)

    monkeypatch.setattr(sm_sarimax.SARIMAX, "fit", broken_sarimax_fit)

    res = fit_and_forecast_spending(s, horizon_days=30)
    assert res["model_used"] == "ARIMA_FALLBACK"
    assert res["fallback_used"] is True
    assert "ARIMA(1,1,1)" in res["order"]
    assert len(res["forecast_payload"]) == 30
    for pt in res["forecast_payload"]:
        assert pt.predicted >= 0.0
        assert pt.lower_ci >= 0.0
        assert pt.upper_ci >= pt.predicted


def test_fit_and_forecast_tier1_double_failure_cascades_to_holt(monkeypatch):
    import statsmodels.tsa.statespace.sarimax as sm_sarimax

    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    s = pd.Series([20.0 + (i % 7) * 5.0 for i in range(30)], index=dates)

    def broken_all_fits(*args, **kwargs):
        raise RuntimeError("Both SARIMAX and ARIMA failed")

    monkeypatch.setattr(sm_sarimax.SARIMAX, "fit", broken_all_fits)

    res = fit_and_forecast_spending(s, horizon_days=30)
    assert res["model_used"] == "HOLT_EXPONENTIAL_SMOOTHING"
    assert res["fallback_used"] is True
    assert "Holt" in res["order"]
    assert len(res["forecast_payload"]) == 30


def test_fit_and_forecast_tier2_holt_20d():
    # 20-day statement (14 <= N < 28)
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    s = pd.Series([15.0 + i * 2.0 for i in range(20)], index=dates)

    res = fit_and_forecast_spending(s, horizon_days=14)
    assert res["model_used"] == "HOLT_EXPONENTIAL_SMOOTHING"
    assert res["fallback_used"] is True
    assert "Holt" in res["order"]
    assert len(res["forecast_payload"]) == 14
    assert res["rmse"] is not None
    for pt in res["forecast_payload"]:
        assert pt.predicted >= 0.0
        assert pt.lower_ci >= 0.0
        assert pt.upper_ci >= pt.predicted


def test_fit_and_forecast_tier2_holt_failure_cascades_to_baseline(monkeypatch):
    import statsmodels.tsa.api as sm_tsa_api

    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    s = pd.Series([20.0] * 20, index=dates)

    def broken_holt_fit(*args, **kwargs):
        raise RuntimeError("Simulated Holt convergence failure")

    monkeypatch.setattr(sm_tsa_api.Holt, "fit", broken_holt_fit)

    res = fit_and_forecast_spending(s, horizon_days=14)
    assert res["model_used"] == "ROLLING_BASELINE"
    assert res["fallback_used"] is True
    assert len(res["forecast_payload"]) == 14
    for pt in res["forecast_payload"]:
        assert pt.predicted == 20.0


def test_fit_and_forecast_tier3_rolling_baseline_7d():
    # 7-day sub-14-day statement
    dates = pd.date_range("2024-01-01", periods=7, freq="D")
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0], index=dates)

    res = fit_and_forecast_spending(s, horizon_days=30)
    assert res["model_used"] == "ROLLING_BASELINE"
    assert res["fallback_used"] is True
    assert "Baseline" in res["order"]
    assert len(res["forecast_payload"]) == 30
    # Mean of 10..70 is 40.0
    for pt in res["forecast_payload"]:
        assert pt.predicted == 40.0
        assert pt.lower_ci >= 0.0
        assert pt.upper_ci >= pt.predicted
    assert res["rolling_avg"] == 40.0


def test_fit_and_forecast_empty_and_sub_4d():
    # Empty series
    res_empty = fit_and_forecast_spending(pd.Series(dtype=float), horizon_days=30)
    assert res_empty["model_used"] == "ROLLING_BASELINE"
    assert len(res_empty["forecast_payload"]) == 30
    for pt in res_empty["forecast_payload"]:
        assert pt.predicted == 0.0

    # 1-day series
    s_1 = pd.Series([50.0], index=pd.date_range("2024-01-01", periods=1, freq="D"))
    res_1 = fit_and_forecast_spending(s_1, horizon_days=7)
    assert res_1["model_used"] == "ROLLING_BASELINE"
    assert len(res_1["forecast_payload"]) == 7
    for pt in res_1["forecast_payload"]:
        assert pt.predicted == 50.0

    # 3-day series
    s_3 = pd.Series([10.0, 20.0, 30.0], index=pd.date_range("2024-01-01", periods=3, freq="D"))
    res_3 = fit_and_forecast_spending(s_3, horizon_days=14)
    assert res_3["model_used"] == "ROLLING_BASELINE"
    assert len(res_3["forecast_payload"]) == 14
    for pt in res_3["forecast_payload"]:
        assert pt.predicted == 20.0


def test_fit_and_forecast_constant_and_zeros_30d():
    # 30-day all zeros (e.g. inactive account)
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    s_zeros = pd.Series([0.0] * 30, index=dates)
    res_zeros = fit_and_forecast_spending(s_zeros, horizon_days=30)
    assert len(res_zeros["forecast_payload"]) == 30
    for pt in res_zeros["forecast_payload"]:
        assert pt.predicted == 0.0
        assert pt.lower_ci == 0.0
        assert pt.upper_ci == 0.0

    # 30-day constant spending (e.g. exact recurring daily charge)
    s_const = pd.Series([25.0] * 30, index=dates)
    res_const = fit_and_forecast_spending(s_const, horizon_days=30)
    assert len(res_const["forecast_payload"]) == 30
    for pt in res_const["forecast_payload"]:
        assert pt.predicted >= 0.0


def test_winsorize_zero_inflated_spike_30d():
    # 25 days with zero spend, 4 days with $30 spend, and 1 day with $5000 tuition spike
    s = pd.Series([0.0] * 25 + [30.0] * 4 + [5000.0])
    w = winsorize_series(s)
    # The extreme $5000 spike must be clipped drastically below $5000 to near normal positive spend
    assert w.max() < 100.0
    assert w.max() >= 30.0
    assert w.min() == 0.0


def test_winsorize_single_debit_not_zeroed():
    # 29 days with 0, 1 day with $5000 deposit/tuition
    s = pd.Series([0.0] * 29 + [5000.0])
    w = winsorize_series(s)
    # The only transaction must not be wiped out to 0
    assert w.max() == 5000.0


def test_prepare_time_series_mixed_case_and_negative():
    txns = [
        {"txn_date": "2024-01-01", "amount": -45.0, "txn_type": "debit", "category": "Food"},
        {"txn_date": "2024-01-02", "amount": 25.0, "txn_type": "DEBIT", "category": "Food"},
        {"txn_date": "2024-01-03", "amount": 100.0, "txn_type": "CREDIT", "category": "Income"},
        {"txn_date": "invalid-date", "amount": 10.0, "txn_type": "DEBIT", "category": "Other"},
    ]
    s = prepare_time_series(txns, granularity="DAILY")
    assert len(s) == 2
    assert s.iloc[0] == 45.0
    assert s.iloc[1] == 25.0


def test_fit_and_forecast_duplicate_dates_index():
    # Duplicate timestamps in DatetimeIndex
    dates = pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02"] + [f"2024-01-{i:02d}" for i in range(3, 31)])
    s = pd.Series([20.0] * len(dates), index=dates)
    res = fit_and_forecast_spending(s, horizon_days=14)
    assert res["model_used"] in ("SARIMA", "ARIMA_FALLBACK")
    assert len(res["forecast_payload"]) == 14
    for pt in res["forecast_payload"]:
        assert pt.predicted >= 0.0
        assert 0.0 <= pt.lower_ci <= pt.predicted <= pt.upper_ci


def test_fit_and_forecast_alpha_ci_scaling():
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    s = pd.Series([10.0 + (i % 5) * 5.0 for i in range(20)], index=dates)
    res_90 = fit_and_forecast_spending(s, horizon_days=10, alpha=0.10)
    res_99 = fit_and_forecast_spending(s, horizon_days=10, alpha=0.01)
    # A 99% CI (alpha=0.01) must have wider bounds than 90% CI (alpha=0.10)
    width_90 = res_90["forecast_payload"][0].upper_ci - res_90["forecast_payload"][0].lower_ci
    width_99 = res_99["forecast_payload"][0].upper_ci - res_99["forecast_payload"][0].lower_ci
    assert width_99 >= width_90



