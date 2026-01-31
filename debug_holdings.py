
import portfolio_db
import sqlite3
import yfinance as yf
import os

def debug_holdings():
    portfolio_db.init_db()
    
    print(f"DB Path: {os.path.abspath(portfolio_db.DB_PATH)}")
    
    if os.path.exists(portfolio_db.DB_PATH):
        print(f"DB File Exists. Size: {os.path.getsize(portfolio_db.DB_PATH)} bytes")
    else:
        print("DB File DOES NOT EXIST")
    
    ent = portfolio_db.get_entity_info("Ocean Embers")
    print(f"Entity Info for 'Ocean Embers': {ent}")
    
    ent = portfolio_db.get_entity_info("Ocean Embers")
    print(f"Entity Info for 'Ocean Embers': {ent}")
    
    conn = sqlite3.connect(portfolio_db.DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM parcels WHERE entity_id = 2")
    rows = cur.fetchall()
    print(f"RAW SQL (entity_id=2): Found {len(rows)} rows")
    for r in rows:
        print(r)
    conn.close()

    # Check Parcels via Function
    print("=== RAW PARCELS (Ocean Embers) ===")
    parcels = portfolio_db.get_parcels("Ocean Embers")
    total_q = {}
    for p in parcels:
        # asset_ticker, quantity, cost_aud, purchase_date, expiry_date
        asset = p[0]
        qty = p[1]
        print(f"Parcel: {asset}, Qty: {qty}, Cost: {p[2]}, Date: {p[3]}")
        total_q[asset] = total_q.get(asset, 0) + qty
        
    print("\n=== TOTAL QUANTITIES ===")
    for a, q in total_q.items():
        print(f"{a}: {q}")
        
    # Check Prices
    print("\n=== PRICE CHECK ===")
    tickers = ["FANG.AX", "SDR.AX", "MQG.AX"]
    for t in tickers:
        try:
            tic = yf.Ticker(t)
            price = tic.fast_info['last_price']
            print(f"{t}: ${price}")
            
            # Check Value
            if t in total_q:
                val = total_q[t] * price
                print(f" -> Implied Value: ${val:,.2f}")
        except Exception as e:
            print(f"{t}: Error {e}")

if __name__ == "__main__":
    debug_holdings()
