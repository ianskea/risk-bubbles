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

ASSET_CONFIG = {
    # TIER 1: CORE (User-Requested Targets)
    "BTC_COLD":    {"tier": "CRYPTO", "base": 0.18, "min": 0.05, "max": 0.30, "exit": 0.85, "reduce": 0.75, "moon": 0.40},
    "ETH_COLD":    {"tier": "CRYPTO", "base": 0.05, "min": 0.02, "max": 0.15, "exit": 0.85, "reduce": 0.75, "moon": 0.40},
    "ETH_STAKE":   {"tier": "CRYPTO", "base": 0.05, "min": 0.02, "max": 0.15, "exit": 0.85, "reduce": 0.75, "moon": 0.40},
    "VGS":         {"tier": "CORE",   "base": 0.15, "min": 0.05, "max": 0.25, "exit": 0.80, "reduce": 0.70, "moon": 0.20},
    "MQG":         {"tier": "CORE",   "base": 0.10, "min": 0.05, "max": 0.20, "exit": 0.80, "reduce": 0.70, "moon": 0.20},
    "PAXG_NEXO":   {"tier": "CORE",   "base": 0.08, "min": 0.02, "max": 0.15, "exit": 0.78, "reduce": 0.68, "moon": 0.25},

    # TIER 2: SATELLITE/AGGRESSIVE
    "VAS":         {"tier": "SAT",  "base": 0.06, "min": 0.00, "max": 0.12, "exit": 0.75, "reduce": 0.65, "moon": 0.25},
    "VAP":         {"tier": "SAT",  "base": 0.04, "min": 0.00, "max": 0.10, "exit": 0.75, "reduce": 0.65, "moon": 0.25},
    "ADA_MINSWAP": {"tier": "AGGR", "base": 0.05, "min": 0.00, "max": 0.10, "exit": 0.85, "reduce": 0.75, "moon": 0.40},

    # TIER 3: CASH/DEFENSIVE (Targets)
    "USD_LEDN":    {"tier": "CASH", "base": 0.10}, 
    "USD_NEXO":    {"tier": "CASH", "base": 0.07}, 
    "JUDO_TD":     {"tier": "CASH", "base": 0.07},
}

MOMENTUM_OVERRIDE = {
    "enabled": True,
    "lookback_days": 30,
    "threshold": 0.15,
    "risk_extension": 0.05
}

portfolio_config = {
    "current_holdings": {
        "BTC_COLD": 0.12,  # ~16k (8%)
        "ADA_MINSWAP": 4700, # ~4k (2%)
        "PAXG_NEXO": 5.5,   # ~24k (12%)
        "MQG": 147,        # ~30k (15%)
        "USD_LEDN": 4000,   # (AUD equivalent)
        "VGS": 10          # Small start
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
                ticker_stats[ticker] = None
            else:
                ticker_stats[ticker] = {
                    "risk": meta['last_risk'],
                    "momentum": calculate_momentum_score(df)
                }
        except Exception as e:
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
        boost = 1.4 if tier in ["CORE", "CRYPTO"] else 1.2
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
        raw_weights[asset] = {"weight": target_w, "stats": stats}
        
        if cfg["tier"] == "CASH":
            cash_base_weight += cfg["base"]
        else:
            risk_assets_weight += target_w
            
    # --- PHASE 2: Normalize ---
    total_allocated = risk_assets_weight + cash_base_weight
    final_weights = {a: (data["weight"] / total_allocated) for a, data in raw_weights.items()}

    # --- PHASE 3: Generate Actions ---
    for asset, weight in final_weights.items():
        w_data = raw_weights[asset]
        stats = w_data["stats"]
        risk = stats['risk'] if stats else None
        
        asset_price = data.get(asset, [0])[0]
        current_asset_val = config["current_holdings"].get(asset, 0) * asset_price
        current_weight = current_asset_val / total_wealth
        
        target_aud = total_wealth * weight
        action_diff = target_aud - current_asset_val
        
        yield_pa = data.get(asset, [0, 0])[1]
        custody = data.get(asset, [0, 0, "Unknown"])[2]
        
        # Thresholds for Status (v2.0 Asymmetric)
        cfg = ASSET_CONFIG.get(asset, {})
        exit_t = cfg.get("exit", 0.75)
        reduce_t = cfg.get("reduce", 0.65)

        # Status Logic Refinement
        status = "HOLD"
        if risk is None:
            status = "❌ ERROR"
        elif action_diff > 10: # BUYING
            if risk == 0.0:
                status = "⚪ CASH BUILD"
            elif risk < 0.30:
                # Value Buy means underweight but it's cheap
                # Value Overweight means already at target but it's so cheap we buy more
                if current_weight < cfg.get("base", 0):
                    status = "🟢 VALUE BUY"
                else:
                    status = "🟢 VALUE OVERWEIGHT"
            else:
                status = "🟢 BUY"
        elif action_diff < -10: # SELLING/REDUCING
            if risk > reduce_t:
                status = "🔴 REDUCE (High Risk)"
            else:
                status = "🟠 REBALANCE (Overweight)"
        else:
            status = "⚫ HOLD (Target Met)"

        if custody in ["Platform", "DeFi"]:
            platform_risk_cap += target_aud
        
        annual_income = target_aud * yield_pa
        total_annual_income += annual_income

        results.append({
            "Asset": asset,
            "Risk": f"{risk:.2f}" if risk is not None else "N/A",
            "CURR%": f"{current_weight*100:.1f}%",
            "TARGET%": f"{weight*100:.1f}%",
            "ACTION": f"${action_diff:,.0f}",
            "Income": annual_income,
            "Status": status
        })
    
    return pd.DataFrame(results), total_wealth, platform_risk_cap, total_annual_income

def generate_dca_plan(risk_data):
    print("\n--- PROVISIONAL 6-MONTH DCA ROADMAP (Current Snapshot) ---")
    print("Note: Re-run monthly as market risks change.\n")
    tradable_assets = [k for k, v in RISK_PROXY_MAP.items() if v]
    
    asset_risks = []
    for k in tradable_assets:
        stats = risk_data[k]
        asset_risks.append((k, stats['risk'] if stats else 0.5))
    
    # Sort by risk (buy lowest risk first)
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
    print(f"Total Platform Risk (Nexo/Ledn/Minswap): ${risk_cap:,.2f} ({round(risk_cap/total_cap*100, 1)}%)")
    print(f"Est. Annual Pre-tax Income: ${total_income:,.2f} (Yield: {round(total_income/total_cap*100, 2)}%)")
    
    print("\n--- PORTFOLIO MASTER TABLE ---")
    print(df_exec[['Asset', 'CURR%', 'TARGET%', 'Risk', 'ACTION', 'Status']].to_string(index=False))
    
    dca_df = generate_dca_plan(risk_data)
    print(dca_df.to_string(index=False))
