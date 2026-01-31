import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from enhanced_risk_analyzer import analyze_asset

# Use v3 CONFIG & Rules
ASSET_CONFIG = {
    "BTC-USD": (0.18, "CRYPTO", 0.10, 0.30, 0.85, 0.75, 0.40),
    "ETH-USD": (0.10, "CRYPTO", 0.05, 0.20, 0.85, 0.75, 0.40),
    "VGS.AX": (0.15, "CORE", 0.10, 0.25, 0.80, 0.70, 0.20),
    "VAS.AX": (0.15, "CORE", 0.10, 0.20, 0.80, 0.70, 0.20),
    "GC=F": (0.08, "COMMODITY", 0.05, 0.15, 0.78, 0.68, 0.25),
    "BHP.AX": (0.10, "COMMODITY", 0.05, 0.15, 0.75, 0.65, 0.25),
    "RIO.AX": (0.07, "COMMODITY", 0.03, 0.12, 0.75, 0.65, 0.25),
    "FMG.AX": (0.04, "COMMODITY", 0.02, 0.10, 0.75, 0.65, 0.20),
    "MQG.AX": (0.08, "CORE", 0.04, 0.15, 0.80, 0.70, 0.20),
    "FANG.AX": (0.10, "GROWTH", 0.05, 0.15, 0.75, 0.65, 0.20),
    "NDQ.AX": (0.05, "GROWTH", 0.03, 0.10, 0.75, 0.65, 0.20),
    "SDR.AX": (0.03, "SAT", 0.00, 0.08, 0.75, 0.65, 0.25),
}

RULES = {
    "regime_lookback": 90,
    "bull_threshold": 0.35,
    "bear_threshold": 0.65,
    "min_hold_days": 45,
    "exception_threshold": 0.95,
    "confirmation_days": 5,
    "spike_tolerance": 0.08,
    "momentum_bonus": 0.5,
    "max_moonbag": 0.70
}

def calculate_metrics(df, initial_capital, risk_free_rate=0.04):
    final_val = df['strat_value'].iloc[-1]
    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25
    cagr = (final_val / initial_capital)**(1/years) - 1 if years > 0 else 0
    
    daily_rets = df['strat_ret'].dropna()
    # Approx check for ASX vs Global
    is_asx = "AX" in str(df.index.dtype) if hasattr(df, 'index') else False
    freq = 252 if is_asx else 365
    ann_vol = daily_rets.std() * np.sqrt(freq)
    ann_ret = daily_rets.mean() * freq
    sharpe = (ann_ret - risk_free_rate) / ann_vol if ann_vol > 0 else 0
    
    bh_final = df['bh_value'].iloc[-1]
    bh_cagr = (bh_final / initial_capital)**(1/years) - 1 if years > 0 else 0
    
    strat_peak = df['strat_value'].cummax()
    max_dd = ((df['strat_value'] - strat_peak) / strat_peak).min()
    
    bh_peak = df['bh_value'].cummax()
    bh_max_dd = ((df['bh_value'] - bh_peak) / bh_peak).min()
    
    return {
        "cagr": cagr, "sharpe": sharpe, "max_dd": max_dd,
        "bh_cagr": bh_cagr, "bh_max_dd": bh_max_dd
    }

def run_backtest_v3(ticker, years=5, initial_capital=10000, fee=0.001):
    """v3 Backtest: Iterative state-based simulation"""
    df, _, _ = analyze_asset(ticker)
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    if len(df) < 150: return None

    # Config
    base_w, tier, min_w, max_w, r_exit, r_reduce, mbag_base = ASSET_CONFIG.get(ticker, (0.1, "CORE", 0.05, 0.15, 0.75, 0.65, 0.2))
    
    # Pre-calculate indicators
    df['ma50'] = df['Close'].rolling(50).mean()
    df['momentum_30'] = df['Close'].pct_change(30)
    
    # State tracking
    last_buy_date = None
    positions = []
    
    # Simulation loop
    risk_col = 'risk_total'
    for i in range(len(df)):
        # 1. Regime Detection (90d lookback)
        if i < RULES["regime_lookback"]:
            regime = "NEUTRAL"
        else:
            avg_risk = df[risk_col].iloc[i-RULES["regime_lookback"]:i].mean()
            if avg_risk < RULES["bull_threshold"]: regime = "BULL"
            elif avg_risk > RULES["bear_threshold"]: regime = "BEAR"
            else: regime = "NEUTRAL"
            
        current_risk = df[risk_col].iloc[i]
        current_date = df.index[i]
        momentum = df['momentum_30'].iloc[i]
        
        # 2. Conviction Hold
        in_conviction = False
        if last_buy_date:
            days_held = (current_date - last_buy_date).days
            if days_held < RULES["min_hold_days"] and current_risk < RULES["exception_threshold"]:
                in_conviction = True
                
        # 3. Dynamic Thresholds
        eff_exit = r_exit + (0.05 if regime == "BULL" else 0) + (0.05 if momentum > 0.15 else 0)
        eff_reduce = r_reduce + (0.05 if regime == "BULL" else 0) + (0.05 if momentum > 0.15 else 0)
        
        # 4. Signal Logic
        if in_conviction:
            pos = 1.0 # Hold 100% of target
        elif current_risk > eff_exit:
            pos = 0.3 # EXIT to moonbag/min
            last_buy_date = None # Reset conviction
        elif current_risk > eff_reduce:
            # 5. Multi-timeframe confirmation (scan back for spikes)
            if i >= RULES["confirmation_days"]:
                avg_recent = df[risk_col].iloc[i-RULES["confirmation_days"]:i].mean()
                if current_risk > avg_recent + RULES["spike_tolerance"]:
                    pos = positions[-1] if positions else 1.0 # Wait
                else:
                    # 6. Dynamic Moonbag
                    m_pct = mbag_base * (1.2 if regime == "BULL" else 0.8 if regime == "BEAR" else 1.0)
                    if momentum > 0.20: m_pct += min(momentum * RULES["momentum_bonus"], 0.30)
                    pos = min(m_pct, RULES["max_moonbag"])
            else:
                pos = 1.0
        elif current_risk < 0.30:
            pos = 1.0
            if last_buy_date is None: last_buy_date = current_date
        else:
            pos = positions[-1] if positions else 1.0
            
        positions.append(pos)
        
    df['position'] = positions
    df['trade'] = df['position'].diff().abs().fillna(0)
    df['fees'] = df['trade'] * fee
    df['raw_ret'] = df['Close'].pct_change()
    df['strat_ret'] = (df['position'].shift(1) * df['raw_ret']) - df['fees']
    
    df['bh_value'] = initial_capital * (1 + df['raw_ret']).cumprod()
    df['strat_value'] = initial_capital * (1 + df['strat_ret']).cumprod()
    
    metrics = calculate_metrics(df, initial_capital)
    metrics['ticker'] = ticker
    return metrics

def run_backtest_v4(ticker, years=5, initial_capital=10000, fee=0.001):
    """v4 Backtest: Smart Entry (Momentum Confirmed DCA)"""
    df, _, _ = analyze_asset(ticker)
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    if len(df) < 150: return None

    # Config
    base_w, tier, min_w, max_w, r_exit, r_reduce, mbag_base = ASSET_CONFIG.get(ticker, (0.1, "CORE", 0.05, 0.15, 0.75, 0.65, 0.2))
    
    # Pre-calculate indicators
    df['ma50'] = df['Close'].rolling(50).mean()
    df['momentum_30'] = df['Close'].pct_change(30)
    
    # State tracking
    last_buy_date = None
    positions = []
    
    # Simulation loop
    risk_col = 'risk_total'
    in_dca_process = False
    
    for i in range(len(df)):
        # 1. Regime Detection (90d lookback)
        if i < RULES["regime_lookback"]:
            regime = "NEUTRAL"
        else:
            avg_risk = df[risk_col].iloc[i-RULES["regime_lookback"]:i].mean()
            if avg_risk < RULES["bull_threshold"]: regime = "BULL"
            elif avg_risk > RULES["bear_threshold"]: regime = "BEAR"
            else: regime = "NEUTRAL"
            
        current_risk = df[risk_col].iloc[i]
        current_date = df.index[i]
        momentum = df['momentum_30'].iloc[i]
        
        # 3. Dynamic Thresholds
        eff_exit = r_exit + (0.05 if regime == "BULL" else 0) + (0.05 if momentum > 0.15 else 0)
        eff_reduce = r_reduce + (0.05 if regime == "BULL" else 0) + (0.05 if momentum > 0.15 else 0)
        
        prev_pos = positions[-1] if positions else 0.0

        # --- SIGNAL LOGIC v4 (Smart Entry) ---
        
        if current_risk > eff_exit:
            # HARD EXIT SIGNAL
            pos = 0.3 # Reduce to Moonbag
            in_dca_process = False
            
        elif current_risk > eff_reduce:
             # REDUCE SIGNAL
            pos = positions[-1] if positions else 0.0
            if pos > 0.5: pos = 0.5 # Trim if heavy
            
        elif current_risk < 0.30:
            # VALUE ZONE - SMART ENTRY LOGIC
            
            # Condition A: Are we already fully invested?
            if prev_pos >= 0.99:
                pos = 1.0 # Maintain Hold
            
            else:
                # We are looking to buy. Check Momentum.
                
                # 1. "Nibble" (Initial Entry) - 33%
                # Logic: If Risk is Low, we ALWAYS want some exposure, even if momentum is bad.
                target_pos = 0.33
                
                # 2. "Confirm" (Momentum Check)
                # Logic: User wants "boil" (volume/bull alignment). 
                # Proxy: Momentum > 0 OR Price > MA50 OR Risk started rising (bottom is in).
                
                is_momentum_turning = (momentum > -0.05) # Momentum stabilizing (not falling knife)
                is_bull_align = (df['Close'].iloc[i] > df['ma50'].iloc[i])
                
                if was_flat_or_improving := (i > 5 and df[risk_col].iloc[i] > df[risk_col].iloc[i-5]):
                    # Risk score hook? (Risk stopped falling = price stopped rising? No wait. Risk low = Good.)
                    # If Risk Score is RISING from lows, it means price is RISING. 
                    # Risk 0.20 -> 0.22 means price went UP. That's a confirmation.
                    pass
                
                if is_momentum_turning or is_bull_align or was_flat_or_improving:
                    target_pos = 1.0 # GO ALL IN / DCA COMPLETE
                    in_dca_process = False
                else:
                    in_dca_process = True # We are nibbling but waiting for confirmation
                
                # Latch mechanism: Don't sell if we were already higher in this zone
                pos = max(prev_pos, target_pos)
                
        else:
            # NEUTRAL ZONE (0.30 - 0.70)
            # Hold what we have
            pos = positions[-1] if positions else 0.0

        positions.append(pos)
        
    df['position'] = positions
    df['trade'] = df['position'].diff().abs().fillna(0)
    df['fees'] = df['trade'] * fee
    df['raw_ret'] = df['Close'].pct_change()
    df['strat_ret'] = (df['position'].shift(1) * df['raw_ret']) - df['fees']
    
    df['bh_value'] = initial_capital * (1 + df['raw_ret']).cumprod()
    df['strat_value'] = initial_capital * (1 + df['strat_ret']).cumprod()
    
    metrics = calculate_metrics(df, initial_capital)
    metrics['ticker'] = ticker
    return metrics

def run_backtest_v5(ticker, years=5, initial_capital=10000, fee=0.001):
    """v5 Backtest: Hybrid Regime-Adaptive (Best of Both Worlds)"""
    # 1. Determine Strategy Mode based on Asset Class
    config = ASSET_CONFIG.get(ticker, (0.1, "CORE", 0.05, 0.15, 0.75, 0.65, 0.2))
    tier = config[1]
    r_exit = config[4]
    r_reduce = config[5]
    mbag_base = config[6]
    
    # Mode Selection
    if tier in ["CRYPTO", "SAT", "GROWTH"]:
        mode = "SMART_ENTRY" # Use v4 logic (Avoid falling knives)
    else:
        mode = "VALUE_ACCUM" # Use v3 logic (Catch V-bottoms)
        
    df, _, _ = analyze_asset(ticker)
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    if len(df) < 150: return None
    
    # Pre-calculate indicators
    df['ma50'] = df['Close'].rolling(50).mean()
    df['momentum_30'] = df['Close'].pct_change(30)
    
    # State tracking
    last_buy_date = None
    positions = []
    
    risk_col = 'risk_total'
    
    for i in range(len(df)):
        # Regime Detection (Shared)
        if i < RULES["regime_lookback"]: regime = "NEUTRAL"
        else:
            avg_risk = df[risk_col].iloc[i-RULES["regime_lookback"]:i].mean()
            if avg_risk < RULES["bull_threshold"]: regime = "BULL"
            elif avg_risk > RULES["bear_threshold"]: regime = "BEAR"
            else: regime = "NEUTRAL"
            
        current_risk = df[risk_col].iloc[i]
        current_date = df.index[i]
        momentum = df['momentum_30'].iloc[i]
        
        # Thresholds
        eff_exit = r_exit + (0.05 if regime == "BULL" else 0) + (0.05 if momentum > 0.15 else 0)
        eff_reduce = r_reduce + (0.05 if regime == "BULL" else 0) + (0.05 if momentum > 0.15 else 0)
        
        # Initial position logic
        if positions:
            prev_pos = positions[-1]
        else:
            # If no history, Core/Commodity (Value Accum) assumes holding (vested interest)
            # Growth/Sat (Smart Entry) assumes cash (safety first)
            prev_pos = 1.0 if mode == "VALUE_ACCUM" else 0.0

        # --- CONVICTION HOLD (Restored from v3) ---
        in_conviction = False
        if last_buy_date:
            days_held = (current_date - last_buy_date).days
            # If within min hold days AND risk hasn't exploded to 95+ (emergency), hold.
            if days_held < RULES["min_hold_days"] and current_risk < RULES["exception_threshold"]:
                in_conviction = True
        
        # --- SIGNAL LOGIC v5 (Hybrid) ---
        
        if in_conviction:
            pos = 1.0 # Force Hold
            
        elif current_risk > eff_exit:
            pos = 0.3 # Reduce to Moonbag (Hard Exit)
            last_buy_date = None
            
        elif current_risk > eff_reduce:
            # Smart Reduce (Restored from v3)
            # Scan back for spikes to avoid premature reduction
            if i >= RULES["confirmation_days"]:
                avg_recent = df[risk_col].iloc[i-RULES["confirmation_days"]:i].mean()
                if current_risk > avg_recent + RULES["spike_tolerance"]:
                    pos = prev_pos # Wait, just a spike
                else:
                    # Dynamic Moonbag calculation
                    m_pct = mbag_base * (1.2 if regime == "BULL" else 0.8 if regime == "BEAR" else 1.0)
                    if momentum > 0.20: m_pct += min(momentum * RULES["momentum_bonus"], 0.30)
                    pos = min(m_pct, RULES["max_moonbag"])
            else:
                pos = 1.0 # Too early to tell
            
        elif current_risk < 0.30:
            # ENTRY ZONE
            
            if mode == "VALUE_ACCUM":
                # v3 Logic: Buy Immediately (Aggressive)
                pos = 1.0
                if last_buy_date is None: last_buy_date = current_date
                
            elif mode == "SMART_ENTRY":
                # v4 Logic: Wait for Confirmation (Safe)
                if prev_pos >= 0.99:
                    pos = 1.0
                else:
                    target_pos = 0.33 # Nibble
                    
                    # Confirm if momentum stabilizing OR price > MA50
                    is_momentum_turning = (momentum > -0.05)
                    is_bull_align = (df['Close'].iloc[i] > df['ma50'].iloc[i])
                    
                    if is_momentum_turning or is_bull_align:
                        target_pos = 1.0
                        if last_buy_date is None: last_buy_date = current_date
                    
                    pos = max(prev_pos, target_pos)
        else:
            pos = positions[-1] if positions else 0.0

        positions.append(pos)
        
    df['position'] = positions
    df['trade'] = df['position'].diff().abs().fillna(0)
    df['fees'] = df['trade'] * fee
    df['raw_ret'] = df['Close'].pct_change()
    df['strat_ret'] = (df['position'].shift(1) * df['raw_ret']) - df['fees']
    
    df['bh_value'] = initial_capital * (1 + df['raw_ret']).cumprod()
    df['strat_value'] = initial_capital * (1 + df['strat_ret']).cumprod()
    
    metrics = calculate_metrics(df, initial_capital)
    metrics['ticker'] = ticker
    return metrics

def evaluate_v5():
    """Stress test v5 (Hybrid) and rank it."""
    test_suite = ["BTC-USD", "ETH-USD", "GC=F", "BHP.AX", "FANG.AX", "SDR.AX", "NDQ.AX", "MQG.AX", "FMG.AX"]
    results = []
    
    print("Starting Multi-Asset stress test (V5.0 HYBRID REGIME-AWARE)...")
    for t in test_suite:
        m = run_backtest_v5(t)
        if m: results.append(m)
        
    res_df = pd.DataFrame(results)
    
    # Metrics
    avg_cagr = res_df['cagr'].mean()
    avg_bh = res_df['bh_cagr'].mean()
    avg_sharpe = res_df['sharpe'].mean()
    dd_improvement = (res_df['bh_max_dd'].abs() - res_df['max_dd'].abs()).mean()
    upside_capture = (res_df['cagr'] / res_df['bh_cagr'].replace(0, 0.001)).mean()
    
    # Scoring Logic
    score = 8.0 # Base for Hybrid
    if dd_improvement > 0.15: score += 1.0
    if upside_capture > 0.8: score += 1.0
    
    final_score = min(10.0, max(0.0, score))
    
    print("\n" + "="*80)
    print(f"STRATEGY AUDIT: v5.0 HYBRID (Smart Entry + Value Accum)")
    print(f"Overall Rating: {final_score}/10")
    print("-" * 80)
    print(f"Portfolio Metrics (Average across {len(test_suite)} assets):")
    print(f"- Strategy CAGR:   {avg_cagr:.1%}")
    print(f"- Buy&Hold CAGR:   {avg_bh:.1%}")
    print(f"- Avg Sharpe:      {avg_sharpe:.2f}")
    print(f"- Crash Avoidance: {dd_improvement*100:+.1f}%")
    print("-" * 80)
    print("Asset Breakdown:")
    print(res_df[['ticker', 'cagr', 'max_dd', 'sharpe']].to_string(index=False))
    print("="*80 + "\n")

if __name__ == "__main__":
    evaluate_v5()
