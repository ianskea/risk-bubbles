import argparse
import pandas as pd
import numpy as np
from itertools import product
from datetime import datetime
from enhanced_risk_analyzer import analyze_asset
from sector_config import SECTOR_INTELLIGENCE, get_sector_readiness


THRESHOLD_GRID = [round(x, 2) for x in np.arange(0.55, 0.96, 0.05)]
BUY_THRESHOLD_GRID = [0.15, 0.25, 0.30, 0.35]
MOONBAG_GRID = [0.0, 0.2, 0.4, 0.6]
BOOST_GRID = [1.0, 1.2, 1.4]
STOP_SMA_GRID = [20, 50]


def get_sector_strategy_params(sector_data):
    params = sector_data.get("strategy_params", {}).copy()
    params.setdefault("exit_threshold", sector_data.get("danger_zone_threshold", 0.8))
    params.setdefault("buy_threshold", 0.30)
    params.setdefault("moonbag_position", 0.2)
    params.setdefault("boost_position", 1.4)
    params.setdefault("stop_sma_days", 20)
    return params


STRATEGY_GRID_SIZE = (
    len(THRESHOLD_GRID)
    * len(BUY_THRESHOLD_GRID)
    * len(MOONBAG_GRID)
    * len(BOOST_GRID)
    * len(STOP_SMA_GRID)
)


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


def get_stop_sma(df, stop_sma_days):
    """Return a stop trend series, deriving it if the analyzer did not."""
    col = f"sma_{stop_sma_days}d"
    if col in df.columns:
        return df[col]
    return df["Close"].rolling(window=stop_sma_days, min_periods=max(2, stop_sma_days // 2)).mean()


def run_strategy_on_frame(
    df,
    exit_threshold,
    fee=0.001,
    buy_threshold=0.30,
    moonbag_position=0.2,
    boost_position=1.4,
    stop_sma_days=20,
):
    df = df.copy()
    stop_sma = get_stop_sma(df, stop_sma_days)

    risk = df["risk_total"]
    price = df["Close"]
    high_risk = risk > exit_threshold
    trend_broken = stop_sma.notna() & (price <= stop_sma)
    buy_zone = risk < buy_threshold

    df["position"] = np.select(
        [high_risk & trend_broken, buy_zone],
        [moonbag_position, boost_position],
        default=1.0,
    )
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


def strategy_parameter_grid():
    """Yield full strategy parameter combinations for sector optimization."""
    for exit_threshold, buy_threshold, moonbag, boost, stop_sma in product(
        THRESHOLD_GRID,
        BUY_THRESHOLD_GRID,
        MOONBAG_GRID,
        BOOST_GRID,
        STOP_SMA_GRID,
    ):
        yield {
            "exit_threshold": exit_threshold,
            "buy_threshold": buy_threshold,
            "moonbag_position": moonbag,
            "boost_position": boost,
            "stop_sma_days": stop_sma,
        }


def score_summary(summary):
    # Blend return alpha and drawdown protection. Protection is a percentage, so
    # divide by 100 to put it on a return-multiple scale.
    return summary["avg_alpha"] + (summary["avg_protection"] / 100)


def optimize_sector_strategy(prepared_assets, fee=0.001):
    recommendations = []

    for sector_name, assets in prepared_assets.items():
        if not assets:
            continue

        print(f"Optimizing {sector_name}: {STRATEGY_GRID_SIZE} parameter sets across {len(assets)} assets...")
        sector_results = []
        for params in strategy_parameter_grid():
            metrics = [
                run_strategy_on_frame(df, fee=fee, **params)
                for _, df in assets
            ]
            summary = summarize_numeric_results(metrics)
            if not summary:
                continue

            sector_results.append({
                "Sector": sector_name,
                "Exit": params["exit_threshold"],
                "Buy": params["buy_threshold"],
                "Moonbag": params["moonbag_position"],
                "Boost": params["boost_position"],
                "Stop SMA": params["stop_sma_days"],
                "Assets": summary["assets"],
                "Avg Alpha": summary["avg_alpha"],
                "Avg Protection": summary["avg_protection"],
                "Success Rate": summary["success_rate"],
                "Score": score_summary(summary),
            })

        if sector_results:
            recommendations.append(max(sector_results, key=lambda row: row["Score"]))

    return recommendations


def configured_sector_readiness(prepared_assets, sectors=None, tickers=None):
    readiness = []

    for sector_name, sector_data, assets in iter_selected_assets(sectors=sectors, tickers=tickers):
        metrics = sector_data.get("validation_metrics", {})
        readiness.append({
            "Sector": sector_name,
            "Readiness": get_sector_readiness(sector_data),
            "Configured Assets": len(assets),
            "Backtest Assets": metrics.get("assets", 0),
            "Loaded Assets": len(prepared_assets.get(sector_name, [])),
            "Avg Alpha": metrics.get("avg_alpha", 0),
            "Avg Protection": metrics.get("avg_protection", 0),
            "Success Rate": metrics.get("success_rate", 0),
            "Validated On": metrics.get("validated_on", "N/A"),
        })

    return readiness


def normalize_ticker(value):
    ticker = value.strip().upper()
    if ticker and "." not in ticker and "-" not in ticker and "=" not in ticker:
        ticker = f"{ticker}.AX"
    return ticker


def iter_selected_assets(sectors=None, tickers=None):
    selected_sectors = {sector.strip() for sector in sectors or []}
    selected_tickers = {normalize_ticker(ticker) for ticker in tickers or []}

    for sector_name, sector_data in SECTOR_INTELLIGENCE.items():
        if selected_sectors and sector_name not in selected_sectors:
            continue

        assets = {}
        for name, ticker in sector_data["assets"].items():
            if selected_tickers and ticker.upper() not in selected_tickers:
                continue
            assets[name] = ticker

        if assets:
            yield sector_name, sector_data, assets


def run_suite(sectors=None, tickers=None, run_sweeps=True):
    print(f"\n{'='*80}")
    print(f" INSTITUTIONAL QA & MULTI-MARKET BACKTEST (v2.1 Momentum Stop)")
    print(f" Date: {datetime.now().strftime('%Y-%m-%d')}")
    if sectors:
        print(f" Sectors: {', '.join(sectors)}")
    if tickers:
        print(f" Tickers: {', '.join(tickers)}")
    if not run_sweeps:
        print(" Sweeps: disabled")
    print(f"{'='*80}")
    
    results = []
    prepared_assets = {}
    skipped = 0
    
    for sector_name, sector_data, assets in iter_selected_assets(sectors=sectors, tickers=tickers):
        strategy_params = get_sector_strategy_params(sector_data)
        prepared_assets[sector_name] = []
        
        for name, ticker in assets.items():
            print(f"Testing {ticker} ({sector_name})...", flush=True)
            df, reason = prepare_backtest_frame(ticker)
            if reason:
                print(f"  Skipping {ticker}: {reason}")
                skipped += 1
                continue

            prepared_assets[sector_name].append((ticker, df))
            metrics = run_strategy_on_frame(df, **strategy_params)
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

    readiness = configured_sector_readiness(prepared_assets, sectors=sectors, tickers=tickers)
    if readiness:
        readiness_df = pd.DataFrame(readiness)
        readiness_df["Avg Alpha"] = readiness_df["Avg Alpha"].map(lambda x: f"{x:+.2f}x")
        readiness_df["Avg Protection"] = readiness_df["Avg Protection"].map(lambda x: f"{x:+.1f}%")
        readiness_df["Success Rate"] = readiness_df["Success Rate"].map(lambda x: f"{x:.0f}%")
        print("\n--- CONFIGURED SECTOR READINESS ---")
        print(readiness_df.to_string(index=False))

    if run_sweeps:
        recommendations = optimize_sector_thresholds(prepared_assets)
        if recommendations:
            rec_df = pd.DataFrame(recommendations)
            rec_df["Avg Alpha"] = rec_df["Avg Alpha"].map(lambda x: f"{x:+.2f}x")
            rec_df["Avg Protection"] = rec_df["Avg Protection"].map(lambda x: f"{x:+.1f}%")
            rec_df["Success Rate"] = rec_df["Success Rate"].map(lambda x: f"{x:.0f}%")
            rec_df["Score"] = rec_df["Score"].map(lambda x: f"{x:+.2f}")
            print("\n--- THRESHOLD SWEEP RECOMMENDATIONS ---")
            print(rec_df.to_string(index=False))

        strategy_recommendations = optimize_sector_strategy(prepared_assets)
        if strategy_recommendations:
            strategy_df = pd.DataFrame(strategy_recommendations)
            strategy_df["Avg Alpha"] = strategy_df["Avg Alpha"].map(lambda x: f"{x:+.2f}x")
            strategy_df["Avg Protection"] = strategy_df["Avg Protection"].map(lambda x: f"{x:+.1f}%")
            strategy_df["Success Rate"] = strategy_df["Success Rate"].map(lambda x: f"{x:.0f}%")
            strategy_df["Score"] = strategy_df["Score"].map(lambda x: f"{x:+.2f}")
            print("\n--- STRATEGY PARAMETER SWEEP RECOMMENDATIONS ---")
            print(strategy_df.to_string(index=False))

    print(f"{'='*80}\n")

def parse_args():
    parser = argparse.ArgumentParser(description="Run sector backtests and strategy sweeps.")
    parser.add_argument("--sector", action="append", dest="sectors", help="Limit to a sector name. Repeatable.")
    parser.add_argument("--ticker", action="append", dest="tickers", help="Limit to a ticker, e.g. HACK or HACK.AX. Repeatable.")
    parser.add_argument("--no-sweep", action="store_true", help="Skip threshold and strategy optimization sweeps.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_suite(sectors=args.sectors, tickers=args.tickers, run_sweeps=not args.no_sweep)
