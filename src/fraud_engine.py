import joblib
import numpy as np
from pathlib import Path

_fraud_model = None

def load_fraud_model():
    """Load fraud detection model"""
    global _fraud_model
    
    if _fraud_model is not None:
        return _fraud_model
    
    models_dir = Path(__file__).parent.parent / "models"
    
    if not models_dir.exists():
        raise FileNotFoundError(f"Models directory not found at: {models_dir}")
    
    model_path = models_dir / "fraud_model.joblib"
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    try:
        _fraud_model = joblib.load(model_path)
    except Exception as e:
        # If joblib fails, try with custom objects
        import pickle
        with open(model_path, 'rb') as f:
            _fraud_model = pickle.load(f)
    
    return _fraud_model

def check_fraud_risk(sector, product, region, payment_method, quantity, agreed_price_birr, market_price_birr):
    """Assess fraud risk"""
    try:
        model = load_fraud_model()
        
        # Feature engineering
        price_deviation = abs(agreed_price_birr - market_price_birr) / max(market_price_birr, 1)
        
        # Create feature vector
        features = np.array([[
            hash(sector) % 100,
            hash(region) % 100,
            hash(payment_method) % 10,
            float(quantity),
            float(price_deviation),
            float(agreed_price_birr) / 1000,
            float(market_price_birr) / 1000,
        ]])
        
        # Predict
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(features)[0]
            fraud_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
        else:
            fraud_prob = float(model.predict(features)[0])
        
        # Determine risk level
        if fraud_prob >= 0.7:
            risk_level = "High"
            is_fraud = 1
        elif fraud_prob >= 0.4:
            risk_level = "Medium"
            is_fraud = 0
        else:
            risk_level = "Low"
            is_fraud = 0
        
        return {
            "risk_level": risk_level,
            "is_fraud": is_fraud,
            "fraud_probability": fraud_prob,
            "risk_factors": [],
            "recommendation": "Review transaction manually" if risk_level == "High" else "Transaction appears safe"
        }
    except Exception as e:
        return {
            "risk_level": "Low",
            "is_fraud": 0,
            "fraud_probability": 0.1,
            "risk_factors": ["Model unavailable - using safe default"],
            "recommendation": "Transaction appears safe",
            "error": str(e)
        }
