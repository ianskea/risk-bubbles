import os
import sqlite3
import portfolio_db

def test_db_constraints():
    print("Testing Database Constraints...")
    conn = sqlite3.connect(portfolio_db.DB_PATH)
    cursor = conn.cursor()
    
    # 1. Test Entity Name Constraint
    try:
        cursor.execute("INSERT INTO entities (name, type) VALUES ('Fake Entity', 'General')")
        conn.commit()
        print("❌ FAIL: Database allowed invalid entity name.")
    except sqlite3.IntegrityError:
        print("✅ PASS: Database rejected invalid entity name.")
        
    # 2. Test Asset Ticker Constraint
    try:
        # Get actual entity id
        cursor.execute("SELECT id FROM entities WHERE name = 'Ocean Embers'")
        e_id = cursor.fetchone()[0]
        cursor.execute(f"INSERT INTO parcels (entity_id, asset_ticker, quantity, cost_aud, purchase_date) VALUES ({e_id}, 'INVALID_TICKER', 10, 100, '2024-01-01')")
        conn.commit()
        print("❌ FAIL: Database allowed invalid asset ticker.")
    except sqlite3.IntegrityError:
        print("✅ PASS: Database rejected invalid asset ticker.")
        
    conn.close()

def test_entity_logic():
    print("\nTesting Multi-Entity Planning Logic...")
    from investment_planner import run_portfolio_optimizer, ASSET_CONFIG, RISK_PROXY_MAP
    
    # Mock data
    mock_risk = {k: {"risk": 0.5, "momentum": 0.0} for k in RISK_PROXY_MAP.keys()}
    mock_risk[None] = {"risk": 0.0, "momentum": 0.0}
    
    # 1. SuperFund Constraints (should exclude PAXG_NEXO, ETH_STAKE etc)
    parcels = [("BTC_COLD", 1, 1000, "2024-01-01", None)]
    df, _ = run_portfolio_optimizer("Test Entity", "SuperFund", parcels, 0, mock_risk)
    
    allowed_assets = df['Asset'].tolist()
    disallowed = ["PAXG_NEXO", "USD_LEDN", "ETH_STAKE"]
    intersection = set(allowed_assets).intersection(set(disallowed))
    
    if not intersection:
        print("✅ PASS: SuperFund strictly excludes disallowed custody types.")
    else:
        print(f"❌ FAIL: SuperFund included disallowed assets: {intersection}")

def test_performance_math():
    print("\nTesting Performance Calculation Math...")
    # Mock some parcels with known cost and current price
    # BTC_COLD price in DATA is ~133k. Let's cost it at 100k for +33% pnl.
    from investment_planner import run_portfolio_optimizer, DATA
    
    price_now = DATA["BTC_COLD"][0]
    cost_basis = price_now / 1.5 # 50% gain
    
    parcels = [("BTC_COLD", 1.0, cost_basis, "2023-01-01", None)] # >12m for CGT+
    mock_risk = {"BTC_COLD": {"risk": 0.5, "momentum": 0.0}}
    
    df, _ = run_portfolio_optimizer("Test", "General", parcels, 0, mock_risk)
    
    btc_row = df[df['Asset'] == 'BTC_COLD'].iloc[0]
    pnl = btc_row['PnL']
    tax = btc_row['TAX']
    
    if "+50.0%" in pnl:
        print("✅ PASS: PnL math is correct.")
    else:
        print(f"❌ FAIL: PnL math incorrect. Got {pnl}")
        
    if "✅ CGT+ (12m)" in tax:
        print("✅ PASS: CGT 12-month rule detected correctly.")
    else:
        print(f"❌ FAIL: CGT status incorrect. Got {tax}")

if __name__ == "__main__":
    print(f"{'='*60}")
    print(" SYSTEM QA & INTEGRATION TEST SUITE")
    print(f"{'='*60}")
    test_db_constraints()
    test_entity_logic()
    test_performance_math()
    print(f"{'='*60}")
