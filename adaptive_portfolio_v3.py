"""
Risk-Adaptive Portfolio Manager v3.0
+ Regime detection
+ Conviction hold periods  
+ Dynamic moonbag sizing
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from enhanced_risk_analyzer import analyze_asset
from enhanced_main import analyze_market_cycle

# =====================================================
# CONFIGURATION V3: REGIME-AWARE SYSTEM
# =====================================================
PORTFOLIO_AUM = 100000
MONTHLY_DCA = 3000

# Asset Universe
# Format: ticker: (weight, tier, min_w, max_w, risk_exit, risk_reduce, moonbag_base)
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
    "CASH": (0.02, "CORE", 0.00, 0.30, 1.0, 1.0, 0.0)
}

# V3: Advanced Configuration
REGIME_DETECTION = {
    "enabled": True,
    "bull_threshold": 0.35,     # Risk < 0.35 = bull accumulation
    "bear_threshold": 0.65,     # Risk > 0.65 = distribution
    "lookback_days": 90         # Regime stability window
}

CONVICTION_HOLD = {
    "enabled": True,
    "min_hold_days": 45,        # Don't sell for 45 days after BUY
    "exception_threshold": 0.95 # Unless risk hits extreme (0.95)
}

DYNAMIC_MOONBAG = {
    "enabled": True,
    "base_multiplier": 1.0,
    "momentum_bonus": 0.5,      # +50% moonbag if momentum strong
    "max_moonbag": 0.70         # Cap at 70% retention
}

MULTI_TIMEFRAME = {
    "enabled": True,
    "confirmation_days": 5,     # Risk must stay high for 5 days
    "spike_tolerance": 0.08     # Allow single-day +0.08 spike
}

# Trade tracking (in-memory for demo, use DB in production)
TRADE_HISTORY = {}

# =====================================================
# V3: REGIME DETECTION
# =====================================================

def detect_market_regime(df, lookback=90):
    """
    Determine if asset is in accumulation/distribution/transition
    Returns: ("BULL", "BEAR", "NEUTRAL", avg_risk)
    """
    if len(df) < lookback:
        return "NEUTRAL", 0.5
    
    recent_risk = df['risk_total'].iloc[-lookback:].mean()
    
    if recent_risk < REGIME_DETECTION["bull_threshold"]:
        return "BULL", recent_risk
    elif recent_risk > REGIME_DETECTION["bear_threshold"]:
        return "BEAR", recent_risk
    else:
        return "NEUTRAL", recent_risk

# =====================================================
# V3: MOMENTUM + REGIME SCORING
# =====================================================

def calculate_momentum_score(df, lookback=30):
    """30-day momentum"""
    if len(df) < lookback:
        return 0.0
    return (df['Close'].iloc[-1] / df['Close'].iloc[-lookback]) - 1

def calculate_trend_strength(df, lookback=90):
    """90-day trend consistency (% days above MA50)"""
    if len(df) < lookback:
        return 0.5
    
    recent = df.iloc[-lookback:]
    ma50 = recent['Close'].rolling(50).mean()
    above_ma = (recent['Close'] > ma50).sum() / len(recent)
    return above_ma

def get_enhanced_risk_data():
    """Fetch risk + momentum + regime for all assets"""
    print("Fetching enhanced risk metrics...")
    
    data = {}
    
    for ticker in ASSET_CONFIG.keys():
        if ticker == "CASH":
            data[ticker] = {
                "risk": 0.0,
                "momentum": 0.0,
                "regime": "NEUTRAL",
                "trend_strength": 0.5,
                "available": True
            }
            continue
        
        try:
            df, _, meta = analyze_asset(ticker)
            
            if meta.get("reason"):
                print(f"  ⚠️  {ticker}: {meta['reason']}")
                data[ticker] = {"available": False}
                continue
            
            regime, avg_risk = detect_market_regime(df)
            momentum = calculate_momentum_score(df)
            trend = calculate_trend_strength(df)
            
            data[ticker] = {
                "risk": meta['last_risk'],
                "momentum": momentum,
                "regime": regime,
                "regime_avg_risk": avg_risk,
                "trend_strength": trend,
                "available": True,
                "df": df  # Keep for history checks
            }
            
            print(f"  ✓ {ticker}: Risk={meta['last_risk']:.2f} | Regime={regime} | Momentum={momentum:+.1%}")
            
        except Exception as e:
            print(f"  ✗ {ticker}: {e}")
            data[ticker] = {"available": False}
    
    return data

# =====================================================
# V3: POSITION LOGIC WITH CONVICTION HOLD
# =====================================================

def should_hold_on_conviction(ticker, risk_score):
    """Check if we're in conviction hold period"""
    if not CONVICTION_HOLD["enabled"]:
        return False
    
    if ticker not in TRADE_HISTORY:
        return False
    
    last_buy = TRADE_HISTORY[ticker].get("last_buy_date")
    if last_buy is None:
        return False
    
    days_held = (datetime.now() - last_buy).days
    
    # Exception: Risk hits extreme (0.95+)
    if risk_score > CONVICTION_HOLD["exception_threshold"]:
        return False
    
    # Hold if within conviction period
    return days_held < CONVICTION_HOLD["min_hold_days"]

def check_multi_timeframe_confirmation(ticker, current_risk, asset_data):
    """Ensure risk signal isn't just a 1-day spike"""
    if not MULTI_TIMEFRAME["enabled"]:
        return True  # Skip check
    
    df = asset_data.get("df")
    if df is None or len(df) < MULTI_TIMEFRAME["confirmation_days"]:
        return True
    
    # Check last N days of risk
    recent_risks = df['risk_total'].iloc[-MULTI_TIMEFRAME["confirmation_days"]:]
    avg_recent = recent_risks.mean()
    
    # If current risk is a spike but average is lower, wait for confirmation
    if current_risk > avg_recent + MULTI_TIMEFRAME["spike_tolerance"]:
        print(f"    ⏸️  {ticker}: Risk spike unconfirmed, holding...")
        return False
    
    return True

def calculate_dynamic_moonbag(base_moonbag, momentum, regime):
    """Scale moonbag based on momentum strength"""
    if not DYNAMIC_MOONBAG["enabled"]:
        return base_moonbag
    
    adjusted = base_moonbag * DYNAMIC_MOONBAG["base_multiplier"]
    
    # Bonus for strong momentum
    if momentum > 0.20:  # 20%+ gain
        bonus = min(momentum * DYNAMIC_MOONBAG["momentum_bonus"], 0.30)
        adjusted += bonus
    
    # Regime adjustment
    if regime == "BULL":
        adjusted *= 1.2  # Keep more in bull markets
    elif regime == "BEAR":
        adjusted *= 0.8  # Keep less in bears
    
    return min(adjusted, DYNAMIC_MOONBAG["max_moonbag"])

# =====================================================
# V3: ADAPTIVE WEIGHTS WITH ALL ENHANCEMENTS
# =====================================================

def calculate_adaptive_weights_v3(asset_data, macro_context):
    """V3: Regime-aware, conviction-based position sizing"""
    
    results = []
    composite_risk = macro_context.get("composite_score", 0.5)
    
    # Global damper
    global_damper = 1.0
    if composite_risk > 0.70:
        global_damper = 0.6
    elif composite_risk > 0.60:
        global_damper = 0.8
    
    print(f"\n📊 Macro Composite Risk: {composite_risk:.2f}")
    print(f"   Global Risk Damper: {global_damper:.1%}\n")
    
    for ticker, (base_weight, tier, min_w, max_w, risk_exit, risk_reduce, moonbag_base) in ASSET_CONFIG.items():
        
        data = asset_data.get(ticker, {})
        
        if not data.get("available", False):
            results.append({
                "ticker": ticker,
                "action": "SKIP (No Data)",
                "normalized_weight": 0
            })
            continue
        
        risk = data["risk"]
        momentum = data["momentum"]
        regime = data["regime"]
        trend_strength = data.get("trend_strength", 0.5)
        
        # CONVICTION HOLD CHECK
        if should_hold_on_conviction(ticker, risk):
            days_left = CONVICTION_HOLD["min_hold_days"] - (datetime.now() - TRADE_HISTORY[ticker]["last_buy_date"]).days
            results.append({
                "ticker": ticker,
                "tier": tier,
                "risk_score": risk,
                "regime": regime,
                "adjusted_weight": base_weight,
                "normalized_weight": base_weight,
                "action": f"🔒 CONVICTION HOLD ({days_left}d remaining)"
            })
            continue
        
        # REGIME-BASED EXIT EXTENSION
        effective_exit = risk_exit
        effective_reduce = risk_reduce
        
        if regime == "BULL":
            effective_exit += 0.05
            effective_reduce += 0.05
        
        # MOMENTUM OVERRIDE
        if momentum > 0.15:
            effective_exit += 0.05
            effective_reduce += 0.05
        
        # MULTI-TIMEFRAME CHECK
        if risk > effective_reduce:
            confirmed = check_multi_timeframe_confirmation(ticker, risk, data)
            if not confirmed:
                results.append({
                    "ticker": ticker,
                    "tier": tier,
                    "risk_score": risk,
                    "regime": regime,
                    "adjusted_weight": base_weight,
                    "normalized_weight": base_weight,
                    "action": f"⏸️  WAIT (Risk spike unconfirmed)"
                })
                continue
        
        # POSITION SIZING
        adjusted = base_weight
        action = "HOLD"
        
        # 1. FULL EXIT
        if risk > effective_exit:
            adjusted = min_w
            action = f"🔴 EXIT (Risk {risk:.2f} > {effective_exit:.2f})"
            TRADE_HISTORY[ticker] = {"last_buy_date": None, "last_sell_date": datetime.now()}
        
        # 2. DYNAMIC MOONBAG
        elif risk > effective_reduce:
            moonbag_pct = calculate_dynamic_moonbag(moonbag_base, momentum, regime)
            adjusted = base_weight * moonbag_pct
            adjusted = max(adjusted, min_w)
            action = f"🟠 MOONBAG (Risk {risk:.2f}, Keep {moonbag_pct:.0%})"
        
        # 3. VALUE ZONE
        elif risk < 0.30:
            boost = 1.0 + ((0.30 - risk) / 0.30) * 0.5
            adjusted = min(base_weight * boost, max_w)
            action = f"🟢 OVERWEIGHT (Value {risk:.2f}, {regime})"
            if ticker not in TRADE_HISTORY or TRADE_HISTORY[ticker].get("last_buy_date") is None:
                TRADE_HISTORY[ticker] = {"last_buy_date": datetime.now()}
        
        # 4. WARNING ZONE
        elif risk > (effective_reduce - 0.10):
            taper = 0.85
            adjusted = max(base_weight * taper, min_w)
            action = f"🟡 REDUCE (Warning {risk:.2f})"
        
        # Apply damper
        if tier in ["GROWTH", "CRYPTO"] and regime != "BULL":
            adjusted *= global_damper
        
        adjusted = max(min_w, min(adjusted, max_w))
        
        results.append({
            "ticker": ticker,
            "tier": tier,
            "risk_score": risk,
            "regime": regime,
            "momentum": momentum,
            "trend_strength": trend_strength,
            "exit_threshold": effective_exit,
            "adjusted_weight": adjusted,
            "action": action
        })
    
    # Normalize
    total_weight = sum(r.get("adjusted_weight", 0) for r in results)
    if total_weight > 0:
        for r in results:
            r["normalized_weight"] = r.get("adjusted_weight", 0) / total_weight
    
    return pd.DataFrame(results)

# =====================================================
# MAIN V3
# =====================================================

def run_adaptive_portfolio_v3():
    print("="*70)
    print("RISK-ADAPTIVE PORTFOLIO V3.0 - REGIME + CONVICTION + DYNAMIC MOONBAG")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("="*70)
    
    # 1. Macro
    cycle_report, macro_context = analyze_market_cycle()
    print(cycle_report)
    
    # 2. Enhanced Risk Data
    asset_data = get_enhanced_risk_data()
    
    # 3. V3 Weights
    weights_df = calculate_adaptive_weights_v3(asset_data, macro_context)
    
    # 4. Display
    print("\n" + "="*70)
    print("ADAPTIVE ALLOCATION V3")
    print("="*70)
    display_cols = ['ticker', 'tier', 'risk_score', 'regime', 'momentum', 
                    'normalized_weight', 'action']
    
    display_df = weights_df[display_cols].copy()
    for col in ['risk_score', 'momentum', 'normalized_weight']:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) and isinstance(x, (int, float)) else x)
    
    print(display_df.to_string(index=False))
    
    # 5. Risk Profile
    if 'tier' in weights_df.columns and 'normalized_weight' in weights_df.columns:
        crypto_weight = weights_df[weights_df['tier']=='CRYPTO']['normalized_weight'].sum()
        core_weight = weights_df[weights_df['tier']=='CORE']['normalized_weight'].sum()
        
        print("\n" + "="*70)
        print("PORTFOLIO RISK PROFILE")
        print("="*70)
        print(f"Crypto Exposure:   {crypto_weight:.1%}")
        print(f"Core Exposure:     {core_weight:.1%}")
        print(f"Macro Risk Score:  {macro_context.get('composite_score', 0):.2f}")
    
    # 6. Feature Status
    print("\n" + "="*70)
    print("V3 FEATURES STATUS")
    print("="*70)
    print(f"Regime Detection:     {'✅ Enabled' if REGIME_DETECTION['enabled'] else '❌ Disabled'}")
    print(f"Conviction Hold:      {'✅ Enabled' if CONVICTION_HOLD['enabled'] else '❌ Disabled'} ({CONVICTION_HOLD['min_hold_days']}d)")
    print(f"Dynamic Moonbag:      {'✅ Enabled' if DYNAMIC_MOONBAG['enabled'] else '❌ Disabled'}")
    print(f"Multi-Timeframe:      {'✅ Enabled' if MULTI_TIMEFRAME['enabled'] else '❌ Disabled'} ({MULTI_TIMEFRAME['confirmation_days']}d)")
    
    return weights_df

if __name__ == "__main__":
    run_adaptive_portfolio_v3()
