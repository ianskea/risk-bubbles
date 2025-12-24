import argparse
import sys
from datetime import datetime
import portfolio_db

def list_holdings(entity_name):
    parcels = portfolio_db.get_parcels(entity_name)
    if not parcels:
        print(f"No holdings found for '{entity_name}'.")
        return
    
    print(f"\n--- Current Parcels for {entity_name} ---")
    print(f"{'Asset':<15} {'Qty':<10} {'Cost (AUD)':<12} {'Purchased':<12} {'Expiry':<12}")
    print("-" * 65)
    for asset, qty, cost, p_date, e_date in parcels:
        e_date = e_date if e_date else "N/A"
        print(f"{asset:<15} {qty:<10.4f} ${cost:<11.2f} {p_date:<12} {e_date:<12}")

def add_holding(args):
    # Validate date
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("Error: Date must be in YYYY-MM-DD format.")
        return

    if args.expiry:
        try:
            datetime.strptime(args.expiry, "%Y-%m-%d")
        except ValueError:
            print("Error: Expiry must be in YYYY-MM-DD format.")
            return

    success = portfolio_db.add_parcel(
        args.entity, args.asset, args.qty, args.cost, args.date, args.expiry
    )
    if success:
        print(f"✅ Added {args.qty} {args.asset} to {args.entity}.")
    else:
        print(f"❌ Failed to add holding. Check if entity '{args.entity}' exists.")

def list_assets():
    data, proxies, configs = portfolio_db.get_asset_defs()
    if not configs:
        print("No assets found in registry.")
        return
    
    print(f"\n--- Institutional Asset Registry ---")
    print(f"{'Ticker':<12} {'Tier':<10} {'Proxy':<12} {'Base%':<8} {'Yield%':<8} {'Custody':<12}")
    print("-" * 75)
    for ticker, cfg in configs.items():
        yld = data[ticker][1]
        proxy = proxies[ticker] if proxies[ticker] else "None"
        print(f"{ticker:<12} {cfg['tier']:<10} {proxy:<12} {cfg['base']*100:<7.1f}% {yld*100:<7.1f}% {cfg['custody']:<12}")

def add_asset(args):
    portfolio_db.add_asset(
        args.ticker, args.tier, args.proxy, args.base, 
        args.min, args.max, args.exit, args.reduce, args.moon, 
        args.yield_pa, args.custody
    )
    print(f"✅ Registered asset '{args.ticker}' in the Institutional Registry.")

def clear_holdings(entity_name):
    import sqlite3
    entity = portfolio_db.get_entity_info(entity_name)
    if not entity:
        print(f"Entity '{entity_name}' not found.")
        return
    
    confirm = input(f"Are you sure you want to delete ALL parcels for '{entity_name}'? (y/n): ")
    if confirm.lower() == 'y':
        conn = sqlite3.connect(portfolio_db.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM parcels WHERE entity_id = ?", (entity[0],))
        conn.commit()
        conn.close()
        print(f"✅ Cleared all holdings for '{entity_name}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Portfolio Holdings & Asset Registry Manager")
    subparsers = parser.add_subparsers(dest="command")

    # List Holdings
    list_p = subparsers.add_parser("list", help="List holdings for an entity")
    list_p.add_argument("--entity", required=True, help="Entity name")

    # Add Parcel
    add_p = subparsers.add_parser("add", help="Add a new investment parcel")
    add_p.add_argument("--entity", required=True, help="Entity name")
    add_p.add_argument("--asset", required=True, help="Asset ticker")
    add_p.add_argument("--qty", type=float, required=True, help="Quantity")
    add_p.add_argument("--cost", type=float, required=True, help="Total cost in AUD")
    add_p.add_argument("--date", required=True, help="Purchase date (YYYY-MM-DD)")
    add_p.add_argument("--expiry", help="Expiry date (YYYY-MM-DD)")

    # Asset Registry Commands
    asset_list_p = subparsers.add_parser("list-assets", help="List all registered assets")
    
    asset_add_p = subparsers.add_parser("add-asset", help="Register a new asset ticker")
    asset_add_p.add_argument("--ticker", required=True)
    asset_add_p.add_argument("--tier", required=True, help="CRYPTO, CORE, SAT, AGGR, or CASH")
    asset_add_p.add_argument("--proxy", help="YFinance proxy (e.g., BTC-USD)")
    asset_add_p.add_argument("--base", type=float, required=True, help="Base target weight (e.g., 0.15)")
    asset_add_p.add_argument("--min", type=float, help="Min weight")
    asset_add_p.add_argument("--max", type=float, help="Max weight")
    asset_add_p.add_argument("--exit", type=float, help="Risk exit threshold")
    asset_add_p.add_argument("--reduce", type=float, help="Risk reduce threshold")
    asset_add_p.add_argument("--moon", type=float, help="Moonbag multiplier")
    asset_add_p.add_argument("--yield_pa", type=float, default=0.0, help="Est yield (e.g., 0.05)")
    asset_add_p.add_argument("--custody", help="Cold Storage, Broker, Platform, etc.")

    # Clear
    clear_p = subparsers.add_parser("clear", help="Clear all holdings for an entity")
    clear_p.add_argument("--entity", required=True, help="Entity name")

    args = parser.parse_args()

    if args.command == "list":
        list_holdings(args.entity)
    elif args.command == "add":
        add_holding(args)
    elif args.command == "list-assets":
        list_assets()
    elif args.command == "add-asset":
        add_asset(args)
    elif args.command == "clear":
        clear_holdings(args.entity)
    else:
        parser.print_help()
