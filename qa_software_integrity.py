import os
import sqlite3
import portfolio_db
import pandas as pd
import investment_planner
from datetime import datetime

def test_db_constraints():
    print("Testing Database Constraints...")
    portfolio_db.init_db()
    conn = sqlite3.connect(portfolio_db.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    # 1. Test Entity Name Constraint (CHECK)
    try:
        cursor.execute("INSERT INTO entities (name, type) VALUES ('Invalid Name', 'General')")
        conn.commit()
    except sqlite3.IntegrityError:
        print("✅ PASS: Database rejected invalid entity name.")
        
    # 2. Test Asset Ticker Constraint (FOREIGN KEY)
    try:
        cursor.execute("SELECT id FROM entities WHERE name = 'Ocean Embers'")
        e_id = cursor.fetchone()[0]
        cursor.execute(f"INSERT INTO parcels (entity_id, asset_ticker, quantity, cost_aud, purchase_date) VALUES ({e_id}, 'GHOST_TICKER', 10, 100, '2024-01-01')")
        conn.commit()
    except sqlite3.IntegrityError:
        print("✅ PASS: Database rejected invalid asset ticker (FK enforced).")
        
    conn.close()

def test_entity_logic():
    print("\nTesting Multi-Entity Planning Logic...")
    
    # Sync registry data into the planner's globals
    db_data, db_proxies, db_config = portfolio_db.get_asset_defs()
    investment_planner.DATA.update(db_data)
    investment_planner.RISK_PROXY_MAP.update(db_proxies)
    investment_planner.ASSET_CONFIG.update(db_config)
    
    # Mock risk
    mock_risk = {k: {"risk": 0.5, "momentum": 0.0} for k in investment_planner.ASSET_CONFIG.keys()}
    
    # Test SuperFund (Strict Rules)
    parcels = [("BTC_COLD", 1.0, 1000, "2024-01-01", None)]
    df, _ = investment_planner.run_portfolio_optimizer("Test Entity", "SuperFund", parcels, 0, mock_risk)
    
    if df.empty:
        print("❌ FAIL: Optimizer returned empty DF for valid SuperFund parcel.")
        return

    allowed_assets = df['Asset'].tolist()
    disallowed = ["PAXG_NEXO", "USD_LEDN", "ETH_STAKE"]
    intersection = set(allowed_assets).intersection(set(disallowed))
    
    if not intersection:
        print("✅ PASS: SuperFund strictly excludes disallowed custody types.")
    else:
        print(f"❌ FAIL: SuperFund included disallowed assets: {intersection}")

def test_performance_math():
    print("\nTesting Performance Calculation Math...")
    
    # Add a test asset to registry
    portfolio_db.add_asset("QA_BTC", "CRYPTO", "BTC-USD", 0.1, custody="Cold Storage")
    
    # Sync it to planner
    db_data, db_proxies, db_config = portfolio_db.get_asset_defs()
    investment_planner.DATA.update(db_data)
    investment_planner.ASSET_CONFIG.update(db_config)
    
    price_now = 120000.0
    cost_basis = 80000.0 # +50% gain
    
    investment_planner.DATA["QA_BTC"] = [price_now, 0, "Cold Storage"]
    
    parcels = [("QA_BTC", 1.0, cost_basis, "2023-01-01", None)] # >12m
    mock_risk = {"QA_BTC": {"risk": 0.5, "momentum": 0.0}}
    
    df, _ = investment_planner.run_portfolio_optimizer("Test", "General", parcels, 0, mock_risk)
    
    row = df[df['Asset'] == 'QA_BTC'].iloc[0]
    pnl = row['PnL']
    tax = row['TAX']
    
    if "+50.0%" in pnl:
        print("✅ PASS: PnL math is correct (+50%).")
    else:
        print(f"❌ FAIL: PnL math incorrect. Got {pnl}")
        
    if "✅ CGT+ (12m)" in tax:
        print("✅ PASS: CGT 12-month rule detected correctly.")
    else:
        print(f"❌ FAIL: CGT status incorrect. Got {tax}")

if __name__ == "__main__":
    print(f"{'='*60}")
    print(" SYSTEM QA & INTEGRATION TEST SUITE (v2.2 Dynamic)")
    print(f"{'='*60}")
    test_db_constraints()
    test_entity_logic()
    test_performance_math()
    print(f"{'='*60}")
