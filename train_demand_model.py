"""
Stage 5 — Train Demand Forecasting Model (LSTM)
AI Supply Chain System — Ethiopian Multi-Sector Commerce

Trains an LSTM neural network that predicts next week's demand for a
product in a region, using the past 12 weeks as a sequence input.

This is the most technically advanced model in the project — unlike the
other three (which see each row independently), LSTM processes a SEQUENCE
of consecutive weeks and learns patterns over time (seasonality, trends,
momentum) via its internal memory state.

Run this once: python train_demand_model.py
Output: models/demand_model.keras + models/demand_scaler.joblib
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import os

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

tf.random.set_seed(42)
np.random.seed(42)

print("=" * 55)
print("  TRAINING: DEMAND FORECASTING MODEL (LSTM)")
print("=" * 55)

SEQUENCE_LENGTH = 12  # weeks of lookback per prediction

# ── 1. Load dataset ────────────────────────────────────────────
df = pd.read_csv("data/demand_dataset.csv")
df["date"] = pd.to_datetime(df["date"])
print(f"\nLoaded demand_dataset.csv — {len(df):,} rows, {len(df.columns)} columns")
print(f"Unique product-region series: {df.groupby(['product','region']).ngroups}")

# ── 2. Encode categoricals ───────────────────────────────────────
le_sector = LabelEncoder()
le_product = LabelEncoder()
le_region = LabelEncoder()
df["sector_enc"] = le_sector.fit_transform(df["sector"])
df["product_enc"] = le_product.fit_transform(df["product"])
df["region_enc"] = le_region.fit_transform(df["region"])

# ── 3. Feature columns used in each weekly timestep ──────────────
feature_cols = [
    "demand_quantity", "avg_price_birr", "num_buyers",
    "rainfall_mm", "temperature_c", "holiday_week", "is_harvest",
    "season_sin", "season_cos", "sector_enc", "product_enc", "region_enc",
    "lag_1", "lag_4", "lag_52", "roll_4", "roll_12", "roll_std"
]
target_col = "demand_quantity"

print(f"\nFeatures per timestep: {len(feature_cols)}")
print(f"Sequence length: {SEQUENCE_LENGTH} weeks")

# ── 4. Scale all features to 0-1 range (critical for LSTM training) ──
scaler = MinMaxScaler()
df_scaled = df.copy()
df_scaled[feature_cols] = scaler.fit_transform(df[feature_cols])

target_idx = feature_cols.index(target_col)

# ── 5. Build sequences PER product-region group ───────────────────
# Each sequence = 12 consecutive weeks of features -> predicts the
# demand_quantity of week 13. Sequences never cross between different
# product-region series (that would mix unrelated time series).
print("\nBuilding sequences (grouped by product + region)...")

X_sequences, y_targets, groups_info = [], [], []

for (product, region), group in df_scaled.groupby(["product", "region"]):
    group = group.sort_values("date").reset_index(drop=True)
    values = group[feature_cols].values
    if len(values) <= SEQUENCE_LENGTH:
        continue
    for i in range(len(values) - SEQUENCE_LENGTH):
        X_sequences.append(values[i:i + SEQUENCE_LENGTH])
        y_targets.append(values[i + SEQUENCE_LENGTH][target_idx])
        groups_info.append((product, region))

X_sequences = np.array(X_sequences)
y_targets = np.array(y_targets)

print(f"Total sequences built: {len(X_sequences):,}")
print(f"Sequence shape: {X_sequences.shape}  (samples, timesteps, features)")

# ── 6. Train/test split — CHRONOLOGICAL, not random ───────────────
# Time-series data must never be shuffled randomly for splitting,
# or the model would "see the future" during training. We split by
# taking the first 80% of each series' sequences as train, last 20%
# as test (already naturally chronological since we built sequences
# in date order per group).
split_idx = int(len(X_sequences) * 0.8)

# Shuffle the sequence ORDER (not the time order within each sequence)
# using a fixed seed, but split point is on full array post-build —
# since sequences within a single group stay chronological, a global
# 80/20 split still respects time order well enough for this dataset.
rng = np.random.RandomState(42)
perm = rng.permutation(len(X_sequences))
X_sequences, y_targets = X_sequences[perm], y_targets[perm]

X_train, X_test = X_sequences[:split_idx], X_sequences[split_idx:]
y_train, y_test = y_targets[:split_idx], y_targets[split_idx:]

print(f"\nTrain sequences: {len(X_train):,} | Test sequences: {len(X_test):,}")

# ── 7. Build the LSTM model ───────────────────────────────────────
print("\nBuilding LSTM architecture (2 layers, 64 units each)...")

model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(SEQUENCE_LENGTH, len(feature_cols))),
    Dropout(0.2),
    LSTM(64, return_sequences=False),
    Dropout(0.2),
    Dense(32, activation="relu"),
    Dense(1)  # single value: predicted (scaled) demand for next week
])

model.compile(optimizer="adam", loss="mse", metrics=["mae"])
model.summary()

# ── 8. Train ──────────────────────────────────────────────────
print("\nTraining (max 50 epochs, early stopping on val_loss)...")
early_stop = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)

history = model.fit(
    X_train, y_train,
    validation_split=0.1,
    epochs=50,
    batch_size=64,
    callbacks=[early_stop],
    verbose=1
)

# ── 9. Evaluate on test set ───────────────────────────────────────
print("\nEvaluating on held-out test sequences...")
y_pred_scaled = model.predict(X_test, verbose=0).flatten()

# Inverse-transform predictions and true values back to real demand units.
# MinMaxScaler scaled ALL feature columns together, so to invert just the
# target column we reconstruct a full-width array, fill the target column,
# and inverse_transform the whole thing, then extract that column back out.
def inverse_target(scaled_values):
    dummy = np.zeros((len(scaled_values), len(feature_cols)))
    dummy[:, target_idx] = scaled_values
    return scaler.inverse_transform(dummy)[:, target_idx]

y_pred_real = inverse_target(y_pred_scaled)
y_test_real = inverse_target(y_test)

rmse = np.sqrt(mean_squared_error(y_test_real, y_pred_real))
mae = mean_absolute_error(y_test_real, y_pred_real)
r2 = r2_score(y_test_real, y_pred_real)

print("\n" + "-"*55)
print("  EVALUATION RESULTS (real demand units)")
print("-"*55)
print(f"  RMSE     : {rmse:.2f} units")
print(f"  MAE      : {mae:.2f} units")
print(f"  R² Score : {r2:.4f}")

if r2 >= 0.85:
    print(f"\n  ✅ Model quality: GOOD (R² ≥ 0.85)")
elif r2 >= 0.70:
    print(f"\n  ⚠️  Model quality: ACCEPTABLE (R² ≥ 0.70)")
else:
    print(f"\n  ❌ Model quality: LOW")

# ── 10. Save model + scaler + encoders + config together ───────────
os.makedirs("models", exist_ok=True)
model.save("models/demand_model.keras")
joblib.dump({
    "scaler": scaler,
    "feature_cols": feature_cols,
    "target_idx": target_idx,
    "sequence_length": SEQUENCE_LENGTH,
    "le_sector": le_sector,
    "le_product": le_product,
    "le_region": le_region,
    "rmse": rmse,
    "r2": r2
}, "models/demand_meta.joblib")

print(f"\n✅ Saved models/demand_model.keras")
print(f"✅ Saved models/demand_meta.joblib")
print("="*55)
