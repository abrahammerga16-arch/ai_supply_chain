# Stage 5 — LSTM Demand Forecasting
## AI-Powered Supply Chain System

This is the **complete, final stage** of the system. It builds on all four
previous stages and adds the fourth AI model: an LSTM neural network that
forecasts weekly demand for any product-region pair.

---

## 📁 Complete file list

```
stage5/
├── app.py                      ← Full Streamlit app (all 4 AI models)
├── schema.sql                  ← Initial Supabase table definitions
├── migration_stage2.sql        ← Adds merchant preference columns
├── migration_stage4.sql        ← Adds fraud risk columns to orders
├── migration_stage5.sql        ← No schema changes (forecasts are real-time)
├── requirements.txt            ← All Python dependencies including TensorFlow
├── .env                        ← Your Supabase credentials (fill in)
├── .env.example                ← Template showing required keys
│
├── src/
│   ├── db.py                   ← Supabase client helper
│   ├── matching_engine.py      ← Stage 2: KNN/SVM smart matching
│   ├── price_engine.py         ← Stage 3: Random Forest price recommendation
│   ├── fraud_engine.py         ← Stage 4: Gradient Boosting fraud detection
│   └── demand_engine.py        ← Stage 5: LSTM demand forecasting (NEW)
│
├── models/
│   ├── matching_model.joblib   ← Trained matching model (99.3% accuracy)
│   ├── price_model.joblib      ← Trained price model (R²=0.987)
│   ├── fraud_model.joblib      ← Trained fraud model (88.5% accuracy)
│   ├── demand_model.keras      ← Trained LSTM model (NEW)
│   └── demand_meta.joblib      ← Scaler, encoders, feature list (NEW)
│
├── data/
│   └── demand_dataset.csv      ← 46,592 weekly demand records (NEW)
│
├── train_demand_model.py       ← LSTM training script (NEW)
├── train_fraud_model.py        ← Fraud model training script
└── fix_fraud_dataset.py        ← Fraud dataset regeneration script
```

---

## 📊 All model results

| Stage | Model | Algorithm | Result |
|---|---|---|---|
| 2 | Smart Matching | SVM (rbf) | 99.3% accuracy |
| 3 | Price Recommendation | Random Forest | R²=0.987 |
| 4 | Fraud Detection | Gradient Boosting | 88.5% accuracy, 88.2% F1 |
| 5 | Demand Forecasting | LSTM (2 layers) | R²=0.963, RMSE=±200 units |

---

## 🚀 Setup (fresh install)

### Step 1 — Supabase migrations
Run in **Supabase → SQL Editor → New Query**, one at a time, in order:
1. `schema.sql`
2. `migration_stage2.sql`
3. `migration_stage4.sql`
4. `migration_stage5.sql`

### Step 2 — Fill `.env`
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```
Get both from **Supabase → Project Settings → API**.

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Run the app
```bash
streamlit run app.py
```

---

## 🧪 Testing all 4 AI features

**Smart Matching (Stage 2)**
Log in as producer → list a product → click **"🤖 Find Best Matches"**
→ See ranked list of merchants scored by compatibility

**Price Recommendation (Stage 3)**
Producer → "➕ List a Product" → fill in sector, product, region, quality
→ See live AI price suggestion update before you submit

**Fraud Detection (Stage 4)**
Log in as merchant → browse products → list includes a **🟢/🟡/🔴 risk badge**
→ List a product at a very low price (e.g. Teff at 200 Birr) to trigger 🔴 High Risk

**Demand Forecast (Stage 5)**
Producer → "📋 My Listings" → below each listing see a **📈 line chart**
showing last 8 weeks actual + next 4 weeks predicted demand with trend indicator

---

## 🧠 About the LSTM model

- **Architecture**: 2 × LSTM(64) + Dropout(0.2) + Dense(32) + Dense(1)
- **Input**: 12 weeks of history × 18 features per week
- **Features**: demand, price, buyers, rainfall, temperature, seasonality
  (sin/cos), harvest flag, lag features (1/4/52 weeks), rolling averages
- **Training**: 46,592 sequences from 224 unique product-region series,
  80/20 train/test split, early stopping with patience=6
- **Result**: R²=0.963, RMSE=±199.8 units on held-out test data

The model forecasts iteratively — to predict 4 weeks ahead, it predicts
week 1, feeds that back into the window, then predicts week 2, and so on.

---

## ⚠️ Common issues

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: tensorflow` | `pip install tensorflow` |
| Demand chart missing | Confirm `demand_model.keras` + `demand_meta.joblib` are in `models/` |
| Fraud badge missing | Run `migration_stage4.sql` in Supabase |
| Supabase error | Check `.env` — URL needs `https://`, use `anon` key not `service_role` |
| Slow first load | Normal — TensorFlow and the LSTM model take ~10s to load the first time |

---

## 🔁 Retraining models

All training scripts are included. Run from the `stage5/` folder:

```bash
# Retrain demand model (takes ~2-5 min)
python train_demand_model.py

# Retrain fraud model
python train_fraud_model.py

# Regenerate fraud dataset (then retrain)
python fix_fraud_dataset.py
python train_fraud_model.py
```
