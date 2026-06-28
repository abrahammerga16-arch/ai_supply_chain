"""
Demand Forecasting Engine
Uses a trained LSTM model to forecast weekly demand for a product-region
pair for the next 1–4 weeks, based on 12 weeks of historical data.
"""
import os
import numpy as np
import pandas as pd
import joblib

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

_META_PATH  = os.path.join(os.path.dirname(__file__), "..", "models", "demand_meta.joblib")
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "demand_model.keras")
_DATA_PATH  = os.path.join(os.path.dirname(__file__), "..", "data",   "demand_dataset.csv")

_meta = _model = _df = None


def _load():
    global _meta, _model, _df
    if _meta is None:
        import tensorflow as tf
        _meta  = joblib.load(_META_PATH)
        _model = tf.keras.models.load_model(_MODEL_PATH)
        _df    = pd.read_csv(_DATA_PATH)
        _df["sector_enc"]  = _meta["le_sector"].transform(_df["sector"])
        _df["product_enc"] = _meta["le_product"].transform(_df["product"])
        _df["region_enc"]  = _meta["le_region"].transform(_df["region"])
    return _meta, _model, _df


def forecast_demand(product: str, region: str, weeks_ahead: int = 4) -> dict:
    """
    Forecast demand for `product` in `region` for the next `weeks_ahead` weeks.

    Returns historical (last 8 weeks), forecast (next 1-4 weeks),
    trend direction, and model accuracy metrics.
    """
    meta, model, df = _load()

    feature_cols = meta["feature_cols"]
    scaler       = meta["scaler"]
    target_idx   = meta["target_idx"]
    seq_len      = meta["sequence_length"]

    # Get the most recent rows for this product-region
    series = df[(df["product"] == product) & (df["region"] == region)].sort_values("week")

    # Fall back to regional data if product not found
    if len(series) < seq_len:
        series = df[df["region"] == region].sort_values("week")

    if len(series) < seq_len:
        return {"error": f"Not enough history for {product} in {region}"}

    series = series.tail(seq_len + 8)

    # Build scaled input window (12 weeks × 18 features)
    window_df     = pd.DataFrame(series[feature_cols].values[-seq_len:], columns=feature_cols)
    window_scaled = scaler.transform(window_df)

    # Predict iteratively: feed each prediction back as the next input
    forecast_scaled = []
    current = window_scaled.copy()
    for _ in range(weeks_ahead):
        pred = float(model.predict(current[np.newaxis, :, :], verbose=0)[0][0])
        forecast_scaled.append(pred)
        next_row = current[-1].copy()
        next_row[target_idx] = pred
        current = np.vstack([current[1:], next_row])

    # Inverse transform back to real demand units
    def to_real(scaled_vals):
        dummy = pd.DataFrame(np.zeros((len(scaled_vals), len(feature_cols))), columns=feature_cols)
        dummy.iloc[:, target_idx] = scaled_vals
        return scaler.inverse_transform(dummy)[:, target_idx]

    forecast = [max(0, int(round(v))) for v in to_real(forecast_scaled)]
    historical = [max(0, int(round(v))) for v in series["demand_quantity"].values[-8:]]

    # Determine trend from forecast direction
    mid, last = forecast[len(forecast) // 2], forecast[-1]
    trend = "up" if last > mid * 1.05 else ("down" if last < mid * 0.95 else "stable")

    return {
        "product":    product,
        "region":     region,
        "weeks":      list(range(1, weeks_ahead + 1)),
        "forecast":   forecast,
        "historical": historical,
        "trend":      trend,
        "r2":         round(meta["r2"], 4),
        "rmse":       round(meta["rmse"], 1),
    }
