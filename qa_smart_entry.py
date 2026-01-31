import pandas as pd
import numpy as np
from backtest_strategy import run_backtest_v3, run_backtest_v5

def compare_strategies(ticker="SDR.AX"):
    print(f"\n{'='*80}")
    print(f" COMPARING STRATEGIES FOR {ticker}")
    print(f"{'='*80}")
    
    # Run v3
    print("Running v3 (Blind Entry)...")
    res_v3 = run_backtest_v3(ticker)
    if not res_v3:
        print("v3 Failed (Insufficient Data?)")
        return
        
    # Run v5
    print("Running v5 (Hybrid)...")
    res_v5 = run_backtest_v5(ticker)
    if not res_v5:
        print("v5 Failed (Insufficient Data?)")
        return

    # metrics keys: cagr, sharpe, max_dd, bh_cagr, bh_max_dd
    
    print(f"\nMETRIC COMPARISON:")
    print(f"{'Metric':<15} | {'v3 (Blind)':<15} | {'v5 (Hybrid)':<15} | {'Diff':<10}")
    print("-" * 65)
    
    for k in ['cagr', 'max_dd', 'sharpe']:
        v3_val = res_v3.get(k, 0)
        v5_val = res_v5.get(k, 0)
        diff = v5_val - v3_val
        
        fmt = ".2%" if k in ['cagr', 'max_dd'] else ".2f"
        
        # Prepare strings
        s_v3 = f"{v3_val:.2%}" if k in ['cagr', 'max_dd'] else f"{v3_val:.2f}"
        s_v4 = f"{v5_val:.2%}" if k in ['cagr', 'max_dd'] else f"{v5_val:.2f}"
        s_diff = f"{diff:+.2%}" if k in ['cagr', 'max_dd'] else f"{diff:+.2f}"
        
        print(f"{k:<15} | {s_v3:<15} | {s_v4:<15} | {s_diff:<10}")
        
    print("-" * 65)
    
    print("\nObservation:")
    if res_v5['cagr'] >= res_v3['cagr'] - 0.005: 
        print("✅ v5 matched/exceeded v3 returns.")
    else:
        print("❌ v5 lagged v3 returns.")
        
    if abs(res_v5['max_dd']) < abs(res_v3['max_dd'])+0.005:
         # Similar or better DD
        print("✅ v5 crash safety check passed.")
    else:
        print("❌ v5 had significantly worse drawdown.")

    print(f"{'='*80}\n")

if __name__ == "__main__":
    # Broad Test Suite
    targets = [
        "BTC-USD", "ETH-USD", # Crypto (Volatile)
        "GC=F", # Commodity (Safeish)
        "SDR.AX", "FANG.AX", # ASX Growth/Sat (Volatile)
        "MQG.AX", "FMG.AX", "BHP.AX", "RIO.AX", # ASX Core (Cyclical)
        "VGS.AX", "VAS.AX" # ETFs (Steady)
    ]
    
    results = []
    print(f"Starting Broad Sweep Backtest on {len(targets)} assets...")
    
    for t in targets:
        print(f"Testing {t}...")
        res = run_backtest_v5(t)
        if res:
            res['ticker'] = t
            # Calculate improvement vs Buy & Hold
            res['dd_improvement'] = abs(res['bh_max_dd']) - abs(res['max_dd'])
            results.append(res)
            
    # Calculate Overall "Engine Rating"
    if not results:
        print("No results found.")
        exit()
        
    df = pd.DataFrame(results)
    
    avg_dd_improvement = df['dd_improvement'].mean()
    win_rate = len(df[df['cagr'] > df['bh_cagr'] - 0.005]) / len(df) # Tolerance 0.5%
    avg_sharpe = df['sharpe'].mean()
    
    print("\n" + "="*80)
    print("STRATEGY v5 ENGINE AUDIT")
    print("-" * 80)
    print(df[['ticker', 'cagr', 'bh_cagr', 'max_dd', 'bh_max_dd', 'sharpe']].to_string(index=False))
    print("-" * 80)
    
    # Scoring Logic
    score = 7.0 # Base
    
    # 1. Safety Bonus (The "Falling Knife" prevention)
    if avg_dd_improvement > 0.10: score += 1.0 # Saved >10% drawdown on avg
    if avg_dd_improvement > 0.15: score += 1.0 # Saved >15% drawdown on avg
    
    # 2. Performance Check
    if win_rate > 0.7: score += 0.5 # Won on most assets
    if win_rate > 0.9: score += 0.5 # Won on almost all
    
    final_score = min(10.0, score)
    
    print(f"\nAverage Crash Protection: {avg_dd_improvement:.1%}")
    print(f"Win Rate vs Buy&Hold:     {win_rate:.0%}")
    print(f"Average Sharpe Ratio:     {avg_sharpe:.2f}")
    print(f"\nFINAL ENGINE RATING: {final_score}/10")
    print("="*80 + "\n")
