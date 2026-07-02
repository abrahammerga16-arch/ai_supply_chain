def recommend_price(sector, product, region, quality_grade, quantity):
    """
    Recommend price based on market data and ML model
    You can add ML model here if you have one, or use rule-based
    """
    # Base prices by sector (example)
    base_prices = {
        "Agriculture": 150,
        "Manufacturing": 300,
        "Handicrafts": 200,
        "Livestock": 500,
        "Food Processing": 250,
    }
    
    base_price = base_prices.get(sector, 200)
    
    # Quality multiplier
    quality_mult = {"A": 1.2, "B": 1.0, "C": 0.8}.get(quality_grade, 1.0)
    
    # Region adjustment
    region_mult = {"Addis Ababa": 1.15, "Dire Dawa": 1.05}.get(region, 1.0)
    
    # Quantity discount
    qty_discount = 0.95 if quantity > 100 else 1.0
    
    recommended = base_price * quality_mult * region_mult * qty_discount
    
    return {
        "recommended_price_birr": round(recommended, 2),
        "price_range": {
            "min": round(recommended * 0.9, 2),
            "max": round(recommended * 1.1, 2)
        },
        "factors": {
            "quality_grade": quality_grade,
            "region": region,
            "quantity_discount": qty_discount < 1.0
        }
    }
