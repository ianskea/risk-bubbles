"""
Risk-Adaptive Portfolio Manager v2.0
Asymmetric risk bands + momentum override for better upside capture
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset
from enhanced_main import analyze_market_cycle

# =====================================================
# CONFIGURATION V2: ASSET-SPECIFIC RISK TOLERANCE
# =====================================================
PORTFOLIO_AUM = 100000
MONTHLY_DCA = 3000

# Asset Universe with ASYMMETRIC risk bands
# Format: ticker: (base_weight, tier, min_w, max_w, risk_exit, risk_reduce, moonbag)
ASSET_CONFIG = {
    # Crypto - High volatility assets need WIDER bands
    "BTC-USD": (0.18, "CRYPTO", 0.10, 0.30, 0.85, 0.75, 0.40),
    "ETH-USD": (0.10, "CRYPTO", 0.05, 0.20, 0.85, 0.75, 0.40),
    
    # Broad Market - Medium bands
    "VGS.AX": (0.15, "CORE", 0.10, 0.25, 0.80, 0.70, 0.20),
    "VAS.AX": (0.15, "CORE", 0.10, 0.20, 0.80, 0.70, 0.20),
    
    # Commodities - Medium-tight bands
    "GC=F": (0.08, "COMMODITY", 0.05, 0.15, 0.78, 0.68, 0.25),
    "BHP.AX": (0.10, "COMMODITY", 0.05, 0.15, 0.75, 0.65, 0.25),
    "RIO.AX": (0.07, "COMMODITY", 0.03, 0.12, 0.75, 0.65, 0.25),
    
    # Tech/Thematic - Tight bands (bubble-prone)
    "FANG.AX": (0.10, "GROWTH", 0.05, 0.15, 0.75, 0.65, 0.20),
    "NDQ.AX": (0.05, "GROWTH", 0.03, 0.10, 0.75, 0.65, 0.20),
    
    # Cash Reserve
    "CASH": (0.02, "CORE", 0.00, 0.30, 1.0, 1.0, 0.0)
}

# New: Momentum Override Rules
MOMENTUM_OVERRIDE = {
    "enabled": True,
    "lookback_days": 30,
    "threshold": 0.15,  # 15% gain in 30 days = strong momentum
    "risk_extension": 0.05  # Allow +0.05 risk before selling
}

# =====================================================
# CORE LOGIC V2
# =====================================================

def calculate_momentum_score(df, lookback=30):
    """Calculate recent momentum to detect parabolic moves"""
    if len(df) < lookback:
        return 0.0
    recent_return = (df['Close'].iloc[-1] / df['Close'].iloc[-lookback]) - 1
    return recent_return

def get_risk_data_with_momentum():
    """Fetch risk scores + momentum for all assets"""
    print("Fetching risk + momentum data...")
    risk_data = {}
    momentum_data = {}
    
    for ticker in ASSET_CONFIG.keys():
        if ticker == "CASH":
            risk_data[ticker] = 0.0
            momentum_data[ticker] = 0.0
            continue
            
        try:
            df, _, meta = analyze_asset(ticker)
            if meta.get("reason"):
                print(f"  ⚠️  {ticker}: {meta['reason']}")
                risk_data[ticker] = None
                momentum_data[ticker] = None
            else:
                risk_data[ticker] = meta['last_risk']
                momentum_data[ticker] = calculate_momentum_score(df)
                print(f"  ✓ {ticker}: Risk={meta['last_risk']:.2f}, Momentum={momentum_data[ticker]:+.1%}")
        except Exception as e:
            print(f"  ✗ {ticker}: Error - {e}")
            risk_data[ticker] = None
            momentum_data[ticker] = None
    
    return risk_data, momentum_data

def calculate_adaptive_weights_v2(risk_data, momentum_data, macro_context):
    """
    V2: Asset-specific risk bands + momentum override
    """
    results = []
    
    # Macro Risk Adjustment
    # Note: analyze_market_cycle doesn't return a direct composite_score yet in enhanced_main.py,
    # but we can infer one from the macro_context or use a default.
    # Refactoring it slightly to match the expected usage or using a safe default.
    composite_risk = macro_context.get("composite_score", 0.5)
    
    # Global damper (unchanged)
    global_damper = 1.0
    if composite_risk > 0.70:
        global_damper = 0.6
    elif composite_risk > 0.60:
        global_damper = 0.8
    
    print(f"\n📊 Macro Composite Risk: {composite_risk:.2f}")
    print(f"   Global Risk Damper: {global_damper:.1%}\n")
    
    for ticker, (base_weight, tier, min_w, max_w, risk_exit, risk_reduce, moonbag) in ASSET_CONFIG.items():
        risk_score = risk_data.get(ticker)
        momentum = momentum_data.get(ticker, 0.0)
        
        # Skip if unavailable
        if risk_score is None:
            results.append({
                "ticker": ticker,
                "base_weight": base_weight,
                "adjusted_weight": 0,
                "risk_score": None,
                "action": "SKIP (No Data)"
            })
            continue
        
        # MOMENTUM OVERRIDE: Extend risk tolerance in parabolic moves
        effective_exit = risk_exit
        effective_reduce = risk_reduce
        
        if MOMENTUM_OVERRIDE["enabled"] and momentum > MOMENTUM_OVERRIDE["threshold"]:
            effective_exit += MOMENTUM_OVERRIDE["risk_extension"]
            effective_reduce += MOMENTUM_OVERRIDE["risk_extension"]
            momentum_flag = f" [🚀 Momentum: {momentum:+.1%}]"
        else:
            momentum_flag = ""
        
        # Position Sizing Logic
        adjusted = base_weight
        action = "HOLD"
        
        # 1. FULL EXIT: Risk > exit threshold
        if risk_score > effective_exit:
            adjusted = min_w
            action = f"🔴 EXIT (Risk {risk_score:.2f} > {effective_exit:.2f}){momentum_flag}"
        
        # 2. MOONBAG: Risk > reduce threshold (take profits but keep exposure)
        elif risk_score > effective_reduce:
            # Scale to moonbag position
            adjusted = base_weight * moonbag
            adjusted = max(adjusted, min_w)
            action = f"🟠 MOONBAG (Risk {risk_score:.2f}, Keep {moonbag:.0%}){momentum_flag}"
        
        # 3. VALUE ZONE: Overweight
        elif risk_score < 0.30:
            boost = 1.0 + ((0.30 - risk_score) / 0.30) * 0.5
            adjusted = min(base_weight * boost, max_w)
            action = f"🟢 OVERWEIGHT (Value {risk_score:.2f})"
        
        # 4. WARNING ZONE: Taper slightly
        elif risk_score > (effective_reduce - 0.10):
            taper = 0.85
            adjusted = max(base_weight * taper, min_w)
            action = f"🟡 REDUCE (Warning {risk_score:.2f})"
        
        # Apply macro damper only to non-core
        if tier in ["GROWTH", "CRYPTO"]:
            adjusted *= global_damper
        
        # Clamp to bounds
        adjusted = max(min_w, min(adjusted, max_w))
        
        results.append({
            "ticker": ticker,
            "tier": tier,
            "base_weight": base_weight,
            "risk_score": risk_score,
            "momentum": momentum,
            "exit_threshold": effective_exit,
            "adjusted_weight": adjusted,
            "action": action
        })
    
    # Normalize weights
    total_weight = sum(r["adjusted_weight"] for r in results)
    if total_weight > 0:
        for r in results:
            r["normalized_weight"] = r["adjusted_weight"] / total_weight
    else:
        for r in results:
            r["normalized_weight"] = 0
    
    return pd.DataFrame(results)

def generate_execution_plan(weights_df, current_holdings=None):
    """Generate buy/sell orders"""
    if current_holdings is None:
        current_holdings = {}
    
    target_value = PORTFOLIO_AUM
    orders = []
    
    for _, row in weights_df.iterrows():
        ticker = row['ticker']
        target_weight = row['normalized_weight']
        target_value_asset = target_value * target_weight
        
        current_value = current_holdings.get(ticker, 0)
        delta = target_value_asset - current_value
        
        if abs(delta) > 500:  # Min trade size $500
            side = "BUY" if delta > 0 else "SELL"
            orders.append({
                "ticker": ticker,
                "side": side,
                "amount_aud": abs(delta),
                "reason": row['action']
            })
    
    return pd.DataFrame(orders)

# =====================================================
# MAIN
# =====================================================

def run_adaptive_portfolio_v2():
    print("="*60)
    print("RISK-ADAPTIVE PORTFOLIO V2.0 - ASYMMETRIC BANDS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("="*60)
    
    # 1. Macro Context
    cycle_report, macro_context = analyze_market_cycle()
    print(cycle_report)
    
    # 2. Get Risk + Momentum
    risk_data, momentum_data = get_risk_data_with_momentum()
    
    # 3. Calculate Adaptive Weights V2
    weights_df = calculate_adaptive_weights_v2(risk_data, momentum_data, macro_context)
    
    # 4. Display
    print("\n" + "="*60)
    print("ADAPTIVE ALLOCATION V2")
    print("="*60)
    display_cols = ['ticker', 'tier', 'risk_score', 'momentum', 
                    'exit_threshold', 'normalized_weight', 'action']
    pd.options.display.float_format = '{:.2f}'.format
    print(weights_df[display_cols].to_string(index=False))
    
    # 5. Generate Orders
    print("\n" + "="*60)
    print("EXECUTION PLAN")
    print("="*60)
    orders_df = generate_execution_plan(weights_df)
    if not orders_df.empty:
        orders_df['amount_aud'] = orders_df['amount_aud'].apply(lambda x: f"${x:,.0f}")
        print(orders_df.to_string(index=False))
    else:
        print("✓ Portfolio in balance - no trades needed")
    
    # 6. Risk Profile Summary
    crypto_weight = weights_df[weights_df['tier']=='CRYPTO']['normalized_weight'].sum()
    core_weight = weights_df[weights_df['tier']=='CORE']['normalized_weight'].sum()
    
    print("\n" + "="*60)
    print("PORTFOLIO RISK PROFILE")
    print("="*60)
    print(f"Crypto Exposure:   {crypto_weight:.1%}")
    print(f"Core Exposure:     {core_weight:.1%}")
    print(f"Macro Risk Score:  {macro_context.get('composite_score', 0):.2f}")
    
    # 7. Strategy Configuration
    print("\n" + "="*60)
    print("RISK BAND CONFIGURATION")
    print("="*60)
    print("Asset Class    | Exit Threshold | Reduce Threshold | Moonbag")
    print("-" * 60)
    for tier in ["CRYPTO", "CORE", "COMMODITY", "GROWTH"]:
        sample = next((v for v in ASSET_CONFIG.values() if v[1] == tier), None)
        if sample:
            print(f"{tier:<14} | {sample[4]:.2f}           | {sample[5]:.2f}             | {sample[6]:.0%}")
    
    return weights_df, orders_df

if __name__ == "__main__":
    run_adaptive_portfolio_v2()
