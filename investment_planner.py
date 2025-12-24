import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset

# =========================================================
# 1. LIVE DATA & YIELD RATES (AUD) - DEC 24, 2025
# =========================================================
INITIAL_INJECTION = 100000.00
MONTHLY_DCA = 3000.00

# Prices and Yields based on Dec 2025 Market Snapshots
DATA = {
    # TICKER: [PRICE_AUD, EST_YIELD_PA, CUSTODY_TYPE]
    "BTC_COLD":    [133142.0, 0.000, "Cold Storage"], 
    "ETH_COLD":    [4611.0,   0.000, "Cold Storage"],
    "ETH_STAKE":   [4611.0,   0.045, "Platform"],     # Staking approx 4.5%
    "PAXG_NEXO":   [4330.0,   0.040, "Platform"],     # 4% yield
    "ADA_MINSWAP": [0.85,     0.120, "DeFi"],         # Minswap 12%
    "USD_LEDN":    [1.52,     0.070, "Platform"],     # Ledn USD 7%
    "USD_NEXO":    [1.52,     0.100, "Platform"],     
    "JUDO_TD":     [1.00,     0.050, "Bank"],         # Judo 5%
    "MQG":         [203.01,   0.035, "Broker"],       
    "VGS":         [154.03,   0.021, "Broker"],       
    "VAS":         [109.15,   0.038, "Broker"],       
    "VAP":         [101.51,   0.041, "Broker"]        
}

# Mapping for Risk Analysis Proxy Tickers
RISK_PROXY_MAP = {
    "BTC_COLD":    "BTC-USD",
    "ETH_COLD":    "ETH-USD",
    "ETH_STAKE":   "ETH-USD",
    "PAXG_NEXO":   "GC=F",
    "ADA_MINSWAP": "ADA-USD",
    "MQG":         "MQG.AX",
    "VGS":         "VGS.AX",
    "VAS":         "VAS.AX",
    "VAP":         "VAP.AX",
    "USD_LEDN":    None,
    "USD_NEXO":    None,
    "JUDO_TD":     None
}

# =========================================================
# 2. PORTFOLIO CONFIGURATION (Risk-Adaptive v2.0)
# =========================================================
# Format: ticker/label: (base, min, max, exit_threshold, reduce_threshold, moonbag)
# Thresholds pulled from v2 logic: Crypto=0.85/0.75, Core=0.80/0.70, etc.

ASSET_CONFIG = {
    # TIER 1: CORE (Higher tolerance)
    "BTC_COLD":    {"tier": "CRYPTO", "base": 0.12, "min": 0.02, "max": 0.20, "exit": 0.85, "reduce": 0.75, "moon": 0.40},
    "ETH_COLD":    {"tier": "CRYPTO", "base": 0.08, "min": 0.02, "max": 0.12, "exit": 0.85, "reduce": 0.75, "moon": 0.40},
    "ETH_STAKE":   {"tier": "CRYPTO", "base": 0.08, "min": 0.02, "max": 0.12, "exit": 0.85, "reduce": 0.75, "moon": 0.40},
    "VGS":         {"tier": "CORE",   "base": 0.12, "min": 0.05, "max": 0.18, "exit": 0.80, "reduce": 0.70, "moon": 0.20},
    "MQG":         {"tier": "CORE",   "base": 0.10, "min": 0.05, "max": 0.15, "exit": 0.80, "reduce": 0.70, "moon": 0.20},
    "PAXG_NEXO":   {"tier": "CORE",   "base": 0.12, "min": 0.05, "max": 0.15, "exit": 0.78, "reduce": 0.68, "moon": 0.25},

    # TIER 2: SATELLITE/AGGRESSIVE
    "VAS":         {"tier": "SAT",  "base": 0.06, "min": 0.00, "max": 0.10, "exit": 0.75, "reduce": 0.65, "moon": 0.25},
    "VAP":         {"tier": "SAT",  "base": 0.04, "min": 0.00, "max": 0.08, "exit": 0.75, "reduce": 0.65, "moon": 0.25},
    "ADA_MINSWAP": {"tier": "AGGR", "base": 0.05, "min": 0.00, "max": 0.08, "exit": 0.85, "reduce": 0.75, "moon": 0.40},

    # TIER 3: CASH/DEFENSIVE
    "USD_LEDN":    {"tier": "CASH", "base": 0.06}, 
    "USD_NEXO":    {"tier": "CASH", "base": 0.07}, 
    "JUDO_TD":     {"tier": "CASH", "base": 0.10},
}

MOMENTUM_OVERRIDE = {
    "enabled": True,
    "lookback_days": 30,
    "threshold": 0.15,
    "risk_extension": 0.05
}

portfolio_config = {
    "current_holdings": {
        "MQG": 350, 
        "SEMI_RBTZ_FANG": 35000 
    }
}

def calculate_momentum_score(df, lookback=30):
    if len(df) < lookback: return 0.0
    return (df['Close'].iloc[-1] / df['Close'].iloc[-lookback]) - 1

def get_latest_risk_data(proxies):
    """Fetches risk + momentum for proxies."""
    risk_data = {}
    unique_tickers = list(set([t for t in proxies.values() if t]))
    
    print(f"Fetching risk + momentum for {len(unique_tickers)} proxies...")
    ticker_stats = {}
    
    for ticker in unique_tickers:
        try:
            df, _, meta = analyze_asset(ticker)
            if meta.get("reason"):
                print(f"  Warning for {ticker}: {meta['reason']}")
                ticker_stats[ticker] = None
            else:
                ticker_stats[ticker] = {
                    "risk": meta['last_risk'],
                    "momentum": calculate_momentum_score(df)
                }
        except Exception as e:
            print(f"  Critical Error for {ticker}: {e}")
            ticker_stats[ticker] = None
            
    for label, ticker in proxies.items():
        if ticker:
            risk_data[label] = ticker_stats.get(ticker)
        else:
            risk_data[label] = {"risk": 0.0, "momentum": 0.0}
            
    return risk_data

def calculate_dynamic_weight(asset, cfg, stats):
    """
    V2 Logic: Asymmetric Bands + Momentum Extension
    """
    if stats is None: return 0.0
    risk = stats['risk']
    momentum = stats['momentum']
    
    tier = cfg.get("tier", "CASH")
    base = cfg.get("base", 0.0)
    if tier == "CASH": return base
        
    min_w = cfg.get("min", 0.0)
    max_w = cfg.get("max", base)
    
    # Thresholds
    exit_t = cfg.get("exit", 0.75)
    reduce_t = cfg.get("reduce", 0.65)
    moonbag = cfg.get("moon", 0.20)
    
    # Momentum Override
    if MOMENTUM_OVERRIDE["enabled"] and momentum > MOMENTUM_OVERRIDE["threshold"]:
        exit_t += MOMENTUM_OVERRIDE["risk_extension"]
        reduce_t += MOMENTUM_OVERRIDE["risk_extension"]
    
    # 1. Full Exit (Extreme)
    if risk > exit_t: return min_w
        
    # 2. Moonbag (High)
    if risk > reduce_t:
        return max(min_w, base * moonbag)
        
    # 3. Value Zone (< 0.30)
    if risk < 0.30:
        boost = 1.5 if tier in ["CORE", "CRYPTO"] else 1.2
        return min(max_w, base * boost)
        
    return base

def run_portfolio_optimizer(config, data, injection, risk_data):
    # Calculate Current Value
    current_val = 0
    for asset, qty in config["current_holdings"].items():
        if asset == "SEMI_RBTZ_FANG":
            current_val += qty 
        else:
            current_val += qty * data.get(asset, [0])[0]
            
    total_wealth = current_val + injection
    
    print(f"\n--- PORTFOLIO SUMMARY ---")
    print(f"Current Assets: ${current_val:,.2f}")
    print(f"New Injection:  ${injection:,.2f}")
    print(f"Total Wealth:   ${total_wealth:,.2f}\n")

    results = []
    platform_risk_cap = 0
    total_annual_income = 0
    
    # --- PHASE 1: Calculate Dynamic Target Weights ---
    raw_weights = {}
    risk_assets_weight = 0
    cash_base_weight = 0
    
    for asset, cfg in ASSET_CONFIG.items():
        stats = risk_data.get(asset)
        
        target_w = calculate_dynamic_weight(asset, cfg, stats)
        raw_weights[asset] = {
            "weight": target_w, 
            "stats": stats
        }
        
        if cfg["tier"] == "CASH":
            cash_base_weight += cfg["base"]
        else:
            risk_assets_weight += target_w
            
    # --- PHASE 2: Normalize / Distribute Residual ---
    total_allocated = risk_assets_weight + cash_base_weight
    residual = 1.0 - total_allocated
    
    final_weights = {}
    if residual < 0:
        factor = 1.0 / total_allocated
        for a in raw_weights:
            final_weights[a] = raw_weights[a]["weight"] * factor
    else:
        cash_assets = [k for k,v in ASSET_CONFIG.items() if v["tier"] == "CASH"]
        cash_weight_sum = sum([ASSET_CONFIG[k]["base"] for k in cash_assets])
        
        for a, w_data in raw_weights.items():
            if a in cash_assets:
                share = (ASSET_CONFIG[a]["base"] / cash_weight_sum) * residual
                final_weights[a] = w_data["weight"] + share
            else:
                final_weights[a] = w_data["weight"]

    # --- PHASE 3: Generate Actions ---
    for asset, weight in final_weights.items():
        w_data = raw_weights[asset]
        stats = w_data["stats"]
        risk = stats['risk'] if stats else None
        momentum = stats['momentum'] if stats else 0
        
        asset_price = data.get(asset, [0])[0]
        current_asset_val = config["current_holdings"].get(asset, 0) * asset_price
        
        target_aud = total_wealth * weight
        action_buy = max(0, target_aud - current_asset_val)
        
        yield_pa = data.get(asset, [0, 0])[1]
        custody = data.get(asset, [0, 0, "Unknown"])[2]
        
        # Thresholds for Status
        cfg = ASSET_CONFIG.get(asset, {})
        exit_t = cfg.get("exit", 0.75)
        # Momentum Adjustment for status text
        if MOMENTUM_OVERRIDE["enabled"] and momentum > MOMENTUM_OVERRIDE["threshold"]:
            exit_t += MOMENTUM_OVERRIDE["risk_extension"]

        # Status Logic
        status = "BUY"
        if risk is None:
            status = "❌ ERROR (Metric Failure)"
            action_buy = 0
        elif risk > exit_t:
            status = "⚠️ REDUCE (High Risk)"
            if action_buy > 0: action_buy = 0
        elif risk < 0.30 and action_buy > 0:
            status = "🟢 VALUE OVERWEIGHT"
        elif action_buy == 0:
            status = "HOLD (Target Met)"

        if custody in ["Platform", "DeFi"]:
            platform_risk_cap += target_aud
        
        annual_income = target_aud * yield_pa
        total_annual_income += annual_income

        results.append({
            "Asset": asset,
            "Risk": f"{risk:.2f}" if risk is not None else "N/A",
            "Target_%": f"{weight*100:.1f}%",
            "Action_BUY": action_buy,
            "Annual_Income": annual_income,
            "Custody": custody,
            "Status": status
        })
    
    return pd.DataFrame(results), total_wealth, platform_risk_cap, total_annual_income

def generate_dca_plan(risk_data, data):
    print("\n--- 6-MONTH RISK-ADJUSTED DCA STRATEGY ($3,000/mo) ---")
    tradable_assets = [k for k, v in RISK_PROXY_MAP.items() if v]
    
    asset_risks = []
    for k in tradable_assets:
        stats = risk_data[k]
        asset_risks.append((k, stats['risk'] if stats else 0.5))
    
    sorted_assets = sorted(asset_risks, key=lambda x: x[1])
    
    dca_plan = []
    months = ["January", "February", "March", "April", "May", "June"]
    
    for i, month in enumerate(months):
        asset, risk = sorted_assets[i % len(sorted_assets)]
        obj = "Value Accumulation" if risk < 0.3 else "Strategic Top-up"
        if risk > 0.7: obj = "Defensive Cash Building"
        
        dca_plan.append([month, asset, f"Risk {risk:.2f}: {obj}"])
        
    return pd.DataFrame(dca_plan, columns=["Month", "Ticker", "Objective"])

if __name__ == "__main__":
    risk_data = get_latest_risk_data(RISK_PROXY_MAP)
    df_exec, total_cap, risk_cap, total_income = run_portfolio_optimizer(
        portfolio_config, DATA, INITIAL_INJECTION, risk_data
    )
    print(f"Total Portfolio Value Post-Injection: ${total_cap:,.2f}")
    print(f"Total Platform Risk (Nexo/Ledn/Beefy): ${risk_cap:,.2f} ({round(risk_cap/total_cap*100, 1)}%)")
    print(f"Est. Annual Pre-tax Income: ${total_income:,.2f} (Yield: {round(total_income/total_cap*100, 2)}%)")
    print("\n--- IMMEDIATE ACTION BUY LIST ---")
    display_cols = ['Asset', 'Target_%', 'Risk', 'Action_BUY', 'Status']
    df_display = df_exec.copy()
    df_display['Action_BUY'] = df_display['Action_BUY'].apply(lambda x: f"${x:,.2f}")
    print(df_display[display_cols].to_string(index=False))
    dca_df = generate_dca_plan(risk_data, DATA)
    print(dca_df.to_string(index=False))
