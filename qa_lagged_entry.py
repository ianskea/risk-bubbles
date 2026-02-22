import pandas as pd
import numpy as np
from enhanced_risk_analyzer import analyze_asset

def test_lagged_entry(ticker="BTC-USD", candles=3):
    print(f"\n{'='*80}")
    print(f" TESTING LAGGED ENTRY (3-CANDLE CONFIRMATION) FOR {ticker}")
    print(f"{'='*80}")
    
    try:
        df, _, _ = analyze_asset(ticker)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # Look for a period where Risk < 0.30 (Value Zone)
    # and compare immediate entry vs lagged entry.
    
    df['ma50'] = df['Close'].rolling(50).mean()
    df['momentum_30'] = df['Close'].pct_change(30)
    
    # 3-candle confirmation: Price > Low of previous 3 candles? 
    # Or just 3 green candles? 
    # Let's try: Current Price > Highest of last 2 Close (Moving Up)
    df['is_stabilizing'] = (df['Close'] > df['Close'].shift(1)) & (df['Close'].shift(1) > df['Close'].shift(2))
    
    # Alternatively: Higher Lows
    df['higher_lows'] = (df['Low'] > df['Low'].shift(1)) & (df['Low'].shift(1) > df['Low'].shift(2))

    risk_col = 'risk_total'
    
    # Simulation
    in_value_zone = False
    blind_entry_date = None
    lagged_entry_date = None
    
    # For demo, let's look at the last 2 years
    start_date = pd.Timestamp.now() - pd.DateOffset(years=2)
    test_df = df[df.index >= start_date].copy()
    
    for i in range(len(test_df)):
        risk = test_df[risk_col].iloc[i]
        date = test_df.index[i]
        
        if risk < 0.30 and not in_value_zone:
            in_value_zone = True
            blind_entry_date = date
            print(f"  [BLIND] Value Zone Entered: {date.date()} (Risk: {risk:.2f}, Price: {test_df['Close'].iloc[i]:.2f})")
            
        if in_value_zone and lagged_entry_date is None:
            # Check for confirmation
            # 1. 3-candle stability (Higher Lows or 2 consecutive greens)
            confirmed = test_df['is_stabilizing'].iloc[i] or test_df['higher_lows'].iloc[i]
            # 2. Momentum turning
            mom_ok = test_df['momentum_30'].iloc[i] > -0.05
            
            if confirmed or mom_ok:
                lagged_entry_date = date
                print(f"  [LAGGED] Entry Confirmed:  {date.date()} (Price: {test_df['Close'].iloc[i]:.2f})")
                
        if risk > 0.40: # Exit zone
            in_value_zone = False
            lagged_entry_date = None
            blind_entry_date = None

    print(f"{'='*80}\n")

if __name__ == "__main__":
    test_lagged_entry("BTC-USD")
    test_lagged_entry("ETH-USD")
    test_lagged_entry("SDR.AX") # High volatility
