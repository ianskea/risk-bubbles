import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
from enhanced_risk_analyzer import analyze_asset
from sector_config import SECTOR_INTELLIGENCE


THRESHOLD_GRID = [round(x, 2) for x in np.arange(0.55, 0.96, 0.05)]


def prepare_backtest_frame(ticker, years=5):
    try:
        df, _, meta = analyze_asset(ticker)
    except Exception as e:
        return None, f"Error loading {ticker}: {e}"

    if meta.get("reason"):
        return None, meta["reason"]

    if df.empty:
        return None, "no data returned"

    if not isinstance(df.index, pd.DatetimeIndex):
        return None, f"expected DatetimeIndex, got {type(df.index).__name__}"

    required_cols = {"Close", "sma_20d", "risk_total"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        return None, f"missing columns {sorted(missing_cols)}"

    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df.index >= start_date].copy()
    if len(df) < 150:
        return None, f"insufficient backtest rows ({len(df)} < 150)"

    return df, None


def run_strategy_on_frame(df, exit_threshold, fee=0.001):
    df = df.copy()

    # Simulation Logic (v2.1 with Momentum Stop)
    positions = []
    risk_col = 'risk_total'
    
    for i in range(len(df)):
        risk = df[risk_col].iloc[i]
        price = df['Close'].iloc[i]
        sma_20 = df['sma_20d'].iloc[i]
        
        # v2.1 Logic:
        # If risk > exit_threshold:
        #    If price > sma_20 -> Hold (Riding the bubble) -> 1.0
        #    If price < sma_20 -> Trend Broken, Cut to Moonbag -> 0.2
        # If risk < 0.30 -> Boost -> 1.4
        # Else -> Base -> 1.0
        
        if risk > exit_threshold:
            if price > sma_20:
                pos = 1.0 # Riding Bubble
            else:
                pos = 0.2 # Trend Broken
        elif risk < 0.30:
            pos = 1.4
        else:
            pos = 1.0
            
        positions.append(pos)

    df['position'] = positions
    df['trade'] = df['position'].diff().abs().fillna(0)
    df['raw_ret'] = df['Close'].pct_change()
    df['strat_ret'] = (df['position'].shift(1) * df['raw_ret']) - (df['trade'] * fee)
    
    # Cumulative returns
    df['bh_cum'] = (1 + df['raw_ret']).cumprod()
    df['strat_cum'] = (1 + df['strat_ret']).cumprod()
    
    # Metrics
    final_strat = df['strat_cum'].iloc[-1]
    final_bh = df['bh_cum'].iloc[-1]
    alpha = final_strat - final_bh
    
    peak = df['strat_cum'].cummax()
    max_dd = ((df['strat_cum'] - peak) / peak).min()
    
    bh_peak = df['bh_cum'].cummax()
    bh_max_dd = ((df['bh_cum'] - bh_peak) / bh_peak).min()
    
    return {
        "final_strat": final_strat,
        "final_bh": final_bh,
        "alpha": alpha,
        "max_dd": max_dd,
        "bh_max_dd": bh_max_dd,
        "protection": (abs(bh_max_dd) - abs(max_dd)) * 100,
    }


def format_backtest_result(ticker, sector_name, metrics):
    return {
        "Ticker": ticker,
        "Sector": sector_name,
        "v2_Return": f"{metrics['final_strat']:.2f}x",
        "B&H_Return": f"{metrics['final_bh']:.2f}x",
        "Alpha": f"{metrics['alpha']:+.2f}x",
        "v2_DD": f"{metrics['max_dd']*100:.1f}%",
        "B&H_DD": f"{metrics['bh_max_dd']*100:.1f}%",
        "Protection": f"{metrics['protection']:+.1f}%"
    }


def backtest_v2_logic(ticker, sector_name, exit_threshold, years=5, fee=0.001):
    df, reason = prepare_backtest_frame(ticker, years=years)
    if reason:
        print(f"  Skipping {ticker}: {reason}")
        return None

    metrics = run_strategy_on_frame(df, exit_threshold, fee=fee)
    return format_backtest_result(ticker, sector_name, metrics)


def summarize_numeric_results(metrics):
    if not metrics:
        return None

    alphas = [m["alpha"] for m in metrics]
    protections = [m["protection"] for m in metrics]
    return {
        "assets": len(metrics),
        "avg_alpha": sum(alphas) / len(alphas),
        "avg_protection": sum(protections) / len(protections),
        "success_rate": len([alpha for alpha in alphas if alpha > 0]) / len(alphas) * 100,
    }


def optimize_sector_thresholds(prepared_assets, fee=0.001):
    recommendations = []

    for sector_name, assets in prepared_assets.items():
        if not assets:
            continue

        sector_results = []
        for threshold in THRESHOLD_GRID:
            metrics = [
                run_strategy_on_frame(df, threshold, fee=fee)
                for _, df in assets
            ]
            summary = summarize_numeric_results(metrics)
            if not summary:
                continue

            # Blend return alpha and drawdown protection. Protection is a
            # percentage, so divide by 100 to put it on a return-multiple scale.
            score = summary["avg_alpha"] + (summary["avg_protection"] / 100)
            sector_results.append({
                "Sector": sector_name,
                "Threshold": threshold,
                "Assets": summary["assets"],
                "Avg Alpha": summary["avg_alpha"],
                "Avg Protection": summary["avg_protection"],
                "Success Rate": summary["success_rate"],
                "Score": score,
            })

        if sector_results:
            recommendations.append(max(sector_results, key=lambda row: row["Score"]))

    return recommendations


def run_suite():
    print(f"\n{'='*80}")
    print(f" INSTITUTIONAL QA & MULTI-MARKET BACKTEST (v2.1 Momentum Stop)")
    print(f" Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*80}")
    
    results = []
    prepared_assets = {}
    skipped = 0
    
    for sector_name, sector_data in SECTOR_INTELLIGENCE.items():
        exit_t = sector_data.get("danger_zone_threshold", 0.8)
        prepared_assets[sector_name] = []
        
        for name, ticker in sector_data["assets"].items():
            print(f"Testing {ticker} ({sector_name})...")
            df, reason = prepare_backtest_frame(ticker)
            if reason:
                print(f"  Skipping {ticker}: {reason}")
                skipped += 1
                continue

            prepared_assets[sector_name].append((ticker, df))
            metrics = run_strategy_on_frame(df, exit_t)
            results.append(format_backtest_result(ticker, sector_name, metrics))
        
    res_df = pd.DataFrame(results)
    print("\n--- DETAILED QA REPORT ---")
    print(res_df.to_string(index=False))
    
    # Summary Insights
    if results:
        alphas = [float(x.replace('x', '')) for x in res_df['Alpha']]
        protections = [float(x.replace('%', '')) for x in res_df['Protection']]
        
        print(f"\n--- EXECUTIVE SUMMARY ---")
        print(f"Assets Validated:   {len(results)}")
        print(f"Avg Alpha vs Hold:  {sum(alphas)/len(alphas):+.2f}x")
        print(f"Avg DD Protection:  {sum(protections)/len(protections):+.1f}% improved")
        print(f"Success Rate:       {len([a for a in alphas if a > 0])/len(alphas)*100:.0f}% outperformance")
    else:
        print("\n--- EXECUTIVE SUMMARY ---")
        print("No assets validated. Check data/network availability before tuning thresholds.")
    print(f"Assets Skipped:     {skipped}")

    recommendations = optimize_sector_thresholds(prepared_assets)
    if recommendations:
        rec_df = pd.DataFrame(recommendations)
        rec_df["Avg Alpha"] = rec_df["Avg Alpha"].map(lambda x: f"{x:+.2f}x")
        rec_df["Avg Protection"] = rec_df["Avg Protection"].map(lambda x: f"{x:+.1f}%")
        rec_df["Success Rate"] = rec_df["Success Rate"].map(lambda x: f"{x:.0f}%")
        rec_df["Score"] = rec_df["Score"].map(lambda x: f"{x:+.2f}")
        print("\n--- THRESHOLD SWEEP RECOMMENDATIONS ---")
        print(rec_df.to_string(index=False))

    print(f"{'='*80}\n")

if __name__ == "__main__":
    run_suite()
