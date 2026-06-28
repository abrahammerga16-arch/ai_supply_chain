"""
Price Recommendation Engine
Predicts a fair market price for a product listing using a trained
Random Forest model based on sector, product, region, quality, and season.
"""
import joblib
import pandas as pd
import numpy as np
import os
import datetime

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "price_model.joblib")
_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(_MODEL_PATH)
    return _bundle


def _encode(encoder, value):
    """Encode a category value; fall back to first class if unseen."""
    try:
        return encoder.transform([value])[0]
    except ValueError:
        return encoder.transform([encoder.classes_[0]])[0]


def recommend_price(sector: str, product: str, region: str, quality_grade: str) -> dict:
    """
    Returns a recommended price and range for a product listing.
    Only requires sector, product, region, and quality grade.
    All market condition values use Ethiopian average defaults.
    """
    bundle = _load()
    model    = bundle["model"]
    encoders = bundle["encoders"]
    feature_cols  = bundle["feature_cols"]
    product_stats = bundle["product_stats"]

    month   = datetime.datetime.now().month
    quarter = (month - 1) // 3 + 1
    season  = {1: "Winter", 2: "Spring", 3: "Summer", 4: "Autumn"}[quarter]

    # Look up this product's historical price average as anchor
    p_stats = product_stats[product_stats["product"] == product]
    if len(p_stats) > 0:
        prod_avg = float(p_stats["product_avg_price"].values[0])
        prod_std = float(p_stats["product_price_std"].values[0])
    else:
        prod_avg = float(product_stats["product_avg_price"].mean())
        prod_std = float(product_stats["product_price_std"].mean())

    row = pd.DataFrame([{
        "sector_enc":        _encode(encoders["sector"], sector),
        "product_enc":       _encode(encoders["product"], product),
        "region_enc":        _encode(encoders["region"], region),
        "quality_grade_enc": _encode(encoders["quality_grade"], quality_grade),
        "season_enc":        _encode(encoders["season"], season),
        "month":             month,
        "quarter":           quarter,
        "is_harvest_season": int(month in [10, 11, 12, 1]),
        "supply_volume":     5000.0,
        "demand_volume":     5000.0,
        "supply_demand_ratio": 1.0,
        "num_sellers":       50,
        "price_volatility":  0.2,
        "rainfall_index":    0.5,
        "inflation_rate":    18.0,
        "exchange_rate_usd": 90.0,
        "product_avg_price": prod_avg,
        "product_price_std": prod_std,
    }])[feature_cols]

    price = float(model.predict(row)[0])
    margin = prod_std if prod_std > 0 else price * 0.1

    return {
        "recommended_price": round(price, 2),
        "min_price": round(max(0, price - margin), 2),
        "max_price": round(price + margin, 2),
    }
