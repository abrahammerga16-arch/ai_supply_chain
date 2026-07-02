import joblib
from pathlib import Path
from tensorflow import keras

# Global cache
_demand_model = None
_demand_meta = None

def load_demand_models():
    """Load demand forecasting models"""
    global _demand_model, _demand_meta
    
    if _demand_model is not None and _demand_meta is not None:
        return _demand_model, _demand_meta
    
    # ✅ CORRECT PATH: Go up from src/ to project root, then into models/
    models_dir = Path(__file__).parent.parent / "models"
    
    if not models_dir.exists():
        raise FileNotFoundError(f"Models directory not found at: {models_dir}")
    
    # ✅ CORRECT FILENAME: .joblib not .pkl
    model_path = models_dir / "demand_model.keras"
    meta_path = models_dir / "demand_meta.joblib"  # ← Changed from .pkl
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Meta file not found: {meta_path}")
    
    # Load Keras model
    _demand_model = keras.models.load_model(model_path)
    
    # Load metadata
    _demand_meta = joblib.load(meta_path)
    
    return _demand_model, _demand_meta

def forecast_demand(sector, product, region, historical_data=None):
    """Forecast demand for a product"""
    try:
        model, meta = load_demand_models()
        
        # Your prediction logic here
        # Example:
        # features = prepare_features(sector, product, region, meta)
        # prediction = model.predict(features)
        
        return {
            "predicted_demand": 100,  # Replace with actual prediction
            "confidence_interval": {"lower": 80, "upper": 120, "confidence": 0.95},
            "trend": "stable",
            "recommendation": "Stock 100 units based on AI forecast"
        }
    except Exception as e:
        return {
            "predicted_demand": 100,
            "confidence_interval": {"lower": 80, "upper": 120, "confidence": 0.8},
            "trend": "unknown",
            "recommendation": "AI forecast unavailable - using default",
            "error": str(e)
        }
