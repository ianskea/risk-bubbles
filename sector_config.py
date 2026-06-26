"""
Sector Intelligence Configuration.

Defines assets by sector, sector-specific thresholds, review metadata, and
lightweight validation helpers. Keep this module import-safe: anything that
fetches live data should run inside a function, not at import time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


DATE_FORMAT = "%Y-%m-%d"
MAX_REVIEW_AGE_DAYS = 30

# Date when the sector specifics were last reviewed.
LAST_UPDATED = "2026-06-26"

# Static fallback floors. Realized Price can be refreshed dynamically via
# get_btc_on_chain_floors(); Balance Price remains a manual cycle-level guard.
BTC_ON_CHAIN_FLOORS = {
    "Realized Price": 55000,
    "Balance Price": 40000,
}

BTC_ON_CHAIN_FLOOR_METADATA = {
    "Realized Price": {
        "source": "Coin Metrics Community API when available; static fallback otherwise.",
        "last_reviewed": LAST_UPDATED,
    },
    "Balance Price": {
        "source": "Manual on-chain/cycle floor estimate.",
        "last_reviewed": LAST_UPDATED,
    },
}

SECTOR_INTELLIGENCE = {
    "Crypto": {
        "danger_zone_threshold": 0.85,
        "fetch_santiment": True,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["global-liquidity", "btc-etf-flows", "on-chain", "usd"],
        "threshold_rationale": "Backtest sweep selected 0.85, but Crypto remains unvalidated: avg alpha -0.30x, avg protection -4.7%, 0% success rate.",
        "sector_context": "High-beta digital assets. Sensitive to global liquidity, ETF/treasury flows, USD strength, and on-chain valuation bands.",
        "assets": {
            "Bitcoin": "BTC-USD",
            "Ethereum": "ETH-USD",
            "Cardano": "ADA-USD",
        },
    },
    "Crypto_Rotations": {
        "danger_zone_threshold": 0.55,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["btc-dominance", "eth-btc", "altcoin-rotation"],
        "threshold_rationale": "Backtest sweep selected 0.55 as the least-bad rotation threshold: avg alpha -0.05x, avg protection -3.5%, 33% success rate.",
        "sector_context": "Crypto cross-pairs (Capital Waterfall). Tracks liquidity rotation from BTC into ETH and Alts. High risk means the altcoin cycle is exhausted against BTC.",
        "assets": {
            "ETH / BTC": "ETH-BTC",
            "ADA / BTC": "ADA-BTC",
            "ADA / ETH": "ADA-ETH",
        },
    },
    "Commodities": {
        "danger_zone_threshold": 0.85,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["real-yields", "usd", "inflation", "geopolitics"],
        "threshold_rationale": "Backtest sweep selected 0.85: roughly neutral avg alpha and drawdown protection, with no observed outperformance edge.",
        "sector_context": "Global hard assets. Driven by inflation expectations, real yields, USD strength, industrial demand, and geopolitical risk.",
        "assets": {
            "Gold": "GC=F",
            "Silver": "SI=F",
        },
    },
    "ASX_Miners": {
        "danger_zone_threshold": 0.55,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["china-demand", "iron-ore", "copper", "lithium", "aud-cny"],
        "threshold_rationale": "Backtest sweep selected 0.55: avg alpha +0.08x, avg protection -1.9%, 71% success rate.",
        "sector_context": "Australian Large-Cap Miners (ASX). Highly correlated to iron ore, copper, lithium demand, Chinese policy support, and AUD/CNY moves.",
        "assets": {
            "BHP Group": "BHP.AX",
            "Rio Tinto": "RIO.AX",
            "Fortescue": "FMG.AX",
            "Mineral Resources": "MIN.AX",
            "Pilbara Minerals": "PLS.AX",
            "South32": "S32.AX",
            "IGO Ltd": "IGO.AX",
        },
    },
    "ASX_Financials_Other": {
        "danger_zone_threshold": 0.85,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["rba-policy", "credit-growth", "housing", "domestic-demand"],
        "threshold_rationale": "Backtest sweep selected 0.85: avg alpha +0.09x, avg protection -4.6%, 67% success rate.",
        "sector_context": "Australian Financials and domestic large caps. Sensitive to RBA policy, mortgage stress, credit growth, and domestic demand.",
        "assets": {
            "Macquarie Group": "MQG.AX",
            "SiteMinder": "SDR.AX",
            "Telstra": "TLS.AX",
        },
    },
    "Global_Tech_ETFs": {
        "danger_zone_threshold": 0.80,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["us-yields", "ai-capex", "earnings-revisions", "valuation"],
        "threshold_rationale": "Backtest sweep selected 0.80: avg alpha +0.13x, avg protection -5.4%, 50% success rate.",
        "sector_context": "Global technology and semiconductor equities. Sensitive to US Treasury yields, AI CapEx durability, earnings revisions, and valuation crowding.",
        "assets": {
            "Global X Semi": "SEMI.AX",
            "Global X FANG+": "FANG.AX",
            "Global X Robots": "RBTZ.AX",
            "BetaShares NDQ": "NDQ.AX",
        },
    },
    "Regional_Equities_ETFs": {
        "danger_zone_threshold": 0.75,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["global-growth", "china-demand", "currency", "exports"],
        "threshold_rationale": "Backtest sweep selected 0.75 as the least-bad setting: avg alpha -0.07x, avg protection -7.1%, 33% success rate.",
        "sector_context": "Broad regional equities (Asia/Europe). Driven by global growth, regional fiscal policy, China demand, currency moves, and export cycles.",
        "assets": {
            "BetaShares Asia": "ASIA.AX",
            "Vanguard Europe": "VEQ.AX",
            "iShares Asia 50": "IAA.AX",
        },
    },
    "Thematic_Global_ETFs": {
        "danger_zone_threshold": 0.85,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["healthcare", "energy", "infrastructure", "capex"],
        "threshold_rationale": "Backtest sweep selected 0.85: avg alpha +0.04x, avg protection -3.2%, 75% success rate.",
        "sector_context": "Global thematic equities. Healthcare is defensive; energy and infrastructure are tied to capex cycles, power demand, and commodity volatility.",
        "assets": {
            "Battery Tech": "ACDC.AX",
            "Global Infrastructure": "IFRA.AX",
            "Global Healthcare": "IXJ.AX",
            "Global Energy": "FUEL.AX",
        },
    },
    "Aussie_Domestic_ETFs": {
        "danger_zone_threshold": 0.70,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["rba-policy", "property", "resources", "domestic-income"],
        "threshold_rationale": "Backtest sweep selected 0.70 as the least-bad setting: avg alpha near 0.00x, avg protection -3.9%, 50% success rate.",
        "sector_context": "Australian domestic sector ETFs. Property is rate and income sensitive; resources remain tied to China demand and commodity cycles.",
        "assets": {
            "BetaShares Mining Resources": "QRE.AX",
            "Vanguard Prop": "VAP.AX",
        },
    },
}


def parse_review_date(value: str) -> datetime:
    """Return a datetime for a YYYY-MM-DD review date."""
    return datetime.strptime(value, DATE_FORMAT)


def get_stale_sector_reviews(
    as_of: datetime | None = None,
    max_age_days: int = MAX_REVIEW_AGE_DAYS,
) -> dict[str, int]:
    """Return sector review ages that exceed the configured freshness window."""
    as_of = as_of or datetime.now()
    stale = {}

    for sector_name, sector_data in SECTOR_INTELLIGENCE.items():
        reviewed = parse_review_date(sector_data.get("last_reviewed", LAST_UPDATED))
        days_old = (as_of - reviewed).days
        if days_old > max_age_days:
            stale[sector_name] = days_old

    return stale


def validate_sector_intelligence(config: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """Return human-readable validation errors for the sector config."""
    if config is None:
        config = SECTOR_INTELLIGENCE
    errors = []
    if not config:
        return ["sector config must be a non-empty dict"]

    required_keys = {
        "danger_zone_threshold",
        "fetch_santiment",
        "last_reviewed",
        "source_tags",
        "threshold_rationale",
        "sector_context",
        "assets",
    }
    ticker_to_sector = {}

    for sector_name, sector_data in config.items():
        missing = required_keys - set(sector_data)
        if missing:
            errors.append(f"{sector_name}: missing keys {sorted(missing)}")

        threshold = sector_data.get("danger_zone_threshold")
        if not isinstance(threshold, (int, float)) or not 0 < threshold < 1:
            errors.append(f"{sector_name}: danger_zone_threshold must be between 0 and 1")

        if not isinstance(sector_data.get("fetch_santiment"), bool):
            errors.append(f"{sector_name}: fetch_santiment must be a bool")

        try:
            parse_review_date(sector_data.get("last_reviewed", ""))
        except (TypeError, ValueError):
            errors.append(f"{sector_name}: last_reviewed must use YYYY-MM-DD")

        for text_key in ("sector_context", "threshold_rationale"):
            if not str(sector_data.get(text_key, "")).strip():
                errors.append(f"{sector_name}: {text_key} must be non-empty")

        source_tags = sector_data.get("source_tags")
        if (
            not isinstance(source_tags, list)
            or not source_tags
            or not all(isinstance(tag, str) and tag for tag in source_tags)
        ):
            errors.append(f"{sector_name}: source_tags must be a non-empty list of strings")

        assets = sector_data.get("assets")
        if not isinstance(assets, dict) or not assets:
            errors.append(f"{sector_name}: assets must be a non-empty dict")
            continue

        for asset_name, ticker in assets.items():
            if not str(asset_name).strip() or not str(ticker).strip():
                errors.append(f"{sector_name}: asset names and tickers must be non-empty")
                continue

            prior_sector = ticker_to_sector.get(ticker)
            if prior_sector and prior_sector != sector_name:
                errors.append(f"{ticker}: duplicate ticker in {prior_sector} and {sector_name}")
            ticker_to_sector[ticker] = sector_name

    return errors


def get_btc_on_chain_floors(dynamic: bool = True) -> dict[str, int]:
    """
    Return BTC on-chain floor estimates.

    Realized Price is refreshed from Coin Metrics when available. The static
    fallback keeps reporting resilient when the API or network is unavailable.
    """
    floors = BTC_ON_CHAIN_FLOORS.copy()

    if not dynamic:
        return floors

    try:
        from coinmetrics_api import fetch_coinmetrics_onchain

        df = fetch_coinmetrics_onchain("BTC-USD")
        if df is not None and not df.empty:
            realized_price = float(df["RealizedPrice"].dropna().iloc[-1])
            if realized_price > 0:
                floors["Realized Price"] = int(round(realized_price, -2))
    except Exception:
        pass

    return floors


if __name__ == "__main__":
    validation_errors = validate_sector_intelligence()
    if validation_errors:
        for error in validation_errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    stale_reviews = get_stale_sector_reviews()
    if stale_reviews:
        for sector_name, days_old in stale_reviews.items():
            print(f"STALE: {sector_name} reviewed {days_old} days ago")
        raise SystemExit(1)

    print("Sector intelligence config OK")
