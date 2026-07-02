import os
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

# Global model cache
_matching_model = None

def load_matching_model():
    """Load merchant matching model"""
    global _matching_model
    
    if _matching_model is not None:
        return _matching_model
    
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
    
    model_path = model_dir / "matching_model.pkl"
    try:
        _matching_model = joblib.load(model_path)
    except Exception as e:
        raise ImportError(f"Failed to load matching_model.pkl: {e}")
    
    return _matching_model

def rank_merchants(listing_data, merchant_list):
    """
    Rank merchants based on compatibility with product listing
    Returns: list of merchants with match_probability and ranking
    """
    model = load_matching_model()
    
    try:
        ranked_merchants = []
        
        for merchant in merchant_list:
            # Calculate compatibility features
            sector_match = 1 if listing_data.get('sector') == merchant.get('preferred_sector') else 0
            region_match = 1 if listing_data.get('region') == merchant.get('region') else 0
            
            # Price compatibility
            total_cost = listing_data.get('price_birr', 0) * listing_data.get('quantity', 1)
            budget_fit = 1 if total_cost <= merchant.get('max_budget_birr', float('inf')) else 0
            
            # Quality match
            quality_match = 1 if (
                merchant.get('preferred_quality') == 'Any' or 
                listing_data.get('quality_grade') == merchant.get('preferred_quality')
            ) else 0
            
            # Create feature vector
            features = np.array([[
                sector_match,
                region_match,
                budget_fit,
                quality_match,
                listing_data.get('price_birr', 0) / 1000,
                listing_data.get('quantity', 0),
                merchant.get('rating', 4.0),
                merchant.get('total_transactions', 0),
                merchant.get('years_in_business', 1),
                merchant.get('return_rate', 0.05),
            ]])
            
            # Predict match probability
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(features)[0]
                match_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
            else:
                match_prob = float(model.predict(features)[0])
            
            # Calculate additional scoring factors
            delivery_bonus = 0.1 if (
                listing_data.get('delivery_available') and 
                merchant.get('needs_delivery', False)
            ) else 0
            
            verification_bonus = 0.05 if merchant.get('is_verified', False) else 0
            
            final_score = min(1.0, match_prob + delivery_bonus + verification_bonus)
            
            ranked_merchants.append({
                **merchant,
                "match_probability": final_score,
                "match_percentage": round(final_score * 100, 1),
                "sector_match": bool(sector_match),
                "region_match": bool(region_match),
                "budget_fit": bool(budget_fit),
                "recommendation": "Excellent match" if final_score >= 0.7 else "Good match" if final_score >= 0.4 else "Potential match"
            })
        
        # Sort by match probability
        ranked_merchants.sort(key=lambda x: x['match_probability'], reverse=True)
        
        return ranked_merchants
        
    except Exception as e:
        # Fallback: simple rule-based matching
        ranked_merchants = []
        for merchant in merchant_list:
            score = 0.3  # Base score
            if listing_data.get('sector') == merchant.get('preferred_sector'):
                score += 0.3
            if listing_data.get('region') == merchant.get('region'):
                score += 0.2
            if listing_data.get('quality_grade') == merchant.get('preferred_quality') or merchant.get('preferred_quality') == 'Any':
                score += 0.2
            
            ranked_merchants.append({
                **merchant,
                "match_probability": min(1.0, score),
                "match_percentage": round(score * 100, 1),
                "recommendation": "Fallback match"
            })
        
        ranked_merchants.sort(key=lambda x: x['match_probability'], reverse=True)
        return ranked_merchants
