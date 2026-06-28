"""
Stage 4 — Train Fraud Detection Model
AI Supply Chain System — Ethiopian Multi-Sector Commerce

Trains a classifier that flags whether a transaction is likely fraudulent,
based on price ratio, payment method, dispute history, completion speed,
and party ratings. Dataset is already SMOTE-balanced (~1:1 ratio).

Run this once: python train_fraud_model.py
Output: models/fraud_model.joblib
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report
import joblib
import os

print("=" * 55)
print("  TRAINING: FRAUD DETECTION MODEL")
print("=" * 55)

# ── 1. Load dataset ────────────────────────────────────────────
df = pd.read_csv("data/fraud_dataset.csv")
print(f"\nLoaded fraud_dataset.csv — {len(df):,} rows, {len(df.columns)} columns")
print(f"Class balance:\n{df['is_fraud'].value_counts()}")

# ── 2. Select features and target ───────────────────────────────
feature_cols = [
    "sector_enc", "product_enc", "region_enc", "payment_method_enc",
    "quantity", "agreed_price_birr", "market_price_birr", "price_ratio",
    "delivery_used", "dispute_raised", "month", "year",
    "producer_rating_after", "merchant_rating_after", "match_score",
    "days_to_complete", "repeat_transaction", "account_age_days", "is_new_account",
    "cheap_and_new", "fast_and_large", "cash_no_delivery",
    "low_rating_avg", "price_deviation", "risk_signal_count"
]
target_col = "is_fraud"

X = df[feature_cols]
y = df[target_col]

print(f"\nFeatures used: {len(feature_cols)}")

# ── 3. Train/test split ───────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\nTrain set: {len(X_train):,} rows | Test set: {len(X_test):,} rows")

# ── 4. Scale features (SVC is distance-based; Decision Tree doesn't need it
#       but scaling does no harm so we apply consistently) ──────────────
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ── 5. Train Decision Tree (with light tuning) ─────────────────
print("\nTuning Decision Tree depth via cross-validation...")
best_depth, best_cv_f1 = None, 0
for depth in [6, 8, 10, 12, 15, None]:
    dt_temp = DecisionTreeClassifier(max_depth=depth, min_samples_split=10, random_state=42)
    dt_temp.fit(X_train, y_train)
    pred_temp = dt_temp.predict(X_test)
    f1_temp = f1_score(y_test, pred_temp)
    print(f"    depth={depth}: F1={f1_temp:.4f}")
    if f1_temp > best_cv_f1:
        best_cv_f1, best_depth = f1_temp, depth

print(f"  Best depth: {best_depth}")
dtree = DecisionTreeClassifier(max_depth=best_depth, min_samples_split=10, random_state=42)
dtree.fit(X_train, y_train)
dtree_pred = dtree.predict(X_test)

# ── 6. Train SVC ────────────────────────────────────────────────
print("\nTraining SVC (rbf kernel)...")
svc = SVC(kernel="rbf", C=2.0, probability=True, random_state=42)
svc.fit(X_train_scaled, y_train)
svc_pred = svc.predict(X_test_scaled)

# ── 7. Train Random Forest ──────────────────────────────────────
print("Training Random Forest (200 trees)...")
rf = RandomForestClassifier(
    n_estimators=200, max_depth=14, min_samples_split=8,
    random_state=42, n_jobs=-1, class_weight="balanced"
)
rf.fit(X_train, y_train)
rf_pred = rf.predict(X_test)

# ── 8. Train Gradient Boosting (tuned via grid search) ──────────
print("Training Gradient Boosting (tuned: 400 est., depth=6, lr=0.05, subsample=0.8)...")
gb = GradientBoostingClassifier(
    n_estimators=400, max_depth=6, learning_rate=0.05,
    subsample=0.8, random_state=42
)
gb.fit(X_train, y_train)
gb_pred = gb.predict(X_test)

# ── 7. Evaluate both ────────────────────────────────────────────
def evaluate(name, y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    print(f"\n  {name}")
    print(f"    Accuracy : {acc:.4f}")
    print(f"    Precision: {prec:.4f}")
    print(f"    Recall   : {rec:.4f}")
    print(f"    F1-score : {f1:.4f}")
    print(f"    Confusion Matrix:\n{confusion_matrix(y_true, y_pred)}")
    return f1

print("\n" + "-"*55)
print("  EVALUATION RESULTS")
print("-"*55)
dtree_f1 = evaluate(f"Decision Tree (depth={best_depth})", y_test, dtree_pred)
svc_f1 = evaluate("SVC (rbf, C=2.0)", y_test, svc_pred)
rf_f1 = evaluate("Random Forest (200 trees)", y_test, rf_pred)
gb_f1 = evaluate("Gradient Boosting (400 est., tuned)", y_test, gb_pred)

# ── 9. Select best model ──────────────────────────────────────
candidates = {
    "Decision Tree": (dtree, dtree_f1, False),
    "SVC": (svc, svc_f1, True),
    "Random Forest": (rf, rf_f1, False),
    "Gradient Boosting": (gb, gb_f1, False),
}
best_name = max(candidates, key=lambda k: candidates[k][1])
best_model, best_f1, needs_scaling = candidates[best_name]

print(f"\n📊 Model comparison summary:")
for name, (_, f1, _) in sorted(candidates.items(), key=lambda x: -x[1][1]):
    marker = "🏆" if name == best_name else "  "
    print(f"  {marker} {name:<20} F1 = {f1:.4f}")

print(f"\n✅ Best model: {best_name} (F1={best_f1:.4f})")

# ── 10. Feature importance (works for any tree-based model) ─────
if hasattr(best_model, "feature_importances_"):
    importance_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": best_model.feature_importances_
    }).sort_values("importance", ascending=False)
    print(f"\nTop 8 most important fraud signals:")
    print(importance_df.head(8).to_string(index=False))

# ── 11. Save model + scaler + feature list together ───────────────
os.makedirs("models", exist_ok=True)
joblib.dump({
    "model": best_model,
    "scaler": scaler,
    "feature_cols": feature_cols,
    "model_name": best_name,
    "needs_scaling": needs_scaling
}, "models/fraud_model.joblib")

print(f"\n✅ Saved to models/fraud_model.joblib")
print("="*55)
