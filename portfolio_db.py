import sqlite3
import os
from datetime import datetime

DB_PATH = "private/portfolio.sqlite"

def init_db():
    """Initializes the database and seeds initial entities if empty."""
    os.makedirs("private", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Entities Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('SuperFund', 'General'))
        )
    ''')

    # Parcels Table (Cost Basis Tracking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parcels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            asset_ticker TEXT NOT NULL,
            quantity REAL NOT NULL,
            cost_aud REAL NOT NULL,
            purchase_date DATE NOT NULL,
            expiry_date DATE,
            FOREIGN KEY (entity_id) REFERENCES entities (id)
        )
    ''')
    
    # Migration: Add expiry_date if it doesn't exist (handle existing DBs)
    try:
        cursor.execute("ALTER TABLE parcels ADD COLUMN expiry_date DATE")
    except sqlite3.OperationalError:
        pass # Already exists

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
    cursor.execute("""
        INSERT INTO parcels (entity_id, asset_ticker, quantity, cost_aud, purchase_date, expiry_date) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (entity[0], asset, qty, cost, date_str, expiry_str))
    conn.commit()
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

def get_holdings_aggregated(entity_name):
    """Returns {asset: total_qty}."""
    parcels = get_parcels(entity_name)
    aggregated = {}
    for asset, qty, cost, date, expiry in parcels:
        aggregated[asset] = aggregated.get(asset, 0) + qty
    return aggregated

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
    """Seeds sample parcels if the database is empty."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if we have any parcels already
    cursor.execute("SELECT COUNT(*) FROM parcels")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("Seeding fresh sample parcels...")
        add_parcel("Ocean Embers", "BTC_COLD", 0.12, 12000, "2024-05-10")
        add_parcel("Ocean Embers", "PAXG_NEXO", 5.5, 20000, "2024-12-01")
        add_parcel("Ocean Embers", "MQG", 147, 28000, "2023-11-20") # > 1 year
        
        # Added expiry date for JUDO_TD (June 2026)
        add_parcel("Aegirs Fire SuperFund", "JUDO_TD", 56657, 56657, "2024-06-01", "2026-06-01")
        print("Sample parcels seeded.")
    else:
        # Check if Judo TD specifically needs an expiry update
        cursor.execute("UPDATE parcels SET expiry_date = '2026-06-01' WHERE asset_ticker = 'JUDO_TD' AND expiry_date IS NULL")
        conn.commit()

    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
    seed_sample_data()
