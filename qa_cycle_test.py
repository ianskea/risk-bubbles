import pandas as pd
import numpy as np
import sqlite3
import os
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

def backtest_cycle(ticker, tier_name, start_date="2021-01-01"):
    cfg = V2_CONFIG.get(tier_name, V2_CONFIG["CORE"])
    
    try:
        df, _, _ = analyze_asset(ticker)
    except Exception as e:
        return None

    df = df[df.index >= start_date].copy()
    if len(df) < 500: return None

    positions = []
    risk_col = 'risk_total'
    
    for i in range(len(df)):
        risk = df[risk_col].iloc[i]
        if risk > cfg['exit']: pos = 0.2
        elif risk > cfg['reduce']: pos = 0.5
        elif risk < 0.30: pos = cfg['boost']
        else: pos = 1.0
        positions.append(pos)

    df['position'] = positions
    df['raw_ret'] = df['Close'].pct_change()
    df['strat_ret'] = (df['position'].shift(1) * df['raw_ret']).fillna(0)
    
    # Cumulative
    df['bh_cum'] = (1 + df['raw_ret']).cumprod()
    df['strat_cum'] = (1 + df['strat_ret']).cumprod()

    # Bear Market Analysis (Max Drawdown from Peak)
    bh_peak = df['bh_cum'].cummax()
    bh_dd = (df['bh_cum'] / bh_peak) - 1
    
    strat_peak = df['strat_cum'].cummax()
    strat_dd = (df['strat_cum'] / strat_peak) - 1

    return {
        "Ticker": ticker,
        "Tier": tier_name,
        "Total_ROI_Strat": f"{df['strat_cum'].iloc[-1]:.2f}x",
        "Total_ROI_Hold": f"{df['bh_cum'].iloc[-1]:.2f}x",
        "Max_Pain_Hold": f"{bh_dd.min()*100:.1f}%",
        "Max_Pain_Strat": f"{strat_dd.min()*100:.1f}%",
        "Protection": f"{abs(bh_dd.min())*100 - abs(strat_dd.min())*100:+.1f}%"
    }

def run_test():
    print(f"\n{'='*90}")
    print(f" FULL CYCLE STRESS TEST: Jan 2021 - Jan 2026 (Bull & Bear)")
    print(f" Goal: Measure capital preservation during the 2022 collapse.")
    print(f"{'='*90}")
    
    conn = sqlite3.connect(portfolio_db.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT tier, proxy FROM assets WHERE proxy IS NOT NULL")
    asset_defs = cursor.fetchall()
    conn.close()
    
    results = []
    for tier, proxy in asset_defs:
        m = backtest_cycle(proxy, tier)
        if m: results.append(m)
        
    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    
    # Portfolio Summary ($1 in each)
    strat_sum = sum([float(x.replace('x','')) for x in res_df['Total_ROI_Strat']])
    hold_sum = sum([float(x.replace('x','')) for x in res_df['Total_ROI_Hold']])
    avg_prot = sum([float(x.replace('%','')) for x in res_df['Protection']]) / len(res_df)

    print(f"\n--- CYCLE EXECUTIVE SUMMARY ---")
    print(f"Total Portfolio Value (Strategy): ${strat_sum:.2f} ({strat_sum/len(res_df):.2f}x)")
    print(f"Total Portfolio Value (Hold):     ${hold_sum:.2f} ({hold_sum/len(res_df):.2f}x)")
    print(f"Average Protection at Bottom:      {avg_prot:+.1f}% less drawdown")
    print(f"{'='*90}\n")

if __name__ == "__main__":
    run_test()
