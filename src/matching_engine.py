import joblib
import numpy as np
from pathlib import Path

# Global cache
_matching_model = None

def load_matching_model():
    """Load merchant matching model"""
    global _matching_model
    
    if _matching_model is not None:
        return _matching_model
    
    # ✅ CORRECT PATH
    models_dir = Path(__file__).parent.parent / "models"
    
    if not models_dir.exists():
        raise FileNotFoundError(f"Models directory not found at: {models_dir}")
    
    # ✅ CORRECT FILENAME
    model_path = models_dir / "matching_model.joblib"  # ← Changed from .pkl
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    _matching_model = joblib.load(model_path)
    
    return _matching_model

def rank_merchants(listing_data, merchant_list):
    """Rank merchants based on compatibility with product listing"""
    try:
        model = load_matching_model()
        
        ranked_merchants = []
        
        for merchant in merchant_list:
            # Calculate compatibility features
            sector_match = 1 if listing_data.get('sector') == merchant.get('preferred_sector') else 0
            region_match = 1 if listing_data.get('region') == merchant.get('region') else 0
            
            # Create feature vector (adjust based on your model's expected input)
            features = np.array([[
                sector_match,
                region_match,
                listing_data.get('price_birr', 0) / 1000,
                listing_data.get('quantity', 0),
                merchant.get('rating', 4.0),
                merchant.get('total_transactions', 0),
            ]])
            
            # Predict match probability
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(features)[0]
                match_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
            else:
                match_prob = float(model.predict(features)[0])
            
            ranked_merchants.append({
                **merchant,
                "match_probability": min(1.0, max(0.0, match_prob)),
                "match_percentage": round(min(1.0, max(0.0, match_prob)) * 100, 1),
                "recommendation": "Excellent match" if match_prob >= 0.7 else "Good match" if match_prob >= 0.4 else "Potential match"
            })
        
        # Sort by match probability
        ranked_merchants.sort(key=lambda x: x['match_probability'], reverse=True)
        
        return ranked_merchants
        
    except Exception as e:
        # Fallback: simple rule-based matching
        ranked_merchants = []
        for merchant in merchant_list:
            score = 0.3
            if listing_data.get('sector') == merchant.get('preferred_sector'):
                score += 0.3
            if listing_data.get('region') == merchant.get('region'):
                score += 0.2
            
            ranked_merchants.append({
                **merchant,
                "match_probability": min(1.0, score),
                "match_percentage": round(score * 100, 1),
                "recommendation": "Fallback match (model unavailable)"
            })
        
        ranked_merchants.sort(key=lambda x: x['match_probability'], reverse=True)
        return ranked_merchants
