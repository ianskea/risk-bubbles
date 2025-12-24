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
    parser = argparse.ArgumentParser(description="Portfolio Holdings Manager")
    subparsers = parser.add_subparsers(dest="command")

    # List
    list_parser = subparsers.add_parser("list", help="List holdings for an entity")
    list_parser.add_argument("--entity", required=True, help="Entity name (e.g., 'Ocean Embers')")

    # Add
    add_parser = subparsers.add_parser("add", help="Add a new investment parcel")
    add_parser.add_argument("--entity", required=True, help="Entity name")
    add_parser.add_argument("--asset", required=True, help="Asset ticker (e.g., BTC_COLD, VGS, MQG)")
    add_parser.add_argument("--qty", type=float, required=True, help="Quantity purchased")
    add_parser.add_argument("--cost", type=float, required=True, help="Total cost in AUD")
    add_parser.add_argument("--date", required=True, help="Purchase date (YYYY-MM-DD)")
    add_parser.add_argument("--expiry", help="Expiry date for Term Deposits (YYYY-MM-DD)")

    # Clear
    clear_parser = subparsers.add_parser("clear", help="Clear all holdings for an entity")
    clear_parser.add_argument("--entity", required=True, help="Entity name")

    args = parser.parse_args()

    if args.command == "list":
        list_holdings(args.entity)
    elif args.command == "add":
        add_holding(args)
    elif args.command == "clear":
        clear_holdings(args.entity)
    else:
        parser.print_help()
