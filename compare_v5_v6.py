import argparse
import json
import os
from datetime import datetime

import pandas as pd

from backtest_strategy import run_backtest_v5, run_backtest_v6


DEFAULT_TICKERS = [
    "BTC-USD",
    "ETH-USD",
    "GC=F",
    "BHP.AX",
    "FANG.AX",
    "SDR.AX",
    "NDQ.AX",
    "MQG.AX",
    "FMG.AX",
]


def fmt_pct(value):
    return "N/A" if pd.isna(value) else f"{value:.1%}"


def fmt_num(value):
    return "N/A" if pd.isna(value) else f"{value:.2f}"


def compare_ticker(ticker, years, initial_capital, fee):
    print(f"\nRunning {ticker}...")
    m5 = run_backtest_v5(ticker, years=years, initial_capital=initial_capital, fee=fee)
    m6 = run_backtest_v6(ticker, years=years, initial_capital=initial_capital, fee=fee)

    if not m5 or not m6:
        return {
            "ticker": ticker,
            "status": "skipped",
            "reason": "missing v5 or v6 result",
        }

    return {
        "ticker": ticker,
        "status": "ok",
        "v5_cagr": m5["cagr"],
        "v6_cagr": m6["cagr"],
        "delta_cagr": m6["cagr"] - m5["cagr"],
        "v5_max_dd": m5["max_dd"],
        "v6_max_dd": m6["max_dd"],
        "delta_max_dd": m6["max_dd"] - m5["max_dd"],
        "v5_sharpe": m5["sharpe"],
        "v6_sharpe": m6["sharpe"],
        "delta_sharpe": m6["sharpe"] - m5["sharpe"],
        "v6_tax_deferred_trims": m6.get("tax_deferred_trims", 0),
        "v6_cagr_win": m6["cagr"] > m5["cagr"],
        "v6_drawdown_win": m6["max_dd"] > m5["max_dd"],
        "v6_sharpe_win": m6["sharpe"] > m5["sharpe"],
    }


def build_summary(df):
    if df.empty or "status" not in df.columns:
        return {
            "ok_count": 0,
            "skipped_count": 0,
            "verdict": "No tickers were provided.",
        }

    ok = df[df["status"] == "ok"].copy()
    if ok.empty:
        return {
            "ok_count": 0,
            "skipped_count": int((df["status"] != "ok").sum()),
            "verdict": "No comparable results.",
        }

    summary = {
        "ok_count": int(len(ok)),
        "skipped_count": int((df["status"] != "ok").sum()),
        "avg_v5_cagr": float(ok["v5_cagr"].mean()),
        "avg_v6_cagr": float(ok["v6_cagr"].mean()),
        "avg_delta_cagr": float(ok["delta_cagr"].mean()),
        "avg_v5_max_dd": float(ok["v5_max_dd"].mean()),
        "avg_v6_max_dd": float(ok["v6_max_dd"].mean()),
        "avg_delta_max_dd": float(ok["delta_max_dd"].mean()),
        "avg_v5_sharpe": float(ok["v5_sharpe"].mean()),
        "avg_v6_sharpe": float(ok["v6_sharpe"].mean()),
        "avg_delta_sharpe": float(ok["delta_sharpe"].mean()),
        "v6_cagr_wins": int(ok["v6_cagr_win"].sum()),
        "v6_drawdown_wins": int(ok["v6_drawdown_win"].sum()),
        "v6_sharpe_wins": int(ok["v6_sharpe_win"].sum()),
    }

    score = 0
    score += summary["avg_delta_cagr"] > 0
    score += summary["avg_delta_max_dd"] > 0
    score += summary["avg_delta_sharpe"] > 0
    if score >= 2:
        summary["verdict"] = "v6 is better overall on this run."
    elif score == 1:
        summary["verdict"] = "mixed result; v6 is not clearly better."
    else:
        summary["verdict"] = "v5 is better overall on this run."

    return summary


def print_table(df, summary):
    if df.empty or "status" not in df.columns:
        print("\nSummary")
        print(f"Comparable assets: {summary['ok_count']}")
        print(f"Skipped assets:    {summary['skipped_count']}")
        print(f"Verdict:           {summary['verdict']}")
        return

    ok = df[df["status"] == "ok"].copy()
    skipped = df[df["status"] != "ok"].copy()

    if not ok.empty:
        print("\nTicker     | v5 CAGR | v6 CAGR | dCAGR  | v5 MaxDD | v6 MaxDD | dDD    | v5 Sh | v6 Sh | dSh")
        print("-" * 104)
        for _, row in ok.iterrows():
            print(
                f"{row['ticker']:<10} | "
                f"{fmt_pct(row['v5_cagr']):>7} | "
                f"{fmt_pct(row['v6_cagr']):>7} | "
                f"{fmt_pct(row['delta_cagr']):>6} | "
                f"{fmt_pct(row['v5_max_dd']):>8} | "
                f"{fmt_pct(row['v6_max_dd']):>8} | "
                f"{fmt_pct(row['delta_max_dd']):>6} | "
                f"{fmt_num(row['v5_sharpe']):>5} | "
                f"{fmt_num(row['v6_sharpe']):>5} | "
                f"{fmt_num(row['delta_sharpe']):>5}"
            )

    if not skipped.empty:
        print("\nSkipped:")
        for _, row in skipped.iterrows():
            print(f"- {row['ticker']}: {row['reason']}")

    print("\nSummary")
    print(f"Comparable assets: {summary['ok_count']}")
    print(f"Skipped assets:    {summary['skipped_count']}")
    if summary["ok_count"]:
        print(f"Avg v5 CAGR:       {fmt_pct(summary['avg_v5_cagr'])}")
        print(f"Avg v6 CAGR:       {fmt_pct(summary['avg_v6_cagr'])}")
        print(f"Avg dCAGR:         {fmt_pct(summary['avg_delta_cagr'])}")
        print(f"Avg v5 MaxDD:      {fmt_pct(summary['avg_v5_max_dd'])}")
        print(f"Avg v6 MaxDD:      {fmt_pct(summary['avg_v6_max_dd'])}")
        print(f"Avg dMaxDD:        {fmt_pct(summary['avg_delta_max_dd'])}")
        print(f"Avg v5 Sharpe:     {fmt_num(summary['avg_v5_sharpe'])}")
        print(f"Avg v6 Sharpe:     {fmt_num(summary['avg_v6_sharpe'])}")
        print(f"Avg dSharpe:       {fmt_num(summary['avg_delta_sharpe'])}")
        print(f"v6 CAGR wins:      {summary['v6_cagr_wins']}/{summary['ok_count']}")
        print(f"v6 DD wins:        {summary['v6_drawdown_wins']}/{summary['ok_count']}")
        print(f"v6 Sharpe wins:    {summary['v6_sharpe_wins']}/{summary['ok_count']}")
    print(f"Verdict:           {summary['verdict']}")


def write_outputs(df, summary, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(out_dir, f"v5_v6_comparison_{stamp}.csv")
    json_path = os.path.join(out_dir, f"v5_v6_comparison_{stamp}.json")
    txt_path = os.path.join(out_dir, f"v5_v6_summary_{stamp}.txt")

    df.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": df.to_dict(orient="records")}, f, indent=2, default=str)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, indent=2, default=str))
        f.write("\n")

    return csv_path, json_path, txt_path


def main():
    parser = argparse.ArgumentParser(description="Compare v5 and v6 backtest strategies.")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--initial-capital", type=float, default=10000)
    parser.add_argument("--fee", type=float, default=0.001)
    parser.add_argument("--out-dir", default=os.path.join("output", "backtests"))
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    args = parser.parse_args()

    rows = [
        compare_ticker(ticker, args.years, args.initial_capital, args.fee)
        for ticker in args.tickers
    ]
    df = pd.DataFrame(rows)
    summary = build_summary(df)
    print_table(df, summary)
    csv_path, json_path, txt_path = write_outputs(df, summary, args.out_dir)

    print("\nWrote:")
    print(f"- {csv_path}")
    print(f"- {json_path}")
    print(f"- {txt_path}")


if __name__ == "__main__":
    main()
