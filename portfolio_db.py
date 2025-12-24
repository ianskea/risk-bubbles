import sqlite3
import os
from datetime import datetime

DB_PATH = "private/portfolio.sqlite"

def init_db():
    """Initializes the database and seeds initial entities if empty."""
    os.makedirs("private", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Entities Table (Hardened with CHECK constraint for specific names)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL CHECK (name IN ('Aegirs Fire SuperFund', 'Ocean Embers')),
            type TEXT NOT NULL CHECK (type IN ('SuperFund', 'General'))
        )
    ''')

    # Assets Table (Dynamic Registry)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            ticker TEXT PRIMARY KEY,
            tier TEXT NOT NULL,
            proxy TEXT,
            base_weight REAL NOT NULL,
            min_weight REAL,
            max_weight REAL,
            exit_threshold REAL,
            reduce_threshold REAL,
            moonbag_base REAL,
            est_yield REAL DEFAULT 0,
            custody_type TEXT,
            asset_type TEXT
        )
    ''')

    # Parcels Table (Refactored to use Foreign Key to assets.ticker)
    cursor.execute('DROP TABLE IF EXISTS parcels') # Recreate to remove hardcoded CHECK
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parcels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            asset_ticker TEXT NOT NULL,
            quantity REAL NOT NULL,
            cost_aud REAL NOT NULL,
            purchase_date DATE NOT NULL,
            expiry_date DATE,
            FOREIGN KEY (entity_id) REFERENCES entities (id),
            FOREIGN KEY (asset_ticker) REFERENCES assets (ticker)
        )
    ''')

    # Snapshots Table (Performance History)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            total_value REAL NOT NULL,
            total_pnl REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entity_id) REFERENCES entities (id)
        )
    ''')

    # Seed Default Entities
    entities = [
        ("Aegirs Fire SuperFund", "SuperFund"),
        ("Ocean Embers", "General")
    ]
    cursor.executemany("INSERT OR IGNORE INTO entities (name, type) VALUES (?, ?)", entities)
    
    conn.commit()
    conn.close()

def add_asset(ticker, tier, proxy, base_w, min_w=None, max_w=None, exit_t=None, reduce_t=None, moon_b=None, yield_pa=0, custody=None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO assets 
        (ticker, tier, proxy, base_weight, min_weight, max_weight, exit_threshold, reduce_threshold, moonbag_base, est_yield, custody_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, tier, proxy, base_w, min_w, max_w, exit_t, reduce_t, moon_b, yield_pa, custody))
    conn.commit()
    conn.close()

def get_asset_defs():
    """Returns a format compatible with investment_planner.py's DATA, RISK_PROXY_MAP, and ASSET_CONFIG."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM assets")
    rows = cursor.fetchall()
    conn.close()
    
    data_map = {}
    proxy_map = {}
    config_map = {}
    
    for r in rows:
        ticker, tier, proxy, base, mi, ma, ex, re, moon, yld, custody, _ = r
        # DATA: [PRICE_AUD, EST_YIELD_PA, CUSTODY_TYPE]
        data_map[ticker] = [1.0, yld, custody]
        proxy_map[ticker] = proxy
        config_map[ticker] = {
            "tier": tier, "base": base, "min": mi, "max": ma, 
            "exit": ex, "reduce": re, "moon": moon, "custody": custody
        }
    return data_map, proxy_map, config_map

def get_entity_info(name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, type FROM entities WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return row

def add_parcel(entity_name, asset, qty, cost, date_str, expiry_str=None):
    entity = get_entity_info(entity_name)
    if not entity: return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO parcels (entity_id, asset_ticker, quantity, cost_aud, purchase_date, expiry_date) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (entity[0], asset, qty, cost, date_str, expiry_str))
        conn.commit()
    except sqlite3.IntegrityError as e:
        print(f"Error adding parcel for {asset}: {e}")
        return False
    finally:
        conn.close()
    return True

def get_parcels(entity_name):
    entity = get_entity_info(entity_name)
    if not entity: return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT asset_ticker, quantity, cost_aud, purchase_date, expiry_date 
        FROM parcels 
        WHERE entity_id = ?
    """, (entity[0],))
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_snapshot(entity_name, total_val, total_pnl):
    entity = get_entity_info(entity_name)
    if not entity: return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO snapshots (entity_id, total_value, total_pnl) VALUES (?, ?, ?)", 
                   (entity[0], total_val, total_pnl))
    conn.commit()
    conn.close()
    return True

def seed_sample_data():
    """Seeds initial assets and sample parcels."""
    # Seed Assets from existing v2.0 logic
    initial_assets = [
        ("BTC_COLD", "CRYPTO", "BTC-USD", 0.18, 0.05, 0.30, 0.85, 0.75, 0.40, 0.000, "Cold Storage"),
        ("ETH_COLD", "CRYPTO", "ETH-USD", 0.10, 0.02, 0.20, 0.85, 0.75, 0.40, 0.000, "Cold Storage"),
        ("ETH_STAKE", "CRYPTO", "ETH-USD", 0.05, 0.02, 0.15, 0.85, 0.75, 0.40, 0.045, "Platform"),
        ("VGS", "CORE", "VGS.AX", 0.15, 0.05, 0.25, 0.80, 0.70, 0.20, 0.021, "Broker"),
        ("MQG", "CORE", "MQG.AX", 0.10, 0.05, 0.20, 0.80, 0.70, 0.20, 0.035, "Broker"),
        ("PAXG_NEXO", "CORE", "GC=F", 0.08, 0.02, 0.15, 0.78, 0.68, 0.25, 0.040, "Platform"),
        ("VAS", "SAT", "VAS.AX", 0.06, 0.00, 0.12, 0.75, 0.65, 0.25, 0.038, "Broker"),
        ("VAP", "SAT", "VAP.AX", 0.04, 0.00, 0.10, 0.75, 0.65, 0.25, 0.041, "Broker"),
        ("ADA_MINSWAP", "AGGR", "ADA-USD", 0.05, 0.00, 0.10, 0.85, 0.75, 0.40, 0.120, "DeFi"),
        ("USD_LEDN", "CASH", None, 0.10, 0.10, 0.10, 0.00, 0.00, 1.00, 0.070, "Platform"),
        ("USD_NEXO", "CASH", None, 0.07, 0.07, 0.07, 0.00, 0.00, 1.00, 0.100, "Platform"),
        ("JUDO_TD", "CASH", None, 0.07, 0.07, 0.07, 0.00, 0.00, 1.00, 0.050, "Bank")
    ]
    for a in initial_assets:
        add_asset(*a)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM parcels")
    if cursor.fetchone()[0] == 0:
        print("Seeding fresh sample parcels...")
        add_parcel("Ocean Embers", "BTC_COLD", 0.12, 12000, "2024-05-10")
        add_parcel("Ocean Embers", "PAXG_NEXO", 5.5, 20000, "2024-12-01")
        add_parcel("Ocean Embers", "MQG", 147, 28000, "2023-11-20") 
        add_parcel("Aegirs Fire SuperFund", "JUDO_TD", 56657, 56657, "2024-06-01", "2026-06-01")
        print("Sample parcels seeded.")
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
    seed_sample_data()
