
import yfinance as yf
import pandas as pd
import numpy as np
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def run_historical_verification():
    """
    Backtests the Market Health 'Regime Card' logic over the last 2 years.
    Specifically checks if 'Narrow Breadth' or 'Compression' flagged danger.
    """
    print("Starting Historical Verification of Market Health Metrics (2Y)...")
    
    # 1. Fetch History (Same logic as market_health.py but keeping time index)
    tickers = [
        "BTC-USD", "ETH-USD", "BNB-USD", "ADA-USD", "SOL-USD", 
        "XRP-USD", "DOGE-USD", "DOT-USD", "LTC-USD", "LINK-USD"
    ] # Reduced basket for speed but representative
    
    print("Fetching Basket Data...")
    data = yf.download(tickers, period="2y", progress=False, group_by='ticker', auto_adjust=True)
    
    # Extract Closes
    closes = pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        # Flatten logic
        for t in tickers:
            try:
                # Key access data['Close']['BTC-USD'] works if level 0 is Price
                # Try standard access
                if t in data:
                    closes[t] = data[t]['Close']
                elif (t, 'Close') in data.columns:
                     closes[t] = data[(t, 'Close')]
            except: pass
    
    # Calculate AD Line History
    if closes.empty:
        print("Error: No data fetched.")
        return

    returns = closes.pct_change()
    advances = (returns > 0).sum(axis=1)
    declines = (returns < 0).sum(axis=1)
    net = advances - declines
    ad_line = net.cumsum()
    
    # Fetch BTC for Reference
    btc = closes['BTC-USD']
    
    # Check Correlations (Rolling 90D)
    # Need SPX/Gold for this
    print("Fetching Macro Data...")
    macro = yf.download(["BTC-USD", "^GSPC", "GC=F"], period="2y", progress=False, auto_adjust=True)
    macro_closes = pd.DataFrame()
    # Simplified extraction (assumes knowledge of yfinance structure from debug)
    # Using previous known structure logic or improved one
    try:
        # Check standard flattened first
        if 'Close' in macro.columns.get_level_values(0):
             c = macro['Close']
             if 'BTC-USD' in c: macro_closes['BTC'] = c['BTC-USD']
             if '^GSPC' in c: macro_closes['SPX'] = c['^GSPC']
             if 'GC=F' in c: macro_closes['GOLD'] = c['GC=F']
        else:
             # Iterate
             for col in macro.columns:
                 if col[0] == 'Close':
                     if col[1] == 'BTC-USD': macro_closes['BTC'] = macro[col]
                     elif col[1] == '^GSPC': macro_closes['SPX'] = macro[col]
                     elif col[1] == 'GC=F': macro_closes['GOLD'] = macro[col]
    except: pass
    
    if macro_closes.empty or 'BTC' not in macro_closes.columns:
        print("Macro data missing, skipping correlation check.")
        corr_check = False
    else:
        corr_check = True
        roll_corr_spx = macro_closes['BTC'].rolling(90).corr(macro_closes['SPX'])
    
    # --- ANALYSIS ---
    # We want to see if "Narrow Breadth" (AD Line dropping) happened while BTC rose
    # Divergence Check
    
    results = []
    
    # Sample every 30 days to avoid spam
    dates = btc.index[::30]
    
    print("\n=== HISTORICAL SNAPSHOTS (REGIME CHECK) ===")
    print(f"{'Date':<12} | {'BTC Price':<10} | {'Breadth Trend':<20} | {'Corr SPX':<10} | {'Regime'}")
    print("-" * 80)
    
    for d in dates:
        if d not in ad_line.index or (corr_check and d not in roll_corr_spx.index): continue
        
        # Breadth Trend (Slope of last 30d)
        # Find index loc
        idx = ad_line.index.get_loc(d)
        if idx < 30: continue
        
        ad_recent = ad_line.iloc[idx-30:idx]
        b_trend = ad_recent.diff().sum() # Net change over 30d
        
        b_status = "Expanding" if b_trend > 20 else "NARROW/WEAK" if b_trend < -20 else "Neutral"
        
        # Corr
        c_spx = roll_corr_spx.loc[d] if corr_check else 0
        
        # Price
        p = btc.loc[d]
        
        regime = "Normal"
        if b_status == "NARROW/WEAK" and c_spx > 0.5:
            regime = "FRAGILE RISK-ON"
        elif b_status == "NARROW/WEAK":
            regime = "APATHY / WEAKNESS"
        elif b_status == "Expanding":
            regime = "HEALTHY"
            
        print(f"{d.strftime('%Y-%m-%d'):<12} | ${p:<9.0f} | {b_status:<20} | {c_spx:<10.2f} | {regime}")

if __name__ == "__main__":
    run_historical_verification()
