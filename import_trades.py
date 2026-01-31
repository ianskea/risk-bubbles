
import portfolio_db
from datetime import datetime
import re

# Raw Data
raw_data = """
Date	Ticker	Amt	Buy	Buy-Fee	Cost	Target	Stop	ATR	ATR*1.5	Off-Stop	Sell-Fee	Sell-Target	Sell-Stop	Current-Price	USD/AUD
HOLD for Dividends															
															
AegirsFire															
24/02	ASX:MQG	87	231.280	9.5	20130.86	244	220			-8.14	9.5	21218.50	19121.00	211.86	AUD
28/02	ASX:MQG	88	227.880	9.5	20062.94	244	220			-8.14	9.5	21462.50	19341.00	211.86	AUD
12/11	ASX:FANG	531	37.710	9.5	20033.51	42	35.58			-1.46	9.5	22292.50	18873.98	34.12	AUD
14/01	ASX:FANG	577	34.690	9.5	20025.63	42	33			1.12	9.5	24224.50	19022.00	34.12	AUD
14/01	ASX:SDR	3402	5.880	9.5	20013.26	42	5			0.80	9.5	142874.50	16991.00	5.80	AUD
															
OceanEmbers															
24/02	ASX:MQG	87	231.280	9.5	20130.86	244	220			-8.14	9.5	21218.50	19121.00	211.86	AUD
28/02	ASX:MQG	88	227.560	9.5	20034.78	244	215			-3.14	9.5	21462.50	18901.00	211.86	AUD
12/11	ASX:FANG	531	37.710	9.5	20033.51	42	35.58			-1.46	9.5	22292.50	18873.98	34.12	AUD
14/01	ASX:FANG	577	34.690	9.5	20025.63	42	33			1.12	9.5	24224.50	19022.00	34.12	AUD
14/01	ASX:SDR	3402	5.880	9.5	20013.26	42	5			0.80	9.5	142874.50	16991.00	5.80	AUD
															
SWING	STOP on 50 day MA				200504.24										
"""

# Mappings
ENTITY_MAP = {
    "AegirsFire": "Aegirs Fire SuperFund",
    "OceanEmbers": "Ocean Embers"
}

def parse_ticker(t_str):
    if t_str.startswith("ASX:"):
        return t_str.replace("ASX:", "") + ".AX"
    return t_str

def parse_date(d_str):
    # Logic: d_str is dd/mm. 
    # Current date: 2026-01-17
    # If month > current_month -> previous year (2025)
    # If month <= current_month -> current year (2026)
    # If month is much anterior, maybe check if > current month logic holds.
    # 24/02 (Feb) > 01 (Jan) -> 2025.
    # 14/01 (Jan) <= 01 (Jan) -> 2026.
    # 12/11 (Nov) > 01 (Jan) -> 2025.
    
    current_year = 2026 # Hardcoded based on "latest source of truth for time" in prompt
    current_month = 1
    
    try:
        day, month = map(int, d_str.split('/'))
        if month > current_month:
            year = current_year - 1
        else:
            year = current_year
        
        return f"{year}-{month:02d}-{day:02d}"
    except:
        return None

def process_import():
    lines = raw_data.strip().split('\n')
    current_entity = None
    
    success_count = 0
    fail_count = 0
    
    # Initialize DB (safe to run multiple times)
    portfolio_db.init_db()
    
    # CLEAR EXISTING DATA
    print("Clearing existing parcels to ensure only latest trades are present...")
    conn = parse_ticker.__globals__['portfolio_db'].sqlite3.connect(parse_ticker.__globals__['portfolio_db'].DB_PATH)
    conn.execute("DELETE FROM parcels")
    conn.commit()
    conn.close()
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Check Entity Header
        if line in ENTITY_MAP:
            current_entity = ENTITY_MAP[line]
            print(f"Switched to Entity: {current_entity}")
            continue
            
        # Skip headers / garbage
        if "Date" in line or "HOLD" in line or "SWING" in line:
            continue
            
        # Parse Data Line
        # Expected: Date Ticker Amt Buy ...
        parts = re.split(r'\t+', line)
        if len(parts) < 6: 
            # Try spaces if tabs fail
            parts = line.split()
            if len(parts) < 6:
                continue
                
        # Indices based on TSV header:
        # 0: Date, 1: Ticker, 2: Amt, 3: Buy, 4: Buy-Fee, 5: Cost
        d_str = parts[0]
        ticker_raw = parts[1]
        amt_str = parts[2]
        cost_str = parts[5].replace(',', '') # Handle 20,130.86 if format exists
        
        date_iso = parse_date(d_str)
        if not date_iso: 
            continue
            
        ticker = parse_ticker(ticker_raw)
        
        try:
            qty = float(amt_str)
            cost_aud = float(cost_str)
        except ValueError:
            print(f"Skipping invalid numbers: {line}")
            continue
            
        if current_entity:
            print(f"Importing {ticker} ({qty}) for {current_entity} on {date_iso}")
            res = portfolio_db.add_parcel(current_entity, ticker, qty, cost_aud, date_iso)
            if res:
                success_count += 1
            else:
                print(f"Failed db insert: {line}")
                fail_count += 1
        else:
            print(f"Skipping line (no entity set): {line}")
            
    print(f"\nImport Complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    process_import()
