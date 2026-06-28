"""
Regenerates the fraud training dataset so is_fraud is driven by realistic,
rule-based fraud signals instead of being assigned independently at random.

Real-world fraud patterns encoded here (matching common Ethiopian informal
marketplace fraud types described in the project proposal):
  1. Price manipulation  -> agreed price far below market price
  2. Ghost transactions  -> marked "Completed" unrealistically fast
  3. New-account scams   -> brand new account + high-value first transaction
  4. Identity/dispute risk -> disputes combined with low ratings afterward
  5. Cash-only evasion   -> cash payment + no delivery + no repeat history

Each transaction gets a fraud PROBABILITY built from these rules, then a
binary label is sampled from that probability (so it's not perfectly
deterministic / trivially learnable, but genuinely predictable above chance).
"""
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from sklearn.preprocessing import LabelEncoder
from imblearn.over_sampling import SMOTE
from collections import Counter
import warnings
warnings.filterwarnings("ignore")

np.random.seed(42)
random.seed(42)

REGIONS  = ["Addis Ababa","Oromia","SNNPR","Amhara","Tigray","Sidama","Dire Dawa","Harari"]
SECTORS  = ["Agriculture","Manufacturing","Handicrafts","Livestock","Food Processing","Textiles","Services"]
PRODUCTS = {
    "Agriculture":     ["Teff","Wheat","Maize","Coffee","Barley","Sorghum","Sesame","Chickpea","Lentils","Sunflower"],
    "Manufacturing":   ["Metal Tools","Plastic Goods","Furniture","Construction Materials","Chemicals","Ceramics","Electronics"],
    "Handicrafts":     ["Pottery","Woven Baskets","Traditional Clothes","Leather Goods","Jewelry","Carved Wood","Paintings"],
    "Livestock":       ["Cattle","Sheep","Goat","Poultry","Camel","Honey","Fish","Eggs"],
    "Food Processing": ["Injera","Spices","Cooking Oil","Flour","Packed Grains","Dairy","Jams","Sauces"],
    "Textiles":        ["Cotton Fabric","Habesha Kemis","Scarves","Yarn","Blankets","Uniforms","Linen"],
    "Services":        ["Transport","Storage","Cold Chain","Packaging","Consulting","Maintenance","Security"]
}
PAY_METHODS = ["Cash","Bank Transfer","Mobile Money","Credit","Cheque"]

def rand_price(sector):
    base = {"Agriculture":2000,"Manufacturing":5000,"Handicrafts":800,
            "Livestock":15000,"Food Processing":1200,"Textiles":600,"Services":3000}
    return round(base[sector] * np.random.uniform(0.5, 2.0), 2)

def rand_date(days_back=1095, end_days_back=0):
    return (datetime.now() - timedelta(days=random.randint(end_days_back, days_back))).strftime("%Y-%m-%d")

print("="*60)
print("  REGENERATING FRAUD DATASET WITH RULE-BASED SIGNAL")
print("="*60)

rows = []
N = 20000
for i in range(N):
    sector  = random.choice(SECTORS)
    product = random.choice(PRODUCTS[sector])
    price   = rand_price(sector)
    qty     = random.randint(10, 3000)

    # Account age in days — new accounts are riskier
    account_age_days = int(np.random.exponential(scale=200))
    is_new_account = int(account_age_days < 14)

    payment_method   = random.choice(PAY_METHODS)
    delivery_used    = random.randint(0, 1)
    repeat_tx        = random.choices([0, 1], weights=[70, 30])[0]
    days_to_complete = max(1, int(np.random.exponential(scale=5)))
    dispute_raised   = random.choices([0, 1], weights=[90, 10])[0]

    # Price ratio: how far the agreed price deviates from market price.
    # Most transactions are close to market price (ratio near 1.0);
    # a minority are suspiciously cheap (classic price manipulation).
    if random.random() < 0.12:
        price_ratio = np.random.uniform(0.4, 0.7)   # suspiciously cheap
    else:
        price_ratio = np.random.uniform(0.85, 1.15)  # normal range
    market_price = price
    agreed_price = round(market_price * price_ratio, 2)

    producer_rating_after = round(np.random.uniform(1.0, 5.0), 1)
    merchant_rating_after = round(np.random.uniform(1.0, 5.0), 1)
    match_score = round(np.random.uniform(0.3, 1.0), 3)

    # ── RULE-BASED FRAUD PROBABILITY ──────────────────────────
    # Each risk factor adds to a cumulative fraud probability.
    fraud_prob = 0.03  # small baseline (innocent transactions can still look odd)

    if price_ratio < 0.75:
        fraud_prob += 0.35                      # price manipulation
    if is_new_account and price_ratio < 0.8:
        fraud_prob += 0.25                      # new account + cheap deal
    if days_to_complete <= 1 and qty > 500:
        fraud_prob += 0.20                      # suspiciously fast for large qty
    if dispute_raised and (producer_rating_after < 2.5 or merchant_rating_after < 2.5):
        fraud_prob += 0.20                      # dispute + bad outcome
    if payment_method == "Cash" and delivery_used == 0 and repeat_tx == 0:
        fraud_prob += 0.15                      # cash, no delivery, no history
    if match_score < 0.4:
        fraud_prob += 0.10                      # poor compatibility match

    fraud_prob = min(fraud_prob, 0.97)
    is_fraud = 1 if random.random() < fraud_prob else 0

    tx_date = rand_date(1095)
    tx_date_dt = datetime.strptime(tx_date, "%Y-%m-%d")

    rows.append({
        "transaction_id":        f"TXN{i+1:05d}",
        "sector":                sector,
        "product":               product,
        "region":                random.choice(REGIONS),
        "payment_method":        payment_method,
        "quantity":              qty,
        "agreed_price_birr":     agreed_price,
        "market_price_birr":     market_price,
        "price_ratio":           round(price_ratio, 4),
        "delivery_used":         delivery_used,
        "dispute_raised":        dispute_raised,
        "month":                 tx_date_dt.month,
        "year":                  tx_date_dt.year,
        "producer_rating_after": producer_rating_after,
        "merchant_rating_after": merchant_rating_after,
        "match_score":           match_score,
        "days_to_complete":      days_to_complete,
        "repeat_transaction":    repeat_tx,
        "account_age_days":      account_age_days,
        "is_new_account":        is_new_account,
        "cheap_and_new":         int(is_new_account and price_ratio < 0.8),
        "fast_and_large":        int(days_to_complete <= 1 and qty > 500),
        "cash_no_delivery":      int(payment_method == "Cash" and delivery_used == 0),
        "low_rating_avg":        round((producer_rating_after + merchant_rating_after) / 2, 2),
        "price_deviation":       round(abs(1 - price_ratio), 4),
        "risk_signal_count":     (
            int(price_ratio < 0.75) + int(is_new_account) +
            int(days_to_complete <= 1) + int(dispute_raised) +
            int(payment_method == "Cash" and delivery_used == 0) +
            int(match_score < 0.4)
        ),
        "is_fraud":              is_fraud,
    })

df = pd.DataFrame(rows)
print(f"\nGenerated {len(df):,} transactions")
print(f"Fraud rate: {df['is_fraud'].mean()*100:.2f}%  ({df['is_fraud'].sum()} fraud cases)")

# Encode categoricals
le = LabelEncoder()
for col in ["sector", "product", "region", "payment_method"]:
    df[col + "_enc"] = le.fit_transform(df[col])

feature_cols = [
    "sector_enc", "product_enc", "region_enc", "payment_method_enc",
    "quantity", "agreed_price_birr", "market_price_birr", "price_ratio",
    "delivery_used", "dispute_raised", "month", "year",
    "producer_rating_after", "merchant_rating_after", "match_score",
    "days_to_complete", "repeat_transaction", "account_age_days", "is_new_account",
    "cheap_and_new", "fast_and_large", "cash_no_delivery",
    "low_rating_avg", "price_deviation", "risk_signal_count"
]

X = df[feature_cols]
y = df["is_fraud"]

print(f"\nBefore SMOTE: {Counter(y)}")
smote = SMOTE(sampling_strategy=1.0, random_state=42, k_neighbors=5)
X_res, y_res = smote.fit_resample(X, y)
print(f"After SMOTE : {Counter(y_res)}")

df_final = pd.DataFrame(X_res, columns=feature_cols)
df_final["is_fraud"] = y_res
df_final.to_csv("data/fraud_dataset.csv", index=False)

print(f"\n✅ Saved fraud_dataset.csv — {len(df_final):,} rows")

print("\nCorrelation with is_fraud (should now be much stronger):")
print(df_final.corr(numeric_only=True)["is_fraud"].sort_values())
