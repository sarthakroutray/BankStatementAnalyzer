import logging
import warnings
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.api import Holt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller

from app.schemas import ForecastDataPoint, HistoricalDataPoint

logger = logging.getLogger("sarima_engine")
warnings.filterwarnings("ignore")

__all__ = [
    "winsorize_series",
    "prepare_time_series",
    "determine_stationarity_orders",
    "_run_cold_start_fallback",
    "fit_and_forecast_spending",
    "train_sarima_and_forecast",
]


def winsorize_series(series: pd.Series, quantile: float = 0.99) -> pd.Series:
    """Winsorize extreme one-off outlier spikes to prevent skewing rolling variance."""
    if len(series) < 5 or series.nunique() <= 1:
        return series

    non_zeros = series[series > 0]
    if len(non_zeros) == 0:
        return series

    try:
        q_high = float(series.quantile(quantile, interpolation="nearest"))
    except TypeError:
        q_high = float(series.quantile(quantile))

    # IQR fences on full series
    q25, q75 = float(series.quantile(0.25)), float(series.quantile(0.75))
    iqr = q75 - q25
    iqr_high = q75 + 3.0 * iqr if iqr > 0 else float("inf")

    # Non-zero IQR fences (to bypass zero-inflation distortion)
    if len(non_zeros) >= 4:
        nz_q25 = float(non_zeros.quantile(0.25))
        nz_q75 = float(non_zeros.quantile(0.75))
        nz_iqr = nz_q75 - nz_q25
        nz_iqr_high = nz_q75 + 3.0 * nz_iqr if nz_iqr > 0 else float("inf")
    else:
        nz_iqr_high = float("inf")

    # Detect extreme isolated spike relative to other positive spending (e.g. tuition/deposit)
    spike_fence = float("inf")
    if len(non_zeros) >= 2:
        sorted_nz = sorted(non_zeros.tolist())
        top_val = sorted_nz[-1]
        second_top = sorted_nz[-2]
        # Extreme one-off spike: > 4x second highest and diff > $100
        if top_val > 4.0 * second_top and (top_val - second_top) > 100.0:
            spike_fence = max(second_top * 1.5, second_top + 50.0)

    fences = [f for f in [q_high, iqr_high, nz_iqr_high, spike_fence] if f < float("inf")]
    upper_threshold = min(fences) if fences else q_high

    min_pos = float(non_zeros.min())
    upper_threshold = max(upper_threshold, min_pos, float(series.median()))

    res = series.clip(upper=upper_threshold)
    res.attrs = dict(series.attrs)
    return res


def prepare_time_series(
    transactions: List[Any],
    granularity: str = "DAILY",
    exclude_transfers: bool = True
) -> pd.Series:
    """
    Filter DEBIT transactions, compute date_span_days = (max_date - min_date).days + 1,
    reindex with continuous daily frequency ('D') filling non-transaction days with 0.0,
    and apply outlier winsorization.
    """
    records = []
    for t in transactions:
        t_type = getattr(t, "txn_type", None) or (t.get("txn_type") if isinstance(t, dict) else None)
        category = getattr(t, "category", "") or (t.get("category", "") if isinstance(t, dict) else "")
        if not t_type or str(t_type).strip().upper() != "DEBIT":
            continue
        if exclude_transfers and str(category).strip().lower() == "transfers":
            continue

        txn_d = getattr(t, "txn_date", None) or (t.get("txn_date") if isinstance(t, dict) else None)
        amt = getattr(t, "amount", None) or (t.get("amount") if isinstance(t, dict) else 0)

        if txn_d and amt:
            try:
                parsed_d = pd.to_datetime(txn_d).normalize()
                if pd.isna(parsed_d):
                    continue
                records.append({"date": parsed_d, "amount": abs(float(amt))})
            except Exception:
                continue

    if not records:
        empty_s = pd.Series(dtype=float, name="spend")
        empty_s.attrs["date_span_days"] = 0
        return empty_s

    df = pd.DataFrame(records).sort_values("date")

    min_date = df["date"].min()
    max_date = df["date"].max()
    date_span_days = int((max_date - min_date).days) + 1
    logger.info(
        "Extracted %d DEBIT transactions spanning %d days (%s to %s).",
        len(records),
        date_span_days,
        min_date.strftime("%Y-%m-%d"),
        max_date.strftime("%Y-%m-%d"),
    )

    if granularity.upper() == "DAILY":
        # Reindex with continuous daily frequency (freq='D'), filling non-transaction days with 0.0
        full_idx = pd.date_range(start=min_date, end=max_date, freq="D")
        grouped = df.groupby("date")["amount"].sum()
        resampled = grouped.reindex(full_idx, fill_value=0.0)
    else:
        df_indexed = df.set_index("date")
        resampled = df_indexed["amount"].resample("W-MON").sum().fillna(0.0)

    resampled.name = "spend"
    resampled.attrs["date_span_days"] = date_span_days
    return winsorize_series(resampled)


def determine_stationarity_orders(series: pd.Series, s: int) -> Tuple[int, int]:
    """
    Run Augmented Dickey-Fuller test to determine differencing order d and seasonal D.
    """
    if len(series) < 10 or series.nunique() <= 1:
        return (1, 0)

    try:
        try:
            adf_res = adfuller(series.dropna(), autolag="AIC", result_object=False)
        except TypeError:
            adf_res = adfuller(series.dropna(), autolag="AIC")
        p_val = adf_res[1]
        d = 0 if p_val <= 0.05 else 1
    except Exception:
        d = 1

    D = 0
    if len(series) >= 2 * s and series.nunique() > 1:
        try:
            seasonal_diff = series.diff(s).dropna()
            if len(seasonal_diff) >= 8 and seasonal_diff.nunique() > 1:
                try:
                    adf_seasonal = adfuller(seasonal_diff, autolag="AIC", result_object=False)
                except TypeError:
                    adf_seasonal = adfuller(seasonal_diff, autolag="AIC")
                if adf_seasonal[1] > 0.05:
                    D = 1
        except Exception:
            D = 0

    return d, D


def _run_cold_start_fallback(
    series: pd.Series,
    future_dates: pd.DatetimeIndex,
    historical_series: List[HistoricalDataPoint],
    horizon: int,
    alpha: float,
    reason: str,
) -> Dict[str, Any]:
    """Execute cold-start fallback ARIMA(1,1,1), Holt-Winters, or Baseline."""
    # Try ARIMA(1, 1, 1)
    try:
        model = ARIMA(series, order=(1, 1, 1))
        fit_res = model.fit()
        forecast_res = fit_res.get_forecast(steps=horizon)
        mean_pred = forecast_res.predicted_mean
        conf_int = forecast_res.conf_int(alpha=alpha)

        residuals = fit_res.resid.dropna()
        rmse_val = float(np.sqrt(np.mean(residuals ** 2))) if len(residuals) > 0 else None
        mae_val = float(np.mean(np.abs(residuals))) if len(residuals) > 0 else None

        forecast_payload = []
        for dt, p, (_, ci) in zip(future_dates, mean_pred, conf_int.iterrows()):
            pred = max(0.0, float(p)) if not np.isnan(p) else 0.0
            ci_0 = float(ci.iloc[0]) if not np.isnan(ci.iloc[0]) else pred * 0.8
            ci_1 = float(ci.iloc[1]) if not np.isnan(ci.iloc[1]) else pred * 1.2
            lower = max(0.0, ci_0)
            upper = max(pred, ci_1)
            forecast_payload.append(
                ForecastDataPoint(
                    date=dt.strftime("%Y-%m-%d"),
                    predicted=round(pred, 2),
                    lower_ci=round(lower, 2),
                    upper_ci=round(upper, 2),
                )
            )

        return {
            "order": "(1,1,1)x(0,0,0,0)",
            "aic": round(float(fit_res.aic), 2) if hasattr(fit_res, "aic") else None,
            "rmse": round(rmse_val, 2) if rmse_val is not None else None,
            "mae": round(mae_val, 2) if mae_val is not None else None,
            "historical_series": historical_series,
            "forecast_payload": forecast_payload,
            "fallback_used": True,
            "model_notes": f"{reason} Trained non-seasonal ARIMA(1,1,1) cold-start fallback.",
        }
    except Exception as ex:
        logger.warning(f"ARIMA fallback failed: {ex}. Falling back to Exponential Smoothing.")
        try:
            hw = ExponentialSmoothing(series, trend="add", seasonal=None).fit()
            hw_preds = hw.forecast(horizon)
            std_resid = float(np.std(series.values - hw.fittedvalues.values))
            if np.isnan(std_resid):
                std_resid = 0.0
            forecast_payload = [
                ForecastDataPoint(
                    date=dt.strftime("%Y-%m-%d"),
                    predicted=round(max(0.0, float(p)) if not np.isnan(p) else 0.0, 2),
                    lower_ci=round(max(0.0, float(p) - 1.645 * std_resid) if not np.isnan(p) else 0.0, 2),
                    upper_ci=round(max(0.0, float(p) + 1.645 * std_resid) if not np.isnan(p) else 0.0, 2),
                )
                for dt, p in zip(future_dates, hw_preds)
            ]
            return {
                "order": "HoltWinters(Add)",
                "aic": None,
                "rmse": round(std_resid, 2),
                "mae": round(std_resid * 0.8, 2),
                "historical_series": historical_series,
                "forecast_payload": forecast_payload,
                "fallback_used": True,
                "model_notes": f"{reason} Fitted Holt-Winters Exponential Smoothing cold-start fallback.",
            }
        except Exception as e_hw:
            logger.error(f"Holt-Winters failed: {e_hw}. Using rolling mean baseline.")
            mean_val = float(series.mean()) if len(series) > 0 else 0.0
            if np.isnan(mean_val) or mean_val < 0.0:
                mean_val = 0.0
            std_val = float(series.std()) if len(series) > 1 and not np.isnan(series.std()) else mean_val * 0.2
            if np.isnan(std_val):
                std_val = mean_val * 0.2
            forecast_payload = [
                ForecastDataPoint(
                    date=dt.strftime("%Y-%m-%d"),
                    predicted=round(max(0.0, mean_val), 2),
                    lower_ci=round(max(0.0, mean_val - 1.645 * std_val), 2),
                    upper_ci=round(max(0.0, mean_val + 1.645 * std_val), 2),
                )
                for dt in future_dates
            ]
            return {
                "order": "Baseline(Mean)",
                "aic": None,
                "rmse": round(std_val, 2),
                "mae": round(std_val * 0.8, 2),
                "historical_series": historical_series,
                "forecast_payload": forecast_payload,
                "fallback_used": True,
                "model_notes": f"{reason} Using rolling mean baseline.",
            }


def fit_and_forecast_spending(
    series: pd.Series,
    horizon_days: int = 30,
    alpha: float = 0.10,
) -> Dict[str, Any]:
    """
    Dynamic Model Selection Ladder for spending forecasts:
    - Tier 1 (N >= 28): Try Daily SARIMA with weekly seasonality (s=7).
      Constrain grid search to lightweight orders: (1,1,1) if N>=60 else (1,0,1).
      Fallback to non-seasonal ARIMA(1,1,1) if SARIMA fails to converge,
      with subsequent cascade to Holt and ROLLING_BASELINE if needed.
    - Tier 2 (14 <= N < 28): Holt Exponential Smoothing with synthetic confidence
      intervals based on residual standard deviation.
    - Tier 3 (N < 14): Flat projection based on rolling 7-day average burn rate.
    """
    horizon_days = max(1, int(horizon_days))
    if series is None or (isinstance(series, (pd.Series, list, np.ndarray)) and len(series) == 0):
        clean_series = pd.Series(dtype=float)
    else:
        if not isinstance(series, pd.Series):
            clean_series = pd.Series(series, dtype=float)
        else:
            clean_series = series.copy().astype(float)
        clean_series = clean_series.fillna(0.0)

    # If datetime index has duplicates, aggregate daily
    if isinstance(clean_series.index, pd.DatetimeIndex) and not clean_series.index.is_unique:
        clean_series = clean_series.groupby(clean_series.index).sum()

    N = len(clean_series)

    # Determine timeline and future dates
    if N > 0 and isinstance(clean_series.index, pd.DatetimeIndex):
        last_date = pd.to_datetime(clean_series.index[-1]).normalize()
    else:
        last_date = pd.Timestamp.now().normalize()
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon_days, freq="D")

    # Format historical series
    historical_series: List[HistoricalDataPoint] = []
    if N > 0:
        if isinstance(clean_series.index, pd.DatetimeIndex):
            historical_series = [
                HistoricalDataPoint(date=dt.strftime("%Y-%m-%d"), actual=round(float(val), 2))
                for dt, val in clean_series.items()
            ]
        else:
            historical_series = [
                HistoricalDataPoint(
                    date=(last_date - pd.Timedelta(days=N - 1 - idx)).strftime("%Y-%m-%d"),
                    actual=round(float(val), 2),
                )
                for idx, val in enumerate(clean_series)
            ]

    model_used = "ROLLING_BASELINE"
    order_str = "Baseline(RollingMean)"
    aic_val: Optional[float] = None
    rmse_val: Optional[float] = None
    mae_val: Optional[float] = None
    pred_mean: Optional[pd.Series] = None
    conf_int: Optional[pd.DataFrame] = None
    synthetic_spread: float = 0.0
    model_notes = ""

    if N >= 28:
        # Tier 1: Try Daily SARIMA with weekly seasonality (s=7)
        try:
            order = (1, 1, 1) if N >= 60 else (1, 0, 1)
            seasonal_order = (1, 1, 0, 7) if N >= 60 else (1, 0, 0, 7)
            from statsmodels.tsa.statespace.sarimax import SARIMAX

            model = SARIMAX(
                clean_series,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            res = model.fit(disp=False, maxiter=50)
            forecast_res = res.get_forecast(steps=horizon_days)
            model_used = "SARIMA"
            order_str = f"{order}x{seasonal_order}"
            pred_mean = forecast_res.predicted_mean
            try:
                conf_int = forecast_res.conf_int(alpha=alpha)
            except Exception:
                conf_int = None
            aic_val = round(float(res.aic), 2) if hasattr(res, "aic") and np.isfinite(res.aic) else None
            residuals = res.resid.dropna()
            rmse_val = round(float(np.sqrt(np.mean(residuals ** 2))), 2) if len(residuals) > 0 else None
            mae_val = round(float(np.mean(np.abs(residuals))), 2) if len(residuals) > 0 else None
            synthetic_spread = rmse_val if rmse_val is not None else 0.0
            model_notes = f"Tier 1: Daily SARIMA {order_str} (s=7) fitted successfully."
        except Exception as e:
            logger.warning("SARIMA Tier 1 fit failed (%s). Falling back to non-seasonal ARIMA(1,1,1).", e)
            try:
                model = ARIMA(clean_series, order=(1, 1, 1))
                res = model.fit()
                forecast_res = res.get_forecast(steps=horizon_days)
                model_used = "ARIMA_FALLBACK"
                order_str = "ARIMA(1,1,1)"
                pred_mean = forecast_res.predicted_mean
                try:
                    conf_int = forecast_res.conf_int(alpha=alpha)
                except Exception:
                    conf_int = None
                aic_val = round(float(res.aic), 2) if hasattr(res, "aic") and np.isfinite(res.aic) else None
                residuals = res.resid.dropna()
                rmse_val = round(float(np.sqrt(np.mean(residuals ** 2))), 2) if len(residuals) > 0 else None
                mae_val = round(float(np.mean(np.abs(residuals))), 2) if len(residuals) > 0 else None
                synthetic_spread = rmse_val if rmse_val is not None else 0.0
                model_notes = f"Tier 1 Fallback: Non-seasonal ARIMA(1,1,1) fitted after SARIMA failure ({e})."
            except Exception as e_arima:
                logger.warning("ARIMA Tier 1 fallback failed (%s). Cascading to Tier 2 Holt.", e_arima)
                try:
                    from statsmodels.tsa.api import Holt

                    fit_model = Holt(clean_series, initialization_method="estimated").fit()
                    pred_mean = fit_model.forecast(horizon_days)
                    model_used = "HOLT_EXPONENTIAL_SMOOTHING"
                    order_str = "Holt"
                    residuals = clean_series.values - fit_model.fittedvalues.values
                    std_resid = float(np.std(residuals)) if len(residuals) > 0 else 0.0
                    if std_resid == 0.0 or not np.isfinite(std_resid):
                        std_resid = float(clean_series.std()) if len(clean_series) > 1 and np.isfinite(clean_series.std()) else float(clean_series.mean()) * 0.2
                    synthetic_spread = std_resid if np.isfinite(std_resid) else 0.0
                    rmse_val = round(synthetic_spread, 2)
                    mae_val = round(float(np.mean(np.abs(residuals))), 2) if len(residuals) > 0 else None
                    aic_val = round(float(fit_model.aic), 2) if hasattr(fit_model, "aic") and np.isfinite(fit_model.aic) else None
                    model_notes = f"Tier 1 Double Fallback: Holt Exponential Smoothing fitted after SARIMA and ARIMA failures."
                except Exception as e_holt_cascade:
                    logger.warning("Holt cascade failed (%s). Cascading to Tier 3 Baseline.", e_holt_cascade)
                    rolling_avg = float(clean_series.tail(7).mean()) if len(clean_series) > 0 else 0.0
                    if not np.isfinite(rolling_avg) or rolling_avg < 0.0:
                        rolling_avg = 0.0
                    model_used = "ROLLING_BASELINE"
                    order_str = "Baseline(RollingMean)"
                    pred_mean = pd.Series([round(rolling_avg, 2)] * horizon_days)
                    std_val = float(clean_series.tail(7).std()) if len(clean_series) > 1 and np.isfinite(clean_series.tail(7).std()) else rolling_avg * 0.2
                    synthetic_spread = std_val if np.isfinite(std_val) else rolling_avg * 0.2
                    rmse_val = round(synthetic_spread, 2)
                    mae_val = round(synthetic_spread * 0.8, 2)
                    model_notes = f"Tier 1 Triple Fallback: Rolling baseline used after SARIMA, ARIMA, and Holt failures."

    elif 14 <= N < 28:
        # Tier 2: Short history - Holt-Winters or Exponential Smoothing
        try:
            from statsmodels.tsa.api import Holt

            fit_model = Holt(clean_series, initialization_method="estimated").fit()
            pred_mean = fit_model.forecast(horizon_days)
            model_used = "HOLT_EXPONENTIAL_SMOOTHING"
            order_str = "Holt"
            residuals = clean_series.values - fit_model.fittedvalues.values
            std_resid = float(np.std(residuals)) if len(residuals) > 0 else 0.0
            if std_resid == 0.0 or not np.isfinite(std_resid):
                std_resid = float(clean_series.std()) if len(clean_series) > 1 and np.isfinite(clean_series.std()) else float(clean_series.mean()) * 0.2
            synthetic_spread = std_resid if np.isfinite(std_resid) else 0.0
            rmse_val = round(synthetic_spread, 2)
            mae_val = round(float(np.mean(np.abs(residuals))), 2) if len(residuals) > 0 else None
            aic_val = round(float(fit_model.aic), 2) if hasattr(fit_model, "aic") and np.isfinite(fit_model.aic) else None
            model_notes = f"Tier 2: Holt Exponential Smoothing fitted for short history ({N} points)."
        except Exception as e_holt:
            logger.warning("Holt Tier 2 fit failed (%s). Cascading to Tier 3 Baseline.", e_holt)
            rolling_avg = float(clean_series.tail(7).mean()) if len(clean_series) > 0 else 0.0
            if not np.isfinite(rolling_avg) or rolling_avg < 0.0:
                rolling_avg = 0.0
            model_used = "ROLLING_BASELINE"
            order_str = "Baseline(RollingMean)"
            pred_mean = pd.Series([round(rolling_avg, 2)] * horizon_days)
            std_val = float(clean_series.tail(7).std()) if len(clean_series) > 1 and np.isfinite(clean_series.tail(7).std()) else rolling_avg * 0.2
            synthetic_spread = std_val if np.isfinite(std_val) else rolling_avg * 0.2
            rmse_val = round(synthetic_spread, 2)
            mae_val = round(synthetic_spread * 0.8, 2)
            model_notes = f"Tier 2 Fallback: Rolling baseline used after Holt failure ({e_holt})."

    else:
        # Tier 3: Under 14 days - Rolling Mean / Moving Average baseline
        rolling_avg = float(clean_series.tail(7).mean()) if len(clean_series) > 0 else 0.0
        if not np.isfinite(rolling_avg) or rolling_avg < 0.0:
            rolling_avg = 0.0
        model_used = "ROLLING_BASELINE"
        order_str = "Baseline(RollingMean)"
        pred_mean = pd.Series([round(rolling_avg, 2)] * horizon_days)
        std_val = float(clean_series.tail(7).std()) if len(clean_series) > 1 and np.isfinite(clean_series.tail(7).std()) else rolling_avg * 0.2
        synthetic_spread = std_val if np.isfinite(std_val) else rolling_avg * 0.2
        rmse_val = round(synthetic_spread, 2)
        mae_val = round(synthetic_spread * 0.8, 2)
        model_notes = f"Tier 3: Rolling mean burn rate baseline projected for sub-14-day history ({N} points)."

    from scipy.stats import norm
    z_mult = float(norm.ppf(1.0 - alpha / 2.0)) if 0.0 < alpha < 1.0 else 1.645

    forecast_payload: List[ForecastDataPoint] = []
    for i, dt in enumerate(future_dates):
        if pred_mean is not None and (hasattr(pred_mean, "iloc") or hasattr(pred_mean, "__getitem__")):
            try:
                p_raw = float(pred_mean.iloc[i]) if hasattr(pred_mean, "iloc") else float(pred_mean[i])
            except Exception:
                p_raw = 0.0
        else:
            p_raw = 0.0

        if not np.isfinite(p_raw) or p_raw < 0.0:
            pred_val = 0.0
        else:
            pred_val = float(p_raw)

        if conf_int is not None and i < len(conf_int):
            try:
                ci_row = conf_int.iloc[i]
                low_val = float(ci_row.iloc[0])
                up_val = float(ci_row.iloc[1])
                lower_ci = min(pred_val, max(0.0, low_val)) if np.isfinite(low_val) else max(0.0, pred_val - z_mult * synthetic_spread)
                upper_ci = max(pred_val, up_val) if np.isfinite(up_val) else max(pred_val, pred_val + z_mult * synthetic_spread)
            except Exception:
                lower_ci = max(0.0, pred_val - z_mult * synthetic_spread)
                upper_ci = max(pred_val, pred_val + z_mult * synthetic_spread)
        else:
            lower_ci = max(0.0, pred_val - z_mult * synthetic_spread)
            upper_ci = max(pred_val, pred_val + z_mult * synthetic_spread)

        forecast_payload.append(
            ForecastDataPoint(
                date=dt.strftime("%Y-%m-%d"),
                predicted=round(pred_val, 2),
                lower_ci=round(lower_ci, 2),
                upper_ci=round(upper_ci, 2),
            )
        )

    burn_rate = round(float(clean_series.tail(7).mean()), 2) if len(clean_series) > 0 else 0.0
    if not np.isfinite(burn_rate) or burn_rate < 0.0:
        burn_rate = 0.0

    return {
        "model_used": model_used,
        "order": order_str,
        "aic": aic_val,
        "rmse": rmse_val,
        "mae": mae_val,
        "historical_series": historical_series,
        "forecast_payload": forecast_payload,
        "predictions": [pt.predicted for pt in forecast_payload],
        "dates": [pt.date for pt in forecast_payload],
        "confidence_intervals": [
            {"lower": pt.lower_ci, "upper": pt.upper_ci} for pt in forecast_payload
        ],
        "fallback_used": model_used != "SARIMA",
        "model_notes": model_notes,
        "rolling_avg": burn_rate,
    }


def train_sarima_and_forecast(
    series: pd.Series,
    granularity: str = "DAILY",
    horizon: int = 30,
    alpha: float = 0.10,
) -> Dict[str, Any]:
    """
    Run grid-search SARIMA forecasting on preprocessed time series.
    Returns: dictionary with historical series, forecasts, confidence intervals, metrics, and order.
    """
    s = 7 if granularity.upper() == "DAILY" else 4
    min_points_seasonal = 2 * s

    # Convert historical series to output format
    historical_series: List[HistoricalDataPoint] = [
        HistoricalDataPoint(date=dt.strftime("%Y-%m-%d"), actual=round(float(val), 2))
        for dt, val in series.items()
    ]

    last_date = series.index[-1] if len(series) > 0 else pd.Timestamp.now()
    freq_str = "D" if granularity.upper() == "DAILY" else "W-MON"
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon, freq=freq_str)

    # 1. Edge Case: Extremely short series (< 4 points)
    if len(series) < 4:
        return _run_cold_start_fallback(
            series=series,
            future_dates=future_dates,
            historical_series=historical_series,
            horizon=horizon,
            alpha=alpha,
            reason="Sparse historical dataset (<4 data points).",
        )

    # 2. Cold-Start Fallback: fewer than 2 * s points
    if len(series) < min_points_seasonal:
        logger.info(f"Series length ({len(series)}) < {min_points_seasonal}. Executing cold-start fallback.")
        return _run_cold_start_fallback(
            series=series,
            future_dates=future_dates,
            historical_series=historical_series,
            horizon=horizon,
            alpha=alpha,
            reason=f"Historical series spans fewer than {min_points_seasonal} points.",
        )

    # 3. Full SARIMA Grid Search Pipeline
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    d, D = determine_stationarity_orders(series, s)

    # Train-test split (hold out last 15% for backtesting out-of-sample RMSE/MAE)
    holdout_size = max(2, int(len(series) * 0.15))
    train_series = series.iloc[:-holdout_size]
    test_series = series.iloc[-holdout_size:]

    p_candidates = [0, 1, 2]
    q_candidates = [0, 1, 2]
    P_candidates = [0, 1]
    Q_candidates = [0, 1]

    best_aic = float("inf")
    best_order = (1, d, 1)
    best_seasonal_order = (1, D, 1, s)
    best_fit = None

    # Fast bounded AIC grid search
    for p in p_candidates:
        for q in q_candidates:
            for P in P_candidates:
                for Q in Q_candidates:
                    try:
                        candidate_model = SARIMAX(
                            train_series,
                            order=(p, d, q),
                            seasonal_order=(P, D, Q, s),
                            enforce_stationarity=False,
                            enforce_invertibility=False,
                        )
                        fit_res = candidate_model.fit(disp=False, maxiter=50)
                        if fit_res.aic < best_aic:
                            best_aic = fit_res.aic
                            best_order = (p, d, q)
                            best_seasonal_order = (P, D, Q, s)
                            best_fit = fit_res
                    except Exception:
                        continue

    # If no candidate model converged during grid search, safely fallback
    if best_fit is None:
        logger.warning("No candidate SARIMA model converged during grid search. Using cold-start fallback.")
        return _run_cold_start_fallback(
            series=series,
            future_dates=future_dates,
            historical_series=historical_series,
            horizon=horizon,
            alpha=alpha,
            reason="SARIMA grid search did not converge on candidate models.",
        )

    # Evaluate out-of-sample backtest RMSE & MAE on holdout set
    rmse = None
    mae = None
    if best_fit is not None and len(test_series) > 0:
        try:
            holdout_forecast = best_fit.get_forecast(steps=len(test_series)).predicted_mean
            holdout_forecast_clamped = np.maximum(0.0, holdout_forecast.values)
            rmse = float(np.sqrt(mean_squared_error(test_series.values, holdout_forecast_clamped)))
            mae = float(mean_absolute_error(test_series.values, holdout_forecast_clamped))
        except Exception as ex:
            logger.warning(f"Error computing out-of-sample metrics: {ex}")

    # Refit best specification on 100% of historical series
    try:
        final_model = SARIMAX(
            series,
            order=best_order,
            seasonal_order=best_seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        final_fit = final_model.fit(disp=False, maxiter=60)
        forecast_obj = final_fit.get_forecast(steps=horizon)
        preds = forecast_obj.predicted_mean
        conf = forecast_obj.conf_int(alpha=alpha)
        final_aic = float(final_fit.aic)
    except Exception as ex:
        logger.error(f"Refitting final SARIMA failed: {ex}. Using best candidate fit.")
        final_fit = best_fit
        forecast_obj = final_fit.get_forecast(steps=horizon)
        preds = forecast_obj.predicted_mean
        conf = forecast_obj.conf_int(alpha=alpha)
        final_aic = best_aic

    forecast_payload = []
    for dt, p, (_, ci) in zip(future_dates, preds, conf.iterrows()):
        pred_val = max(0.0, float(p))
        lower_val = max(0.0, float(ci.iloc[0]))
        upper_val = max(pred_val, float(ci.iloc[1]))
        forecast_payload.append(
            ForecastDataPoint(
                date=dt.strftime("%Y-%m-%d"),
                predicted=round(pred_val, 2),
                lower_ci=round(lower_val, 2),
                upper_ci=round(upper_val, 2),
            )
        )

    order_str = f"{best_order}x{best_seasonal_order}"

    return {
        "order": order_str,
        "aic": round(final_aic, 2) if not np.isinf(final_aic) else None,
        "rmse": round(rmse, 2) if rmse is not None else None,
        "mae": round(mae, 2) if mae is not None else None,
        "historical_series": historical_series,
        "forecast_payload": forecast_payload,
        "fallback_used": False,
        "model_notes": f"Fitted optimal SARIMA model {order_str} via grid search (s={s}). Out-of-sample 15% holdout backtested.",
    }
