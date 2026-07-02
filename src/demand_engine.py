import os
import joblib
import numpy as np
from pathlib import Path

# Global model cache
_demand_model = None
_demand_meta = None

def load_demand_models():
    """Load demand forecasting models from models directory"""
    global _demand_model, _demand_meta
    
    if _demand_model is not None and _demand_meta is not None:
        return _demand_model, _demand_meta
    
    # Try multiple paths
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
    
    # Load Keras model
    try:
        from tensorflow import keras
        model_path = model_dir / "demand_model.keras"
        _demand_model = keras.models.load_model(model_path)
    except Exception as e:
        raise ImportError(f"Failed to load demand_model.keras: {e}")
    
    # Load metadata (scaler, encoders, etc.)
    meta_path = model_dir / "demand_meta.pkl"
    try:
        _demand_meta = joblib.load(meta_path)
    except Exception as e:
        raise ImportError(f"Failed to load demand_meta.pkl: {e}")
    
    return _demand_model, _demand_meta

def forecast_demand(sector, product, region, historical_data=None):
    """
    Forecast demand for a product
    Returns: dict with predicted_demand, confidence_interval, trend
    """
    model, meta = load_demand_models()
    
    # Prepare input features
    # Adjust this based on your model's expected input
    try:
        # Example: encode categorical variables
        sector_enc = meta.get('sector_encoder', {}).get(sector, 0)
        region_enc = meta.get('region_encoder', {}).get(region, 0)
        
        # Create feature vector
        # Adjust dimensions based on your model
        features = np.array([[
            sector_enc,
            region_enc,
            meta.get('product_map', {}).get(product, 0),
            # Add other features as needed
        ]])
        
        # Scale features if scaler exists
        if 'scaler' in meta:
            features = meta['scaler'].transform(features)
        
        # Predict
        prediction = model.predict(features, verbose=0)
        predicted_demand = float(prediction[0][0])
        
        # Calculate confidence interval (if available)
        confidence = meta.get('confidence', 0.95)
        std_error = meta.get('std_error', predicted_demand * 0.1)
        
        return {
            "predicted_demand": max(0, predicted_demand),
            "confidence_interval": {
                "lower": max(0, predicted_demand - 1.96 * std_error),
                "upper": predicted_demand + 1.96 * std_error,
                "confidence": confidence
            },
            "trend": "increasing" if predicted_demand > meta.get('avg_demand', 0) else "stable",
            "recommendation": f"Stock {max(0, predicted_demand):.0f} units based on AI forecast"
        }
        
    except Exception as e:
        # Fallback to simple heuristic
        return {
            "predicted_demand": 100,  # Default
            "confidence_interval": {"lower": 80, "upper": 120, "confidence": 0.8},
            "trend": "unknown",
            "recommendation": "AI forecast unavailable - using default estimate",
            "error": str(e)
        }
