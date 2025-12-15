
import pandas as pd
import sys
from risk_analyzer import calculate_log_regression_risk as legacy_calc
from enhanced_risk_analyzer import analyze_asset

def compare_ticker(ticker):
    print(f"\n--- Comparing Systems for {ticker} ---")
    
    # Run New System
    try:
        new_df, _, new_meta = analyze_asset(ticker)
        new_risk = new_meta.get('last_risk', 0)
    except Exception as e:
        print(f"New System Error: {e}")
        return

    # Run Legacy System
    try:
        # Legacy fetch_data is inside risk_analyzer or we can reuse? 
        # Actually risk_analyzer.fetch_data is same as imported one? 
        # existing risk_analyzer imports yfinance directly.
        # Let's import fetch_data from risk_analyzer to be safe.
        from risk_analyzer import fetch_data as legacy_fetch
        leg_data = legacy_fetch(ticker)
        leg_df = legacy_calc(leg_data)
        leg_risk = leg_df['risk'].iloc[-1]
    except Exception as e:
        print(f"Legacy System Error: {e}")
        return
        
    print(f"Price: {new_meta.get('last_price'):.2f}")
    print(f"Legacy Risk Score: {leg_risk:.4f}")
    print(f"New System Score:  {new_risk:.4f}")
    
    diff = new_risk - leg_risk
    print(f"Difference:        {diff:+.4f}")
    
    if abs(diff) > 0.3:
        print(">> SIGNIFICANT DIVERGENCE <<")
    
if __name__ == "__main__":
    if len(sys.argv) > 1:
        compare_ticker(sys.argv[1])
    else:
        # Default test
        compare_ticker("BTC-USD")
        compare_ticker("ETH-USD")
