import pandas as pd
import numpy as np
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset

def audit_black_swan(ticker, start="2020-01-01", end="2020-06-01"):
    try:
        df, _, _ = analyze_asset(ticker)
    except:
        return None

    df = df[(df.index >= start) & (df.index <= end)].copy()
    if df.empty: return None

    # Identify the Top and Bottom
    peak_price = df['Close'].max()
    peak_date = df['Close'].idxmax()
    peak_risk = df.loc[peak_date, 'risk_total']
    
    bottom_price = df['Close'].min()
    bottom_date = df['Close'].idxmin()
    bottom_risk = df.loc[bottom_date, 'risk_total']
    
    # Check for early warning (risk increase in the 2 weeks leading up to the peak)
    pre_peak = df[:peak_date].tail(14)
    risk_trend = pre_peak['risk_total'].mean()

    return {
        "Ticker": ticker,
        "Peak_Price": f"${peak_price:.2f}",
        "Peak_Risk": f"{peak_risk:.2f}",
        "Crash_Depth": f"{(bottom_price/peak_price - 1)*100:.1f}%",
        "Bottom_Risk": f"{bottom_risk:.2f}",
        "Early_Warning": "YES" if peak_risk > 0.70 else "NO"
    }

def run_audit():
    print(f"\n{'='*80}")
    print(f" BLACK SWAN AUDIT: The COVID Crash (Feb-Mar 2020)")
    print(f" Goal: Did the system see risk rising before the cliff?")
    print(f"{'='*80}")
    
    tickers = ["SPY", "BTC-USD", "BHP.AX", "GLD", "MQG.AX"]
    results = []
    for t in tickers:
        print(f"Auditing {t}...")
        res = audit_black_swan(t)
        if res: results.append(res)
        
    print("\n--- RESULTS ---")
    print(pd.DataFrame(results).to_string(index=False))
    print(f"{'='*80}\n")
    print("Interpretation:")
    print("1. Peak Risk > 0.75: System would have been 'Reducing' exposure before the crash.")
    print("2. Bottom Risk < 0.30: System would have been 'Boosting' at the absolute bottom.")
    print("3. Peak Risk < 0.50: Pure Black Swan - no warning, just reactive management.")

if __name__ == "__main__":
    run_audit()
