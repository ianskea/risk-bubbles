# 🚀 Institutional Risk Intelligence & Portfolio Management

A statistically validated, multi-entity portfolio management system with risk-adaptive rebalancing, performance tracking, and tax-aware planning.

---

## 🏛️ Core Components

| Component | Purpose | Command |
|-----------|---------|---------|
| **Market Intelligence** | Risk analysis, AI insights & bubble detection | `./venv/bin/python3 enhanced_main.py` |
| **Portfolio Planner** | Multi-entity rebalancing & action list | `./venv/bin/python3 investment_planner.py` |
| **Asset Manager** | Manage holdings & asset registry | `./venv/bin/python3 manage_holdings.py` |
| **Backtest Engine** | Stress test logic across historical cycles | `./venv/bin/python3 backtest_strategy.py` |

---

## 📅 Institutional Cadence (Routine)

### 1. Weekly Intelligence (Market Awareness)
**Command**: `./venv/bin/python3 enhanced_main.py`  
Identify assets moving toward "Danger Zones" or "Value Zones." Review AI-generated risk reports.

### 2. Monthly Execution (Capital Deployment)
**Command**: `./venv/bin/python3 investment_planner.py --entity "Ocean Embers"`  
Generate specific rebalance actions (BUY/SELL) for your monthly DCA and rebalancing.

### 3. Maintenance (As Needed)
**Command**: `./venv/bin/python3 manage_holdings.py list`  
Update your local database when you perform buys/sells to keep tracking data accurate.

---

## 🔒 Privacy & Persistence (Local SQLite)

All portfolio data is stored locally in `private/portfolio.sqlite`. This directory is **git-ignored** to ensure your holdings never leave your machine.

### Multi-Entity Tracking
The system supports distinct rules for different investment buckets:
- **Aegirs Fire SuperFund**: Enforces strict AUD/ASX/Cold-Storage rules.
- **Ocean Embers**: Full flexibility (Platforms/DeFi/International).

### Performance & Tax Tracking
- **Unrealized PnL**: Tracks price growth for every individual purchase parcel.
- **CGT Bonus (12m)**: Automatically flags assets held for >365 days that qualify for the Aussie capital gains discount.
- **Wealth Snapshots**: Automatically saves your total equity and profit history every time you run the planner.
- **TD Maturity**: Countdown timer for Term Deposits with expiry alerts.

---

## ⚙️ Management CLI (`manage_holdings.py`)

### Asset Registry (Add any Ticker)
You can extend the system to any market in seconds without touching code:
```bash
# Register a new asset (e.g. Gold)
./venv/bin/python3 manage_holdings.py add-asset --ticker "GOLD" --tier "COMMODITY" --proxy "GC=F" --base 0.10

# List valid registry assets
./venv/bin/python3 manage_holdings.py list-assets
```

### Loading Parcels
```bash
# Register a buy action
./venv/bin/python3 manage_holdings.py add --entity "Ocean Embers" --asset "BTC_COLD" --qty 0.5 --cost 62000 --date "2024-05-15"

# List current holdings
./venv/bin/python3 manage_holdings.py list --entity "Ocean Embers"
```

---

## 🛡️ Risk-Adaptive v2.0 Logic

| Asset Class | Risk Redline | Action at Redline |
|-------------|--------------|-------------------|
| **Crypto** | **> 0.85** | 🔴 EXIT to Moonbag (20-40%) |
| **Core Labels** | **> 0.80** | 🔴 REDUCE aggressively |
| **Commodities**| **> 0.75** | 🔴 REBALANCE to base |

---

## 🤖 Automation

Schedule native macOS alerts to keep you updated on market risk:
1. **Test it**: `./venv/bin/python3 macos_notifier.py`
2. **Add to Crontab**: `0 8 * * 1 /Users/ianskea/Sites/risk-bubbles/automated_report_cron.sh`

---

## ⚖️ Disclaimer
**Educational/Research purposes only.** Not financial advice. Past performance ≠ future results. Use the verification suite (`qa_backtest_suite.py`) to audit all logic before deployment.
