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
LAST_UPDATED = "2026-08-11"

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
        "danger_zone_threshold": 0.55,
        "fetch_santiment": True,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["global-liquidity", "btc-etf-flows", "on-chain", "usd"],
        "strategy_params": {
            "exit_threshold": 0.55,
            "buy_threshold": 0.15,
            "moonbag_position": 0.0,
            "boost_position": 1.0,
            "stop_sma_days": 50,
        },
        "validation_metrics": {
            "avg_alpha": 0.04,
            "avg_protection": 0.9,
            "success_rate": 67,
            "assets": 3,
            "validated_on": "2026-06-26",
        },
        "validation_status": "thin_edge",
        "threshold_rationale": "Strategy sweep selected exit 0.55, buy 0.15, moonbag 0.0, boost 1.0, stop SMA 50: avg alpha +0.04x, avg protection +0.9%, 67% success rate.",
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
        "strategy_params": {
            "exit_threshold": 0.55,
            "buy_threshold": 0.15,
            "moonbag_position": 0.0,
            "boost_position": 1.0,
            "stop_sma_days": 20,
        },
        "validation_metrics": {
            "avg_alpha": 0.05,
            "avg_protection": 2.2,
            "success_rate": 67,
            "assets": 3,
            "validated_on": "2026-06-26",
        },
        "validation_status": "validated",
        "threshold_rationale": "Strategy sweep selected exit 0.55, buy 0.15, moonbag 0.0, boost 1.0, stop SMA 20: avg alpha +0.05x, avg protection +2.2%, 67% success rate.",
        "sector_context": "Crypto cross-pairs (Capital Waterfall). Tracks liquidity rotation from BTC into ETH and Alts. High risk means the altcoin cycle is exhausted against BTC.",
        "assets": {
            "ETH / BTC": "ETH-BTC",
            "ADA / BTC": "ADA-BTC",
            "ADA / ETH": "ADA-ETH",
        },
    },
    "Commodities": {
        "danger_zone_threshold": 0.60,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["real-yields", "usd", "inflation", "geopolitics"],
        "strategy_params": {
            "exit_threshold": 0.60,
            "buy_threshold": 0.35,
            "moonbag_position": 0.6,
            "boost_position": 1.4,
            "stop_sma_days": 50,
        },
        "validation_metrics": {
            "avg_alpha": 0.02,
            "avg_protection": 2.1,
            "success_rate": 100,
            "assets": 2,
            "validated_on": "2026-06-26",
        },
        "validation_status": "thin_edge",
        "threshold_rationale": "Strategy sweep selected exit 0.60, buy 0.35, moonbag 0.6, boost 1.4, stop SMA 50: avg alpha +0.02x, avg protection +2.1%, 100% success rate.",
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
        "strategy_params": {
            "exit_threshold": 0.55,
            "buy_threshold": 0.15,
            "moonbag_position": 0.0,
            "boost_position": 1.0,
            "stop_sma_days": 20,
        },
        "validation_metrics": {
            "avg_alpha": 0.19,
            "avg_protection": 3.4,
            "success_rate": 86,
            "assets": 7,
            "validated_on": "2026-06-26",
        },
        "validation_status": "validated",
        "threshold_rationale": "Strategy sweep selected exit 0.55, buy 0.15, moonbag 0.0, boost 1.0, stop SMA 20: avg alpha +0.19x, avg protection +3.4%, 86% success rate.",
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
        "danger_zone_threshold": 0.75,
        "fetch_santiment": False,
        "last_reviewed": LAST_UPDATED,
        "source_tags": ["rba-policy", "credit-growth", "housing", "domestic-demand"],
        "strategy_params": {
            "exit_threshold": 0.75,
            "buy_threshold": 0.30,
            "moonbag_position": 0.0,
            "boost_position": 1.4,
            "stop_sma_days": 50,
        },
        "validation_metrics": {
            "avg_alpha": 0.12,
            "avg_protection": -4.8,
            "success_rate": 67,
            "assets": 3,
            "validated_on": "2026-06-26",
        },
        "validation_status": "return_edge_drawdown_risk",
        "threshold_rationale": "Strategy sweep selected exit 0.75, buy 0.30, moonbag 0.0, boost 1.4, stop SMA 50: avg alpha +0.12x, avg protection -4.8%, 67% success rate.",
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
        "strategy_params": {
            "exit_threshold": 0.80,
            "buy_threshold": 0.30,
            "moonbag_position": 0.0,
            "boost_position": 1.4,
            "stop_sma_days": 20,
        },
        "validation_metrics": {
            "avg_alpha": 0.13,
            "avg_protection": -5.4,
            "success_rate": 50,
            "assets": 4,
            "validated_on": "2026-06-26",
        },
        "validation_status": "return_edge_drawdown_risk",
        "threshold_rationale": "Strategy sweep selected exit 0.80, buy 0.30, moonbag 0.0, boost 1.4, stop SMA 20: avg alpha +0.13x, avg protection -5.4%, 50% success rate.",
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
        "strategy_params": {
            "exit_threshold": 0.75,
            "buy_threshold": 0.15,
            "moonbag_position": 0.0,
            "boost_position": 1.0,
            "stop_sma_days": 20,
        },
        "validation_metrics": {
            "avg_alpha": 0.03,
            "avg_protection": -0.4,
            "success_rate": 100,
            "assets": 3,
            "validated_on": "2026-06-26",
        },
        "validation_status": "thin_edge",
        "threshold_rationale": "Strategy sweep selected exit 0.75, buy 0.15, moonbag 0.0, boost 1.0, stop SMA 20: avg alpha +0.03x, avg protection -0.4%, 100% success rate.",
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
        "strategy_params": {
            "exit_threshold": 0.85,
            "buy_threshold": 0.35,
            "moonbag_position": 0.0,
            "boost_position": 1.4,
            "stop_sma_days": 50,
        },
        "validation_metrics": {
            "avg_alpha": 0.09,
            "avg_protection": -3.2,
            "success_rate": 100,
            "assets": 4,
            "validated_on": "2026-06-26",
        },
        "validation_status": "return_edge_drawdown_risk",
        "threshold_rationale": "Strategy sweep selected exit 0.85, buy 0.35, moonbag 0.0, boost 1.4, stop SMA 50: avg alpha +0.09x, avg protection -3.2%, 100% success rate.",
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
        "strategy_params": {
            "exit_threshold": 0.70,
            "buy_threshold": 0.35,
            "moonbag_position": 0.0,
            "boost_position": 1.4,
            "stop_sma_days": 20,
        },
        "validation_metrics": {
            "avg_alpha": 0.06,
            "avg_protection": -3.3,
            "success_rate": 100,
            "assets": 2,
            "validated_on": "2026-06-26",
        },
        "validation_status": "return_edge_drawdown_risk",
        "threshold_rationale": "Strategy sweep selected exit 0.70, buy 0.35, moonbag 0.0, boost 1.4, stop SMA 20: avg alpha +0.06x, avg protection -3.3%, 100% success rate.",
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
        "strategy_params",
        "threshold_rationale",
        "sector_context",
        "assets",
    }
    strategy_required_keys = {
        "exit_threshold",
        "buy_threshold",
        "moonbag_position",
        "boost_position",
        "stop_sma_days",
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

        strategy_params = sector_data.get("strategy_params")
        if not isinstance(strategy_params, dict):
            errors.append(f"{sector_name}: strategy_params must be a dict")
        else:
            missing_strategy_keys = strategy_required_keys - set(strategy_params)
            if missing_strategy_keys:
                errors.append(f"{sector_name}: strategy_params missing keys {sorted(missing_strategy_keys)}")

            for key in ("exit_threshold", "buy_threshold"):
                value = strategy_params.get(key)
                if not isinstance(value, (int, float)) or not 0 < value < 1:
                    errors.append(f"{sector_name}: strategy_params.{key} must be between 0 and 1")

            for key in ("moonbag_position", "boost_position"):
                value = strategy_params.get(key)
                if not isinstance(value, (int, float)) or value < 0:
                    errors.append(f"{sector_name}: strategy_params.{key} must be >= 0")

            if strategy_params.get("stop_sma_days") not in (20, 50):
                errors.append(f"{sector_name}: strategy_params.stop_sma_days must be 20 or 50")

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
