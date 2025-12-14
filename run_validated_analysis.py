
import sys
import pandas as pd
from enhanced_risk_analyzer import analyze_asset
from model_validation import validate_model, generate_validation_report_text

def run_menu():
    print("""
    =============================================
    INSTITUTIONAL RISK ANALYSIS - VALIDATION SUITE
    =============================================
    1. Full Validation Suite (5 Core Assets)
    2. Single Asset Validation
    3. Quick Check (Single Asset Analysis)
    4. Exit
    """)
    choice = input("Select Option (1-4): ")
    return choice

def run_suite():
    assets = ["BTC-USD", "ETH-USD", "GC=F", "SPY", "BHP.AX"]
    print(f"\nRunning Validation on Core Basket: {assets}")
    
    results = []
    for ticker in assets:
        print(f"\n--- Processing {ticker} ---")
        try:
            df, _, _ = analyze_asset(ticker)
            if df.empty:
                print(f"Skipping {ticker} (No Data)")
                continue
                
            metrics = validate_model(df)
            print(generate_validation_report_text(ticker, metrics))
            results.append(metrics.get('score', 0))
        except Exception as e:
            print(f"Error validating {ticker}: {e}")
            
    if results:
        avg_score = sum(results) / len(results)
        print(f"\n=============================================")
        print(f"SYSTEM AGGREGATE SCORE: {avg_score:.1f}/100")
        print(f"=============================================")
    else:
        print("No results generated.")

def run_single_validation():
    ticker = input("Enter Ticker Symbol (e.g., BTC-USD, AAPL): ").strip().upper()
    print(f"Validating {ticker}...")
    try:
        df, _, _ = analyze_asset(ticker)
        if df.empty:
            print("No data found.")
            return
        
        metrics = validate_model(df)
        print(generate_validation_report_text(ticker, metrics))
    except Exception as e:
        print(f"Error: {e}")

def run_quick_check():
    ticker = input("Enter Ticker Symbol: ").strip().upper()
    print(f"Analyzing {ticker}...")
    try:
        df, _, meta = analyze_asset(ticker)
        if df.empty:
            print("No data found.")
            return
            
        last = df.iloc[-1]
        print("\n--------------------------------")
        print(f"Asset: {ticker}")
        print(f"Price: {last['Close']:.2f}")
        print(f"Risk:  {last['risk_total']:.2f} ({meta.get('rating')})")
        print("--------------------------------")
        print("Factors:")
        print(f"  Valuation: {last['risk_valuation']:.2f}")
        print(f"  Momentum:  {last['risk_momentum']:.2f}")
        print(f"  Volatility:{last['risk_volatility']:.2f}")
        print("--------------------------------")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    while True:
        c = run_menu()
        if c == '1':
            run_suite()
        elif c == '2':
            run_single_validation()
        elif c == '3':
            run_quick_check()
        elif c == '4':
            print("Exiting.")
            sys.exit(0)
        else:
            print("Invalid option.")
