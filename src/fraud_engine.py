"""
Fraud Detection Engine
Scores a transaction's fraud risk using a trained Gradient Boosting model.
Returns Low / Medium / High risk with plain-English reasons.
"""
import joblib
import pandas as pd
import os
from datetime import datetime

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "fraud_model.joblib")
_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(_MODEL_PATH)
    return _bundle


def check_fraud_risk(
    sector: str, product: str, region: str, payment_method: str,
    quantity: float, agreed_price_birr: float, market_price_birr: float,
    delivery_used: int = 1, dispute_raised: int = 0,
    producer_rating: float = 4.0, merchant_rating: float = 4.0,
    match_score: float = 0.7, days_to_complete: int = 3,
    repeat_transaction: int = 0, account_age_days: int = 365,
) -> dict:
    """
    Score one transaction for fraud risk.
    Returns: is_fraud (0/1), fraud_probability, risk_level, reasons list.
    """
    bundle       = _load()
    model        = bundle["model"]
    scaler       = bundle["scaler"]
    feature_cols = bundle["feature_cols"]
    needs_scaling = bundle["needs_scaling"]

    # Encode categories using sorted alphabetical order (matches training LabelEncoder)
    sectors  = sorted(["Agriculture","Food Processing","Handicrafts","Livestock",
                        "Manufacturing","Services","Textiles"])
    regions  = sorted(["Addis Ababa","Amhara","Dire Dawa","Harari",
                        "Oromia","SNNPR","Sidama","Tigray"])
    payments = sorted(["Bank Transfer","Cash","Cheque","Credit","Mobile Money"])

    sector_enc  = sectors.index(sector)  if sector  in sectors  else 0
    region_enc  = regions.index(region)  if region  in regions  else 0
    payment_enc = payments.index(payment_method) if payment_method in payments else 0
    product_enc = abs(hash(product)) % 50

    price_ratio    = agreed_price_birr / market_price_birr if market_price_birr else 1.0
    is_new_account = int(account_age_days < 14)
    now            = datetime.now()

    # Engineered interaction features — same as training
    row = pd.DataFrame([{
        "sector_enc":           sector_enc,
        "product_enc":          product_enc,
        "region_enc":           region_enc,
        "payment_method_enc":   payment_enc,
        "quantity":             quantity,
        "agreed_price_birr":    agreed_price_birr,
        "market_price_birr":    market_price_birr,
        "price_ratio":          price_ratio,
        "delivery_used":        delivery_used,
        "dispute_raised":       dispute_raised,
        "month":                now.month,
        "year":                 now.year,
        "producer_rating_after": producer_rating,
        "merchant_rating_after": merchant_rating,
        "match_score":          match_score,
        "days_to_complete":     days_to_complete,
        "repeat_transaction":   repeat_transaction,
        "account_age_days":     account_age_days,
        "is_new_account":       is_new_account,
        "cheap_and_new":        int(is_new_account and price_ratio < 0.8),
        "fast_and_large":       int(days_to_complete <= 1 and quantity > 500),
        "cash_no_delivery":     int(payment_method == "Cash" and delivery_used == 0),
        "low_rating_avg":       round((producer_rating + merchant_rating) / 2, 2),
        "price_deviation":      round(abs(1 - price_ratio), 4),
        "risk_signal_count":    (
            int(price_ratio < 0.75) + int(is_new_account) +
            int(days_to_complete <= 1) + int(dispute_raised) +
            int(payment_method == "Cash" and delivery_used == 0) +
            int(match_score < 0.4)
        ),
    }])[feature_cols]

    row_input = scaler.transform(row) if needs_scaling else row
    pred  = int(model.predict(row_input)[0])
    proba = float(model.predict_proba(row_input)[0][1])

    risk_level = "Low" if proba < 0.35 else ("Medium" if proba < 0.65 else "High")

    reasons = []
    if price_ratio < 0.75:
        reasons.append("Price is significantly below market value")
    if is_new_account:
        reasons.append("Account is less than 14 days old")
    if days_to_complete <= 1 and quantity > 500:
        reasons.append("Large quantity completed unusually fast")
    if dispute_raised and (producer_rating < 2.5 or merchant_rating < 2.5):
        reasons.append("Dispute raised with low post-transaction ratings")
    if payment_method == "Cash" and delivery_used == 0 and repeat_transaction == 0:
        reasons.append("Cash payment with no delivery and no transaction history")

    return {
        "is_fraud":          pred,
        "fraud_probability": round(proba, 4),
        "risk_level":        risk_level,
        "reasons":           reasons if reasons else ["No major risk signals detected"],
    }
