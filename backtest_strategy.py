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
    "max_moonbag": 0.70,
    "smart_tiers": ["CRYPTO", "GROWTH", "SAT"],
    "confirmation_candles": 3,
    "momentum_threshold": -0.05,
    "initial_nibble": 0.33,
    "cgt_discount_days": 365
}

DEFAULT_STRATEGY = "v5"

def calculate_metrics(df, initial_capital, risk_free_rate=0.04, ticker=None):
    final_val = df['strat_value'].iloc[-1]
    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25
    cagr = (final_val / initial_capital)**(1/years) - 1 if years > 0 else 0

    daily_rets = df['strat_ret'].dropna()
    is_asx = bool(ticker and str(ticker).endswith(".AX"))
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

def filter_backtest_window(df, years):
    """Return the requested backtest window, or an empty frame when analysis data is unavailable."""
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame()

    start_date = pd.Timestamp.now(tz=df.index.tz) - pd.DateOffset(years=years)
    return df[df.index >= start_date].copy()

def run_backtest_v3(ticker, years=5, initial_capital=10000, fee=0.001):
    """v3 Backtest: Iterative state-based simulation"""
    df, _, _ = analyze_asset(ticker)
    df = filter_backtest_window(df, years)
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

    metrics = calculate_metrics(df, initial_capital, ticker=ticker)
    metrics['ticker'] = ticker
    return metrics

def run_backtest_v4(ticker, years=5, initial_capital=10000, fee=0.001):
    """v4 Backtest: Smart Entry (Momentum Confirmed DCA)"""
    df, _, _ = analyze_asset(ticker)
    df = filter_backtest_window(df, years)
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

    metrics = calculate_metrics(df, initial_capital, ticker=ticker)
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
    df = filter_backtest_window(df, years)
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

    metrics = calculate_metrics(df, initial_capital, ticker=ticker)
    metrics['ticker'] = ticker
    return metrics

def run_backtest_v6(
    ticker,
    years=5,
    initial_capital=10000,
    fee=0.001,
    tax_drag_optimization=True,
    cgt_discount_days=RULES["cgt_discount_days"],
):
    """Experimental defensive variant with VWAP/CMF entry filters and tax-aware trim deferral."""
    df, _, _ = analyze_asset(ticker)
    df = filter_backtest_window(df, years)
    if len(df) < 150: return None

    # Config
    base_w, tier, min_w, max_w, r_exit, r_reduce, mbag_base = ASSET_CONFIG.get(ticker, (0.1, "CORE", 0.05, 0.15, 0.75, 0.65, 0.2))

    # Mode Selection (Production logic)
    mode = "SMART_ENTRY" if tier in RULES["smart_tiers"] else "VALUE_ACCUM"

    # Pre-calculate indicators (Institutional Upgrades: VWAP + CMF)
    df['ma50'] = df['Close'].rolling(50).mean()
    df['momentum_30'] = df['Close'].pct_change(30)

    has_volume = 'Volume' in df.columns and df['Volume'].notna().any() and 'High' in df.columns
    if has_volume:
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        tp_v = tp * df['Volume']
        df['vwap_20'] = tp_v.rolling(20).sum() / df['Volume'].rolling(20).sum()

        # 20-Day Chaikin Money Flow (CMF)
        mfm = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low']).replace(0, np.nan)
        mfv = mfm * df['Volume']
        df['cmf_20'] = mfv.rolling(20).sum() / df['Volume'].rolling(20).sum()
        df['cmf_20'] = df['cmf_20'].fillna(0.0)
    else:
        df['vwap_20'] = df['Close'].rolling(20).mean()
        df['cmf_20'] = 0.1 # Default positive for non-volume assets

    # Helper for confirmation
    def is_confirmed(idx, data):
        if idx < 20: return True # Warm up indicators

        # 1. Momentum Check (not in a severe downward cascade)
        if data['momentum_30'].iloc[idx] < RULES["momentum_threshold"]:
            return False

        # 2. VWAP Hook: Price must be above 20-day rolling VWAP
        above_vwap = data['Close'].iloc[idx] > data['vwap_20'].iloc[idx]

        # 3. Money Flow Confirmation: CMF is positive (buying accumulation)
        flow_ok = data['cmf_20'].iloc[idx] > 0

        # 4. 3-Candle Stability (higher lows or consecutive green)
        higher_low = data['Low'].iloc[idx] > data['Low'].iloc[idx-1]
        consecutive_green = (data['Close'].iloc[idx] > data['Close'].iloc[idx-1]) and (data['Open'].iloc[idx] < data['Close'].iloc[idx])
        stability_ok = higher_low or consecutive_green

        # Combined Signal: Needs stability, positive accumulation flow, and a VWAP hook.
        if stability_ok and flow_ok and above_vwap:
            return True

        return False

    # State tracking
    last_buy_date = None
    avg_entry_date = None
    avg_entry_price = None
    positions = []
    tax_deferred_trims = 0

    risk_col = 'risk_total'

    def should_defer_taxable_trim(target_pos, prev_pos, current_date, current_price, hard_exit):
        if (
            not tax_drag_optimization
            or hard_exit
            or target_pos >= prev_pos
            or avg_entry_date is None
            or avg_entry_price is None
            or current_price <= avg_entry_price
        ):
            return False

        holding_days = (current_date - avg_entry_date).days
        return holding_days < cgt_discount_days

    for i in range(len(df)):
        # Regime Detection
        if i < RULES["regime_lookback"]: regime = "NEUTRAL"
        else:
            avg_risk = df[risk_col].iloc[i-RULES["regime_lookback"]:i].mean()
            if avg_risk < RULES["bull_threshold"]: regime = "BULL"
            elif avg_risk > RULES["bear_threshold"]: regime = "BEAR"
            else: regime = "NEUTRAL"

        current_risk = df[risk_col].iloc[i]
        current_date = df.index[i]
        current_price = df['Close'].iloc[i]
        momentum = df['momentum_30'].iloc[i]

        # Thresholds
        eff_exit = r_exit + (0.05 if regime == "BULL" else 0) + (0.05 if momentum > 0.15 else 0)
        eff_reduce = r_reduce + (0.05 if regime == "BULL" else 0) + (0.05 if momentum > 0.15 else 0)

        prev_pos = positions[-1] if positions else (1.0 if mode == "VALUE_ACCUM" else 0.0)

        # Signal Logic
        in_conviction = False
        if last_buy_date:
            days_held = (current_date - last_buy_date).days
            if days_held < RULES["min_hold_days"] and current_risk < RULES["exception_threshold"]:
                in_conviction = True

        hard_exit_signal = False
        if in_conviction:
            pos = 1.0
        elif current_risk > eff_exit:
            pos = 0.3
            last_buy_date = None
            hard_exit_signal = True
        elif current_risk > eff_reduce:
            if i >= RULES["confirmation_days"]:
                avg_recent = df[risk_col].iloc[i-RULES["confirmation_days"]:i].mean()
                if current_risk > avg_recent + RULES["spike_tolerance"]:
                    pos = prev_pos
                else:
                    m_pct = mbag_base * (1.2 if regime == "BULL" else 0.8 if regime == "BEAR" else 1.0)
                    if momentum > 0.20: m_pct += min(momentum * RULES["momentum_bonus"], 0.30)
                    pos = min(m_pct, RULES["max_moonbag"])
            else:
                pos = 1.0
        elif current_risk < 0.30:
            if mode == "SMART_ENTRY":
                is_vested = last_buy_date is not None
                if is_vested:
                    pos = 1.0
                else:
                    if is_confirmed(i, df):
                        pos = 1.0
                        last_buy_date = current_date
                    else:
                        pos = RULES["initial_nibble"]
            else:
                pos = 1.0
                if last_buy_date is None: last_buy_date = current_date
        else:
            pos = prev_pos

        if should_defer_taxable_trim(pos, prev_pos, current_date, current_price, hard_exit_signal):
            pos = prev_pos
            tax_deferred_trims += 1

        if not positions and pos > 0 and avg_entry_date is None:
            avg_entry_date = current_date
            avg_entry_price = current_price
        elif pos > prev_pos:
            added = pos - prev_pos
            if avg_entry_date is None or avg_entry_price is None or prev_pos <= 0:
                avg_entry_date = current_date
                avg_entry_price = current_price
            else:
                avg_entry_price = ((avg_entry_price * prev_pos) + (current_price * added)) / pos
                previous_weight = prev_pos / pos
                added_weight = added / pos
                avg_timestamp = (
                    avg_entry_date.timestamp() * previous_weight
                    + current_date.timestamp() * added_weight
                )
                avg_entry_date = pd.Timestamp(datetime.fromtimestamp(avg_timestamp))
        elif pos <= 0:
            avg_entry_date = None
            avg_entry_price = None

        positions.append(pos)

    df['position'] = positions
    df['trade'] = df['position'].diff().abs().fillna(0)
    df['fees'] = df['trade'] * fee
    df['raw_ret'] = df['Close'].pct_change()
    df['strat_ret'] = (df['position'].shift(1) * df['raw_ret']) - df['fees']

    df['bh_value'] = initial_capital * (1 + df['raw_ret']).cumprod()
    df['strat_value'] = initial_capital * (1 + df['strat_ret']).cumprod()

    metrics = calculate_metrics(df, initial_capital, ticker=ticker)
    metrics['ticker'] = ticker
    metrics['tax_deferred_trims'] = tax_deferred_trims
    return metrics

def run_backtest_default(ticker, years=5, initial_capital=10000, fee=0.001):
    """Default production strategy. Keep v5 unless a newer strategy proves better."""
    return run_backtest_v5(ticker, years=years, initial_capital=initial_capital, fee=fee)


def evaluate_v5():
    """Rigorous comparison of v3 (Blind) vs default v5 hybrid strategy."""
    test_suite = ["BTC-USD", "ETH-USD", "GC=F", "BHP.AX", "FANG.AX", "SDR.AX", "NDQ.AX", "MQG.AX", "FMG.AX"]
    results_v3 = []
    results_v5 = []

    print("\n" + "="*80)
    print("RIGOROUS BACKTEST: v3 (Blind) vs v5 (Default Hybrid)")
    print("="*80)

    for t in test_suite:
        m3 = run_backtest_v3(t)
        m5 = run_backtest_default(t)
        if m3: results_v3.append(m3)
        if m5: results_v5.append(m5)

    df3 = pd.DataFrame(results_v3)
    df5 = pd.DataFrame(results_v5)
    if df3.empty or df5.empty:
        print("\nNo comparable backtest results were produced. Check data/network availability.")
        return
    comparison = df3.merge(df5, on="ticker", suffixes=("_v3", "_v5"))
    if comparison.empty:
        print("\nNo overlapping v3/v5 ticker results were produced.")
        return

    # Comparison Table
    print(f"\n{'Ticker':<10} | {'v3 CAGR':<10} | {'v5 CAGR':<10} | {'v3 MaxDD':<10} | {'v5 MaxDD':<10}")
    print("-" * 65)
    for _, row in comparison.iterrows():
        t = row['ticker']
        c3 = row['cagr_v3']
        c5 = row['cagr_v5']
        d3 = row['max_dd_v3']
        d5 = row['max_dd_v5']
        print(f"{t:<10} | {c3:7.1%} | {c5:7.1%} | {d3:8.1%} | {d5:8.1%}")

    # Portfolio Aggregates
    print("\n" + "="*80)
    print("PORTFOLIO PERFORMANCE SUMMARY")
    print("-" * 80)
    print(f"Avg CAGR (v3 Blind):   {comparison['cagr_v3'].mean():.1%}")
    print(f"Avg CAGR (v5 Default): {comparison['cagr_v5'].mean():.1%}")
    print(f"Avg MaxDD (v3 Blind):  {comparison['max_dd_v3'].mean():.1%}")
    print(f"Avg MaxDD (v5 Default): {comparison['max_dd_v5'].mean():.1%}")
    print(f"Avg Sharpe (v3 Blind): {comparison['sharpe_v3'].mean():.2f}")
    print(f"Avg Sharpe (v5 Default): {comparison['sharpe_v5'].mean():.2f}")

    improvement = abs(comparison['max_dd_v3'].mean()) - abs(comparison['max_dd_v5'].mean())
    print(f"\nCrash Protection Added: {improvement:+.1%}")
    print("="*80 + "\n")


def evaluate_v6():
    """Experimental comparison retained for defensive v6 research."""
    from compare_v5_v6 import main as compare_main
    compare_main()

if __name__ == "__main__":
    evaluate_v5()
