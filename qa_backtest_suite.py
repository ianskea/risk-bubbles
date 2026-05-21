import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
from enhanced_risk_analyzer import analyze_asset
from sector_config import SECTOR_INTELLIGENCE

def backtest_v2_logic(ticker, sector_name, exit_threshold, years=5, fee=0.001):
    try:
        df, _, _ = analyze_asset(ticker)
    except Exception as e:
        print(f"  Error loading {ticker}: {e}")
        return None

    # Filter for timeframe
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    if len(df) < 150: return None

    # Simulation Logic (v2.1 with Momentum Stop)
    positions = []
    risk_col = 'risk_total'
    
    for i in range(len(df)):
        risk = df[risk_col].iloc[i]
        price = df['Close'].iloc[i]
        sma_20 = df['sma_20d'].iloc[i]
        
        # v2.1 Logic:
        # If risk > exit_threshold:
        #    If price > sma_20 -> Hold (Riding the bubble) -> 1.0
        #    If price < sma_20 -> Trend Broken, Cut to Moonbag -> 0.2
        # If risk < 0.30 -> Boost -> 1.4
        # Else -> Base -> 1.0
        
        if risk > exit_threshold:
            if price > sma_20:
                pos = 1.0 # Riding Bubble
            else:
                pos = 0.2 # Trend Broken
        elif risk < 0.30:
            pos = 1.4
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
        "Sector": sector_name,
        "v2_Return": f"{final_strat:.2f}x",
        "B&H_Return": f"{final_bh:.2f}x",
        "Alpha": f"{alpha:+.2f}x",
        "v2_DD": f"{max_dd*100:.1f}%",
        "B&H_DD": f"{bh_max_dd*100:.1f}%",
        "Protection": f"{(abs(bh_max_dd) - abs(max_dd))*100:+.1f}%"
    }

def run_suite():
    print(f"\n{'='*80}")
    print(f" INSTITUTIONAL QA & MULTI-MARKET BACKTEST (v2.1 Momentum Stop)")
    print(f" Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*80}")
    
    results = []
    
    for sector_name, sector_data in SECTOR_INTELLIGENCE.items():
        exit_t = sector_data.get("danger_zone_threshold", 0.8)
        
        for name, ticker in sector_data["assets"].items():
            print(f"Testing {ticker} ({sector_name})...")
            m = backtest_v2_logic(ticker, sector_name, exit_t)
            if m: results.append(m)
        
    res_df = pd.DataFrame(results)
    print("\n--- DETAILED QA REPORT ---")
    print(res_df.to_string(index=False))
    
    # Summary Insights
    if results:
        alphas = [float(x.replace('x', '')) for x in res_df['Alpha']]
        protections = [float(x.replace('%', '')) for x in res_df['Protection']]
        
        print(f"\n--- EXECUTIVE SUMMARY ---")
        print(f"Assets Validated:   {len(results)}")
        print(f"Avg Alpha vs Hold:  {sum(alphas)/len(alphas):+.2f}x")
        print(f"Avg DD Protection:  {sum(protections)/len(protections):+.1f}% improved")
        print(f"Success Rate:       {len([a for a in alphas if a > 0])/len(alphas)*100:.0f}% outperformance")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    run_suite()
