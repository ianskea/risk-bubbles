import pandas as pd
import numpy as np
import os
import sqlite3
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset
import portfolio_db

def backtest_buy_timing(ticker, tier_name, years=5):
    try:
        df, _, _ = analyze_asset(ticker)
    except Exception as e:
        return None

    # Filter for timeframe
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    if len(df) < 150: return None

    risk_col = 'risk_total'
    
    # 1. Blind Buy $1 (Start of Window)
    blind_entry_price = df['Close'].iloc[0]
    blind_final_value = (1.0 / blind_entry_price) * df['Close'].iloc[-1]
    
    # 2. Value Buy $1 (Only when Risk < 0.30)
    low_risk_mask = df[risk_col] < 0.30
    low_risk_days = df[low_risk_mask]
    
    if low_risk_days.empty:
        # If no low risk days, we don't buy anything (Value Entry = 0 or fallback)
        value_final_value = 0
        avg_buy_price = 0
    else:
        # We spend $1 total, divided equally amongst all "Value" days
        investment_per_day = 1.0 / len(low_risk_days)
        total_units = (investment_per_day / low_risk_days['Close']).sum()
        value_final_value = total_units * df['Close'].iloc[-1]
        avg_buy_price = low_risk_days['Close'].mean()

    return {
        "Ticker": ticker,
        "Tier": tier_name,
        "Blind_ROI": f"{blind_final_value:.2f}x",
        "Value_ROI": f"{value_final_value:.2f}x",
        "Improvement": f"{(value_final_value - blind_final_value):+.2f}x",
        "Value_Days": len(low_risk_days)
    }

def run_compare():
    print(f"\n{'='*80}")
    print(f" STRATEGY: 'THE PATIENT BUYER' (Buy <0.30 Risk, Never Sell)")
    print(f" Goal: Compare $1 'Blind Entry' vs $1 'Value-Timed Entry'")
    print(f"{'='*80}")
    
    conn = sqlite3.connect(portfolio_db.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT tier, proxy FROM assets WHERE proxy IS NOT NULL")
    asset_defs = cursor.fetchall()
    conn.close()
    
    results = []
    for tier, proxy in asset_defs:
        m = backtest_buy_timing(proxy, tier)
        if m: results.append(m)
        
    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    
    # Portfolio Level (Equal weighted $1 in each)
    total_blind = sum([float(x.replace('x','')) for x in res_df['Blind_ROI']])
    total_value = sum([float(x.replace('x','')) for x in res_df['Value_ROI']])
    
    print(f"\n--- TOTAL PORTFOLIO PERFORMANCE ---")
    print(f"Total Invested: ${len(res_df):.2f}")
    print(f"Final Value (Blind Entry): ${total_blind:.2f} ({total_blind/len(res_df):.2f}x)")
    print(f"Final Value (Value Entry): ${total_value:.2f} ({total_value/len(res_df):.2f}x)")
    print(f"Alpha from Timing:         {((total_value/total_blind)-1)*100:+.1f}%")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    run_compare()
