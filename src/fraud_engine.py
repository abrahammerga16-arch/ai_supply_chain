import os
import joblib
import numpy as np
from pathlib import Path

# Global model cache
_fraud_model = None

def load_fraud_model():
    """Load fraud detection model"""
    global _fraud_model
    
    if _fraud_model is not None:
        return _fraud_model
    
    possible_paths = [
        Path(__file__).parent.parent / "models",
        Path(__file__).parent / "models",
        Path("models"),
    ]
    
    model_dir = None
    for p in possible_paths:
        if p.exists():
            model_dir = p
            break
    
    if model_dir is None:
        raise FileNotFoundError("models directory not found")
    
    model_path = model_dir / "fraud_model.pkl"
    try:
        _fraud_model = joblib.load(model_path)
    except Exception as e:
        raise ImportError(f"Failed to load fraud_model.pkl: {e}")
    
    return _fraud_model

def check_fraud_risk(sector, product, region, payment_method, quantity, agreed_price_birr, market_price_birr):
    """
    Assess fraud risk for a transaction
    Returns: dict with risk_level, is_fraud, fraud_probability, risk_factors
    """
    model = load_fraud_model()
    
    try:
        # Feature engineering
        price_deviation = abs(agreed_price_birr - market_price_birr) / max(market_price_birr, 1)
        
        # Encode features
        features = {
            'sector': sector,
            'region': region,
            'payment_method': payment_method,
            'quantity': quantity,
            'price_deviation': price_deviation,
            'agreed_price': agreed_price_birr,
            'market_price': market_price_birr,
        }
        
        # Convert to model input format
        # Adjust based on your model's requirements
        feature_vector = np.array([[
            hash(sector) % 100,  # Replace with proper encoding
            hash(region) % 100,
            hash(payment_method) % 10,
            quantity,
            price_deviation,
            agreed_price_birr / 1000,
            market_price_birr / 1000,
        ]])
        
        # Predict
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(feature_vector)[0]
            fraud_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
        else:
            fraud_prob = float(model.predict(feature_vector)[0])
        
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
        
        # Identify risk factors
        risk_factors = []
        if price_deviation > 0.3:
            risk_factors.append("Unusual price deviation")
        if quantity > 1000:
            risk_factors.append("Large quantity order")
        if payment_method == "Cash":
            risk_factors.append("Cash payment method")
        
        return {
            "risk_level": risk_level,
            "is_fraud": is_fraud,
            "fraud_probability": fraud_prob,
            "risk_factors": risk_factors,
            "recommendation": "Review transaction manually" if risk_level == "High" else "Proceed with caution" if risk_level == "Medium" else "Transaction appears safe"
        }
        
    except Exception as e:
        # Fallback
        return {
            "risk_level": "Unknown",
            "is_fraud": 0,
            "fraud_probability": 0.5,
            "risk_factors": ["Model unavailable"],
            "recommendation": "Manual review recommended",
            "error": str(e)
        }
