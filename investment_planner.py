
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset
from sentiment_engine import get_asset_sentiment

# =========================================================
# 1. LIVE DATA & YIELD RATES (AUD) - DEC 24, 2025
# =========================================================
INITIAL_INJECTION = 100000.00
MONTHLY_DCA = 3000.00

# Prices and Yields based on Dec 2025 Market Snapshots
DATA = {
    # TICKER: [PRICE_AUD, EST_YIELD_PA, CUSTODY_TYPE]
    "BTC_COLD":   [133142.0, 0.000, "Cold Storage"], 
    "BTC_LEDN":   [133142.0, 0.070, "Platform"],     
    "ETH_STAKE":  [4611.0,   0.065, "Platform"],     
    "USD_NEXO":   [1.51,     0.100, "Platform"],     
    "PAXG_NEXO":  [4330.0,   0.045, "Platform"],     
    "JUDO_TD":    [1.00,     0.045, "Bank"],         
    "ADA_BEEFY":  [0.85,     0.120, "DeFi"],         
    "MQG":        [203.01,   0.035, "Broker"],       
    "VGS":        [154.03,   0.021, "Broker"],       
    "VAS":        [109.15,   0.038, "Broker"],       
    "VAP":        [101.51,   0.041, "Broker"]        
}

# Mapping for Risk Analysis Proxy Tickers
RISK_PROXY_MAP = {
    "BTC_COLD": "BTC-USD",
    "BTC_LEDN": "BTC-USD",
    "ETH_STAKE": "ETH-USD",
    "PAXG_NEXO": "GC=F",
    "ADA_BEEFY": "ADA-USD",
    "MQG": "MQG.AX",
    "VGS": "VGS.AX",
    "VAS": "VAS.AX",
    "VAP": "VAP.AX",
    "USD_NEXO": None, # Stable/Cash
    "JUDO_TD": None   # Bank/Cash
}

# =========================================================
# 2. PORTFOLIO CONFIGURATION
# =========================================================
portfolio_config = {
    "target_weights": {
        "BTC_COLD": 0.08, "BTC_LEDN": 0.08, "ETH_STAKE": 0.16, 
        "PAXG_NEXO": 0.12, "USD_NEXO": 0.10, "JUDO_TD": 0.10, 
        "VGS": 0.10, "VAS": 0.06, "VAP": 0.05, "ADA_BEEFY": 0.05,
        "MQG": 0.10 
    },
    "current_holdings": {
        "MQG": 350, 
        "SEMI_RBTZ_FANG": 35000 # This is a lump sum value for existing equity
    }
}

def get_latest_risk_data(proxies):
    """Fetches risk AND sentiment for a list of tickers."""
    risk_data = {}
    sentiment_data = {}
    unique_tickers = list(set([t for t in proxies.values() if t]))
    
    print(f"Fetching risk & sentiment metrics for {len(unique_tickers)} proxies...")
    ticker_risks = {}
    ticker_sentiments = {}
    
    for ticker in unique_tickers:
        try:
            # 1. Quantitative Risk
            df, _, meta = analyze_asset(ticker)
            ticker_risks[ticker] = meta['last_risk']
            
            # 2. Qualitative Sentiment
            print(f"  Fetching news sentiment for {ticker}...")
            sent_score = get_asset_sentiment(ticker)
            ticker_sentiments[ticker] = sent_score
            
        except Exception as e:
            print(f"  Error fetching metrics for {ticker}: {e}")
            ticker_risks[ticker] = 0.5 
            ticker_sentiments[ticker] = 0.5
            
    for label, ticker in proxies.items():
        if ticker:
            risk_data[label] = ticker_risks[ticker]
            sentiment_data[label] = ticker_sentiments[ticker]
        else:
            risk_data[label] = 0.0 # Lowest risk for Cash/Bank
            sentiment_data[label] = 0.5 # Neutral
            
    return risk_data, sentiment_data

def apply_sentiment_bias(base_risk, sentiment_score):
    """
    Adjusts risk based on sentiment.
    - Fear (<0.5) INCREASES risk (avoid knife catching)
    - Greed (>0.5) DECREASES risk (confirm trend)
    """
    bias = (0.5 - sentiment_score) * 0.2
    return max(0.0, min(1.0, base_risk + bias))

def run_portfolio_optimizer(config, data, injection, risk_data, sentiment_data):
    # Calculate Current Value
    current_val = 0
    for asset, qty in config["current_holdings"].items():
        if asset == "SEMI_RBTZ_FANG":
            current_val += qty # Use direct AUD value
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

    for asset, target_pct in config["target_weights"].items():
        # Current value of this specific asset (handle MQG specially since it has holdings)
        asset_price = data.get(asset, [0])[0]
        current_asset_val = config["current_holdings"].get(asset, 0) * asset_price
        
        target_aud = total_wealth * target_pct
        action_buy = max(0, target_aud - current_asset_val)
        
        yield_pa = data.get(asset, [0, 0])[1]
        custody = data.get(asset, [0, 0, "Unknown"])[2]
        
        # Risk Calculation
        base_risk = risk_data.get(asset, 0)
        sentiment = sentiment_data.get(asset, 0.5)
        adj_risk = apply_sentiment_bias(base_risk, sentiment)
        
        # Risk Gate logic (using Adjusted Risk)
        status = "BUY"
        if adj_risk > 0.70:
            status = "⚠️ SKIP (High Risk)"
            action_buy = 0
        elif adj_risk < 0.30 and action_buy > 0:
            status = "🟢 VALUE BUY"
        elif action_buy == 0:
            status = "HOLD (Target Met)"

        if custody in ["Platform", "DeFi"]:
            platform_risk_cap += target_aud
        
        annual_income = target_aud * yield_pa
        total_annual_income += annual_income

        results.append({
            "Asset": asset,
            "Base_Risk": f"{base_risk:.2f}",
            "Sentiment": f"{sentiment:.2f}",
            "Adj_Risk": f"{adj_risk:.2f}",
            "Action_BUY": action_buy,
            "Annual_Income": annual_income,
            "Custody": custody,
            "Status": status
        })
    
    return pd.DataFrame(results), total_wealth, platform_risk_cap, total_annual_income

def generate_dca_plan(risk_data, sentiment_data, data):
    print("\n--- 6-MONTH RISK-ADJUSTED DCA STRATEGY ($3,000/mo) ---")
    # Strategy: Prioritize assets with lowest ADJUSTED risk scores
    tradable_assets = [k for k, v in RISK_PROXY_MAP.items() if v]
    
    # Calculate adj risk for sorting
    asset_risks = []
    for k in tradable_assets:
        base = risk_data[k]
        sent = sentiment_data[k]
        adj = apply_sentiment_bias(base, sent)
        asset_risks.append((k, adj))
    
    sorted_assets = sorted(asset_risks, key=lambda x: x[1])
    
    dca_plan = []
    months = ["January", "February", "March", "April", "May", "June"]
    
    for i, month in enumerate(months):
        asset, risk = sorted_assets[i % len(sorted_assets)]
        obj = "Value Accumulation" if risk < 0.3 else "Strategic Top-up"
        if risk > 0.7: obj = "Defensive Cash Building"
        
        dca_plan.append([month, asset, f"Adj Risk {risk:.2f}: {obj}"])
        
    return pd.DataFrame(dca_plan, columns=["Month", "Ticker", "Objective"])

if __name__ == "__main__":
    # 1. Fetch Latest Data
    risk_data, sentiment_data = get_latest_risk_data(RISK_PROXY_MAP)
    
    # 2. Run Optimizer
    df_exec, total_cap, risk_cap, total_income = run_portfolio_optimizer(
        portfolio_config, DATA, INITIAL_INJECTION, risk_data, sentiment_data
    )
    
    # 3. Output Results
    print(f"Total Portfolio Value Post-Injection: ${total_cap:,.2f}")
    print(f"Total Platform Risk (Nexo/Ledn/Beefy): ${risk_cap:,.2f} ({round(risk_cap/total_cap*100, 1)}%)")
    print(f"Est. Annual Pre-tax Income: ${total_income:,.2f} (Yield: {round(total_income/total_cap*100, 2)}%)")
    
    print("\n--- IMMEDIATE ACTION BUY LIST ---")
    display_cols = ['Asset', 'Base_Risk', 'Sentiment', 'Adj_Risk', 'Action_BUY', 'Status']
    # Format Action_BUY for display
    df_display = df_exec.copy()
    df_display['Action_BUY'] = df_display['Action_BUY'].apply(lambda x: f"${x:,.2f}")
    print(df_display[display_cols].to_string(index=False))
    
    # 4. DCA Plan
    dca_df = generate_dca_plan(risk_data, sentiment_data, DATA)
    print(dca_df.to_string(index=False))
