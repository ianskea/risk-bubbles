import pandas as pd
import numpy as np
import os
import sqlite3
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset
import portfolio_db

# CONFIG: v2.0 Thresholds
V2_CONFIG = {
    "CRYPTO":    {"exit": 0.85, "reduce": 0.75, "boost": 1.4},
    "CORE":      {"exit": 0.80, "reduce": 0.70, "boost": 1.4},
    "COMMODITY": {"exit": 0.78, "reduce": 0.68, "boost": 1.2},
    "GROWTH":    {"exit": 0.75, "reduce": 0.65, "boost": 1.2},
    "SAT":       {"exit": 0.75, "reduce": 0.65, "boost": 1.2},
    "AGGR":      {"exit": 0.85, "reduce": 0.75, "boost": 1.4},
}

def backtest_v2_logic(ticker, tier_name, years=5, fee=0.001):
    cfg = V2_CONFIG.get(tier_name, V2_CONFIG["CORE"])
    
    try:
        print(f"Testing {ticker} ({tier_name})...")
        df, _, _ = analyze_asset(ticker)
    except Exception as e:
        print(f"  Error loading {ticker}: {e}")
        return None

    # Filter for timeframe
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    if len(df) < 150: 
        print(f"  Insufficient data for {ticker}")
        return None

    # Simulation Logic (Simplified v2.0)
    positions = []
    risk_col = 'risk_total'
    
    for i in range(len(df)):
        risk = df[risk_col].iloc[i]
        
        if risk > cfg['exit']:
            pos = 0.2
        elif risk > cfg['reduce']:
            pos = 0.5
        elif risk < 0.30:
            pos = min(1.5, cfg['boost'])
        else:
            pos = 1.0
            
        positions.append(pos)

    df['position'] = positions
    df['trade'] = df['position'].diff().abs().fillna(0)
    df['raw_ret'] = df['Close'].pct_change()
    df['strat_ret'] = (df['position'].shift(1) * df['raw_ret']) - (df['trade'] * fee)
    
    # Cumulative returns
    df['bh_cum'] = (1 + df['raw_ret']).cumprod()
    df['strat_cum'] = (1 + df['strat_ret']).cumprod()
    
    # Metrics
    final_strat = df['strat_cum'].iloc[-1]
    final_bh = df['bh_cum'].iloc[-1]
    alpha = final_strat - final_bh
    
    peak = df['strat_cum'].cummax()
    max_dd = ((df['strat_cum'] - peak) / peak).min()
    
    bh_peak = df['bh_cum'].cummax()
    bh_max_dd = ((df['bh_cum'] - bh_peak) / bh_peak).min()
    
    return {
        "Ticker": ticker,
        "Tier": tier_name,
        "v2_Return": f"{final_strat:.2f}x",
        "B&H_Return": f"{final_bh:.2f}x",
        "Alpha": f"{alpha:+.2f}x",
        "v2_DD": f"{max_dd*100:.1f}%",
        "B&H_DD": f"{bh_max_dd*100:.1f}%",
        "Protection": f"{(abs(bh_max_dd) - abs(max_dd))*100:+.1f}%"
    }

def run_portfolio_backtest():
    print(f"\n{'='*80}")
    print(f" CURRENT PORTFOLIO BACKTEST (v2.0 Logic)")
    print(f" Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*80}")
    
    # Get all tickers/proxies from DB
    conn = sqlite3.connect(portfolio_db.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT tier, proxy FROM assets WHERE proxy IS NOT NULL")
    asset_defs = cursor.fetchall()
    conn.close()
    
    results = []
    for tier, proxy in asset_defs:
        m = backtest_v2_logic(proxy, tier)
        if m: results.append(m)
        
    if not results:
        print("No valid proxies found for backtesting.")
        return

    res_df = pd.DataFrame(results)
    print("\n--- PORTFOLIO QUALITY ASSURANCE REPORT ---")
    print(res_df.to_string(index=False))
    
    # Summary Insights
    alphas = [float(x.replace('x', '')) for x in res_df['Alpha']]
    protections = [float(x.replace('%', '')) for x in res_df['Protection']]
    
    print(f"\n--- EXECUTIVE SUMMARY ---")
    print(f"Assets Validated:   {len(results)}")
    print(f"Avg Alpha vs Hold:  {sum(alphas)/len(alphas):+.2f}x")
    print(f"Avg DD Protection:  {sum(protections)/len(protections):+.1f}% improved")
    print(f"Success Rate:       {len([a for a in alphas if a > 0])/len(alphas)*100:.0f}% outperformance")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    run_portfolio_backtest()
