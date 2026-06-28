"""
Smart Matching Engine
Scores compatibility between a producer listing and merchant profiles
using a trained SVM model to rank the best merchant matches.
"""
import joblib
import pandas as pd
import os

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "matching_model.joblib")
_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(_MODEL_PATH)
    return _bundle


def _build_features(listing: dict, merchant: dict) -> dict:
    """Build the 18 features used during training from a listing and merchant profile."""
    qmap = {"A": 3, "B": 2, "C": 1, "A or B": 2.5, "Any": 1}
    total_cost = listing.get("price_birr", 0) * listing.get("quantity", 0)

    return {
        "same_region":          int(listing.get("region") == merchant.get("region")),
        "same_sector":          int(listing.get("sector") == merchant.get("preferred_sector")),
        "same_product":         int(listing.get("product_name") == merchant.get("preferred_product")),
        "price_fits_budget":    int(total_cost <= merchant.get("max_budget_birr", 0)),
        "quality_match":        int(
            qmap.get(listing.get("quality_grade", "C"), 1) >=
            qmap.get(merchant.get("preferred_quality", "Any"), 1)
        ),
        "both_verified":        int(listing.get("is_verified", 1) and merchant.get("is_verified", 1)),
        "delivery_match":       int(listing.get("delivery_available", 1) and merchant.get("needs_delivery", 0)),
        "payment_match":        int(merchant.get("payment_method") in ["Mobile Money", "Bank Transfer"]),
        "producer_rating":      listing.get("producer_rating", 4.0),
        "merchant_rating":      merchant.get("rating", 4.0),
        "producer_experience":  listing.get("producer_experience", 3),
        "merchant_experience":  merchant.get("years_in_business", 3),
        "producer_tx":          listing.get("producer_tx", 0),
        "merchant_tx":          merchant.get("total_transactions", 0),
        "producer_verified":    listing.get("is_verified", 1),
        "merchant_verified":    merchant.get("is_verified", 1),
        "producer_return_rate": listing.get("return_rate", 0.05),
        "merchant_return_rate": merchant.get("return_rate", 0.05),
    }


def rank_merchants(listing: dict, merchant_list: list) -> list:
    """
    Scores all merchants for compatibility with a listing and returns
    them sorted by match probability (highest first).
    """
    bundle = _load()
    model        = bundle["model"]
    scaler       = bundle["scaler"]
    feature_cols = bundle["feature_cols"]

    results = []
    for merchant in merchant_list:
        feats = _build_features(listing, merchant)
        X = pd.DataFrame([[feats[c] for c in feature_cols]], columns=feature_cols)
        X_scaled = scaler.transform(X)

        pred  = int(model.predict(X_scaled)[0])
        proba = float(model.predict_proba(X_scaled)[0][1])

        results.append({**merchant, "is_match": pred, "match_probability": round(proba, 4)})

    results.sort(key=lambda r: r["match_probability"], reverse=True)
    return results
