import pandas as pd
import numpy as np
import os
import sys
import argparse
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset
import portfolio_db

# Initialize Local Database
portfolio_db.init_db()
portfolio_db.seed_sample_data()

# Asset definitions (Loaded dynamically in main)
DATA = {}
RISK_PROXY_MAP = {}
ASSET_CONFIG = {}

# --- ENTITY CONSTRAINTS ---
ENTITY_RULES = {
    "SuperFund": {
        "allowed_custody": ["Cold Storage", "Broker", "Bank"],
        "disallowed_assets": ["PAXG_NEXO", "USD_LEDN", "USD_NEXO", "ADA_MINSWAP", "ETH_STAKE"],
        "default_dca": 3000.00
    },
    "General": {
        "allowed_custody": ["Cold Storage", "Platform", "DeFi", "Broker", "Bank"],
        "disallowed_assets": [],
        "default_dca": 0.00
    }
}

MOMENTUM_OVERRIDE = {
    "enabled": True,
    "lookback_days": 30,
    "threshold": 0.15,
    "risk_extension": 0.05
}

def calculate_momentum_score(df, lookback=30):
    if len(df) < lookback: return 0.0
    return (df['Close'].iloc[-1] / df['Close'].iloc[-lookback]) - 1

def get_latest_risk_data(proxies):
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
                ticker_stats[ticker] = {"risk": meta['last_risk'], "momentum": calculate_momentum_score(df)}
        except Exception:
            ticker_stats[ticker] = None
    for label, ticker in proxies.items():
        if ticker:
            risk_data[label] = ticker_stats.get(ticker)
        else:
            risk_data[label] = {"risk": 0.0, "momentum": 0.0}
    return risk_data

def calculate_dynamic_weight(asset, cfg, stats):
    if stats is None: return 0.0
    risk = stats['risk']
    momentum = stats['momentum']
    tier = cfg.get("tier", "CASH")
    base = cfg.get("base", 0.0)
    if tier == "CASH": return base
    min_w = cfg.get("min", 0.0)
    max_w = cfg.get("max", base)
    exit_t = cfg.get("exit", 0.75)
    reduce_t = cfg.get("reduce", 0.65)
    moonbag = cfg.get("moon", 0.20)
    if MOMENTUM_OVERRIDE["enabled"] and momentum > MOMENTUM_OVERRIDE["threshold"]:
        exit_t += MOMENTUM_OVERRIDE["risk_extension"]
        reduce_t += MOMENTUM_OVERRIDE["risk_extension"]
    if risk > exit_t: return min_w
    if risk > reduce_t: return max(min_w, base * moonbag)
    if risk < 0.30:
        boost = 1.4 if tier in ["CORE", "CRYPTO"] else 1.2
        return min(max_w, base * boost)
    return base

def run_portfolio_optimizer(entity_name, entity_type, parcels, injection, risk_data):
    # Filter Allowed Assets based on Entity Rules
    rules = ENTITY_RULES.get(entity_type, ENTITY_RULES["General"])
    active_config = {k: v for k, v in ASSET_CONFIG.items() 
                    if k not in rules["disallowed_assets"] 
                    and v["custody"] in rules["allowed_custody"]}
    
    # 1. Calculate Aggregate Holdings & Performance from Parcels
    holdings = {}
    total_cost_basis = 0
    asset_performance = {} # {asset: {'cost': 0, 'qty': 0, 'cgt_eligible': True/False, 'expiry': None}}
    
    now = datetime.now()
    for asset, qty, cost, purchase_date_str, expiry_date_str in parcels:
        holdings[asset] = holdings.get(asset, 0) + qty
        total_cost_basis += cost
        
        if asset not in asset_performance:
            asset_performance[asset] = {'cost': 0, 'qty': 0, 'cgt_eligible': True, 'expiry': None}
        
        asset_performance[asset]['cost'] += cost
        asset_performance[asset]['qty'] += qty
        
        # Track Expiry (Assume one expiry per ticker for simplicity in table)
        if expiry_date_str:
            asset_performance[asset]['expiry'] = expiry_date_str
        
        # CGT Check: 12-month rule (365 days)
        p_date = datetime.strptime(purchase_date_str, "%Y-%m-%d")
        if (now - p_date).days < 365:
            asset_performance[asset]['any_short_term'] = True

    current_val = 0
    for asset, qty in holdings.items():
        if asset in DATA:
            current_val += qty * DATA[asset][0]
            
    total_wealth = current_val + injection
    total_unrealized_pnl = current_val - total_cost_basis
    
    if total_wealth <= 0:
        print(f"\n--- PORTFOLIO SUMMARY: {entity_name} ---")
        print("Portfolio is empty. Please add parcels or an injection.")
        return pd.DataFrame(), 0

    print(f"\n--- PORTFOLIO SUMMARY: {entity_name} ---")
    print(f"Type:           {entity_type}")
    print(f"Current Assets: ${current_val:,.2f}")
    print(f"Total PnL:      ${total_unrealized_pnl:,.2f} ({total_unrealized_pnl/max(1, total_cost_basis)*100:.1f}%)")
    print(f"New Injection:  ${injection:,.2f}")
    print(f"Total Wealth:   ${total_wealth:,.2f}\n")

    # --- PHASE 1: Targets ---
    raw_weights = {}
    risk_assets_weight = 0
    cash_base_weight = 0
    
    for asset, cfg in active_config.items():
        stats = risk_data.get(asset)
        target_w = calculate_dynamic_weight(asset, cfg, stats)
        raw_weights[asset] = {"weight": target_w, "stats": stats}
        if cfg["tier"] == "CASH":
            cash_base_weight += cfg["base"]
        else:
            risk_assets_weight += target_w
            
    total_allocated = risk_assets_weight + cash_base_weight
    final_weights = {a: (data["weight"] / total_allocated) for a, data in raw_weights.items()}

    # --- PHASE 2: Generate Actions ---
    results = []
    total_annual_income = 0
    
    for asset, weight in final_weights.items():
        w_data = raw_weights[asset]
        stats = w_data["stats"]
        risk = stats['risk'] if stats else None
        
        asset_price = DATA[asset][0]
        qty = holdings.get(asset, 0)
        current_asset_val = qty * asset_price
        current_weight = current_asset_val / total_wealth
        
        # PnL & Tax for this asset
        perf = asset_performance.get(asset, {'cost': 0, 'qty': 0})
        pnl_pct = 0
        if perf['cost'] > 0:
            pnl_pct = (current_asset_val - perf['cost']) / perf['cost'] * 100
        
        # Tax Status
        tax_status = "⏳ SHORT"
        if asset in asset_performance:
            if qty > 0 and not asset_performance[asset].get('any_short_term'):
                tax_status = "✅ CGT+ (12m)"
            elif qty > 0 and asset_performance[asset].get('any_short_term'):
                tax_status = "⚠️ MIXED"

        # Expiry Check
        maturity_str = "N/A"
        if asset_performance.get(asset, {}).get('expiry'):
            e_date = datetime.strptime(asset_performance[asset]['expiry'], "%Y-%m-%d")
            days_left = (e_date - now).days
            if days_left < 0:
                maturity_str = "🛑 EXPIRED"
            elif days_left < 30:
                maturity_str = f"🔔 {days_left}d"
            else:
                maturity_str = f"{days_left}d"

        target_aud = total_wealth * weight
        action_diff = target_aud - current_asset_val
        
        yield_pa = DATA[asset][1]
        cfg = active_config.get(asset, {})
        reduce_t = cfg.get("reduce", 0.65)

        status = "HOLD"
        if risk is None: status = "❌ ERROR"
        elif action_diff > 10:
            if risk == 0.0: status = "⚪ CASH BUILD"
            elif risk < 0.30:
                status = "🟢 VALUE BUY" if current_weight < cfg.get("base", 0) else "🟢 VALUE OVERWEIGHT"
            else: status = "🟢 BUY"
        elif action_diff < -10:
            status = "🔴 REDUCE (High Risk)" if risk > reduce_t else "🟠 REBALANCE (Overweight)"
        else: status = "⚫ HOLD (Target Met)"

        total_annual_income += target_aud * yield_pa
        results.append({
            "Asset": asset,
            "Risk": f"{risk:.2f}" if risk is not None else "N/A",
            "CURR%": f"{current_weight*100:.1f}%",
            "TARGET%": f"{weight*100:.1f}%",
            "PnL": f"{pnl_pct:+.1f}%",
            "TAX": tax_status,
            "MATURITY": maturity_str,
            "ACTION": f"${action_diff:,.0f}",
            "Status": status
        })
    
    # Save Snapshot
    portfolio_db.save_snapshot(entity_name, total_wealth, total_unrealized_pnl)
    
    return pd.DataFrame(results), total_annual_income

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Entity Risk-Adaptive Portfolio Planner")
    parser.add_argument("--entity", type=str, default="Ocean Embers", help="Entity name")
    parser.add_argument("--injection", type=float, default=None, help="New cash injection amount")
    args = parser.parse_args()

    # Dynamic Data Loading
    print("Loading Institutional Asset Registry...")
    db_data, db_proxies, db_config = portfolio_db.get_asset_defs()
    DATA.update(db_data)
    RISK_PROXY_MAP.update(db_proxies)
    ASSET_CONFIG.update(db_config)
    
    entity_name = args.entity
    entity_info = portfolio_db.get_entity_info(entity_name)
    
    if not entity_info:
        print(f"Error: Entity '{entity_name}' not found in database.")
        sys.exit(1)
        
    entity_type = entity_info[1]
    
    # Use provided injection, or fallback to entity default DCA
    rules = ENTITY_RULES.get(entity_type, ENTITY_RULES["General"])
    injection = args.injection if args.injection is not None else rules.get("default_dca", 0.0)

    parcels = portfolio_db.get_parcels(entity_name)
    risk_data = get_latest_risk_data(RISK_PROXY_MAP)
    
    # Update DATA with latest live prices from risk_data fetch (if available)
    import yfinance as yf
    print("Updating registry with live market prices...")
    for label, proxy in RISK_PROXY_MAP.items():
        if proxy:
            try:
                # We can reuse the price from analyze_asset if we change it, 
                # but for simplicity, let's just use the latest risk_data fetch 
                # or a quick yf call if needed. Actually, let's fetch AUD prices.
                ticker_yf = yf.Ticker(proxy)
                current_price_usd = ticker_yf.fast_info['last_price']
                
                # Convert to AUD if it's a USD asset
                if "USD" in proxy or proxy in ["GC=F", "BTC-USD", "ETH-USD", "ADA-USD"]:
                    aud_usd = yf.Ticker("AUDUSD=X").fast_info['last_price']
                    DATA[label][0] = current_price_usd / aud_usd
                else:
                    DATA[label][0] = current_price_usd
            except Exception:
                print(f"  Warning: Could not update live price for {label}. Using fallback.")

    df_exec, total_income = run_portfolio_optimizer(
        entity_name, entity_type, parcels, injection, risk_data
    )
    
    print("\n--- PERFORMANCE, TAX & MATURITY TABLE ---")
    cols = ['Asset', 'CURR%', 'TARGET%', 'Risk', 'PnL', 'TAX', 'MATURITY', 'ACTION', 'Status']
    print(df_exec[cols].to_string(index=False))
    print(f"\nEst. Annual Pre-tax Income: ${total_income:,.2f}")
