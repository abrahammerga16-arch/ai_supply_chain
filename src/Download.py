import os
import urllib.request
from pathlib import Path

def download_models_from_github():
    """Download models from GitHub repository"""
    
    repo_url = "https://raw.githubusercontent.com/abrahammerga16-arch/ai_supply_chain/main/models"
    
    models = [
        "demand_model.keras",
        "demand_meta.pkl",
        "fraud_model.pkl",
        "matching_model.pkl"
    ]
    
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    
    for model_name in models:
        model_path = models_dir / model_name
        if not model_path.exists():
            print(f"Downloading {model_name}...")
            url = f"{repo_url}/{model_name}"
            try:
                urllib.request.urlretrieve(url, model_path)
                print(f"✓ Downloaded {model_name}")
            except Exception as e:
                print(f"✗ Failed to download {model_name}: {e}")
        else:
            print(f"✓ {model_name} already exists")

if __name__ == "__main__":
    download_models_from_github()
