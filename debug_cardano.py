
import pandas as pd
import numpy as np
from enhanced_risk_analyzer import analyze_asset
from model_validation import validate_model, generate_validation_report_text

def debug_final():
    ticker = "ADA-USD"
    print(f"Analyzing {ticker}...")
    try:
        df, _, meta = analyze_asset(ticker)
        if df.empty:
            print("No data found.")
            return
        
        # Exact logic from model_validation.py
        val_df = df.copy()
        import pandas as pd
        val_df['fwd_return'] = val_df['Close'].shift(-30) / val_df['Close'] - 1
        val_df = val_df.dropna()
        
        val_df['sma_200'] = val_df['Close'].rolling(200).mean()
        val_df['sma_200'] = val_df['sma_200'].bfill()
        trend_strength = (val_df['Close'] > val_df['sma_200']).mean()
        print(f"Trend Strength: {trend_strength:.4f}")
        
        is_momentum = trend_strength > 0.40
        print(f"Is Momentum (Threshold 0.40): {is_momentum}")
        
        metrics = validate_model(df)
        print("\n--- System Validation Result ---")
        print(generate_validation_report_text(ticker, metrics))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_final()
