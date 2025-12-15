
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from enhanced_risk_analyzer import analyze_asset

def run_backtest(ticker, years=4, initial_capital=10000):
    print(f"Backtesting {ticker} for last {years} years...")
    
    # 1. Get Data & Risk
    df, _, _ = analyze_asset(ticker)
    
    # Filter for last N years
    # Assuming daily data approx 252 trading days per year, crypto is 365
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    
    if df.empty:
        print("Not enough data.")
        return

    # 2. Define Strategy
    # Rule:
    # - Buy/Hold when Risk < 0.4
    # - Reduce/Sell when Risk > 0.75
    # Simplified logic: 
    # Position = 1 (100% Invested) if Risk < 0.6
    # Position = 0 (Cash) if Risk > 0.8
    # Sliding scale? 
    # Let's use the README traffic light logic:
    # < 0.4: Buy (100%)
    # > 0.75: Sell (0%)
    # In between: Hold previous position
    
    df['position'] = np.nan
    # Buy Zone
    df.loc[df['risk_total'] < 0.4, 'position'] = 1.0
    
    # Sell Zone (With Moonbag)
    # User feedback: "Buy and Hold worked best".
    # Solution: Never sell 100% in a bull market. Keep a "Moonbag" (30%) to catch the mania spike.
    # Ben Cowen also suggests "Scale out", not "Exit all".
    df.loc[df['risk_total'] > 0.75, 'position'] = 0.3
    
    # Forward fill position (Hold previous state between signals)
    df['position'] = df['position'].ffill().fillna(0.3) # Start conservative if unknown
    
    # 3. Calculate Returns
    df['pct_change'] = df['Close'].pct_change()
    
    # Strategy Return
    df['strat_ret'] = df['position'].shift(1) * df['pct_change']
    
    # Cumulative Returns
    df['bh_value'] = initial_capital * (1 + df['pct_change']).cumprod()
    df['strat_value'] = initial_capital * (1 + df['strat_ret']).cumprod()
    
    # --- Drawdown Analysis ---
    # Buy & Hold Drawdown
    bh_peak = df['bh_value'].cummax()
    bh_dd = (df['bh_value'] - bh_peak) / bh_peak
    bh_max_dd = bh_dd.min()
    
    # Strategy Drawdown
    strat_peak = df['strat_value'].cummax()
    strat_dd = (df['strat_value'] - strat_peak) / strat_peak
    strat_max_dd = strat_dd.min()
    
    # Stats
    final_bh = df['bh_value'].iloc[-1]
    final_strat = df['strat_value'].iloc[-1]
    
    bh_ret = (final_bh - initial_capital) / initial_capital
    strat_ret = (final_strat - initial_capital) / initial_capital
    
    print("\n--- RESULTS (MOONBAG 30%) ---")
    print(f"Initial Investment: ${initial_capital:,.2f}")
    print(f"Buy & Hold Final:   ${final_bh:,.2f} (+{bh_ret*100:.1f}%) | Max Drawdown: {bh_max_dd*100:.1f}%")
    print(f"Strategy Final:     ${final_strat:,.2f} (+{strat_ret*100:.1f}%) | Max Drawdown: {strat_max_dd*100:.1f}%")
    
    if final_strat > final_bh:
        print(f"🏆 Strategy OUTPERFORMED by {strat_ret - bh_ret:.1%}")
    else:
        print(f"Strategy Underperformed by {strat_ret - bh_ret:.1%}")
    
    print(f"Risk Adjusted Return Ratio (Ret/DD):")
    print(f"B&H: {abs(bh_ret/bh_max_dd):.2f} | Strategy: {abs(strat_ret/strat_max_dd):.2f}")

    # Trades
    trades = df['position'].diff().abs()
    num_trades = trades[trades > 0].sum()
    print(f"Total Trades: {int(num_trades)}")
    
    return df

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "BTC-USD"
    run_backtest(ticker)
