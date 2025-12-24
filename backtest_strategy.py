import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset

# Use v2 CONFIG for high-fidelity testing
ASSET_CONFIG = {
    "BTC-USD": (0.18, "CRYPTO", 0.10, 0.30, 0.85, 0.75, 0.40),
    "ETH-USD": (0.10, "CRYPTO", 0.05, 0.20, 0.85, 0.75, 0.40),
    "VGS.AX": (0.15, "CORE", 0.10, 0.25, 0.80, 0.70, 0.20),
    "VAS.AX": (0.15, "CORE", 0.10, 0.20, 0.80, 0.70, 0.20),
    "GC=F": (0.08, "COMMODITY", 0.05, 0.15, 0.78, 0.68, 0.25),
    "BHP.AX": (0.10, "COMMODITY", 0.05, 0.15, 0.75, 0.65, 0.25),
    "RIO.AX": (0.07, "COMMODITY", 0.03, 0.12, 0.75, 0.65, 0.25),
    "FANG.AX": (0.10, "GROWTH", 0.05, 0.15, 0.75, 0.65, 0.20),
    "NDQ.AX": (0.05, "GROWTH", 0.03, 0.10, 0.75, 0.65, 0.20),
}

MOMENTUM_OVERRIDE = {
    "enabled": True,
    "lookback_days": 30,
    "threshold": 0.15,
    "risk_extension": 0.05
}

def calculate_metrics(df, initial_capital, risk_free_rate=0.04):
    """Calculates CAGR, Sharpe Ratio, and Drawdown stats."""
    final_val = df['strat_value'].iloc[-1]
    
    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25
    cagr = (final_val / initial_capital)**(1/years) - 1 if years > 0 else 0
    
    daily_rets = df['strat_ret'].dropna()
    is_asx = "AX" in str(df.index.name) or (hasattr(df.index, 'dtype') and "AX" in str(df.index.dtype))
    # Approximation for data frequency
    freq = 252 if is_asx else 365
    ann_vol = daily_rets.std() * np.sqrt(freq)
    ann_ret = daily_rets.mean() * freq
    sharpe = (ann_ret - risk_free_rate) / ann_vol if ann_vol > 0 else 0
    
    bh_final = df['bh_value'].iloc[-1]
    bh_cagr = (bh_final / initial_capital)**(1/years) - 1 if years > 0 else 0
    
    # Max Drawdown
    strat_peak = df['strat_value'].cummax()
    strat_dd = (df['strat_value'] - strat_peak) / strat_peak
    max_dd = strat_dd.min()
    
    bh_peak = df['bh_value'].cummax()
    bh_dd = (df['bh_value'] - bh_peak) / bh_peak
    bh_max_dd = bh_dd.min()
    
    return {
        "final_value": final_val,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "bh_cagr": bh_cagr,
        "bh_max_dd": bh_max_dd
    }

def run_backtest(ticker, years=5, initial_capital=10000, fee=0.001):
    """
    Backtests v2.0 Logic:
    - Asymmetric Thresholds per ASSET_CONFIG
    - Momentum Override extensions
    """
    df, _, _ = analyze_asset(ticker)
    
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    
    if df.empty or len(df) < 100:
        return None

    # Get v2 config for this ticker
    # Format: (base_weight, tier, min_w, max_w, risk_exit, risk_reduce, moonbag)
    config = ASSET_CONFIG.get(ticker, (0.1, "CORE", 0.05, 0.15, 0.75, 0.65, 0.3))
    base_w, tier, min_w, max_w, r_exit, r_reduce, mbag = config
    
    # 1. Momentum Calculation
    df['momentum'] = df['Close'].pct_change(30)
    
    # 2. Dynamic Thresholds
    df['effective_exit'] = r_exit
    df['effective_reduce'] = r_reduce
    
    if MOMENTUM_OVERRIDE["enabled"]:
        mask = df['momentum'] > MOMENTUM_OVERRIDE["threshold"]
        df.loc[mask, 'effective_exit'] += MOMENTUM_OVERRIDE["risk_extension"]
        df.loc[mask, 'effective_reduce'] += MOMENTUM_OVERRIDE["risk_extension"]
        
    # 3. Signal Logic
    df['target_pos'] = 1.0 
    
    # Exit Zone (Use min_w proxy)
    df.loc[df['risk_total'] > df['effective_exit'], 'target_pos'] = 0.3 # Scale to 30% or config moonbag
    # Reduce Zone
    mask_reduce = (df['risk_total'] > df['effective_reduce']) & (df['risk_total'] <= df['effective_exit'])
    df.loc[mask_reduce, 'target_pos'] = mbag
    
    # Ffill assumes we hold previous state
    df['position'] = df['target_pos'].ffill().fillna(1.0)
    
    # 3. Transaction Costs & Returns
    df['trade'] = df['position'].diff().abs().fillna(0)
    df['fees'] = df['trade'] * fee
    df['raw_ret'] = df['Close'].pct_change()
    df['strat_ret'] = (df['position'].shift(1) * df['raw_ret']) - df['fees']
    
    # 4. Values
    df['bh_value'] = initial_capital * (1 + df['raw_ret']).cumprod()
    df['strat_value'] = initial_capital * (1 + df['strat_ret']).cumprod()
    
    return calculate_metrics(df, initial_capital)

def evaluate_and_rank_v2():
    """Runs stress tests with v2 rules and re-ranks."""
    test_suite = ["BTC-USD", "ETH-USD", "GC=F", "BHP.AX", "MQG.AX", "FANG.AX"]
    results = []
    
    print(f"Starting Multi-Asset stress test (V2.0 ASYMMETRIC)...")
    for t in test_suite:
        m = run_backtest(t)
        if m:
            m['ticker'] = t
            results.append(m)
        
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print(f"{'ASSET':<10} | {'STRAT CAGR':<10} | {'B&H CAGR':<10} | {'STRAT DD':<10} | {'B&H DD':<10} | {'SHARPE'}")
    print("-" * 80)
    
    for _, row in res_df.iterrows():
        print(f"{row['ticker']:<10} | {row['cagr']*100:8.1f}% | {row['bh_cagr']*100:8.1f}% | {row['max_dd']*100:8.1f}% | {row['bh_max_dd']*100:8.1f}% | {row['sharpe']:4.2f}")
    
    # EVALUATION
    dd_improvement = (abs(res_df['bh_max_dd']) - abs(res_df['max_dd'])).mean()
    # Handle potentially zero bh_cagr if testing weird assets, though not here.
    upside_capture = (res_df['cagr'] / res_df['bh_cagr'].replace(0, 0.001)).mean() 
    
    score = 6 
    if dd_improvement > 0.15: score += 2 
    if upside_capture > 0.80: score += 2 
    
    print("\n" + "="*80)
    print(f"LOGIC AUDIT v2.0: ASYMMETRIC BANDS + MOMENTUM")
    print(f"Overall Rank: {min(10, score)}/10")
    print("-" * 80)
    print(f"Improvements vs v1.0:")
    print(f"- Upside Capture:  {upside_capture:.1%}")
    print(f"- Crash Avoidance: {'RETAINED' if dd_improvement > 0.1 else 'COMPROMISED'}")
    print(f"- Average Sharpe:  {res_df['sharpe'].mean():.2f}")
    print("="*80 + "\n")

if __name__ == "__main__":
    evaluate_and_rank_v2()
